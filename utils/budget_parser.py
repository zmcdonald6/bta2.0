import pandas as pd

from .drive_utils import download_file, extract_drive_file_id
from .db import get_active_budget_metadata
import streamlit as st

MONTH_COLUMNS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

def normalize_key(key: str) -> str:
    return str(key).strip().lower().replace(" ", "")

@st.cache_data(show_spinner="Loading active budget…")
def _load_budget_from_drive(file_id: str) -> pd.DataFrame:
    """
    Heavy operation:
    - Downloads budget from Drive
    - Parses Excel
    - Normalizes and reshapes data

    Cached until file_id changes.
    """
    file_bytes = download_file(file_id)

    df = pd.read_excel(file_bytes)

    # --------------------------------------------------
    # Validate required columns
    # --------------------------------------------------
    required_columns = {"Category", "Subcategory", "Total"} | set(MONTH_COLUMNS)
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Budget file missing required columns: {missing}")

    # --------------------------------------------------
    # Preserve display values
    # --------------------------------------------------
    df["category_display"] = df["Category"].astype(str).str.strip()
    df["subcategory_display"] = df["Subcategory"].astype(str).str.strip()

    # --------------------------------------------------
    # Generate normalized keys
    # --------------------------------------------------
    df["category_key"] = df["category_display"].apply(normalize_key)
    df["subcategory_key"] = df["subcategory_display"].apply(normalize_key)

    # --------------------------------------------------
    # Annual total
    # --------------------------------------------------
    df["annual_total"] = (
        pd.to_numeric(df["Total"], errors="coerce")
        .fillna(0)
    )

    # --------------------------------------------------
    # Melt months → long format
    # --------------------------------------------------
    df_long = df.melt(
        id_vars=[
            "category_key",
            "category_display",
            "subcategory_key",
            "subcategory_display",
            "annual_total",
        ],
        value_vars=MONTH_COLUMNS,
        var_name="month",
        value_name="budget_amount",
    )

    # --------------------------------------------------
    # Normalize month & values
    # --------------------------------------------------
    df_long["month"] = df_long["month"].str.lower()
    df_long["budget_amount"] = (
        pd.to_numeric(df_long["budget_amount"], errors="coerce")
        .fillna(0)
    )

    return df_long[
        [
            "category_key",
            "category_display",
            "subcategory_key",
            "subcategory_display",
            "month",
            "budget_amount",
            "annual_total",
        ]
    ]



def load_active_budget():
    """
    Returns the active budget.
    Cached automatically until the active budget file changes.
    """
    budget_meta = get_active_budget_metadata()

    if not budget_meta or "file_url" not in budget_meta:
        raise RuntimeError("No active budget found in database.")

    file_id = extract_drive_file_id(budget_meta["file_url"])
    if not file_id:
        raise RuntimeError("Could not extract Drive file ID.")

    return _load_budget_from_drive(file_id)
