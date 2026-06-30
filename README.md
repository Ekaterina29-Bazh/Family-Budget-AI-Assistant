# Family Budget AI Assistant

**Project Summary**

Family Budget AI Assistant is an intelligent financial assistant designed for households. It automatically processes text messages, bank statement PDFs, and receipt screenshots, classifies expenses into meaningful categories, and records everything into a shared Google Sheet – minimizing manual data entry.
The system runs on Google Cloud, is secured via user context separation (and optionally Google Cloud IAP), and is built around modular AI skills powered by Gemini.

**The Problem**

Keeping track of a family budget means dealing with two very different types of expenses.
Cash purchases happen instantly and leave no digital trace – a trip to the bakery, a parking meter, a quick stop at the pharmacy. Unless you write it down immediately, it’s forgotten. Bank transactions, on the other hand, are documented in monthly PDF statements, but going through them manually – line by line, deciding what belongs where – takes time and patience most families don’t have.
Most budgeting apps don’t solve this. They either require manual input for every entry, or they need direct bank API access, which is rarely available to regular users. This project removes both friction points: users describe a cash expense in a short text message, upload their monthly bank PDF or receipt image, and the assistant takes care of the rest.

**How It Works**

The assistant handles multiple types of interactions through a simple chat and dashboard interface:

*Recording a cash expense*
As easy as typing a quick text: *“Spent €23.50 at Lidl today.”* The assistant parses the message, extracts the relevant details, assigns a category, and saves the entry to the shared Google Sheet – all within seconds.

*Processing a bank statement or receipt*
Requires just a PDF or image upload. The assistant reads through all transactions, classifies each one automatically, and presents them for review before writing them to the sheet in one go. For well-known merchants like Rossmann or Shell, this works reliably with very high confidence. For ambiguous entries like Amazon purchases, the assistant pauses and requests manual confirmation: *“Was that clothing, electronics, a gift, or something else?”*

*Correcting a mistake*
After reviewing the sheet, a user can simply say or type: *“The HEM entry from June 22nd wasn’t fuel, it was a car wash.”* The assistant finds the right row, updates the category, and confirms the change. If multiple entries could match, it asks which one to update before touching anything.

*Viewing Analytics*
A live dashboard provides an annual overview, category breakdowns (via donut charts), and monthly comparison trends to keep the household informed of their savings and spending habits.

**Architecture: One Agent, Six Skills**

Rather than building multiple separate agents that communicate with each other, the system uses a single assistant workflow that calls specialized skills depending on the situation. This approach is clean to implement, easy to debug, and highly modular.

*   **Skill 1: Text Parser** – Extracts structured transaction data from natural language text entries using Gemini.
*   **Skill 2: Document & Image Parser** – Extracts and structures transaction lines from bank statement PDFs and receipt images using `pdfplumber` combined with Gemini Vision.
*   **Skill 3: Budget Classifier** – Determines the category and subcategory of a transaction, assigning a confidence score. If the confidence falls below 0.8, it triggers a clarification prompt in the UI.
*   **Skill 4: Sheets Writer** – Formats and appends transaction data as a new row in the shared Google Sheet (with a local Excel fallback option).
*   **Skill 5: Correction Skill** – Locates existing spreadsheet entries and updates their category based on natural language feedback, with disambiguation safeguards.
*   **Skill 6: Analytics Generator** – Computes monthly budgets, trends, category totals, and net balances, rendering interactive charts and updating compilation metrics in the sheets.

**Expense Categories**

Expenses are divided into fixed and variable costs:
*   **Fixed costs** cover predictable monthly items: housing, utilities, communication, streaming & media, mobility, fitness, insurance, and other fixed costs.
*   **Variable costs** include groceries, drugstore, fuel, car maintenance, clothing, health, gifts, digital & subscriptions, leisure, dining out, and transfers.

*The Amazon Rule*
Amazon is treated as a merchant, not a category. Since Amazon sells everything from books to kitchen appliances, automatically labelling it as “Shopping” would be meaningless. Instead, the assistant always requests clarification when it encounters an Amazon entry – making the resulting data actually useful for budget analysis.

**Data Storage**

All transactions are stored in a Google Sheet (or local Excel fallback) with the following structure:
*   **Transactions Tab:** Where the assistant writes every entry, with columns for date, merchant, amount, category, subcategory, and source (text, PDF, image, or manual).
*   **Budget Tab:** Serves as a live dashboard using spreadsheet formulas referencing the Transactions tab, ensuring spending totals and remaining budgets update automatically.

**Security**

Since the application handles personal financial data and runs in the cloud, security is built into the design:

*   **Access Control:** Access and user context are toggled directly inside the UI. For production environments, authentication is managed at the infrastructure level (e.g., via Google Cloud Identity-Aware Proxy) to restrict access to authorized Google accounts without storing login credentials.
*   **API Keys:** All API credentials are read from environment variables, which can be injected dynamically via Google Cloud Secret Manager.
*   **Data Access:** The Google Sheet is private. The assistant writes through a dedicated Google Service Account that has access to exactly that one spreadsheet file.
*   **Transport:** HTTPS transport security is enforced automatically by Streamlit when deployed on Google Cloud.

**Technical Stack**

*   **Frontend:** Streamlit
*   **AI Model:** Gemini 2.5 Flash / Pro (using `google-genai` SDK)
*   **Document & Image Parsing:** `pdfplumber` + Gemini Vision
*   **Data Storage:** Google Sheets API (with local `openpyxl` Excel fallback)
*   **Orchestration:** Procedural Python & Streamlit Session State
*   **Deployment:** Google Cloud (App Engine or Cloud Run)
*   **Secret Management:** Google Cloud Secret Manager / Environment Variables
