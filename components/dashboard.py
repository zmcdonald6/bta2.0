import streamlit as st
from .classification_dashboard import render_classification_dashboard
import pandas as pd

def render_report_dashboard(
    *,
    df_budget,
    df_expense,
    selected_budget:str,
    render_classification_dashboard,
    load_budget_state_monthly,
    save_budget_state_monthly,
    role: str = "user",
    expense_file_id: str = None,
    budget_year: int = None,
    budget_type: str = None,
):
    """
    Renders the FULL reporting dashboard.

    Assumptions:
    - df_budget and df_expense is already parsed, FX-converted, and filtered
    - selected_budget is known.
    - no required file selection.
    
    Function is purely a renderer.
    """

    # ============================
    # SECTION A — CLASSIFICATION
    # ============================
    
    render_classification_dashboard(
        df_budget=df_budget,
        df_expense=df_expense,
        selected_budget=selected_budget,
        load_budget_state_monthly=load_budget_state_monthly,
        save_budget_state_monthly=save_budget_state_monthly,
    )

    st.divider()
    

    st.subheader("📊 Year-To-Date Budget Report")

    # -----------------------------
    # 1. Prepare budget base
    # -----------------------------
    budget_base = (
        df_budget[["Category", "Sub-Category", "Total"]]
        .rename(columns={"Total": "Amount Budgeted"})
        .copy()
    )

    budget_base["Amount Budgeted"] = pd.to_numeric(
        budget_base["Amount Budgeted"], errors="coerce"
    ).fillna(0)

    budget_keys = set(
        zip(budget_base["Category"], budget_base["Sub-Category"])
    )

    # -----------------------------
    # 2. Aggregate expenses
    # -----------------------------
    expense_agg = (
        df_expense
        .groupby(
            ["category_display", "subcategory_display"],
            as_index=False,
            dropna=False
        )["amount_spent"]
        .sum()
        .rename(columns={
            "category_display": "Category",
            "subcategory_display": "Sub-Category",
            "amount_spent": "Amount Spent"
        })
    )

    expense_agg["Amount Spent"] = pd.to_numeric(
        expense_agg["Amount Spent"], errors="coerce"
    ).fillna(0)

    # -----------------------------
    # 3. Split IN-BUDGET vs OOB
    # -----------------------------
    expense_agg["is_oob"] = ~expense_agg.apply(
        lambda r: (r["Category"], r["Sub-Category"]) in budget_keys,
        axis=1
    )

    in_budget_expenses = expense_agg[~expense_agg["is_oob"]].drop(columns="is_oob")
    oob_expenses = expense_agg[expense_agg["is_oob"]].drop(columns="is_oob")

    # -----------------------------
    # 4. Merge in-budget rows
    # -----------------------------
    merged = budget_base.merge(
        in_budget_expenses,
        how="left",
        on=["Category", "Sub-Category"]
    )

    merged["Amount Spent"] = merged["Amount Spent"].fillna(0)

    merged["Variance"] = merged["Amount Budgeted"] - merged["Amount Spent"]

    # -----------------------------
    # 5. Build OOB rows
    # -----------------------------
    if not oob_expenses.empty:
        oob_rows = oob_expenses.copy()
        oob_rows["Amount Budgeted"] = 0.0
        oob_rows["Variance"] = -oob_rows["Amount Spent"]
        oob_rows["Category"] = "OOB"
    else:
        oob_rows = pd.DataFrame(
            columns=["Category", "Sub-Category", "Amount Budgeted", "Amount Spent", "Variance"]
        )

    # -----------------------------
    # 6. Combine final dataset
    # -----------------------------
    final_df = pd.concat(
        [
            merged[["Category", "Sub-Category", "Amount Budgeted", "Amount Spent", "Variance"]],
            oob_rows[["Category", "Sub-Category", "Amount Budgeted", "Amount Spent", "Variance"]],
        ],
        ignore_index=True
    )

    # -----------------------------
    # 7. Status calculation
    # -----------------------------
    def get_status(row):
        # Check for OOB rows first - they should always show "Out of Budget"
        if row["Category"] == "OOB":
            return "Out of Budget"
        
        budget = row["Amount Budgeted"]
        spent = row["Amount Spent"]

        if budget == 0:
            return "Overspent" if spent > 0 else "Within Budget"

        usage = spent / budget

        if usage <= 0.7:
            return "Within Budget"
        elif usage <= 1.0:
            return "Warning - Approaching Limit"
        else:
            return "Overspent"

    final_df["Status"] = final_df.apply(get_status, axis=1)

    # -----------------------------
    # 8. Add category totals at the top of each category
    # -----------------------------
    # Calculate category totals
    category_totals = (
        final_df.groupby("Category", as_index=False)
        .agg({
            "Amount Budgeted": "sum",
            "Amount Spent": "sum",
            "Variance": "sum"
        })
    )
    
    # Create category total rows with special Sub-Category indicator
    category_totals["Sub-Category"] = "TOTAL"
    
    # Calculate status for category totals
    category_totals["Status"] = category_totals.apply(get_status, axis=1)
    
    # Reorder columns to match final_df
    category_totals = category_totals[["Category", "Sub-Category", "Amount Budgeted", "Amount Spent", "Variance", "Status"]]
    
    # -----------------------------
    # 9. Combine totals with line items, sorted by category
    # -----------------------------
    # Create a list to hold the final dataframe rows
    result_rows = []
    
    # Get unique categories in sorted order
    categories = sorted(final_df["Category"].unique())
    
    for category in categories:
        # Add category total row first
        cat_total = category_totals[category_totals["Category"] == category]
        if not cat_total.empty:
            result_rows.append(cat_total.iloc[0].to_dict())
        
        # Then add all subcategory rows for this category
        cat_rows = final_df[final_df["Category"] == category].copy()
        # Sort subcategories within the category
        cat_rows = cat_rows.sort_values("Sub-Category", key=lambda s: s.astype(str))
        result_rows.extend(cat_rows.to_dict(orient="records"))
    
    # Create final dataframe with category totals at top
    final_df_with_totals = pd.DataFrame(result_rows)
    
    # -----------------------------
    # 10. Formatting + display
    # -----------------------------
    # Prepare display dataframe
    display_df = final_df_with_totals.copy()
    
    # Indent subcategories by adding spaces (visual indentation)
    mask = display_df["Sub-Category"] != "TOTAL"
    display_df.loc[mask, "Sub-Category"] = "  " + display_df.loc[mask, "Sub-Category"].astype(str)
    
    # Make TOTAL rows more visually distinct
    total_mask = display_df["Sub-Category"] == "TOTAL"
    display_df.loc[total_mask, "Sub-Category"] = "▶ TOTAL"
    
    # Select columns for display
    display_cols = ["Category", "Sub-Category", "Amount Budgeted", "Amount Spent", "Variance", "Status"]
    
    # Styling function for total rows - bold + background color
    def style_total_rows(row):
        """Style TOTAL rows with bold text and background color"""
        if row["Sub-Category"] == "▶ TOTAL":
            # Light gray background for the entire row, bold black text
            return ["background-color: #E8E8E8; font-weight: bold; color: black; border-top: 2px solid #CCCCCC; border-bottom: 2px solid #CCCCCC;"] * len(row)
        return [""] * len(row)
    
    # Styling function for variance colors based on Status
    def variance_colour_style(row):
        """Color code Variance column based on Status"""
        # Default = no styling
        styles = [""] * len(row)
        
        # Get status from the row
        status = row["Status"]
        
        # Determine color based on status
        if status == "Within Budget":
            colour = "background-color: #90EE90; color: black;"  # Light green
        elif status == "Overspent":
            colour = "background-color: #8B0000; color: white;"  # Light red
        elif status == "Out of Budget":
            colour = "background-color: #FFA500; color: black;"  # Orange
        elif status == "Warning - Approaching Limit":
            colour = "background-color: #ADD8E6; color: black;"  # Light blue
        else:
            colour = ""  # No styling for unknown status
        
        # Apply to Variance column only
        try:
            index = row.index.get_loc("Variance")
            styles[index] = colour
        except Exception as e:
            pass  # Column not found, skip styling
        
        return styles
    
    # Apply styling functions - order matters: total row styling first, then variance colors
    styled_df = (
        display_df[display_cols]
        .style.apply(style_total_rows, axis=1)
        .apply(variance_colour_style, axis=1)
    )
    
    # Display using styled dataframe
    st.dataframe(
        styled_df,
        width='stretch',
        hide_index=True,
        column_config={
            "Category": st.column_config.TextColumn(),
            "Sub-Category": st.column_config.TextColumn(),
            "Amount Budgeted": st.column_config.NumberColumn(format="$%.2f"),
            "Amount Spent": st.column_config.NumberColumn(format="$%.2f"),
            "Variance": st.column_config.NumberColumn(format="$%.2f"),
            "Status": st.column_config.TextColumn(),
        }
    )
    
    # ============================================================
    # EXPENSE DETAILS EXPANDER
    # ============================================================
    st.write("")  # Spacing
    with st.expander("🔍 View Individual Invoices per Expense Item"):
        st.markdown("### 📋 Invoice Details")
        st.caption("Select a budget line item to view all individual invoice amounts.")
        
        # Create list of line items for selection (exclude TOTAL rows)
        line_items = final_df_with_totals[
            final_df_with_totals["Sub-Category"] != "TOTAL"
        ][["Category", "Sub-Category"]].drop_duplicates()
        
        if not line_items.empty:
            # Separate Category and Sub-Category selectors
            col1, col2 = st.columns(2)
            
            with col1:
                # Get unique categories
                categories = sorted(line_items["Category"].unique().tolist())
                selected_category = st.selectbox(
                    "Category:",
                    options=categories,
                    key="expense_detail_category"
                )
            
            with col2:
                # Get subcategories for selected category
                subcategories = sorted(
                    line_items[line_items["Category"] == selected_category]["Sub-Category"].unique().tolist()
                )
                selected_subcategory = st.selectbox(
                    "Sub-Category:",
                    options=subcategories,
                    key="expense_detail_subcategory"
                )
            
            if selected_category and selected_subcategory:
                
                # Load raw expenses if parameters are provided
                if expense_file_id and budget_year and budget_type:
                    from utils.expense_parser import load_raw_expenses, get_expense_cache_key
                    
                    try:
                        raw_expenses = load_raw_expenses(
                            expense_file_id=expense_file_id,
                            budget_year=budget_year,
                            budget_type=budget_type,
                            cache_day_key=get_expense_cache_key()
                        )
                        
                        # Filter expenses for selected line item
                        filtered_expenses = raw_expenses[
                            (raw_expenses["category_display"] == selected_category) &
                            (raw_expenses["subcategory_display"] == selected_subcategory)
                        ].copy()
                        
                        if not filtered_expenses.empty:
                            # Select relevant columns for display
                            display_columns = ["Invoice Date", "Vendor", "Amount", "Currency", "amount_spent", "Status"]
                            # Only include columns that exist
                            available_columns = [col for col in display_columns if col in filtered_expenses.columns]
                            
                            expenses_display = filtered_expenses[available_columns].copy()
                            
                            # Rename for better display
                            if "amount_spent" in expenses_display.columns:
                                expenses_display = expenses_display.rename(columns={"amount_spent": "Amount (USD)"})
                            
                            # Sort by invoice date (most recent first)
                            if "Invoice Date" in expenses_display.columns:
                                try:
                                    expenses_display["Invoice Date"] = pd.to_datetime(expenses_display["Invoice Date"], errors='coerce')
                                    expenses_display = expenses_display.sort_values("Invoice Date", ascending=False, na_position='last')
                                    expenses_display["Invoice Date"] = expenses_display["Invoice Date"].dt.strftime("%Y-%m-%d")
                                    expenses_display["Invoice Date"] = expenses_display["Invoice Date"].fillna("N/A")
                                except Exception:
                                    # If date parsing fails, just keep original values
                                    pass
                            
                            # Show summary
                            total_spent = expenses_display["Amount (USD)"].sum() if "Amount (USD)" in expenses_display.columns else 0
                            num_expenses = len(expenses_display)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Total Expenses(USD)", f"${total_spent:,.2f}")
                            with col2:
                                st.metric("Number of Transactions", num_expenses)
                            
                            st.write("")  # Spacing
                            
                            # Display expenses table
                            st.dataframe(
                                expenses_display,
                                hide_index=True,
                                use_container_width=True,
                                column_config={
                                    "Invoice Date": st.column_config.TextColumn(),
                                    "Vendor": st.column_config.TextColumn(),
                                    "Amount": st.column_config.NumberColumn(format="$%.2f"),
                                    "Currency": st.column_config.TextColumn(),
                                    "Amount (USD)": st.column_config.NumberColumn(format="$%.2f"),
                                    "Status": st.column_config.TextColumn(),
                                }
                            )
                        else:
                            st.info(f"ℹ️ No expenses found for {selected_category} - {selected_subcategory}")
                    except Exception as e:
                        st.warning(f"⚠️ Could not load expense details: {str(e)}")
                else:
                    st.info("ℹ️ Expense details are not available. Please ensure expense file parameters are provided.")
        else:
            st.info("ℹ️ No line items available to view expenses.")