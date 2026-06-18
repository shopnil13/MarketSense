"""Executive Agent — action drafting and human-in-the-loop queue."""
import asyncio
import os
import logging

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters.langgraph import LangGraphAdapter
from band.config.loader import load_agent_config  # C3

from core.llm import get_aiml_llm
from core.database import init_db
from agents.executive.tools import load_analysis_report, draft_action_content, queue_for_human_approval

EXECUTIVE_INSTRUCTIONS = """You are the Executive Agent for MarketSense AI — responsible for translating
analysis into governed, human-approved actions.

## Your role
Receive handoffs from the Analyst, load the full analysis from Postgres, draft a clear
action for human review, and queue it for HiTL approval. Nothing executes without a human.

Everything happens in the CURRENT room. Do NOT create new chatrooms.

## How to message a peer (IMPORTANT — the platform requires this)
- Every message you send MUST include at least one participant in the `mentions` list,
  using their exact name (e.g. mentions=["analyst"]). A message with no mention is rejected.

## Workflow (follow these steps in exact order)

### Step 1 — Load the analysis
Extract the `report_id` from the analyst's message.
Call `load_analysis_report(report_id=...)`.

### Step 2 — Draft the action content
Call `draft_action_content(...)` with the data returned from Step 1.
This produces a human-readable Markdown draft for the reviewer.

### Step 3 — Queue for human approval
Call `queue_for_human_approval(...)` with the draft from Step 2.
This persists the action in Postgres as "pending" and sends a Slack notification
with a link to the HiTL review dashboard.

### Step 4 — Report back in the Band room
Post ONE final message mentioning "analyst" (mentions=["analyst"]) to close the loop:
  "Action queued for human approval. Reviewer notified. Review URL: <url>
   Nothing will execute until approved. Full audit trail in Postgres."
This is your LAST action — after posting it, end your turn and do nothing further.

## ANTI-LOOP rules (critical)
- Queue each report_id exactly ONCE. If you have already queued this report in this room,
  do not queue it again — stay silent and end your turn.
- Never execute or simulate executing a price change — only queue for human review.
- Load data from Postgres via `load_analysis_report`; do not parse JSON from the chat message (§3.1).
- Keep Band messages concise — structured data lives in Postgres, not in chat.
"""


async def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [EXECUTIVE] %(message)s")

    await init_db()

    agent_id, api_key = load_agent_config("executive")

    adapter = LangGraphAdapter(
        llm=get_aiml_llm(temperature=0),
        checkpointer=InMemorySaver(),
        additional_tools=[load_analysis_report, draft_action_content, queue_for_human_approval],
        custom_section=EXECUTIVE_INSTRUCTIONS,  # C1
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("THENVOI_WS_URL"),     # C2
        rest_url=os.getenv("THENVOI_REST_URL"),   # C2
    )

    logging.info("Executive Agent online — connected to Band")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
