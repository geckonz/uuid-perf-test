"""CLI: Generate all benchmark data to CSV files.

Usage:
    uv run python -m generators.generate_csv [--scale FLOAT]

--scale: Fraction of full data to generate (default 1.0).
         Use 0.001 for a quick smoke test (~5k customers, ~7k accounts).
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

from config.settings import (
    ACCOUNTS_V4_CSV,
    ACCOUNTS_V7_CSV,
    CUSTOMERS_V4_CSV,
    CUSTOMERS_V7_CSV,
    CUSTOMER_IDS_V4_NPY,
    CUSTOMER_IDS_V7_NPY,
    DATA_DIR,
    NUM_ACCOUNTS,
    NUM_CUSTOMERS,
)
from generators.data_factory import account_fields, customer_fields
from generators.distribution import build_account_counts
from generators.uuid_factory import new_uuid4, new_uuid7

CUSTOMER_FIELDNAMES = ["id", "name", "email", "phone", "address", "created_at", "updated_at"]
ACCOUNT_FIELDNAMES = [
    "id",
    "customer_id",
    "account_type",
    "balance",
    "currency",
    "status",
    "opened_at",
    "updated_at",
]


def _progress(current: int, total: int, label: str, start: float) -> None:
    pct = current / total * 100
    elapsed = time.monotonic() - start
    rate = current / elapsed if elapsed > 0 else 0
    print(
        f"\r  {label}: {current:,}/{total:,} ({pct:.1f}%) — {rate:,.0f} rows/s",
        end="",
        flush=True,
    )


def generate_customers(
    num_customers: int,
    uuid_fn,
    csv_path: Path,
    npy_path: Path,
    label: str,
) -> np.ndarray:
    """Generate customer rows, write CSV, and save UUIDs as .npy."""
    print(f"Generating {num_customers:,} {label} customers → {csv_path.name}")
    start = time.monotonic()

    uuid_strs = []
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CUSTOMER_FIELDNAMES)
        writer.writeheader()
        for i in range(num_customers):
            fields, ts = customer_fields()
            uid = uuid_fn(ts)
            
            uid_str = str(uid)
            uuid_strs.append(uid_str)
            row = {"id": uid_str, **fields}
            writer.writerow(row)
            if (i + 1) % 100_000 == 0:
                _progress(i + 1, num_customers, label, start)

    print()  # newline after progress
    elapsed = time.monotonic() - start
    print(f"  Done in {elapsed:.1f}s ({num_customers / elapsed:,.0f} rows/s)")

    id_array = np.array(uuid_strs, dtype="U36")
    np.save(npy_path, id_array)
    print(f"  Saved UUID cache → {npy_path.name}")
    return id_array


def generate_accounts(
    customer_ids: np.ndarray,
    num_accounts: int,
    uuid_fn,
    csv_path: Path,
    label: str,
) -> None:
    """Generate account rows using the given customer_ids array."""
    num_customers = len(customer_ids)
    account_counts = build_account_counts(num_customers, num_accounts)

    print(f"Generating {num_accounts:,} {label} accounts → {csv_path.name}")
    start = time.monotonic()
    written = 0

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ACCOUNT_FIELDNAMES)
        writer.writeheader()
        for cust_idx, count in enumerate(account_counts):
            cust_id = customer_ids[cust_idx]
            for _ in range(count):
                fields, ts = account_fields()
                uid = uuid_fn(ts)
                
                row = {"id": str(uid), "customer_id": cust_id, **fields}
                writer.writerow(row)
                written += 1
            if (cust_idx + 1) % 100_000 == 0:
                _progress(written, num_accounts, label, start)

    print()
    elapsed = time.monotonic() - start
    print(f"  Done in {elapsed:.1f}s ({num_accounts / elapsed:,.0f} rows/s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate UUID benchmark CSV data")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Fraction of full dataset to generate (default: 1.0)",
    )
    args = parser.parse_args()

    if not (0 < args.scale <= 1.0):
        print("Error: --scale must be between 0 (exclusive) and 1.0 (inclusive)", file=sys.stderr)
        sys.exit(1)

    num_customers = max(1, int(NUM_CUSTOMERS * args.scale))
    num_accounts = max(1, int(NUM_ACCOUNTS * args.scale))

    print(f"Scale: {args.scale} → {num_customers:,} customers, {num_accounts:,} accounts")
    print(f"Output directory: {DATA_DIR}")
    print()

    total_start = time.monotonic()

    # --- v4 customers ---
    v4_ids = generate_customers(
        num_customers, new_uuid4, CUSTOMERS_V4_CSV, CUSTOMER_IDS_V4_NPY, "v4"
    )
    print()

    # --- v7 customers ---
    v7_ids = generate_customers(
        num_customers, new_uuid7, CUSTOMERS_V7_CSV, CUSTOMER_IDS_V7_NPY, "v7"
    )
    print()

    # --- v4 accounts ---
    generate_accounts(v4_ids, num_accounts, new_uuid4, ACCOUNTS_V4_CSV, "v4")
    print()

    # --- v7 accounts ---
    generate_accounts(v7_ids, num_accounts, new_uuid7, ACCOUNTS_V7_CSV, "v7")
    print()

    total_elapsed = time.monotonic() - total_start
    print(f"All CSV files generated in {total_elapsed:.1f}s total.")


if __name__ == "__main__":
    main()
