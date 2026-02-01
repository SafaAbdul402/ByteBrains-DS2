import streamlit as st
import requests
import os

require_password()

st.set_page_config(page_title="HTTP Test (via FastAPI)", layout="centered")
st.title("🔌 Test HTTP Connection (Streamlit → FastAPI → n8n)")

API_BASE = os.getenv("API_BASE", "http://localhost:8000")   # FastAPI address (local for now)
SECRET = os.getenv("TEST_SHARED_SECRET", "")            # must match TEST_SHARED_SECRET in backend

st.caption("This page calls FastAPI, which then calls the n8n webhook and returns the response.")
st.divider()

col1, col2 = st.columns([1, 1], gap="large")

message = st.text_input(
    "Message to send to n8n",
    value="Hello from Streamlit 👋"
)

with col1:
    st.text("Run the full roundtrip test")
    if st.button("Run roundtrip test", use_container_width=True):
        with st.spinner("Calling FastAPI (which calls n8n)..."):
            try:
                r = requests.post(
                    f"{API_BASE}/test/n8n-roundtrip",
                    json={"source": "streamlit", 
                          "type": "test", 
                          "message": message},
                    headers={"X-BB-SECRET": SECRET},
                    timeout=20,
                )
                r.raise_for_status()
                st.success("Success ✅")
                st.json(r.json())
            except Exception as e:
                st.error("Failed")
                st.code(str(e))

with col2:
    st.text("Load last stored result from backend")
    if st.button("Load last stored result", use_container_width=True):
        try:
            r = requests.get(
                f"{API_BASE}/test/last",
                headers={"X-BB-SECRET": SECRET},
                timeout=10,
            )
            r.raise_for_status()
            st.info("Last stored result:")
            st.json(r.json())
        except Exception as e:
            st.error("Failed to load last result")
            st.code(str(e))