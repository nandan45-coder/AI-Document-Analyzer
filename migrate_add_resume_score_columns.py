"""
One-time migration script for the Dashboard analytics upgrade.

Your existing documents.db already has a resume_history table WITHOUT
the new resume_score / ats_score / recommended_role columns.
Base.metadata.create_all() only creates missing TABLES, it does not add
missing COLUMNS to an existing table - so this needs to run once before
the app will work with the new resume_history.py model.

Run this once from your project root:
    python migrate_add_resume_score_columns.py

Safe to run multiple times - it checks for each column first.
"""

import sqlite3

DB_PATH = "documents.db"

NEW_COLUMNS = [
    ("resume_score", "INTEGER"),
    ("ats_score", "INTEGER"),
    ("recommended_role", "VARCHAR"),
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(resume_history)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_type in NEW_COLUMNS:
        if column_name in existing_columns:
            print(f"Column '{column_name}' already exists - skipping.")
            continue

        cursor.execute(
            f"ALTER TABLE resume_history ADD COLUMN {column_name} {column_type}"
        )
        print(f"Added column '{column_name}' ({column_type}).")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()