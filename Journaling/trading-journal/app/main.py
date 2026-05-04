from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import engine, get_db, Base
from app import models
from app.journal import update_notes, update_tags

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Trading Journal")


# --- Schemas ---

class TradeCreate(BaseModel):
    symbol: str
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class TradeResponse(TradeCreate):
    id: int
    created_at: str

    class Config:
        from_attributes = True


class NotesUpdate(BaseModel):
    notes: Optional[str] = None


class TagsUpdate(BaseModel):
    tags: list[str] = []


# --- Routes ---

@app.get("/")
def root():
    return {"message": "Trading Journal API is running"}


@app.post("/trades", response_model=TradeResponse, status_code=201)
def create_trade(trade: TradeCreate, db: Session = Depends(get_db)):
    new_trade = models.Trade(**trade.model_dump())
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return new_trade


@app.get("/trades", response_model=list[TradeResponse])
def list_trades(db: Session = Depends(get_db)):
    return db.query(models.Trade).all()


@app.get("/trades/{trade_id}", response_model=TradeResponse)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@app.patch("/trades/{trade_id}/notes", response_model=TradeResponse)
def patch_notes(trade_id: int, body: NotesUpdate, db: Session = Depends(get_db)):
    """Update the journal notes for a trade."""
    try:
        return update_notes(db, trade_id=trade_id, notes=body.notes)
    except ValueError:
        raise HTTPException(status_code=404, detail="Trade not found")


@app.patch("/trades/{trade_id}/tags", response_model=TradeResponse)
def patch_tags(trade_id: int, body: TagsUpdate, db: Session = Depends(get_db)):
    """Replace the tags list for a trade."""
    try:
        return update_tags(db, trade_id=trade_id, tags=body.tags)
    except ValueError:
        raise HTTPException(status_code=404, detail="Trade not found")


@app.delete("/trades/{trade_id}", status_code=204)
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(trade)
    db.commit()
