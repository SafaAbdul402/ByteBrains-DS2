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

DEMO_TRANSCRIPTS_DIR = Path(__file__).resolve().parents[1] / "demo_transcripts"

DEMO_OPTIONS = {
    "short": ("Short demo (~3 min)", DEMO_TRANSCRIPTS_DIR / "short_3min.json"),
    "medium": ("Medium demo (~16 min)", DEMO_TRANSCRIPTS_DIR / "medium_16min.json"),
    "long": ("Long demo (~29 min)", DEMO_TRANSCRIPTS_DIR / "long_29min.json"),
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
        if isinstance(seg, dict) and "speaker" in seg and "text" in seg:
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


def build_demo_payload(meeting_id: str, transcript: list[dict], profiles: list[dict]) -> dict:
    return {"meeting_id": meeting_id, "transcript": transcript, "profiles": profiles}


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


# -----------------------
# Header
# -----------------------
c1, c2, c3 = st.columns([2, 1, 2])
with c1:
    st.session_state.meeting_id = (
        st.text_input("Meeting ID", st.session_state.meeting_id).strip()
        or st.session_state.meeting_id
    )
with c2:
    if st.button("New ID", use_container_width=True):
        st.session_state.meeting_id = f"demo-{uuid.uuid4().hex[:8]}"
        st.session_state.sent = False
        st.session_state.result = None
        st.session_state.last_start_ts = 0.0
        st.session_state.last_status_ts = 0.0
        st.rerun()
with c3:
    st.caption(f"Backend: {API_BASE}")


# -----------------------
# Preload data (once)
# -----------------------
if not PROFILES_PATH.exists():
    st.error(f"Missing profiles file: {PROFILES_PATH}")
    st.stop()

profiles = load_profiles(PROFILES_PATH)
if not profiles:
    st.warning("Loaded 0 profiles from profiles_complete.json. Payload will still send, but n8n role-mapping may be weaker.")

payloads: dict[str, dict] = {}
meta: dict[str, dict] = {}

for key, (label, path) in DEMO_OPTIONS.items():
    if not path.exists():
        st.error(f"Missing demo transcript file: {path}")
        st.stop()

    segments = load_demo_transcript(path)
    dur_s = transcript_duration_seconds(segments)
    payloads[key] = build_demo_payload(st.session_state.meeting_id, segments, profiles)
    meta[key] = {"label": label, "path": path.name, "count": len(segments), "dur": fmt_minutes(dur_s)}


# -----------------------
# Send controls (ONLY buttons)
# -----------------------
st.subheader("Run a demo")
st.caption("Each button sends its transcript immediately. No extra 'Send' button.")

now = time.time()
start_remaining = max(0, int(st.session_state.start_cooldown_s - (now - st.session_state.last_start_ts)))
can_start = (start_remaining == 0) and (not st.session_state.sent)

if st.session_state.sent:
    st.info("Already sent for this Meeting ID. Click **New ID** to send again.")
elif not can_start:
    st.caption(f"Start cooldown: try again in {start_remaining}s")

b1, b2, b3 = st.columns(3)

def render_demo_column(col, key: str):
    label = meta[key]["label"]
    info = f"{meta[key]['path']} • {meta[key]['count']} segments • ~{meta[key]['dur']}"

    with col:
        st.markdown(f"**{label}**")
        st.caption(info)

        if st.button(f"▶ Run {key}", use_container_width=True, disabled=not can_start):
            ok, msg = post_start(st.session_state.meeting_id, payloads[key])
            if not ok:
                st.session_state.sent = False
                st.error(msg)
                st.stop()

            st.session_state.last_start_ts = time.time()
            st.session_state.sent = True
            st.success("Sent ✅")

        with st.expander("Payload preview", expanded=False):
            st.json(payloads[key])

render_demo_column(b1, "short")
render_demo_column(b2, "medium")
render_demo_column(b3, "long")

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