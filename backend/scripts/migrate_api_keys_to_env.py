#!/usr/bin/env python3
"""
Migrate API keys from SQLite database to .env file.

This script:
1. Reads API keys from llm_configurations table
2. Writes them to .env file (creates if not exists)
3. Optionally clears keys from database

Usage:
    cd backend
    python scripts/migrate_api_keys_to_env.py

    # To also clear keys from database after migration:
    python scripts/migrate_api_keys_to_env.py --clear-db
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Project paths
BACKEND_DIR = Path(__file__).parent.parent
DB_PATH = BACKEND_DIR / "epub_translator.db"
ENV_PATH = BACKEND_DIR / ".env"
ENV_EXAMPLE_PATH = BACKEND_DIR / ".env.example"

# Provider to environment variable mapping
PROVIDER_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def get_api_keys_from_db() -> dict[str, str]:
    """Read API keys from database, grouped by provider."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return {}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT provider, api_key, name, model
            FROM llm_configurations
            WHERE api_key IS NOT NULL AND api_key != ''
            ORDER BY is_active DESC, updated_at DESC
        """)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        return {}
    finally:
        conn.close()

    # Group by provider, keep first (most recent active) key per provider
    keys_by_provider: dict[str, str] = {}
    configs_info: list[dict] = []

    for provider, api_key, name, model in rows:
        configs_info.append({
            "provider": provider,
            "name": name,
            "model": model,
            "key_preview": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "****"
        })

        if provider not in keys_by_provider:
            keys_by_provider[provider] = api_key

    # Print found configurations
    if configs_info:
        print(f"\nFound {len(configs_info)} configuration(s) in database:")
        print("-" * 60)
        for info in configs_info:
            print(f"  - {info['name']} ({info['provider']}/{info['model']})")
            print(f"    Key: {info['key_preview']}")
        print("-" * 60)

    return keys_by_provider


def write_env_file(api_keys: dict[str, str]) -> None:
    """Write API keys to .env file, preserving existing values."""

    # Start with template if .env doesn't exist
    if ENV_PATH.exists():
        with open(ENV_PATH, "r") as f:
            content = f.read()
    elif ENV_EXAMPLE_PATH.exists():
        with open(ENV_EXAMPLE_PATH, "r") as f:
            content = f.read()
        # Remove comment markers from API key lines we're setting
        for provider, api_key in api_keys.items():
            env_var = PROVIDER_ENV_MAP.get(provider)
            if env_var:
                # Uncomment and set the value
                content = content.replace(f"# {env_var}=", f"{env_var}=")
    else:
        content = ""

    # Parse existing content into lines
    lines = content.split("\n")
    updated_vars: set[str] = set()

    # Update existing lines or uncomment them
    new_lines = []
    for line in lines:
        modified = False
        for provider, api_key in api_keys.items():
            env_var = PROVIDER_ENV_MAP.get(provider)
            if not env_var:
                continue

            # Check if this line is for this env var
            if line.strip().startswith(f"{env_var}=") or line.strip().startswith(f"# {env_var}="):
                new_lines.append(f"{env_var}={api_key}")
                updated_vars.add(env_var)
                modified = True
                break

        if not modified:
            new_lines.append(line)

    # Add any keys not found in existing content
    for provider, api_key in api_keys.items():
        env_var = PROVIDER_ENV_MAP.get(provider)
        if env_var and env_var not in updated_vars:
            # Find the LLM API Keys section or add at the end
            insert_idx = len(new_lines)
            for i, line in enumerate(new_lines):
                if "LLM API Keys" in line:
                    # Find end of this section
                    for j in range(i + 1, len(new_lines)):
                        if new_lines[j].startswith("# ==="):
                            insert_idx = j
                            break
                    break

            new_lines.insert(insert_idx, f"{env_var}={api_key}")
            updated_vars.add(env_var)

    # Write updated content
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(new_lines))

    print(f"\nUpdated {ENV_PATH}")
    print(f"Added/updated {len(updated_vars)} API key(s):")
    for var in sorted(updated_vars):
        print(f"  - {var}")


def clear_keys_from_db() -> int:
    """Clear API keys from database after migration."""
    if not DB_PATH.exists():
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE llm_configurations
            SET api_key = NULL
            WHERE api_key IS NOT NULL
        """)
        affected = cursor.rowcount
        conn.commit()
        return affected
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate API keys from database to .env file"
    )
    parser.add_argument(
        "--clear-db",
        action="store_true",
        help="Clear API keys from database after migration"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("API Key Migration: Database -> .env")
    print("=" * 60)

    # Step 1: Read keys from database
    api_keys = get_api_keys_from_db()

    if not api_keys:
        print("\nNo API keys found in database. Nothing to migrate.")
        return 0

    print(f"\nFound {len(api_keys)} unique provider key(s) to migrate:")
    for provider, key in api_keys.items():
        env_var = PROVIDER_ENV_MAP.get(provider, f"{provider.upper()}_API_KEY")
        preview = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "****"
        print(f"  {provider} -> {env_var} = {preview}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")
        return 0

    # Step 2: Write to .env file
    write_env_file(api_keys)

    # Step 4: Optionally clear from database
    if args.clear_db:
        print("\nClearing API keys from database...")
        cleared = clear_keys_from_db()
        print(f"Cleared {cleared} key(s) from database.")
    else:
        print("\nNote: API keys are still in database.")
        print("Run with --clear-db to remove them after verifying .env works.")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Verify .env file contains your API keys")
    print("2. Restart the backend to load new environment variables")
    print("3. Test that LLM operations still work")
    if not args.clear_db:
        print("4. Run with --clear-db to remove keys from database")

    return 0


if __name__ == "__main__":
    sys.exit(main())

