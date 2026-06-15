"""Scout Agent tools — scan competitor prices and fetch social sentiment."""
import json
import uuid
import datetime

from langchain_core.tools import tool
from loguru import logger
from sqlalchemy import select

from core.database import AsyncSessionFactory
from core.models import Product, Competitor, PriceSnapshot, SentimentRecord
from core.config import settings
from agents.scout.scraper import get_competitor_prices


@tool
async def scan_competitor_prices(sku: str, demo_mode: bool = True) -> str:
    """Scan competitor prices for a product SKU and detect significant drops.

    Returns a JSON payload with the event details + a ready-to-relay Band
    recruitment_message and suggested_room_name (§3.5 — reduces tool-call variance).

    Args:
        sku: Product SKU to scan (e.g. "PUMA-SNK-001").
        demo_mode: When True, simulates a 15% drop on Daraz for demo reliability.
    """
    async with AsyncSessionFactory() as db:
        product = (await db.execute(select(Product).where(Product.sku == sku))).scalar_one_or_none()
        if not product:
            return json.dumps({"error": f"Product {sku} not found in database."})

        competitors = (
            await db.execute(select(Competitor).where(Competitor.product_id == product.id))
        ).scalars().all()

        comp_dicts = [{"name": c.competitor_name, "url": c.url} for c in competitors]

    prices = await get_competitor_prices(
        sku,
        comp_dicts,
        use_live=False,
        demo_drop_competitor="Daraz" if demo_mode else None,
        demo_drop_pct=0.15,
    )

    async with AsyncSessionFactory() as db:
        product = (await db.execute(select(Product).where(Product.sku == sku))).scalar_one_or_none()
        competitors_map = {
            c.competitor_name: c
            for c in (await db.execute(select(Competitor).where(Competitor.product_id == product.id))).scalars().all()
        }

        snapshots = []
        for p in prices:
            comp = competitors_map.get(p.competitor_name)
            if comp:
                snap = PriceSnapshot(
                    product_id=product.id,
                    competitor_id=comp.id,
                    price=p.price,
                    source=p.source,
                )
                db.add(snap)
                snapshots.append((p, snap))
        await db.commit()
        for _, s in snapshots:
            await db.refresh(s)

    threshold = settings.price_drop_threshold_pct / 100
    our_price = float(product.our_price)
    drop_events = []

    for p, snap in snapshots:
        drop_pct = (our_price - p.price) / our_price
        if drop_pct >= threshold:
            today = datetime.date.today().isoformat()
            room_name = f"alert-{sku}-{p.competitor_name[:4].upper()}-{today}"
            recruitment_message = (
                f"@Analyst Agent 🚨 Price alert: {product.name} ({sku})\n"
                f"• {p.competitor_name} dropped to PKR {p.price:,.0f} ({drop_pct:.1%} below our PKR {our_price:,.0f})\n"
                f"• Snapshot ID: {snap.id}\n"
                f"Please analyse and determine our optimal response."
            )
            drop_events.append({
                "sku": sku,
                "product_name": product.name,
                "our_price": our_price,
                "competitor_name": p.competitor_name,
                "competitor_price": p.price,
                "drop_pct": round(drop_pct * 100, 1),
                "event_id": snap.id,
                "room_name": room_name,
                "recruitment_message": recruitment_message,
                "action_required": True,
            })
            logger.info(f"[Scout] Price alert: {sku} — {p.competitor_name} at {p.price} ({drop_pct:.1%} drop)")

    if not drop_events:
        price_summary = [{"competitor": p.competitor_name, "price": p.price} for p, _ in snapshots]
        return json.dumps({
            "sku": sku,
            "status": "no_significant_drop",
            "our_price": our_price,
            "competitor_prices": price_summary,
        })

    return json.dumps({"sku": sku, "alerts": drop_events})


@tool
async def get_social_sentiment(sku: str, report_id: str = "") -> str:
    """Fetch (simulated) social sentiment for a product SKU.

    In production this would call a social listening API. For the demo it
    returns plausible mock sentiment and persists it in Postgres.

    Args:
        sku: Product SKU to analyse.
        report_id: The Analyst's report_id — included in reply so Analyst can correlate.
    """
    import random

    MOCK_SENTIMENT = {
        "PUMA-SNK-001": {"score": -0.15, "volume": 342, "summary": "Customers price-sensitive; several comments note cheaper options at Daraz. Brand loyalty moderate."},
        "NIKE-AIR-002": {"score": 0.42, "volume": 891, "summary": "Strong positive buzz; limited-edition colourway trending on Instagram. Price elasticity low."},
        "ADIDAS-RUN-003": {"score": 0.08, "volume": 215, "summary": "Neutral to mildly positive. Main concern is shipping speed, not price."},
    }

    data = MOCK_SENTIMENT.get(sku, {"score": 0.0, "volume": 50, "summary": "Insufficient data for sentiment analysis."})

    async with AsyncSessionFactory() as db:
        product = (await db.execute(select(Product).where(Product.sku == sku))).scalar_one_or_none()
        if product:
            record = SentimentRecord(
                product_id=product.id,
                sku=sku,
                score=data["score"],
                volume=data["volume"],
                summary=data["summary"],
            )
            db.add(record)
            await db.commit()

    result = {
        "report_id": report_id,
        "sku": sku,
        "sentiment_score": data["score"],
        "mention_volume": data["volume"],
        "summary": data["summary"],
    }
    logger.info(f"[Scout] Sentiment for {sku}: score={data['score']}, volume={data['volume']}")
    return json.dumps(result)
