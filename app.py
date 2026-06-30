# app.py

import os
import logging
from dotenv import load_dotenv
load_dotenv(override=True)

logger = logging.getLogger(__name__)

import streamlit as st
import pandas as pd
from datetime import datetime

# Import skills and utilities
from utils.categories import (
    CATEGORIES, BUDGET_LIMITS, load_categories_from_sheets, 
    add_category, delete_category, update_category_keywords, 
    count_transactions_with_category
)
from utils.sheets_handler import sheets_handler, get_friendly_error_message
from skills.text_parser import parse_text, clarify_pending_transaction, generate_general_response
from skills.classifier import classify_transaction
from skills.sheets_writer import write_to_sheets
from skills.analytics import generate_analytics, write_analytics_to_sheets, ENGLISH_MONTHS
from skills.correction import correct_transaction
from skills.pdf_parsing_skill import parse_pdf, parse_image

# Page configuration
st.set_page_config(
    page_title="FamilyBudget AI Assistant",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom styling for premium wowed aesthetics
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Container padding and max-width */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 4rem !important;
        padding-right: 4rem !important;
        max-width: 1400px !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0.5rem !important;
    }
    
    /* Default image rendering inside containers */
    div[data-testid="stImage"] img {
        width: 100% !important;
        display: block !important;
    }
    
    /* Premium background gradient for the main content area */
    .stApp {
        background: radial-gradient(circle at 80% 20%, #f3faf6 0%, #e5ede7 100%) !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        color: #0b1a11 !important;
        letter-spacing: -0.5px !important;
        margin-top: 0.2rem !important;
        margin-bottom: 0.4rem !important;
    }
    
    /* Custom Sidebar styling matching rich dark forest green */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0B291A 0%, #071E13 100%) !important;
        border-right: 1px solid rgba(0, 230, 118, 0.12) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #d0e5d5;
    }
    .sidebar-logo-title {
        color: #00E676 !important;
        font-size: 1.6rem !important;
        font-weight: 800 !important;
        font-family: 'Outfit', sans-serif !important;
        margin: 0 !important;
        line-height: 1.1 !important;
        letter-spacing: -0.5px !important;
    }
    
    /* Hide the radio button label & circles & style option items */
    div[data-testid="stRadio"] label[data-testid="stWidgetLabel"] {
        display: none !important;
    }
    div[data-testid="stRadio"] > div {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    div[data-testid="stRadio"] label {
        background: transparent !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 10px 14px !important;
        margin-bottom: 6px !important;
        color: #d0e5d5 !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
    }
    div[data-testid="stRadio"] label:hover {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff !important;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        background: #00E676 !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(0, 230, 118, 0.25) !important;
    }
    div[data-testid="stRadio"] label:has(input:checked) * {
        color: #041F10 !important;
        font-weight: 700 !important;
    }
    div[data-testid="stRadio"] label > div:first-of-type {
        display: none !important;
    }
    div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] {
        padding-left: 0 !important;
    }
    
    /* Main area selectboxes styling (clean light-themed look) */
    section.main div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1px solid rgba(0, 135, 90, 0.15) !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    section.main div[data-testid="stSelectbox"] div[role="button"], 
    section.main div[data-testid="stSelectbox"] [data-baseweb="select"] * {
        color: #0b1a11 !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
    }
    section.main div[data-testid="stSelectbox"] svg {
        fill: #00875a !important;
    }
    section.main div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {
        border-color: #00875a !important;
    }
    section.main div[data-testid="stSelectbox"] label {
        color: #5C7F67 !important;
    }
    
    /* Sidebar Selectbox Custom Card Styling */
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] {
        background-color: rgba(255, 255, 255, 0.04) !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        margin-bottom: 16px !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] label[data-testid="stWidgetLabel"] {
        display: block !important;
        font-size: 0.72rem !important;
        color: #5C7F67 !important;
        font-weight: 500 !important;
        margin-bottom: 2px !important;
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        height: auto !important;
        min-height: 0 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] [data-baseweb="select"] * {
        color: #00E676 !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] svg {
        fill: #00E676 !important;
    }
    
    /* Custom Card Containers */
    .glass-card {
        background: rgba(255, 255, 255, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(0, 135, 90, 0.1) !important;
        padding: 24px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 135, 90, 0.05) !important;
        margin-bottom: 20px !important;
    }
    
    /* Chat styling */
    .chat-bubble {
        padding: 14px 18px;
        border-radius: 18px;
        margin-bottom: 12px;
        max-width: 85%;
        line-height: 1.5;
        font-size: 0.95rem;
    }
    .user-bubble {
        background: linear-gradient(135deg, #1B2A4A, #2A3F6D);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 4px;
        box-shadow: 0 4px 12px rgba(27, 42, 74, 0.15);
    }
    .agent-bubble {
        background: white;
        color: #1b2e23;
        margin-right: auto;
        border-bottom-left-radius: 4px;
        border: 1px solid rgba(0, 135, 90, 0.12);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
    }
    
    /* Form input styling */
    .stTextInput input {
        border-radius: 12px !important;
        padding: 12px !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.2s ease !important;
    }
    .stTextInput input:focus {
        border-color: #00875A !important;
        box-shadow: 0 0 0 2px rgba(0, 135, 90, 0.15) !important;
        background-color: #ffffff !important;
    }

    /* Hide Streamlit form helper text */
    [data-testid="InputInstructions"], 
    [data-testid="stForm"] [data-testid="stMarkdownContainer"] small,
    [data-testid="stForm"] small,
    [data-testid="stFormSubmitButton"] + div,
    div:has(> [data-testid="stFormSubmitButton"]) + div {
        display: none !important;
    }

    /* Modebar container */
    .modebar-container {
        background: rgba(255, 255, 255, 0.7) !important;
        backdrop-filter: blur(8px) !important;
        border-radius: 8px !important;
        border: 1px solid rgba(27, 42, 74, 0.1) !important;
        padding: 2px 4px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    }

    /* Individual buttons */
    .modebar-btn path {
        fill: #1B2A4A !important;
    }
    .modebar-btn:hover path {
        fill: #2E7D32 !important;
    }
    .modebar-btn.active path {
        fill: #2E7D32 !important;
    }
</style>
""", unsafe_allow_html=True)

def section_title(icon, title, subtitle=""):
    sub_html = f"<div style='font-size: 13px; color: #6B7280; font-weight: 400; margin-top: 2px;'>{subtitle}</div>" if subtitle else ""
    st.markdown(f"""
    <div style='margin-bottom: 1.2rem; margin-top: 1.5rem;'>
        <div style='font-size: 18px; font-weight: 700; color: #1B2A4A; display: flex; align-items: center; gap: 8px;'>
            <span>{icon}</span> <span>{title}</span>
        </div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)

# Helper: Load mock data if file does not exist
def seed_mock_data():
    if sheets_handler.use_google:
        return
    if not os.path.exists("family_budget_data.xlsx"):
        try:
            tx_data = [
                {"date": "2026-06-01", "type": "income", "person": "katja", "merchant": "Employer Inc.", "amount": 2800.0, "category": "Salary", "subcategory": "Salary", "source": "manual", "note": "Monthly Salary"},
                {"date": "2026-06-01", "type": "income", "person": "dirk", "merchant": "Tech AG", "amount": 3342.50, "category": "Salary", "subcategory": "Salary", "source": "manual", "note": "Monthly Salary"},
                {"date": "2026-06-02", "type": "expense", "person": "shared", "merchant": "Property Management", "amount": 1100.0, "category": "Housing", "subcategory": "Rent", "source": "manual"},
                {"date": "2026-06-03", "type": "expense", "person": "shared", "merchant": "Power Utilities", "amount": 180.0, "category": "Utilities", "subcategory": "Power/Gas", "source": "manual"},
                {"date": "2026-06-05", "type": "expense", "person": "shared", "merchant": "Lidl", "amount": 84.30, "category": "Groceries", "subcategory": "Supermarket", "source": "manual"},
                {"date": "2026-06-08", "type": "expense", "person": "shared", "merchant": "dm drugstore", "amount": 24.15, "category": "Drugstore", "subcategory": "Drugstore Supplies", "source": "manual"},
                {"date": "2026-06-10", "type": "expense", "person": "shared", "merchant": "Shell Gas Station", "amount": 75.0, "category": "Fuel", "subcategory": "Gasoline", "source": "manual"},
                {"date": "2026-06-12", "type": "expense", "person": "shared", "merchant": "Netflix", "amount": 17.99, "category": "Streaming & Media", "subcategory": "Streaming", "source": "manual"},
                {"date": "2026-06-15", "type": "expense", "person": "shared", "merchant": "Rewe", "amount": 42.10, "category": "Groceries", "subcategory": "Supermarket", "source": "manual"},
                {"date": "2026-06-20", "type": "savings", "person": "katja", "merchant": "Trade Republic", "amount": 300.0, "category": "Investments (Savings Plans)", "subcategory": "ETF", "source": "manual", "note": "Monthly Salary"},
                {"date": "2026-06-20", "type": "savings", "person": "dirk", "merchant": "Allianz", "amount": 200.0, "category": "Retirement", "subcategory": "Pension", "source": "manual"}
            ]
            for tx in tx_data:
                sheets_handler.add_transaction(tx)
                
            tx_data_may = [
                {"date": "2026-05-01", "type": "income", "person": "katja", "merchant": "Employer Inc.", "amount": 2800.0, "category": "Salary", "subcategory": "Salary", "source": "manual"},
                {"date": "2026-05-01", "type": "income", "person": "dirk", "merchant": "Tech AG", "amount": 3342.50, "category": "Salary", "subcategory": "Salary", "source": "manual"},
                {"date": "2026-05-02", "type": "expense", "person": "shared", "merchant": "Property Management", "amount": 1100.0, "category": "Housing", "subcategory": "Rent", "source": "manual"},
                {"date": "2026-05-05", "type": "expense", "person": "shared", "merchant": "Lidl", "amount": 91.50, "category": "Groceries", "subcategory": "Supermarket", "source": "manual"},
                {"date": "2026-05-08", "type": "expense", "person": "shared", "merchant": "dm drugstore", "amount": 32.80, "category": "Drugstore", "subcategory": "Drugstore Supplies", "source": "manual"},
                {"date": "2026-05-10", "type": "expense", "person": "shared", "merchant": "Shell Gas Station", "amount": 73.50, "category": "Fuel", "subcategory": "Gasoline", "source": "manual"},
                {"date": "2026-05-15", "type": "expense", "person": "shared", "merchant": "Pizzeria Napoli", "amount": 42.00, "category": "Dining Out", "subcategory": "Dining Out", "source": "manual"}
            ]
            for tx in tx_data_may:
                sheets_handler.add_transaction(tx)
        except Exception as e:
            logger.error(f"Failed to seed mock data: {e}")

seed_mock_data()

# Initialize session state variables
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "agent", "text": "Hello! I am your **FamilyBudget AI Assistant**. How can I help you today?"}
    ]
if "pending_tx" not in st.session_state:
    st.session_state.pending_tx = None
if "waiting_for" not in st.session_state:
    st.session_state.waiting_for = None
if "pending_correction" not in st.session_state:
    st.session_state.pending_correction = None
if "pending_pdf_txs" not in st.session_state:
    st.session_state.pending_pdf_txs = []
if "menu_selection" not in st.session_state:
    st.session_state.menu_selection = "💬 Chat Assistant"

# --- Google Sheets Active Verification check ---
is_sheet_accessible = False
sheet_error_detail = None
if sheets_handler.use_google:
    try:
        sheets_handler.service.spreadsheets().get(spreadsheetId=sheets_handler.spreadsheet_id).execute()
        is_sheet_accessible = True
    except Exception as e:
        sheet_error_detail = str(e)
        is_sheet_accessible = False

# --- Sidebar Navigation & User Info ---
st.sidebar.markdown("""
<div style='text-align: left; margin-bottom: 16px; margin-top: 5px; padding-left: 2px;'>
    <div style='font-size: 1.6rem; margin-bottom: 4px;'>💰</div>
    <div class='sidebar-logo-title'>FamilyBudget.ai</div>
    <div style='font-size: 0.65rem; color: #5C7F67; letter-spacing: 1.5px; text-transform: uppercase; font-weight: 700; margin-top: 4px;'>FINANCIAL ASSISTANT</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<hr style='border:none; border-top:1px solid rgba(255,255,255,0.08); margin:14px 0;'>", unsafe_allow_html=True)

st.sidebar.markdown("<p style='font-size:11px; color:#5C7F67; letter-spacing:0.12em; font-weight:700; margin-bottom:6px; text-transform:uppercase;'>ACCOUNT</p>", unsafe_allow_html=True)

current_user = st.sidebar.selectbox(
    "ACTIVE ACCOUNT",
    ["Katja", "Dirk"],
    key="active_user_select"
)
st.session_state.current_user = current_user.lower()

english_months = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
now_dt = datetime.now().date()
current_month_str_en = f"{english_months.get(now_dt.month, now_dt.strftime('%B'))} {now_dt.year}"

st.sidebar.markdown(f"""
<div style='background: rgba(255, 255, 255, 0.04); border-radius: 10px; padding: 8px 12px; margin-bottom: 16px;'>
    <div style='font-size: 0.72rem; color: #5C7F67; font-weight: 500; margin-bottom: 2px;'>Current Month</div>
    <div style='color:#00E676; font-weight:700; font-size:0.95rem; font-family: "Outfit", sans-serif;'>{current_month_str_en}</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<p style='font-size:11px; color:#5C7F67; letter-spacing:0.12em; font-weight:700; margin-bottom:6px; text-transform:uppercase;'>MENU</p>", unsafe_allow_html=True)

MENU_OPTIONS = ["💬 Chat Assistant", "📊 Analytics", "📄 Document Upload", "⚙️ Settings"]

if "sidebar_radio" in st.session_state and st.session_state.sidebar_radio != st.session_state.menu_selection:
    st.session_state.menu_selection = st.session_state.sidebar_radio

try:
    default_menu_idx = MENU_OPTIONS.index(st.session_state.menu_selection)
except ValueError:
    default_menu_idx = 0

menu = st.sidebar.radio(
    "MENU",
    MENU_OPTIONS,
    index=default_menu_idx,
    key="sidebar_radio"
)
st.session_state.menu_selection = menu

st.sidebar.markdown("<div style='margin-top: 40px;'></div>", unsafe_allow_html=True)
if sheets_handler.use_google:
    if is_sheet_accessible:
        status_color = "#00E676"
        status_text = "Connected"
        status_icon = "●"
    else:
        status_color = "#EF5350"
        status_text = "Error"
        status_icon = "○"
    sheets_label = f"Google Sheets · {status_text}"
else:
    status_color = "#F1C40F"
    status_text = "Local Mode (Excel)"
    status_icon = "●"
    sheets_label = status_text

st.sidebar.markdown(f"""
<div style='padding-top: 12px; margin-top: 12px;'>
    <span style='color:{status_color}; font-size:10px;'>{status_icon}</span>
    <span style='color:#5C7F67; font-size:11px;'> {sheets_label}</span>
</div>
""", unsafe_allow_html=True)

# --- Content Sections ---

if menu == "💬 Chat Assistant":
    if os.path.exists("banner.png") and len(st.session_state.get("chat_history", [])) <= 1:
        st.markdown("""
            <div style="border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.12); margin-bottom: 2rem;">
        """, unsafe_allow_html=True)
        st.image("banner.png", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("## 💬 Chat Assistant")
    st.write("Manage your family budget conversationally. Log expenses via text, correct transactions, or ask for budget analytics.")

    def process_and_check_transaction(tx):
        if tx.get("type") in ["income", "savings"] and tx.get("person") == "unknown":
            tx["person"] = st.session_state.get("current_user", "shared")

        if not tx.get("merchant_specified") or tx.get("merchant", "Unknown") in ["Unknown", "Unbekannt"]:
            st.session_state.pending_tx = tx
            st.session_state.waiting_for = "merchant"
            st.session_state.chat_history.append({
                "role": "agent",
                "text": "❓ Which merchant or source should I record this transaction for? (Reply in chat or type 'cancel')"
            })
            st.rerun()

        if not tx.get("amount_specified") or tx.get("amount", 0.0) <= 0.0:
            st.session_state.pending_tx = tx
            st.session_state.waiting_for = "amount"
            st.session_state.chat_history.append({
                "role": "agent",
                "text": f"❓ What was the amount for **{tx['merchant']}**? (Reply in chat or type 'cancel')"
            })
            st.rerun()

        if not tx.get("date_specified"):
            st.session_state.pending_tx = tx
            st.session_state.waiting_for = "date"
            st.session_state.chat_history.append({
                "role": "agent",
                "text": f"📅 Which month (e.g. May) or date should I record the transaction for **{tx['merchant']}** of **€{tx['amount']:.2f}**?\n"
                        f"*(Reply in chat or type 'cancel'. Default is today: {tx['date']})*"
            })
            st.rerun()

        is_cat_unclear = tx.get("confidence", 1.0) < 0.8 or tx.get("category", "Unknown") in ["Unknown", "Unbekannt"]
        
        if is_cat_unclear and st.session_state.waiting_for != "category":
            with st.spinner("Classifying category..."):
                classification = classify_transaction(
                    tx.get("merchant"), 
                    tx.get("amount"), 
                    category_hint=tx.get("category_hint"),
                    tx_type=tx.get("type")
                )
                tx["category"] = classification["category"]
                tx["subcategory"] = classification["subcategory"]
                tx["confidence"] = classification["confidence"]
            
            if tx["confidence"] < 0.8 or tx["category"] in ["Unknown", "Unbekannt"]:
                st.session_state.pending_tx = tx
                st.session_state.waiting_for = "category"
                confirm_prompt = f"❓ I detected the following details:\n\n" \
                                 f"**Merchant/Source:** {tx['merchant']}\n" \
                                 f"**Amount:** €{tx['amount']:.2f}\n" \
                                 f"**Date:** {tx['date']}\n" \
                                 f"**Category:** {tx['category']} (Confidence: {tx['confidence']:.2f})\n\n" \
                                 f"Please confirm the category or select another:"
                st.session_state.chat_history.append({
                    "role": "agent", 
                    "text": confirm_prompt,
                    "needs_confirmation": True
                })
                st.rerun()

        with st.spinner("Saving transaction..."):
            res_msg = write_to_sheets(tx)
        st.session_state.chat_history.append({"role": "agent", "text": res_msg})
        st.session_state.pending_tx = None
        st.session_state.waiting_for = None
        st.rerun()

    chat_container = st.container()
    with chat_container:
        for idx, chat in enumerate(st.session_state.chat_history):
            role_class = "user-bubble" if chat["role"] == "user" else "agent-bubble"
            st.markdown(f'<div class="chat-bubble {role_class}">{chat["text"]}</div>', unsafe_allow_html=True)
            
            if idx == len(st.session_state.chat_history) - 1:
                if st.session_state.pending_tx and chat.get("needs_confirmation"):
                    tx = st.session_state.pending_tx
                    st.write("---")
                    st.warning(f"Category confirmation required for: **{tx['merchant']}** | **€{tx['amount']:.2f}**")
                    
                    parsed_date = datetime.strptime(tx.get("date", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
                    cols_date = st.columns(2)
                    with cols_date[0]:
                        new_date = st.date_input("Adjust Date / Month for transaction:", value=parsed_date)
                        tx["date"] = new_date.strftime("%Y-%m-%d")
                    
                    tx_type = tx.get("type", "expense")
                    options = []
                    if tx_type == "expense":
                        options = CATEGORIES["expense"]["Variable Costs"] + CATEGORIES["expense"]["Fixed Costs"]
                    elif tx_type == "income":
                        options = CATEGORIES["income"]["Income"]
                    elif tx_type == "savings":
                        options = CATEGORIES["savings"]["Savings"]
                    
                    suggested = tx.get("category", "Unknown")
                    
                    cols = st.columns(4)
                    for c_idx, opt in enumerate(options[:12]):
                        with cols[c_idx % 4]:
                            label = f"⭐ {opt}" if opt == suggested else opt
                            if st.button(label, key=f"confirm_btn_{c_idx}"):
                                tx["category"] = opt
                                tx["subcategory"] = "-"
                                with st.spinner("Writing to spreadsheet..."):
                                    res_msg = write_to_sheets(tx)
                                st.session_state.chat_history.append({"role": "agent", "text": res_msg})
                                st.session_state.pending_tx = None
                                st.session_state.waiting_for = None
                                st.rerun()

                if st.session_state.pending_correction and chat.get("needs_disambiguation"):
                    disambig = st.session_state.pending_correction
                    st.write("---")
                    st.info("Please select the transaction to modify:")
                    cols = st.columns(len(disambig["matches"]))
                    for m_idx, match in enumerate(disambig["matches"]):
                        with cols[m_idx]:
                            btn_label = f"{match['merchant']} (€{match['amount']:.2f} on {match['date']})"
                            if st.button(btn_label, key=f"disambig_btn_{m_idx}"):
                                success = sheets_handler.update_transaction(
                                    match["date"], match["merchant"], match["amount"], disambig["new_category"]
                                )
                                if success:
                                    success_msg = f"✅ Corrected:\n**{match['merchant']}** | {match['date']} | €{match['amount']:.2f} → Category updated to **{disambig['new_category']}**"
                                    st.session_state.chat_history.append({"role": "agent", "text": success_msg})
                                else:
                                    st.session_state.chat_history.append({"role": "agent", "text": "❌ Error updating row in spreadsheet."})
                                st.session_state.pending_correction = None
                                st.rerun()

    if len(st.session_state.chat_history) == 1:
        st.write("")
        st.markdown("<p style='font-size: 0.75rem; font-weight: 700; color: #486352; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;'>Quick Actions:</p>", unsafe_allow_html=True)
        cols_quick = st.columns(3)
        quick_actions = [
            ("📝 Lidl €14.50", "Spent €14.50 today at Lidl"),
            ("📊 June Analytics", "Show me the analytics for June 2026"),
            ("💡 Check Budget", "What is my budget status for this month?")
        ]
        for q_idx, (label, cmd_text) in enumerate(quick_actions):
            with cols_quick[q_idx]:
                if st.button(label, key=f"quick_act_{q_idx}", use_container_width=True):
                    st.session_state.run_chat_query = cmd_text
                    st.session_state.chat_history.append({"role": "user", "text": cmd_text})
                    st.rerun()

    st.write("")
    with st.form("chat_form", clear_on_submit=True):
        chat_cols = st.columns([8.5, 1.5])
        with chat_cols[0]:
            user_input = st.text_input(
                "Enter message...", 
                placeholder="e.g. 'Spent €23.50 today at Lidl'...", 
                label_visibility="collapsed"
            )
        with chat_cols[1]:
            submitted = st.form_submit_button("Send", use_container_width=True)

    query_text = ""
    if submitted and user_input.strip():
        query_text = user_input.strip()
        st.session_state.chat_history.append({"role": "user", "text": query_text})
    elif "run_chat_query" in st.session_state:
        query_text = st.session_state.pop("run_chat_query")

    if query_text:
        user_input_lower = query_text.lower().strip()
        
        is_cancel = user_input_lower in ["cancel", "abbrechen", "stop", "no", "stornieren"]
        is_correction = "correct" in user_input_lower or "korrigiere" in user_input_lower or "change" in user_input_lower or "modify" in user_input_lower
        is_analytics = "analytics" in user_input_lower or "auswertung" in user_input_lower or "analysis" in user_input_lower or "trend" in user_input_lower

        try:
            if is_cancel:
                st.session_state.pending_tx = None
                st.session_state.waiting_for = None
                st.session_state.chat_history.append({
                    "role": "agent",
                    "text": "Operation canceled. How else can I assist you?"
                })
                st.rerun()

            elif is_correction:
                st.session_state.pending_tx = None
                st.session_state.waiting_for = None
                with st.spinner("Searching for transaction to correct..."):
                    result = correct_transaction(query_text)
                
                if result["status"] == "success":
                    st.session_state.chat_history.append({"role": "agent", "text": result["message"]})
                elif result["status"] == "disambiguate":
                    st.session_state.pending_correction = {
                        "matches": result["matches"],
                        "new_category": result["new_category"]
                    }
                    st.session_state.chat_history.append({
                        "role": "agent", 
                        "text": result["message"],
                        "needs_disambiguation": True
                    })
                else:
                    st.session_state.chat_history.append({"role": "agent", "text": result["message"]})
                st.rerun()

            elif is_analytics:
                st.session_state.pending_tx = None
                st.session_state.waiting_for = None
                target_month = None
                months_mapping = {
                    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
                    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"
                }
                for en_m, m_num in months_mapping.items():
                    if en_m in user_input_lower:
                        target_month = f"2026-{m_num}"
                        break
                
                with st.spinner("Calculating monthly analytics..."):
                    summary_text, _ = generate_analytics(target_month)
                st.session_state.chat_history.append({"role": "agent", "text": summary_text})
                st.rerun()

            elif st.session_state.pending_tx and st.session_state.waiting_for:
                with st.spinner("Processing your answer..."):
                    updated_tx = clarify_pending_transaction(st.session_state.pending_tx, query_text)
                    st.session_state.pending_tx = updated_tx
                process_and_check_transaction(updated_tx)

            else:
                with st.spinner("Analyzing financial text..."):
                    tx = parse_text(query_text)
                
                if tx.get("is_transaction"):
                    process_and_check_transaction(tx)
                else:
                    with st.spinner("Generating response..."):
                        gen_resp = generate_general_response(query_text)
                    st.session_state.chat_history.append({"role": "agent", "text": gen_resp})
                    st.rerun()

        except Exception as err:
            logger.error("Error in chat processing", exc_info=True)
            friendly_err = get_friendly_error_message(err)
            st.session_state.chat_history.append({
                "role": "agent",
                "text": f"❌ Error during processing: {friendly_err}"
            })
            st.rerun()

elif menu == "📊 Analytics":
    st.markdown("## 📊 Analytics")
    st.write("Analyze your family budget. Compare income, expenses, and savings over the year or in detail.")
    
    try:
        if "analytics_results" not in st.session_state or st.session_state.get("analytics_dirty", True):
            with st.spinner("Calculating analytics from spreadsheet data..."):
                sheet_names = sheets_handler.get_all_sheet_names()
                sheet_data = {}
                for name in sheet_names:
                    if any(w in name.lower() for w in ["expenses", "income", "savings", "ausgaben", "einnahmen", "ersparnisse"]):
                        df = sheets_handler.read_sheet_data(name)
                        sheet_data[name] = df
                        
                from skills.analytics import generate_analytics, write_analytics_to_sheets, ENGLISH_MONTHS
                analytics_results = generate_analytics(sheet_data)
                st.session_state.analytics_results = analytics_results
                st.session_state.analytics_dirty = False
                
                try:
                    write_analytics_to_sheets(analytics_results)
                except Exception as e:
                    logger.error(f"Error writing analytics back to sheets: {e}")
        else:
            analytics_results = st.session_state.analytics_results
            from skills.analytics import ENGLISH_MONTHS
            
        import plotly.graph_objects as go

        def section_title(icon: str, text: str, subtitle: str = ""):
            st.markdown(f"""
                <div style='margin-bottom: 4px;'>
                    <span style='font-size:18px; font-weight:700; color:#1B2A4A;'>
                        {icon}&nbsp;&nbsp;{text}
                    </span>
                </div>
                {"<p style='font-size:13px; color:#6B7280; margin-top:0;'>" + subtitle + "</p>" if subtitle else ""}
            """, unsafe_allow_html=True)

        def format_currency_en(val: float) -> str:
            sign = "-" if val < 0 else ""
            abs_val = abs(val)
            return f"{sign}€{abs_val:,.2f}"
            
        def color_bilanz(val):
            color = "#00875a" if val >= 0 else "#d97706"
            return f"color: {color}; font-weight: bold;"

        # --- Section 1: Annual Overview ---
        col_hdr1, col_hdr2 = st.columns([7.5, 2.5])
        with col_hdr1:
            section_title("▦", "Annual Overview")
        with col_hdr2:
            if st.button("Reload Data 🔄", key="ref_analytics_btn", use_container_width=True):
                st.session_state.analytics_dirty = True
                st.rerun()
        
        summary_table_rows = analytics_results["summary_table"]
        
        if not summary_table_rows:
            st.warning("No data available for annual overview.")
        else:
            df_summary = pd.DataFrame(summary_table_rows)
            if "_month_key" in df_summary.columns:
                df_summary = df_summary.drop(columns=["_month_key"])
                
            df_display = df_summary.copy()
            for col_name in ["Income", "Expenses", "Savings", "Net Balance", "Einnahmen", "Ausgaben", "Ersparnisse", "Bilanz"]:
                if col_name in df_display.columns:
                    df_display[col_name] = df_display[col_name].apply(format_currency_en)
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("---")

        # --- Section 2: Donut Chart ---
        expenses_by_category = analytics_results["expenses_by_category"]
        current_month_str = analytics_results.get("current_month", "Unknown")
        parts = current_month_str.split("-")
        month_name = ENGLISH_MONTHS.get(parts[1], parts[1]) if len(parts) > 1 else parts[0]
        year_str = parts[0] if len(parts) > 0 else ""
        current_month_display = f"{month_name} {year_str}".strip()
        
        CHART_COLORS = [
            "#1B2A4A", "#2E7D32", "#388E3C", "#43A047", 
            "#66BB6A", "#81C784", "#A5D6A7", "#C8E6C9", 
            "#B0BEC5", "#90A4AE", "#78909C", "#546E7A"
        ]

        BAR_COLORS = {
            "Income":   "#2E7D32",
            "Expenses": "#1B2A4A",
            "Savings":  "#81C784",
        }

        section_title("◉", "Expenses by Category", f"Category breakdown for {current_month_display}")
        if not expenses_by_category:
            st.info(f"No category expenses recorded for {current_month_display}.")
        else:
            sorted_exp = sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)
            labels = [k for k, v in sorted_exp]
            values = [v for k, v in sorted_exp]
            total_val = sum(values) if sum(values) > 0 else 1.0
            
            legend_labels = [f"{lbl} ({format_currency_en(val)})" for lbl, val in zip(labels, values)]
            slice_colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(values))]
            text_templates = ["%{percent:.1%}" if (v / total_val) >= 0.03 else "" for v in values]
            
            fig_pie = go.Figure(data=[go.Pie(
                labels=legend_labels,
                values=values,
                hole=0.45,
                textposition='inside',
                textinfo='percent',
                texttemplate=text_templates,
                textfont=dict(size=11, color="white"),
                insidetextorientation="auto",
                marker=dict(colors=slice_colors),
                hovertemplate="<b>%{label}</b><br>Amount: €%{value:,.2f}<br>Share: %{percent}<extra></extra>"
            )])
            fig_pie.update_layout(
                height=420,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#1B2A4A", family="Inter, Helvetica, sans-serif", size=13),
                margin=dict(t=20, b=20, l=20, r=20),
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.02,
                    bgcolor="rgba(0,0,0,0)",
                    borderwidth=0,
                    font=dict(color="#1B2A4A", size=12),
                ),
            )
            st.plotly_chart(
                fig_pie,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": [
                        "select2d", "lasso2d", "autoScale2d",
                        "hoverClosestCartesian", "hoverCompareCartesian",
                        "toggleSpikelines", "zoom2d", "zoomIn2d", "zoomOut2d",
                    ],
                    "modeBarButtonsToAdd": [],
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "expenses_by_category",
                        "scale": 2,
                    },
                }
            )

        st.markdown("<div style='margin: 1.5rem 0'></div>", unsafe_allow_html=True)
        st.markdown("---")

        # --- Section 3: Bar Chart ---
        section_title("↗", "Monthly Trend", "Income, Expenses & Savings Comparison")
        if not summary_table_rows:
            st.info("No trend data available for bar chart.")
        else:
            ALL_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            row_by_m = {}
            for row in summary_table_rows:
                m_key = row.get("_month_key", "")
                if m_key and "-" in m_key:
                    try:
                        m_idx = int(m_key.split("-")[1])
                        row_by_m[m_idx] = row
                    except ValueError:
                        pass
                else:
                    for idx_m, (m_num_str, m_full_name) in enumerate(ENGLISH_MONTHS.items(), start=1):
                        m_val = row.get("Month", row.get("Monat", ""))
                        if m_full_name.lower() == str(m_val).lower():
                            row_by_m[idx_m] = row
                            break

            months_list = ALL_MONTHS
            incomes = [float(row_by_m.get(i, {}).get("Income", row_by_m.get(i, {}).get("Einnahmen", 0.0))) for i in range(1, 13)]
            expenses = [float(row_by_m.get(i, {}).get("Expenses", row_by_m.get(i, {}).get("Ausgaben", 0.0))) for i in range(1, 13)]
            savings = [float(row_by_m.get(i, {}).get("Savings", row_by_m.get(i, {}).get("Ersparnisse", 0.0))) for i in range(1, 13)]
            
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=months_list,
                y=incomes,
                name="Income",
                marker_color=BAR_COLORS["Income"],
                offsetgroup=0,
                text=[f"<b>€{int(round(v)):,}" + "</b>" if v > 0 else "" for v in incomes],
                textposition="outside",
                constraintext="none",
                textfont=dict(size=14, color="#1B2A4A", family="Inter, Helvetica, sans-serif"),
                cliponaxis=False,
            ))
            fig_bar.add_trace(go.Bar(
                x=months_list,
                y=expenses,
                name="Expenses",
                marker_color=BAR_COLORS["Expenses"],
                offsetgroup=1,
                text=[f"<b>€{int(round(v)):,}" + "</b>" if v > 0 else "" for v in expenses],
                textposition="outside",
                constraintext="none",
                textfont=dict(size=14, color="#1B2A4A", family="Inter, Helvetica, sans-serif"),
                cliponaxis=False,
            ))
            fig_bar.add_trace(go.Bar(
                x=months_list,
                y=savings,
                name="Savings",
                marker_color=BAR_COLORS["Savings"],
                offsetgroup=2,
                text=[f"<b>€{int(round(v)):,}" + "</b>" if v > 0 else "" for v in savings],
                textposition="outside",
                constraintext="none",
                textfont=dict(size=14, color="#1B2A4A", family="Inter, Helvetica, sans-serif"),
                cliponaxis=False,
            ))
            
            try:
                curr_m_str = analytics_results.get("current_month", datetime.now().strftime("%Y-%m"))
                current_month_idx = int(curr_m_str.split("-")[1])
            except Exception:
                current_month_idx = datetime.now().month

            start_idx = max(0, current_month_idx - 3)
            end_idx = min(11, current_month_idx + 2)
            
            fig_bar.update_layout(
                width=1400,
                height=420,
                dragmode="pan",
                barmode="group",
                bargap=0.25,
                bargroupgap=0.08,
                uniformtext=dict(minsize=14, mode='show'),
                xaxis=dict(
                    title=None, 
                    tickfont=dict(size=12, color="#1B2A4A"), 
                    fixedrange=False,
                    range=[start_idx - 0.5, end_idx + 0.5]
                ),
                yaxis=dict(
                    title="Amount in €", 
                    tickfont=dict(color="#1B2A4A"), 
                    gridcolor="rgba(0,0,0,0.06)",
                    fixedrange=True
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#1B2A4A", family="Inter, Helvetica, sans-serif", size=13),
                margin=dict(t=70, b=80, l=60, r=40),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.18,
                    xanchor="center",
                    x=0.5,
                    bgcolor="rgba(0,0,0,0)",
                    borderwidth=0,
                    font=dict(color="#1B2A4A", size=12),
                ),
            )
            st.plotly_chart(
                fig_bar,
                use_container_width=False,
                config={
                    "scrollZoom": False,
                    "displayModeBar": False,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": [
                        "select2d", "lasso2d", "autoScale2d",
                        "hoverClosestCartesian", "hoverCompareCartesian",
                        "toggleSpikelines", "zoom2d", "zoomIn2d", "zoomOut2d",
                    ],
                    "modeBarButtonsToAdd": [],
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "monthly_trend",
                        "scale": 2,
                    },
                }
            )

        st.markdown("---")

        # --- Section 4: Month-over-Month Category Comparison ---
        section_title("⇄", "Comparison: Current Month vs. Previous Month")
        
        mom_comparison = analytics_results["mom_comparison"]
        
        if not mom_comparison:
            st.info("No data available for comparison.")
        else:
            categories = list(mom_comparison.keys())
            cols = st.columns(4)
            for idx, cat in enumerate(categories):
                data = mom_comparison[cat]
                curr_val = data["current"]
                prev_val = data["previous"]
                
                if prev_val == 0:
                    delta_text = "No Prev Month"
                    delta_color = "#9CA3AF"
                    icon_sym = "●"
                else:
                    pct = ((curr_val - prev_val) / prev_val) * 100
                    if pct > 0:
                        delta_text = f"+{pct:.1f}%"
                        delta_color = "#DC2626"
                        icon_sym = "▲"
                    elif pct < 0:
                        delta_text = f"{pct:.1f}%"
                        delta_color = "#16A34A"
                        icon_sym = "▼"
                    else:
                        delta_text = "±0%"
                        delta_color = "#6B7280"
                        icon_sym = "●"
                    
                with cols[idx % 4]:
                    card_html = f"""
                    <div style="background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid rgba(0, 135, 90, 0.15); border-radius: 16px; padding: 16px; margin-bottom: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); min-height: 135px;">
                        <div title="{cat}" style="font-size: 0.78rem; color: #1f3a29; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; line-height: 1.2; min-height: 2.2rem; display: flex; align-items: center; word-break: break-word;">
                            {cat}
                        </div>
                        <div style="font-size: 1.5rem; font-weight: 800; color: #0b1a11; margin-top: 6px; font-family: 'Outfit', sans-serif;">
                            {format_currency_en(curr_val)}
                        </div>
                        <div style="font-size: 0.8rem; margin-top: 6px; font-weight: 600; color: {delta_color};">
                            {icon_sym} {delta_text} <br><span style="color: #3b5243;">vs. prev month ({format_currency_en(prev_val)})</span>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                    
    except Exception as e:
        logger.error(f"Error loading analytics data: {e}", exc_info=True)
        st.error("❌ Could not load data. Please verify your Google Sheets connection.")
        if st.button("Go to Settings ⚙️", key="err_go_to_settings"):
            st.session_state.menu_selection = "⚙️ Settings"
            st.rerun()


elif menu == "📄 Document Upload":
    st.markdown("## 📄 Document Upload (PDF / Image)")
    st.write("Upload your bank statement as a PDF or a screenshot/image of your income or savings. The assistant automatically extracts all bookings.")
    
    uploaded_file = st.file_uploader("Select file (PDF, PNG, JPG, JPEG)...", type=["pdf", "png", "jpg", "jpeg"])
    
    st.write("")
    st.markdown("#### Optional Comment")
    user_comment = st.text_area(
        label="Note for assistant (optional)",
        placeholder=(
            "e.g. 'This is the bank statement for May 2026.' "
            "or 'The transfer of €200 is rent, not leisure.' "
            "or 'Transactions from BAKERY are always Dining Out.'"
        ),
        height=100,
        max_chars=500,
        help="Your note will be passed directly to the assistant to help ensure accurate categorization.",
    )
    
    if uploaded_file is not None:
        file_ext = uploaded_file.name.split(".")[-1].lower()
        is_pdf = file_ext == "pdf"
        
        button_label = "Analyze Document"
        
        if st.button(button_label):
            spinner_msg = "Analyzing PDF content with pdfplumber + Gemini..." if is_pdf else "Analyzing image content with Gemini Vision..."
            with st.spinner(spinner_msg):
                try:
                    file_bytes = uploaded_file.read()
                    if is_pdf:
                        parsed_txs = parse_pdf(file_bytes, context=user_comment)
                    else:
                        mime_type = f"image/{file_ext}" if file_ext in ["png", "gif"] else "image/jpeg"
                        parsed_txs = parse_image(file_bytes, mime_type, context=user_comment)
                        
                    if not parsed_txs:
                        st.error("No transactions could be identified in the document.")
                    else:
                        for i, tx in enumerate(parsed_txs):
                            tx["id"] = f"tx_{i}"
                        st.session_state.pending_pdf_txs = parsed_txs
                        if user_comment and user_comment.strip():
                            st.session_state.last_doc_comment = user_comment.strip()
                        else:
                            st.session_state.last_doc_comment = None
                        st.success(f"Successfully identified {len(parsed_txs)} transactions! Please review the categorizations below.")
                except Exception as e:
                    st.error(f"Error during document processing: {e}")

    if st.session_state.pending_pdf_txs:
        st.markdown("### 🔍 Transaction Review")
        if st.session_state.get("last_doc_comment"):
            st.info(f"ℹ️ Your note was applied: “{st.session_state.last_doc_comment}”")
        st.info("Flagged transactions (⚠️) require manual confirmation. You can adjust categories and assignments directly.")
        
        updated_txs = []
        
        for idx, tx in enumerate(st.session_state.pending_pdf_txs):
            confidence = tx.get("confidence", 1.0)
            is_low_conf = confidence < 0.8 or tx.get("category") in ["Unknown", "Unbekannt"]
            
            col1, col2, col3, col4, col5, col6 = st.columns([1.0, 2.3, 1.2, 2.5, 1.8, 0.7])
            
            with col1:
                st.write(tx.get("date"))
            with col2:
                warning_label = "⚠️ " if is_low_conf else "✅ "
                st.write(f"{warning_label}**{tx.get('merchant')}**")
            with col3:
                sign = "+" if tx.get("type") in ["income"] else "-"
                color = "#00875a" if tx.get("type") in ["income"] else "#e6b800" if tx.get("type") in ["expense"] else "#52b788"
                st.markdown(f"<span style='color:{color}; font-weight: 600;'>{sign} €{tx.get('amount'):.2f}</span>", unsafe_allow_html=True)
            with col4:
                tx_type = tx.get("type", "expense")
                if tx_type == "expense":
                    categories_list = CATEGORIES["expense"]["Variable Costs"] + CATEGORIES["expense"]["Fixed Costs"]
                elif tx_type == "income":
                    categories_list = CATEGORIES["income"]["Income"]
                else:
                    categories_list = CATEGORIES["savings"]["Savings"]
                
                cur_cat = tx.get("category", "Unknown")
                if cur_cat not in categories_list:
                    categories_list.append(cur_cat)
                    
                selected_cat = st.selectbox(
                    "Category",
                    categories_list,
                    index=categories_list.index(cur_cat),
                    key=f"pdf_cat_{tx.get('id', idx)}",
                    label_visibility="collapsed"
                )
                tx["category"] = selected_cat
            with col5:
                if tx_type in ["income", "savings"]:
                    raw_pers = tx.get("person", "unknown")
                    if raw_pers.lower() in ["shared", "gemeinsam"]:
                        cur_pers = "Shared"
                    elif raw_pers.lower() == "unknown":
                        cur_pers = "Unknown"
                    else:
                        cur_pers = raw_pers.capitalize()
                        
                    pers_list = ["Katja", "Dirk", "Shared"]
                    if cur_pers not in pers_list and cur_pers != "Unknown":
                        pers_list.append(cur_pers)
                    
                    default_idx = 0
                    if cur_pers == "Dirk":
                        default_idx = 1
                    elif cur_pers in ["Shared", "Gemeinsam"]:
                        default_idx = 2
                        
                    selected_pers = st.selectbox(
                        "Person",
                        pers_list,
                        index=default_idx,
                        key=f"pdf_pers_{tx.get('id', idx)}",
                        label_visibility="collapsed"
                    )
                    tx["person"] = "shared" if selected_pers == "Shared" else selected_pers.lower()
                else:
                    st.write("Shared")
            with col6:
                if st.button("🗑️", key=f"del_pdf_tx_{tx.get('id', idx)}"):
                    st.session_state.pending_pdf_txs.remove(tx)
                    st.rerun()
            updated_txs.append(tx)
            st.markdown("<hr style='margin: 8px 0; opacity: 0.1;'>", unsafe_allow_html=True)
            
        st.write("")
        col_actions = st.columns([6, 2, 2])
        with col_actions[1]:
            if st.button("Cancel", width="stretch"):
                st.session_state.pending_pdf_txs = []
                st.rerun()
        with col_actions[2]:
            if st.button("Save to Sheets", type="primary", width="stretch"):
                with st.spinner("Saving transactions..."):
                    try:
                        saved_count = 0
                        for tx in updated_txs:
                            success = sheets_handler.add_transaction(tx)
                            if success:
                                saved_count += 1
                        
                        st.success(f"Successfully saved {saved_count} of {len(updated_txs)} transactions!")
                        st.session_state.pending_pdf_txs = []
                        st.rerun()
                    except Exception as err:
                        friendly_err = get_friendly_error_message(err)
                        st.error(f"⚠️ Error saving transactions: {friendly_err}")


elif menu == "⚙️ Settings":
    st.markdown("## ⚙️ Settings & Setup")
    
    st.write("Configure API keys and Google Sheets connections here.")
    
    st.markdown("""
    <div class="glass-card">
        <h3>🔑 API Keys</h3>
        <p>The application reads keys by default from Secret Manager or your local <b>.env</b> file.</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    
    with st.expander("Google Sheets API Configuration"):
        st.write("Enter your Service Account Credentials and Spreadsheet ID to activate Google Sheets sync:")
        
        spreadsheet_id_val = st.text_input("Spreadsheet ID", value=os.environ.get("SPREADSHEET_ID", ""))
        service_account_exists = os.path.exists("service_account.json")
        st.write(f"Local 'service_account.json' file present: {'✅ Yes' if service_account_exists else '❌ No'}")
        
        if st.button("Update Sheets Connection"):
            os.environ["SPREADSHEET_ID"] = spreadsheet_id_val
            from importlib import reload
            import utils.sheets_handler
            reload(utils.sheets_handler)
            st.success("Settings loaded! Please refresh the app to activate connection.")
            st.rerun()

    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    section_title("≡", "Manage Categories", "Categories for expenses, income, and savings")
    
    all_categories_data = load_categories_from_sheets()
    
    tab_exp, tab_inc, tab_sav = st.tabs(["💸 Expenses", "💰 Income", "🏦 Savings"])
    
    tab_mapping = [
        (tab_exp, "expense", "Expenses"),
        (tab_inc, "income", "Income"),
        (tab_sav, "savings", "Savings")
    ]
    
    for tab_obj, type_key, type_title in tab_mapping:
        with tab_obj:
            st.write(f"Manage categories and automated keywords for **{type_title}**:")
            items = all_categories_data.get(type_key, [])
            
            if not items:
                st.info(f"No categories available for {type_title}.")
            else:
                h1, h2, h3 = st.columns([3, 5, 1])
                with h1:
                    st.markdown("<span style='font-size:0.8rem; color:#8da382; font-weight:700; text-transform:uppercase;'>Category Name</span>", unsafe_allow_html=True)
                with h2:
                    st.markdown("<span style='font-size:0.8rem; color:#8da382; font-weight:700; text-transform:uppercase;'>Keywords (comma-separated)</span>", unsafe_allow_html=True)
                with h3:
                    st.markdown("<span style='font-size:0.8rem; color:#8da382; font-weight:700; text-transform:uppercase;'>Action</span>", unsafe_allow_html=True)
                
                st.markdown("<hr style='margin:4px 0 12px 0; opacity:0.2;'>", unsafe_allow_html=True)
                
                for i, cat in enumerate(items):
                    col1, col2, col3 = st.columns([3, 5, 1])
                    with col1:
                        st.markdown(f"<div style='margin-top: 6px;'>**{cat['name']}**</div>", unsafe_allow_html=True)
                    with col2:
                        kw_val = ", ".join(cat.get("keywords", []))
                        new_keywords_input = st.text_input(
                            label="Keywords",
                            value=kw_val,
                            key=f"kw_{type_key}_{i}",
                            label_visibility="collapsed"
                        )
                        clean_kws = [k.strip() for k in new_keywords_input.split(",") if k.strip()]
                        if clean_kws != cat.get("keywords", []):
                            update_category_keywords(type_key, cat["name"], clean_kws)
                            st.rerun()
                            
                    with col3:
                        if st.button("🗑️", key=f"del_{type_key}_{i}", help="Delete category"):
                            usage_count = count_transactions_with_category(cat["name"])
                            if usage_count > 0:
                                st.warning(f"⚠️ “{cat['name']}” is used in {usage_count} transactions and cannot be deleted. Assign those transactions to another category first.")
                            else:
                                delete_category(type_key, cat["name"])
                                st.success(f"✅ Category “{cat['name']}” deleted.")
                                st.rerun()
                                
            st.markdown("<hr style='margin: 1.5rem 0 1rem 0;'>", unsafe_allow_html=True)
            st.markdown("##### Add New Category")
            
            col1, col2, col3 = st.columns([3, 5, 1])
            with col1:
                new_name = st.text_input("Category Name", placeholder="e.g. Pets", key=f"new_cat_name_{type_key}")
            with col2:
                new_keywords = st.text_input("Keywords (comma-separated)", placeholder="e.g. vet,petco,chewy", key=f"new_cat_keywords_{type_key}")
            with col3:
                st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                if st.button("＋ Add", key=f"add_cat_{type_key}"):
                    if new_name.strip():
                        add_category(
                            type_=type_key,
                            name=new_name.strip(),
                            keywords=[k.strip() for k in new_keywords.split(",") if k.strip()]
                        )
                        st.success(f"✅ Category “{new_name.strip()}” added.")
                        st.rerun()
                    else:
                        st.warning("⚠️ Please enter a category name.")
