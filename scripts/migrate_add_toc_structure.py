#!/usr/bin/env python3
"""Migration script to add toc_structure column to projects table."""

import sqlite3
import sys
from pathlib import Path

# Default database path
DB_PATH = Path(__file__).parent.parent / "backend" / "epub_translator.db"


def migrate(db_path: Path = DB_PATH):
    """Add toc_structure column to projects table if it doesn't exist."""
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cursor.fetchall()]

        if "toc_structure" in columns:
            print("Column 'toc_structure' already exists in 'projects' table.")
            return True

        # Add the column
        print("Adding 'toc_structure' column to 'projects' table...")
        cursor.execute("""
            ALTER TABLE projects
            ADD COLUMN toc_structure TEXT
        """)
        conn.commit()
        print("Migration completed successfully!")
        return True

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    success = migrate(db_path)
    sys.exit(0 if success else 1)
