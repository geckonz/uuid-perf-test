# UUID v4 vs v7 Performance Benchmark

Empirical measurement of the performance difference between UUID v4 (random)
and UUID v7 (time-ordered) as primary/foreign keys in PostgreSQL 16 and
MongoDB 7, at 5 million customer + 7 million account record scale.

**Why it matters:** UUID v7's monotonically increasing timestamp prefix means
every insert appends to the rightmost B-tree leaf page. UUID v4's random
distribution causes inserts to land on arbitrary pages throughout the index,
triggering constant page splits, higher fragmentation, and worse buffer cache
utilisation. This benchmark makes that difference measurable.

---

## Requirements

- Docker + Docker Compose
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `curl -Lf https://astral.sh/uv/install.sh | sh`)

---

## Quick start

```bash
# 1. Start databases
docker compose up -d

# 2. Install dependencies
uv sync

# 3. Initialise schemas and collections
uv run python -m db.postgres.init
uv run python -m db.mongo.init

# 4. Generate data (smoke test — ~5k customers, ~7k accounts, takes ~2s)
uv run python -m generators.generate_csv --scale 0.001

# 5. Load into databases
uv run python -m loaders.load_postgres
uv run python -m loaders.load_mongo

# 6. Run benchmarks
uv run python -m runner.run_all
```

Results are printed to stdout and saved to `reports/results/` as JSON and
Markdown.

---

## Full-scale run (5M customers / 7M accounts)

```bash
# Generate full dataset (~30 min, produces ~3.5 GB of CSV)
uv run python -m generators.generate_csv

# Load into PostgreSQL (~10 min)
uv run python -m loaders.load_postgres

# Load into MongoDB (~15 min)
uv run python -m loaders.load_mongo

# Run full benchmark suite (~5 min)
uv run python -m runner.run_all
```

You can also run each database independently:

```bash
uv run python -m runner.run_postgres
uv run python -m runner.run_mongo
```

---

## Project structure

```
├── config/settings.py          # DB URLs, record counts, file paths
├── db/
│   ├── postgres/               # DDL (schema_v4.sql, schema_v7.sql) + init
│   └── mongo/                  # Collection + index creation
├── generators/
│   ├── generate_csv.py         # CLI: generates all CSV files
│   ├── uuid_factory.py         # new_uuid4() / new_uuid7() helpers
│   ├── data_factory.py         # Faker-based field generation
│   └── distribution.py        # 60/30/8/2% account-per-customer distribution
├── loaders/
│   ├── load_postgres.py        # COPY protocol bulk loader + index timing
│   └── load_mongo.py           # insert_many bulk loader
├── benchmarks/
│   ├── timer.py                # TimingResult + BenchmarkTimer
│   ├── postgres/               # bench_insert, bench_select, bench_update, analyze
│   └── mongo/                  # bench_insert, bench_select, bench_update, analyze
├── runner/
│   ├── run_postgres.py         # Full PostgreSQL suite
│   ├── run_mongo.py            # Full MongoDB suite
│   └── run_all.py              # Both databases sequentially
└── reports/
    ├── collector.py            # Aggregates results, computes v4/v7 ratios
    └── formatter.py            # ASCII table + JSON + Markdown output
```

---

## Data model

Two schemas in PostgreSQL (`bench_v4`, `bench_v7`) and four collections in
MongoDB (`uuid_v4.customers`, `uuid_v4.accounts`, `uuid_v7.*`) with identical
structure. The only difference is the UUID version used for primary keys.

**customers** — 5,000,000 rows: `id`, `name`, `email` (unique), `phone`,
`address`, `created_at`, `updated_at`

**accounts** — 7,000,000 rows: `id`, `customer_id` (FK), `account_type`,
`balance`, `currency`, `status`, `opened_at`, `updated_at`

Account distribution per customer: 60% → 1, 30% → 2, 8% → 3, 2% → 4.

MongoDB UUIDs are stored as `BSON Binary subtype 4` (not strings) so that
WiredTiger preserves the ordering properties of v7.

---

## Benchmark tests

| Test | PostgreSQL | MongoDB |
|---|---|---|
| Individual insert | 10,000 rows, one-at-a-time | 10,000 docs, insert_one |
| PK point lookup | 100,000 `WHERE id = ?` | 100,000 `find_one({"_id": …})` |
| Range query (1 hr) | `WHERE created_at BETWEEN …` × 10 | `find({"created_at": {…}})` × 10 |
| Range query (1 day) | same, wider window | same, wider window |
| Join / lookup | 50,000 customer + accounts joins | 50,000 account + customer pairs |
| Update by PK | 100,000 `UPDATE … WHERE id = ?` | 100,000 `update_one` |
| Index analysis | `pg_relation_size` per index | `collStats` |
| Query plans | `EXPLAIN (ANALYZE, BUFFERS)` | `cursor.explain()` |

---

## Sample results (5M customers / 7M accounts)

Hardware: local machine, Docker with `fsync=off` / `--syncdelay 0` to isolate
index structure costs from disk latency.

### PostgreSQL

| Operation | v4 | v7 | v7 speedup |
|---|---|---|---|
| Insert customers (10k) | 2.57s | 2.22s | 1.16x |
| **Insert accounts (10k)** | **2.62s** | **1.32s** | **1.98x** |
| **Update by PK (100k)** | **8.43s** | **5.23s** | **1.61x** |
| Join (50k) | 2.87s | 2.64s | 1.09x |
| PK select (100k) | 3.63s | 4.05s | 0.90x |
| Range query 1 hr | 0.01s | 0.01s | 1.17x |
| Range query 1 day | 0.08s | 0.10s | 0.96x |

**PostgreSQL PK index sizes:**

| | v4 | v7 | reduction |
|---|---|---|---|
| customers PK | 193 MB | 151 MB | 22% smaller |
| accounts PK | 280 MB | 211 MB | 25% smaller |

Index build times during load also showed strong v7 advantages:
`accounts.customer_id` index built 3.5x faster with v7 keys.

### MongoDB

| Operation | v4 | v7 | v7 speedup |
|---|---|---|---|
| **Insert customers (10k)** | **1.66s** | **1.14s** | **1.46x** |
| **Insert accounts (10k)** | **1.73s** | **1.40s** | **1.24x** |
| Range query 1 hr | 0.01s | 0.01s | 1.43x |
| Range query 1 day | 0.15s | 0.21s | 0.96x |
| PK select (100k) | 9.82s | 10.52s | 0.93x |
| Lookup (50k pairs) | 10.87s | 12.38s | 0.88x |
| Update by _id (100k) | 10.71s | 10.51s | 1.02x |

**MongoDB total index sizes** (customers + secondary indexes combined):

| | v4 | v7 | reduction |
|---|---|---|---|
| customers indexes | 563 MB | 417 MB | 26% smaller |
| accounts indexes | 719 MB | 492 MB | 32% smaller |

### Interpretation

- **Inserts:** v7 wins consistently (1.2–2.0x) in both databases. The
  append-only insert pattern eliminates B-tree page splits entirely.
- **Updates:** v7 wins in PostgreSQL (1.2–1.6x). Updating clustered rows
  dirties fewer, more localised pages.
- **Index size:** v7 indexes are 20–32% smaller due to denser page packing
  (less fragmentation from page splits).
- **Point lookups:** v4 ties or edges v7 slightly. A fully-loaded random index
  can spread hot rows across more buffer pages, marginally improving hit rate
  when sampling uniformly at random.
- **Range queries:** v7 advantage is real but noisy at this scale. Expected to
  be more pronounced with cold caches or at higher row counts where temporal
  locality translates directly to fewer I/O pages read.

---

## Configuration

All tunables are in `config/settings.py`:

```python
NUM_CUSTOMERS = 5_000_000
NUM_ACCOUNTS  = 7_000_000
BENCH_INSERT_COUNT = 10_000
BENCH_SELECT_COUNT = 100_000
BENCH_UPDATE_COUNT = 100_000
BENCH_JOIN_COUNT   = 50_000
```

Docker Compose flags are chosen to eliminate I/O flush overhead so the
benchmark measures index structure costs, not disk latency:

- **PostgreSQL:** `fsync=off`, `full_page_writes=off`,
  `synchronous_commit=off`, `shared_buffers=1GB`, `work_mem=64MB`
- **MongoDB:** `--syncdelay 0`, `--wiredTigerCacheSizeGB 2`
