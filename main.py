import streamlit as st
from utils.auth import auth_flow
from utils.db import *

seed_admin_user()

st.markdown("""
                    <style>
                    [data-testid="stSidebarNav"] {
                        display: none;
                    }
                    </style>
                    """, unsafe_allow_html=True)
if not auth_flow():
    st.stop()

ip = get_ip()
log_login_activity(st.session_state.email, "Login", ip)

role = st.session_state.user_record.get('role','user').lower()

st.set_page_config(initial_sidebar_state="collapsed")

if role == 'admin':
    st.switch_page("pages/1_admin.py")
elif role == "manager":
    st.switch_page("pages/2_Dashboard.py")