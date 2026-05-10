import json
import logging

from langchain_core.tools import tool

from src.db.database import run_query_safe

logger = logging.getLogger(__name__)


def _safe_int(value: str, name: str = "ID") -> tuple[int | None, str | None]:
    try:
        return int(value), None
    except (ValueError, TypeError):
        return None, f"Invalid {name} '{value}'. Please provide a numeric value."


@tool
def get_invoices_by_customer(customer_id: str) -> str:
    """Get all invoices for a customer sorted by date (most recent first)."""
    logger.info("Tool: get_invoices_by_customer | customer_id=%s", customer_id)
    cid, err = _safe_int(customer_id, "Customer ID")
    if err:
        return err

    result = run_query_safe(
        "SELECT i.InvoiceId, i.CustomerId, i.InvoiceDate, "
        "i.BillingAddress, i.BillingCity, i.BillingCountry, i.Total "
        "FROM Invoice i "
        "WHERE i.CustomerId = :cid "
        "ORDER BY i.InvoiceDate DESC",
        {"cid": cid},
    )
    rows = json.loads(result)
    if not rows:
        return f"No invoices found for customer ID {cid}."
    return result


@tool
def get_purchased_tracks_by_customer(customer_id: str) -> str:
    """Get all tracks purchased by a customer across all invoices, sorted by unit price (highest first)."""
    logger.info("Tool: get_purchased_tracks_by_customer | customer_id=%s", customer_id)
    cid, err = _safe_int(customer_id, "Customer ID")
    if err:
        return err

    result = run_query_safe(
        "SELECT t.TrackId, t.Name AS TrackName, ar.Name AS Artist, "
        "a.Title AS Album, il.UnitPrice, i.InvoiceDate "
        "FROM InvoiceLine il "
        "JOIN Invoice i ON il.InvoiceId = i.InvoiceId "
        "JOIN Track t ON il.TrackId = t.TrackId "
        "JOIN Album a ON t.AlbumId = a.AlbumId "
        "JOIN Artist ar ON a.ArtistId = ar.ArtistId "
        "WHERE i.CustomerId = :cid "
        "ORDER BY il.UnitPrice DESC",
        {"cid": cid},
    )
    rows = json.loads(result)
    if not rows:
        return f"No purchased tracks found for customer ID {cid}."
    return result


@tool
def get_support_rep_for_invoice(invoice_id: str) -> str:
    """Get the support representative assigned to a customer's invoice."""
    logger.info("Tool: get_support_rep_for_invoice | invoice_id=%s", invoice_id)
    iid, err = _safe_int(invoice_id, "Invoice ID")
    if err:
        return err

    result = run_query_safe(
        "SELECT e.EmployeeId, e.FirstName || ' ' || e.LastName AS RepName, "
        "e.Title, e.Email AS RepEmail, e.Phone AS RepPhone "
        "FROM Invoice i "
        "JOIN Customer c ON i.CustomerId = c.CustomerId "
        "JOIN Employee e ON c.SupportRepId = e.EmployeeId "
        "WHERE i.InvoiceId = :iid",
        {"iid": iid},
    )
    rows = json.loads(result)
    if not rows:
        return f"No support representative found for invoice ID {iid}."
    return result


@tool
def get_invoice_line_items(invoice_id: str) -> str:
    """Get the detailed line items (tracks purchased) for a specific invoice."""
    logger.info("Tool: get_invoice_line_items | invoice_id=%s", invoice_id)
    iid, err = _safe_int(invoice_id, "Invoice ID")
    if err:
        return err

    result = run_query_safe(
        "SELECT il.InvoiceLineId, il.InvoiceId, t.TrackId, "
        "t.Name AS TrackName, ar.Name AS Artist, a.Title AS Album, "
        "il.UnitPrice, il.Quantity "
        "FROM InvoiceLine il "
        "JOIN Track t ON il.TrackId = t.TrackId "
        "JOIN Album a ON t.AlbumId = a.AlbumId "
        "JOIN Artist ar ON a.ArtistId = ar.ArtistId "
        "WHERE il.InvoiceId = :iid "
        "ORDER BY il.InvoiceLineId",
        {"iid": iid},
    )
    rows = json.loads(result)
    if not rows:
        return f"No line items found for invoice ID {iid}."
    return result


invoice_tools = [
    get_invoices_by_customer,
    get_purchased_tracks_by_customer,
    get_support_rep_for_invoice,
    get_invoice_line_items,
]
