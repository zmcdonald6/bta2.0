import streamlit as st
import time
"""
Contains standard sidebar menu options.
"""

role = st.session_state.user_record.get('role','user').lower()



def sidebar_user_menu():
    user_name = st.session_state.get("name", "User")
    st.markdown("""
                    <style>
                    [data-testid="stSidebarNav"] {
                        display: none;
                    }
                    </style>
                    """, unsafe_allow_html=True)
    with st.sidebar:
        
       
        
        try:
            with st.expander(user_name, expanded=False):
                if st.button("Profile"):
                    st.switch_page("pages/2_profile.py")
        except Exception as e:
            st.error("Page not found")
            
            st.warning("Redirecting to relevant page")

            if role == "admin":
                st.warning("Redirecting to home page ...")
                time.sleep(3)
                st.switch_page("pages/1_Admin.py")    
        
        
        
    return True