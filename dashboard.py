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
            creds = {
                "username": st.secrets["TRADOVATE_USERNAME"],
                "password": st.secrets["TRADOVATE_PASSWORD"],
                "app_id": st.secrets.get("TRADOVATE_APP_ID", "Sample App"),
                "app_version": st.secrets.get("TRADOVATE_APP_VERSION", "1.0"),
                "cid": int(st.secrets.get("TRADOVATE_CID", "8")),
                "secret": st.secrets["TRADOVATE_SECRET"],
                "env": st.secrets.get("TRADOVATE_ENV", "live"),
            }
            from app.tradovate.auth import get_valid_token
            from app.tradovate.client import TradovateClient
            client = TradovateClient(credentials=creds)
            raw_fills = client.get_fills()
            with Session() as db:
                inserted, skipped = insert_fills(db, raw_fills)
            st.success(f"Sync complete — {inserted} new fill(s) added, {skipped} duplicate(s) skipped.")
            st.rerun()
        except KeyError as exc:
            st.error(f"Missing secret: {exc}. Add it in the Streamlit app settings under Secrets.")
        except Exception as exc:
            st.error(f"Sync failed: {exc}")

st.divider()

# --- CSV Import ---
st.header("Import Fills from CSV")
st.caption("Export your executions from Tradovate (Reports → Executions → Export) and upload the CSV here.")

uploaded = st.file_uploader("Choose a Tradovate CSV file", type="csv")
if uploaded:
    try:
        raw = pd.read_csv(uploaded)
        st.write("Detected columns:", list(raw.columns))

        col_map = {c.lower().strip(): c for c in raw.columns}

        def find_col(*candidates):
            for c in candidates:
                if c in col_map:
                    return col_map[c]
            return None

        id_col        = find_col("id", "fillid", "fill id", "orderid", "order id")
        ts_col        = find_col("timestamp", "date/time", "datetime", "time", "date")
        inst_col      = find_col("contract", "symbol", "instrument", "name")
        price_col     = find_col("price", "fill price", "execprice")
        qty_col       = find_col("qty", "quantity", "size", "filled qty")
        side_col      = find_col("action", "side", "b/s", "buy/sell", "direction")
        pnl_col       = find_col("realizedpnl", "realized pnl", "pnl", "realized", "p&l")

        missing = [n for n, c in [("id", id_col), ("timestamp", ts_col), ("contract", inst_col),
                                   ("price", price_col), ("qty", qty_col), ("side", side_col)] if c is None]
        if missing:
            st.error(f"Could not find columns for: {missing}. Please check the column names above.")
        else:
            fills_to_insert = []
            for i, row in raw.iterrows():
                fills_to_insert.append({
                    "id": int(row[id_col]) if id_col else i,
                    "timestamp": str(row[ts_col]),
                    "contractId": str(row[inst_col]),
                    "price": float(row[price_col]),
                    "qty": float(row[qty_col]),
                    "action": str(row[side_col]),
                    "realisedPnl": float(row[pnl_col]) if pnl_col and pd.notna(row[pnl_col]) else None,
                })

            st.dataframe(raw.head(5), use_container_width=True)
            if st.button("Import into Journal", type="primary"):
                with Session() as db:
                    inserted, skipped = insert_fills(db, fills_to_insert)
                st.success(f"Imported {inserted} new fill(s), {skipped} duplicate(s) skipped.")
                st.rerun()
    except Exception as exc:
        st.error(f"Failed to parse CSV: {exc}")

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
