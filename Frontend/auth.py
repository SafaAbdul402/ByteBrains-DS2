import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

def require_password():
    PASSWORD = os.getenv("APP_PASSWORD")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    st.title("🔒 ByteBrains – Protected App")

    pw = st.text_input("Enter password", type="password")

    if pw:
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.success("Access granted")
            st.rerun()
        else:
            st.error("Wrong password")

    st.stop()