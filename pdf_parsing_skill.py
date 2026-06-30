# skills/pdf_parsing_skill.py

import io
import pdfplumber
import logging
from utils.gemini_client import gemini_client

logger = logging.getLogger(__name__)

def parse_pdf(file_bytes: bytes, context: str = "") -> list[dict]:
    """
    Skill 2: Extract text from bank PDF using pdfplumber,
    and structure transactions using Gemini (including classification).
    """
    from utils.categories import CATEGORIES, STATIC_RULES
    import re
    
    # 1. Extract raw text from PDF bytes
    raw_text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    raw_text += f"\n--- PAGE {page_idx + 1} ---\n{text}"
    except Exception as e:
        logger.error(f"Error reading PDF with pdfplumber: {e}")
        raise ValueError(f"Error reading PDF file: {str(e)}")

    if not raw_text.strip():
        raise ValueError("Could not extract any text from PDF. Is the PDF scanned or empty?")

    # Build a flat category list for the prompt
    all_categories = {}
    for tx_type, groups in CATEGORIES.items():
        for group_name, cats in groups.items():
            for cat in cats:
                all_categories[cat] = tx_type

    category_list_str = "\n".join(f"  - {cat} (Type: {tx_type})" for cat, tx_type in all_categories.items())

    context_hint = ""
    if context and context.strip():
        context_hint = f"""\nADDITIONAL USER NOTE (IMPORTANT — consider this note carefully during extraction, date correction, name assignment, and categorization):\nUSER COMMENT: {context.strip()}\n"""

    # 2. Single Gemini call: extract AND classify
    prompt = f"""
You are FamilyBudget AI. Analyze the following bank statement text and extract all bookings (transactions, income, savings).

{context_hint}
Extraction Rules:
- Search for all monetary transactions (debits, transfers, credits).
- Determine transaction date in "YYYY-MM-DD" format.
- Determine merchant name, purpose, recipient, or sender ("merchant").
- Determine monetary amount ("amount") as positive float.
- Determine transaction "type":
  - "expense": for all regular purchases, direct debits, card payments, money outflows.
  - "income": for salary, credits, incoming transfers, interest, dividends.
  - "savings": for recognizable savings rates, transfers to savings accounts, 401k, ETFs.
- Determine "person" (katja, dirk, shared, unknown):
  - For regular expenses ("type" is "expense"): always "shared".
  - For income or savings: assign to Katja or Dirk if recognizable from text. Otherwise "unknown".

Categorization Rules (IMPORTANT — select the most appropriate category from this list):
{category_list_str}
- If uncertain, select "Unknown" with confidence under 0.50.
- Set "confidence" to 0.0 to 1.0 based on assignment certainty.

- Determine an optional short note ("note").

Respond exclusively with a valid JSON array of objects. Use no markdown formatting other than the pure JSON array.
Format must look exactly like this:
[
  {{
    "date": "YYYY-MM-DD",
    "merchant": "Merchant name / Purpose",
    "amount": 12.34,
    "type": "expense | income | savings",
    "person": "katja | dirk | shared | unknown",
    "category": "Category name from list above",
    "confidence": 0.85,
    "note": "optional"
  }},
  ...
]

Bank statement text:
\"\"\"{raw_text}\"\"\"
"""
    try:
        extracted_txs = gemini_client.generate_json(prompt)
        if not isinstance(extracted_txs, list):
            if isinstance(extracted_txs, dict) and "transactions" in extracted_txs:
                extracted_txs = extracted_txs["transactions"]
            elif isinstance(extracted_txs, dict):
                extracted_txs = [extracted_txs]
            else:
                extracted_txs = []
    except Exception as e:
        logger.error(f"Error parsing PDF transactions with Gemini: {e}")
        raise ValueError(f"Gemini could not parse transactions from PDF: {str(e)}")

    # 3. Post-process: apply static rules as overrides
    valid_categories = set(all_categories.keys())
    classified_txs = []
    for tx in extracted_txs:
        try:
            merchant = tx.get("merchant", "Unknown")
            amount = float(tx.get("amount", 0.0))
            tx_type = tx.get("type", "expense").lower()
            category = tx.get("category", "Unknown")
            confidence = float(tx.get("confidence", 0.70))

            # Override with static rules if they match
            merchant_clean = merchant.strip().lower()
            for rule in STATIC_RULES:
                if re.search(rule["pattern"], merchant_clean):
                    category = rule["category"]
                    confidence = rule["confidence"]
                    break

            # Validate category
            if category not in valid_categories:
                category = "Unknown"
                confidence = min(confidence, 0.40)

            full_tx = {
                "date": tx.get("date"),
                "type": tx_type,
                "person": tx.get("person", "shared"),
                "merchant": merchant,
                "amount": amount,
                "category": category,
                "subcategory": "-",
                "source": "pdf",
                "confidence": confidence,
                "note": tx.get("note", "")
            }
            classified_txs.append(full_tx)
        except Exception as e:
            logger.error(f"Error processing PDF transaction {tx}: {e}")
            
    return classified_txs

def parse_image(file_bytes: bytes, mime_type: str, context: str = "") -> list[dict]:
    """
    Skill 2b: Extract and classify transactions from receipts/screenshots.
    """
    from google.genai import types
    from utils.categories import CATEGORIES, STATIC_RULES
    import re

    # Build flat category list for prompt
    all_categories = {}
    for tx_type, groups in CATEGORIES.items():
        for group_name, cats in groups.items():
            for cat in cats:
                all_categories[cat] = tx_type

    category_list_str = "\n".join(f"  - {cat} (Type: {tx_type})" for cat, tx_type in all_categories.items())

    context_hint = ""
    if context and context.strip():
        context_hint = f"""\nADDITIONAL USER NOTE (IMPORTANT — consider this note carefully during extraction, date correction, name assignment, and categorization):\nUSER COMMENT: {context.strip()}\n"""

    prompt = f"""
You are FamilyBudget AI. Analyze the uploaded image of a financial document (e.g. screenshot, receipt, invoice, income proof) and extract all bookings (expenses, income, savings).

{context_hint}
Extraction Rules:
- Search for all monetary movements (amounts, transfers, salary, savings, dividends, interest).
- Determine date in "YYYY-MM-DD" format.
- Determine merchant name, source, or recipient/sender ("merchant").
- Determine monetary amount ("amount") as positive float.
- Determine "type" of transaction ("expense", "income", or "savings").
- Determine "person" (katja, dirk, shared, unknown).

Categorization Rules (IMPORTANT — select most appropriate category from list):
{category_list_str}
- If uncertain, select "Unknown" with confidence under 0.50.

Respond exclusively with a valid JSON array of objects.
Format must look exactly like this:
[
  {{
    "date": "YYYY-MM-DD",
    "merchant": "Merchant name / Purpose",
    "amount": 12.34,
    "type": "expense | income | savings",
    "person": "katja | dirk | shared | unknown",
    "category": "Category name from list above",
    "confidence": 0.85,
    "note": "optional"
  }},
  ...
]
"""
    
    contents = [
        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
        prompt
    ]
    
    try:
        extracted_txs = gemini_client.generate_json(contents)
        if not isinstance(extracted_txs, list):
            if isinstance(extracted_txs, dict) and "transactions" in extracted_txs:
                extracted_txs = extracted_txs["transactions"]
            elif isinstance(extracted_txs, dict):
                extracted_txs = [extracted_txs]
            else:
                extracted_txs = []
    except Exception as e:
        logger.error(f"Error parsing image transactions with Gemini: {e}")
        raise ValueError(f"Gemini could not parse image: {str(e)}")
        
    # Post-process: apply static rules as overrides
    valid_categories = set(all_categories.keys())
    classified_txs = []
    for tx in extracted_txs:
        try:
            merchant = tx.get("merchant", "Unknown")
            amount = float(tx.get("amount", 0.0))
            tx_type = tx.get("type", "expense").lower()
            category = tx.get("category", "Unknown")
            confidence = float(tx.get("confidence", 0.70))

            # Override with static rules if they match
            merchant_clean = merchant.strip().lower()
            for rule in STATIC_RULES:
                if re.search(rule["pattern"], merchant_clean):
                    category = rule["category"]
                    confidence = rule["confidence"]
                    break

            if category not in valid_categories:
                category = "Unknown"
                confidence = min(confidence, 0.40)

            full_tx = {
                "date": tx.get("date"),
                "type": tx_type,
                "person": tx.get("person", "shared"),
                "merchant": merchant,
                "amount": amount,
                "category": category,
                "subcategory": "-",
                "source": "image",
                "confidence": confidence,
                "note": tx.get("note", "")
            }
            classified_txs.append(full_tx)
        except Exception as e:
            logger.error(f"Error processing image transaction {tx}: {e}")
            
    return classified_txs
