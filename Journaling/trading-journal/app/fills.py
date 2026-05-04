"""
CRUD helpers for Tradovate fills.

Schema (fills table):
    id          INTEGER  PRIMARY KEY
    fill_id     INTEGER  UNIQUE NOT NULL   -- Tradovate's own execution ID
    timestamp   DATETIME NOT NULL
    instrument  TEXT     NOT NULL
    price       REAL     NOT NULL
    quantity    REAL     NOT NULL
    side        TEXT     NOT NULL          -- 'Buy' | 'Sell'
    pnl         REAL                       -- nullable; set when known
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Fill


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

def insert_fill(
    db: Session,
    *,
    fill_id: int,
    timestamp: datetime,
    instrument: str,
    price: float,
    quantity: float,
    side: str,
    pnl: Optional[float] = None,
) -> Fill | None:
    """
    Insert a single fill. Returns the new Fill row, or None if fill_id
    already exists (duplicate silently skipped).
    """
    row = Fill(
        fill_id=fill_id,
        timestamp=timestamp,
        instrument=instrument,
        price=price,
        quantity=quantity,
        side=side,
        pnl=pnl,
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        return None


def insert_fills(db: Session, fills: list[dict]) -> tuple[int, int]:
    """
    Bulk-insert Tradovate fill dicts (as returned by TradovateClient.get_fills()).
    Returns (inserted, skipped) counts.

    Expected keys per dict:
        id          – Tradovate fill ID
        timestamp   – ISO-8601 string  e.g. "2024-01-15T14:30:00Z"
        contractId  – instrument identifier
        price       – fill price
        qty         – quantity
        action      – 'Buy' | 'Sell'
        realisedPnl – optional realised P&L
    """
    inserted = skipped = 0
    for f in fills:
        ts_raw = f.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            ts = datetime.utcnow()

        result = insert_fill(
            db,
            fill_id=int(f["id"]),
            timestamp=ts,
            instrument=str(f.get("contractId", "")),
            price=float(f.get("price", 0.0)),
            quantity=float(f.get("qty", 0.0)),
            side=str(f.get("action", "")),
            pnl=f.get("realisedPnl"),
        )
        if result is None:
            skipped += 1
        else:
            inserted += 1

    return inserted, skipped


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_all_fills(db: Session) -> list[Fill]:
    """Return all fills ordered by timestamp ascending."""
    return db.query(Fill).order_by(Fill.timestamp).all()


def fetch_fill_by_id(db: Session, fill_id: int) -> Fill | None:
    """Look up a fill by Tradovate's fill_id."""
    return db.query(Fill).filter(Fill.fill_id == fill_id).first()
