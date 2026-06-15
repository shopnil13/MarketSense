import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=True)
    our_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    cost_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    competitors: Mapped[list["Competitor"]] = relationship(back_populates="product")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(back_populates="product")
    sentiment_records: Mapped[list["SentimentRecord"]] = relationship(back_populates="product")
    analysis_reports: Mapped[list["AnalysisReport"]] = relationship(back_populates="product")


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    competitor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="competitors")
    snapshots: Mapped[list["PriceSnapshot"]] = relationship(back_populates="competitor")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    competitor_id: Mapped[str] = mapped_column(ForeignKey("competitors.id"), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    source: Mapped[str] = mapped_column(String(32), default="mock")  # "mock" | "live"

    product: Mapped["Product"] = relationship(back_populates="price_snapshots")
    competitor: Mapped["Competitor"] = relationship(back_populates="snapshots")


class SentimentRecord(Base):
    __tablename__ = "sentiment_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)  # -1.0 to 1.0
    volume: Mapped[int] = mapped_column(nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="sentiment_records")


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_event: Mapped[dict] = mapped_column(JSON, nullable=True)
    price_comparison: Mapped[dict] = mapped_column(JSON, nullable=True)
    recommended_action: Mapped[str] = mapped_column(String(64), nullable=True)  # "match" | "undercut" | "hold"
    proposed_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    expected_margin: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    strategic_narrative: Mapped[str] = mapped_column(Text, nullable=True)
    llm_recommendation: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="analysis_reports")
    pending_actions: Mapped[list["PendingAction"]] = relationship(back_populates="report")


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("analysis_reports.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)  # "price_change" | etc.
    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    draft_content: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # "pending" | "approved" | "rejected"
    reviewer_note: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    report: Mapped["AnalysisReport"] = relationship(back_populates="pending_actions")
