import sqlite3
from datetime import datetime
from langchain_core.tools import tool
from reportlab.pdfgen import canvas
from src.db import DB_PATH, init_db


@tool
def generate_purchase_order_pdf(supplier: str, item: str, quantity: int, total_gbp: float) -> str:
    """Generates a PDF purchase order invoice and returns the local filename."""
    filename = f"po_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf = canvas.Canvas(filename)
    pdf.drawString(50, 780, f"PURCHASE ORDER — {supplier}")
    pdf.drawString(50, 760, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.drawString(50, 735, f"Item: {item} | Quantity: {quantity}")
    pdf.drawString(50, 715, f"Total Amount: GBP {total_gbp:.2f}")
    pdf.drawString(50, 690, "Status: PENDING HUMAN & SUPERVISOR SIGN-OFF")
    pdf.save()
    return filename


@tool
def fetch_recent_audit_logs(limit: int = 5) -> str:
    """Fetches recent audit entries from SQLite for compliance checks."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT timestamp, actor, rating, details FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return "\n".join(str(r) for r in rows) if rows else "No prior audit entries."
