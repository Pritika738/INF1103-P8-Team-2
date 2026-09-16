import streamlit as st

from login_screen import show_login_screen
from register_screen import show_register_screen
from dashboard_screen import show_dashboard_screen
from upload_screen import show_upload_screen
from history_screen import show_history_screen
from trends_screen import show_trends_screen
from consultation_screen import show_consultation_screen

st.set_page_config(
    page_title="Health History & Consultation Preparation",
    page_icon="🩺",
    layout="centered"
)

if "page" not in st.session_state:
    st.session_state.page = "login"

if st.session_state.page == "login":
    show_login_screen()

elif st.session_state.page == "register":
    show_register_screen()

elif st.session_state.page == "dashboard":
    show_dashboard_screen()

elif st.session_state.page == "upload":
    show_upload_screen()

elif st.session_state.page == "history":
    show_history_screen()

elif st.session_state.page == "trends":
    show_trends_screen()

elif st.session_state.page == "consultation":
    show_consultation_screen()