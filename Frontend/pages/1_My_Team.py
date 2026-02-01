import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import json
import requests

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

def api_get_profiles():
    r = requests.get(f"{API_BASE}/profiles", timeout=10)
    r.raise_for_status()
    return r.json()

def api_sync_trello(board_input):
    try:
        r = requests.post(
            f"{API_BASE}/trello/sync-members",
            json={"board": board_input},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        st.session_state.team = data.get("team", [])

        # IMPORTANT: don't write to trello_board directly (widget key)
        st.session_state["_pending_trello_board"] = data.get("trello_board", board_input) or board_input

        st.success(f"Imported/updated {len(st.session_state.team)} members ✅")
        st.rerun()

    except Exception as e:
        st.error("Import failed")
        st.code(str(e))

def api_save_profiles(team):
    r = requests.post(f"{API_BASE}/profiles", json={"team": team}, timeout=10)
    r.raise_for_status()
    return r.json()

def profile_state(p: dict) -> str:
    # returns: "deleted" | "incomplete" | "eligible"
    if p.get("status") == "deleted":
        return "deleted"

    role_ok = bool((p.get("role") or "").strip())
    skills = p.get("skills") or []
    skills_ok = isinstance(skills, list) and any(str(s).strip() for s in skills)

    if role_ok and skills_ok:
        return "eligible"
    return "incomplete"

st.set_page_config(page_title="ByteBrains – My Team", layout="wide")
st.title("My Team / Profiles")

# -----------------------
# Session state init
# -----------------------

if "_pending_trello_board" in st.session_state:
    st.session_state["trello_board"] = st.session_state.pop("_pending_trello_board")

if "team" not in st.session_state or "trello_board" not in st.session_state:
    try:
        data = api_get_profiles()
        st.session_state.team = data.get("team", [])
        st.session_state.trello_board = data.get("trello_board", "") or ""
    except Exception:
        st.session_state.team = []
        st.session_state.trello_board = ""

if "team_edit_id" not in st.session_state:
    st.session_state.team_edit_id = None

if "integrations" not in st.session_state:
    st.session_state.integrations = {
        "trello_webhook_url": "",
        "n8n_base_url": "",
    }

# -----------------------
# Helpers
# -----------------------

def find_member(member_id: str):
    for m in st.session_state.team:
        if m["id"] == member_id:
            return m
    return None

def delete_member(member_id: str):
    st.session_state.team = [m for m in st.session_state.team if m["id"] != member_id]
    if st.session_state.team_edit_id == member_id:
        st.session_state.team_edit_id = None

def reset_edit():
    st.session_state.team_edit_id = None

def normalize_skills(skills_text: str):
    return [s.strip() for s in skills_text.split(",") if s.strip()]


# -----------------------
# Trello: Integration
# -----------------------
with st.expander("Trello Board URL:", expanded=(not st.session_state.trello_board)):
    st.text_input(
        "",
        key="trello_board",
        placeholder="https://trello.com/..."
    )

# -----------------------
# Top controls: Search + Add button
# -----------------------
top_l, top_r, top_rr = st.columns([3, 1, 1])

with top_l:
    search = st.text_input(
        "Search (name / role / skill)",
        placeholder="e.g., Whisper, Automation, Max…",
    )

with top_r:
    if st.button("Update/Import members", use_container_width=True):
        api_sync_trello(st.session_state.trello_board)
        #st.session_state.show_add = True
        #reset_edit()
        #st.rerun()

with top_rr:
    # Optional: show/hide table view later; for now just a quick count
    st.metric("Members", len(st.session_state.team))


# -----------------------
# Add/Edit form (expander)
# -----------------------
edit_mode = st.session_state.team_edit_id is not None
current = find_member(st.session_state.team_edit_id) if edit_mode else None

if edit_mode: #st.session_state.show_add or 
    title = "Edit member" if edit_mode else "Add new member"
    with st.expander(title, expanded=True):
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
                    placeholder = "Tip: Add age, work experience, strengths, or context that helps task assignment.",
                    height=90,
                )

            with col2:
                st.markdown("**Profile photo (optional)**")
                photo = st.file_uploader(
                    "Upload",
                    type=["png", "jpg", "jpeg"],
                    label_visibility="collapsed",
                )
                st.caption("If empty, a default avatar is shown.")

            save = st.form_submit_button("Save", use_container_width=True)
            cancel = st.form_submit_button("Cancel", use_container_width=True)

        if cancel:
            #st.session_state.show_add = False
            reset_edit()
            st.rerun()

        if save:
            skills = normalize_skills(skills_text)

            if not role.strip() or len(skills) == 0:
                st.error("Please fill Role and at least 1 Skill.")
                st.stop()
            else:
                # Prevent duplicate names (simple rule)
                existing_names = [m["name"] for m in st.session_state.team if (not edit_mode or m["id"] != current["id"])]
                if name.strip() in existing_names:
                    st.error("A member with this name already exists. Please choose a different name.")
                else:
                    skills = normalize_skills(skills_text)

                    photo_bytes = None
                    if photo is not None:
                        photo_bytes = photo.getvalue()
                    else:
                        # keep existing photo when editing
                        if edit_mode:
                            photo_bytes = current.get("photo", None)

                    if edit_mode and current:
                        current["email"] = email.strip()
                        current["role"] = role.strip()
                        current["skills"] = skills
                        current["notes"] = notes.strip()
                        current["photo"] = photo_bytes
                        current["trello_username"] = current.get("trello_username", "")
                        current["trello_id"] = current.get("trello_id", "")
                    st.success("Saved.")
                    api_save_profiles(st.session_state.team)
                    #st.session_state.show_add = False
                    reset_edit()
                    st.rerun()


# -----------------------
# Filter team members
# -----------------------
team = st.session_state.team

if search:
    s = search.lower().strip()

    def matches(m):
        if s in m.get("name", "").lower():
            return True
        if s in m.get("role", "").lower():
            return True
        if s in m.get("email", "").lower():
            return True
        if any(s in sk.lower() for sk in m.get("skills", [])):
            return True
        if s in m.get("notes", "").lower():
            return True
        return False

    team = [m for m in team if matches(m)]


# -----------------------
# Main view: Cards grid
# -----------------------
st.divider()
st.subheader("Team members")

    # -----------------------
    # Optional: Table view (collapsed)
    # -----------------------

with st.expander("Table view", expanded=False):
    df = pd.DataFrame(
        [
            {
                "Name": m.get("name", ""),
                "Role": m.get("role", ""),
                "Email": m.get("email", ""),
                "Skills": ", ".join(m.get("skills", [])),
                "Notes": m.get("notes", ""),
            }
            for m in st.session_state.team
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

if not st.session_state.team:
    st.warning("No team members yet. Pleaes import your Trello board members.")
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
                        st.markdown(
                            f"""
                            <div style="
                                background:#f3f4f6;
                                border:1px solid #e5e7eb;
                                border-radius:12px;
                                padding:14px 14px 10px 14px;
                                opacity:0.55;
                                filter:grayscale(1);
                            ">
                                <div style="font-size:40px; line-height:1;">👤</div>
                                <div style="margin-top:6px; font-weight:700;">
                                    [DELETED] {m.get('name','')}
                                </div>
                                <div style="margin-top:6px; color:#6b7280;">
                                    This member was removed from Trello. You can only delete the profile here.
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,)

                        # Only clickable control:
                        if st.button("Delete", key=f"del_{m['id']}", type="secondary", use_container_width=True):
                            delete_member(m["id"])
                            st.rerun()
                    continue
                else:
                    with st.container(border=True):
                        # Image
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

                            st.warning("This profile is incomplete and cannot be used for speaker mapping until Role + Skills are filled.")   
                        else:
                            st.markdown(f"**{m.get('name','')}**")
                            st.caption(m.get("role", ""))
                            skills = m.get("skills", [])
                            if skills:
                                st.write("**Skills:** " + ", ".join(skills))
                            if m.get("notes"):
                                st.write(m["notes"])
                    
                        
                        top_l, top_r = st.columns([1, 1])
                        with top_l:
                            if st.button("Edit", key=f"edit_{m['id']}", use_container_width=True):
                                st.session_state.team_edit_id = m["id"]
                                #st.session_state.show_add = False
                                st.rerun()
                        with top_r:
                            if st.button("Delete", key=f"del_{m['id']}", type="secondary", use_container_width=True):
                                delete_member(m["id"])
                                st.rerun()