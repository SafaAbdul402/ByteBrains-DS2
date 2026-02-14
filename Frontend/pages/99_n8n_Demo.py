import os
import time
import uuid
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"

st.set_page_config(page_title="ByteBrains – n8n Demo", layout="wide")
st.title("n8n Demo Sender")

if not API_BASE:
    st.error("API_BASE is not set. Add it to your environment variables.")
    st.stop()

# --- Demo-only hint (optional)
if not DEMO_MODE:
    st.warning("DEMO_MODE is off. This page is intended for demo deployments.")

# -----------------------
# Payload (exact same shape)
# -----------------------
def build_demo_payload(meeting_id: str) -> dict:
    # ✅ EXACT shape used by production:
    # {"meeting_id": str, "transcript": [..], "profiles": [..]}
    return {
        "meeting_id": meeting_id,
        "transcript": [
            {"speaker": "Adarsh Haridas", "start": 0.0, "end": 2.0, "text": "Hello, this is a demo."},
            {"speaker": "Farshad Soleimani", "start": 2.0, "end": 4.0, "text": "Great, testing n8n integration."},
        ],
        "profiles": [
            {
                "id": "trello-691cfb6877a5455b0f060b6b",
                "name": "Adarsh Haridas",
                "trello_id": "691cfb6877a5455b0f060b6b",
                "trello_username": "adarshharidas2",
                "email": "adarsh.haridas@stud.tu-darmstadt.de",
                "role": "AI Engineer",
                "skills": ["Python", "Voice Recognition"],
                "notes": "",
                "photo": None,
                "status": "imported",
            },
            {
                "id": "trello-691dc049bee1daebfa96ccdb",
                "name": "Farshad Soleimani",
                "trello_id": "691dc049bee1daebfa96ccdb",
                "trello_username": "farshadsoleimani3",
                "email": "",
                "role": "n8n Workflow Engineer",
                "skills": ["n8n", "Python"],
                "notes": "",
                "photo": None,
                "status": "imported",
            },
        ],
    }

# -----------------------
# Very small helpers
# -----------------------
def post_start(meeting_id: str, payload: dict) -> tuple[bool, str]:
    url = f"{API_BASE}/n8n/start/{meeting_id}"
    try:
        r = requests.post(url, json=payload, timeout=15)
    except Exception as e:
        return False, f"Network error: {e}"

    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        return False, f"429 rate-limited. Retry-After={ra or 'n/a'} Body={r.text[:200]}"

    if not r.ok:
        return False, f"HTTP {r.status_code}: {r.text[:400]}"

    return True, r.text[:400] or "ok"

def get_status(meeting_id: str) -> tuple[bool, dict | str]:
    url = f"{API_BASE}/n8n/status/{meeting_id}"
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        return False, f"Network error: {e}"

    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        return False, f"429 rate-limited. Retry-After={ra or 'n/a'} Body={r.text[:200]}"

    if not r.ok:
        return False, f"HTTP {r.status_code}: {r.text[:400]}"

    try:
        return True, r.json()
    except Exception:
        return False, f"Bad JSON response: {r.text[:400]}"

# -----------------------
# Session state
# -----------------------
if "meeting_id" not in st.session_state:
    st.session_state.meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
if "sent" not in st.session_state:
    st.session_state.sent = False
if "result" not in st.session_state:
    st.session_state.result = None
if "last_start_ts" not in st.session_state:
    st.session_state.last_start_ts = 0.0
if "start_cooldown_s" not in st.session_state:
    st.session_state.start_cooldown_s = 5.0

# -----------------------
# UI
# -----------------------
c1, c2, c3 = st.columns([2, 1, 2])
with c1:
    st.session_state.meeting_id = st.text_input("Meeting ID", st.session_state.meeting_id).strip() or st.session_state.meeting_id
with c2:
    if st.button("New ID", use_container_width=True):
        st.session_state.meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
        st.session_state.sent = False
        st.session_state.result = None
        st.rerun()
with c3:
    st.caption(f"Backend: {API_BASE}")

payload = build_demo_payload(st.session_state.meeting_id)

with st.expander("Payload preview", expanded=False):
    st.json(payload)

st.divider()

now = time.time()
start_remaining = max(0, int(st.session_state.start_cooldown_s - (now - st.session_state.last_start_ts)))
can_start = (start_remaining == 0) and (not st.session_state.sent)

send = st.button("Send to n8n", type="primary", use_container_width=True, disabled=not can_start)

if not can_start:
    if st.session_state.sent:
        st.info("Already sent for this Meeting ID. Click **New ID** to send again.")
    else:
        st.caption(f"Start cooldown: try again in {start_remaining}s")

if send:
    st.session_state.last_start_ts = time.time()
    ok, msg = post_start(st.session_state.meeting_id, payload)
    if not ok:
        # allow retry if it failed
        st.session_state.sent = False
        st.error(msg)
        st.stop()
    st.session_state.sent = True
    st.success("Sent ✅")

st.divider()

now = time.time()
status_remaining = max(0, int(st.session_state.status_cooldown_s - (now - st.session_state.last_status_ts)))
can_poll = st.session_state.sent and (status_remaining == 0)

refresh = st.button("Refresh status", use_container_width=True, disabled=not can_poll)

if st.session_state.sent and not can_poll:
    st.caption(f"Next status refresh in {status_remaining}s")

if refresh:
    st.session_state.last_status_ts = time.time()
    ok, data = get_status(st.session_state.meeting_id)
    if not ok:
        st.error(data)
        st.stop()

    latest = (data or {}).get("latest")
    result = (data or {}).get("result")

    st.subheader("Latest")
    st.json(latest or {})

    if result:
        st.subheader("Final result")
        st.session_state.result = result
        st.json(result)

if st.session_state.result and not refresh:
    st.subheader("Final result")
    st.json(st.session_state.result)