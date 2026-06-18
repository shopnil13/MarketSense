"""Analyst Agent — pricing strategy analysis with bidirectional Scout collaboration."""
import asyncio
import os
import logging

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config.loader import load_agent_config  # C3

from core.llm import get_aiml_llm  # C4: Analyst brain stays on AI/ML API
from core.database import init_db
from agents.analyst.tools import (
    get_product_pricing_data,
    calculate_strategy_options,
    generate_strategic_narrative,
    save_analysis_report,
)

ANALYST_INSTRUCTIONS = """You are the Analyst Agent for MarketSense AI — a senior pricing strategist.

## Your role
Receive price-drop alerts from Scout, conduct analysis (including requesting social sentiment
from Scout), generate a strategic recommendation via an open-source model, and hand off a
persisted report to the Executive for human-in-the-loop approval.

## Workflow (follow these steps in order)

### Step 1 — Load product data
Call `get_product_pricing_data(sku)` to load our current price and cost from Postgres.

### Step 2 — Request social sentiment from Scout
@mention "Scout Agent" with:
  "Sentiment request for <product_name> (<sku>). Please call get_social_sentiment(sku='<sku>', report_id='pending').
   Reply with score and summary."

Then **stop and end your turn**. Scout will reply in this room, which will re-invoke you.
**Only continue to Step 3 after you have received Scout's reply.**
**Never invent sentiment values — if you haven't received Scout's reply, you are not done.**

### Step 3 — Calculate strategy options (after receiving Scout's sentiment)
Call `calculate_strategy_options(sku, our_price, cost_price, competitor_price, sentiment_score)`
using the competitor price from the Scout alert and the sentiment score from Scout's reply.

### Step 4 — Generate strategic narrative
Call `generate_strategic_narrative(context_json)` with a JSON string summarising the options,
prices, margin, and sentiment. This is a bounded reasoning call — wait for the result.

### Step 5 — Persist the report
Call `save_analysis_report(...)` with all the analysis data. Note the returned `report_id`.

### Step 6 — Recruit Executive and hand off
1. Look up "Executive Agent" in the Band peer directory.
2. Add Executive Agent to this room.
3. @mention "Executive Agent" with a concise summary:
   "Analysis complete for <product_name> (<sku>).
    Recommendation: <action> — proposed price PKR <price> (margin <X>%).
    report_id: <id>. Please draft the action and queue for human approval."
4. End your turn.

## Critical rules
- The Band message to Executive carries only the report_id + human-readable summary.
  The full structured data is in Postgres — do NOT paste large JSON into Band messages.
- End your turn after each request; do not block-wait inside a single turn.
- Never skip the sentiment step — genuine bidirectional Scout collaboration is required.
"""


async def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [ANALYST] %(message)s")

    await init_db()

    agent_id, api_key = load_agent_config("analyst")

    adapter = LangGraphAdapter(
        llm=get_aiml_llm(temperature=0),  # C4: AI/ML API for reliable tool-calling
        checkpointer=InMemorySaver(),
        additional_tools=[
            get_product_pricing_data,
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
