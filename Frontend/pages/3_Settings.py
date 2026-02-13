import streamlit as st
from Frontend.api_client import api_get_json, api_post_json, invalidate
import os
#from Frontend.auth import require_password
#from Frontend.lease_client import acquire_or_block
#acquire_or_block()

#require_password()

API_BASE = os.getenv("API_BASE", "")
DISABLE_TRELLO = os.getenv("DISABLE_TRELLO", "0") == "1"

def api_get_settings():
    return api_get_json("/settings", name="settings", ttl_s=60, timeout=10)

def api_save_settings(trello_board: str):
    return api_post_json("/settings", {"trello_board": trello_board}, name="settings_save", timeout=10)

st.set_page_config(page_title="ByteBrains – Settings", layout="centered")
st.title("Settings")

# Load settings once per session
if "settings" not in st.session_state:
    data = api_get_settings()
    if data.get("_rate_limited"):
        st.warning(f"Backend rate limited (429). Wait ~{data.get('_wait_s', 10)}s and retry.")
        st.stop()
    if data.get("_error"):
        st.session_state.settings = {"trello_board": "", "trello_last_sync": None}
    else:
        st.session_state.settings = data

s = st.session_state.settings

st.subheader("Trello")

if DISABLE_TRELLO:
    st.info("Trello is disabled in this deployment.")
    st.stop()

with st.form("settings_form"):
    trello_board = st.text_input(
        "Default Trello Board URL / shortlink",
        value=s.get("trello_board", "") or "",
        placeholder="https://trello.com/b/xxxxxxx/your-board",
    )

    last_sync = s.get("trello_last_sync")
    st.caption(f"Last sync: {last_sync if last_sync else '—'}")

    col1, col2 = st.columns([1, 1])
    save = col1.form_submit_button("Save", use_container_width=True)
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

st.divider()
with st.expander("Diagnostics", expanded=False):
    if st.button("Ping backend", use_container_width=True):
        try:
            _ = api_get_settings()
            st.success("Backend reachable ✅")
        except Exception as e:
            st.error("Backend not reachable")
            st.code(str(e))