import json
import os
from datetime import datetime
from typing import Any, Dict, List
import pandas as pd
import requests
import streamlit as st
from Backend.config import MEETINGS_PATH, RUNS_DIR
from pathlib import Path
from Frontend.auth import require_password

require_password()

meeting_id = st.session_state.get("meeting_id")
if not meeting_id:
    st.error("No meeting selected.")

run_dir = RUNS_DIR / meeting_id
transcript_path = run_dir / "vr_transcript.json"

st.set_page_config(page_title="Meetings / Results", layout="wide")

# ---------------------------
# Config
# ---------------------------
DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "..", "data"))
MEETINGS_FILE = str(MEETINGS_PATH)

# Optional: n8n webhook URL (store locally in .streamlit/secrets.toml)
# [n8n]
# trello_webhook="https://YOUR_N8N_WEBHOOK_URL"
try:
    N8N_TRELLO_WEBHOOK = st.secrets["n8n"]["trello_webhook"]
except Exception:
    N8N_TRELLO_WEBHOOK = ""

# ---------------------------
# Helpers: persistence
# ---------------------------
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_meetings() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not os.path.exists(MEETINGS_FILE):
        return []
    try:
        with open(MEETINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_meetings(meetings: List[Dict[str, Any]]) -> None:
    ensure_data_dir()
    with open(MEETINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(meetings, f, indent=2, ensure_ascii=False)

def get_meeting_label(m: Dict[str, Any]) -> str:
    dt = m.get("created_at", "")
    title = m.get("title", "Untitled meeting")
    return f"{title}  —  {dt}"

def default_demo_meeting() -> Dict[str, Any]:
    return {
        "meeting_id": f"demo-{int(datetime.now().timestamp())}",
        "title": "Demo Meeting",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": "• Discussed project scope\n• Agreed on next steps\n• Open questions listed",
        "email_draft": "Hi all,\n\nthanks for the meeting today. Here are the next steps...\n\nBest,\nByteBrains",
        "tasks": [
            {
                "task": "Finalize UI layout",
                "assigned_to": "Max 1",
                "deadline": "2026-01-20",
                "reason": "Owner of UI module",
                "status": "Open",
            },
            {
                "task": "Prepare n8n webhook endpoint",
                "assigned_to": "Max 2",
                "deadline": "2026-01-21",
                "reason": "Owner of automation pipeline",
                "status": "Open",
            },
        ],
        "trello_sync": {"last_status": "Not sent", "last_timestamp": None},
    }

# ---------------------------
# Session state init
# ---------------------------
if "meetings" not in st.session_state:
    st.session_state.meetings = load_meetings()

if "selected_meeting_id" not in st.session_state:
    st.session_state.selected_meeting_id = None

# If empty, create one demo entry so the page doesn't look blank
if len(st.session_state.meetings) == 0:
    st.session_state.meetings = [default_demo_meeting()]
    save_meetings(st.session_state.meetings)

# ---------------------------
# UI Layout
# ---------------------------
st.title("My Meetings / Results")

# Top actions row
top_left, top_right = st.columns([3, 1])
with top_left:
    st.caption("Browse processed meetings and view notes, tasks, and email drafts.")
with top_right:
    if st.button("➕ Add demo meeting", use_container_width=True):
        st.session_state.meetings.insert(0, default_demo_meeting())
        save_meetings(st.session_state.meetings)
        st.rerun()

# Main layout
col_list, col_details = st.columns([1, 2], gap="large")

with col_list:
    st.subheader("Meetings Database")

    # Search
    q = st.text_input("Search", placeholder="Search by title…")

    filtered = st.session_state.meetings
    if q.strip():
        filtered = [
            m for m in st.session_state.meetings
            if q.lower() in (m.get("title", "") + " " + m.get("created_at", "")).lower()
        ]

    if not filtered:
        st.info("No meetings match your search.")
    else:
        labels = [get_meeting_label(m) for m in filtered]
        idx = st.selectbox("Select a meeting", range(len(labels)),
                           format_func=lambda i: labels[i])
        selected = filtered[idx]
        st.session_state.selected_meeting_id = selected.get("meeting_id")

    st.divider()

    if st.session_state.selected_meeting_id:
        # Delete meeting
        if st.button("🗑️ Delete selected meeting", type="secondary", use_container_width=True):
            st.session_state.meetings = [
                m for m in st.session_state.meetings
                if m.get("meeting_id") != st.session_state.selected_meeting_id
            ]
            st.session_state.selected_meeting_id = None
            save_meetings(st.session_state.meetings)
            st.rerun()

with col_details:
    if not st.session_state.selected_meeting_id:
        st.info("Select a meeting on the left to view results.")
    else:
        meeting = next(
            (m for m in st.session_state.meetings if m.get("meeting_id") == st.session_state.selected_meeting_id),
            None,
        )

        if not meeting:
            st.warning("Meeting not found.")
        else:
            # Header
            st.subheader(meeting.get("title", "Meeting"))
            st.caption(f"Meeting ID: {meeting.get('meeting_id')} • {meeting.get('created_at')}")

            with st.expander("Transcript", expanded=False):
                if transcript_path.exists():
                    data = json.loads(transcript_path.read_text(encoding="utf-8"))
                    segments = data.get("segments", [])
                    for seg in segments:
                        st.markdown(f"**{seg.get('speaker_id','?')}**: {seg.get('text','')}")
                else:
                    st.info("No transcript file found yet for this meeting.")

            # --- Notes / Summary
            st.markdown("### Meeting Notes / Minutes")
            notes = meeting.get("notes", "")
            st.text_area("Notes", value=notes, height=160, key="notes_view", label_visibility="collapsed")

            # --- Tasks table
            st.markdown("### Action Items / Tasks")
            tasks = meeting.get("tasks", [])
            df = pd.DataFrame(tasks) if tasks else pd.DataFrame(columns=["task", "assigned_to", "deadline", "reason", "status"])

            # show table
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

            # Buttons row for tasks
            b1, b2 = st.columns([1, 1])
            with b1:
                assign_clicked = st.button("Assign in Trello", type="primary", use_container_width=True)
            with b2:
                if st.button("Export tasks JSON", use_container_width=True):
                    st.download_button(
                        "Download tasks.json",
                        data=json.dumps(tasks, indent=2, ensure_ascii=False),
                        file_name=f"{meeting.get('meeting_id')}_tasks.json",
                        mime="application/json",
                        use_container_width=True,
                    )

            # Trello integration (n8n webhook)
            if assign_clicked:
                if not N8N_TRELLO_WEBHOOK:
                    st.warning("n8n Trello webhook URL is not set yet (add it to .streamlit/secrets.toml).")
                else:
                    payload = {
                        "meeting_id": meeting.get("meeting_id"),
                        "title": meeting.get("title"),
                        "created_at": meeting.get("created_at"),
                        "tasks": tasks,
                        # optionally send mapping / profiles later:
                        # "speaker_mapping": {...},
                        # "profiles": [...]
                    }
                    try:
                        r = requests.post(N8N_TRELLO_WEBHOOK, json=payload, timeout=30)
                        ok = 200 <= r.status_code < 300
                        meeting.setdefault("trello_sync", {})
                        meeting["trello_sync"]["last_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        meeting["trello_sync"]["last_status"] = f"{r.status_code} {'OK' if ok else 'Error'}"

                        save_meetings(st.session_state.meetings)

                        if ok:
                            st.success("Sent tasks to n8n for Trello assignment ✅")
                        else:
                            st.error(f"n8n returned status {r.status_code}: {r.text[:200]}")
                    except Exception as e:
                        st.error(f"Failed to reach n8n webhook: {e}")

            # --- Email draft
            st.markdown("### Follow-up Email Draft")
            email_text = meeting.get("email_draft", "")
            st.text_area("Email", value=email_text, height=180, key="email_view", label_visibility="collapsed")

            # Copy button (best-effort; works locally when 'pyperclip' installed)
            copy_col1, copy_col2 = st.columns([1, 2])
            with copy_col1:
                if st.button("Copy to clipboard", use_container_width=True):
                    try:
                        import pyperclip  # optional dependency
                        pyperclip.copy(st.session_state.email_view)
                        st.success("Copied ✅")
                    except Exception:
                        st.info("Clipboard copy needs 'pyperclip'. Alternatively, manually copy from the text box.")

            with copy_col2:
                trello_info = meeting.get("trello_sync", {})
                st.caption(f"Trello sync: {trello_info.get('last_status', '—')} • {trello_info.get('last_timestamp', '—')}")