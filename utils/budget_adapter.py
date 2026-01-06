import pandas as pd

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

def adapt_budget_long_to_classification(df_long: pd.DataFrame) -> pd.DataFrame:
    """
    Converts long-format budget dataframe into the
    wide-format dataframe expected by the classification dashboard.
    """

    # Normalize month names to Title Case
    df = df_long.copy()
    df["Month"] = df["month"].str.title()

    # Pivot months to columns
    pivot_df = (
        df.pivot_table(
            index=["category_display", "subcategory_display"],
            columns="Month",
            values="budget_amount",
            aggfunc="sum",
        )
        .reset_index()
    )

    # Ensure all months exist
    for m in MONTHS:
        if m not in pivot_df.columns:
            pivot_df[m] = 0.0

    # Add Total column
    totals = (
        df.groupby(
            ["category_display", "subcategory_display"],
            as_index=False
        )["annual_total"]
        .first()
    )

    final_df = pivot_df.merge(
        totals,
        on=["category_display", "subcategory_display"],
        how="left",
    )

    # Rename to EXACT column names expected
    final_df = final_df.rename(columns={
        "category_display": "Category",
        "subcategory_display": "Sub-Category",
        "annual_total": "Total",
    })

    # Column ordering
    ordered_cols = ["Category", "Sub-Category"] + MONTHS + ["Total"]
    final_df = final_df[ordered_cols]

    return final_df