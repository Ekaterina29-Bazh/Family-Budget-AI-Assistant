# skills/text_parser.py

import datetime
import logging
from utils.gemini_client import gemini_client

logger = logging.getLogger(__name__)

def parse_text(message: str) -> dict:
    """
    Skill 1: Parses English text to extract a structured transaction.
    Returns a dictionary matching the target JSON schema.
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    prompt = f"""
You are FamilyBudget AI. Analyze the following text.
First, determine whether it represents a financial transaction (e.g. income, expense, savings, booking, like "Lidl $23.50" or "Salary received").
If it is a general question, greeting (e.g. "Hello", "Good morning"), unrelated conversation, clear/cancel action, or pure analytics query, set "is_transaction" to false.

Field rules:
1. "is_transaction": true if text describes a financial transaction (expense, income, or savings). Otherwise false.
2. "date": Date in "YYYY-MM-DD" format. Today's date (default for 'date' if no other date/month is mentioned in text): {today_str}
3. "date_specified": true if a concrete date, month (e.g., "in May", "June"), or relative day ("today", "yesterday", "last week") was explicitly or implicitly mentioned. Otherwise false.
4. "merchant": The name of the merchant, source, or recipient (e.g., "Lidl", "Shell Gas Station", "eBay").
5. "merchant_specified": true if a merchant, recipient, or source was mentioned in text. Otherwise false.
6. "amount": The monetary amount as a float (e.g. 23.50). Use a period as decimal separator.
7. "amount_specified": true if a monetary amount was mentioned in text. Otherwise false.
8. "type": One of the following: "expense" (default for purchases/expenses), "income" (for earnings like salary, sale), "savings" (for savings rates, 401k, ETF).
9. "person": "katja", "dirk", or "shared". Unless Katja or Dirk is explicitly named in text, always use "shared".
10. "category_hint": A category mentioned or implied in text (e.g., "Groceries", "Fuel", "Salary"). This is only a hint for classification.
11. "source": Always "text".
12. "note": An optional short note or extra info from text (e.g., "for birthday party"). If none, empty string "".

Respond exclusively with a valid JSON object without additional text. The JSON must match this exact structure:
{{
  "is_transaction": true | false,
  "date": "YYYY-MM-DD",
  "date_specified": true | false,
  "merchant": "Merchant name or source",
  "merchant_specified": true | false,
  "amount": 0.00,
  "amount_specified": true | false,
  "type": "expense | income | savings",
  "person": "katja | dirk | shared",
  "category_hint": "Hint",
  "source": "text",
  "note": "optional"
}}

Text to analyze:
"{message}"
"""

    try:
        parsed = gemini_client.generate_json(prompt)
        # Ensure default values and types
        if not parsed.get("date"):
            parsed["date"] = today_str
        if parsed.get("amount"):
            try:
                parsed["amount"] = float(str(parsed["amount"]).replace(",", "."))
            except ValueError:
                parsed["amount"] = 0.0
        else:
            parsed["amount"] = 0.0
            
        # Standardize types and person
        parsed["type"] = parsed.get("type", "expense").lower()
        p = str(parsed.get("person", "shared")).lower()
        if "katja" in p:
            parsed["person"] = "katja"
        elif "dirk" in p:
            parsed["person"] = "dirk"
        else:
            parsed["person"] = "shared"
                
        parsed["merchant"] = parsed.get("merchant", "Unknown")
        parsed["source"] = "text"
        parsed["note"] = parsed.get("note", "")
        
        # Ensure specified flags exist
        parsed["is_transaction"] = bool(parsed.get("is_transaction", True))
        parsed["date_specified"] = bool(parsed.get("date_specified", False))
        parsed["merchant_specified"] = bool(parsed.get("merchant_specified", False))
        parsed["amount_specified"] = bool(parsed.get("amount_specified", False))
        
        return parsed
    except Exception as e:
        logger.error(f"Error in parse_text: {e}")
        # Fallback empty structure
        return {
            "is_transaction": False,
            "date": today_str,
            "date_specified": False,
            "person": "shared",
            "merchant": "Unknown",
            "merchant_specified": False,
            "amount": 0.0,
            "amount_specified": False,
            "type": "expense",
            "category_hint": "",
            "source": "text",
            "note": f"Error parsing: {str(e)}"
        }

def clarify_pending_transaction(pending_tx: dict, user_reply: str) -> dict:
    """
    Skill 1b: Clarifies an incomplete transaction by merging it with the user's clarification response.
    """
    prompt = f"""
You are FamilyBudget AI. We have an incomplete or unclear transaction:
{pending_tx}

The user gave the following response to our request for clarification:
"{user_reply}"

Update the transaction details based on the user's response.
If the user specifies a date or month (e.g. "May", "in June", "last month"), adjust the "date" field and set "date_specified" to true.
If the user names a merchant, adjust "merchant" and set "merchant_specified" to true.
If the user specifies an amount, adjust "amount" and set "amount_specified" to true.
If the user specifies or selects a category, adjust "category".
If the user says "looks good", "today", or confirms default values, set the corresponding specified field to true (e.g. "date_specified" to true for today/looks good).

Respond exclusively with a valid JSON object without additional text. The JSON must match the exact same structure as the transaction with updated values:
{{
  "is_transaction": true,
  "date": "YYYY-MM-DD",
  "date_specified": true | false,
  "merchant": "Merchant name or source",
  "merchant_specified": true | false,
  "amount": 0.00,
  "amount_specified": true | false,
  "type": "expense | income | savings",
  "person": "katja | dirk | shared | unknown",
  "category": "...",
  "subcategory": "...",
  "confidence": 0.00 to 1.00,
  "source": "text",
  "note": "..."
}}
"""
    try:
        parsed = gemini_client.generate_json(prompt)
        # Ensure default values and types
        if parsed.get("amount"):
            try:
                parsed["amount"] = float(str(parsed["amount"]).replace(",", "."))
            except ValueError:
                parsed["amount"] = pending_tx.get("amount", 0.0)
        else:
            parsed["amount"] = pending_tx.get("amount", 0.0)
            
        parsed["type"] = parsed.get("type", pending_tx.get("type", "expense")).lower()
        parsed["person"] = parsed.get("person", pending_tx.get("person", "shared")).lower()
        parsed["merchant"] = parsed.get("merchant", pending_tx.get("merchant", "Unknown"))
        parsed["source"] = "text"
        parsed["note"] = parsed.get("note", pending_tx.get("note", ""))
        
        # Ensure specified flags are updated
        parsed["is_transaction"] = True
        parsed["date_specified"] = bool(parsed.get("date_specified", pending_tx.get("date_specified", False)))
        parsed["merchant_specified"] = bool(parsed.get("merchant_specified", pending_tx.get("merchant_specified", False)))
        parsed["amount_specified"] = bool(parsed.get("amount_specified", pending_tx.get("amount_specified", False)))
        
        return parsed
    except Exception as e:
        logger.error(f"Error clarifying pending transaction: {e}")
        return pending_tx

def generate_general_response(message: str) -> str:
    """
    Generates a general assistant response for non-transaction questions or conversation.
    """
    prompt = f"""
You are FamilyBudget AI, an intelligent and friendly financial assistant for a family (Katja and Dirk).
The user sent the following message (not a direct booking transaction):
"{message}"

Respond in a friendly, concise, and helpful manner in English. You can explain how you can help (e.g., logging expenses, reading PDF bank statements, generating budget analytics). Keep it concise.
"""
    try:
        response = gemini_client.generate(prompt)
        return response
    except Exception as e:
        return f"Hello! I am your FamilyBudget AI Assistant. How can I help you today? (Error generating response: {e})"
