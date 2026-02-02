import pandas as pd
import streamlit as st
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import time as t

from .drive_utils import download_file
from .budget_parser import normalize_key
from .fx_helper import get_usd_rates, convert_row_amount_to_usd


# ============================================================
# Cache rollover helper (6:15 AM Jamaica time)
# ============================================================

def get_expense_cache_key() -> str:
    """
    Returns a cache key that rolls over daily at 6:15 AM Jamaica time.
    The value is stable all day and changes once after rollover.
    """
    tz = ZoneInfo("America/Jamaica")
    now = datetime.now(tz)
    rollover = time(6, 15)

    if now.time() >= rollover:
        return now.date().isoformat()
    else:
        return (now.date() - timedelta(days=1)).isoformat()


# ============================================================
# Expense parsing + aggregation (CACHED)
# ============================================================

@st.cache_data(show_spinner="Processing expenses…")
def parseExpense(
    expense_file_id: str,
    budget_year: int,
    budget_type: str,
    cache_day_key: str   # "budget(opex)" or "budget(capex)" # forces cache expiry at 6:15 AM
) -> pd.DataFrame:
    """
    Loads the canonical expense CSV from Google Drive, applies all
    business filters, converts amounts to USD, and aggregates spend
    by category + subcategory.

    Returns ONE row per budget line with:
      - category_key
      - subcategory_key
      - category_display
      - subcategory_display
      - amount_spent (USD)
    """
    # --------------------------------------------------
    # 1. Load expense CSV from Drive
    # --------------------------------------------------
    file_bytes = download_file(expense_file_id)
    df = pd.read_csv(file_bytes)

    # --------------------------------------------------
    # 2. Validate required columns
    # --------------------------------------------------
    required_columns = {
        "Company",
        "Vendor",
        "Classification",
        "Sub-Category",
        "Amount",
        "Invoice Date",
        "Status",
        "Approver-1 approval",
        "Approver-2 approval",
        "Approver-3 approval",
        "Currency",
        "Budget Year",
    }

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Expense file missing required columns: {missing}")

    # --------------------------------------------------
    # 3. Apply hard business filters
    # --------------------------------------------------

    # Company
    df = df[df["Company"] == "Musson"]

    # Budget year
    df = df[df["Budget Year"] == budget_year]

    # Status (exclude void)
    df = df[df["Status"].astype(str).str.lower() != "void"]

    # Approver exclusions (any declined)
    for col in [
        "Approver-1 approval",
        "Approver-2 approval",
        "Approver-3 approval",
    ]:
        df = df[~df[col].astype(str).str.lower().eq("declined")]

    # Classification vs budget type
    budget_type = budget_type.lower()
    if budget_type == "budget(opex)":
        df = df[df["Classification"].astype(str).str.upper() == "OPEX"]
    elif budget_type == "budget(capex)":
        df = df[df["Classification"].astype(str).str.upper() == "CAPEX"]
    else:
        raise ValueError(f"Unknown budget type: {budget_type}")

    # If nothing survives filtering, return empty but well-formed DF
    if df.empty:
        return pd.DataFrame(
            columns=[
                "category_key",
                "subcategory_key",
                "category_display",
                "subcategory_display",
                "amount_spent",
            ]
        )

    # --------------------------------------------------
    # 4. Parse category & subcategory from Sub-Category
    # --------------------------------------------------
    # Format: "<Category> *** <Subcategory>"

    split_cols = (
        df["Sub-Category"]
        .astype(str)
        .str.split("***", n=1, expand=True, regex = False)
    )

    if split_cols.shape[1] != 2:
        raise ValueError(
            "Sub-Category column must follow 'Category *** Subcategory' format"
        )

    df["category_display"] = split_cols[0].str.strip()
    df["subcategory_display"] = split_cols[1].str.strip()

    df["category_key"] = df["category_display"].apply(normalize_key)
    df["subcategory_key"] = df["subcategory_display"].apply(normalize_key)

    # --------------------------------------------------
    # 5. Convert amounts to USD
    # --------------------------------------------------
    rates = get_usd_rates()

    df["amount_spent"] = df.apply(
        lambda row: convert_row_amount_to_usd(row, rates, df),
        axis=1,
    )

    # Drop rows that could not be converted
    df = df[pd.notna(df["amount_spent"])]

    if df.empty:
        return pd.DataFrame(
            columns=[
                "category_key",
                "subcategory_key",
                "category_display",
                "subcategory_display",
                "amount_spent",
            ]
        )

    # --------------------------------------------------
    # 6. Aggregate (CRITICAL STEP)
    # --------------------------------------------------
    # One row per (category, subcategory)

    df_agg = (
        df.groupby(
            [
                "category_key",
                "subcategory_key",
                "category_display",
                "subcategory_display",
            ],
            as_index=False,
        )["amount_spent"]
        .sum()
    )

    return df_agg

@st.cache_data(show_spinner="Loading expense details…")
def load_raw_expenses(
    expense_file_id: str,
    budget_year: int,
    budget_type: str,
    cache_day_key: str
) -> pd.DataFrame:
    """
    Loads the canonical expense CSV from Google Drive, applies all
    business filters, converts amounts to USD, but DOES NOT aggregate.
    
    Returns individual expense rows with all original columns plus:
      - category_display
      - subcategory_display
      - amount_spent (USD)
    """
    # --------------------------------------------------
    # 1. Load expense CSV from Drive
    # --------------------------------------------------
    file_bytes = download_file(expense_file_id)
    df = pd.read_csv(file_bytes)

    # --------------------------------------------------
    # 2. Validate required columns
    # --------------------------------------------------
    required_columns = {
        "Company",
        "Vendor",
        "Classification",
        "Sub-Category",
        "Amount",
        "Invoice Date",
        "Status",
        "Approver-1 approval",
        "Approver-2 approval",
        "Approver-3 approval",
        "Currency",
        "Budget Year",
    }

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Expense file missing required columns: {missing}")

    # --------------------------------------------------
    # 3. Apply hard business filters
    # --------------------------------------------------

    # Company
    df = df[df["Company"] == "Musson"]

    # Budget year
    df = df[df["Budget Year"] == budget_year]

    # Status (exclude void)
    df = df[~df["Status"].astype(str).str.upper().eq("VOID")]

    # Approver exclusions (any declined)
    for col in [
        "Approver-1 approval",
        "Approver-2 approval",
        "Approver-3 approval",
    ]:
        df = df[~df[col].astype(str).str.lower().eq("declined")]

    # Classification vs budget type
    budget_type = budget_type.lower()
    if budget_type == "budget(opex)":
        df = df[df["Classification"].astype(str).str.upper() == "OPEX"]
    elif budget_type == "budget(capex)":
        df = df[df["Classification"].astype(str).str.upper() == "CAPEX"]
    else:
        raise ValueError(f"Unknown budget type: {budget_type}")

    # If nothing survives filtering, return empty but well-formed DF
    if df.empty:
        return pd.DataFrame()

    # --------------------------------------------------
    # 4. Parse category & subcategory from Sub-Category
    # --------------------------------------------------
    # Format: "<Category> *** <Subcategory>"

    split_cols = (
        df["Sub-Category"]
        .astype(str)
        .str.split("***", n=1, expand=True, regex = False)
    )

    if split_cols.shape[1] != 2:
        raise ValueError(
            "Sub-Category column must follow 'Category *** Subcategory' format"
        )

    df["category_display"] = split_cols[0].str.strip()
    df["subcategory_display"] = split_cols[1].str.strip()

    # --------------------------------------------------
    # 5. Convert amounts to USD
    # --------------------------------------------------
    rates = get_usd_rates()

    df["amount_spent"] = df.apply(
        lambda row: convert_row_amount_to_usd(row, rates, df),
        axis=1,
    )

    # Drop rows that could not be converted
    df = df[pd.notna(df["amount_spent"])]

    # Return raw expenses (not aggregated)
    return df