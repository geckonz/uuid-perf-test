"""Central configuration for all benchmark components."""

from pathlib import Path

# Project root
ROOT_DIR = Path(__file__).parent.parent

# Data directory for CSV and NumPy files
DATA_DIR = ROOT_DIR / "data"

# Reports output directory
RESULTS_DIR = ROOT_DIR / "reports" / "results"

# Database connection URLs
POSTGRES_URL = "postgresql://bench:bench@localhost:5432/bench"
MONGO_URL = "mongodb://localhost:27017"
MONGO_DB_NAME = "uuid_bench"

# Record counts (full scale)
NUM_CUSTOMERS = 5_000_000
NUM_ACCOUNTS = 7_000_000

# Account distribution (must sum to NUM_ACCOUNTS given NUM_CUSTOMERS)
# 60% → 1 account, 30% → 2, 8% → 3, 2% → 4
ACCOUNT_DISTRIBUTION = {1: 0.60, 2: 0.30, 3: 0.08, 4: 0.02}

# Batch sizes
POSTGRES_COPY_BATCH = 50_000
MONGO_INSERT_BATCH = 10_000

# Benchmark iteration counts
BENCH_INSERT_COUNT = 10_000
BENCH_SELECT_COUNT = 100_000
BENCH_JOIN_COUNT = 50_000
BENCH_UPDATE_COUNT = 100_000

# Range query windows
RANGE_QUERY_HOURS = 1
RANGE_QUERY_DAYS = 1

# CSV file paths
CUSTOMERS_V4_CSV = DATA_DIR / "customers_v4.csv"
CUSTOMERS_V7_CSV = DATA_DIR / "customers_v7.csv"
ACCOUNTS_V4_CSV = DATA_DIR / "accounts_v4.csv"
ACCOUNTS_V7_CSV = DATA_DIR / "accounts_v7.csv"

# NumPy ID cache paths
CUSTOMER_IDS_V4_NPY = DATA_DIR / "customer_ids_v4.npy"
CUSTOMER_IDS_V7_NPY = DATA_DIR / "customer_ids_v7.npy"
