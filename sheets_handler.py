# utils/sheets_handler.py

import os
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Google API client imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv(override=True)

logger = logging.getLogger(__name__)

LOCAL_FILE = "family_budget_data.xlsx"
HEADERS = ["Date", "Merchant", "Amount", "Category", "Subcategory", "Source", "Person", "Type", "Note"]

def get_friendly_error_message(e: Exception) -> str:
    err_str = str(e)
    if "must not be an Office file" in err_str or "Office file" in err_str:
        return "The Google Spreadsheet is saved in Office format (.xlsx). Please convert it to a native Google Sheet (go to Google Drive, open the file in Google Sheets, click on **File -> Save as Google Sheets**) and enter the new Spreadsheet ID in your settings."
    elif "403" in err_str or "PERMISSION_DENIED" in err_str:
        return "Access denied (403). Please ensure you have shared the Google Spreadsheet with the Service Account email address (with edit permissions)."
    elif "404" in err_str or "NOT_FOUND" in err_str:
        return "The Google Spreadsheet was not found. Please check the Spreadsheet ID in settings."
    return f"Google Sheets connection error: {err_str}"

def format_person(p_val) -> str:
    if not p_val:
        return "Shared"
    p_str = str(p_val).strip().lower()
    if "katja" in p_str:
        return "Katja"
    elif "dirk" in p_str:
        return "Dirk"
    else:
        return "Shared"


class SheetsHandler:
    def __init__(self):
        raw_id = os.environ.get("SPREADSHEET_ID") or os.environ.get("SPREDSHEET_ID")
        self.spreadsheet_id = None
        if raw_id:
            raw_id = raw_id.strip()
            if "docs.google.com/spreadsheets" in raw_id:
                import re
                match = re.search(r"/d/([a-zA-Z0-9-_]+)", raw_id)
                if match:
                    self.spreadsheet_id = match.group(1)
                else:
                    self.spreadsheet_id = raw_id
            else:
                self.spreadsheet_id = raw_id

        self.creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
        self.use_google = False
        self.service = None

        if self.spreadsheet_id and os.path.exists(self.creds_path):
            try:
                # Attempt to authenticate with Google Sheets API
                scopes = ["https://www.googleapis.com/auth/spreadsheets"]
                creds = service_account.Credentials.from_service_account_file(
                    self.creds_path, scopes=scopes
                )
                self.service = build("sheets", "v4", credentials=creds)
                self.use_google = True
                logger.info("Successfully connected to Google Sheets API.")
            except Exception as e:
                logger.error(f"Google Sheets connection failed, falling back to local Excel: {e}")
                self.use_google = False
        else:
            logger.info("Using local Excel file fallback (no Google Sheets credentials found).")

    def _invalidate_cache(self):
        try:
            import streamlit as st
            if hasattr(st, "session_state"):
                st.session_state["analytics_dirty"] = True
        except Exception:
            pass

    def _get_sheet_name(self, date_str: str) -> str:
        """Get the tab name based on date (e.g., '06.2026')"""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime('%m.%Y')
        except Exception:
            # Fallback to current month if parsing fails
            return datetime.now().strftime('%m.%Y')

    # --- LOCAL EXCEL METHODS ---
    
    def _init_local_sheet(self, sheet_name: str) -> str:
        """Ensure local Excel exists and has the requested sheet name. Returns exact sheet title."""
        if not os.path.exists(LOCAL_FILE):
            # Create a new workbook with headers
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                df = pd.DataFrame(columns=HEADERS)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                # Create empty Analytics sheet
                df_analytics = pd.DataFrame(columns=["Section", "Metric", "Value"])
                df_analytics.to_excel(writer, sheet_name="Analytics", index=False)
            return sheet_name

        # Check if sheet exists
        xls = pd.ExcelFile(LOCAL_FILE)
        existing_sheet = next((s for s in xls.sheet_names if s.lower() == sheet_name.lower()), None)
        if not existing_sheet:
            # Load existing sheets and append the new sheet
            sheets = {}
            for name in xls.sheet_names:
                sheets[name] = pd.read_excel(xls, name)
            
            sheets[sheet_name] = pd.DataFrame(columns=HEADERS)
            
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                for name, df in sheets.items():
                    df.to_excel(writer, sheet_name=name, index=False)
            return sheet_name
        else:
            return existing_sheet

    def _read_local_sheet(self, sheet_name: str) -> pd.DataFrame:
        actual_name = self._init_local_sheet(sheet_name)
        try:
            return pd.read_excel(LOCAL_FILE, sheet_name=actual_name)
        except Exception as e:
            logger.error(f"Error reading local sheet {actual_name}: {e}")
            return pd.DataFrame(columns=HEADERS)

    def _write_local_sheet(self, sheet_name: str, df: pd.DataFrame):
        actual_name = self._init_local_sheet(sheet_name)
        xls = pd.ExcelFile(LOCAL_FILE)
        sheets = {}
        for name in xls.sheet_names:
            if name == actual_name:
                sheets[name] = df
            else:
                sheets[name] = pd.read_excel(xls, name)
        
        with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
            for name, d in sheets.items():
                d.to_excel(writer, sheet_name=name, index=False)

    # --- GOOGLE SHEETS API METHODS ---

    def _init_google_sheet(self, sheet_name: str) -> str:
        """Ensure Google Sheet tab exists."""
        if not self.use_google:
            return sheet_name
        
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_names = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]
            
            # Create monthly tab if not exists
            existing_sheet = next((s for s in sheet_names if s.lower() == sheet_name.lower()), None)
            if not existing_sheet:
                body = {
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {
                                    "title": sheet_name
                                }
                            }
                        }
                    ]
                }
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id, body=body
                ).execute()
                
                # Write headers
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{sheet_name}'!A1:I1",
                    valueInputOption="USER_ENTERED",
                    body={"values": [HEADERS]}
                ).execute()
                target_sheet = sheet_name
            else:
                target_sheet = existing_sheet
                
            # Create Analytics tab if not exist
            if not any(s.lower() == "analytics" for s in sheet_names):
                body = {
                    "requests": [{"addSheet": {"properties": {"title": "Analytics"}}}]
                }
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id, body=body
                ).execute()
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range="'Analytics'!A1:C1",
                    valueInputOption="USER_ENTERED",
                    body={"values": [["Section", "Metric", "Value"]]}
                ).execute()
                
            return target_sheet
                        
        except HttpError as err:
            logger.error(f"Google API error in _init_google_sheet: {err}")
            raise err

    def _init_new_google_sheet(self, sheet_name: str, headers: list[str]) -> str:
        """Ensure Google Sheet tab exists with the given headers. Returns exact sheet title."""
        if not self.use_google:
            return sheet_name
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_names = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]
            
            existing_sheet = next((s for s in sheet_names if s.lower() == sheet_name.lower()), None)
            if not existing_sheet:
                body = {
                    "requests": [{"addSheet": {"properties": {"title": sheet_name}}}]
                }
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id, body=body
                ).execute()
                
                # Write headers
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{sheet_name}'!A1:{chr(65 + len(headers) - 1)}1",
                    valueInputOption="USER_ENTERED",
                    body={"values": [headers]}
                ).execute()
                return sheet_name
            else:
                return existing_sheet
        except HttpError as err:
            logger.error(f"Google API error in _init_new_google_sheet: {err}")
            raise err

    def _init_new_local_sheet(self, sheet_name: str, headers: list[str]) -> str:
        """Ensure local Excel sheet exists with the given headers. Returns exact sheet title."""
        if not os.path.exists(LOCAL_FILE):
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                df = pd.DataFrame(columns=headers)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            return sheet_name
            
        xls = pd.ExcelFile(LOCAL_FILE)
        existing_sheet = next((s for s in xls.sheet_names if s.lower() == sheet_name.lower()), None)
        if not existing_sheet:
            sheets = {}
            for name in xls.sheet_names:
                sheets[name] = pd.read_excel(xls, name)
            sheets[sheet_name] = pd.DataFrame(columns=headers)
            
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                for name, df in sheets.items():
                    header = False if name.lower() == "analytics" else True
                    df.to_excel(writer, sheet_name=name, index=False, header=header)
            return sheet_name
        else:
            return existing_sheet

    # --- PUBLIC INTERFACE ---

    def add_transaction(self, transaction: dict) -> bool:
        """Add a transaction dict to the correct month sheet based on type."""
        date_val = transaction.get("date", datetime.now().strftime("%Y-%m-%d"))
        tx_type = transaction.get("type", "expense").lower()
        if tx_type not in ["expense", "income", "savings"]:
            tx_type = "expense"
            
        month_str = date_val[:7] # YYYY-MM
        person_val = format_person(transaction.get("person"))

        if tx_type == "income":
            sheet_name = f"{month_str} income"
        elif tx_type == "savings":
            sheet_name = f"{month_str} savings"
        else:
            sheet_name = f"{month_str} expenses"

        headers = HEADERS
        merchant_val = transaction.get("merchant", "")
        if not merchant_val and tx_type in ["income", "savings"]:
            merchant_val = person_val
            
        row_data = [
            date_val,
            merchant_val,
            float(transaction.get("amount", 0.0)),
            transaction.get("category", ""),
            transaction.get("subcategory", "-"),
            transaction.get("source", "text"),
            person_val,
            tx_type,
            transaction.get("note", "")
        ]
            
        if self.use_google:
            try:
                sheet_name = self._init_new_google_sheet(sheet_name, headers)
                # Append row
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{sheet_name}'!A:I",
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row_data]}
                ).execute()
                self._invalidate_cache()
                return True
            except Exception as e:
                logger.error(f"Failed to write to Google Sheets: {e}.")
                raise e
                
        # Local Excel writing
        sheet_name = self._init_new_local_sheet(sheet_name, headers)
        try:
            df = pd.read_excel(LOCAL_FILE, sheet_name=sheet_name)
        except Exception:
            df = pd.DataFrame(columns=headers)
            
        new_row = pd.DataFrame([row_data], columns=headers)
        df = pd.concat([df, new_row], ignore_index=True)
        
        # Write back all sheets
        xls = pd.ExcelFile(LOCAL_FILE)
        sheets = {}
        for name in xls.sheet_names:
            if name == sheet_name:
                sheets[name] = df
            else:
                sheets[name] = pd.read_excel(xls, name)
                
        with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
            for name, d in sheets.items():
                header = False if name.lower() == "analytics" else True
                d.to_excel(writer, sheet_name=name, index=False, header=header)
        self._invalidate_cache()
        return True

    def _normalize_and_translate_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Helper to map any dataframe (German or English) to standard English headers and categories."""
        if df is None or df.empty:
            return pd.DataFrame(columns=HEADERS)
            
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        col_map = {
            "datum": "date", "händler": "merchant", "betrag": "amount", 
            "kategorie": "category", "unterkategorie": "subcategory", 
            "quelle": "source", "confidence": "confidence", "person": "person",
            "typ": "type", "notiz": "note"
        }
        df = df.rename(columns=col_map)
        
        # Ensure all columns in HEADERS exist
        for col in HEADERS:
            col_lower = col.lower()
            if col_lower not in df.columns:
                df[col_lower] = ""
                
        # Build mapped rows to ensure proper order and map category/person names
        from utils.categories import CATEGORY_MAP_DE_TO_EN
        mapped_rows = []
        for _, row in df.iterrows():
            raw_cat = str(row.get("category", "")).strip()
            cat_val = CATEGORY_MAP_DE_TO_EN.get(raw_cat, raw_cat)
            
            raw_person = str(row.get("person", "")).strip().lower()
            if raw_person in ["gemeinsam", "shared", ""]:
                person_val = "Shared"
            elif "katja" in raw_person:
                person_val = "Katja"
            elif "dirk" in raw_person:
                person_val = "Dirk"
            else:
                person_val = raw_person.capitalize()
                
            raw_type = str(row.get("type", "")).strip().lower()
            if raw_type in ["ausgaben", "ausgabe", "expense"]:
                type_val = "expense"
            elif raw_type in ["einnahmen", "einnahme", "income"]:
                type_val = "income"
            elif raw_type in ["ersparnisse", "ersparnis", "sparen", "savings"]:
                type_val = "savings"
            else:
                type_val = "expense"
                
            mapped_rows.append({
                "Date": str(row.get("date", "")),
                "Merchant": str(row.get("merchant", "Unknown")),
                "Amount": str(row.get("amount", 0.0)),
                "Category": cat_val,
                "Subcategory": str(row.get("subcategory", "-")),
                "Source": str(row.get("source", "manual")),
                "Person": person_val,
                "Type": type_val,
                "Note": str(row.get("note", ""))
            })
            
        return pd.DataFrame(mapped_rows, columns=HEADERS)

    def get_transactions(self, month_str: str = None) -> pd.DataFrame:
        """
        Get transactions for a specific month (format 'YYYY-MM' or 'MM.YYYY').
        If month_str is None, returns transactions of the current month.
        """
        if not month_str:
            month_yyyy_mm = datetime.now().strftime("%Y-%m")
            month_mm_yyyy = datetime.now().strftime("%m.%Y")
        elif "-" in month_str:
            parts = month_str.split("-")
            month_yyyy_mm = f"{parts[0]}-{parts[1]}"
            month_mm_yyyy = f"{parts[1]}.{parts[0]}"
        elif "." in month_str:
            parts = month_str.split(".")
            month_yyyy_mm = f"{parts[1]}-{parts[0]}"
            month_mm_yyyy = f"{parts[0]}.{parts[1]}"
        else:
            month_yyyy_mm = datetime.now().strftime("%Y-%m")
            month_mm_yyyy = datetime.now().strftime("%m.%Y")
            
        sheet_names = self.get_all_sheet_names()
        new_exp_sheet = next((s for s in sheet_names if s.lower() == f"{month_yyyy_mm} expenses"), None)
        
        if new_exp_sheet:
            new_inc_sheet = next((s for s in sheet_names if s.lower() == f"{month_yyyy_mm} income"), None)
            new_sav_sheet = next((s for s in sheet_names if s.lower() == f"{month_yyyy_mm} savings"), None)
            
            df_exp = self.read_sheet_data(new_exp_sheet)
            if not df_exp.empty and "type" not in [c.lower() for c in df_exp.columns]:
                df_exp["type"] = "expense"
            df_inc = self.read_sheet_data(new_inc_sheet) if new_inc_sheet else pd.DataFrame()
            if not df_inc.empty and "type" not in [c.lower() for c in df_inc.columns]:
                df_inc["type"] = "income"
            df_sav = self.read_sheet_data(new_sav_sheet) if new_sav_sheet else pd.DataFrame()
            if not df_sav.empty and "type" not in [c.lower() for c in df_sav.columns]:
                df_sav["type"] = "savings"
            
            combined_df = pd.concat([df_exp, df_inc, df_sav], ignore_index=True)
            return self._normalize_and_translate_df(combined_df)

        # Fallback to old format
        sheet_name = month_mm_yyyy
        
        if self.use_google:
            try:
                self._init_google_sheet(sheet_name)
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{sheet_name}'!A:Z"
                ).execute()
                rows = result.get("values", [])
                
                if not rows:
                    return pd.DataFrame(columns=HEADERS)
                    
                is_custom = len(rows[0]) > 0 and "Datum" not in rows[0] and "Date" not in rows[0]
                if is_custom:
                    return self._parse_custom_layout(rows, month_mm_yyyy)
                
                if len(rows) <= 1:
                    return pd.DataFrame(columns=HEADERS)
                
                header = rows[0]
                cleaned_rows = []
                for row in rows[1:]:
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    elif len(row) > len(header):
                        row = row[:len(header)]
                    cleaned_rows.append(row)
                
                df = pd.DataFrame(cleaned_rows, columns=header)
                return self._normalize_and_translate_df(df)
            except Exception as e:
                logger.error(f"Google API error in get_transactions: {e}.")
                raise e
                
        df = self._read_local_sheet(sheet_name)
        return self._normalize_and_translate_df(df)

    def _parse_custom_layout(self, rows, month_str: str) -> pd.DataFrame:
        """Parses user's custom budget overview tab into transaction list."""
        try:
            parts = month_str.split(".")
            default_date = f"{parts[1]}-{parts[0]}-15"
        except Exception:
            default_date = "2026-06-15"
            
        def parse_val(val_str):
            if not val_str:
                return 0.0
            val_str = str(val_str).strip()
            val_str = val_str.replace("€", "").replace("\u20ac", "").strip()
            val_str = val_str.replace(",", "")
            try:
                return float(val_str)
            except ValueError:
                return 0.0

        try:
            from utils.categories import CATEGORY_MAP_DE_TO_EN
            transactions = []
            income_categories = ["Einkommen", "Einkommen ", "Dividenden", "Zinsen", "Cashback", "Verkauf", "Geschenk (Geld)", "Sonstiges",
                                 "Income", "Dividends", "Interest", "Cashback", "Sales", "Monetary Gift", "Other Income"]
            savings_categories = ["Investitionen (Sparpläne)", "Altersvorsorge", "Zeitwertpapiere",
                                  "Investments (Savings Plans)", "Retirement", "Securities"]
            
            last_income_category = None
            last_savings_category = None
            last_active_type = None
            
            for row_idx, r in enumerate(rows):
                row = r + [""] * (25 - len(r))
                
                col_a = row[0].strip()
                col_b = row[1].strip()
                col_c = row[2].strip()
                
                is_income_total = False
                if col_a and ("TOTAL" in col_a.upper() or "GESAMT" in col_a.upper()):
                    last_active_type = None
                    last_income_category = None
                    last_savings_category = None
                    is_income_total = True
                    
                if col_b and col_b.upper() in ["TOTAL", "GESAMT"]:
                    is_income_total = True
                    
                if not is_income_total:
                    if col_a:
                        category = col_a
                        person = col_b.lower() if col_b else "shared"
                        amount = parse_val(col_c)
                        
                        tx_type = None
                        if category in income_categories:
                            tx_type = "income"
                            last_income_category = category
                            last_active_type = "income"
                        elif category in savings_categories:
                            tx_type = "savings"
                            last_savings_category = category
                            last_active_type = "savings"
                        else:
                            last_active_type = None
                            
                        if tx_type and amount > 0:
                            transactions.append({
                                "Date": default_date,
                                "Merchant": "Unknown",
                                "Amount": amount,
                                "Category": CATEGORY_MAP_DE_TO_EN.get(category.strip(), category.strip()),
                                "Subcategory": "-",
                                "Source": "manual",
                                "Person": person.capitalize(),
                                "Type": tx_type,
                                "Note": ""
                            })
                    elif col_b and col_c:
                        person = col_b.lower()
                        amount = parse_val(col_c)
                        
                        if last_active_type == "income" and last_income_category:
                            transactions.append({
                                "Date": default_date,
                                "Merchant": "Unknown",
                                "Amount": amount,
                                "Category": CATEGORY_MAP_DE_TO_EN.get(last_income_category.strip(), last_income_category.strip()),
                                "Subcategory": "-",
                                "Source": "manual",
                                "Person": person.capitalize(),
                                "Type": "income",
                                "Note": ""
                            })
                        elif last_active_type == "savings" and last_savings_category:
                            transactions.append({
                                "Date": default_date,
                                "Merchant": "Unknown",
                                "Amount": amount,
                                "Category": CATEGORY_MAP_DE_TO_EN.get(last_savings_category.strip(), last_savings_category.strip()),
                                "Subcategory": "-",
                                "Source": "manual",
                                "Person": person.capitalize(),
                                "Type": "savings",
                                "Note": ""
                            })

                col_e = row[4].strip()
                col_f = row[5].strip()
                col_g = row[6].strip()
                
                if col_f and not col_f.startswith("TOTAL"):
                    category = col_f
                    total_amount = parse_val(col_g)
                    
                    tx_amounts = []
                    for col_idx in range(8, len(row)):
                        val = parse_val(row[col_idx])
                        if val > 0:
                            tx_amounts.append(val)
                            
                    if tx_amounts:
                        sum_tx = sum(tx_amounts)
                        for amt in tx_amounts:
                            transactions.append({
                                "Date": default_date,
                                "Merchant": "Unknown",
                                "Amount": amt,
                                "Category": CATEGORY_MAP_DE_TO_EN.get(category.strip(), category.strip()),
                                "Subcategory": "-",
                                "Source": "manual",
                                "Person": "Shared",
                                "Type": "expense",
                                "Note": ""
                            })
                        if sum_tx < total_amount:
                            transactions.append({
                                "Date": default_date,
                                "Merchant": "Unknown",
                                "Amount": round(total_amount - sum_tx, 2),
                                "Category": CATEGORY_MAP_DE_TO_EN.get(category.strip(), category.strip()),
                                "Subcategory": "-",
                                "Source": "manual",
                                "Person": "Shared",
                                "Type": "expense",
                                "Note": "Rest"
                            })
                    elif total_amount > 0:
                        transactions.append({
                            "Date": default_date,
                            "Merchant": "Unknown",
                            "Amount": total_amount,
                            "Category": CATEGORY_MAP_DE_TO_EN.get(category.strip(), category.strip()),
                            "Subcategory": "-",
                            "Source": "manual",
                            "Person": "Shared",
                            "Type": "expense",
                            "Note": ""
                        })
            return pd.DataFrame(transactions, columns=HEADERS)
        except Exception as e:
            logger.error(f"Error parsing custom layout: {e}")
            return pd.DataFrame(columns=HEADERS)

    def get_all_months(self) -> list[str]:
        """Returns a list of month strings ('MM.YYYY') that have tabs."""
        import re
        month_pattern = re.compile(r"^\d{2}\.\d{4}$")
        new_pattern = re.compile(r"^(\d{4})-(\d{2}) expenses$", re.IGNORECASE)
        
        sheet_names = self.get_all_sheet_names()
        months = set()
        for name in sheet_names:
            if month_pattern.match(name):
                months.add(name)
            else:
                m = new_pattern.match(name)
                if m:
                    months.add(f"{m.group(2)}.{m.group(1)}")
        if not months:
            return [datetime.now().strftime("%m.%Y")]
        return sorted(list(months))

    def update_transaction(self, date_str: str, merchant: str, amount: float, new_category: str) -> bool:
        """Finds and updates the category of a transaction."""
        month_yyyy_mm = date_str[:7]
        sheet_names = self.get_all_sheet_names()
        new_exp_sheet = next((s for s in sheet_names if s.lower() == f"{month_yyyy_mm} expenses"), None)
        
        amount = float(amount)
        if new_exp_sheet:
            sheet_name = new_exp_sheet
            is_new_format = True
        else:
            sheet_name = self._get_sheet_name(date_str)
            is_new_format = False
            
        if self.use_google:
            try:
                if is_new_format:
                    self._init_new_google_sheet(sheet_name, ["date", "merchant", "amount", "category", "subcategory", "source", "confidence"])
                else:
                    self._init_google_sheet(sheet_name)
                    
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{sheet_name}'!A:I"
                ).execute()
                rows = result.get("values", [])
                if not rows or len(rows) <= 1:
                    return False
                
                headers = [h.strip().lower() for h in rows[0]]
                
                def find_col_idx(names: list[str]) -> int:
                    for name in names:
                        name_lower = name.lower()
                        if name_lower in headers:
                            return headers.index(name_lower)
                    raise ValueError(f"None of {names} found in sheet headers {headers}")
                    
                date_idx = find_col_idx(["date", "datum"])
                merchant_idx = find_col_idx(["merchant", "händler"])
                amount_idx = find_col_idx(["amount", "betrag"])
                cat_idx = find_col_idx(["category", "kategorie"])
                
                updated = False
                for idx, row in enumerate(rows[1:], start=2): # 1-based, index 1 is header
                    if len(row) > max(date_idx, merchant_idx, amount_idx):
                        # Clean values for matching
                        row_date = row[date_idx].strip()
                        row_merchant = row[merchant_idx].strip().lower()
                        try:
                            # Normalize commas/dots in amounts
                            row_amt_str = row[amount_idx].replace(",", ".").strip()
                            row_amount = float(row_amt_str)
                        except ValueError:
                            continue
                        
                        if row_date == date_str and merchant.lower() in row_merchant and abs(row_amount - amount) < 0.01:
                            # Update Category cell
                            cell_range = f"'{sheet_name}'!{chr(65 + cat_idx)}{idx}"
                            self.service.spreadsheets().values().update(
                                spreadsheetId=self.spreadsheet_id,
                                range=cell_range,
                                valueInputOption="USER_ENTERED",
                                body={"values": [[new_category]]}
                            ).execute()
                            updated = True
                            break
                if updated:
                    self._invalidate_cache()
                return updated
            except Exception as e:
                logger.error(f"Google API error in update_transaction: {e}.")
                raise e

        # Local Excel
        try:
            df = pd.read_excel(LOCAL_FILE, sheet_name=sheet_name)
        except Exception:
            return False
            
        if df.empty:
            return False

        cols_lower = [str(c).lower().strip() for c in df.columns]
        
        def get_col_name(names: list[str], default: str) -> str:
            for n in names:
                if n.lower() in cols_lower:
                    idx = cols_lower.index(n.lower())
                    return df.columns[idx]
            return default
            
        date_col = get_col_name(["date", "datum"], "date")
        merchant_col = get_col_name(["merchant", "händler"], "merchant")
        amount_col = get_col_name(["amount", "betrag"], "amount")
        cat_col = get_col_name(["category", "kategorie"], "category")

        matched_indices = df[
            (df[date_col].astype(str) == date_str) & 
            (df[merchant_col].str.lower().str.contains(merchant.lower(), na=False)) & 
            ((df[amount_col].astype(float) - amount).abs() < 0.01)
        ].index
        
        if len(matched_indices) > 0:
            df.loc[matched_indices[0], cat_col] = new_category
            
            # Write back all sheets
            xls = pd.ExcelFile(LOCAL_FILE)
            sheets = {}
            for name in xls.sheet_names:
                if name == sheet_name:
                    sheets[name] = df
                else:
                    sheets[name] = pd.read_excel(xls, name)
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                for name, d in sheets.items():
                    header = False if name == "analytics" else True
                    d.to_excel(writer, sheet_name=name, index=False, header=header)
            self._invalidate_cache()
            return True
        return False

    def write_analytics(self, summary_rows: list[list]) -> bool:
        """Write processed analytics summary to the Analytics tab."""
        if self.use_google:
            try:
                # Clear and write new analytics
                self.service.spreadsheets().values().clear(
                    spreadsheetId=self.spreadsheet_id,
                    range="'Analytics'!A1:C100"
                ).execute()
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range="'Analytics'!A1",
                    valueInputOption="USER_ENTERED",
                    body={"values": [["Section", "Metric", "Value"]] + summary_rows}
                ).execute()
                return True
            except Exception as e:
                logger.error(f"Google API error writing analytics: {e}")
                raise e
                
        # Local Excel
        df = pd.DataFrame(summary_rows, columns=["Section", "Metric", "Value"])
        xls = pd.ExcelFile(LOCAL_FILE)
        sheets = {}
        for name in xls.sheet_names:
            if name == "Analytics":
                sheets[name] = df
            else:
                sheets[name] = pd.read_excel(xls, name)
        
        with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
            for name, d in sheets.items():
                d.to_excel(writer, sheet_name=name, index=False)
        return True

    def get_all_sheet_names(self) -> list[str]:
        """Returns a list of all sheet names in the spreadsheet."""
        if self.use_google:
            try:
                spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
                return [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]
            except Exception as e:
                logger.error(f"Google API error in get_all_sheet_names: {e}")
                raise e
        # Local Excel
        if not os.path.exists(LOCAL_FILE):
            return []
        xls = pd.ExcelFile(LOCAL_FILE)
        return xls.sheet_names

    def read_sheet_data(self, sheet_name: str) -> pd.DataFrame:
        """Reads raw data from a sheet directly and returns as a DataFrame."""
        if self.use_google:
            try:
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{sheet_name}'!A:Z"
                ).execute()
                rows = result.get("values", [])
                if not rows:
                    return pd.DataFrame()
                
                header = rows[0]
                cleaned_rows = []
                for row in rows[1:]:
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    elif len(row) > len(header):
                        row = row[:len(header)]
                    cleaned_rows.append(row)
                
                return pd.DataFrame(cleaned_rows, columns=header)
            except Exception as e:
                logger.error(f"Google API error in read_sheet_data for {sheet_name}: {e}")
                return pd.DataFrame()
        
        # Local Excel
        if not os.path.exists(LOCAL_FILE):
            return pd.DataFrame()
        xls = pd.ExcelFile(LOCAL_FILE)
        if sheet_name not in xls.sheet_names:
            return pd.DataFrame()
        try:
            return pd.read_excel(LOCAL_FILE, sheet_name=sheet_name)
        except Exception as e:
            logger.error(f"Error reading local Excel sheet {sheet_name}: {e}")
            return pd.DataFrame()

    def _init_analytics_sheet(self):
        """Ensure 'analytics' (lowercase) tab exists."""
        if not self.use_google:
            return
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_names = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]
            
            exists = any(s.lower() == "analytics" for s in sheet_names)
            if not exists:
                body = {
                    "requests": [{"addSheet": {"properties": {"title": "analytics"}}}]
                }
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id, body=body
                ).execute()
        except HttpError as err:
            logger.error(f"Google API error in _init_analytics_sheet: {err}")
            raise err

    def write_to_analytics_tab(self, rows: list[list]) -> bool:
        """Writes data rows to the 'analytics' tab, clearing it first."""
        if self.use_google:
            try:
                self._init_analytics_sheet()
                sheet_names = self.get_all_sheet_names()
                actual_name = next((s for s in sheet_names if s.lower() == "analytics"), "analytics")
                
                # Clear and write new analytics
                self.service.spreadsheets().values().clear(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{actual_name}'!A1:Z1000"
                ).execute()
                
                if rows:
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.spreadsheet_id,
                        range=f"'{actual_name}'!A1",
                        valueInputOption="USER_ENTERED",
                        body={"values": rows}
                    ).execute()
                return True
            except Exception as e:
                logger.error(f"Google API error writing to analytics tab: {e}")
                raise e
                
        # Local Excel
        if not rows:
            df = pd.DataFrame()
        else:
            max_cols = max(len(row) for row in rows)
            padded_rows = [row + [""] * (max_cols - len(row)) for row in rows]
            df = pd.DataFrame(padded_rows)
            
        if not os.path.exists(LOCAL_FILE):
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="analytics", index=False, header=False)
            return True
            
        xls = pd.ExcelFile(LOCAL_FILE)
        sheets = {}
        for name in xls.sheet_names:
            if name == "analytics":
                sheets[name] = df
            else:
                sheets[name] = pd.read_excel(xls, name)
        
        if "analytics" not in sheets:
            sheets["analytics"] = df
            
        with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
            for name, d in sheets.items():
                d.to_excel(writer, sheet_name=name, index=False, header=(name != "analytics"))
        return True

    def read_settings_sheet(self) -> pd.DataFrame:
        """Read the 'settings' sheet. Returns DataFrame with columns ['type', 'name', 'keywords', 'active']."""
        headers = ["type", "name", "keywords", "active"]
        if self.use_google:
            try:
                actual_name = self._init_new_google_sheet("settings", headers)
                df = self.read_sheet_data(actual_name)
                if df.empty:
                    return pd.DataFrame(columns=headers)
                df.columns = [str(c).strip().lower() for c in df.columns]
                for col in headers:
                    if col not in df.columns:
                        df[col] = ""
                return df[headers]
            except Exception as e:
                logger.error(f"Error reading Google settings sheet: {e}")
                return pd.DataFrame(columns=headers)
        else:
            actual_name = self._init_new_local_sheet("settings", headers)
            try:
                df = pd.read_excel(LOCAL_FILE, sheet_name=actual_name)
                if df.empty:
                    return pd.DataFrame(columns=headers)
                df.columns = [str(c).strip().lower() for c in df.columns]
                for col in headers:
                    if col not in df.columns:
                        df[col] = ""
                return df[headers]
            except Exception as e:
                logger.error(f"Error reading local settings sheet: {e}")
                return pd.DataFrame(columns=headers)

    def write_settings_sheet(self, df: pd.DataFrame) -> bool:
        """Overwrite the 'settings' sheet with the given DataFrame."""
        headers = ["type", "name", "keywords", "active"]
        for col in headers:
            if col not in df.columns:
                df[col] = ""
        df = df[headers].copy()
        
        if self.use_google:
            try:
                actual_name = self._init_new_google_sheet("settings", headers)
                self.service.spreadsheets().values().clear(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{actual_name}'!A1:Z1000"
                ).execute()
                
                # Convert values to clean serializable types
                clean_values = []
                for row in df.values.tolist():
                    clean_row = [str(item) if not pd.isna(item) else "" for item in row]
                    clean_values.append(clean_row)
                    
                rows = [headers] + clean_values
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"'{actual_name}'!A1",
                    valueInputOption="USER_ENTERED",
                    body={"values": rows}
                ).execute()
                self._invalidate_cache()
                return True
            except Exception as e:
                logger.error(f"Error writing Google settings sheet: {e}")
                raise e
        else:
            actual_name = self._init_new_local_sheet("settings", headers)
            xls = pd.ExcelFile(LOCAL_FILE)
            sheets = {}
            for name in xls.sheet_names:
                if name == actual_name:
                    sheets[name] = df
                else:
                    sheets[name] = pd.read_excel(xls, name)
            
            if actual_name not in sheets:
                sheets[actual_name] = df
                
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                for name, d in sheets.items():
                    d.to_excel(writer, sheet_name=name, index=False, header=(name != "analytics"))
            self._invalidate_cache()
            return True

# Single shared instance
sheets_handler = SheetsHandler()
