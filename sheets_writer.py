# skills/sheets_writer.py

from utils.sheets_handler import sheets_handler

def write_to_sheets(transaction: dict) -> str:
    """
    Skill 4: Writes a classified transaction to Google Sheets or local Excel fallback.
    Returns a success confirmation message in English.
    """
    success = sheets_handler.add_transaction(transaction)
    
    if success:
        date_val = transaction.get("date")
        month_str = date_val[:7] if date_val else ""
        merchant = transaction.get("merchant", "")
        amount = transaction.get("amount", 0.0)
        category = transaction.get("category", "")
        
        storage_info = "Google Sheets" if sheets_handler.use_google else "local Excel file"
        message = f"✅ Transaction recorded via chat in **{storage_info}**:\n" \
                  f"Date: {date_val} | Merchant: {merchant} | Amount: €{amount:,.2f} | Category: {category}"
        
        # Show category total spending so far this month
        if transaction.get("type") == "expense" and category and category not in ["Unknown", "Unbekannt"]:
            tx_df = sheets_handler.get_transactions(month_str)
            if not tx_df.empty:
                cols_lower = [str(c).lower().strip() for c in tx_df.columns]
                cat_col = tx_df.columns[cols_lower.index("category")] if "category" in cols_lower else (tx_df.columns[cols_lower.index("kategorie")] if "kategorie" in cols_lower else tx_df.columns[3])
                type_col = tx_df.columns[cols_lower.index("type")] if "type" in cols_lower else (tx_df.columns[cols_lower.index("typ")] if "typ" in cols_lower else tx_df.columns[7])
                amt_col = tx_df.columns[cols_lower.index("amount")] if "amount" in cols_lower else (tx_df.columns[cols_lower.index("betrag")] if "betrag" in cols_lower else tx_df.columns[2])
                
                expenses_df = tx_df[
                    (tx_df[cat_col].astype(str).str.strip().str.lower() == category.strip().lower()) & 
                    (tx_df[type_col].astype(str).str.strip().str.lower() == "expense")
                ]
                total_spent = pd_to_num(expenses_df[amt_col]).sum() if not expenses_df.empty else 0.0
                message += f"\n\n📊 Total spending in **{category}** this month: €{total_spent:,.2f}"
        return message
    else:
        return "❌ Failed to write transaction to spreadsheet."

def pd_to_num(series):
    import pandas as pd
    return pd.to_numeric(series.astype(str).str.replace(",", ".").str.replace("€", "").str.strip(), errors="coerce").fillna(0.0)
