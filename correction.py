# skills/correction.py

import logging
from datetime import datetime
from utils.sheets_handler import sheets_handler
from utils.gemini_client import gemini_client
from utils.categories import CATEGORIES

logger = logging.getLogger(__name__)

def parse_correction_request(message: str) -> dict:
    """
    Uses Gemini to extract target parameters for correction from user text.
    """
    today_str = datetime.today().strftime("%Y-%m-%d")
    
    # Extract all valid categories for the prompt
    all_cats = []
    for grp in CATEGORIES.values():
        for subgrp in grp.values():
            all_cats.extend(subgrp)
            
    prompt = f"""
You are FamilyBudget AI. The user wants to correct an incorrectly categorized transaction.
Analyze the correction request and extract:
1. "date": The date of the original transaction in "YYYY-MM-DD" format (if mentioned, otherwise null).
2. "merchant": The name of the merchant of the affected booking (e.g. "Shell Gas Station" or "Amazon").
3. "amount": The amount of the booking as a float (e.g. 68.51) or null if not mentioned.
4. "new_category": The new category to assign to the booking (must be one of the following: {all_cats}).

Respond exclusively with a valid JSON object.
JSON format:
{{
  "date": "YYYY-MM-DD" or null,
  "merchant": "Merchant name",
  "amount": 12.34 or null,
  "new_category": "New Category"
}}

Text:
"{message}"
"""
    try:
        res = gemini_client.generate_json(prompt)
        # Ensure values
        if res.get("amount"):
            res["amount"] = float(str(res["amount"]).replace(",", "."))
        return res
    except Exception as e:
        logger.error(f"Error parsing correction request: {e}")
        return {"date": None, "merchant": None, "amount": None, "new_category": None}

def correct_transaction(message: str) -> dict:
    """
    Skill 6: Corrects an existing transaction.
    Returns a dictionary indicating the result.
    """
    # 1. Parse correction parameters
    params = parse_correction_request(message)
    target_merchant = params.get("merchant")
    new_category = params.get("new_category")
    target_date = params.get("date")
    target_amount = params.get("amount")

    if not target_merchant or not new_category:
        return {
            "status": "error",
            "message": "❌ Could not recognize the merchant name or new category from your message. Please try something like: 'Correct the Shell transaction from June 22, that was Car instead of Fuel.'"
        }

    # Verify if category is valid
    all_valid_cats = []
    for grp in CATEGORIES.values():
        for subgrp in grp.values():
            all_valid_cats.extend(subgrp)
    if new_category not in all_valid_cats:
        return {
            "status": "error",
            "message": f"❌ Category '{new_category}' is not recognized in our system."
        }

    # 2. Get transaction worksheet
    if target_date:
        month_str = target_date[:7]
    else:
        month_str = datetime.today().strftime("%Y-%m")

    df = sheets_handler.get_transactions(month_str)
    if df.empty:
        return {
            "status": "error",
            "message": f"❌ Could not find any transaction records for month {month_str}."
        }

    # Helper for column lookup
    cols_lower = [str(c).lower().strip() for c in df.columns]
    def get_col(names: list[str]) -> str:
        for n in names:
            if n.lower() in cols_lower:
                return df.columns[cols_lower.index(n.lower())]
        return names[0]

    date_col = get_col(["date", "datum"])
    merchant_col = get_col(["merchant", "händler"])
    amount_col = get_col(["amount", "betrag"])
    cat_col = get_col(["category", "kategorie"])

    # 3. Find matching rows
    df["Betrag_float"] = df[amount_col].astype(str).str.replace(",", ".").astype(float)
    df["Händler_lower"] = df[merchant_col].astype(str).str.lower().str.strip()
    
    matches = df.copy()
    
    # Filter by Date
    if target_date:
        matches = matches[matches[date_col] == target_date]
        
    # Filter by Merchant
    matches = matches[matches["Händler_lower"].str.contains(target_merchant.lower(), na=False)]
    
    # Filter by Amount
    if target_amount:
        matches = matches[(matches["Betrag_float"] - target_amount).abs() < 0.01]

    if matches.empty:
        # If no matches found with exact date, try searching the entire sheet for this merchant
        matches = df[df["Händler_lower"].str.contains(target_merchant.lower(), na=False)]
        if target_amount:
            matches = matches[(matches["Betrag_float"] - target_amount).abs() < 0.01]
            
        if matches.empty:
            return {
                "status": "error",
                "message": f"❌ No matching transaction found for '{target_merchant}' in month {month_str}."
            }

    # 4. Handle results
    if len(matches) == 1:
        # Exactly one match: perform update
        matched_row = matches.iloc[0]
        actual_date = matched_row[date_col]
        actual_merchant = matched_row[merchant_col]
        actual_amount = float(str(matched_row[amount_col]).replace(",", "."))
        old_category = matched_row[cat_col]
        
        success = sheets_handler.update_transaction(actual_date, actual_merchant, actual_amount, new_category)
        if success:
            return {
                "status": "success",
                "message": f"✅ Corrected:\n" \
                           f"**{actual_merchant}** | {actual_date} | €{actual_amount:,.2f} → Category updated from **{old_category}** to **{new_category}**",
                "updated_transaction": {
                    "date": actual_date,
                    "merchant": actual_merchant,
                    "amount": actual_amount,
                    "category": new_category
                }
            }
        else:
            return {
                "status": "error",
                "message": "❌ Error updating spreadsheet record."
            }
            
    else:
        # Multiple matches found: need disambiguation
        match_list = []
        for idx, row in matches.iterrows():
            match_list.append({
                "index": idx,
                "date": row[date_col],
                "merchant": row[merchant_col],
                "amount": float(str(row[amount_col]).replace(",", ".")),
                "category": row[cat_col]
            })
            
        prompt_text = f"Multiple transactions match '{target_merchant}' on {target_date or month_str}:\n"
        for i, m in enumerate(match_list):
            prompt_text += f"[{chr(65 + i)}] {m['merchant']} – €{m['amount']:,.2f} on {m['date']} (Current category: {m['category']})\n"
        prompt_text += "Which one should I modify?"
        
        return {
            "status": "disambiguate",
            "message": prompt_text,
            "matches": match_list,
            "new_category": new_category
        }
