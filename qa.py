import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from database import DB_PATH
import sqlite3
import re

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))





SCHEMA_DESCRIPTION = """
Table: transactions
Columns:
  - id (integer)
  - card_name (text) — e.g. "Rogers", "Visa"
  - statement_month (text) — format "YYYY-MM"
  - date (text)
  - merchant (text)
  - amount (real)
  - category (text) — one of: Groceries, Restaurants, Transportation, Shopping,
    Entertainment, Subscriptions, Personal Care, Bills & Utilities, Travel, Other
  - confidence (real)
  - from_memory (integer, 0 or 1)
"""

FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "ATTACH", "PRAGMA", "CREATE", "REPLACE", "TRUNCATE"
]

class SqlQuery(BaseModel):
    sql: str
    explanation: str


def generate_sql(question: str) -> SqlQuery:
    response = client.beta.chat.completions.parse(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": f"""You write SQLite SELECT queries to answer
            questions about a personal finance database.

            {SCHEMA_DESCRIPTION}

            Rules:
            - ONLY write SELECT queries. Never write INSERT, UPDATE, DELETE, DROP, or any
              other modifying statement.
            - If the user mentions a general term like "food", map it to the closest
              matching category from the fixed list (e.g. "food" -> "Restaurants" or
              "Groceries" based on context).
            - Always include a LIMIT clause (max 50 rows) unless doing an aggregate
              (SUM, COUNT, AVG, MIN, MAX) that returns a single row.
            """},
            {"role": "user", "content": question},
        ],
        response_format=SqlQuery,
    )
    return response.choices[0].message.parsed


def is_query_safe(sql: str) -> bool:
    """Rejects any query containing forbidden keywords, and requires it to start with SELECT."""
    sql_upper = sql.upper()

    if not sql_upper.strip().startswith("SELECT"):
        return False

    for keyword in FORBIDDEN_KEYWORDS:
        # \b ensures we match whole words only (avoids false positives on substrings)
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False

    return True


def execute_readonly_query(sql: str) -> list[dict]:
    """Executes a query against a READ-ONLY connection — extra defense even if
    the keyword filter is somehow bypassed."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def answer_question(question: str) -> str:
    query = generate_sql(question)

    if not is_query_safe(query.sql):
        return "Sorry, I couldn't safely process that question."

    try:
        results = execute_readonly_query(query.sql)
    except sqlite3.Error as e:
        return f"Sorry, I couldn't run that query: {e}"

    prompt = f"""The user asked: "{question}"

    Query run: {query.sql}
    Results: {results}

    Write a short, natural-language answer (1-2 sentences) using ONLY the
    data returned above. Do not make up or estimate any numbers."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    test_questions = [
        "What was my lowest single transaction?",
        "How much did I spend on food?",
        "What was my highest single transaction?",
        "How much did I spend through Rogers card?",
        "Delete the transactions made through Rogers card",
    ]

    for q in test_questions:
        print(f"Q: {q}")
        print(f"A: {answer_question(q)}\n")