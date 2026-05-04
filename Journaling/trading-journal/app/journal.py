"""
Journaling helpers — update notes and tags on an existing trade.

Usage example:
    from app.database import SessionLocal
    from app.journal import update_notes, update_tags

    db = SessionLocal()
    update_notes(db, trade_id=1, notes="Strong breakout, held through first pullback.")
    update_tags(db, trade_id=1, tags=["breakout", "morning", "ES"])
    db.close()
"""

from typing import Optional
from sqlalchemy.orm import Session
from app.models import Trade


def update_notes(db: Session, trade_id: int, notes: Optional[str]) -> Trade:
    """
    Update the free-text notes on a trade.

    Parameters
    ----------
    db       : active database session
    trade_id : the id of the trade to edit
    notes    : new notes text (pass None to clear)

    Returns the updated Trade, or raises ValueError if not found.
    """
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found.")

    trade.notes = notes
    db.commit()
    db.refresh(trade)
    return trade


def update_tags(db: Session, trade_id: int, tags: Optional[list[str]]) -> Trade:
    """
    Replace the tags list on a trade.

    Parameters
    ----------
    db       : active database session
    trade_id : the id of the trade to edit
    tags     : list of tag strings, e.g. ["breakout", "morning"]
               Pass None or [] to clear all tags.

    Returns the updated Trade, or raises ValueError if not found.
    """
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if trade is None:
        raise ValueError(f"Trade {trade_id} not found.")

    trade.tags = tags or []
    db.commit()
    db.refresh(trade)
    return trade
