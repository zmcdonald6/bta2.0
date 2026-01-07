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
    #variance_colour_style,
    #get_variance_status,
    role: str = "user",
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
    
    # Select columns for display
    display_cols = ["Category", "Sub-Category", "Amount Budgeted", "Amount Spent", "Variance", "Status"]
    
    # Styling function for bold totals
    def make_total_bold(row):
        """Make TOTAL rows bold"""
        if row["Sub-Category"] == "TOTAL":
            return ["font-weight: bold"] * len(row)
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
    
    # Apply both styling functions
    styled_df = (
        display_df[display_cols]
        .style.apply(make_total_bold, axis=1)
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