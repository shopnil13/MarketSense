"""Pydantic schemas for inter-agent message contracts passed via Band."""
from typing import Optional
from pydantic import BaseModel


class PriceDropEvent(BaseModel):
    """Scout → Analyst: a significant competitor price drop was detected."""
    sku: str
    product_name: str
    our_price: float
    competitor_name: str
    competitor_price: float
    drop_pct: float
    event_id: str  # PriceSnapshot.id for Postgres lookup
    room_name: str
    recruitment_message: str  # ready-to-relay Band message (§3.5)


class SentimentRequest(BaseModel):
    """Analyst → Scout: request social sentiment for a product."""
    sku: str
    product_name: str
    report_id: str  # so Scout can include it in the reply


class SentimentReply(BaseModel):
    """Scout → Analyst: sentiment result."""
    report_id: str
    sku: str
    score: float       # -1.0 to 1.0
    volume: int
    summary: str


class AnalysisHandoff(BaseModel):
    """Analyst → Executive: analysis complete, ready for action draft."""
    report_id: str
    sku: str
    product_name: str
    recommended_action: str
    proposed_price: float
    expected_margin: float
    summary: str  # human-readable one-liner for Band room
