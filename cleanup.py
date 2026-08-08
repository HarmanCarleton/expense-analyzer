"""
Manually run this script periodically to clear all stored personal data —
useful before/after live demos, or to purge accumulated uploads.

Usage:
    python cleanup.py              # clears database tables + uploaded files
    python cleanup.py --full       # also deletes the database file entirely
"""
import os
import shutil
import sqlite3
import sys
from database import DB_PATH

STATEMENTS_DIR = "statements"
REPORTS_DIR = "reports"
MEMORY_FILE = "merchant_memory.json"

def clear_database_tables():
    if not os.path.exists(DB_PATH):
        print("No database file found — nothing to clear.")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM reports")
    conn.commit()
    conn.close()
    print("Cleared all rows from 'transactions' and 'reports' tables.")

def delete_database_file():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Deleted database file: {DB_PATH}")
    else:
        print("No database file found.")

def clear_folder(folder_path: str):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)
        print(f"Cleared all files in: {folder_path}/")
    else:
        print(f"{folder_path}/ does not exist — nothing to clear.")

def delete_merchant_memory():
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
        print(f"Deleted {MEMORY_FILE}")
    else:
        print(f"{MEMORY_FILE} not found — nothing to delete.")

if __name__ == "__main__":
    full_wipe = "--full" in sys.argv

    print("Starting cleanup...\n")

    clear_folder(STATEMENTS_DIR)   # deletes all uploaded PDFs
    clear_folder(REPORTS_DIR)      # deletes all generated charts
    delete_merchant_memory()       # clears learned merchant categories

    if full_wipe:
        delete_database_file()
    else:
        clear_database_tables()

    print("\nCleanup complete.")