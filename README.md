# 💳 AI Expense Analyzer

A multi-agent AI system that turns raw credit card PDF statements into categorized spending insights, month-over-month trend analysis, and natural-language Q&A — with a privacy-first design that redacts PII before any data reaches an LLM.

## What it does

1. Upload a credit card statement (PDF)
2. Extracts and cleans transaction data (handles multi-column bank PDF layouts)
3. Redacts personally identifiable information before any LLM call
4. Categorizes each transaction using an AI agent, with confidence scoring
5. Flags low-confidence categorizations for human review via the UI
6. Analyzes month-over-month spending trends
7. Generates a natural-language monthly summary + chart
8. Answers free-form questions about your spending history (e.g. "What was my highest expenditure?")

## Architecture

## Tech Stack

- **Python** — core language
- **CrewAI** — multi-agent orchestration (Categorizer, Analyst, Reporter agents)
- **OpenAI (gpt-4.1-mini)** — LLM backend
- **pdfplumber** — PDF text/layout extraction
- **Presidio (Microsoft)** — PII detection and redaction
- **SQLite** — persistent transaction and report storage
- **Streamlit** — web UI
- **Pydantic** — structured LLM output validation
- **matplotlib** — chart generation

## Key Design Decisions

**Deterministic work stays in code; agents only handle judgment.** Extraction, redaction, and database operations are plain Python — no LLM involved. Agents are reserved for genuinely judgment-based tasks: categorizing ambiguous merchants, identifying "notable" trends, and writing natural-language summaries. This keeps the pipeline fast, cheap, and predictable where it can be.

**PII redaction happens before any data reaches an LLM**, using a two-layer approach: Presidio's NER-based detection (tuned to exclude entity types like dates and locations that are functionally needed, not sensitive here) plus a regex-based safety gate as a fail-safe. If the gate detects anything suspicious post-redaction, the pipeline halts rather than silently sending data onward.

**Merchant memory skips redundant LLM calls.** Once a merchant is categorized (via LLM or human correction), it's cached and matched on future runs without needing another API call — reducing cost and improving consistency across statements.

**Text-to-SQL for Q&A is sandboxed, not trusted blindly.** The Q&A feature lets an LLM generate SQL queries to answer free-form questions, but every query is validated against a `SELECT`-only allowlist and executed against a read-only database connection — defense in depth against the LLM ever generating a destructive query.

**No arithmetic is ever delegated to an LLM.** All totals, comparisons, and aggregations are computed in code (SQL or Python); LLMs only interpret and phrase results.

## Setup

1. Clone the repo and create a virtual environment:
```bash
   python3.12 -m venv venv
   source venv/bin/activate
```
2. Install dependencies:
```bash
   pip install -r requirements.txt
   python -m spacy download en_core_web_lg
```
3. Add your OpenAI API key to a `.env` file:

4. Run the app:
```bash
   streamlit run app.py
```

## Known Limitations

- PDF extraction is tuned for statements with a "date, description, amount" line structure; heavily scanned/image-based statements would need an OCR fallback (not currently implemented).
- No user authentication — designed as a single-user local tool.

## Security Notes

- Real financial statements, the SQLite database, and merchant memory files are excluded from version control (see `.gitignore`).
- The public demo deployment (if applicable) uses synthetic data only.

## Live Demo

https://expense-analyzer-harman.streamlit.app/


Note: This is a portfolio demo. Please don't upload real financial statements —
use the app to explore the categorization, multi-agent analysis, and Q&A features
with your own test data instead.

## Data Handling & Cleanup

This app stores uploaded statements and derived data locally (SQLite + local
files). For the live demo, stored data is periodically and manually cleared
using `cleanup.py`:

```bash
python cleanup.py          # clears all transactions, reports, uploads, memory
python cleanup.py --full   # also deletes the database file entirely
```

No data is retained long-term on the deployed instance.