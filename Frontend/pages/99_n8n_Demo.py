import os
import time as pytime
import uuid
import streamlit as st

from Frontend.api_client import api_get_json, api_post_json, invalidate

API_BASE = os.getenv("API_BASE", "").rstrip("/")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"

st.set_page_config(page_title="ByteBrains – n8n Demo", layout="wide")
st.title("n8n Demo Sender")
st.sidebar.success("Use this page only.\nOther pages are disabled in DEMO_MODE.")
st.caption("This page sends a demo payload through the SAME backend endpoint as production: "
           "POST /n8n/start/{meeting_id} with {meeting_id, transcript, profiles}.")

# --- optional: enforce that this page is only used in demo mode
if not DEMO_MODE:
    st.warning("DEMO_MODE is not enabled. This page is intended for demo deployments only.")

# -----------------------
# Helpers
# -----------------------
def demo_payload(meeting_id: str) -> dict:
    # ✅ Matches the production shape:
    # payload = { "meeting_id": str, "transcript": list[dict], "profiles": list[dict] }
    return {
        "meeting_id": meeting_id,
        "transcript": [
                {
                "speaker": "Adarsh Haridas",
                "start": 0.0,
                "end": 2.0,
                "text": "Hello, this is a demo."
                },
                {
                "speaker": "Farshad Soleimani",
                "start": 2.0,
                "end": 4.0,
                "text": "Great, testing n8n integration."
                }
            ],
        "profiles": [
            {
            "id": "trello-691cfb6877a5455b0f060b6b",
            "name": "Adarsh Haridas",
            "trello_id": "691cfb6877a5455b0f060b6b",
            "trello_username": "adarshharidas2",
            "email": "adarsh.haridas@stud.tu-darmstadt.de",
            "role": "AI Engineer",
            "skills": [
                "Python",
                "Voice Recognition"
            ],
            "notes": "",
            "photo": null,
            "status": "imported"
            },
            {
            "id": "trello-691dc049bee1daebfa96ccdb",
            "name": "Farshad Soleimani",
            "trello_id": "691dc049bee1daebfa96ccdb",
            "trello_username": "farshadsoleimani3",
            "email": "",
            "role": "n8n Workflow Engineer",
            "skills": [
                "n8n",
                "Python"
            ],
            "notes": "",
            "photo": null,
            "status": "imported"
            },
            {
            "id": "trello-691cc9c0b8b51e2811fe2bf4",
            "name": "Tabia Karim",
            "trello_id": "691cc9c0b8b51e2811fe2bf4",
            "trello_username": "tabiakarim",
            "email": "tabia.karim@stud.tu-darmstadt.de",
            "role": "Frontend Developer",
            "skills": [
                "Python",
                "Streamlit",
                "C++",
                "ROS2"
            ],
            "notes": "",
            "photo": null,
            "status": "imported"
            }
        ]
    }

def api_get_n8n_status(meeting_id: str) -> dict:
    return api_get_json(
        f"/n8n/status/{meeting_id}",
        name=f"n8n_status__{meeting_id}",
        ttl_s=0,       # don’t cache status
        timeout=10,
    )

def apply_status(latest: dict | None):
    if not latest:
        st.info("No status yet.")
        return
    # show whatever n8n sends back
    st.write("**Latest status**")
    st.json(latest)

# -----------------------
# Session State
# -----------------------
if "demo_meeting_id" not in st.session_state:
    st.session_state.demo_meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
if "n8n_started" not in st.session_state:
    st.session_state.n8n_started = False
if "last_poll_ts" not in st.session_state:
    st.session_state.last_poll_ts = 0.0
if "n8n_result" not in st.session_state:
    st.session_state.n8n_result = None

# -----------------------
# UI
# -----------------------
col1, col2, col3 = st.columns([2, 2, 2])

with col1:
    meeting_id = st.text_input("Meeting ID", value=st.session_state.demo_meeting_id)
    st.session_state.demo_meeting_id = meeting_id.strip() or st.session_state.demo_meeting_id

with col2:
    if st.button("New Meeting ID", use_container_width=True):
        st.session_state.demo_meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
        st.session_state.n8n_started = False
        st.session_state.n8n_result = None
        st.session_state.last_poll_ts = 0.0
        st.rerun()

with col3:
    st.write("")
    st.write("")
    st.write(f"Backend: `{API_BASE}`")

st.divider()

# --- Send button
payload = demo_payload(st.session_state.demo_meeting_id)

with st.expander("Payload preview (exact shape)", expanded=False):
    st.json(payload)

send = st.button("Send demo payload to n8n", type="primary", use_container_width=True)

if send:
    invalidate(f"n8n_status__{meeting_id}")
    st.session_state.n8n_result = None

    res = api_post_json(
        f"/n8n/start/{meeting_id}",
        payload,
        name=f"n8n_start__{meeting_id}",
        timeout=30,
    )

    if res.get("_rate_limited"):
        st.session_state.n8n_started = False  # allow retry
        st.warning(f"429 rate limited. Wait ~{res.get('_wait_s', 10)}s and click again.")
        st.stop()

    if res.get("_error"):
        st.session_state.n8n_started = False  # allow retry
        st.error("Failed to start n8n workflow.")
        st.code(f"HTTP {res.get('_status')}: {res.get('_text')}")
        st.stop()

    st.session_state.n8n_started = True
    st.success("Sent ✅ Now poll status below.")

st.divider()

# --- Poll status (manual + cooldown)
POLL_EVERY = 10.0
now = pytime.time()
remaining = max(0, int(POLL_EVERY - (now - st.session_state.last_poll_ts)))
can_poll = (now - st.session_state.last_poll_ts) >= POLL_EVERY

cA, cB = st.columns([1, 3])
with cA:
    refresh = st.button("↻ Refresh status", use_container_width=True, disabled=not can_poll)
    st.caption(f"Next allowed refresh in {remaining}s")
with cB:
    st.caption("Manual refresh avoids Streamlit rerun-spam. n8n updates are pulled when you refresh.")

if refresh:
    st.session_state.last_poll_ts = pytime.time()
    status_data = api_get_n8n_status(meeting_id)

    if status_data.get("_rate_limited"):
        st.warning(f"429 rate limited. Wait ~{status_data.get('_wait_s', 10)}s and refresh again.")
        st.stop()

    latest = status_data.get("latest")
    result = status_data.get("result")

    apply_status(latest)

    if result:
        st.session_state.n8n_result = result

# --- Show final result if present
if st.session_state.n8n_result:
    st.subheader("Final Result (from /n8n/status)")
    st.json(st.session_state.n8n_result)
else:
    st.info("No final result yet. Click Refresh status after n8n finishes.")