import streamlit as st
import bcrypt
from utils.db import get_user_by_email, update_password
import time
import base64

st.set_page_config("Profile", initial_sidebar_state = "collapsed")

if st.session_state.user_record.get('role') != 'admin':
    st.markdown("""
    <style>
        /* Hide the admin page link */
        [data-testid="stSidebarNav"] li:nth-child(2) {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)


st.title("Your Profile")

st.subheader("Account Information")
st.write ("")

#Displaying user information
user = st.session_state.user_record

st.write(f"Name: {user.get('name')}")
st.write(f"Email: {st.session_state.email}")
st.write(f"Role: {st.session_state.user_record.get("role")}")

# # with st.expander("Change Password"):
#     current_pwd = st.text_input("Current Password", type = "password")
#     new_pwd = st.text_input("New Passwrrd", type = "password")
#     confirm_pwd = st.text_input("Confirm New Password", type = "password")

#     #Pulling user record
#     user = get_user_by_email(st.session_state.email)

#     #2 Validate current password
#     if not bcrypt.checkpw(current_pwd.encode(), user["hashed_password"].encode()):
#         st.error("Incorect current password")
#         st.stop()

#     #3 Check new password match
#     elif new_pwd != confirm_pwd:
#         st.error("New passwords do not match")
#         st.stop()

#     #hashing new password
#     hashed = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt().decode())

#     update_password(st.session_state.email, hashed)

#     st.success("Password updated successfully")
#     st.info("You will need to use this new password the next time you log in.")

#     time.sleep(3)
#     if st.session_state.user_record.get('role') == 'admin':
#         st.switch_page("pages/1_admin.py")
#     elif st.session_state.user_record.get('role') != 'user':
#         pass

# with st.expander("Change Password"):
#     current_pwd = st.text_input("Current Password", type="password")
#     new_pwd = st.text_input("New Password", type="password")
#     confirm_pwd = st.text_input("Confirm New Password", type="password")

#     user = get_user_by_email(st.session_state.email)

#     # Decode stored hash from base64 back into bcrypt format
#     try:
#         stored_hash = base64.b64decode(user["hashed_password"])
#     except Exception:
#         st.error("Stored password is invalid.")
#         st.stop()

#     # Validate current password
#     if not bcrypt.checkpw(current_pwd.encode(), stored_hash):
#         st.error("Incorrect current password.")
#         st.stop()

#     # Check new password match
#     if new_pwd != confirm_pwd:
#         st.error("New passwords do not match.")
#         st.stop()

#     # Hash new password (bcrypt returns bytes)
#     bcrypt_hash = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt())

#     # Encode in base64 before saving — REQUIRED for your system
#     stored_format = base64.b64encode(bcrypt_hash).decode()

#     # Save to DB
#     update_password(st.session_state.email, stored_format)

#     st.success("Password updated successfully.")
#     st.info("You will need to use this new password next login.")

#     time.sleep(3)
#     role = st.session_state.user_record.get('role')

#     if role == 'admin':
#         st.switch_page("pages/1_admin.py")

with st.expander("Change Password"):
    current_pwd = st.text_input("Current Password", type="password")
    new_pwd = st.text_input("New Password", type="password")
    confirm_pwd = st.text_input("Confirm New Password", type="password")

    if st.button("Update Password"):   # <<< THIS IS THE FIX
        
        user = get_user_by_email(st.session_state.email)

        # Decode stored hash from base64 back into bcrypt format
        try:
            stored_hash = base64.b64decode(user["hashed_password"])
        except Exception:
            st.error("Stored password is invalid.")
            st.stop()

        # Validate current password
        if not bcrypt.checkpw(current_pwd.encode(), stored_hash):
            st.error("Incorrect current password.")
            st.stop()

        # Check new password match
        if new_pwd != confirm_pwd:
            st.error("New passwords do not match.")
            st.stop()

        # Hash new password (bcrypt returns bytes)
        bcrypt_hash = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt())

        # Encode in base64 before saving — REQUIRED for your system
        stored_format = base64.b64encode(bcrypt_hash).decode()

        # Save to DB
        update_password(st.session_state.email, stored_format, first_login=False)

        st.success("Password updated successfully.")
        st.info("You will need to use this new password next login.")

        time.sleep(3)
        role = st.session_state.user_record.get('role')

        if role == 'admin':
            st.switch_page("pages/1_admin.py")

