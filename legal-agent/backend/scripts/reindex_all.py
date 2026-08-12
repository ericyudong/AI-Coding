"""Reindex all contracts for a user."""
import asyncio
import sys
from pathlib import Path

# Allow running as: python scripts/reindex_all.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.services import vector_store
from app.services.index_service import reindex_all


async def main() -> None:
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    vector_store.reset_client()
    async with SessionLocal() as session:
        count = await reindex_all(session, user_id=user_id)
        print(f"Indexed {count} contracts for user_id={user_id}")


if __name__ == "__main__":
    asyncio.run(main())
