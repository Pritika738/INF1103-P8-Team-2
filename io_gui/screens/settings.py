"""Settings screen - manage the quick-login PIN."""

import streamlit as st

from core import (
    hero, severity_badge, current_user,
    user_has_pin, set_user_pin, remove_user_pin, validate_pin,
)

def show_settings():
    hero("Settings", "Manage how you sign in to PASSAY.")
    username = current_user()

    with st.container(border=True):
        st.subheader("Quick-login PIN")
        has_pin = user_has_pin(username)
        if has_pin:
            st.caption("A 4-digit PIN is currently set. You can use it with your username on the "
                       "login screen for faster sign-in. Set a new one below to replace it, or "
                       "remove it entirely.")
            st.markdown(severity_badge("info") + " &nbsp; "
                        "<span style='color:var(--text-muted);font-size:0.88rem;'>"
                        "PIN is active for this account.</span>", unsafe_allow_html=True)
        else:
            st.caption("Set a 4-digit PIN to sign in faster next time. You'll still enter your "
                       "username with it. A PIN is a convenience shortcut - keep using your password "
                       "if you prefer.")
        st.write("")
        new_pin = st.text_input("New 4-digit PIN", type="password", max_chars=4, key="settings_new_pin")
        confirm_pin = st.text_input("Confirm PIN", type="password", max_chars=4, key="settings_confirm_pin")
        cols = st.columns(2)
        with cols[0]:
            if st.button("Change PIN" if has_pin else "Set PIN", type="primary", width="stretch"):
                pin_error = validate_pin(new_pin)
                if pin_error:
                    st.error(pin_error)
                elif new_pin != confirm_pin:
                    st.error("The two PINs do not match.")
                elif set_user_pin(username, new_pin):
                    st.success("Your quick-login PIN has been saved.")
                    st.rerun()
                else:
                    st.error("Could not save your PIN. Please try again.")
        with cols[1]:
            if has_pin:
                if st.button("Remove PIN", width="stretch"):
                    if remove_user_pin(username):
                        st.success("Your quick-login PIN has been removed.")
                        st.rerun()
                    else:
                        st.error("Could not remove your PIN. Please try again.")

    st.caption("Security note: a 4-digit PIN is a convenience shortcut, not a replacement for your "
               "password. It is stored only as a salted hash, never in plain text, and is locked "
               "after several wrong attempts.")
