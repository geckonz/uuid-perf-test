"""PostgreSQL index size analysis and EXPLAIN ANALYZE capture."""

import json
import random
from datetime import timedelta

import psycopg

from config.settings import POSTGRES_URL


def index_sizes(conn: psycopg.Connection, schema: str) -> dict:
    """Return a dict of index name → size in bytes for the given schema."""
    sql = """
        SELECT
            i.relname AS index_name,
            pg_relation_size(i.oid) AS size_bytes,
            pg_size_pretty(pg_relation_size(i.oid)) AS size_pretty
        FROM pg_class i
        JOIN pg_index ix ON ix.indexrelid = i.oid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = %s
        ORDER BY pg_relation_size(i.oid) DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (schema,))
        rows = cur.fetchall()

    return {
        row[0]: {"size_bytes": row[1], "size_pretty": row[2]}
        for row in rows
    }


def table_bloat(conn: psycopg.Connection, schema: str) -> dict:
    """Return approximate bloat stats for tables in the given schema."""
    sql = """
        SELECT
            relname,
            n_live_tup,
            n_dead_tup,
            CASE WHEN n_live_tup > 0
                 THEN round(n_dead_tup::numeric / n_live_tup * 100, 2)
                 ELSE 0 END AS dead_pct,
            pg_size_pretty(pg_total_relation_size(relid)) AS total_size
        FROM pg_stat_user_tables
        WHERE schemaname = %s
        ORDER BY relname
    """
    with conn.cursor() as cur:
        cur.execute(sql, (schema,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    return {row[0]: dict(zip(cols[1:], row[1:])) for row in rows}


def explain_pk_select(conn: psycopg.Connection, schema: str) -> str:
    """Capture EXPLAIN ANALYZE for a PK lookup on customers."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {schema}.customers LIMIT 1")
        sample_id = cur.fetchone()[0]

    sql = (
        f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        f"SELECT * FROM {schema}.customers WHERE id = %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (sample_id,))
        return json.dumps(cur.fetchone()[0], indent=2)


def explain_range_query(conn: psycopg.Connection, schema: str) -> str:
    """Capture EXPLAIN ANALYZE for a 1-hour range query on customers."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT MIN(created_at), MAX(created_at) FROM {schema}.customers")
        min_ts, max_ts = cur.fetchone()

    mid = min_ts + (max_ts - min_ts) / 2
    end = mid + timedelta(hours=1)

    sql = (
        f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        f"SELECT * FROM {schema}.customers WHERE created_at BETWEEN %s AND %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (mid, end))
        return json.dumps(cur.fetchone()[0], indent=2)


def explain_join(conn: psycopg.Connection, schema: str) -> str:
    """Capture EXPLAIN ANALYZE for a customer+accounts JOIN."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT c.id FROM {schema}.customers c "
            f"JOIN {schema}.accounts a ON a.customer_id = c.id "
            f"LIMIT 1"
        )
        sample_cid = cur.fetchone()[0]

    sql = (
        f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
        f"SELECT c.id, c.name, a.id, a.account_type, a.balance "
        f"FROM {schema}.customers c "
        f"JOIN {schema}.accounts a ON a.customer_id = c.id "
        f"WHERE c.id = %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (sample_cid,))
        return json.dumps(cur.fetchone()[0], indent=2)


def run(conn: psycopg.Connection, schema: str) -> dict:
    """Collect all analysis data for the given schema. Returns a dict."""
    print(f"  [analyze] {schema} index sizes...")
    sizes = index_sizes(conn, schema)

    print(f"  [analyze] {schema} table bloat stats...")
    bloat = table_bloat(conn, schema)

    print(f"  [analyze] {schema} EXPLAIN ANALYZE queries...")
    explains = {
        "pk_select": explain_pk_select(conn, schema),
        "range_query_1hr": explain_range_query(conn, schema),
        "join": explain_join(conn, schema),
    }

    return {
        "schema": schema,
        "index_sizes": sizes,
        "table_bloat": bloat,
        "explain_analyze": explains,
    }
