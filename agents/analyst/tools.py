"""Analyst Agent tools — pricing data, strategy calculation, strategic narrative, report persistence."""
import json
import uuid
from decimal import Decimal

from langchain_core.tools import tool
from loguru import logger
from sqlalchemy import select

from core.database import AsyncSessionFactory
from core.models import Product, AnalysisReport, SentimentRecord
from core.config import settings
from core.llm import aiml_reason
from core.text import clean_text


@tool
async def get_product_pricing_data(sku: str) -> str:
    """Load current product pricing and cost data from Postgres (the shared market state).

    Args:
        sku: Product SKU (e.g. "PUMA-SNK-001").
    """
    async with AsyncSessionFactory() as db:
        product = (await db.execute(select(Product).where(Product.sku == sku))).scalar_one_or_none()
        if not product:
            return json.dumps({"error": f"Product {sku} not found."})

        return json.dumps({
            "sku": sku,
            "product_name": product.name,
            "category": product.category,
            "our_price": float(product.our_price),
            "cost_price": float(product.cost_price),
            "current_margin_pct": round((float(product.our_price) - float(product.cost_price)) / float(product.our_price) * 100, 2),
        })


@tool
async def get_sentiment_for_sku(sku: str) -> str:
    """Read the most recent social sentiment for a SKU from Postgres.

    Scout records sentiment via its get_social_sentiment tool. After you have asked
    Scout for sentiment (once) and Scout has replied, call THIS tool to retrieve the
    value reliably from the shared database — do NOT parse it from the chat message,
    and do NOT send Scout another request.

    Args:
        sku: Product SKU (e.g. "PUMA-SNK-001").

    Returns:
        JSON with sentiment_score, mention_volume, summary, and `available` flag.
        If Scout hasn't recorded sentiment yet, `available` is false — end your turn
        and wait to be re-invoked; do NOT re-ask Scout.
    """
    async with AsyncSessionFactory() as db:
        record = (
            await db.execute(
                select(SentimentRecord)
                .where(SentimentRecord.sku == sku)
                .order_by(SentimentRecord.recorded_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if not record:
        return json.dumps({"sku": sku, "available": False,
                           "note": "No sentiment recorded yet. End your turn and wait for Scout's reply."})

    return json.dumps({
        "sku": sku,
        "available": True,
        "sentiment_score": float(record.score),
        "mention_volume": record.volume,
        "summary": record.summary,
    })


@tool
async def calculate_strategy_options(
    sku: str,
    our_price: float,
    cost_price: float,
    competitor_price: float,
    sentiment_score: float,
) -> str:
    """Calculate pricing strategy options given market data and sentiment.

    Evaluates match / undercut / hold strategies against the margin floor.

    Args:
        sku: Product SKU.
        our_price: Our current price.
        cost_price: Our cost price (used for margin calculation).
        competitor_price: Key competitor's price.
        sentiment_score: Social sentiment score (-1.0 to 1.0) from Scout.
    """
    floor = settings.margin_floor_pct / 100
    max_drop = settings.max_price_change_pct / 100

    options = []

    def margin(price: float) -> float:
        return (price - cost_price) / price * 100

    # Option 1: match competitor
    match_price = round(competitor_price, 2)
    match_margin = margin(match_price)
    options.append({
        "strategy": "match",
        "price": match_price,
        "margin_pct": round(match_margin, 2),
        "viable": match_margin >= settings.margin_floor_pct,
        "note": f"Matches {sku} competitor. Margin {'above' if match_margin >= settings.margin_floor_pct else 'BELOW'} floor.",
    })

    # Option 2: undercut by 2%
    undercut_price = round(competitor_price * 0.98, 2)
    undercut_margin = margin(undercut_price)
    options.append({
        "strategy": "undercut",
        "price": undercut_price,
        "margin_pct": round(undercut_margin, 2),
        "viable": undercut_margin >= settings.margin_floor_pct,
        "note": f"2% undercut. Margin {'above' if undercut_margin >= settings.margin_floor_pct else 'BELOW'} floor.",
    })

    # Option 3: hold current price
    hold_margin = margin(our_price)
    options.append({
        "strategy": "hold",
        "price": our_price,
        "margin_pct": round(hold_margin, 2),
        "viable": True,
        "note": "Hold price. Risk: volume loss if market is price-sensitive.",
    })

    # Recommend best viable strategy
    # Sentiment < 0 means customers are price-sensitive — prefer matching/undercutting
    viable = [o for o in options if o["viable"]]
    if not viable:
        recommended = options[2]  # hold — only safe fallback
    elif sentiment_score < -0.1:
        recommended = viable[0]  # match or undercut — price-sensitive market
    else:
        recommended = viable[-1]  # hold — brand loyalty sufficient

    return json.dumps({
        "sku": sku,
        "options": options,
        "recommended": recommended,
        "margin_floor_pct": settings.margin_floor_pct,
        "sentiment_score": sentiment_score,
    })


@tool
async def generate_strategic_narrative(context_json: str) -> str:
    """Generate a 3-4 sentence strategic narrative via a bounded AI/ML API call.

    Takes a JSON string with pricing options and market context; returns a concise
    recommendation the Executive can act on. This is a bounded, single-shot reasoning
    call — no tool-calling.

    Args:
        context_json: JSON string with strategy options, margin data, and sentiment.
    """
    prompt = (
        f"You are advising on a pricing decision for a Pakistani e-commerce retailer.\n\n"
        f"Context:\n{context_json}\n\n"
        f"Write a 3-4 sentence strategic narrative that:\n"
        f"1. States the market situation clearly.\n"
        f"2. Recommends the best action and why.\n"
        f"3. Calls out any risk (e.g. margin floor, brand perception).\n"
        f"Be concise and decisive. Use plain English — no bullet points."
    )
    try:
        narrative = await aiml_reason(prompt)
    except Exception as e:
        logger.warning(f"Narrative call failed ({e}), using fallback narrative.")
        narrative = "Market data indicates a competitive price drop. Recommend matching the competitor price to defend volume while maintaining margin above the floor. Monitor sentiment for further brand impact."

    return json.dumps({"narrative": narrative})


@tool
async def save_analysis_report(
    sku: str,
    trigger_event: str,
    price_comparison: str,
    recommended_action: str,
    proposed_price: float,
    expected_margin: float,
    strategic_narrative: str,
    llm_recommendation: str,
) -> str:
    """Persist the full analysis to Postgres and return a report_id for the Executive.

    The Band message to Executive carries only the report_id + a human-readable
    summary — the structured data lives here (§3.1 of implementation plan).

    Args:
        sku: Product SKU.
        trigger_event: JSON string of the PriceDropEvent from Scout.
        price_comparison: JSON string of strategy options.
        recommended_action: "match" | "undercut" | "hold".
        proposed_price: Recommended price.
        expected_margin: Expected margin percentage at proposed_price.
        strategic_narrative: LLM-generated strategic narrative text.
        llm_recommendation: Full LLM reasoning / recommendation text.
    """
    async with AsyncSessionFactory() as db:
        product = (await db.execute(select(Product).where(Product.sku == sku))).scalar_one_or_none()
        if not product:
            return json.dumps({"error": f"Product {sku} not found."})

        import json as _json
        report = AnalysisReport(
            product_id=product.id,
            sku=sku,
            trigger_event=clean_text(_json.loads(trigger_event) if isinstance(trigger_event, str) else trigger_event),
            price_comparison=clean_text(_json.loads(price_comparison) if isinstance(price_comparison, str) else price_comparison),
            recommended_action=recommended_action,
            proposed_price=proposed_price,
            expected_margin=expected_margin,
            strategic_narrative=clean_text(strategic_narrative),  # strip NUL bytes Postgres rejects
            llm_recommendation=clean_text(llm_recommendation),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

    logger.info(f"[Analyst] Saved report {report.id} for {sku} — action={recommended_action}, price={proposed_price}")
    return json.dumps({
        "report_id": report.id,
        "sku": sku,
        "recommended_action": recommended_action,
        "proposed_price": proposed_price,
        "expected_margin": expected_margin,
    })
