import sqlite3
from categorize import Transaction
import json

DB_PATH = "expenses.db"

def init_db():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT NOT NULL,
            statement_month TEXT NOT NULL,
            date TEXT NOT NULL,
            merchant TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            confidence REAL NOT NULL,
            from_memory INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT NOT NULL,
            statement_month TEXT NOT NULL,
            total_spent REAL NOT NULL,
            category_totals TEXT NOT NULL,
            insights TEXT NOT NULL,
            summary TEXT NOT NULL,
            chart_path TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            UNIQUE(card_name, statement_month)
        )
    """)
    connection.commit()
    connection.close()

def has_existing_transactions(card_name: str, statement_month: str) -> bool:
    """Checks whether transactions already exist for this card + month combination."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM transactions WHERE card_name = ? AND statement_month = ?",
        (card_name, statement_month)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def delete_transactions_for_month(card_name: str, statement_month: str):
    """Deletes all transactions for a given card + month — used before re-saving, to avoid duplicates."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transactions WHERE card_name = ? AND statement_month = ?",
        (card_name, statement_month)
    )
    conn.commit()
    conn.close()

def save_transactions(transactions: list[Transaction], card_name: str, statement_month: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for t in transactions:
        cursor.execute("""
            INSERT INTO transactions (card_name, statement_month, date, merchant, amount, category, confidence, from_memory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (card_name, statement_month, t.date, t.merchant, t.amount, t.category, t.confidence, int(t.from_memory)))
    conn.commit()
    conn.close()

def get_transactions_for_month(statement_month: str,card_name: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE card_name = ? AND statement_month = ?",
        (card_name, statement_month)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_transactions_for_month(statement_month: str) -> list[dict]:
    """NEW: combines transactions across ALL cards for a given month —
    useful when you want total spending regardless of which card was used."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE statement_month = ?", (statement_month,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_months() -> list[str]:
    """Returns a sorted list of all distinct months we have data for."""
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT statement_month FROM transactions ORDER BY statement_month")
    months = [row[0] for row in cursor.fetchall()]
    connection.close()
    return months


def save_report(report: dict, card_name: str):
    """Saves a full monthly report, replacing any existing report for that month."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reports (card_name,statement_month, total_spent, category_totals, insights, summary, chart_path, generated_at)
        VALUES (?,?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_name, statement_month) DO UPDATE SET
            total_spent=excluded.total_spent,
            category_totals=excluded.category_totals,
            insights=excluded.insights,
            summary=excluded.summary,
            chart_path=excluded.chart_path,
            generated_at=excluded.generated_at
    """, (
        card_name,
        report["statement_month"],
        report["total_spent"],
        json.dumps(report["category_totals"]),  # dict -> JSON string, since SQLite has no dict type
        report["insights"],
        report["summary"],
        report["chart_path"],
        report["generated_at"],
    ))
    conn.commit()
    conn.close()

def get_report(statement_month: str, card_name: str) -> dict | None:
    """Retrieves a single saved report by month, or None if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE card_name =? AND statement_month = ?", (card_name,statement_month))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    report = dict(row)
    report["category_totals"] = json.loads(report["category_totals"])  # JSON string -> dict
    return report

def get_all_reports() -> list[dict]:
    """Retrieves all saved reports, ordered by month."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports ORDER BY statement_month")
    rows = cursor.fetchall()
    conn.close()

    reports = []
    for row in rows:
        r = dict(row)
        r["category_totals"] = json.loads(r["category_totals"])
        reports.append(r)
    return reports
    
def get_all_card_names() -> list[str]:
    """Returns a sorted list of all distinct card names we have data for."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT card_name FROM reports ORDER BY card_name")
    cards = [row[0] for row in cursor.fetchall()]
    conn.close()
    return cards

def get_months_for_card(card_name: str) -> list[str]:
    """Returns all months we have a report for, for a given card."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT statement_month FROM reports WHERE card_name = ? ORDER BY statement_month DESC",
        (card_name,)
    )
    months = [row[0] for row in cursor.fetchall()]
    conn.close()
    return months


#EXTRA
def get_distinct_merchants() -> list[str]:
    """Returns every unique merchant name we've ever categorized."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT merchant FROM transactions")
    merchants = [row[0] for row in cursor.fetchall()]
    conn.close()
    return merchants

def sum_by_merchant(merchant: str) -> float:
    """Total amount spent at a specific merchant, across all months/cards."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE merchant = ?", (merchant,))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result else 0.0