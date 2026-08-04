"""
Migration script to add security_question and security_answer columns to users table in documents.db.
Run this script once from your project root:
    python migrate_add_security_question_columns.py
Safe to run multiple times.
"""

import sqlite3

DB_PATH = "documents.db"

NEW_COLUMNS = [
    ("security_question", "VARCHAR"),
    ("security_answer", "VARCHAR"),
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    if not cursor.fetchone():
        print("Table 'users' does not exist yet. It will be created automatically on app startup.")
        conn.close()
        return

    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_type in NEW_COLUMNS:
        if column_name in existing_columns:
            print(f"Column '{column_name}' already exists - skipping.")
            continue

        cursor.execute(
            f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
        )
        print(f"Added column '{column_name}' ({column_type}).")

    conn.commit()
    conn.close()
    print("Users table migration complete.")


if __name__ == "__main__":
    main()
