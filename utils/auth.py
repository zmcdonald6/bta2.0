"""
Helper functions for application authorization.
"""



import time
import streamlit as st
import bcrypt
import base64
from datetime import datetime, timedelta

from .db import (
    get_user_by_email,
    update_password,
    log_login_activity,
    get_ip
)



# ============================================================
# INITIALIZE LOCAL SESSION STATE
# ============================================================
def init_auth_session():
    defaults = {
        "authenticated": False,
        "email": "",
        "name": "",
        "user_record": {},
        "force_pw_change": False,
        "last_active": datetime.now(),
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ============================================================
# INACTIVITY TIMEOUT
# ============================================================
INACTIVITY_MINUTES = 10

def inactivity_timeout():
    if st.session_state.authenticated:
        elapsed = datetime.now() - st.session_state.last_active
        if elapsed > timedelta(minutes=INACTIVITY_MINUTES):
            st.warning("⏱ Session timed out due to inactivity.")
            ip = get_ip()
            log_login_activity(st.session_state.email, "Auto Logout (Inactivity)", ip)
            logout_user()
            st.rerun()
        else:
            st.session_state.last_active = datetime.now()


# ============================================================
# LOGOUT
# ============================================================
def logout_user():
    st.session_state.authenticated = False
    st.session_state.email = ""
    st.session_state.name = ""
    st.session_state.user_record = {}
    st.session_state.force_pw_change = False

def logout_button():
    st.markdown(
        """
        <style>
            div.stButton > button:first-child {
                float: right;
                background-color: #d9534f;
                color: white;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Logout"):
        logout_user()
        st.switch_page("main.py")
        st.rerun

# ============================================================
# LOGIN SCREEN
# ============================================================
def render_login_screen():
    st.set_page_config(page_title = "Login", initial_sidebar_state="collapsed")

    #Logo
    left, center, right = st.columns([3, 5, 1])
    with center:
        st.image("static/mussonjamaica_1_0.png", width=200)

    st.write("")    #space between logo and login screen.

    
    
    left, center, right = st.columns([1, 4, 1])
    with center:
        st.header("🔐 Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

            if submit:
                user = get_user_by_email(email)

                if not user:
                    st.error("❌ Email not found.")
                    return

                try:
                    decoded_hash = base64.b64decode(user["hashed_password"])
                except:
                    st.error("❌ Corrupted stored password.")
                    return

                if not bcrypt.checkpw(password.encode(), decoded_hash):
                    st.error("❌ Incorrect password.")
                    return

                # Set login state
                st.session_state.authenticated = True
                st.session_state.email = email
                st.session_state.name = user["name"]
                st.session_state.user_record = user
                st.session_state.last_active = datetime.now()

                # First login → must update password
                if user.get("first_login", False):
                    st.session_state.force_pw_change = True
                    st.rerun()

                # Save persistent cookie
                token_value = f"{email}|{int(time.time())}"
                # cookies[COOKIE_NAME] = token_value
                # cookies.save()

                st.rerun()


# ============================================================
# FIRST LOGIN PASSWORD RESET
# ============================================================
def render_first_login_reset():
    st.title("🔑 Reset Password")

    with st.form("reset_form"):
        pw1 = st.text_input("New Password", type="password")
        pw2 = st.text_input("Confirm New Password", type="password")
        submit = st.form_submit_button("Update Password")

        if submit:
            if len(pw1) < 8:
                st.error("Password must be at least 8 characters.")
                return
            if pw1 != pw2:
                st.error("Passwords do not match.")
                return

            new_hash = bcrypt.hashpw(pw1.encode(), bcrypt.gensalt())
            encoded = base64.b64encode(new_hash).decode()

            update_password(st.session_state.email, encoded)

            st.session_state.user_record["first_login"] = False
            st.session_state.user_record["hashed_password"] = encoded
            st.session_state.force_pw_change = False

            # Refresh cookie timestamp
            token_value = f"{st.session_state.email}|{int(time.time())}"
            # cookies[COOKIE_NAME] = token_value
            # cookies.save()

            st.success("Password updated successfully.")
            st.rerun()


# ============================================================
# MASTER LOGIN FLOW
# ============================================================
def auth_flow():
    init_auth_session()
    inactivity_timeout()
 
    # Not logged in
    if not st.session_state.authenticated and not st.session_state.force_pw_change:
        render_login_screen()
        return False

    # First login password update
    if st.session_state.force_pw_change:
        render_first_login_reset()
        return False

    # Logged in
    if st.button("🚪 Logout"):
        ip = get_ip()
        log_login_activity(st.session_state.email, "Logout", ip)
        logout_user()
        st.rerun()

    return True


def require_login():
    if not st.session_state.get("authenticated", False):
        st.warning("You need to be logged in to access this page.")
        time.sleep(3)
        st.switch_page("main.py")
        st.stop()