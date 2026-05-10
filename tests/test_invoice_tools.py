"""Tests for the 4 invoice tools."""
import json
import pytest

from src.db.database import get_engine
from src.tools.invoice_tools import (
    get_invoice_line_items,
    get_invoices_by_customer,
    get_purchased_tracks_by_customer,
    get_support_rep_for_invoice,
)


@pytest.fixture(scope="module", autouse=True)
def db():
    get_engine()


# ── get_invoices_by_customer ──────────────────────────────────────────────────

class TestGetInvoicesByCustomer:
    def test_found_customer_1(self):
        result = get_invoices_by_customer.invoke({"customer_id": "1"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_all_invoices_belong_to_customer(self):
        result = get_invoices_by_customer.invoke({"customer_id": "2"})
        rows = json.loads(result)
        for row in rows:
            assert row["CustomerId"] == 2

    def test_sorted_by_date_desc(self):
        result = get_invoices_by_customer.invoke({"customer_id": "1"})
        rows = json.loads(result)
        dates = [r["InvoiceDate"] for r in rows]
        assert dates == sorted(dates, reverse=True), "Invoices not sorted DESC by date"

    def test_not_found_returns_message(self):
        result = get_invoices_by_customer.invoke({"customer_id": "99999"})
        assert "No invoices found" in result

    def test_invalid_id_returns_error(self):
        result = get_invoices_by_customer.invoke({"customer_id": "abc"})
        assert "Invalid" in result

    def test_valid_json_on_found(self):
        result = get_invoices_by_customer.invoke({"customer_id": "5"})
        rows = json.loads(result)
        assert isinstance(rows, list)


# ── get_purchased_tracks_by_customer ─────────────────────────────────────────

class TestGetPurchasedTracksByCustomer:
    def test_found_customer_1(self):
        result = get_purchased_tracks_by_customer.invoke({"customer_id": "1"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_sorted_by_price_desc(self):
        result = get_purchased_tracks_by_customer.invoke({"customer_id": "1"})
        rows = json.loads(result)
        prices = [r["UnitPrice"] for r in rows]
        assert prices == sorted(prices, reverse=True), "Tracks not sorted by price DESC"

    def test_has_track_and_artist_fields(self):
        result = get_purchased_tracks_by_customer.invoke({"customer_id": "1"})
        rows = json.loads(result)
        assert "TrackName" in rows[0]
        assert "Artist" in rows[0]

    def test_not_found_returns_message(self):
        result = get_purchased_tracks_by_customer.invoke({"customer_id": "99999"})
        assert "No purchased tracks found" in result

    def test_invalid_id_returns_error(self):
        result = get_purchased_tracks_by_customer.invoke({"customer_id": "xyz"})
        assert "Invalid" in result


# ── get_support_rep_for_invoice ───────────────────────────────────────────────

class TestGetSupportRepForInvoice:
    def test_found_invoice_1(self):
        result = get_support_rep_for_invoice.invoke({"invoice_id": "1"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) == 1

    def test_result_has_rep_fields(self):
        result = get_support_rep_for_invoice.invoke({"invoice_id": "1"})
        rows = json.loads(result)
        rep = rows[0]
        assert "RepName" in rep
        assert "Title" in rep

    def test_not_found_returns_message(self):
        result = get_support_rep_for_invoice.invoke({"invoice_id": "99999"})
        assert "No support representative found" in result

    def test_invalid_id_returns_error(self):
        result = get_support_rep_for_invoice.invoke({"invoice_id": "abc"})
        assert "Invalid" in result

    def test_valid_json_on_found(self):
        result = get_support_rep_for_invoice.invoke({"invoice_id": "10"})
        rows = json.loads(result)
        assert isinstance(rows, list)


# ── get_invoice_line_items ────────────────────────────────────────────────────

class TestGetInvoiceLineItems:
    def test_found_invoice_1(self):
        result = get_invoice_line_items.invoke({"invoice_id": "1"})
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_all_items_belong_to_invoice(self):
        result = get_invoice_line_items.invoke({"invoice_id": "1"})
        rows = json.loads(result)
        for row in rows:
            assert row["InvoiceId"] == 1

    def test_has_track_and_price_fields(self):
        result = get_invoice_line_items.invoke({"invoice_id": "1"})
        rows = json.loads(result)
        assert "TrackName" in rows[0]
        assert "UnitPrice" in rows[0]

    def test_not_found_returns_message(self):
        result = get_invoice_line_items.invoke({"invoice_id": "99999"})
        assert "No line items found" in result

    def test_invalid_id_returns_error(self):
        result = get_invoice_line_items.invoke({"invoice_id": "xyz"})
        assert "Invalid" in result

    def test_valid_json_on_found(self):
        result = get_invoice_line_items.invoke({"invoice_id": "5"})
        rows = json.loads(result)
        assert isinstance(rows, list)
