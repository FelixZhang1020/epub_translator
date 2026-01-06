#!/usr/bin/env python3
"""Database migration script for V2 parser schema.

This script adds the new columns needed for V2 parser:
- xpath: XPath for element location in EPUB
- original_html: Raw HTML including tags
- has_formatting: Boolean for inline formatting

Run this script to migrate existing database:
    python scripts/migrate_v2.py

This migration is safe to run multiple times - it checks if columns exist first.
"""

import sqlite3
from pathlib import Path

# Database path - relative to backend directory
DB_PATH = Path(__file__).parent.parent / "epub_translator.db"


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    """Run the migration."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Database will be created with new schema on first run.")
        return

    print(f"Migrating database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Add xpath column
        if not column_exists(cursor, "paragraphs", "xpath"):
            print("Adding 'xpath' column to paragraphs table...")
            cursor.execute("ALTER TABLE paragraphs ADD COLUMN xpath TEXT")
            print("  Done.")
        else:
            print("Column 'xpath' already exists.")

        # Add original_html column
        if not column_exists(cursor, "paragraphs", "original_html"):
            print("Adding 'original_html' column to paragraphs table...")
            cursor.execute("ALTER TABLE paragraphs ADD COLUMN original_html TEXT")
            print("  Done.")
        else:
            print("Column 'original_html' already exists.")

        # Add has_formatting column
        if not column_exists(cursor, "paragraphs", "has_formatting"):
            print("Adding 'has_formatting' column to paragraphs table...")
            cursor.execute(
                "ALTER TABLE paragraphs ADD COLUMN has_formatting BOOLEAN DEFAULT 0"
            )
            print("  Done.")
        else:
            print("Column 'has_formatting' already exists.")

        # Add images column to chapters table
        if not column_exists(cursor, "chapters", "images"):
            print("Adding 'images' column to chapters table...")
            cursor.execute("ALTER TABLE chapters ADD COLUMN images JSON")
            print("  Done.")
        else:
            print("Column 'images' already exists.")

        conn.commit()
        print("\nMigration completed successfully!")
        print("\nTo populate the new columns for existing projects, use:")
        print("  POST /api/v1/projects/{project_id}/reparse")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
