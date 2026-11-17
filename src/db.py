import os
import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = os.getenv("DB_PATH", "ops_audit.db")

SEED_INVENTORY = [
    ("USB-C Docks", 6, 15, 12, 14),
    ("Wireless Keyboards", 18, 25, 15, 15),
    ("27-inch Monitors", 110, 15, 15, 8),
    ("Webcam Pro 4K", 45, 10, 12, 6),
]


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                rating TEXT,
                details TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                item TEXT PRIMARY KEY,
                current_stock INTEGER NOT NULL,
                reorder_threshold INTEGER NOT NULL,
                projected_weekly_sales INTEGER NOT NULL,
                actual_weekly_sales INTEGER NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()
        if count == 0:
            conn.executemany(
                "INSERT INTO inventory VALUES (?, ?, ?, ?, ?)",
                SEED_INVENTORY,
            )


def log_audit_event(actor: str, details: str, rating: str = "N/A") -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp, actor, rating, details) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), actor, rating, details),
        )


def increment_stock(item_name: str, quantity: int) -> str:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "UPDATE inventory SET current_stock = current_stock + ? WHERE LOWER(item) = LOWER(?)",
            (quantity, item_name.strip()),
        )
        if cur.rowcount == 0:
            return f"Item '{item_name}' not found in inventory table; skipped stock increment."
        new_qty = conn.execute(
            "SELECT current_stock FROM inventory WHERE LOWER(item) = LOWER(?)",
            (item_name.strip(),),
        ).fetchone()
    return f"Updated '{item_name}' stock to {new_qty} units (+{quantity})."


def _classify_stock(row: pd.Series) -> str:
    sell_through = (row["Actual_Weekly_Sales"] / max(row["Projected_Weekly_Sales"], 1)) * 100
    weeks_cover = row["Current_Stock"] / max(row["Actual_Weekly_Sales"], 1)

    if row["Current_Stock"] <= row["Reorder_Threshold"] * 0.5:
        return "CRITICAL LOW"
    if row["Current_Stock"] <= row["Reorder_Threshold"]:
        return "NEAR LOW"
    if weeks_cover > 8 and sell_through < 70:
        return "OVERBOUGHT"
    if sell_through < 70:
        return "SLOW-MOVING"
    return "HEALTHY"


def export_department_workbook(output_path: str = "weekly_department_report.xlsx") -> str:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        audit_df = pd.read_sql_query("SELECT * FROM audit_log", conn)
        stock_df = pd.read_sql_query(
            """
            SELECT
                item AS Item,
                current_stock AS Current_Stock,
                reorder_threshold AS Reorder_Threshold,
                projected_weekly_sales AS Projected_Weekly_Sales,
                actual_weekly_sales AS Actual_Weekly_Sales
            FROM inventory
            """,
            conn,
        )

    handled = len(audit_df)
    resolved = len(audit_df[audit_df["details"].str.contains("APPROVED|REJECTED", na=False)])

    support_df = pd.DataFrame(
        [
            {
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Tickets_Handled": handled,
                "Tickets_Resolved": resolved,
                "Resolution_Rate_%": round((resolved / handled) * 100, 1) if handled else 0.0,
            }
        ]
    )

    stock_df["Sell_Through_%"] = round((stock_df["Actual_Weekly_Sales"] / stock_df["Projected_Weekly_Sales"]) * 100, 1)
    stock_df["Weeks_Of_Cover"] = round(stock_df["Current_Stock"] / stock_df["Actual_Weekly_Sales"], 1)
    stock_df["Status"] = stock_df.apply(_classify_stock, axis=1)

    growth_df = pd.DataFrame(
        [
            {"Segment": "B2B Tech Startups", "MoM_Growth_%": 18.5, "Strategy": "Expand USB-C Dock bundles (116.7% sell-through)"},
            {"Segment": "Corporate Offices", "MoM_Growth_%": -6.0, "Strategy": "Discount overbought 27-inch Monitors (53.3% sell-through)"},
        ]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        support_df.to_excel(writer, sheet_name="Support_KPIs", index=False)
        stock_df.to_excel(writer, sheet_name="Stock_Control", index=False)
        growth_df.to_excel(writer, sheet_name="Growth_Targets", index=False)

    flagged = stock_df[stock_df["Status"] != "HEALTHY"]
    alerts = [
        f"{r['Item']}: {r['Status']} (Stock={r['Current_Stock']}, Sell-through={r['Sell_Through_%']}%)"
        for _, r in flagged.iterrows()
    ]
    return "INVENTORY HEALTH:\n- " + "\n- ".join(alerts) if alerts else "INVENTORY HEALTH: All items healthy."
