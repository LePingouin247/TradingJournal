import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.tradovate.client import TradovateClient
from app.fills import insert_fills

DB_PATH = os.path.join(os.path.dirname(__file__), "journal.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)


def load_trades() -> pd.DataFrame:
    with Session() as db:
        rows = db.execute(
            __import__("sqlalchemy").text(
                "SELECT id, symbol, entry_price, exit_price, quantity, notes, tags, created_at FROM trades ORDER BY created_at DESC"
            )
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["id", "symbol", "entry_price", "exit_price", "quantity", "pnl", "notes", "tags", "created_at"])

    df = pd.DataFrame(rows, columns=["id", "symbol", "entry_price", "exit_price", "quantity", "notes", "tags", "created_at"])
    df["pnl"] = (df["exit_price"] - df["entry_price"]) * df["quantity"]
    df["tags"] = df["tags"].apply(lambda t: ", ".join(t) if isinstance(t, list) else (t or ""))
    return df


def load_fills() -> pd.DataFrame:
    with Session() as db:
        rows = db.execute(
            __import__("sqlalchemy").text(
                "SELECT id, fill_id, timestamp, instrument, price, quantity, side, pnl FROM fills ORDER BY timestamp DESC"
            )
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["id", "fill_id", "timestamp", "instrument", "price", "quantity", "side", "pnl"])
    return pd.DataFrame(rows, columns=["id", "fill_id", "timestamp", "instrument", "price", "quantity", "side", "pnl"])


def save_trade_edits(trade_id: int, notes: str, tags_str: str):
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    with Session() as db:
        import sqlalchemy
        db.execute(
            sqlalchemy.text("UPDATE trades SET notes = :notes, tags = :tags WHERE id = :id"),
            {"notes": notes or None, "tags": __import__("json").dumps(tags), "id": trade_id},
        )
        db.commit()


st.set_page_config(page_title="Trading Journal", layout="wide")
st.title("Trading Journal")

trades_df = load_trades()
fills_df = load_fills()

# --- Stats ---
st.header("Stats")
col1, col2, col3 = st.columns(3)

with col1:
    total_pnl = trades_df["pnl"].sum() if not trades_df.empty else 0.0
    st.metric("Total P&L", f"${total_pnl:,.2f}")

with col2:
    num_trades = len(trades_df)
    st.metric("Total Trades", num_trades)

with col3:
    if not trades_df.empty and trades_df["pnl"].notna().any():
        wins = (trades_df["pnl"] > 0).sum()
        closed = trades_df["pnl"].notna().sum()
        win_rate = wins / closed * 100 if closed > 0 else 0.0
        st.metric("Win Rate", f"{win_rate:.1f}%")
    else:
        st.metric("Win Rate", "N/A")

st.divider()

# --- Trades table ---
st.header("Trades")

if trades_df.empty:
    st.info("No trades found in the database.")
else:
    display_cols = ["id", "symbol", "entry_price", "exit_price", "quantity", "pnl", "notes", "tags", "created_at"]
    st.dataframe(
        trades_df[display_cols].style.format(
            {"entry_price": "{:.4f}", "exit_price": "{:.4f}", "pnl": "{:.2f}"}
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Edit Notes / Tags")
    trade_options = {f"#{row.id} — {row.symbol}": row.id for row in trades_df.itertuples()}
    selected_label = st.selectbox("Select trade", list(trade_options.keys()))
    selected_id = trade_options[selected_label]
    row = trades_df[trades_df["id"] == selected_id].iloc[0]

    notes_input = st.text_area("Notes", value=row["notes"] or "")
    tags_input = st.text_input("Tags (comma-separated)", value=row["tags"] or "")

    if st.button("Save"):
        save_trade_edits(selected_id, notes_input, tags_input)
        st.success("Saved.")
        st.rerun()

st.divider()

# --- Sync Trades ---
st.header("Sync Trades")
if st.button("Sync Trades from Tradovate", type="primary"):
    with st.spinner("Fetching fills from Tradovate..."):
        try:
            client = TradovateClient.from_env()
            raw_fills = client.get_fills()
            with Session() as db:
                inserted, skipped = insert_fills(db, raw_fills)
            st.success(f"Sync complete — {inserted} new fill(s) added, {skipped} duplicate(s) skipped.")
            st.rerun()
        except KeyError as exc:
            st.error(f"Missing environment variable: {exc}. Check your .env file.")
        except Exception as exc:
            st.error(f"Sync failed: {exc}")

st.divider()

# --- Fills table ---
st.header("Fills")

if fills_df.empty:
    st.info("No fills found in the database.")
else:
    fills_pnl_total = fills_df["pnl"].sum(skipna=True)
    st.caption(f"Total fills P&L: ${fills_pnl_total:,.2f}")
    st.dataframe(
        fills_df.drop(columns=["id"]).style.format({"price": "{:.4f}", "pnl": "{:.2f}"}),
        use_container_width=True,
        hide_index=True,
    )
