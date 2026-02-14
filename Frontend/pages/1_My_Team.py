import streamlit as st
import pandas as pd
from datetime import datetime
import time as pytime
import uuid
import json
import requests
import os
from Backend.config import PROFILES_COMPLETED_PATH, PROFILES_PATH
from Frontend.api_client import api_get_json, api_post_json, invalidate
#from Frontend.lease_client import acquire_or_block
#acquire_or_block()

API_BASE = os.getenv("API_BASE", "")
PROFILES_TTL_S = 60  # cache /profiles for 30s in this Streamlit session

DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
DEMO_TEAM = os.getenv("DEMO_TEAM", "1") == "1"
DISABLE_TRELLO = os.getenv("DISABLE_TRELLO", "0") == "1"
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
if DEMO_MODE:
    st.set_page_config(page_title="ByteBrains – Demo", layout="centered")
    st.title("Demo deployment")
    st.info("This deployment is for n8n testing only. Please use the **n8n Demo** page.")
    if st.button("Go to n8n Demo", type="primary", use_container_width=True):
        st.switch_page("pages/0_N8N_Demo.py")
    st.stop()
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

if "team" not in st.session_state:
    st.session_state.team = []
if "trello_board" not in st.session_state:
    st.session_state.trello_board = ""
if "team_edit_id" not in st.session_state:
    st.session_state.team_edit_id = None

if DEMO_MODE:
    st.session_state.team = load_completed_profiles()
    st.session_state.trello_board = ""   # or keep a local value
else:
    data = api_get_json("/profiles", name="profiles", ttl_s=60)

    if data.get("_rate_limited"):
        st.warning(f"Backend rate limited (429). Wait ~{data.get('_wait_s', 10)}s and click Retry.")
        if st.button("Retry"):
            invalidate("profiles")
            st.rerun()
        st.stop()

    if data.get("_error"):
        st.error("Could not load profiles.")
        st.code(f"HTTP {data.get('_status')}: {data.get('_text')[:400]}")
        st.stop()

    st.session_state.team = data.get("team", [])
    st.session_state.trello_board = data.get("trello_board", "") or ""

# -----------------------
# Trello: Integration
# -----------------------

if not DEMO_MODE and (not DISABLE_TRELLO): 
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
            res = api_post_json("/trello/sync-members", {...}, name="trello_sync", timeout=60)

            if res.get("_rate_limited"):
                wait_s = res.get("_wait_s", 10)
                st.warning(f"Rate limited (429). Wait {wait_s}s and click again.")
                st.stop()

            if res.get("_error"):
                st.error("Import failed")
                st.code(f"HTTP {res.get('_status')}: {res.get('_text')}")
                st.stop()

            st.session_state.team = res.get("team", [])
            st.session_state.trello_board = res.get("trello_board", st.session_state.trello_board) or st.session_state.trello_board

            invalidate("profiles")
            st.success(f"Imported/updated {len(st.session_state.team)} members")
            st.rerun()

    with top_rr:
        st.metric("Members", len(st.session_state.team))
else:
    st.info("Demo mode: Trello import disabled. Using completed demo team.")

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
        invalidate("profiles")
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
            if DEMO_MODE:
                st.warning("Demo mode: changes are local only (not saved to backend).")
            else:
                res = api_post_json("/profiles", {"team": st.session_state.team}, name="profiles_save", timeout=20)
            
            st.session_state.team_last_updated = pytime.time()
            invalidate("profiles")

            if res.get("_rate_limited"):
                wait_s = res.get("_wait_s", 3)
                st.warning(f"Rate limited (429) while saving. Wait {wait_s}s and click Save again.")
                st.stop()

            if res.get("_error"):
                st.error("Saving failed")
                st.code(f"HTTP {res.get('_status')}: {res.get('_text')}")
                st.stop()

            invalidate("profiles")
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
                            res = api_post_json("/profiles", {"team": team}, name="profiles_save", timeout=20)
                            if res.get("_error") or res.get("_rate_limited"):
                                st.warning("Could not persist deletion to backend. Please try again.")
                            invalidate("profiles")
                            st.rerun()