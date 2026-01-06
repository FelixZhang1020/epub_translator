#!/usr/bin/env python3
"""Migration script to convert BookAnalysis to dynamic raw_analysis format.

This migration:
1. Adds raw_analysis column if it doesn't exist
2. Migrates data from old fixed columns to raw_analysis JSON
3. Old columns are left in place (SQLite limitation) but will be ignored

Run from backend directory:
    python scripts/migrate_analysis_to_dynamic.py
"""

import json
import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    """Get the database path from the backend directory."""
    # Check for database in common locations
    possible_paths = [
        Path("./epub_translator.db"),
        Path("../epub_translator.db"),
        Path(__file__).parent.parent / "epub_translator.db",
    ]

    for path in possible_paths:
        if path.exists():
            return path.resolve()

    raise FileNotFoundError(
        "Database not found. Please run this script from the backend directory."
    )


def has_column(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in the table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_analysis():
    """Migrate book_analyses table to use raw_analysis JSON field."""
    db_path = get_db_path()
    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if book_analyses table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='book_analyses'"
        )
        if not cursor.fetchone():
            print("Table 'book_analyses' does not exist. Nothing to migrate.")
            return

        # Check if raw_analysis column already exists
        if has_column(cursor, "book_analyses", "raw_analysis"):
            print("Column 'raw_analysis' already exists.")

            # Check if there are records with old format (author_biography exists but raw_analysis is null)
            if has_column(cursor, "book_analyses", "author_biography"):
                cursor.execute(
                    "SELECT COUNT(*) FROM book_analyses WHERE raw_analysis IS NULL AND author_biography IS NOT NULL"
                )
                needs_migration = cursor.fetchone()[0]
                if needs_migration > 0:
                    print(f"Found {needs_migration} records to migrate to new format.")
                else:
                    print("All records already in new format. Migration complete.")
                    return
            else:
                print("Migration complete. No old columns found.")
                return
        else:
            # Add raw_analysis column
            print("Adding 'raw_analysis' column...")
            cursor.execute(
                "ALTER TABLE book_analyses ADD COLUMN raw_analysis TEXT"
            )
            conn.commit()
            print("Column added successfully.")

        # Check if we have old format columns to migrate
        old_columns = [
            "author_biography",
            "writing_style",
            "tone",
            "target_audience",
            "genre_conventions",
            "key_terminology",
        ]

        existing_old_columns = [
            col for col in old_columns
            if has_column(cursor, "book_analyses", col)
        ]

        if not existing_old_columns:
            print("No old columns found. Migration complete.")
            return

        print(f"Found old columns: {existing_old_columns}")

        # Migrate data from old columns to raw_analysis
        cursor.execute(
            f"SELECT id, {', '.join(existing_old_columns)} FROM book_analyses WHERE raw_analysis IS NULL"
        )
        rows = cursor.fetchall()

        if not rows:
            print("No records need migration.")
            return

        print(f"Migrating {len(rows)} records...")

        for row in rows:
            record_id = row[0]
            raw_analysis = {}

            for i, col in enumerate(existing_old_columns):
                value = row[i + 1]
                if value:
                    # Try to parse JSON for complex fields
                    if col in ("genre_conventions", "key_terminology"):
                        try:
                            raw_analysis[col] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            raw_analysis[col] = value
                    else:
                        raw_analysis[col] = value

            if raw_analysis:
                cursor.execute(
                    "UPDATE book_analyses SET raw_analysis = ? WHERE id = ?",
                    (json.dumps(raw_analysis, ensure_ascii=False), record_id)
                )

        conn.commit()
        print(f"Successfully migrated {len(rows)} records.")

        print("\nMigration complete!")
        print("Note: Old columns are left in place (SQLite limitation).")
        print("They will be ignored by the application.")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_analysis()
