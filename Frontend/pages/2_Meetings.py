import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from pathlib import Path

from Backend.config import MEETINGS_PATH, RUNS_DIR
#from Frontend.auth import require_password

# MUST be first Streamlit call
st.set_page_config(page_title="Meetings / Results", layout="wide")

#require_password()

# ---------------------------
# Config / paths
# ---------------------------
MEETINGS_FILE = Path(MEETINGS_PATH)
from Frontend.env import load_env
API_BASE = load_env()
if not API_BASE.startswith("http"):
    st.error("API_BASE is missing. Set API_BASE=https://<your-render-backend>.onrender.com in .env")
    st.stop()

if not API_BASE:
    st.caption("API_BASE not set — Trello board link disabled.")

def api_get_profiles():
    r = requests.get(f"{API_BASE}/profiles", timeout=10)
    r.raise_for_status()
    return r.json()
# ---------------------------
# Helpers
# ---------------------------
@st.cache_data(ttl=60)
def get_trello_board_url(api_base: str) -> str:
    if not api_base:
        return ""
    try:
        r = requests.get(f"{api_base}/profiles", timeout=10)
        r.raise_for_status()
        prof = r.json()
        return (prof.get("trello_board") or "").strip()
    except Exception:
        return ""

trello_board_url = get_trello_board_url(API_BASE)

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
        run_dir / "n8n_transcript.json",
        run_dir / "n8n_result_merged.json",
    ]

def load_transcript(run_dir: Path) -> Optional[Any]:
    for p in transcript_candidates(run_dir):
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))

                # If merged file, extract transcript
                if isinstance(data, dict) and "transcript" in data:
                    return data["transcript"]

                return data
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
    return raw.replace("_", " ")

def normalize_tasks(tasks: Any) -> List[Dict[str, Any]]:
    if not tasks:
        return []
    if isinstance(tasks, list):
        return [t for t in tasks if isinstance(t, dict)]
    if isinstance(tasks, dict):
        # tolerate {"0":{"json":{...}}, ...}
        out = []
        for _, item in sorted(tasks.items(), key=lambda kv: str(kv[0])):
            if isinstance(item, dict) and isinstance(item.get("json"), dict):
                out.append(item["json"])
        return out
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
st.title("My Meetings")
st.caption("Browse processed meetings and view transcript, notes, and tasks.")

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
    st.markdown("### Meeting Notes")

    notes = meeting.get("notes") or ""

    # per-meeting state keys (prevents cross-meeting bleed)
    edit_flag_key = f"notes_editing__{mid}"
    notes_key = f"notes_text__{mid}"

    if edit_flag_key not in st.session_state:
        st.session_state[edit_flag_key] = False

    # show a pretty, read-only view by default
    if not st.session_state[edit_flag_key]:
        if notes.strip():
            # Basic formatting: keep line breaks + bullets if n8n outputs them
            clean_notes = notes.replace("****", "\n\n")  # your sample had ****
            st.markdown(clean_notes)
        else:
            st.caption("No notes yet.")

        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("Edit notes", use_container_width=True):
                st.session_state[notes_key] = notes.replace("****", "\n\n")
                st.session_state[edit_flag_key] = True
                st.rerun()

    else:
        # edit mode
        st.text_area(
            "Edit Notes",
            value=st.session_state.get(notes_key, notes),
            key=notes_key,
            height=220,
            label_visibility="collapsed",
        )

        b1, b2 = st.columns([1, 1])
        with b1:
            if st.button("Save", type="primary", use_container_width=True):
                meeting["notes"] = st.session_state.get(notes_key, "")
                save_meetings(st.session_state.meetings)
                st.session_state[edit_flag_key] = False
                st.success("Saved notes.")
                st.rerun()
        with b2:
            if st.button("Cancel", use_container_width=True):
                st.session_state[edit_flag_key] = False
                st.rerun()

    # ---------- Tasks
    st.markdown("### Action Items")
    tasks = normalize_tasks(meeting.get("tasks"))
    if not tasks:
        st.info("No action items found for this meeting yet.")
    else:
        df = pd.DataFrame(tasks)

        # 1) Drop internal / noisy columns (hide trello_id)
        drop_cols = [c for c in ["trello_id", "trelloId", "card_id", "id"] if c in df.columns]
        if drop_cols:
            df = df.drop(columns=drop_cols)

        # 2) Rename columns to be human-friendly
        rename_map = {
            "taskName": "Task",
            "task": "Task",
            "descr": "Description",
            "description": "Description",
            "due_date": "Due",
            "deadline": "Due",
            "assigned_to": "Assignee",
            "owner": "Assignee",
            "status": "Status",
            "reason": "Notes",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        # 3) Keep only the columns we want, in a nice order
        preferred_order = ["Task", "Description", "Assignee", "Due", "Status", "Notes"]
        keep = [c for c in preferred_order if c in df.columns]
        # also keep any unexpected extra columns at the end (optional)
        extras = [c for c in df.columns if c not in keep]
        df = df[keep + extras]

        # 4) Cosmetic: ensure missing values look clean
        if "Due" in df.columns:
            df["Due"] = df["Due"].apply(lambda x: "—" if not str(x).strip() else str(x))
        df = df.fillna("")

        st.dataframe(df, width="stretch", hide_index=True)

    b1, b2 = st.columns([1, 1])
    with b1:
        if trello_board_url:
            st.link_button("See in Trello", trello_board_url, use_container_width=True)
        else:
            st.caption("Trello board URL not set. Add it in My Team or Settings.")
    with b2:
        st.download_button(
            "Download tasks.json",
            data=json.dumps(tasks, indent=2, ensure_ascii=False),
            file_name=f"{mid}_tasks.json",
            mime="application/json",
            use_container_width=True,
        )
    #with b3:
     #   if st.button("Open run folder info", use_container_width=True):
      #      st.info(f"Run dir: {run_dir}")