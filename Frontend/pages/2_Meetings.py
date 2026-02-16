import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from pathlib import Path
import re
from Backend.config import MEETINGS_PATH, RUNS_DIR
from Frontend.ui_branding import apply_branding
#from Frontend.auth import require_password

# MUST be first Streamlit call
st.set_page_config(page_title="Meeting Results", layout="wide")
apply_branding()

#require_password()

# ---------------------------
# Config / paths
# ---------------------------
DEMO_RUNS_DIR = Path("data/demo_runs")
OVERRIDES_FILE = Path("data/meeting_overrides.json")  # new

from Frontend.env import load_env
API_BASE = load_env()
if not API_BASE.startswith("http"):
    st.error("API_BASE is missing. Set API_BASE=https://<your-render-backend>.onrender.com in .env")
    st.stop()

if not API_BASE:
    st.caption("API_BASE not set — Trello board link disabled.")

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

SEED_MEETINGS = Path("data/permanent_meetings.json")

def load_overrides() -> dict:
    if not OVERRIDES_FILE.exists():
        return {}
    try:
        data = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_overrides(overrides: dict) -> None:
    OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES_FILE.write_text(json.dumps(overrides, indent=2, ensure_ascii=False), encoding="utf-8")

def set_override(mid: str, patch: dict) -> None:
    overrides = load_overrides()
    cur = overrides.get(mid, {})
    if not isinstance(cur, dict):
        cur = {}
    cur.update(patch)
    overrides[mid] = cur
    save_overrides(overrides)

def load_seed_meetings() -> list[dict]:
    if not SEED_MEETINGS.exists():
        return []
    try:
        data = json.loads(SEED_MEETINGS.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def find_run_dir(mid: str) -> Path | None:
    d = RUNS_DIR / mid
    if d.exists():
        return d
    d = DEMO_RUNS_DIR / mid
    if d.exists():
        return d
    return None

def discover_meeting_ids(*bases: Path) -> set[str]:
    out = set()
    for base in bases:
        if not base.exists():
            continue
        for d in base.glob("meeting-*"):
            if d.is_dir():
                out.add(d.name)
    return out

def load_meetings() -> list[dict]:
    seed = load_seed_meetings()
    seed_titles = {
        (s.get("meeting_id") or "").strip(): (s.get("title") or "").strip()
        for s in seed
        if isinstance(s, dict)
    }
    seed_ids = {mid for mid in seed_titles.keys() if mid}

    discovered = discover_meeting_ids(RUNS_DIR, DEMO_RUNS_DIR)
    all_ids = sorted(discovered.union(seed_ids))

    overrides = load_overrides()
    meetings: list[dict] = []

    for mid in all_ids:
        if overrides.get(mid, {}).get("hidden"):
            continue

        run_dir = find_run_dir(mid)

        created_at = "Demo" if mid in seed_ids else ""
        if run_dir:
            meta = run_dir / "meeting_meta.json"
            if meta.exists():
                try:
                    m = json.loads(meta.read_text(encoding="utf-8"))
                    if isinstance(m, dict):
                        created_at = (m.get("created_at") or m.get("createdAt") or created_at or "").strip()
                except Exception:
                    pass

        title = seed_titles.get(mid) or "Processed Meeting"
        ov = overrides.get(mid, {})
        if isinstance(ov, dict) and (ov.get("title") or "").strip():
            title = ov["title"].strip()

        meetings.append({"meeting_id": mid, "title": title, "created_at": created_at})

    return meetings

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
    Prefer the transcript that includes FINAL names (n8n output),
    then fall back to VR transcripts.
    """
    return [
        # ✅ best: n8n-produced transcript with names
        run_dir / "n8n_transcript.json",

        # ✅ also acceptable: merged result that contains transcript
        run_dir / "n8n_result_from_api.json",   # if you save this sometimes
        #run_dir / "n8n_result_skipped.json",    # your skip-n8n demo writes this

        # fallback: VR outputs
        run_dir / "transcript_with_speakers.json",
        run_dir / "vr_transcript.json",
        run_dir / "transcript.json",
        run_dir / ".voice_internal" / "transcript_with_speakers.json",
        run_dir / ".voice_internal" / "vr_transcript.json",
    ]

def load_transcript(run_dir: Path) -> Optional[Any]:
    for p in transcript_candidates(run_dir):
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))

            # common shapes:
            # A) [ {...}, {...} ]
            if isinstance(data, list):
                return data

            # B) { "transcript": [...] }
            if isinstance(data, dict) and isinstance(data.get("transcript"), list):
                return data["transcript"]

            # C) { "result": { "transcript": [...] } } (just in case)
            if isinstance(data, dict):
                inner = data.get("result")
                if isinstance(inner, dict) and isinstance(inner.get("transcript"), list):
                    return inner["transcript"]

            return data
        except Exception:
            return {"_error": f"Could not parse transcript JSON: {p.name}"}
    return None

def is_placeholder_speaker(s: str) -> bool:
    s = (s or "").strip()
    return bool(re.match(r"^SPEAKER[\s_-]?\d+$", s, flags=re.IGNORECASE))

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

PROFILES_COMPLETED_PATH = Path("data/profiles_complete.json")

@st.cache_data(ttl=300)
def load_completed_profiles_file() -> list[dict]:
    if not PROFILES_COMPLETED_PATH.exists():
        return []
    try:
        data = json.loads(PROFILES_COMPLETED_PATH.read_text(encoding="utf-8"))
        team = data.get("team", []) if isinstance(data, dict) else []
        return team if isinstance(team, list) else []
    except Exception:
        return []

@st.cache_data(ttl=300)
def trello_id_to_name_from_completed_profiles() -> dict:
    team = load_completed_profiles_file()
    out = {}
    for p in team:
        if not isinstance(p, dict):
            continue
        tid = (p.get("trello_id") or "").strip()
        name = (p.get("name") or "").strip()
        if tid and name:
            out[tid] = name
    return out

def load_n8n_result(run_dir: Path) -> dict | None:
    candidates = [
        run_dir / "n8n_result_from_api.json",
        run_dir / "n8n_result_merged.json",
        run_dir / "n8n_result_skipped.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else None
            except Exception:
                return None
    return None


def get_meeting_notes(mid: str, run_dir: Path | None) -> str:
    # user override wins
    ov = load_overrides().get(mid, {})
    if isinstance(ov, dict) and "notes" in ov:
        return ov.get("notes") or ""

    if not run_dir:
        return ""

    res = load_n8n_result(run_dir) or {}
    return (res.get("summary") or "").strip()

def get_meeting_tasks(run_dir: Path | None) -> list[dict]:
    if not run_dir:
        return []
    res = load_n8n_result(run_dir) or {}
    t = res.get("tasks")
    return t if isinstance(t, list) else []

# ---------------------------
# Session state
# ---------------------------
if "meetings" not in st.session_state or st.session_state.get("force_reload_meetings"):
    st.session_state.meetings = load_meetings()
    st.session_state.force_reload_meetings = False

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
#with top_r:
 #   if st.button("↻ Refresh list", use_container_width=True):
  #      st.session_state.meetings = load_meetings()
   #     st.rerun()

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
                mid_to_hide = st.session_state.selected_meeting_id
                set_override(mid_to_hide, {"hidden": True})
                st.success("Hidden meeting.")
                st.session_state.selected_meeting_id = None
                st.session_state.force_reload_meetings = True
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

    # ---- Title editor
    title_edit_key = f"title_editing__{mid}"
    title_text_key = f"title_text__{mid}"

    if title_edit_key not in st.session_state:
        st.session_state[title_edit_key] = False

    row_l, row_r = st.columns([3, 1])

    with row_l:
        if not st.session_state[title_edit_key]:
            st.subheader(title)
        else:
            st.text_input(
                "Meeting title",
                value=st.session_state.get(title_text_key, title),
                key=title_text_key,
                label_visibility="collapsed",
            )

    with row_r:
        if not st.session_state[title_edit_key]:
            if st.button("Edit title", use_container_width=True):
                st.session_state[title_text_key] = title
                st.session_state[title_edit_key] = True
                st.rerun()
        else:
            if st.button("Save title", type="primary", use_container_width=True):
                new_title = (st.session_state.get(title_text_key, "") or "").strip()
                new_title = (st.session_state.get(title_text_key, "") or "").strip()
                set_override(mid, {"title": new_title})  # empty string means "remove override"
                st.session_state[title_edit_key] = False
                st.success("Saved title.")
                st.rerun()

    st.caption(f"Meeting ID: {mid} • Created: {created_at}")
    
    run_dir = find_run_dir(mid)

    # ---------- Transcript
    with st.expander("Transcript", expanded=False):
        if not run_dir or not run_dir.exists():
            st.info(f"No run folder found for this meeting yet: {run_dir}")
        else:
            t = load_transcript(run_dir)

            if t is None:
                st.info("No transcript file found yet for this meeting.")
            elif isinstance(t, dict) and t.get("_error"):
                st.error(t["_error"])
            else:
                # normalize transcript to a list of segments
                if isinstance(t, dict) and isinstance(t.get("segments"), list):
                    segments = t["segments"]
                elif isinstance(t, list):
                    segments = t
                else:
                    segments = []

                if not segments:
                    st.info("Transcript loaded, but no segments were found.")
                else:
                    def seg_speaker(seg: dict) -> str:
                        return (seg.get("speaker") or seg.get("speaker_id") or "").strip()

                    # Only hide SPEAKER_x if we ALSO have real names
                    has_named_speakers = any(
                        s and not is_placeholder_speaker(s)
                        for s in (seg_speaker(seg) for seg in segments if isinstance(seg, dict))
                    )

                    for seg in segments:
                        if not isinstance(seg, dict):
                            continue
                        raw_spk = seg_speaker(seg)
                        text = (seg.get("text") or "").strip()
                        if not text:
                            continue

                        if has_named_speakers and is_placeholder_speaker(raw_spk):
                            continue

                        spk = raw_spk or "Unknown"
                        st.markdown(f"**{spk}**: {text}")

                    st.download_button(
                        "Download transcript JSON",
                        data=json.dumps(t, indent=2, ensure_ascii=False),
                        file_name=f"{mid}_transcript.json",
                        mime="application/json",
                        use_container_width=True,
                    )       

    # ---------- Notes
    st.markdown("### Meeting Notes")

    notes = get_meeting_notes(mid, run_dir)

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
                set_override(mid, {"notes": st.session_state.get(notes_key, "")})
                st.session_state[edit_flag_key] = False
                st.success("Saved notes.")
                st.rerun()
        with b2:
            if st.button("Cancel", use_container_width=True):
                st.session_state[edit_flag_key] = False
                st.rerun()

        # ---------- Tasks
    st.markdown("### Action Items")
    tasks = normalize_tasks(get_meeting_tasks(run_dir))
    if not tasks:
        st.info("No action items found for this meeting yet.")
    else:
        df_raw = pd.DataFrame(tasks).fillna("")

        # map Trello member id -> name from profiles_complete.json
        trello_id_to_name = trello_id_to_name_from_completed_profiles()

        def owner_from_trello_id(x):
            s = str(x).strip()
            if not s:
                return ""
            return trello_id_to_name.get(s, s)  # fallback: show raw id if unknown

        # --- Build the output table with exactly the columns you want
        out = pd.DataFrame()
        out["Task"] = df_raw["taskName"] if "taskName" in df_raw.columns else df_raw.get("task", "")
        out["Owner"] = df_raw["trello_id"].apply(owner_from_trello_id) if "trello_id" in df_raw.columns else ""
        out["Due date"] = df_raw["due_date"] if "due_date" in df_raw.columns else df_raw.get("deadline", "")
        out["Description"] = df_raw["descr"] if "descr" in df_raw.columns else df_raw.get("description", "")

        # cosmetic cleanup
        out["Due date"] = out["Due date"].apply(lambda x: "—" if not str(x).strip() else str(x))

        st.dataframe(out, width="stretch", hide_index=True)

        b1, b2 = st.columns([1, 1])
        with b1:
            if trello_board_url:
                st.link_button("See in Trello", trello_board_url, type="primary", use_container_width=True)
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