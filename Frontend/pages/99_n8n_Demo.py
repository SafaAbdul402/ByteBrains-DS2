import os
import time
import uuid
import json
from pathlib import Path

import requests
import streamlit as st


API_BASE = os.getenv("API_BASE", "").rstrip("/")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
N8N_ROUTE_SECRET = os.getenv("N8N_ROUTE_SECRET", "devsecret")

st.set_page_config(page_title="ByteBrains – n8n Demo", layout="wide")
st.title("n8n Demo Sender")

if not API_BASE:
    st.error("API_BASE is not set. Add it to your environment variables.")
    st.stop()

if not DEMO_MODE:
    st.warning("DEMO_MODE is off. This page is intended for demo deployments.")

# Frontend/pages/99_n8n_Demo.py -> parents[1] = Frontend/
DEMO_TRANSCRIPTS_DIR = Path(__file__).resolve().parents[1] / "demo_transcripts"

DEMO_OPTIONS = {
    "Short demo (~3 min)": DEMO_TRANSCRIPTS_DIR / "short_3min.json",
    "Medium demo (~16 min)": DEMO_TRANSCRIPTS_DIR / "medium_16min.json",
    "Long demo (~29 min)": DEMO_TRANSCRIPTS_DIR / "long_29min.json",
}
PROFILES_PATH = DEMO_TRANSCRIPTS_DIR / "profiles_complete.json"


# -----------------------
# Loaders
# -----------------------
@st.cache_data
def load_demo_transcript(path: Path) -> list[dict]:
    """
    Accepts either:
      A) [ {...}, {...} ]
      B) { "transcript": [ {...}, {...} ] }
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict) and isinstance(data.get("transcript"), list):
        segments = data["transcript"]
    elif isinstance(data, list):
        segments = data
    else:
        raise ValueError(f"{path.name} must be a list OR {{'transcript': [...]}}")

    out = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        # minimal requirements
        if "speaker" in seg and "text" in seg:
            out.append(seg)
    return out


@st.cache_data
def load_profiles(path: Path) -> list[dict]:
    """
    Accepts:
      A) { "team": [..] }  (your profiles_complete.json)
      B) { "profiles": [..] }
      C) [..]
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if isinstance(data.get("team"), list):
            return [p for p in data["team"] if isinstance(p, dict)]
        if isinstance(data.get("profiles"), list):
            return [p for p in data["profiles"] if isinstance(p, dict)]
        return []
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    return []


def transcript_duration_seconds(segments: list[dict]) -> float:
    ends = []
    for s in segments:
        try:
            ends.append(float(s.get("end", 0)))
        except Exception:
            pass
    return max(ends) if ends else 0.0


def fmt_minutes(seconds: float) -> str:
    return f"{seconds / 60.0:.1f} min"


# -----------------------
# API calls
# -----------------------
def post_start(meeting_id: str, payload: dict) -> tuple[bool, str]:
    url = f"{API_BASE}/n8n/{N8N_ROUTE_SECRET}/start/{meeting_id}"
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
    url = f"{API_BASE}/n8n/{N8N_ROUTE_SECRET}/status/{meeting_id}"
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


def build_demo_payload(meeting_id: str, transcript: list[dict], profiles: list[dict]) -> dict:
    return {
        "meeting_id": meeting_id,
        "transcript": transcript,
        "profiles": profiles,
    }


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
if "last_status_ts" not in st.session_state:
    st.session_state.last_status_ts = 0.0
if "status_cooldown_s" not in st.session_state:
    st.session_state.status_cooldown_s = 5.0
if "demo_choice" not in st.session_state:
    st.session_state.demo_choice = "Medium demo (~16 min)"
if "auto_send" not in st.session_state:
    st.session_state.auto_send = False


# -----------------------
# UI header
# -----------------------
c1, c2, c3 = st.columns([2, 1, 2])
with c1:
    st.session_state.meeting_id = st.text_input("Meeting ID", st.session_state.meeting_id).strip() or st.session_state.meeting_id
with c2:
    if st.button("New ID", use_container_width=True):
        st.session_state.meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
        st.session_state.sent = False
        st.session_state.result = None
        st.session_state.last_start_ts = 0.0
        st.session_state.last_status_ts = 0.0
        st.session_state.auto_send = False
        st.rerun()
with c3:
    st.caption(f"Backend: {API_BASE}")


# -----------------------
# Choose transcript
# -----------------------
st.subheader("Choose demo transcript")

choice = st.radio(
    "Demo length",
    list(DEMO_OPTIONS.keys()),
    index=list(DEMO_OPTIONS.keys()).index(st.session_state.demo_choice)
    if st.session_state.demo_choice in DEMO_OPTIONS else 1,
    horizontal=True,
)
st.session_state.demo_choice = choice

selected_path = DEMO_OPTIONS[choice]
if not selected_path.exists():
    st.error(f"Missing demo transcript file: {selected_path}")
    st.stop()
if not PROFILES_PATH.exists():
    st.error(f"Missing profiles file: {PROFILES_PATH}")
    st.stop()

try:
    selected_transcript = load_demo_transcript(selected_path)
except Exception as e:
    st.error(f"Could not load {selected_path.name}: {e}")
    st.stop()

profiles = load_profiles(PROFILES_PATH)

dur_s = transcript_duration_seconds(selected_transcript)
st.caption(f"Loaded **{selected_path.name}** • {len(selected_transcript)} segments • ~{fmt_minutes(dur_s)} • profiles={len(profiles)}")

payload = build_demo_payload(st.session_state.meeting_id, selected_transcript, profiles)

with st.expander("Payload preview", expanded=False):
    st.json(payload)

st.divider()

# -----------------------
# Send controls
# -----------------------
now = time.time()
start_remaining = max(0, int(st.session_state.start_cooldown_s - (now - st.session_state.last_start_ts)))
can_start = (start_remaining == 0) and (not st.session_state.sent)

st.subheader("Quick run buttons")
b1, b2, b3 = st.columns(3)
with b1:
    if st.button("▶ Run short (~3 min)", use_container_width=True):
        st.session_state.demo_choice = "Short demo (~3 min)"
        st.session_state.auto_send = True
        st.rerun()
with b2:
    if st.button("▶ Run medium (~16 min)", use_container_width=True):
        st.session_state.demo_choice = "Medium demo (~16 min)"
        st.session_state.auto_send = True
        st.rerun()
with b3:
    if st.button("▶ Run long (~29 min)", use_container_width=True):
        st.session_state.demo_choice = "Long demo (~29 min)"
        st.session_state.auto_send = True
        st.rerun()

st.divider()

send = st.button("Send to n8n", type="primary", use_container_width=True, disabled=not can_start)

if st.session_state.sent:
    st.info("Already sent for this Meeting ID. Click **New ID** to send again.")
elif not can_start:
    st.caption(f"Start cooldown: try again in {start_remaining}s")

def do_send():
    ok, msg = post_start(st.session_state.meeting_id, payload)
    if not ok:
        st.session_state.sent = False
        st.session_state.auto_send = False
        st.error(msg)
        st.stop()
    st.session_state.last_start_ts = time.time()
    st.session_state.sent = True
    st.session_state.auto_send = False
    st.success("Sent ✅")

if send and can_start:
    do_send()

# Auto-send (from quick buttons)
if st.session_state.auto_send and can_start and not st.session_state.sent:
    do_send()

st.divider()

# -----------------------
# Status polling
# -----------------------
now = time.time()
status_remaining = max(0, int(st.session_state.status_cooldown_s - (now - st.session_state.last_status_ts)))
can_poll = st.session_state.sent and (status_remaining == 0)

refresh = st.button("Refresh status", use_container_width=True, disabled=not can_poll)

if st.session_state.sent and not can_poll:
    st.caption(f"Next status refresh in {status_remaining}s")

if refresh:
    ok, data = get_status(st.session_state.meeting_id)
    if not ok:
        st.error(data)
        st.stop()

    st.session_state.last_status_ts = time.time()

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