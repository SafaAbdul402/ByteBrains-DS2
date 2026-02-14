import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
import os

from Backend.config import RUNS_DIR
from Backend.store import load_meetings, save_meetings
#from Frontend.lease_client import acquire_or_block
#acquire_or_block()
# from Frontend.auth import require_password

# MUST be first Streamlit call
st.set_page_config(page_title="Meetings / Results", layout="wide")
# require_password()
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
if DEMO_MODE:
    st.set_page_config(page_title="ByteBrains – Demo", layout="centered")
    st.title("Demo deployment")
    st.info("This deployment is for n8n testing only. Please use the **n8n Demo** page.")
    if st.button("Go to n8n Demo", type="primary", use_container_width=True):
        st.switch_page("pages/99_n8n_Demo.py")
    st.stop()

# ---------------------------
# Config
# ---------------------------
try:
    N8N_TRELLO_WEBHOOK = st.secrets["n8n"]["trello_webhook"]
except Exception:
    N8N_TRELLO_WEBHOOK = ""

# ---------------------------
# Helpers
# ---------------------------
def meeting_label(m: Dict[str, Any]) -> str:
    title = (m.get("title") or "Untitled meeting").strip()
    created_at = (m.get("created_at") or "").strip()
    mid = (m.get("meeting_id") or "").strip()
    suffix = f" • {created_at}" if created_at else ""
    return f"{title}{suffix} ({mid})"

def find_meeting(meetings: List[Dict[str, Any]], meeting_id: str) -> Optional[Dict[str, Any]]:
    return next((m for m in meetings if m.get("meeting_id") == meeting_id), None)

def transcript_candidates(run_dir: Path) -> List[Path]:
    return [
        run_dir / "transcript_with_speakers.json",
        run_dir / "vr_transcript.json",
        run_dir / "transcript.json",
        run_dir / ".voice_internal" / "transcript_with_speakers.json",
        run_dir / ".voice_internal" / "vr_transcript.json",
    ]

def load_transcript(run_dir: Path) -> Optional[Any]:
    for p in transcript_candidates(run_dir):
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {"_error": f"Could not parse transcript JSON: {p.name}"}
    return None

def speaker_audio_labels(run_dir: Path) -> List[str]:
    speaker_dir = run_dir / "speaker_audio"
    if not speaker_dir.exists():
        speaker_dir = run_dir / "speakers_audio"  # tolerate older typo

    if not speaker_dir.exists():
        return []

    stems = [wav.stem for wav in sorted(speaker_dir.glob("*.wav"))]
    # de-dup preserving order
    seen, out = set(), []
    for s in stems:
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out

def format_speaker_for_ui(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.upper().startswith("SPEAKER_"):
        try:
            idx = int(raw.split("_", 1)[1])
            letter = chr(ord("A") + idx) if 0 <= idx < 26 else str(idx + 1)
            return f"Speaker {letter}"
        except Exception:
            pass
    return raw.replace("_", " ").title()

def normalize_tasks(tasks: Any) -> List[Dict[str, Any]]:
    if isinstance(tasks, list):
        return [t for t in tasks if isinstance(t, dict)]
    return []

def ensure_meeting_widgets_synced(meeting: Dict[str, Any]) -> None:
    """
    Keep per-meeting widget state separated.
    When selection changes, we re-initialize the widgets for that meeting.
    """
    mid = meeting.get("meeting_id")
    if not mid:
        return

    notes_key = f"notes_{mid}"
    email_key = f"email_{mid}"

    if notes_key not in st.session_state:
        st.session_state[notes_key] = meeting.get("notes") or ""
    if email_key not in st.session_state:
        st.session_state[email_key] = meeting.get("email_draft") or ""

def persist_meeting_edits(meeting: Dict[str, Any]) -> None:
    """
    Writes widget values back into the selected meeting and saves meetings.json.
    """
    mid = meeting.get("meeting_id")
    if not mid:
        return

    notes_key = f"notes_{mid}"
    email_key = f"email_{mid}"

    meeting["notes"] = st.session_state.get(notes_key, "") or ""
    meeting["email_draft"] = st.session_state.get(email_key, "") or ""

    save_meetings(st.session_state.meetings)

# ---------------------------
# Session state init
# ---------------------------
if "meetings" not in st.session_state:
    st.session_state.meetings = load_meetings()

if "selected_meeting_id" not in st.session_state:
    # optionally accept selection from Home.py
    st.session_state.selected_meeting_id = st.session_state.get("meeting_id")

if "last_selected_meeting_id" not in st.session_state:
    st.session_state.last_selected_meeting_id = None

# ---------------------------
# UI
# ---------------------------
st.title("My Meetings / Results")
st.caption("Browse processed meetings and view transcript, notes, tasks, and (optional) email drafts.")

top_l, top_r = st.columns([3, 1])
with top_r:
    if st.button("↻ Refresh list", use_container_width=True):
        st.session_state.meetings = load_meetings()
        st.rerun()

col_list, col_details = st.columns([1, 2], gap="large")

# ---- Left: meeting list
with col_list:
    st.subheader("Meetings Database")

    meetings = st.session_state.meetings

    if not meetings:
        st.info("No meetings found yet. Process a meeting first to see it here.")
    else:
        q = st.text_input("Search", placeholder="Search by title / date / id…")

        filtered = meetings
        if q.strip():
            ql = q.strip().lower()
            filtered = [
                m for m in meetings
                if ql in f"{m.get('title','')} {m.get('created_at','')} {m.get('meeting_id','')}".lower()
            ]

        if not filtered:
            st.info("No meetings match your search.")
        else:
            options = {meeting_label(m): m.get("meeting_id") for m in filtered}
            labels = list(options.keys())

            current = st.session_state.selected_meeting_id
            default_idx = 0
            if current:
                for i, lbl in enumerate(labels):
                    if options[lbl] == current:
                        default_idx = i
                        break

            chosen_label = st.selectbox("Select a meeting", labels, index=default_idx)
            chosen_id = options[chosen_label]
            st.session_state.selected_meeting_id = chosen_id

        st.divider()

        if st.session_state.selected_meeting_id:
            if st.button("🗑️ Delete selected meeting", type="secondary", use_container_width=True):
                mid = st.session_state.selected_meeting_id
                st.session_state.meetings = [m for m in meetings if m.get("meeting_id") != mid]
                save_meetings(st.session_state.meetings)

                # also clean widget state for that meeting
                st.session_state.pop(f"notes_{mid}", None)
                st.session_state.pop(f"email_{mid}", None)

                st.session_state.selected_meeting_id = None
                st.success("Deleted meeting from meetings.json ✅")
                st.rerun()

# ---- Right: meeting details
with col_details:
    mid = st.session_state.selected_meeting_id

    if not mid:
        st.info("Select a meeting on the left to view results.")
        st.stop()

    meeting = find_meeting(st.session_state.meetings, mid)
    if not meeting:
        st.warning("Meeting not found in database. Try Refresh list.")
        st.stop()

    # If selection changed, make sure widgets reflect THIS meeting
    if st.session_state.last_selected_meeting_id != mid:
        # reset existing widgets for the newly selected meeting
        st.session_state.pop(f"notes_{mid}", None)
        st.session_state.pop(f"email_{mid}", None)
        st.session_state.last_selected_meeting_id = mid

    ensure_meeting_widgets_synced(meeting)

    title = meeting.get("title") or "Meeting"
    created_at = meeting.get("created_at") or "—"
    run_dir = RUNS_DIR / mid

    st.subheader(title)
    st.caption(f"Meeting ID: {mid} • Created: {created_at}")

    # ---------- Transcript
    with st.expander("Transcript", expanded=False):
        if not run_dir.exists():
            st.info(f"No run folder found for this meeting yet: {run_dir}")
        else:
            t = load_transcript(run_dir)

            if t is None:
                st.info("No transcript file found yet for this meeting.")
            elif isinstance(t, dict) and t.get("_error"):
                st.error(t["_error"])
            else:
                # accepted shapes:
                # A) {"segments":[...]}
                # B) [...]
                if isinstance(t, dict) and isinstance(t.get("segments"), list):
                    segments = t["segments"]
                elif isinstance(t, list):
                    segments = t
                else:
                    segments = []

                if not segments:
                    st.info("Transcript loaded, but no segments were found.")
                else:
                    raw_speakers = speaker_audio_labels(run_dir)
                    pretty_map = {s: format_speaker_for_ui(s) for s in raw_speakers}

                    for seg in segments:
                        if not isinstance(seg, dict):
                            continue
                        raw_spk = seg.get("speaker") or seg.get("speaker_id") or "UNKNOWN"
                        ui_spk = pretty_map.get(raw_spk, format_speaker_for_ui(str(raw_spk)))
                        text = seg.get("text") or ""
                        if text:
                            st.markdown(f"**{ui_spk}**: {text}")

                st.download_button(
                    "Download transcript JSON",
                    data=json.dumps(t, indent=2, ensure_ascii=False),
                    file_name=f"{mid}_transcript.json",
                    mime="application/json",
                    use_container_width=True,
                )

    # ---------- Notes
    st.markdown("### Meeting Notes / Minutes")
    notes_key = f"notes_{mid}"
    st.text_area(
        "Notes",
        key=notes_key,
        height=180,
        label_visibility="collapsed",
    )

    # ---------- Tasks
    st.markdown("### Action Items / Tasks")
    tasks = normalize_tasks(meeting.get("tasks"))
    df = pd.DataFrame(tasks) if tasks else pd.DataFrame(
        columns=["task", "assigned_to", "deadline", "reason", "status"]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    b1, b2, b3 = st.columns([1, 1, 1])
    with b1:
        assign_clicked = st.button("Assign in Trello", type="primary", use_container_width=True)
    with b2:
        st.download_button(
            "Download tasks.json",
            data=json.dumps(tasks, indent=2, ensure_ascii=False),
            file_name=f"{mid}_tasks.json",
            mime="application/json",
            use_container_width=True,
        )
    with b3:
        st.button("Save edits", use_container_width=True, on_click=persist_meeting_edits, args=(meeting,))

    # Trello via n8n webhook (optional)
    if assign_clicked:
        if not N8N_TRELLO_WEBHOOK:
            st.warning("n8n Trello webhook not set in secrets.toml.")
        else:
            payload = {"meeting_id": mid, "title": title, "created_at": created_at, "tasks": tasks}
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

    trello_info = meeting.get("trello_sync", {}) or {}
    st.caption(f"Trello sync: {trello_info.get('last_status', '—')} • {trello_info.get('last_timestamp', '—')}")

    # ---------- Email (optional)
    st.markdown("### Follow-up Email Draft (optional)")
    email_key = f"email_{mid}"
    st.text_area(
        "Email",
        key=email_key,
        height=220,
        label_visibility="collapsed",
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Copy to clipboard", use_container_width=True):
            try:
                import pyperclip
                pyperclip.copy(st.session_state.get(email_key, ""))
                st.success("Copied ✅")
            except Exception:
                st.info("Clipboard copy needs 'pyperclip'. Otherwise copy manually.")

    with c2:
        st.download_button(
            "Download email.txt",
            data=st.session_state.get(email_key, ""),
            file_name=f"{mid}_email.txt",
            mime="text/plain",
            use_container_width=True,
        )