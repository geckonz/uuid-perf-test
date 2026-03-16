"""CLI: Load benchmark CSV data into MongoDB using bulk insert_many.

Usage:
    uv run python -m loaders.load_mongo

Loads uuid_v4 collections first, then uuid_v7.
UUIDs are stored as bson.Binary (subtype 4) for correct ordering semantics.
"""

import csv
import json
import time
import uuid as _uuid_mod
from datetime import datetime, timezone
from pathlib import Path

import bson
import pymongo

from config.settings import (
    ACCOUNTS_V4_CSV,
    ACCOUNTS_V7_CSV,
    CUSTOMERS_V4_CSV,
    CUSTOMERS_V7_CSV,
    MONGO_DB_NAME,
    MONGO_INSERT_BATCH,
    MONGO_URL,
    RESULTS_DIR,
)


def _str_to_binary(uuid_str: str) -> bson.Binary:
    """Convert a UUID hex string to BSON Binary subtype 4."""
    return bson.Binary(_uuid_mod.UUID(uuid_str).bytes, subtype=4)


def _parse_customer(row: dict) -> dict:
    return {
        "_id": _str_to_binary(row["id"]),
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "address": row["address"],
        "created_at": datetime.fromisoformat(row["created_at"]),
        "updated_at": datetime.fromisoformat(row["updated_at"]),
    }


def _parse_account(row: dict) -> dict:
    return {
        "_id": _str_to_binary(row["id"]),
        "customer_id": _str_to_binary(row["customer_id"]),
        "account_type": row["account_type"],
        "balance": float(row["balance"]),
        "currency": row["currency"],
        "status": row["status"],
        "opened_at": datetime.fromisoformat(row["opened_at"]),
        "updated_at": datetime.fromisoformat(row["updated_at"]),
    }


def _bulk_insert_csv(
    collection: pymongo.collection.Collection,
    csv_path: Path,
    parse_fn,
    batch_size: int = MONGO_INSERT_BATCH,
    label: str = "",
) -> float:
    """Read CSV, parse rows, and insert_many in batches. Returns elapsed seconds."""
    start = time.monotonic()
    batch = []
    total = 0

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            batch.append(parse_fn(row))
            if len(batch) >= batch_size:
                collection.insert_many(batch, ordered=False)
                total += len(batch)
                batch = []
                if total % 500_000 == 0:
                    elapsed = time.monotonic() - start
                    print(
                        f"    {label}: {total:,} rows — {elapsed:.1f}s "
                        f"({total / elapsed:,.0f} rows/s)",
                        flush=True,
                    )

    if batch:
        collection.insert_many(batch, ordered=False)
        total += len(batch)

    elapsed = time.monotonic() - start
    print(f"  {label}: {total:,} rows in {elapsed:.2f}s ({total / elapsed:,.0f} rows/s)")
    return elapsed


def load_prefix(
    db: pymongo.database.Database,
    prefix: str,
    customers_csv: Path,
    accounts_csv: Path,
) -> dict:
    """Load one prefix (uuid_v4 or uuid_v7). Returns timing dict."""
    print(f"\n=== Loading {prefix} ===")
    timings: dict = {}

    cust_col_name = f"{prefix}.customers"
    acct_col_name = f"{prefix}.accounts"

    # Drop and recreate collections
    db.drop_collection(cust_col_name)
    db.drop_collection(acct_col_name)

    cust_col = db[cust_col_name]
    acct_col = db[acct_col_name]

    # Create secondary indexes
    cust_col.create_index("email", unique=True, background=True)
    cust_col.create_index("created_at", background=True)
    acct_col.create_index("customer_id", background=True)
    acct_col.create_index("opened_at", background=True)
    acct_col.create_index("status", background=True)

    # Bulk insert customers
    timings["insert_customers"] = _bulk_insert_csv(
        cust_col, customers_csv, _parse_customer, label=f"{prefix}.customers"
    )

    # Bulk insert accounts
    timings["insert_accounts"] = _bulk_insert_csv(
        acct_col, accounts_csv, _parse_account, label=f"{prefix}.accounts"
    )

    # Optional compact (defragment)
    print(f"  Running compact on {cust_col_name}...")
    start = time.monotonic()
    try:
        db.command("compact", cust_col_name)
        timings["compact_customers"] = time.monotonic() - start
    except Exception as e:
        print(f"  compact skipped: {e}")
        timings["compact_customers"] = None

    print(f"  {prefix} load complete.")
    return timings


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    client = pymongo.MongoClient(MONGO_URL)
    db = client[MONGO_DB_NAME]

    all_timings: dict = {}

    all_timings["uuid_v4"] = load_prefix(db, "uuid_v4", CUSTOMERS_V4_CSV, ACCOUNTS_V4_CSV)
    all_timings["uuid_v7"] = load_prefix(db, "uuid_v7", CUSTOMERS_V7_CSV, ACCOUNTS_V7_CSV)

    client.close()

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"load_timings_{ts}_mongo.json"
    out_path.write_text(json.dumps(all_timings, indent=2, default=str))
    print(f"\nLoad timings saved → {out_path}")


if __name__ == "__main__":
    main()
