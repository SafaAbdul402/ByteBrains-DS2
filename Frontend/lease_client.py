# Frontend/lease_client.py
import os, time, uuid
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")
SESSION = requests.Session()

HB_EVERY_S = 30

def acquire_or_block():
    if not API_BASE:
        st.error("API_BASE is not set.")
        st.stop()

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    now = time.time()

    # 1) acquire once per browser session
    if not st.session_state.get("lease_acquired", False):
        endpoint = "/lease/acquire"
        do_call = True
    else:
        # 2) heartbeat only every HB_EVERY_S
        last_hb = st.session_state.get("_lease_last_hb", 0.0)
        do_call = (now - last_hb) >= HB_EVERY_S
        endpoint = "/lease/heartbeat"

    # If we don't need to call, do nothing (IMPORTANT)
    if not do_call:
        return

    try:
        r = SESSION.post(
            f"{API_BASE}{endpoint}",
            json={"session_id": st.session_state.session_id},
            timeout=5,
        )
    except Exception as e:
        st.error(f"Backend not reachable: {e}")
        st.stop()

    if r.status_code == 503:
        st.error("🚦 Too many people are using the app right now. Please try again in a minute.")
        st.stop()

    if r.status_code == 429:
        # show the body, but don't hard-stop forever
        st.warning("Backend rate limited this page load. Please wait a few seconds and retry.")
        st.code(r.text[:400])
        st.stop()

    if not r.ok:
        st.error(f"Backend error: HTTP {r.status_code}")
        st.code(r.text[:400])
        st.stop()

    # mark state only AFTER success
    if endpoint == "/lease/acquire":
        st.session_state.lease_acquired = True
    else:
        st.session_state["_lease_last_hb"] = now