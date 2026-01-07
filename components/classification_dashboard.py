import streamlit as st
import pandas as pd
"""
Provides function to display budget classification dashboard.

Author: Zedaine McDonald
Date: 2025-11-26
"""

def render_classification_dashboard(df_budget, df_expense, selected_budget,
              load_budget_state_monthly, save_budget_state_monthly):
    """
    Logic to display a budget dashboard summary using coloured dashboard buttons.

    This function loads, saves and displays budget state as well as well as a summarized dashboard.

    Parameters:
    - df_budget: dataframe
        Budget dataframe with annual totals.
    - df_expense: dataframe
        Expense dataframe.
    - selected_budget: str
        File name of budget selected for the dashboard
    - load_budget_state_monthly: callable 
        Function that loads the state of the current budget (yearly classifications)
    - save_budget_state_monthly: callable
        Function that saves the current state of the budget (yearly classifications)
    """

    # ============================================================
    # SESSION STATE
    # ============================================================
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0   # bump after save

    # ============================================================
    # ALWAYS LOAD STATE FROM MYSQL
    # ============================================================
    saved_state = load_budget_state_monthly(selected_budget)

    # Build base budget DF with annual totals
    base_df = df_budget[["Category", "Sub-Category", "Total"]].copy()
    base_df = base_df.rename(columns={"Total": "Total Amount"})

    # Merge saved statuses
    if not saved_state.empty:
        # Merge saved status category
        merged_df = base_df.merge(
            saved_state[["Category", "Sub-Category", "Status Category"]],
            on=["Category", "Sub-Category"],
            how="left"
        )
    else:
        merged_df = base_df.copy()
        merged_df["Status Category"] = None

    # Column order: Category | Sub-Category | Total Amount | Status Category
    merged_df = merged_df[["Category", "Sub-Category", "Total Amount", "Status Category"]]

    # ============================================================
    # DASHBOARD SUMMARY — Tiles + Totals
    # ============================================================
    st.subheader("📊 Budget Health Summary")

    status_options = [
        "Wishlist", "To be confirmed", "Spent", "To be spent",
        "To be spent (Projects)", "To be spent (Recurring)",
        "Will not be spent", "Out of Budget"
    ]

    editor_options = [
        "Wishlist", "To be confirmed", "To be spent",
        "To be spent (Projects)", "To be spent (Recurring)",
        "Will not be spent"
    ]
    

    # Compute summary using annual totals
    if saved_state.empty:
        rows_summary = pd.DataFrame({
            "Status Category": status_options,
            "Total": [0] * len(status_options)
        })
    else:
        # Use Amount column which now contains annual totals
        rows_summary = (
            saved_state.groupby("Status Category")["Amount"]
            .sum()
            .reset_index()
            .rename(columns={"Amount": "Total"})
            .set_index("Status Category")
            .reindex(status_options, fill_value=0)
            .reset_index()
        )

    # Override "Spent" tile to reflect actual expenses
    
    # Top totals
    budget_total = df_budget["Total"].sum()
    spent_usd = df_expense["amount_spent"].sum()
    balance = budget_total - spent_usd

    rows_summary.loc[
        rows_summary["Status Category"] == "Spent",
        "Total"
    ] = spent_usd

    #Build valid budget key set
    valid_budget_keys = set(
        zip(
            df_budget["Category"],
            df_budget["Sub-Category"]
        )
    )

    expense_keys = list(
    zip(
        df_expense["category_display"],
        df_expense["subcategory_display"]
    )
)

    out_of_budget_mask = [
        key not in valid_budget_keys for key in expense_keys
    ]

    out_of_budget_total = df_expense.loc[
        out_of_budget_mask,
        "amount_spent"
    ].sum()

    rows_summary.loc[
    rows_summary["Status Category"] == "Out of Budget",
    "Total"
    ] = out_of_budget_total

    col1, col2 = st.columns(2)
    with col1: st.metric("Budget Total", f"{budget_total:,.2f}")
    with col2: st.metric("Budget Balance", f"{balance:,.2f}")

    # ============================================================
    # STATUS TILES (Restored)
    # ============================================================
    status_colors = {
        "Wishlist": "#BD9D69",
        "To be confirmed": "#F43FEE73",
        "Spent": "#3CE780",
        "To be spent": "#33FF00FF",
        "To be spent (Projects)": "#3498DB",
        "To be spent (Recurring)": "#1ABC9C",
        "Will not be spent": "#EE0909",
        "Out of Budget": "#F39C12",
    }

    rows = 2
    cols_per_row = 4

    for r in range(rows):
        row_cols = st.columns(cols_per_row)
        for c in range(cols_per_row):
            idx = r * cols_per_row + c
            if idx >= len(status_options):
                break

            st_status = rows_summary.loc[idx, "Status Category"]
            total = rows_summary.loc[idx, "Total"]

            with row_cols[c]:
                st.write(
                    f"""
                    <div style="background:{status_colors[st_status]};
                                padding:18px; border-radius:12px;
                                text-align:center; color:white;">
                        <strong>{st_status}</strong><br>
                        <span style="font-size:22px;">{total:,.2f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # ============================================================
    # Classifications EDITOR
    # ============================================================
    #Creating space between dashboard and editor
    st.write("")
    st.write("")
    st.write("")
    with st.expander("Apply Budget Classifications"):
        st.subheader("📘 Budget Classifications")

        editor_cols = {
            "Total Amount": st.column_config.NumberColumn(disabled=True, format="$%.2f"),
            "Status Category": st.column_config.SelectboxColumn(options=editor_options),
        }

        # Unique key ensures Streamlit never restores old data
        editor_key = f"editor_{selected_budget}_{st.session_state.editor_version}"

        edited_df = st.data_editor(
            merged_df,
            column_config=editor_cols,
            width='stretch',
            key=editor_key
        )

        # ============================================================
        # ONE-BUTTON SAVE — Writes to MySQL
        # ============================================================
        if st.button("💾 Save Classifications"):

            # Prepare data for saving - merge with annual totals from budget
            final_df = edited_df.merge(
                df_budget[["Category", "Sub-Category", "Total"]],
                on=["Category", "Sub-Category"],
                how="left"
            )

            # Rename Total to Amount for database compatibility
            final_df = final_df.rename(columns={"Total": "Amount"})

            # Select only required columns
            final_df = final_df[["Category", "Sub-Category", "Amount", "Status Category"]]

            # Replace NaN with None for MySQL compatibility
            final_df = final_df.where(pd.notnull(final_df), None)

            save_budget_state_monthly(selected_budget, final_df, st.session_state.email)

            # Force clean widget reload
            st.session_state.editor_version += 1

            st.success("🎉 Saved! Reloading updated classifications...")
            st.rerun()
