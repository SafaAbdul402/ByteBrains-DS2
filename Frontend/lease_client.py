# Frontend/lease_client.py
import os, time, uuid
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")

HEARTBEAT_EVERY_S = int(os.getenv("LEASE_HEARTBEAT_EVERY_S", "30"))

def acquire_or_block() -> None:
    # One id per browser session
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    now = time.time()
    last_hb = st.session_state.get("_lease_last_hb", 0.0)

    # Only heartbeat every HEARTBEAT_EVERY_S seconds to avoid hammering
    do_heartbeat = (now - last_hb) >= HEARTBEAT_EVERY_S

    # If we never acquired (or we lost the lease), try acquire.
    has_lease = st.session_state.get("lease_acquired", False)
    endpoint = "/lease/heartbeat" if (has_lease and do_heartbeat) else "/lease/acquire"

    try:
        r = requests.post(
            f"{API_BASE}{endpoint}",
            json={"session_id": st.session_state.session_id},
            timeout=5,
        )
    except Exception as e:
        st.error(f"Backend not reachable: {e}")
        st.stop()

    if r.status_code == 503:
        # IMPORTANT: don't mark as acquired
        st.session_state["lease_acquired"] = False
        st.error("🚦 Too many people are using the app right now. Please try again in a minute.")
        st.stop()

    if not r.ok:
        st.session_state["lease_acquired"] = False
        st.error(f"Backend error: HTTP {r.status_code}")
        st.code(r.text[:400])
        st.stop()

    # Parse response (heartbeat can return missing=True)
    try:
        data = r.json()
    except Exception:
        data = {}

    # If heartbeat says missing, immediately re-acquire next rerun.
    if endpoint.endswith("/heartbeat") and data.get("missing"):
        st.session_state["lease_acquired"] = False
        # don't stop the app; next rerun will re-acquire
        return

    # Success
    st.session_state["lease_acquired"] = True
    if endpoint.endswith("/heartbeat"):
        st.session_state["_lease_last_hb"] = now