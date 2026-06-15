"""Competitor price scraper — mock-first with best-effort live fallback.

Demo always uses mock data for reliability (§5 of the implementation plan).
The live path (httpx + BeautifulSoup + tenacity retry) is wired and falls back
cleanly. Production would swap in Playwright or official retailer feeds.
"""
import asyncio
import random
import datetime
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

from core.config import settings


@dataclass
class CompetitorPrice:
    competitor_name: str
    price: float
    url: Optional[str] = None
    source: str = "mock"


# Deterministic mock catalogue — realistic Pakistani e-commerce prices (PKR)
_MOCK_CATALOGUE: dict[str, list[CompetitorPrice]] = {
    "PUMA-SNK-001": [
        CompetitorPrice("Daraz", 8500, source="mock"),
        CompetitorPrice("Goto", 8800, source="mock"),
        CompetitorPrice("Naheed", 9100, source="mock"),
    ],
    "NIKE-AIR-002": [
        CompetitorPrice("Daraz", 12500, source="mock"),
        CompetitorPrice("Goto", 12800, source="mock"),
    ],
    "ADIDAS-RUN-003": [
        CompetitorPrice("Daraz", 9800, source="mock"),
        CompetitorPrice("Goto", 10000, source="mock"),
        CompetitorPrice("Naheed", 10200, source="mock"),
    ],
}


def get_mock_prices(sku: str, drop_competitor: Optional[str] = None, drop_pct: float = 0.15) -> list[CompetitorPrice]:
    """Return mock prices; optionally simulate a drop for demo triggering."""
    base = _MOCK_CATALOGUE.get(sku, [])
    results = []
    for entry in base:
        price = entry.price
        if drop_competitor and entry.competitor_name == drop_competitor:
            price = round(price * (1 - drop_pct), 2)
        results.append(CompetitorPrice(entry.competitor_name, price, entry.url, "mock"))
    return results


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, Exception)),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=False,
)
async def _try_live_scrape(url: str, competitor_name: str) -> Optional[CompetitorPrice]:
    """Best-effort live scrape — not used during demo (JS-heavy SPAs block BS4)."""
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Generic price selector — retailer-specific selectors belong here
        tag = soup.select_one("[class*='price']")
        if tag:
            raw = tag.get_text(strip=True).replace("Rs", "").replace(",", "").strip()
            price = float(raw)
            return CompetitorPrice(competitor_name, price, url, "live")
    return None


async def get_competitor_prices(
    sku: str,
    competitors: list[dict],  # [{"name": "Daraz", "url": "..."}]
    *,
    use_live: bool = False,
    demo_drop_competitor: Optional[str] = None,
    demo_drop_pct: float = 0.15,
) -> list[CompetitorPrice]:
    """Return competitor prices. Mock-first; live attempted only when use_live=True."""
    if not use_live:
        return get_mock_prices(sku, demo_drop_competitor, demo_drop_pct)

    results = []
    tasks = [_try_live_scrape(c["url"], c["name"]) for c in competitors if c.get("url")]
    live_results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, res in enumerate(live_results):
        if isinstance(res, CompetitorPrice):
            results.append(res)
        else:
            # Live failed — fall back to mock for this competitor
            name = competitors[i]["name"]
            logger.warning(f"Live scrape failed for {name} ({sku}), using mock. Error: {res}")
            mock = next((p for p in get_mock_prices(sku) if p.competitor_name == name), None)
            if mock:
                results.append(mock)

    return results or get_mock_prices(sku, demo_drop_competitor, demo_drop_pct)
