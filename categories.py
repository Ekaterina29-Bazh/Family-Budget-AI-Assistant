# utils/categories.py

CATEGORY_MAP_DE_TO_EN = {
    # Fixkosten -> Fixed Costs
    "Fixkosten": "Fixed Costs",
    "Wohnen": "Housing",
    "Miete": "Housing",
    "Nebenkosten": "Utilities",
    "Kommunikation": "Communication",
    "Telefon & Internet": "Communication",
    "Streaming & Medien": "Streaming & Media",
    "Streaming": "Streaming & Media",
    "Mobilität": "Mobility",
    "Fitness": "Fitness",
    "Versicherung": "Insurance",
    "Versicherungen": "Insurance",
    "Sonstige Fixkosten": "Other Fixed Costs",
    
    # Variable Kosten -> Variable Costs
    "Variable Kosten": "Variable Costs",
    "Lebensmittel": "Groceries",
    "Drogerie": "Drugstore",
    "Benzin": "Fuel",
    "Tanken": "Fuel",
    "Auto": "Car",
    "Kleidung": "Clothing",
    "Gesundheit": "Health",
    "Geschenke": "Gifts",
    "Digitales & Abonnements": "Digital & Subscriptions",
    "Abos": "Digital & Subscriptions",
    "Freizeit": "Leisure",
    "Restaurant / Café": "Dining Out",
    "Dining Out": "Dining Out",
    "Restaurant": "Dining Out",
    "Ausgehen": "Dining Out",
    "Umbuchung": "Transfer",
    "Überweisung": "Transfer",
    "Transfer": "Transfer",
    "Unbekannt": "Unknown",
    "Unknown": "Unknown",
    
    # Einnahmen -> Income
    "Einnahmen": "Income",
    "Gehalt": "Salary",
    "Einkommen": "Salary",
    "Dividenden": "Dividends",
    "Zinsen": "Interest",
    "Cashback": "Cashback",
    "Verkauf": "Sales",
    "Geldgeschenk": "Monetary Gift",
    "Geschenk (Geld)": "Monetary Gift",
    "Geschenk": "Monetary Gift",
    "Sonstige Einnahmen": "Other Income",
    "Sonstiges": "Other Income",
    
    # Ersparnisse -> Savings
    "Ersparnisse": "Savings",
    "Investitionen (Sparpläne)": "Investments (Savings Plans)",
    "Sparpläne": "Investments (Savings Plans)",
    "Altersvorsorge": "Retirement",
    "Wertpapiere": "Securities",
    "Zeitwertpapiere": "Securities",
}

CATEGORIES = {
    "expense": {
        "Fixed Costs": [
            "Housing",
            "Utilities",
            "Communication",
            "Streaming & Media",
            "Mobility",
            "Fitness",
            "Insurance",
            "Other Fixed Costs"
        ],
        "Variable Costs": [
            "Groceries",
            "Drugstore",
            "Fuel",
            "Car",
            "Clothing",
            "Health",
            "Gifts",
            "Digital & Subscriptions",
            "Leisure",
            "Dining Out",
            "Transfer",
            "Unknown"
        ]
    },
    "income": {
        "Income": [
            "Salary",
            "Dividends",
            "Interest",
            "Cashback",
            "Sales",
            "Monetary Gift",
            "Other Income"
        ]
    },
    "savings": {
        "Savings": [
            "Investments (Savings Plans)",
            "Retirement",
            "Securities"
        ]
    }
}

STATIC_RULES = [
    {"pattern": r"rossmann|dm\b|dm drogerie", "category": "Drugstore", "subcategory": "Drugstore Supplies", "confidence": 0.99, "type": "expense"},
    {"pattern": r"kaufland|penny|lidl|aldi|netto|rewe|walmart|trader joe", "category": "Groceries", "subcategory": "Supermarket", "confidence": 0.99, "type": "expense"},
    {"pattern": r"too good to go|tgtg", "category": "Groceries", "subcategory": "Too Good To Go", "confidence": 0.97, "type": "expense"},
    {"pattern": r"hem|shell|aral|gas station|tankstelle|esso|total\b|jet\b", "category": "Fuel", "subcategory": "Gasoline", "confidence": 0.98, "type": "expense"},
    {"pattern": r"netflix|spotify|youtube premium|disney|apple music", "category": "Streaming & Media", "subcategory": "Streaming", "confidence": 0.97, "type": "expense"},
    {"pattern": r"apple\s*pay|apple\.com|google\s*pay|google\s*payment|google\s*play", "category": "Digital & Subscriptions", "subcategory": "Digital Services", "confidence": 0.95, "type": "expense"},
    {"pattern": r"amazon", "category": "Unknown", "subcategory": "Amazon Review", "confidence": 0.70, "type": "expense"},
    {"pattern": r"transfer|standing order|wire transfer|sepa", "category": "Transfer", "subcategory": "Bank Transfer", "confidence": 0.95, "type": "expense"}
]

BUDGET_LIMITS = {
    "Housing": 1200.0,
    "Utilities": 200.0,
    "Communication": 50.0,
    "Streaming & Media": 30.0,
    "Mobility": 100.0,
    "Fitness": 40.0,
    "Insurance": 150.0,
    "Other Fixed Costs": 50.0,
    "Groceries": 500.0,
    "Drugstore": 50.0,
    "Fuel": 150.0,
    "Car": 100.0,
    "Clothing": 100.0,
    "Health": 80.0,
    "Gifts": 50.0,
    "Digital & Subscriptions": 30.0,
    "Leisure": 120.0,
    "Dining Out": 150.0,
    "Transfer": 0.0,
    "Unknown": 0.0
}

import logging
import pandas as pd
from utils.sheets_handler import sheets_handler

logger = logging.getLogger(__name__)

DEFAULT_KEYWORDS = {
    "Groceries": "lidl, aldi, rewe, kaufland, penny, netto, supermarket, trader joe, walmart",
    "Drugstore": "rossmann, dm, drugstore, cvs, walgreens",
    "Fuel": "hem, shell, aral, gas station, esso, total, jet, chevron",
    "Streaming & Media": "netflix, spotify, youtube, disney, apple music, hbo",
    "Digital & Subscriptions": "apple, google, patreon, icloud, amazon prime",
    "Transfer": "transfer, wire, standing order, bank transfer",
    "Housing": "rent, apartment, mortgage, housing fee",
    "Utilities": "utilities, electricity, gas, water, power",
    "Communication": "vodafone, verizon, at&t, o2, t-mobile",
    "Mobility": "train, subway, bus, transit, ticket, uber, lyft",
    "Fitness": "gym, fitness, workout, planet fitness",
    "Insurance": "insurance, allianz, geico, state farm",
    "Dining Out": "restaurant, cafe, bakery, pizzeria, burger, sushi, starbucks",
    "Salary": "salary, wages, paycheck, income",
    "Dividends": "dividend, stock dividend",
    "Interest": "interest, savings interest",
    "Cashback": "cashback, reward",
    "Sales": "ebay, etsy, craigslist, poshmark",
    "Investments (Savings Plans)": "etf, stocks, trade republic, vanguard, fidelity",
    "Retirement": "pension, retirement, 401k, ira"
}

def get_default_categories_flat() -> list[dict]:
    """Construct default rows for settings sheet."""
    rows = []
    for cat in CATEGORIES["expense"]["Fixed Costs"] + CATEGORIES["expense"]["Variable Costs"]:
        rows.append({"type": "expense", "name": cat, "keywords": DEFAULT_KEYWORDS.get(cat, ""), "active": "TRUE"})
    for cat in CATEGORIES["income"]["Income"]:
        rows.append({"type": "income", "name": cat, "keywords": DEFAULT_KEYWORDS.get(cat, ""), "active": "TRUE"})
    for cat in CATEGORIES["savings"]["Savings"]:
        rows.append({"type": "savings", "name": cat, "keywords": DEFAULT_KEYWORDS.get(cat, ""), "active": "TRUE"})
    return rows

def update_global_categories_dict(loaded_dict: dict):
    """Sync memory CATEGORIES dict with loaded categories from sheets."""
    exp_names = [item["name"] for item in loaded_dict.get("expense", [])]
    inc_names = [item["name"] for item in loaded_dict.get("income", [])]
    sav_names = [item["name"] for item in loaded_dict.get("savings", [])]
    
    if exp_names:
        CATEGORIES["expense"]["Variable Costs"] = exp_names
    if inc_names:
        CATEGORIES["income"]["Income"] = inc_names
    if sav_names:
        CATEGORIES["savings"]["Savings"] = sav_names

def load_categories_from_sheets() -> dict:
    """Load all categories from the 'settings' tab in Google Sheets."""
    try:
        df = sheets_handler.read_settings_sheet()
        if df.empty or "name" not in df.columns or df["name"].dropna().empty:
            default_rows = get_default_categories_flat()
            df = pd.DataFrame(default_rows)
            sheets_handler.write_settings_sheet(df)
            
        result = {"expense": [], "income": [], "savings": []}
        for _, row in df.iterrows():
            t_val = str(row.get("type", "expense")).strip().lower()
            if t_val in ["ausgaben", "ausgabe", "expense"]:
                t_val = "expense"
            elif t_val in ["einnahmen", "einnahme", "income"]:
                t_val = "income"
            elif t_val in ["ersparnisse", "ersparnis", "sparen", "savings"]:
                t_val = "savings"
            else:
                t_val = "expense"
                
            c_name = str(row.get("name", "")).strip()
            if not c_name:
                continue
            c_name = CATEGORY_MAP_DE_TO_EN.get(c_name, c_name)
            kw_raw = str(row.get("keywords", ""))
            if pd.isna(kw_raw) or kw_raw.lower() == "nan":
                kw_raw = ""
            keywords_list = [k.strip() for k in kw_raw.split(",") if k.strip()]
            act_raw = str(row.get("active", "TRUE")).strip().upper()
            is_active = act_raw in ["TRUE", "1", "YES", "WAHR"]
            
            result[t_val].append({
                "name": c_name,
                "keywords": keywords_list,
                "active": is_active
            })
            
        update_global_categories_dict(result)
        return result
    except Exception as e:
        logger.error(f"Error loading categories from sheets: {e}")
        fallback = {"expense": [], "income": [], "savings": []}
        for group, cats in CATEGORIES["expense"].items():
            for c in cats:
                fallback["expense"].append({"name": c, "keywords": [k.strip() for k in DEFAULT_KEYWORDS.get(c, "").split(",") if k.strip()], "active": True})
        for c in CATEGORIES["income"]["Income"]:
            fallback["income"].append({"name": c, "keywords": [k.strip() for k in DEFAULT_KEYWORDS.get(c, "").split(",") if k.strip()], "active": True})
        for c in CATEGORIES["savings"]["Savings"]:
            fallback["savings"].append({"name": c, "keywords": [k.strip() for k in DEFAULT_KEYWORDS.get(c, "").split(",") if k.strip()], "active": True})
        return fallback

def save_categories_to_sheets(categories_dict: dict) -> None:
    """Write all categories back to the 'settings' tab. Overwrites existing data."""
    rows = []
    for t_val in ["expense", "income", "savings"]:
        for item in categories_dict.get(t_val, []):
            kw_str = ", ".join(item.get("keywords", []))
            act_str = "TRUE" if item.get("active", True) else "FALSE"
            rows.append({
                "type": t_val,
                "name": item.get("name", "").strip(),
                "keywords": kw_str,
                "active": act_str
            })
    df = pd.DataFrame(rows)
    sheets_handler.write_settings_sheet(df)
    update_global_categories_dict(categories_dict)

def add_category(type_: str, name: str, keywords: list[str]) -> None:
    """Add a new category. type_ must be 'expense', 'income', or 'savings'."""
    cats = load_categories_from_sheets()
    t_clean = type_.lower().strip()
    if t_clean not in cats:
        t_clean = "expense"
        
    existing = next((c for c in cats[t_clean] if c["name"].lower() == name.lower().strip()), None)
    if not existing:
        cats[t_clean].append({"name": name.strip(), "keywords": keywords, "active": True})
    else:
        existing["keywords"] = list(set(existing["keywords"] + keywords))
        existing["active"] = True
        
    save_categories_to_sheets(cats)

def delete_category(type_: str, name: str) -> None:
    """Delete a category by name and type."""
    cats = load_categories_from_sheets()
    t_clean = type_.lower().strip()
    if t_clean in cats:
        cats[t_clean] = [c for c in cats[t_clean] if c["name"].lower() != name.lower().strip()]
        save_categories_to_sheets(cats)

def update_category_keywords(type_: str, name: str, keywords: list[str]) -> None:
    """Update keywords for a given category."""
    cats = load_categories_from_sheets()
    t_clean = type_.lower().strip()
    if t_clean in cats:
        for item in cats[t_clean]:
            if item["name"].lower() == name.lower().strip():
                item["keywords"] = keywords
                break
        save_categories_to_sheets(cats)

def count_transactions_with_category(category_name: str) -> int:
    """Count how many transactions across all sheet tabs use category_name."""
    try:
        sheet_names = sheets_handler.get_all_sheet_names()
        count = 0
        cat_target = category_name.strip().lower()
        for s_name in sheet_names:
            s_lower = s_name.lower()
            if "expenses" in s_lower or "income" in s_lower or "savings" in s_lower or "ausgaben" in s_lower or "einnahmen" in s_lower or "ersparnisse" in s_lower or "." in s_lower:
                df = sheets_handler.read_sheet_data(s_name)
                if df is not None and not df.empty:
                    df.columns = [str(c).strip().lower() for c in df.columns]
                    col_cat = next((c for c in df.columns if c in ["kategorie", "category"]), None)
                    if col_cat:
                        matches = df[df[col_cat].astype(str).str.strip().str.lower() == cat_target]
                        count += len(matches)
        return count
    except Exception as e:
        logger.error(f"Error counting transactions for category {category_name}: {e}")
        return 0
