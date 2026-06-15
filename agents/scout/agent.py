"""Scout Agent — competitive price monitoring and sentiment retrieval."""
import asyncio
import os
import logging

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config.loader import load_agent_config  # C3: SDK loader, no pyyaml needed

from core.llm import get_aiml_llm
from core.database import init_db
from agents.scout.tools import scan_competitor_prices, get_social_sentiment

SCOUT_INSTRUCTIONS = """You are the Scout Agent for MarketSense AI — a competitive intelligence specialist.

## Your role
- Monitor competitor prices across Pakistani e-commerce platforms.
- Detect significant price drops (≥5% below our price) and alert the Analyst.
- Respond to Analyst sentiment requests promptly and accurately.

## Workflow: price scan
1. Call `scan_competitor_prices(sku)` for each SKU you're monitoring (start with PUMA-SNK-001 for demo).
2. If the result contains `"alerts"`, for each alert:
   a. Create a Band chatroom using the `room_name` from the alert payload.
   b. Look up "Analyst Agent" in the Band peer directory.
   c. Add Analyst Agent to the room.
   d. Send the `recruitment_message` verbatim — do NOT rewrite it.
3. If no alert, report the scan results and stop.

## Workflow: sentiment reply (when @mentioned by Analyst)
When the Analyst sends you a sentiment request:
1. Extract the `sku` and `report_id` from the message.
2. Call `get_social_sentiment(sku=..., report_id=...)`.
3. @mention "Analyst Agent" with the result as a concise summary.
4. Include the numeric score and a one-line interpretation. End your turn.

## Critical rules
- Never invent prices or sentiment scores — use only tool results.
- Keep your Band messages concise and human-readable; the JSON details live in Postgres.
- End your turn after fulfilling a request; do not wait inside a single turn.
"""


async def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [SCOUT] %(message)s")

    await init_db()

    agent_id, api_key = load_agent_config("scout")

    adapter = LangGraphAdapter(
        llm=get_aiml_llm(temperature=0),
        checkpointer=InMemorySaver(),
        additional_tools=[scan_competitor_prices, get_social_sentiment],
        custom_section=SCOUT_INSTRUCTIONS,  # C1: custom_section, NOT system_prompt
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("THENVOI_WS_URL"),   # C2
        rest_url=os.getenv("THENVOI_REST_URL"),  # C2
    )

    logging.info("Scout Agent online — connected to Band")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
