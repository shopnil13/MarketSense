"""Executive Agent tools — load analysis, draft actions, queue for human approval."""
import json
import datetime

import httpx
from langchain_core.tools import tool
from loguru import logger
from sqlalchemy import select

from core.database import AsyncSessionFactory
from core.models import AnalysisReport, PendingAction, Product
from core.config import settings


@tool
async def load_analysis_report(report_id: str) -> str:
    """Load the full analysis from Postgres by report_id (§3.1 — pass ids, not JSON blobs).

    The Analyst provided this report_id in the Band message. Loading from Postgres
    avoids re-parsing LLM-formatted JSON from the chat message.

    Args:
        report_id: UUID of the AnalysisReport row.
    """
    async with AsyncSessionFactory() as db:
        report = await db.get(AnalysisReport, report_id)
        if not report:
            return json.dumps({"error": f"No report found for id={report_id}"})

        product = await db.get(Product, report.product_id)
        product_name = product.name if product else report.sku

        return json.dumps({
            "report_id": str(report.id),
            "sku": report.sku,
            "product_name": product_name,
            "recommended_action": report.recommended_action,
            "proposed_price": float(report.proposed_price or 0),
            "expected_margin": float(report.expected_margin or 0),
            "strategic_narrative": report.strategic_narrative,
            "reasoning": report.llm_recommendation,
            "trigger_event": report.trigger_event,
            "price_comparison": report.price_comparison,
        })


@tool
async def draft_action_content(
    report_id: str,
    sku: str,
    product_name: str,
    recommended_action: str,
    proposed_price: float,
    expected_margin: float,
    strategic_narrative: str,
) -> str:
    """Draft the human-facing action content for HiTL review.

    Creates a clear, concise action summary the human reviewer will see
    on the approval dashboard.

    Args:
        report_id: The analysis report UUID.
        sku: Product SKU.
        product_name: Product display name.
        recommended_action: "match" | "undercut" | "hold".
        proposed_price: Recommended new price.
        expected_margin: Expected margin % at proposed_price.
        strategic_narrative: LLM-generated strategic context.
    """
    action_map = {
        "match": "Price Match",
        "undercut": "Price Undercut (−2%)",
        "hold": "Price Hold",
    }
    action_label = action_map.get(recommended_action, recommended_action.title())

    draft = (
        f"## Pricing Action Required: {action_label}\n\n"
        f"**Product:** {product_name} ({sku})\n"
        f"**Proposed Price:** PKR {proposed_price:,.0f}\n"
        f"**Expected Margin:** {expected_margin:.1f}%\n\n"
        f"### Strategic Context\n{strategic_narrative}\n\n"
        f"_Report ID: {report_id} — Full analysis in Postgres._\n"
        f"_Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
    )

    return json.dumps({
        "report_id": report_id,
        "sku": sku,
        "action_type": f"price_{recommended_action}",
        "proposed_price": proposed_price,
        "expected_margin": expected_margin,
        "draft_content": draft,
    })


@tool
async def queue_for_human_approval(
    report_id: str,
    sku: str,
    action_type: str,
    proposed_price: float,
    expected_margin: float,
    draft_content: str,
) -> str:
    """Persist the action to Postgres as 'pending' and send a Slack notification.

    The human reviews and approves/rejects via the FastAPI HiTL dashboard.
    Nothing executes without human approval — this is the governance gate.

    Args:
        report_id: Analysis report UUID.
        sku: Product SKU.
        action_type: e.g. "price_match".
        proposed_price: Recommended price to action.
        expected_margin: Margin at proposed_price.
        draft_content: Markdown draft for the human reviewer.
    """
    async with AsyncSessionFactory() as db:
        action = PendingAction(
            report_id=report_id,
            sku=sku,
            action_type=action_type,
            action_payload={
                "proposed_price": proposed_price,
                "expected_margin": expected_margin,
            },
            draft_content=draft_content,
            status="pending",
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)

    action_id = action.id
    hitl_url = f"{settings.hitl_api_url}/actions/{action_id}"
    logger.info(f"[Executive] Queued action {action_id} for {sku} — review at {hitl_url}")

    # Slack notification (best-effort — demo continues even if Slack fails)
    if settings.slack_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(settings.slack_webhook_url, json={
                    "text": (
                        f":bell: *MarketSense AI — Action Pending Approval*\n"
                        f">Product: {sku}\n"
                        f">Action: {action_type.replace('_', ' ').title()}\n"
                        f">Proposed Price: PKR {proposed_price:,.0f} (margin {expected_margin:.1f}%)\n"
                        f">Review: {hitl_url}"
                    )
                })
        except Exception as e:
            logger.warning(f"Slack notification failed (non-fatal): {e}")

    return json.dumps({
        "action_id": action_id,
        "status": "pending",
        "review_url": hitl_url,
        "message": f"Action queued for human approval. Reviewer notified at {hitl_url}",
    })
