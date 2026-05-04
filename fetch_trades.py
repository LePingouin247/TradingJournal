"""
Fetch Tradovate trade executions and store them in journal.db.

Before running:
  1. Copy .env.example to .env
  2. Fill in your Tradovate credentials
  3. Run:  python fetch_trades.py
"""

from app.database import engine, SessionLocal
from app import models
from app.tradovate.client import TradovateClient
from app.fills import insert_fills, fetch_all_fills

# Ensure the fills table exists
models.Base.metadata.create_all(bind=engine)


def main() -> None:
    client = TradovateClient.from_env()

    print("Fetching accounts...")
    for acct in client.get_accounts():
        print(f"  {acct.get('name')} (id={acct.get('id')})")

    print("\nFetching trade executions (fills)...")
    fills = client.get_fills()

    if not fills:
        print("  No fills found.")
        return

    print(f"  Retrieved {len(fills)} fill(s) from Tradovate.")

    with SessionLocal() as db:
        inserted, skipped = insert_fills(db, fills)
        print(f"  Stored: {inserted} new  |  Skipped (duplicates): {skipped}")

        print("\nAll fills in database:")
        print(f"{'DB-ID':<6} {'Fill-ID':<10} {'Instrument':<15} {'Side':<5} "
              f"{'Qty':<6} {'Price':<10} {'PnL':<10} {'Timestamp'}")
        print("-" * 80)
        for row in fetch_all_fills(db):
            pnl_str = f"{row.pnl:.2f}" if row.pnl is not None else "-"
            print(
                f"{row.id:<6} {row.fill_id:<10} {row.instrument:<15} "
                f"{row.side:<5} {row.quantity:<6} {row.price:<10} "
                f"{pnl_str:<10} {row.timestamp}"
            )


if __name__ == "__main__":
    main()
