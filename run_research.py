"""
run_research.py
---------------
Runs every query in queries_research.sql against Oracle and returns
results as pandas DataFrames + NumPy arrays for downstream analysis.

Requirements:
    pip install oracledb pandas numpy
"""

import re
import oracledb
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple

# Enable Thick mode by pointing to the Instant Client folder
oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_19_32")


# ─────────────────────────────────────────────────────────────
# 1. CONNECTION CONFIG  ← EDIT THIS
# ─────────────────────────────────────────────────────────────
DB_CONFIG = {
    "user":         "ernst",
    "password":     "",
    "host":         "localhost",
    "port":         1521,
    "service_name": "xe",       # or use "sid": "xe"
}


def get_connection():
    dsn = oracledb.makedsn(
        DB_CONFIG["host"],
        DB_CONFIG["port"],
        service_name=DB_CONFIG.get("service_name"),
        sid=DB_CONFIG.get("sid"),
    )
    return oracledb.connect(
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dsn=dsn,
    )


# ─────────────────────────────────────────────────────────────
# 2. PARSE THE .SQL FILE INTO (name, sql) PAIRS
# ─────────────────────────────────────────────────────────────
# Strategy: a comment line like  "-- 2.1.1. Which times..."  starts a new
# query. Everything until the next numbered header is that query's SQL.
# Bare comments inside a query body are kept as part of the SQL (Oracle
# accepts `--` comments inline), so they never split a query.

# FIX 1: capture optional trailing letter suffix (2.3.5a, 2.3.5b, ...)
SECTION_RE = re.compile(r"^--\s*(\d+(?:\.\d+)*[a-z]?)\.?\s+(.*)$", re.IGNORECASE)


def parse_sql_file(path: str) -> List[Tuple[str, str]]:
    """
    Split queries_research.sql into (query_id, sql_text) tuples.

    A new query starts ONLY at a numbered header comment:
        -- 2.3.5a. Are rider cancellations more sensitive to ...
    All other `--` comments are preserved inside the SQL body so they
    don't accidentally split or rename queries.
    """
    text = Path(path).read_text(encoding="utf-8-sig")

    # Normalise invisible characters
    text = (text.replace("\u00a0", " ").replace("\u200b", "")
                .replace("\u2018", "'").replace("\u2019", "'")
                .replace("\u201c", '"').replace("\u201d", '"'))

    queries: List[Tuple[str, str]] = []
    current_id: str | None = None
    current_desc: str = ""
    buffer: List[str] = []

    def clean_sql(raw: str) -> str:
        sql = raw.strip()
        while sql.endswith(";"):
            sql = sql[:-1].rstrip()
        return sql

    def flush():
        nonlocal buffer, current_id, current_desc
        if not current_id or not buffer:
            buffer = []
            return
        raw = clean_sql("\n".join(buffer))

        # Fallback: split on ';' followed by SELECT/WITH
        parts = re.split(r";\s*(?=(?:SELECT|WITH)\b)",
                         raw, flags=re.IGNORECASE)

        for i, part in enumerate(parts):
            sql = clean_sql(part)
            if not sql:
                continue
            suffix = chr(ord("a") + i) if i > 0 else ""
            qid = f"{current_id}{suffix} {current_desc}".strip()
            queries.append((qid, sql))

        buffer = []
        # FIX 2: clear the id/desc so a stale id can't leak into the
        # next query's name (this caused "2.3.4 2.3.5a ...").
        current_id = None
        current_desc = ""

    for line in text.splitlines():
        stripped = line.strip()

        # Case A: numbered header like '-- 2.3.5a. Question text'
        m = SECTION_RE.match(stripped)
        if m:
            flush()
            current_id = m.group(1)
            current_desc = m.group(2).strip()
            continue

        # Case B: any other comment line — keep it inside the buffer.
        # FIX 3: no longer treat bare `--` comments as query boundaries.
        buffer.append(line)

    flush()
    return queries


# ─────────────────────────────────────────────────────────────
# 3. QUERY RUNNER
# ─────────────────────────────────────────────────────────────
def run_query(sql: str, conn) -> pd.DataFrame:
    """Execute SQL and return a DataFrame; empty DataFrame on error."""
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0].lower() for d in cur.description]
            rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    except oracledb.DatabaseError as e:
        print(f"   ⚠ Query failed: {e}")
        print(f"   ── DEBUG: length = {len(sql)} chars ──")
        print(f"   ── First 300 chars ──")
        print(repr(sql[:300]))
        print(f"   ── Last 300 chars ──")
        print(repr(sql[-300:]))
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────
def main():
    sql_file = "queries_research.sql"
    queries = parse_sql_file(sql_file)
    print(f"▶ Parsed {len(queries)} queries from {sql_file}\n")

    results: Dict[str, pd.DataFrame] = {}
    arrays:  Dict[str, np.ndarray] = {}

    with get_connection() as conn:
        for qid, sql in queries:
            print(f"▶ Running {qid} ...")
            df = run_query(sql, conn)
            results[qid] = df
            # Convert to numeric where possible for clean NumPy arrays
            try:
                arrays[qid] = df.apply(pd.to_numeric, errors="ignore").to_numpy()
            except Exception:
                arrays[qid] = df.to_numpy(dtype=object)
            print(f"   ✔ {len(df)} rows × {df.shape[1]} cols\n")

    # ── Persist results ──────────────────────────────────────
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)

    # 1) One CSV per query — easy to open in Excel / load elsewhere
    for qid, df in results.items():
        if df.empty:
            continue
        safe = re.sub(r"[^\w]+", "_", qid).strip("_")
        df.to_csv(out_dir / f"{safe}.csv", index=False)

    # 2) One combined .npz with all arrays — fast reload later
    np.savez_compressed(
        out_dir / "all_results.npz",
        **{re.sub(r"[^\w]+", "_", k).strip("_"): v
           for k, v in arrays.items() if v.size > 0},
    )

    print(f"✔ Wrote {len(results)} CSVs + all_results.npz to ./{out_dir}/")
    return results, arrays


if __name__ == "__main__":
    results, arrays = main()

    # ── Example: peek at a specific result ──────────────────
    key = next((k for k in results if k.startswith("2.1.1")), None)
    if key:
        print(f"\n=== {key} ===")
        print(results[key])
        print("\nAs NumPy array:")
        print(arrays[key])