# Database Migrations

This directory contains Alembic database migrations for the epub_translator project.

## Quick Start

```bash
cd backend

# Apply all pending migrations
alembic upgrade head

# Check current migration status
alembic current

# Show migration history
alembic history
```

## Creating Migrations

After modifying database models:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new column to projects table"

# Review the generated migration in migrations/versions/
# Edit if necessary, then apply
alembic upgrade head
```

## Rollback

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

## Development vs Production

- **Development**: The app uses `create_all()` on startup for convenience
- **Production**: Use Alembic migrations for controlled schema changes

To switch to migration-only mode, set `SKIP_DB_CREATE_ALL=true` in your environment.

## Notes

- Always review auto-generated migrations before applying
- SQLite has limited ALTER TABLE support - some migrations may need manual adjustment
- Test migrations on a copy of production data before deploying

