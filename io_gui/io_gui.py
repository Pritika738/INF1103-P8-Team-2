"""
io_gui.py

PASSAY entry point. Sets the Streamlit page config, injects CSS, then
routes to the right screen based on st.session_state.page. All the
real work lives in styles.py, core.py and the screens/ package.
"""

import streamlit as st

st.set_page_config(
    page_title="PASSAY - Health History and Consultation Prep",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

from styles import inject_css
import core  # noqa: F401
from screens import (
    sidebar_nav, show_login, show_pin_login, show_register,
    show_dashboard, show_upload, show_history, show_trends,
    show_vitals, show_consultation, show_profile, show_settings,
)

inject_css()

# Every new browser session starts on the login page. This must run on
# every script run: core.py is imported only once per server process, so
# a default set there would only reach the very first session.
if "page" not in st.session_state:
    st.session_state.page = "login"

if st.session_state.page in ("login", "register", "pin_login"):

    with st.sidebar:
        st.markdown("")

    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="stExpandSidebarButton"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.page == "login":
        show_login()
    elif st.session_state.page == "pin_login":
        show_pin_login()
    else:
        show_register()

else:

    sidebar_nav()

    if st.session_state.page == "dashboard":
        show_dashboard()
    elif st.session_state.page == "upload":
        show_upload()
    elif st.session_state.page == "history":
        show_history()
    elif st.session_state.page == "trends":
        show_trends()
    elif st.session_state.page == "vitals":
        show_vitals()
    elif st.session_state.page == "consultation":
        show_consultation()
    elif st.session_state.page == "profile":
        show_profile()
    elif st.session_state.page == "settings":
        show_settings()
    else:
        show_dashboard()
