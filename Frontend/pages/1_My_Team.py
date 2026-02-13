import streamlit as st
import pandas as pd
from datetime import datetime
import time as pytime
import uuid
import json
import requests
import os

from Backend.config import PROFILES_COMPLETED_PATH, PROFILES_PATH

API_BASE = os.getenv("API_BASE", "")
PROFILES_TTL_S = 30  # cache /profiles for 30s in this Streamlit session

# -----------------------
# HTTP helpers
# -----------------------
def safe_get_json(url: str, timeout: int = 10) -> dict:
    r = requests.get(url, timeout=timeout)

    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After")
        wait_s = int(retry_after) if (retry_after and retry_after.isdigit()) else 3
        return {"_rate_limited": True, "_wait_s": wait_s, "_status": 429, "_text": r.text}

    if not r.ok:
        return {"_error": True, "_status": r.status_code, "_text": r.text}

    return r.json()

def safe_post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    r = requests.post(url, json=payload, timeout=timeout)

    if r.status_code == 429:
        retry_after = r.headers.get("Retry-After")
        wait_s = int(retry_after) if (retry_after and retry_after.isdigit()) else 3
        return {"_rate_limited": True, "_wait_s": wait_s, "_status": 429, "_text": r.text}

    if not r.ok:
        return {"_error": True, "_status": r.status_code, "_text": r.text}

    return r.json()

# -----------------------
# API calls
# -----------------------
def api_get_profiles():
    return safe_get_json(f"{API_BASE}/profiles", timeout=10)

def api_save_profiles(team):
    return safe_post_json(f"{API_BASE}/profiles", {"team": team}, timeout=10)

def api_sync_trello(board_input):
    return safe_post_json(
        f"{API_BASE}/trello/sync-members",
        {"board": board_input},
        timeout=30,
    )

# -----------------------
# Throttled profiles fetch (prevents rerun hammering)
# -----------------------
def get_profiles_throttled() -> dict:
    now = pytime.time()

    # if we have fresh cached data, use it
    cached = st.session_state.get("_profiles_cache")
    ts = st.session_state.get("_profiles_cache_ts", 0.0)
    if cached and (now - ts) < PROFILES_TTL_S:
        return cached

    # cooldown after a 429
    retry_at = st.session_state.get("_profiles_retry_at", 0.0)
    if now < retry_at:
        wait_s = int(retry_at - now)
        return {"_rate_limited": True, "_wait_s": max(wait_s, 1)}

    data = api_get_profiles()

    if data.get("_rate_limited"):
        wait_s = int(data.get("_wait_s", 3))
        st.session_state["_profiles_retry_at"] = now + wait_s
        return data

    # success: cache it
    st.session_state["_profiles_cache"] = data
    st.session_state["_profiles_cache_ts"] = now
    st.session_state["_profiles_retry_at"] = 0.0
    return data

def invalidate_profiles_cache():
    st.session_state.pop("_profiles_cache", None)
    st.session_state.pop("_profiles_cache_ts", None)
    st.session_state["_profiles_retry_at"] = 0.0

# -----------------------
# Local helpers
# -----------------------
def profile_state(p: dict) -> str:
    if p.get("status") == "deleted":
        return "deleted"
    role_ok = bool((p.get("role") or "").strip())
    skills = p.get("skills") or []
    skills_ok = isinstance(skills, list) and any(str(s).strip() for s in skills)
    return "eligible" if (role_ok and skills_ok) else "incomplete"

def load_completed_profiles() -> list[dict]:
    if not PROFILES_COMPLETED_PATH.exists():
        return []
    try:
        data = json.loads(PROFILES_COMPLETED_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("team", [])
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def load_profiles_team_from_file() -> list[dict]:
    if not PROFILES_PATH.exists():
        return []
    try:
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("team", [])
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def find_member(team, member_id: str):
    return next((m for m in team if m.get("id") == member_id), None)

def delete_member(member_id: str):
    st.session_state.team = [m for m in st.session_state.team if m.get("id") != member_id]
    if st.session_state.team_edit_id == member_id:
        st.session_state.team_edit_id = None

def normalize_skills(skills_text: str):
    return [s.strip() for s in skills_text.split(",") if s.strip()]

# -----------------------
# UI
# -----------------------
st.set_page_config(page_title="ByteBrains – My Team", layout="wide")
st.title("My Team / Profiles")

# ---- init session state keys
if "team" not in st.session_state:
    st.session_state.team = []
if "trello_board" not in st.session_state:
    st.session_state.trello_board = ""
if "team_edit_id" not in st.session_state:
    st.session_state.team_edit_id = None
if "team_last_updated" not in st.session_state:
    st.session_state.team_last_updated = 0.0

# handle pending trello board write (avoids widget key write conflict)
if "_pending_trello_board" in st.session_state:
    st.session_state["trello_board"] = st.session_state.pop("_pending_trello_board")

# ---- Initial load (only if team empty / never loaded)
if not st.session_state.team and st.session_state.team_last_updated == 0.0:
    data = get_profiles_throttled()
    st.session_state.team_last_updated = pytime.time()

    if data.get("_rate_limited"):
        wait_s = data.get("_wait_s", 3)
        st.warning(f"Backend rate limited (429). Wait {wait_s}s then click Retry.")
        if st.button("Retry"):
            st.session_state["_profiles_retry_at"] = 0.0
            invalidate_profiles_cache()
            st.rerun()
        st.stop()

    if data.get("_error"):
        st.error("Could not load profiles from backend.")
        st.code(f"HTTP {data.get('_status')}: {data.get('_text')}")
        st.info("You can still use local fallback profiles.json if present.")
        st.session_state.team = load_profiles_team_from_file()
    else:
        st.session_state.team = data.get("team", [])
        st.session_state.trello_board = data.get("trello_board", "") or ""

# -----------------------
# Trello: Integration
# -----------------------
with st.expander("Trello Board URL:", expanded=(not st.session_state.trello_board)):
    st.text_input(
        "Trello board URL",
        key="trello_board",
        placeholder="https://trello.com/...",
        label_visibility="collapsed",
    )

top_l, top_r, top_rr = st.columns([3, 1, 1])
with top_l:
    search = st.text_input("Search (name / role / skill)", placeholder="e.g., Whisper, Automation, Max…")

with top_r:
    if st.button("Update/Import members", use_container_width=True):
        data = api_sync_trello(st.session_state.trello_board)

        if data.get("_rate_limited"):
            wait_s = data.get("_wait_s", 3)
            st.warning(f"Rate limited (429). Wait {wait_s}s and click the button again.")
            st.stop()

        if data.get("_error"):
            st.error("Import failed")
            st.code(f"HTTP {data.get('_status')}: {data.get('_text')}")
            st.stop()

        st.session_state.team = data.get("team", [])
        st.session_state["_pending_trello_board"] = data.get("trello_board", st.session_state.trello_board) or st.session_state.trello_board
        st.session_state.team_last_updated = pytime.time()
        invalidate_profiles_cache()
        st.success(f"Imported/updated {len(st.session_state.team)} members ✅")
        st.rerun()

with top_rr:
    st.metric("Members", len(st.session_state.team))

# -----------------------
# Use completed toggle
# -----------------------
use_completed = st.toggle("Use completed profiles", help="Show fully edited profiles", key="use_completed_profiles")

if "use_completed_profiles_prev" not in st.session_state:
    st.session_state.use_completed_profiles_prev = use_completed

if use_completed != st.session_state.use_completed_profiles_prev:
    st.session_state.use_completed_profiles_prev = use_completed

    if use_completed:
        st.session_state.team = load_completed_profiles()
        st.success(f"Loaded {len(st.session_state.team)} completed profiles ✅")
        st.rerun()
    else:
        data = get_profiles_throttled()
        st.session_state.team_last_updated = pytime.time()

        if data.get("_rate_limited"):
            wait_s = data.get("_wait_s", 3)
            st.warning(f"Backend rate limited (429). Wait {wait_s}s then click Retry.")
            if st.button("Retry"):
                st.session_state["_profiles_retry_at"] = 0.0
                invalidate_profiles_cache()
                st.rerun()
            st.stop()

        if data.get("_error"):
            st.warning("Could not load profiles from backend, using local fallback.")
            st.session_state.team = load_profiles_team_from_file()
        else:
            st.session_state.team = data.get("team", [])
        st.rerun()

# -----------------------
# Add/Edit form
# -----------------------
edit_mode = st.session_state.team_edit_id is not None
current = find_member(st.session_state.team, st.session_state.team_edit_id) if edit_mode else None

if edit_mode:
    with st.expander("Edit member", expanded=True):
        with st.form("member_form", clear_on_submit=False):
            col1, col2 = st.columns([2, 1])

            with col1:
                is_trello = bool(current and current.get("trello_id"))
                name = st.text_input("Name*", value=current["name"] if current else "", disabled=is_trello)
                email = st.text_input("Email (optional)", value=current.get("email", "") if current else "")
                role = st.text_input("Role / Function*", value=current.get("role", "") if current else "")

                skills_text = st.text_input(
                    "Skill* (comma-separated)",
                    value=", ".join(current.get("skills", [])) if current else "",
                    placeholder="Python, Whisper, n8n, Prompting",
                )
                notes = st.text_area(
                    "Notes (optional)",
                    value=current.get("notes", "") if current else "",
                    placeholder="Tip: Add strengths, context, etc.",
                    height=90,
                )

            with col2:
                st.markdown("**Profile photo (optional)**")
                photo = st.file_uploader("Upload", type=["png", "jpg", "jpeg"], label_visibility="collapsed")

            save = st.form_submit_button("Save", use_container_width=True)
            cancel = st.form_submit_button("Cancel", use_container_width=True)

        if cancel:
            st.session_state.team_edit_id = None
            st.rerun()

        if save:
            skills = normalize_skills(skills_text)
            if not role.strip() or len(skills) == 0:
                st.error("Please fill Role and at least 1 Skill.")
                st.stop()

            # duplicate name protection
            existing_names = [m.get("name") for m in st.session_state.team if (not current or m.get("id") != current.get("id"))]
            if name.strip() in existing_names:
                st.error("A member with this name already exists. Choose a different name.")
                st.stop()

            photo_bytes = photo.getvalue() if photo is not None else (current.get("photo") if current else None)

            # update current record
            if current:
                current["email"] = email.strip()
                current["role"] = role.strip()
                current["skills"] = skills
                current["notes"] = notes.strip()
                current["photo"] = photo_bytes

            # save to backend
            res = api_save_profiles(st.session_state.team)
            st.session_state.team_last_updated = pytime.time()
            invalidate_profiles_cache()

            if res.get("_rate_limited"):
                wait_s = res.get("_wait_s", 3)
                st.warning(f"Rate limited (429) while saving. Wait {wait_s}s and click Save again.")
                st.stop()

            if res.get("_error"):
                st.error("Saving failed")
                st.code(f"HTTP {res.get('_status')}: {res.get('_text')}")
                st.stop()

            st.success("Saved ✅")
            st.session_state.team_edit_id = None
            st.rerun()

# -----------------------
# Filter team members
# -----------------------
team = st.session_state.team
if search:
    s = search.lower().strip()
    def matches(m):
        if s in (m.get("name", "").lower()): return True
        if s in (m.get("role", "").lower()): return True
        if s in (m.get("email", "").lower()): return True
        if any(s in str(sk).lower() for sk in (m.get("skills") or [])): return True
        if s in (m.get("notes", "").lower()): return True
        return False
    team = [m for m in team if matches(m)]

# -----------------------
# View
# -----------------------
st.divider()
st.subheader("Team members")

with st.expander("Table view", expanded=False):
    df = pd.DataFrame([
        {
            "Name": m.get("name", ""),
            "Role": m.get("role", ""),
            "Email": m.get("email", ""),
            "Skills": ", ".join(m.get("skills", [])),
            "Notes": m.get("notes", ""),
        }
        for m in st.session_state.team
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

if not st.session_state.team:
    st.warning("No team members yet. Please import your Trello board members.")
else:
    if not team:
        st.info("No matches found for your search.")
    else:
        cols = st.columns(3, gap="large")
        for i, m in enumerate(team):
            with cols[i % 3]:
                state = profile_state(m)

                if state == "deleted":
                    with st.container(border=True):
                        st.markdown(f"### 👤 [DELETED] {m.get('name','')}")
                        st.caption("Removed from Trello. You can only delete the profile here.")
                        if st.button("Delete", key=f"del_{m.get('id')}", type="secondary", use_container_width=True):
                            delete_member(m.get("id"))
                            st.rerun()
                    continue

                with st.container(border=True):
                    if m.get("photo"):
                        st.image(m["photo"], width=72)
                    else:
                        st.markdown("### 👤")

                    if state == "incomplete":
                        st.markdown(f"[INCOMPLETE] **{m.get('name','')}**")
                        st.caption(m.get("role", ""))
                        if m.get("email"):
                            st.caption(m["email"])
                        if m.get("trello_username"):
                            st.caption(f"@{m.get('trello_username','')}")
                        st.warning("Fill Role + Skills to be eligible for speaker mapping.")
                    else:
                        st.markdown(f"**{m.get('name','')}**")
                        st.caption(m.get("role", ""))
                        if m.get("skills"):
                            st.write("**Skills:** " + ", ".join(m.get("skills", [])))
                        if m.get("notes"):
                            st.write(m["notes"])

                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Edit", key=f"edit_{m.get('id')}", use_container_width=True):
                            st.session_state.team_edit_id = m.get("id")
                            st.rerun()
                    with b2:
                        if st.button("Delete", key=f"del_{m.get('id')}", type="secondary", use_container_width=True):
                            delete_member(m.get("id"))
                            st.rerun()