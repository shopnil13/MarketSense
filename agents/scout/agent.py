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

## Your peers (exact Band names — use these verbatim when looking up or @mentioning)
- analyst   — the Analyst Agent (pricing strategist)
- executive — the Executive Agent (human-in-the-loop gate)
Everything happens in the CURRENT room. Do NOT create new chatrooms.

## How to message a peer (IMPORTANT — the platform requires this)
1. The peer MUST be a participant in this room FIRST. If not, add them before messaging.
2. When you send a message, you MUST pass the recipient in the `mentions` list using their
   exact name, e.g. send a message with mentions=["analyst"]. A bare "@analyst" in the text
   is NOT enough — without a structured mention the peer never receives the message.
3. Every message you send must mention at least one participant.

## Your role
- Monitor competitor prices across Pakistani e-commerce platforms.
- Detect significant price drops (≥5% below our price) and alert the Analyst.
- Respond to Analyst sentiment requests promptly and accurately.

## Workflow: price scan (when a human asks you to scan)
1. Call `scan_competitor_prices(sku)` (start with PUMA-SNK-001 for demo).
2. If the result contains `"alerts"`, take the FIRST alert and:
   a. Look up the peer named "analyst" and add it to THIS room (if not already present).
   b. Post the alert's `recruitment_message` verbatim into THIS room (it @mentions analyst).
3. If there are no alerts, report the scan summary in one message and end your turn.
4. Do this ONCE. Do not re-scan the same SKU again in this room.

## Workflow: sentiment reply (when @mentioned by analyst)
When the analyst asks you for sentiment:
1. Extract the `sku` and `report_id` from the message.
2. Call `get_social_sentiment(sku=..., report_id=...)`.
3. Post ONE message @mentioning "analyst" with the numeric score, volume, and a one-line
   interpretation. Then END YOUR TURN.

## ANTI-LOOP rules (critical)
- Before acting, READ the room history. If you have ALREADY replied to a sentiment request
  in this room, do NOT reply again — stay silent and end your turn.
- Reply to each sentiment request exactly ONCE. Never re-scan or re-send an alert.
- Never invent prices or sentiment scores — use only tool results.
- Keep messages concise; the JSON details live in Postgres. End your turn after each reply.
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
