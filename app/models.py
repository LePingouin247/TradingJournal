from datetime import datetime
from typing import Optional
from sqlalchemy import Float, Integer, String, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # e.g. ["breakout", "morning"]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Fill(Base):
    """
    Raw Tradovate fill (execution). fill_id is Tradovate's own ID and
    carries a unique constraint to prevent duplicate inserts.
    """

    __tablename__ = "fills"
    __table_args__ = (UniqueConstraint("fill_id", name="uq_fills_fill_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fill_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    instrument: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)       # 'Buy' | 'Sell'
    pnl: Mapped[float] = mapped_column(Float, nullable=True)        # populated when available
