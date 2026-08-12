"""SQLite schema migrations for new columns."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def run_migrations(engine: AsyncEngine) -> None:
    """Add columns to existing SQLite tables if missing."""
    migrations = [
        ("contract_reviews", "content_text", "TEXT DEFAULT ''"),
        ("contract_reviews", "parse_status", "VARCHAR(32) DEFAULT 'pending'"),
        ("contract_reviews", "parse_warnings_json", "TEXT DEFAULT '[]'"),
        ("managed_contracts", "index_status", "VARCHAR(32) DEFAULT 'pending'"),
        ("managed_contracts", "indexed_at", "DATETIME"),
        ("contract_import_tasks", "content_text", "TEXT DEFAULT ''"),
        ("contract_import_tasks", "parse_warnings_json", "TEXT DEFAULT '[]'"),
        ("users", "role", "VARCHAR(32) DEFAULT 'legal'"),
        ("users", "department_id", "INTEGER"),
        ("users", "is_active", "BOOLEAN DEFAULT 1"),
        ("managed_contracts", "department_id", "INTEGER"),
        ("managed_contracts", "summary_locked", "BOOLEAN DEFAULT 0"),
        ("managed_contracts", "tag_level1", "VARCHAR(64) DEFAULT ''"),
        ("managed_contracts", "tag_level2", "VARCHAR(64) DEFAULT ''"),
        ("managed_contracts", "parse_status", "VARCHAR(32) DEFAULT 'done'"),
        ("contract_import_tasks", "retry_count", "INTEGER DEFAULT 0"),
        ("performance_alerts", "email_status", "VARCHAR(32) DEFAULT 'pending'"),
        ("performance_alerts", "email_sent_at", "DATETIME"),
        ("performance_alerts", "email_error", "TEXT DEFAULT ''"),
        ("performance_adjustments", "evidence_note", "TEXT DEFAULT ''"),
        ("performance_adjustments", "evidence_filename", "VARCHAR(256) DEFAULT ''"),
    ]
    async with engine.begin() as conn:
        for table, column, col_type in migrations:
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            cols = {row[1] for row in result.fetchall()}
            if column not in cols:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
