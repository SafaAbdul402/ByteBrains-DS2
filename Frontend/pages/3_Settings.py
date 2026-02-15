import streamlit as st
import requests
import os
#from Frontend.auth import require_password
from Frontend.ui_branding import apply_branding

#require_password()

from Frontend.env import load_env
API_BASE = load_env()
if not API_BASE.startswith("http"):
    st.error("API_BASE is missing. Set API_BASE=https://<your-render-backend>.onrender.com in .env")
    st.stop()

def api_get_settings():
    r = requests.get(f"{API_BASE}/settings", timeout=10)
    r.raise_for_status()
    return r.json()

def api_save_settings(trello_board: str):
    r = requests.post(
        f"{API_BASE}/settings",
        json={"trello_board": trello_board},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

st.set_page_config(page_title="ByteBrains – Settings", layout="centered")
st.title("Settings")
apply_branding()

# Load settings once per session
if "settings" not in st.session_state:
    try:
        st.session_state.settings = api_get_settings()
    except Exception:
        st.session_state.settings = {"trello_board": "", "trello_last_sync": None}

s = st.session_state.settings

st.subheader("Trello")

with st.form("settings_form"):
    trello_board = st.text_input(
        "Default Trello Board URL / shortlink",
        value=s.get("trello_board", "") or "",
        placeholder="https://trello.com/b/xxxxxxx/your-board",
    )

    last_sync = s.get("trello_last_sync")
    st.caption(f"Last sync: {last_sync if last_sync else '—'}")

    col1, col2 = st.columns([1, 1])
    save = col1.form_submit_button("Save", use_container_width=True, type="primary")
    clear = col2.form_submit_button("Clear", use_container_width=True)

if save:
    try:
        st.session_state.settings = api_save_settings(trello_board)
        st.success("Saved.")
        st.rerun()
    except Exception as e:
        st.error("Failed to save settings")
        st.code(str(e))

if clear:
    try:
        st.session_state.settings = api_save_settings("")
        st.success("Cleared.")
        st.rerun()
    except Exception as e:
        st.error("Failed to clear")
        st.code(str(e))

#st.divider()
#with st.expander("Diagnostics", expanded=False):
 #   if st.button("Ping backend", use_container_width=True):
  #      try:
   #         _ = api_get_settings()
    #        st.success("Backend reachable ✅")
     #   except Exception as e:
      #      st.error("Backend not reachable")
       #     st.code(str(e))