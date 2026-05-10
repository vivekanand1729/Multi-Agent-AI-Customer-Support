"""Tests for database utilities: run_query_safe, normalize_phone, verify_database."""
import json
import pytest

from src.db.database import (
    get_engine,
    lookup_customer_by_phone,
    normalize_phone,
    run_query_safe,
    verify_database,
)


@pytest.fixture(scope="module", autouse=True)
def db():
    """Ensure the Chinook database is loaded once for all tests."""
    get_engine()


# ── run_query_safe ────────────────────────────────────────────────────────────

class TestRunQuerySafe:
    def test_returns_json_string(self):
        result = run_query_safe("SELECT COUNT(*) AS cnt FROM Customer")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_customer_count(self):
        result = run_query_safe("SELECT COUNT(*) AS cnt FROM Customer")
        cnt = json.loads(result)[0]["cnt"]
        assert cnt == 59

    def test_artist_count(self):
        result = run_query_safe("SELECT COUNT(*) AS cnt FROM Artist")
        cnt = json.loads(result)[0]["cnt"]
        assert cnt == 275

    def test_parameterized_query(self):
        result = run_query_safe(
            "SELECT CustomerId FROM Customer WHERE CustomerId = :cid", {"cid": 1}
        )
        rows = json.loads(result)
        assert len(rows) == 1
        assert rows[0]["CustomerId"] == 1

    def test_empty_result_returns_empty_list(self):
        result = run_query_safe(
            "SELECT * FROM Customer WHERE CustomerId = :cid", {"cid": 99999}
        )
        rows = json.loads(result)
        assert rows == []

    def test_empty_result_is_valid_json(self):
        result = run_query_safe(
            "SELECT * FROM Artist WHERE ArtistId = :aid", {"aid": -1}
        )
        assert json.loads(result) == []


# ── normalize_phone ───────────────────────────────────────────────────────────

class TestNormalizePhone:
    def test_international_with_spaces(self):
        assert normalize_phone("+1 (403) 262-3443") == "+14032623443"

    def test_international_keeps_plus(self):
        result = normalize_phone("+55 (11) 3055-3278")
        assert result.startswith("+")

    def test_domestic_strips_formatting(self):
        assert normalize_phone("555-123-4567") == "5551234567"

    def test_none_returns_empty_string(self):
        assert normalize_phone(None) == ""

    def test_empty_string_returns_empty(self):
        assert normalize_phone("") == ""

    def test_parentheses_and_dashes(self):
        result = normalize_phone("(800) 555-1212")
        assert result == "8005551212"

    def test_no_crash_on_whitespace(self):
        result = normalize_phone("   ")
        assert result == ""


# ── verify_database ───────────────────────────────────────────────────────────

class TestVerifyDatabase:
    def test_returns_dict(self):
        result = verify_database()
        assert isinstance(result, dict)

    def test_healthy_status(self):
        result = verify_database()
        assert result["status"] == "healthy"

    def test_all_tables_present(self):
        result = verify_database()
        for table in ["Customer", "Artist", "Album", "Track", "Invoice", "InvoiceLine"]:
            assert table in result["tables"]

    def test_all_tables_ok(self):
        result = verify_database()
        for table, info in result["tables"].items():
            assert info["ok"], f"Table {table} count mismatch"


# ── lookup_customer_by_phone ──────────────────────────────────────────────────

class TestLookupCustomerByPhone:
    def test_found_with_formatted_phone(self):
        # Customer 1 has phone "+55 (12) 3923-5555"
        result = lookup_customer_by_phone("+55 (12) 3923-5555")
        assert result is not None
        assert result["CustomerId"] == 1

    def test_not_found_returns_none(self):
        result = lookup_customer_by_phone("+1 (999) 999-9999")
        assert result is None

    def test_none_input_returns_none(self):
        result = lookup_customer_by_phone(None)
        assert result is None
