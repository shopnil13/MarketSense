"""Analyst Agent — pricing strategy analysis with bidirectional Scout collaboration."""
import asyncio
import os
import logging

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from core.config import resolve_agent_credentials  # env vars (prod) -> agent_config.yaml (local)

from core.llm import get_aiml_llm  # C4: Analyst brain stays on AI/ML API
from core.database import init_db
from agents.analyst.tools import (
    get_product_pricing_data,
    get_sentiment_for_sku,
    calculate_strategy_options,
    generate_strategic_narrative,
    save_analysis_report,
)

ANALYST_INSTRUCTIONS = """You are the Analyst Agent for MarketSense AI — a senior pricing strategist.

## Your peers (exact Band names — use these verbatim when looking up or @mentioning)
- scout     — the Scout Agent (price + sentiment data)
- executive — the Executive Agent (human-in-the-loop gate)
Everything happens in the CURRENT room. Do NOT create new chatrooms.

## How to message a peer (IMPORTANT — the platform requires this)
1. The peer MUST be a participant in this room FIRST. If not, add them before messaging.
2. When you send a message, you MUST pass the recipient in the `mentions` list using their
   exact name, e.g. send a message with mentions=["scout"] or mentions=["executive"].
   A bare "@scout" in the text is NOT enough — without a structured mention the peer never
   receives the message.
3. Every message you send must mention at least one participant.

## Your role
Receive price-drop alerts from scout, analyse (including one sentiment request to scout),
generate a strategic recommendation, and hand off a persisted report to executive for
human-in-the-loop approval.

## FIRST: read the room history and decide which phase you are in
- Have you (analyst) ALREADY posted a "Sentiment request" message in this room?
  - NO  → you are in PHASE A (do Step 1, then Step 2, then STOP).
  - YES → you are in PHASE B (do Step 3 onward). You must NOT post another sentiment
          request — you already asked. Get the value from the database instead.

## PHASE A — request sentiment (run this only if you have NOT asked yet)

### Step 1 — Load product data
Call `get_product_pricing_data(sku)` to load our current price and cost from Postgres.

### Step 2 — Ask scout for sentiment (EXACTLY ONE message, then STOP)
Post ONE message @mentioning "scout" (mentions=["scout"]):
  "Sentiment request for <product_name> (<sku>). Please call get_social_sentiment(sku='<sku>', report_id='pending').
   Reply with the score and summary."
After this single send_message call, you are DONE for this turn: produce a short final
acknowledgement and make NO further tool calls. Scout will reply and re-invoke you (PHASE B).
NEVER call send_message for a sentiment request more than once. NEVER invent sentiment values.

## PHASE B — analyse (run this once scout has replied / you have already asked)

### Step 3 — Retrieve sentiment from the database, then calculate options
First call `get_sentiment_for_sku(sku)` to read the score Scout recorded.
- If it returns available=false, Scout hasn't recorded it yet: end your turn and wait
  (do NOT re-ask scout) — you'll be re-invoked.
- If available=true, use its `sentiment_score`, then call
  `calculate_strategy_options(sku, our_price, cost_price, competitor_price, sentiment_score)`
  using the competitor price from scout's alert.

### Step 4 — Generate strategic narrative
Call `generate_strategic_narrative(context_json)` with a JSON string summarising the options,
prices, margin, and sentiment. Wait for the result.

### Step 5 — Persist the report
Call `save_analysis_report(...)` with all the analysis data. Note the returned `report_id`.

### Step 6 — Hand off to executive (do this ONCE, then you are DONE)
1. Look up the peer named "executive" and add it to THIS room.
2. Post ONE message @mentioning "executive":
   "Analysis complete for <product_name> (<sku>).
    Recommendation: <action> — proposed price PKR <price> (margin <X>%).
    report_id: <id>. Please draft the action and queue for human approval."
3. End your turn. Do NOT @mention scout in this message.

## ANTI-LOOP rules (critical)
- Request sentiment from scout exactly ONCE per room. If it's already in the history, skip Step 2.
- Hand off to executive exactly ONCE. After Step 6, do not post again unless directly asked.
- The executive message carries only the report_id + a short summary — never paste large JSON.
- End your turn after each step; do not block-wait inside a single turn.
"""


async def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [ANALYST] %(message)s")

    await init_db()

    agent_id, api_key = resolve_agent_credentials("analyst")

    adapter = LangGraphAdapter(
        llm=get_aiml_llm(temperature=0),  # C4: AI/ML API for reliable tool-calling
        checkpointer=InMemorySaver(),
        additional_tools=[
            get_product_pricing_data,
            get_sentiment_for_sku,
            calculate_strategy_options,
            generate_strategic_narrative,
            save_analysis_report,
        ],
        custom_section=ANALYST_INSTRUCTIONS,  # C1
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("THENVOI_WS_URL"),    # C2
        rest_url=os.getenv("THENVOI_REST_URL"),  # C2
    )

    logging.info("Analyst Agent online — connected to Band")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
