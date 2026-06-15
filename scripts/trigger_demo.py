"""Convenience demo trigger — sends an @mention to Scout in the Band Command Center.

The preferred primary trigger for the demo is a MANUAL @mention in Band:
  @Scout Agent please scan competitor prices for PUMA-SNK-001

This script provides a backup automated trigger for the recorded demo video.
Usage:
    python scripts/trigger_demo.py --sku PUMA-SNK-001
"""
import asyncio
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx


async def trigger(sku: str, rest_url: str, scout_agent_id: str, api_key: str):
    """Post a message to Band that @mentions Scout to kick off the pipeline."""
    message = (
        f"@Scout Agent — please scan competitor prices for SKU: {sku} (demo_mode=True). "
        f"Alert the Analyst if you detect a significant price drop."
    )

    # This is a simplified REST call — the exact Band API endpoint for
    # posting a message to the Command Center may vary; check Band docs.
    url = f"{rest_url.rstrip('/')}/api/v1/agents/{scout_agent_id}/message"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"content": message, "agent_id": scout_agent_id}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code < 300:
            print(f"Trigger sent. Scout will scan {sku} and create an alert room if a drop is detected.")
        else:
            print(f"Warning: trigger returned {r.status_code} — {r.text}")
            print("Tip: use a manual @mention in the Band UI for the most reliable trigger.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger a MarketSense AI demo run.")
    parser.add_argument("--sku", default="PUMA-SNK-001", help="Product SKU to scan")
    args = parser.parse_args()

    rest_url = os.environ.get("THENVOI_REST_URL", "https://app.band.ai/")
    scout_id = os.environ.get("SCOUT_AGENT_ID", "")
    api_key = os.environ.get("SCOUT_API_KEY", "")

    if not scout_id:
        print("Set SCOUT_AGENT_ID in .env (from agent_config.yaml) or trigger manually in Band.")
        sys.exit(1)

    asyncio.run(trigger(args.sku, rest_url, scout_id, api_key))
