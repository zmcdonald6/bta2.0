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

from streamlit_cookies_manager import EncryptedCookieManager

#Managing Cookies
COOKIE_TTL = 43200
def init_cookies():
    cookies = EncryptedCookieManager(prefix = st.secrets["cookies"]["prefix"],
                                     password = st.secrets["cookies"]["cookie_secret"])
    return cookies

#restoring session state values from cookies.
def restore_session_from_cookie(cookies: EncryptedCookieManager):
    if "email" not in cookies or "login_time" not in cookies:
        return False

    try:
        login_time = int(cookies["login_time"])
    except ValueError:
        return False

    if time.time() - login_time > COOKIE_TTL:
        cookies.clear()
        cookies.save()
        return False

    user = get_user_by_email(cookies["email"])
    if not user:
        cookies.clear()
        cookies.save()
        return False

    st.session_state.authenticated = True
    st.session_state.email = user["email"]
    st.session_state.name = user["name"]
    st.session_state.user_record = user
    st.session_state.last_active = datetime.now()
    return True


def set_login_cookie(cookies, email):
    cookies["email"] = email
    cookies["login_time"] = str(int(time.time()))
    cookies.save()


def clear_login_cookie(cookies):
    cookies.clear()
    cookies.save()

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
INACTIVITY_MINUTES = 30

def inactivity_timeout():
    if st.session_state.authenticated:
        elapsed = datetime.now() - st.session_state.last_active
        if elapsed > timedelta(minutes=INACTIVITY_MINUTES):
            ip = get_ip()
            log_login_activity(st.session_state.email, "Auto Logout (Inactivity)", ip)

            logout_user()
            clear_login_cookie(init_cookies())

            st.warning("Session timed out due to inactivity.")
            


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
        st.rerun()

# ============================================================
# LOGIN SCREEN
# ============================================================
def render_login_screen(cookies):
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
                set_login_cookie(cookies, email)

                st.rerun()


# ============================================================
# FIRST LOGIN PASSWORD RESET
# ============================================================
def render_first_login_reset(cookies):
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
            set_login_cookie(cookies, st.session_state.email)

            st.success("Password updated successfully.")
            st.rerun()


# ============================================================
# MASTER LOGIN FLOW
# ============================================================
def auth_flow():
    init_auth_session()
    cookies = init_cookies()

    if not cookies.ready():
        st.write("Initializing session")
        st.stop()

    #inactivity_timeout()

    #if not st.session_state.authenticated:
    #    restore_session_from_cookie(cookies)


    # Not logged in
    if not st.session_state.authenticated and not st.session_state.force_pw_change:
        render_login_screen(cookies)
        return False

    # First login password update
    if st.session_state.force_pw_change:
        render_first_login_reset(cookies)
        return False

    # Logged in
    if st.button("🚪 Logout"):
        ip = get_ip()
        log_login_activity(st.session_state.email, "Logout", ip)
        clear_login_cookie(cookies)
        logout_user()
        st.rerun()

    return True


def require_login():
    if not st.session_state.get("authenticated", False):
        st.warning("You need to be logged in to access this page.")
        time.sleep(3)
        st.switch_page("main.py")
        st.stop()