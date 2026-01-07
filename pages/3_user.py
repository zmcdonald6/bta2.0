import streamlit as st
import pandas as pd
from datetime import datetime

from utils.db import (
    get_uploaded_files,
    get_active_budget,
    set_active_budget,
    get_all_users,
    add_user,
    delete_user,
    reset_user_password,
    get_login_logs,
    delete_uploaded_file,
    load_budget_state_monthly,
    save_budget_state_monthly,
    get_active_budget_metadata
)
from utils.auth import logout_button, require_login
from utils.expense_parser import parseExpense, get_expense_cache_key
from utils.budget_parser import load_active_budget
from utils.budget_adapter import adapt_budget_long_to_classification




from components.menu import sidebar_user_menu
from components.dashboard import render_report_dashboard
from components.classification_dashboard import render_classification_dashboard

#PAGE SETUP

st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

#Login logic
require_login()
sidebar_user_menu()
logout_button()

role = st.session_state.user_record.get("role", "").lower()
email = st.session_state.user_record.get("email", "").lower()

if role != "user" and role != "admin":
    st.write("Problem")
    st.error("You do not have permission to view this page")
    st.stop()


st.sidebar.title("👤 User Panel")

#Sidebar display options
user_choice = st.sidebar.radio(
    "Menu",
    [
        "📊 Dashboard",
        "📁 File Management",
        "🎯 Active Budget",
        
    ]
)

#Dashboard display
if user_choice == "📊 Dashboard":
    #Loading current active budget and transforming it to fit the classification dataframe
    budget_df_long = load_active_budget()
    budget_df = adapt_budget_long_to_classification(budget_df_long)
    

    #Getting budget metadata
    budgetdata = get_active_budget_metadata()
    budgetyear = budgetdata.get("year")
    budget_type= budgetdata.get("file_type")
    selected_budget = budgetdata.get("file_name")

    #Parsing expenses
    expense_df = parseExpense(expense_file_id=st.secrets["GOOGLE"]["expense_sheet"],
                              budget_year=budgetyear,
                              budget_type=budget_type,
                              cache_day_key=get_expense_cache_key())
    
    #Displaying dashboard
    render_report_dashboard(
    df_budget=budget_df,
    df_expense=expense_df,
    selected_budget=selected_budget,
    render_classification_dashboard=render_classification_dashboard,
    load_budget_state_monthly=load_budget_state_monthly,
    save_budget_state_monthly=save_budget_state_monthly,
)

#File Uploader
if user_choice == "📁 File Management":
    st.subheader("📁 File Management")

    #Pulling files from the database and converting to dataframe
    files = get_uploaded_files()
    df_files = pd.DataFrame(files)

    # Filter files to only show those uploaded by the current user
    if not df_files.empty and "uploader_email" in df_files.columns:
        df_files = df_files[df_files["uploader_email"].str.lower() == email.lower()]
    elif not df_files.empty:
        # If uploader_email column doesn't exist, show empty
        df_files = pd.DataFrame()

    # -----------------------------
    # VIEW FILES
    # -----------------------------
    if df_files.empty:
        st.info("No uploaded files found.")
    else:
        st.dataframe(df_files, width='content')

    st.divider()

    #FILE UPLOAD FORM
    with st.expander("Upload Files"):
        with st.form("file_upload_form"):
            uploaded = st.file_uploader("Choose a .xlsx file", type=["xlsx"])
            custom_name = st.text_input("Custom File Name (Required)")
            file_type = st.selectbox(
                "Budget Type",
                ["budget(opex)", "budget(capex)"]
            )

            #Pulling current year, select box options for the year.
            #Displays options for the previous 5 years and future 5 years.
            current_year = datetime.now().year
            year_opts = [year for year in range(current_year-5, current_year + 6)]
            year = st.selectbox("Input Year", options=year_opts, index=5)

            submit_upload = st.form_submit_button("Upload File")

            if submit_upload:
                if not uploaded:
                    st.error("Please choose a file.")
                elif not custom_name.strip():
                    st.error("Please enter a file name.")
                elif not year:
                    st.error("Please input budget year")
                else:
                    from utils.drive_utils import upload_to_drive_and_log
                    try:
                        result_url = upload_to_drive_and_log(
                            uploaded,
                            file_type,
                            st.session_state.email,
                            custom_name,
                            year
                        )

                        if result_url:
                            st.success("✅ File uploaded successfully.")
                            st.write(f"[View File]({result_url})")
                            st.rerun()
                        else:
                            st.error("Upload failed. Please try again.")

                    except Exception as e:
                        st.error(f"Upload error: {e}")

    #File delete form
    with st.expander("Delete Files"):
        st.subheader("🗑️ Delete File Record")
        if df_files.empty:
            st.info("No files available to delete.")
        else:
            selected_file = st.selectbox(
                "Select file record to delete",
                df_files["file_name"].tolist()
            )

            # Quick details
            sel_row = df_files[df_files["file_name"] == selected_file].iloc[0]
            st.caption(
                f"Type: {sel_row.get('file_type')} • "
                f"Uploaded by: {sel_row.get('uploader_email')} • "
                f"At: {sel_row.get('upload_date') or sel_row.get('timestamp', 'N/A')}"
            )

            # Additional security check - ensure user can only delete their own files
            uploader_email = sel_row.get('uploader_email', '').lower()
            if uploader_email != email.lower():
                st.error("You can only delete files you uploaded.")
            else:
                confirm = st.checkbox("Yes, delete this file record")
                if st.button("Delete File Record"):
                    if not confirm:
                        st.error("Please confirm deletion first.")
                    else:
                        try:
                            delete_uploaded_file(selected_file)
                            st.success("File record deleted.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting record: {e}")

if user_choice == "🎯 Active Budget":
    st.subheader("🎯 Active Budget Selection")

    ##Pulling uploaded files and putting them in a dataframe
    files = get_uploaded_files()
    df_files = pd.DataFrame(files)

    if df_files.empty:
        st.info("No uploaded files found.")
    else:
        # Only show budget files
        df_budget_files = df_files[
            df_files["file_type"].str.contains("budget", case=False, na=False)
        ]

        if df_budget_files.empty:
            st.warning("No budget files found. Upload one first.")
        else:
            # Current active budget
            try:
                current_active = get_active_budget()
                st.caption(f"Current Active Budget: **{current_active}**")
            except Exception:
                current_active = None
                st.caption("Current Active Budget: **None Set**")

            budget_options = df_budget_files["file_name"].tolist()

            selected = st.selectbox(
                "Select a budget file:",
                budget_options,
                index=budget_options.index(current_active) if current_active in budget_options else 0
            )

            if st.button("🚀 Set as Active Budget"):
                try:
                    set_active_budget(selected)
                    st.success(f"Active budget updated to: **{selected}**")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to set active budget: {e}")
