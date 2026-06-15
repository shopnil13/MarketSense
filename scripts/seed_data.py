"""Seed the database with demo products and competitors.

Run once after `alembic upgrade head` (or after init_db in dev):
    python scripts/seed_data.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.database import AsyncSessionFactory, init_db
from core.models import Product, Competitor
from sqlalchemy import select


PRODUCTS = [
    {
        "sku": "PUMA-SNK-001",
        "name": "PUMA Sneaker Classic White",
        "category": "Footwear",
        "our_price": 9500.0,
        "cost_price": 5700.0,
        "competitors": [
            {"name": "Daraz", "url": None},
            {"name": "Goto", "url": None},
            {"name": "Naheed", "url": None},
        ],
    },
    {
        "sku": "NIKE-AIR-002",
        "name": "Nike Air Max 270",
        "category": "Footwear",
        "our_price": 13500.0,
        "cost_price": 8100.0,
        "competitors": [
            {"name": "Daraz", "url": None},
            {"name": "Goto", "url": None},
        ],
    },
    {
        "sku": "ADIDAS-RUN-003",
        "name": "Adidas Ultraboost 22",
        "category": "Footwear",
        "our_price": 10500.0,
        "cost_price": 6300.0,
        "competitors": [
            {"name": "Daraz", "url": None},
            {"name": "Goto", "url": None},
            {"name": "Naheed", "url": None},
        ],
    },
]


async def seed():
    await init_db()

    async with AsyncSessionFactory() as db:
        for p_data in PRODUCTS:
            existing = (
                await db.execute(select(Product).where(Product.sku == p_data["sku"]))
            ).scalar_one_or_none()

            if existing:
                print(f"  ✓ Product {p_data['sku']} already exists — skipping.")
                continue

            product = Product(
                sku=p_data["sku"],
                name=p_data["name"],
                category=p_data["category"],
                our_price=p_data["our_price"],
                cost_price=p_data["cost_price"],
            )
            db.add(product)
            await db.flush()  # get product.id

            for c_data in p_data["competitors"]:
                competitor = Competitor(
                    product_id=product.id,
                    competitor_name=c_data["name"],
                    url=c_data.get("url"),
                )
                db.add(competitor)

            print(f"  + Seeded {p_data['sku']} with {len(p_data['competitors'])} competitors.")

        await db.commit()

    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
