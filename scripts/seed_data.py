"""Seed the database with demo products and competitors (idempotent).

    python scripts/seed_data.py

Shares its data/logic with the HiTL API startup via core.seed.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.database import engine
from core.seed import seed_products


async def main():
    count = await seed_products(create_tables=True)
    print(f"Seed complete — {count} new product(s) inserted (existing skipped).")
    await engine.dispose()  # close asyncpg pool so the process exits cleanly


if __name__ == "__main__":
    asyncio.run(main())
