"""Shared seed data + idempotent seeding routine.

Used by both scripts/seed_data.py (CLI) and the HiTL API startup event (so a fresh
Railway database is populated automatically without a separate seed process).
"""
from loguru import logger
from sqlalchemy import select

from core.database import AsyncSessionFactory, init_db
from core.models import Product, Competitor


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


async def seed_products(create_tables: bool = True) -> int:
    """Insert demo products + competitors if missing. Idempotent. Returns count seeded."""
    if create_tables:
        await init_db()

    seeded = 0
    async with AsyncSessionFactory() as db:
        for p_data in PRODUCTS:
            existing = (
                await db.execute(select(Product).where(Product.sku == p_data["sku"]))
            ).scalar_one_or_none()
            if existing:
                continue

            product = Product(
                sku=p_data["sku"],
                name=p_data["name"],
                category=p_data["category"],
                our_price=p_data["our_price"],
                cost_price=p_data["cost_price"],
            )
            db.add(product)
            await db.flush()

            for c_data in p_data["competitors"]:
                db.add(Competitor(
                    product_id=product.id,
                    competitor_name=c_data["name"],
                    url=c_data.get("url"),
                ))
            seeded += 1

        await db.commit()

    logger.info(f"[seed] products seeded this run: {seeded} (existing skipped)")
    return seeded
