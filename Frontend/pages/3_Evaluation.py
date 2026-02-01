import streamlit as st
from Frontend.auth import require_password

require_password()

st.title("Evaluation – Data Science II")