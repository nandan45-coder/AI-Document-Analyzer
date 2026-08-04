from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlite3
import os

DATABASE_URL = "sqlite:///./documents.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def run_migrations():
    db_path = "documents.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_history';")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(resume_history)")
                cols = {row[1] for row in cursor.fetchall()}
                for col_name, col_type in [("resume_score", "INTEGER"), ("ats_score", "INTEGER"), ("recommended_role", "VARCHAR")]:
                    if col_name not in cols:
                        cursor.execute(f"ALTER TABLE resume_history ADD COLUMN {col_name} {col_type}")
                conn.commit()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(users)")
                cols = {row[1] for row in cursor.fetchall()}
                for col_name, col_type in [("security_question", "VARCHAR"), ("security_answer", "VARCHAR")]:
                    if col_name not in cols:
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                conn.commit()
            conn.close()
        except Exception:
            pass


run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()