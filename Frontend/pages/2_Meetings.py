import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from pathlib import Path

from Backend.config import MEETINGS_PATH, RUNS_DIR
from Frontend.auth import require_password

# MUST be first Streamlit call
st.set_page_config(page_title="Meetings / Results", layout="wide")

require_password()

# ---------------------------
# Config / paths
# ---------------------------
MEETINGS_FILE = Path(MEETINGS_PATH)

# Optional n8n webhook stored in secrets
try:
    N8N_TRELLO_WEBHOOK = st.secrets["n8n"]["trello_webhook"]
except Exception:
    N8N_TRELLO_WEBHOOK = ""

# ---------------------------
# Helpers
# ---------------------------
def load_meetings() -> List[Dict[str, Any]]:
    if not MEETINGS_FILE.exists():
        return []
    try:
        return json.loads(MEETINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_meetings(meetings: List[Dict[str, Any]]) -> None:
    MEETINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEETINGS_FILE.write_text(json.dumps(meetings, indent=2, ensure_ascii=False), encoding="utf-8")

def meeting_label(m: Dict[str, Any]) -> str:
    title = (m.get("title") or "Untitled meeting").strip()
    created_at = (m.get("created_at") or "").strip()
    mid = (m.get("meeting_id") or "").strip()
    suffix = f" • {created_at}" if created_at else ""
    return f"{title}{suffix} ({mid})"

def find_meeting(meetings: List[Dict[str, Any]], meeting_id: str) -> Optional[Dict[str, Any]]:
    for m in meetings:
        if m.get("meeting_id") == meeting_id:
            return m
    return None

def transcript_candidates(run_dir: Path) -> List[Path]:
    """
    VR team file names have changed a few times.
    We support multiple candidates without breaking.
    """
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
    """
    If VR doesn't produce speakers.json, we infer speakers from speaker_audio/*.wav
    """
    speaker_dir = run_dir / "speaker_audio"
    if not speaker_dir.exists():
        # also tolerate older/typo folder name if needed
        speaker_dir = run_dir / "speakers_audio"
    if not speaker_dir.exists():
        return []

    speakers = []
    for wav in sorted(speaker_dir.glob("*.wav")):
        speakers.append(wav.stem)  # e.g. "SPEAKER_0"
    # de-dup while preserving order
    seen = set()
    out = []
    for s in speakers:
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out

def format_speaker_for_ui(raw: str) -> str:
    """
    SPEAKER_0 -> Speaker A
    SPEAKER_1 -> Speaker B
    ...
    If index is big, fallback to number.
    """
    raw = (raw or "").strip()
    if raw.upper().startswith("SPEAKER_"):
        try:
            idx = int(raw.split("_", 1)[1])
            letter = chr(ord("A") + idx) if 0 <= idx < 26 else str(idx + 1)
            return f"Speaker {letter}"
        except Exception:
            pass
    # fallback formatting
    return raw.replace("_", " ").title()

def normalize_tasks(tasks: Any) -> List[Dict[str, Any]]:
    if not tasks:
        return []
    if isinstance(tasks, list):
        return [t for t in tasks if isinstance(t, dict)]
    return []

# ---------------------------
# Session state
# ---------------------------
if "meetings" not in st.session_state:
    st.session_state.meetings = load_meetings()

# The selected meeting can come from:
# - Meetings page selection
# - Home.py setting st.session_state["selected_meeting_id"]
# - fallback: st.session_state["meeting_id"]
if "selected_meeting_id" not in st.session_state or not st.session_state.selected_meeting_id:
    fallback = st.session_state.get("meeting_id")
    st.session_state.selected_meeting_id = fallback

# ---------------------------
# UI
# ---------------------------
st.title("My Meetings / Results")
st.caption("Browse processed meetings and view transcript, notes, tasks, and email drafts.")

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
                if ql in (f"{m.get('title','')} {m.get('created_at','')} {m.get('meeting_id','')}".lower())
            ]

        if not filtered:
            st.info("No meetings match your search.")
        else:
            # choose by meeting_id to avoid index mismatch bugs
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
                st.session_state.selected_meeting_id = None
                st.success("Deleted meeting.")
                st.rerun()

# ---- Right: meeting details
with col_details:
    mid = st.session_state.selected_meeting_id

    if not mid:
        st.info("Select a meeting on the left to view results.")
        st.stop()

    meeting = find_meeting(st.session_state.meetings, mid)
    if not meeting:
        st.warning("Meeting not found in the database. Try Refresh list.")
        st.stop()

    title = meeting.get("title") or "Meeting"
    created_at = meeting.get("created_at") or "—"

    st.subheader(title)
    st.caption(f"Meeting ID: {mid} • Created: {created_at}")

    run_dir = RUNS_DIR / mid

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
                # Try multiple shapes:
                # A) { "segments": [...] }
                # B) [ {speaker, text, ...}, ... ]
                segments = None
                if isinstance(t, dict) and isinstance(t.get("segments"), list):
                    segments = t["segments"]
                elif isinstance(t, list):
                    segments = t
                else:
                    segments = []

                if not segments:
                    st.info("Transcript loaded, but no segments were found.")
                else:
                    # Build mapping from raw speaker IDs to pretty names
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
    notes = meeting.get("notes") or ""
    st.text_area(
        "Notes",
        value=notes,
        height=170,
        key="notes_view",
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
        if st.button("Open run folder info", use_container_width=True):
            st.info(f"Run dir: {run_dir}")

    # Trello via n8n webhook (optional)
    if assign_clicked:
        if not N8N_TRELLO_WEBHOOK:
            st.warning("n8n Trello webhook not set in secrets.toml.")
        else:
            payload = {
                "meeting_id": mid,
                "title": title,
                "created_at": created_at,
                "tasks": tasks,
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

    trello_info = meeting.get("trello_sync", {}) or {}
    st.caption(
        f"Trello sync: {trello_info.get('last_status', '—')} • {trello_info.get('last_timestamp', '—')}"
    )

    # ---------- Email
    st.markdown("### Follow-up Email Draft")
    email_text = meeting.get("email_draft") or ""
    st.text_area(
        "Email",
        value=email_text,
        height=200,
        key="email_view",
        label_visibility="collapsed",
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Copy to clipboard", use_container_width=True):
            try:
                import pyperclip
                pyperclip.copy(st.session_state.email_view)
                st.success("Copied ✅")
            except Exception:
                st.info("Clipboard copy needs 'pyperclip'. Otherwise, copy manually from the text box.")
    with c2:
        st.download_button(
            "Download email.txt",
            data=email_text,
            file_name=f"{mid}_email.txt",
            mime="text/plain",
            use_container_width=True,
        )