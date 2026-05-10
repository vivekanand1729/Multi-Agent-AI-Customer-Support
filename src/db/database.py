import json
import logging
import re
import sqlite3
import subprocess
import urllib.request
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

CHINOOK_URL = (
    "https://raw.githubusercontent.com/lerocha/chinook-database/"
    "master/ChinookDatabase/DataSources/Chinook_Sqlite.sql"
)
CACHE_PATH = Path(__file__).parent / "chinook_cache.sql"

_engine = None


def _fetch_url_no_proxy(url: str) -> str:
    """Download URL bypassing system proxy settings."""
    # Try curl first (most reliable proxy bypass on macOS)
    try:
        result = subprocess.run(
            ["curl", "-sL", "--noproxy", "*", "--max-time", "30", url],
            capture_output=True, text=True, timeout=35,
        )
        if result.returncode == 0 and len(result.stdout) > 1000:
            return result.stdout
    except Exception as e:
        logger.debug("curl attempt failed: %s", e)

    # Fallback: urllib with no-proxy handler
    handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    with opener.open(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _download_chinook() -> str:
    if CACHE_PATH.exists():
        content = CACHE_PATH.read_text(encoding="utf-8")
        if len(content) > 1000:
            logger.info("Loading Chinook SQL from cache: %s", CACHE_PATH)
            return content

    logger.info("Downloading Chinook database from GitHub...")
    sql = _fetch_url_no_proxy(CHINOOK_URL)
    CACHE_PATH.write_text(sql, encoding="utf-8")
    logger.info("Chinook SQL cached at %s (%d bytes)", CACHE_PATH, len(sql))
    return sql


def _build_engine() -> None:
    global _engine
    sql_content = _download_chinook()

    raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
    raw_conn.executescript(sql_content)
    raw_conn.commit()
    logger.info("Chinook database loaded into in-memory SQLite")

    _engine = create_engine(
        "sqlite+pysqlite://",
        creator=lambda: raw_conn,
        poolclass=StaticPool,
    )


def get_engine():
    global _engine
    if _engine is None:
        _build_engine()
    return _engine


def run_query_safe(sql: str, params: dict | None = None) -> str:
    """Execute a parameterized SQL query and return JSON string of results."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            rows = [dict(row._mapping) for row in result]
            return json.dumps(rows)
    except Exception as e:
        logger.error("Query error: %s | SQL: %s | params: %s", e, sql, params)
        return json.dumps([])


def normalize_phone(phone: str | None) -> str:
    """Normalize a phone number by stripping non-digit characters, preserving leading +."""
    if not phone:
        return ""
    stripped = phone.strip()
    if stripped.startswith("+"):
        digits = "+" + re.sub(r"\D", "", stripped[1:])
    else:
        digits = re.sub(r"\D", "", stripped)
    return digits


def lookup_customer_by_phone(phone: str) -> dict | None:
    """Find a customer whose normalized phone matches the provided phone."""
    normalized_input = normalize_phone(phone)
    if not normalized_input:
        return None

    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM Customer WHERE Phone IS NOT NULL")
        )
        for row in result.mappings():
            if normalize_phone(row["Phone"]) == normalized_input:
                return dict(row)
    return None


def verify_database() -> dict:
    """Health check: verify Chinook tables and row counts."""
    checks = {
        "Customer": 59,
        "Artist": 275,
        "Album": 347,
        "Track": 3503,
        "Invoice": 412,
        "InvoiceLine": 2240,
    }
    results = {}
    try:
        for table, expected in checks.items():
            rows = json.loads(
                run_query_safe(f"SELECT COUNT(*) as cnt FROM {table}")
            )
            actual = rows[0]["cnt"] if rows else 0
            results[table] = {"expected": expected, "actual": actual, "ok": actual == expected}

        all_ok = all(v["ok"] for v in results.values())
        return {"status": "healthy" if all_ok else "degraded", "tables": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}
