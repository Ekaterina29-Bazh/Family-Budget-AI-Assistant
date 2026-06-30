# skills/analytics.py

import logging
import pandas as pd
from datetime import datetime
from utils.sheets_handler import sheets_handler

logger = logging.getLogger(__name__)

ENGLISH_MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December"
}

def get_previous_month(month_str: str) -> str:
    """Helper to get YYYY-MM for the previous month."""
    try:
        y, m = map(int, month_str.split("-"))
        if m == 1:
            return f"{y-1}-12"
        else:
            return f"{y}-{m-1:02d}"
    except Exception:
        return ""

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Helper to clean columns and numeric values in raw dataframes."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    # Normalize column names to lowercase and strip whitespace
    df.columns = [str(col).strip().lower() for col in df.columns]
    
    # Map columns to standard English names
    column_mapping = {
        "datum": "date",
        "händler": "merchant",
        "betrag": "amount",
        "kategorie": "category",
        "unterkategorie": "subcategory",
        "quelle": "source",
        "person": "person",
        "typ": "type",
        "notiz": "note"
    }
    df = df.rename(columns=column_mapping)
    
    if "amount" in df.columns:
        df["amount"] = df["amount"].astype(str).str.replace(",", ".").str.replace("€", "").str.replace("$", "").str.strip()
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    
    if "category" in df.columns:
        df["category"] = df["category"].astype(str).str.strip()
        
    return df

def generate_analytics(sheet_data: dict) -> dict:
    """
    Part 1: Processes monthly sheet data and returns structured dictionary
    containing the four required analytics.
    """
    # 1. Determine current month and year based on the data
    expense_keys = [k for k in sheet_data.keys() if k.lower().endswith(" expenses") or k.lower().endswith(" ausgaben")]
    
    if expense_keys:
        dates = []
        for k in expense_keys:
            parts = k.split(" ")
            if parts:
                dates.append(parts[0])
        current_month = max(dates)
    else:
        current_month = datetime.now().strftime("%Y-%m")
        
    current_year = current_month.split("-")[0]
    previous_month = get_previous_month(current_month)

    # 2. Get and clean data for current month, previous month, and all months of current year
    cleaned_sheets = {}
    for key, df in sheet_data.items():
        cleaned_sheets[key.lower()] = clean_dataframe(df)

    # 1. Expenses by Category (current month)
    curr_expenses_key = f"{current_month} expenses"
    df_curr_exp = cleaned_sheets.get(curr_expenses_key, cleaned_sheets.get(f"{current_month} ausgaben", pd.DataFrame()))
    
    expenses_by_category = {}
    if not df_curr_exp.empty and "category" in df_curr_exp.columns and "amount" in df_curr_exp.columns:
        cat_sums = df_curr_exp.groupby("category")["amount"].sum()
        expenses_by_category = cat_sums.to_dict()
        expenses_by_category = {k: float(v) for k, v in expenses_by_category.items()}

    # 2. Income vs. Expenses vs. Savings (monthly, full year)
    monthly_totals = {}
    
    for m in range(1, 13):
        m_str = f"{current_year}-{m:02d}"
        
        exp_key = f"{m_str} expenses"
        inc_key = f"{m_str} income"
        sav_key = f"{m_str} savings"
        
        has_data = any(k in cleaned_sheets for k in [exp_key, inc_key, sav_key, f"{m_str} ausgaben", f"{m_str} einnahmen", f"{m_str} ersparnisse"])
        if not has_data:
            continue
            
        df_exp = cleaned_sheets.get(exp_key, cleaned_sheets.get(f"{m_str} ausgaben", pd.DataFrame()))
        df_inc = cleaned_sheets.get(inc_key, cleaned_sheets.get(f"{m_str} einnahmen", pd.DataFrame()))
        df_sav = cleaned_sheets.get(sav_key, cleaned_sheets.get(f"{m_str} ersparnisse", pd.DataFrame()))
        
        exp_total = df_exp["amount"].sum() if not df_exp.empty and "amount" in df_exp.columns else 0.0
        inc_total = df_inc["amount"].sum() if not df_inc.empty and "amount" in df_inc.columns else 0.0
        sav_total = df_sav["amount"].sum() if not df_sav.empty and "amount" in df_sav.columns else 0.0
        
        monthly_totals[m_str] = {
            "expenses": float(exp_total),
            "income": float(inc_total),
            "savings": float(sav_total)
        }

    # 3. Month-over-Month Comparison
    prev_expenses_key = f"{previous_month} expenses"
    df_prev_exp = cleaned_sheets.get(prev_expenses_key, cleaned_sheets.get(f"{previous_month} ausgaben", pd.DataFrame()))
    
    prev_expenses_by_category = {}
    if not df_prev_exp.empty and "category" in df_prev_exp.columns and "amount" in df_prev_exp.columns:
        prev_expenses_by_category = df_prev_exp.groupby("category")["amount"].sum().to_dict()

    mom_comparison = {}
    all_categories = set(list(expenses_by_category.keys()) + list(prev_expenses_by_category.keys()))
    
    for cat in sorted(all_categories):
        curr_val = expenses_by_category.get(cat, 0.0)
        prev_val = prev_expenses_by_category.get(cat, 0.0)
        
        if prev_val > 0:
            change_pct = ((curr_val - prev_val) / prev_val) * 100
        else:
            change_pct = 0.0
            
        mom_comparison[cat] = {
            "current": float(curr_val),
            "previous": float(prev_val),
            "change_pct": round(change_pct, 2)
        }

    # 4. Summary Table (all months, current year)
    summary_table = []
    for month_key in sorted(monthly_totals.keys()):
        m_num = month_key.split("-")[1]
        m_name = ENGLISH_MONTHS.get(m_num, month_key)
        
        totals = monthly_totals[month_key]
        inc = totals["income"]
        exp = totals["expenses"]
        sav = totals["savings"]
        bilanz = inc - exp - sav
        
        summary_table.append({
            "Month": m_name,
            "Income": inc,
            "Expenses": exp,
            "Savings": sav,
            "Net Balance": bilanz,
            "_month_key": month_key
        })

    return {
        "expenses_by_category": expenses_by_category,
        "monthly_totals": monthly_totals,
        "mom_comparison": mom_comparison,
        "summary_table": summary_table,
        "current_month": current_month,
        "current_year": current_year
    }

def write_analytics_to_sheets(analytics_results: dict):
    """
    Part 3: Writes calculated summary to the 'analytics' tab in Google Sheets.
    """
    rows = []
    # Section 1: Annual Overview
    rows.append(["Annual Overview"])
    rows.append(["Month", "Income", "Expenses", "Savings", "Net Balance"])
    
    for month_row in analytics_results["summary_table"]:
        rows.append([
            month_row.get("Month", month_row.get("Monat", "")),
            month_row.get("Income", month_row.get("Einnahmen", 0.0)),
            month_row.get("Expenses", month_row.get("Ausgaben", 0.0)),
            month_row.get("Savings", month_row.get("Ersparnisse", 0.0)),
            month_row.get("Net Balance", month_row.get("Bilanz", 0.0))
        ])
        
    rows.append([]) # Blank row
    
    # Section 2: Category Breakdown
    current_month_str = analytics_results.get("current_month", "Unknown")
    parts = current_month_str.split("-")
    month_name = ENGLISH_MONTHS.get(parts[1], parts[1]) if len(parts) > 1 else parts[0]
    year_str = parts[0] if len(parts) > 0 else ""
    current_month_display = f"{month_name} {year_str}".strip()
    
    rows.append([f"Expenses by Category – {current_month_display}"])
    rows.append(["Category", "Amount", "Share %"])
    
    expenses_by_category = analytics_results["expenses_by_category"]
    total_expenses = sum(expenses_by_category.values())
    
    for cat, amt in sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True):
        share_pct = (amt / total_expenses * 100) if total_expenses > 0 else 0.0
        rows.append([
            cat,
            amt,
            f"{share_pct:.2f}%"
        ])
        
    sheets_handler.write_to_analytics_tab(rows)
