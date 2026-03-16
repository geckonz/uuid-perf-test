"""MongoDB collection stats and explain() capture."""

import json
import random
from datetime import timedelta

import pymongo


def coll_stats(db: pymongo.database.Database, prefix: str) -> dict:
    """Return collStats for customers and accounts collections."""
    result = {}
    for coll_suffix in ("customers", "accounts"):
        name = f"{prefix}.{coll_suffix}"
        try:
            stats = db.command("collStats", name)
            result[coll_suffix] = {
                "count": stats.get("count", 0),
                "size_bytes": stats.get("size", 0),
                "storage_size_bytes": stats.get("storageSize", 0),
                "total_index_size_bytes": stats.get("totalIndexSize", 0),
                "index_sizes": stats.get("indexSizes", {}),
                "avg_obj_size_bytes": stats.get("avgObjSize", 0),
            }
        except Exception as e:
            result[coll_suffix] = {"error": str(e)}
    return result


def explain_pk_select(db: pymongo.database.Database, prefix: str) -> dict:
    """Run explain() for a PK _id lookup on customers."""
    col = db[f"{prefix}.customers"]
    sample = list(col.aggregate([{"$sample": {"size": 1}}, {"$project": {"_id": 1}}]))
    if not sample:
        return {}
    uid = sample[0]["_id"]
    return col.find({"_id": uid}).explain()


def explain_range_query(db: pymongo.database.Database, prefix: str) -> dict:
    """Run explain() for a created_at range query on customers."""
    col = db[f"{prefix}.customers"]
    pipeline = [
        {"$group": {"_id": None, "min": {"$min": "$created_at"}, "max": {"$max": "$created_at"}}}
    ]
    agg = list(col.aggregate(pipeline))
    if not agg:
        return {}
    min_ts = agg[0]["min"]
    end_ts = min_ts + timedelta(hours=1)
    return col.find({"created_at": {"$gte": min_ts, "$lt": end_ts}}).explain()


def run(db: pymongo.database.Database, prefix: str) -> dict:
    """Collect all analysis data for the given prefix. Returns a dict."""
    print(f"  [analyze] {prefix} collStats...")
    stats = coll_stats(db, prefix)

    print(f"  [analyze] {prefix} explain() pk select...")
    pk_explain = explain_pk_select(db, prefix)

    print(f"  [analyze] {prefix} explain() range query...")
    range_explain = explain_range_query(db, prefix)

    return {
        "prefix": prefix,
        "coll_stats": stats,
        "explain": {
            "pk_select": pk_explain,
            "range_query_1hr": range_explain,
        },
    }
