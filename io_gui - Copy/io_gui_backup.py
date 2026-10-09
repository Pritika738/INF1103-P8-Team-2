import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Health History & Consultation Preparation",
    page_icon="🩺",
    layout="centered"
)


# --------------------------------------------------
# PAGE STATE
# --------------------------------------------------

# When the app first opens, start on the login page.
if "page" not in st.session_state:
    st.session_state.page = "login"


# --------------------------------------------------
# LOGIN SCREEN
# --------------------------------------------------

def show_login():
    st.title("Health History & Consultation Preparation")

    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.write("Don't have an account?")

    if st.button("Create Account"):
        st.session_state.page = "register"
        st.rerun()


# --------------------------------------------------
# CREATE ACCOUNT SCREEN
# --------------------------------------------------

def show_register():
    st.title("Create Account")

    st.text_input("Username")
    st.text_input("Email")
    st.text_input("Password", type="password")

    if st.button("Create Account"):
        st.success("Account creation will be implemented later.")

    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.rerun()


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

def show_dashboard():
    st.title("Profile Dashboard")

    st.subheader("User's Profile")

    st.write("**Records Stored:** 0")
    st.write("**Latest Record:** No records yet")

    st.divider()

    if st.button("➕ Add Medical Report"):
        st.session_state.page = "upload"
        st.rerun()

    if st.button("View Health History"):
        st.session_state.page = "history"
        st.rerun()

    if st.button("View Health Trends"):
        st.session_state.page = "trends"
        st.rerun()

    if st.button("Generate Consultation Report"):
        st.session_state.page = "consultation"
        st.rerun()

    st.divider()

    if st.button("Log Out"):
        st.session_state.page = "login"
        st.rerun()


# --------------------------------------------------
# TEMPORARY EMPTY SCREENS
# --------------------------------------------------

def show_upload():
    st.title("Add Medical Report")

    st.write("Medical report upload will go here.")

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def show_history():
    st.title("Health History")

    st.write("Health history will go here.")

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def show_trends():
    st.title("Health Trends")

    st.write("Health trend graphs will go here.")

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def show_consultation():
    st.title("Consultation Preparation Report")

    st.write("Consultation report will go here.")

    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


# --------------------------------------------------
# DECIDE WHICH SCREEN TO SHOW
# --------------------------------------------------

if st.session_state.page == "login":
    show_login()

elif st.session_state.page == "register":
    show_register()

elif st.session_state.page == "dashboard":
    show_dashboard()

elif st.session_state.page == "upload":
    show_upload()

elif st.session_state.page == "history":
    show_history()

elif st.session_state.page == "trends":
    show_trends()

elif st.session_state.page == "consultation":
    show_consultation()