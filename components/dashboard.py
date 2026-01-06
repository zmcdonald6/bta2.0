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
        budget = row["Amount Budgeted"]
        spent = row["Amount Spent"]

        if budget == 0:
            return "Overspent" if spent > 0 else "Within Budget"

        usage = spent / budget

        if usage <= 0.7:
            return "Within Budget"
        elif usage <= 1.0:
            return "Warning"
        else:
            return "Overspent"

    final_df["Status"] = final_df.apply(get_status, axis=1)

    # -----------------------------
    # 8. Formatting + display
    # -----------------------------
    final_df = final_df.sort_values(
        ["Category", "Sub-Category"],
        key=lambda s: s.astype(str)
    ).reset_index(drop=True)

    st.data_editor(
        final_df,
        use_container_width=True,
        disabled=True,
        column_config={
            "Amount Budgeted": st.column_config.NumberColumn(format="$%.2f"),
            "Amount Spent": st.column_config.NumberColumn(format="$%.2f"),
            "Variance": st.column_config.NumberColumn(format="$%.2f"),
            "Status": st.column_config.TextColumn(),
        }
    )