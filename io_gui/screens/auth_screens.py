"""Login, quick-login-with-PIN and registration screens."""

import streamlit as st

from core import (
    hero, go, load_accounts,
    authenticate_temporary_account, authenticate_with_pin,
    validate_username, validate_password, validate_pin,
    create_temporary_account, PIN_MAX_ATTEMPTS,
)

def show_login():
    left, mid, right = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(
            "<div class='vt-hero' style='text-align:center;margin-top:2.5rem;'>"
            "<div class='vt-bob' style='font-size:3.8rem;'>🩺</div>"
            "<h1 style='margin:0;font-size:2.7rem;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);"
            "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>PASSAY</h1>"
            "<p style='color:var(--text-muted);'>"
            "Track your health over time and prepare for your next appointment.</p></div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.subheader("Welcome back")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Log In", type="primary", width="stretch"):
                if not username.strip():
                    st.error("Please enter your username.")
                elif not password:
                    st.error("Please enter your password.")
                elif not authenticate_temporary_account(username, password):
                    st.error("Incorrect username or password.")
                else:
                    accounts = load_accounts()
                    account = accounts[username.strip().lower()]
                    st.session_state.username = account["username"]
                    go("dashboard")
            st.caption("Don't have an account?")
            if st.button("Create Account", width="stretch"):
                go("register")
            if st.button("Quick Login with PIN", width="stretch"):
                go("pin_login")

def show_pin_login():
    left, mid, right = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(
            "<div class='vt-hero' style='text-align:center;margin-top:2.5rem;'>"
            "<div class='vt-bob' style='font-size:3.8rem;'>🔑</div>"
            "<h1 style='margin:0;font-size:2.3rem;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);"
            "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>Quick Login with PIN</h1>"
            "<p style='color:var(--text-muted);'>"
            "Enter your username and 4-digit PIN for faster sign-in.</p></div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            attempts = st.session_state.get("pin_attempts", 0)
            if attempts >= PIN_MAX_ATTEMPTS:
                st.error("Too many incorrect PIN attempts. Please sign in with your password instead.")
            else:
                pin_username = st.text_input("Username", key="pin_login_username")
                pin_value = st.text_input("4-digit PIN", type="password", max_chars=4, key="pin_login_pin")
                if st.button("Log In with PIN", type="primary", width="stretch"):
                    pin_error = validate_pin(pin_value)
                    if not pin_username.strip():
                        st.error("Please enter your username.")
                    elif pin_error:
                        st.error(pin_error)
                    elif authenticate_with_pin(pin_username, pin_value):
                        accounts = load_accounts()
                        account = accounts[pin_username.strip().lower()]
                        st.session_state.username = account["username"]
                        st.session_state.pop("pin_attempts", None)
                        go("dashboard")
                    else:
                        st.session_state["pin_attempts"] = attempts + 1
                        remaining = PIN_MAX_ATTEMPTS - st.session_state["pin_attempts"]
                        if remaining > 0:
                            st.error(f"Incorrect username or PIN. {remaining} attempt(s) remaining.")
                        else:
                            st.error("Too many incorrect PIN attempts. Please sign in with your password instead.")
            st.write("")
            if st.button("Back to Login", width="stretch"):
                st.session_state.pop("pin_attempts", None)
                go("login")

def show_register():
    left, mid, right = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(
            "<div class='vt-hero' style='text-align:center;margin-top:2rem;'>"
            "<div class='vt-bob' style='font-size:3rem;'>🩺</div>"
            "<h1 style='margin:0;"
            "background:linear-gradient(90deg,#a78bfa,#5eead4);"
            "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>Create Account</h1>"
            "<p style='color:var(--text-muted);'>Create your secure PASSAY profile.</p></div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            username = st.text_input("Username", key="register_username")
            password = st.text_input("Password", type="password", key="register_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm_password")
            st.caption("Password must contain at least 8 characters, including an uppercase letter, "
                       "a lowercase letter, a number and a special character.")
            if st.button("Create Account", type="primary", width="stretch"):
                username_error = validate_username(username)
                password_error = validate_password(password)
                if username_error:
                    st.error(username_error)
                elif password_error:
                    st.error(password_error)
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    created, message = create_temporary_account(username, password)
                    if created:
                        st.success("Account created successfully.")
                        st.info("Your account is ready. Return to Login to continue.")
                    else:
                        st.error(message)
            if st.button("Back to Login", width="stretch"):
                go("login")
