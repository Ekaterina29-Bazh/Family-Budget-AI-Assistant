import re
from utils.categories import CATEGORIES, STATIC_RULES, load_categories_from_sheets

def classify_transaction(merchant: str, amount: float, category_hint: str = None, tx_type: str = "expense") -> dict:
    """
    Skill 3: Determines the category and subcategory of a transaction,
    and returns a confidence score (0.0 - 1.0).
    """
    amount = float(amount)
    merchant_clean = merchant.strip().lower()
    
    # 1. Check static rules first
    for rule in STATIC_RULES:
        if re.search(rule["pattern"], merchant_clean):
            if "amazon" in merchant_clean:
                return {
                    "category": "Unknown",
                    "subcategory": "Amazon Review",
                    "confidence": 0.70
                }
            return {
                "category": rule["category"],
                "subcategory": rule["subcategory"],
                "confidence": rule["confidence"]
            }

    # 1b. Check keywords from user-defined categories in Sheets
    try:
        active_cats = load_categories_from_sheets()
        for t_val, items in active_cats.items():
            for item in items:
                if item.get("active", True):
                    cat_name = item.get("name")
                    for kw in item.get("keywords", []):
                        if kw and len(kw) >= 2 and kw.lower() in merchant_clean:
                            return {
                                "category": cat_name,
                                "subcategory": "-",
                                "confidence": 0.98
                            }
    except Exception:
        pass

    # 2. Check category_hint
    if category_hint:
        hint_clean = category_hint.strip().lower()
        for cat_group, cats in CATEGORIES["expense"].items():
            for c in cats:
                if c.lower() in hint_clean:
                    return {"category": c, "subcategory": "-", "confidence": 0.95}
        for c in CATEGORIES["income"]["Income"]:
            if c.lower() in hint_clean:
                return {"category": c, "subcategory": "-", "confidence": 0.95}
        for c in CATEGORIES["savings"]["Savings"]:
            if c.lower() in hint_clean:
                return {"category": c, "subcategory": "-", "confidence": 0.95}

    # 3. Fallback: Use Gemini to classify based on categories list
    from utils.gemini_client import gemini_client
    
    # Flatten categories for prompt
    categories_schema = {
        "expense": CATEGORIES["expense"],
        "income": CATEGORIES["income"],
        "savings": CATEGORIES["savings"]
    }
    
    prompt = f"""
Classify the following financial transaction based on our category system.

Merchant/Source: "{merchant}"
Amount: {amount} EUR
Type: {tx_type}
Category Hint (optional): "{category_hint or ''}"

Available Category System:
{categories_schema}

Your Tasks:
1. Determine the appropriate main category and subcategory.
2. Calculate a confidence score (0.0 to 1.0) indicating assignment certainty.
   - If the merchant is completely unknown and no category hint helps, select main category "Unknown" and a confidence score under 0.50 (e.g. 0.30).
   - If you are very confident, return a high score (e.g. 0.85 to 0.95).

Respond strictly in this JSON structure:
{{
  "category": "Main Category",
  "subcategory": "Subcategory or -",
  "confidence": 0.85
}}
"""
    try:
        response = gemini_client.generate_json(prompt)
        cat = response.get("category", "Unknown")
        sub = response.get("subcategory", "-")
        conf = float(response.get("confidence", 0.40))
        
        # Ensure category is valid in our system
        all_valid_cats = []
        for group in CATEGORIES.values():
            for cats in group.values():
                all_valid_cats.extend(cats)
                
        if cat not in all_valid_cats:
            cat = "Unknown"
            conf = 0.30
            
        return {
            "category": cat,
            "subcategory": sub,
            "confidence": conf
        }
    except Exception:
        # Emergency fallback
        return {
            "category": "Unknown",
            "subcategory": "-",
            "confidence": 0.30
        }
