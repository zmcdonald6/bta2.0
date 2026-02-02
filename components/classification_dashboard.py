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
    
    # Track pending new allocations (added but not yet saved)
    pending_allocations_key = f"pending_allocations_{selected_budget}"
    if pending_allocations_key not in st.session_state:
        st.session_state[pending_allocations_key] = []

    # ============================================================
    # ALWAYS LOAD STATE FROM MYSQL
    # ============================================================
    saved_state = load_budget_state_monthly(selected_budget)

    # Build base budget DF with annual totals
    base_df = df_budget[["Category", "Sub-Category", "Total"]].copy()
    base_df = base_df.rename(columns={"Total": "Total Amount"})

    # ============================================================
    # PREPARE DATA FOR TWO-TABLE VIEW
    # ============================================================
    # Load all individual allocations
    if not saved_state.empty and "Allocated Amount" in saved_state.columns:
        # Convert Allocated Amount to numeric
        saved_state["Allocated Amount"] = pd.to_numeric(saved_state["Allocated Amount"], errors='coerce').fillna(0)
        # Filter out rows with zero or null allocated amounts
        allocations_df = saved_state[saved_state["Allocated Amount"] > 0].copy()
    else:
        allocations_df = pd.DataFrame(columns=["Category", "Sub-Category", "Amount", "Allocated Amount", "Status Category"])

    # Create main summary table: one row per line item
    # Merge base budget with allocated totals
    if not allocations_df.empty:
        # Sum allocated amounts per line item
        allocated_totals = allocations_df.groupby(["Category", "Sub-Category"])["Allocated Amount"].sum().reset_index()
        allocated_totals.columns = ["Category", "Sub-Category", "Allocated Amount"]
        
        # Merge with base budget
        main_table = base_df.merge(
            allocated_totals,
            on=["Category", "Sub-Category"],
            how="left"
        )
        main_table["Allocated Amount"] = main_table["Allocated Amount"].fillna(0)
    else:
        main_table = base_df.copy()
        main_table["Allocated Amount"] = 0

    # Calculate remaining balance
    main_table["Remaining Balance"] = main_table["Total Amount"] - main_table["Allocated Amount"]

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
    

    # Compute summary using allocated amounts (not full amounts)
    if saved_state.empty:
        rows_summary = pd.DataFrame({
            "Status Category": status_options,
            "Total": [0] * len(status_options)
        })
    else:
        # Use Allocated Amount if available, otherwise fall back to Amount
        if "Allocated Amount" in saved_state.columns:
            amount_col = "Allocated Amount"
        else:
            amount_col = "Amount"
        
        rows_summary = (
            saved_state.groupby("Status Category")[amount_col]
            .sum()
            .reset_index()
            .rename(columns={amount_col: "Total"})
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
    # BUDGET CLASSIFICATIONS - TWO TABLE VIEW
    # ============================================================
    #Creating space between dashboard and editor
    st.write("")
    st.write("")
    st.write("")
    with st.expander("Apply Budget Classifications"):
        st.subheader("📘 Budget Classifications")
        
        # ============================================================
        # MAIN TABLE: One row per line item
        # ============================================================
        st.markdown("### 📋 Budget Line Items Summary")
        st.caption("Overview of all budget line items with allocated amounts and remaining balances")
        
        main_table_display = main_table[["Category", "Sub-Category", "Total Amount", "Allocated Amount", "Remaining Balance"]].copy()
        
        st.dataframe(
            main_table_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Total Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Allocated Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Remaining Balance": st.column_config.NumberColumn(format="$%.2f"),
            }
        )
        
        st.write("")  # Spacing
        
        # ============================================================
        # ALLOCATIONS MANAGEMENT TABLE
        # ============================================================
        st.markdown("### 🔧 Manage Allocations")
        st.caption("View, edit, and delete individual budget allocations. Filter by Status Category to find specific allocations.")
        
        # Prepare allocations table for editing
        if not allocations_df.empty:
            # Merge with base_df to get Amount (total budget) for each allocation
            allocations_display = allocations_df.merge(
                base_df[["Category", "Sub-Category", "Total Amount"]],
                on=["Category", "Sub-Category"],
                how="left"
            )
            # Select and reorder columns
            allocations_display = allocations_display[["Category", "Sub-Category", "Total Amount", "Allocated Amount", "Status Category"]]
        else:
            # Create empty structure
            allocations_display = pd.DataFrame(columns=["Category", "Sub-Category", "Total Amount", "Allocated Amount", "Status Category"])
        
        # Add pending allocations from session state
        if st.session_state[pending_allocations_key]:
            pending_df = pd.DataFrame(st.session_state[pending_allocations_key])
            allocations_display = pd.concat([allocations_display, pending_df], ignore_index=True)
        
        # Filter by Status Category
        if not allocations_display.empty:
            # Get all unique status categories (including from pending)
            all_statuses = sorted(allocations_display["Status Category"].dropna().unique().tolist())
            status_filter = st.selectbox(
                "Filter by Status Category:",
                options=["All"] + all_statuses,
                key=f"status_filter_{selected_budget}"
            )
            
            if status_filter != "All":
                allocations_display = allocations_display[allocations_display["Status Category"] == status_filter]
        
        # Add new allocation section
        with st.expander("➕ Add New Allocation"):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # Get unique categories
                categories = sorted(base_df["Category"].unique().tolist())
                new_category = st.selectbox("Category", options=categories, key="new_alloc_category")
            
            with col2:
                # Get subcategories for selected category
                subcategories = sorted(base_df[base_df["Category"] == new_category]["Sub-Category"].unique().tolist())
                new_subcategory = st.selectbox("Sub-Category", options=subcategories, key="new_alloc_subcategory")
            
            with col3:
                # Get total amount for this line item
                line_item_total = base_df[
                    (base_df["Category"] == new_category) & 
                    (base_df["Sub-Category"] == new_subcategory)
                ]["Total Amount"].iloc[0] if not base_df[
                    (base_df["Category"] == new_category) & 
                    (base_df["Sub-Category"] == new_subcategory)
                ].empty else 0
                
                # Get current allocated amount for this line item (from DB + pending)
                current_allocated_db = allocations_df[
                    (allocations_df["Category"] == new_category) & 
                    (allocations_df["Sub-Category"] == new_subcategory)
                ]["Allocated Amount"].sum() if not allocations_df[
                    (allocations_df["Category"] == new_category) & 
                    (allocations_df["Sub-Category"] == new_subcategory)
                ].empty else 0
                
                # Add pending allocations for this line item
                current_allocated_pending = sum(
                    [alloc["Allocated Amount"] for alloc in st.session_state[pending_allocations_key]
                    if alloc["Category"] == new_category and alloc["Sub-Category"] == new_subcategory]
                )
                
                current_allocated = current_allocated_db + current_allocated_pending
                available = line_item_total - current_allocated
                st.metric("Available", f"${available:,.2f}")
            
            with col4:
                new_allocated = st.number_input(
                    "Allocated Amount",
                    min_value=0.0,
                    max_value=float(available) if available > 0 else 0.0,
                    value=0.0,
                    step=100.0,
                    key="new_alloc_amount"
                )
                new_status = st.selectbox("Status Category", options=editor_options, key="new_alloc_status")
            
            if st.button("Add Allocation", key="add_new_alloc"):
                if new_allocated > 0 and new_status:
                    # Add to pending allocations in session state
                    new_allocation = {
                        "Category": new_category,
                        "Sub-Category": new_subcategory,
                        "Total Amount": float(line_item_total),
                        "Allocated Amount": float(new_allocated),
                        "Status Category": new_status
                    }
                    st.session_state[pending_allocations_key].append(new_allocation)
                    st.success(f"✅ Added allocation: ${new_allocated:,.2f} for {new_category} - {new_subcategory}")
                    st.rerun()
                else:
                    st.warning("⚠️ Please enter a valid allocated amount and select a status category.")
        
        # Allocations editor
        if not allocations_display.empty:
            editor_cols = {
                "Total Amount": st.column_config.NumberColumn(disabled=True, format="$%.2f"),
                "Allocated Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Status Category": st.column_config.SelectboxColumn(options=editor_options),
            }
            
            editor_key = f"allocations_editor_{selected_budget}_{st.session_state.editor_version}"
            
            edited_allocations = st.data_editor(
                allocations_display,
                column_config=editor_cols,
                width='stretch',
                key=editor_key,
                num_rows="dynamic"  # Allow deleting rows
            )
        else:
            edited_allocations = allocations_display.copy()
            st.info("ℹ️ No allocations yet. Use the 'Add New Allocation' section above to create your first allocation.")
        
        # ============================================================
        # SAVE BUTTON
        # ============================================================
        if st.button("💾 Save All Allocations", key="save_allocations"):
            if edited_allocations.empty:
                # If no allocations, delete all existing ones
                from utils.db import get_db
                db = get_db()
                with db.cursor() as c:
                    c.execute("DELETE FROM budget_state WHERE file_name = %s", (selected_budget,))
                db.commit()
                # Clear pending allocations
                st.session_state[pending_allocations_key] = []
                st.success("✅ All allocations cleared.")
                st.session_state.editor_version += 1
                st.rerun()
            else:
                # Filter out invalid rows
                valid_allocations = edited_allocations[
                    (edited_allocations["Status Category"].notna()) & 
                    (edited_allocations["Status Category"] != "") &
                    (edited_allocations["Allocated Amount"].notna()) &
                    (pd.to_numeric(edited_allocations["Allocated Amount"], errors='coerce') > 0)
                ].copy()
                
                if valid_allocations.empty:
                    st.warning("⚠️ No valid allocations to save. Please add at least one allocation with a Status Category and Allocated Amount > 0.")
                else:
                    # Merge with annual totals from budget to get Amount (total budget)
                    final_df = valid_allocations.merge(
                        df_budget[["Category", "Sub-Category", "Total"]],
                        on=["Category", "Sub-Category"],
                        how="left"
                    )
                    
                    # Rename Total to Amount for database compatibility
                    final_df = final_df.rename(columns={"Total": "Amount"})
                    
                    # Select required columns
                    final_df = final_df[["Category", "Sub-Category", "Amount", "Allocated Amount", "Status Category"]]
                    
                    # Replace NaN with None for MySQL compatibility
                    final_df = final_df.where(pd.notnull(final_df), None)
                    
                    # Delete all existing allocations for this budget first, then insert new ones
                    from utils.db import get_db
                    db = get_db()
                    with db.cursor() as c:
                        c.execute("DELETE FROM budget_state WHERE file_name = %s", (selected_budget,))
                    db.commit()
                    
                    # Save new allocations
                    save_budget_state_monthly(selected_budget, final_df, st.session_state.email)
                    
                    # Clear pending allocations
                    st.session_state[pending_allocations_key] = []
                    
                    # Force clean widget reload
                    st.session_state.editor_version += 1
                    
                    st.success("🎉 Saved! Reloading updated classifications...")
                    st.rerun()
