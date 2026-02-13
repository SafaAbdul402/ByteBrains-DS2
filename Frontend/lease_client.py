# Frontend/lease_client.py
import os, time, uuid
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")

LEASE_HB_EVERY_S = int(os.getenv("LEASE_HB_EVERY_S", "30"))  # client throttle

def acquire_or_block():
    # one id per browser session
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    now = time.time()
    last_hb = st.session_state.get("_lease_last_hb", 0.0)
    lease_acquired = st.session_state.get("_lease_acquired", False)

    # ✅ If we already have a lease and it's not time to heartbeat, DO NOTHING.
    if lease_acquired and (now - last_hb) < LEASE_HB_EVERY_S:
        return

    endpoint = "/lease/acquire" if not lease_acquired else "/lease/heartbeat"

    try:
        r = requests.post(
            f"{API_BASE}{endpoint}",
            json={"session_id": st.session_state.session_id},
            timeout=5,
        )
    except Exception as e:
        st.error(f"Backend not reachable: {e}")
        st.stop()

    # Capacity reached (your feature)
    if r.status_code == 503:
        st.error("🚦 Too many people are using the app right now. Please try again in a minute.")
        st.stop()

    # ✅ If rate limited, show friendly message and stop WITHOUT rerun loops
    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        wait_s = int(ra) if (ra and ra.isdigit()) else 10
        st.warning(f"Backend rate limited (429). Please wait {wait_s}s and refresh.")
        st.stop()

    if not r.ok:
        st.error(f"Backend error: HTTP {r.status_code}")
        st.code(r.text[:400])
        st.stop()

    # heartbeat response might say missing lease → reacquire next time
    data = {}
    try:
        data = r.json()
    except Exception:
        pass

    if endpoint == "/lease/acquire":
        st.session_state["_lease_acquired"] = True
        st.session_state["_lease_last_hb"] = now
    else:
        # heartbeat
        if data.get("missing"):
            st.session_state["_lease_acquired"] = False
        else:
            st.session_state["_lease_last_hb"] = now