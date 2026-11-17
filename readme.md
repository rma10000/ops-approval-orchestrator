# ops-approval-orchestrator

Local multi-agent operations simulator and SQLite audit orchestrator for testing semantic ticket routing, risk-scored human approvals, live inventory updates, and multi-horizon forecasting (`£0` runtime cost).

## Project Structure

```diff
@@ ops-approval-orchestrator/ @@
  ├── .github/
  │   └── workflows/
+ │       └── test.yml               # Pytest CI for policy guardrails & stock math
@@ ├── src/ @@
  │   ├── __init__.py
+ │   ├── state.py                   # TypedDict graph state & Pydantic schemas
+ │   ├── db.py                      # SQLite audit log, inventory table & Excel exporter
+ │   ├── tools.py                   # @tool functions for PDF POs & audit log lookups
+ │   ├── agents.py                  # Router, Memory, Procurement, Risk Rater & Forecast nodes
+ │   └── graph.py                   # LangGraph state machine, edges & SqliteSaver checkpoints
@@ ├── test/ @@
  │   ├── __init__.py
+ │   └── test_guardrails.py         # Offline unit tests for policy overrides & stock status
+ ├── simulate.py                    # 4-event live operational simulator with terminal sign-off
+ ├── evals.py                       # 12-case routing & policy guardrail benchmark
  ├── .env.example
  ├── .gitignore
  ├── requirements.txt
  └── README.md
```

## How It Works

Incoming requests pass through a shared `OpsState` graph backed by SQLite checkpoints:

1. **Memory & BI Metrics (`sync_memory_and_metrics`):** Logs incoming events to `ops_audit.db`, checks live warehouse levels in SQLite, and generates a multi-tab Excel workbook (`weekly_department_report.xlsx`) covering Support KPIs, Stock Control, and Growth Targets.
2. **Intent Router (`route_request`):** Classifies incoming tickets into `stock`, `planning`, or `support` and routes them down the matching branch.
3. **Procurement & PDF Generation (`draft_stock_order`):** Extracts supplier, item, quantity, and GBP total via `@tool` calling (`generate_purchase_order_pdf`), generates a timestamped PDF purchase order (`po_YYYYMMDD_HHMMSS.pdf`), and drafts the supplier email.
4. **Supervisor Risk Rater (`evaluate_order_risk`):** Scores purchase orders (`1–10`) against company spend caps (`£1,000` max), approved vendors, and sell-through rates (`OVERBOUGHT` / `SLOW-MOVING` flags) using a strict Pydantic schema.
5. **Human Approval Gate (`await_human_signoff`):** Pauses execution via LangGraph `interrupt()` and displays the Supervisor risk rating, timestamped PDF filename, and email draft before any stock mutations occur.
6. **Multi-Horizon Forecast (`generate_forecast`):** Uses current sell-through rates and baseline revenue figures to generate best-case and worst-case projections for tomorrow, next week, next month, and next year.

## Generated Runtime Artefacts

Running `simulate.py` writes local operational outputs (excluded from version control via `.gitignore`):

* **Timestamped Purchase Order PDFs (`po_YYYYMMDD_HHMMSS.pdf`):** Generated with the exact execution date and run time and attached to supplier approval drafts:
  ```text
  PURCHASE ORDER — TechSupply Ltd
  Generated: 2026-11-17 08:07
  Item: 27-inch Monitors | Quantity: 25
  Total Amount: GBP 850.00
  Status: PENDING HUMAN & SUPERVISOR SIGN-OFF
  ```
* **Weekly Department Report (`weekly_department_report.xlsx`):** Multi-tab Excel workbook refreshed on each run across Support KPIs, Stock Control, and Growth Targets:
  * **Support KPIs:** `2026-11-17` — `42` tickets handled, `28` resolved (`66.7%` resolution rate).
  * **Growth Targets:** `B2B Tech Startups` (`+18.5%` MoM growth — expand USB-C Dock bundles at `116.7%` sell-through) and `Corporate Offices` (`-6%` MoM growth — discount overbought 27-inch Monitors at `53.3%` sell-through).
* **SQLite Audit & Checkpoint Databases (`ops_audit.db`, `checkpoints.db`):** Persistent event logs and LangGraph thread checkpoints.

## Engineering Trade-offs

* **Closed-loop SQLite state:** Warehouse stock lives in a persistent SQLite `inventory` table rather than static prompt text. When a restock PO passes both the Supervisor score threshold and human sign-off, `increment_stock()` updates the table and refreshes `weekly_department_report.xlsx` so `CRITICAL LOW` items flip to `HEALTHY` on subsequent runs.
* **Deterministic guardrails over LLM autonomy:** Separating LLM risk scoring (`evaluate_order_risk`) from hard Python checks (`finalize_decision`) ensures any PO scored `< 5/10` (exceeding the `£1,000` cap, unapproved vendor, or flagged `OVERBOUGHT`) is automatically rejected even if a human reviewer types `y`.
* **Zero-token BI arithmetic:** Sell-through percentages (`Actual / Projected`) and weeks-of-cover calculations run in `pandas` before the LLM sees the data, preventing arithmetic hallucinations and keeping token usage minimal.
* **Rate-limit resilience (`tenacity`):** Chained multi-agent LLM calls can hit `429` throttling on free-tier endpoints. Wrapping model calls in exponential backoff with randomised jitter (`2s–30s`) prevents dropped state during multi-event simulations.

## Quickstart

```bash
git clone https://github.com/rma10000/ops-approval-orchestrator
cd ops-approval-orchestrator

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env       # Add your Groq API key (LLM_API_KEY) and set LLM_BASE_URL=https://api.groq.com/openai/v1
python -m pytest test -v   # Run offline guardrail & stock math tests (£0 cost)
python -m simulate         # Run 4-event live simulation with human approval prompts
python -m evals            # Run 12-case routing & policy guardrail benchmark
```

**Windows PowerShell All-in-One Run:**
```powershell
.\.venv\Scripts\python.exe -m pytest test -v; .\.venv\Scripts\python.exe -m simulate; .\.venv\Scripts\python.exe -m evals
```

## Benchmarks & Test Results

Local verification and evaluation results from `openai/gpt-oss-120b` via Groq (`£0` runtime cost):

| Suite | Cases | Result | What It Tests |
| :--- | :---: | :---: | :--- |
| **Offline Unit Guardrails (`pytest`)** | 4 | 100% (4/4) | Policy score overrides, human rejection handling, and stock health classification |
| **Intent Routing (`evals`)** | 6 | 100% (6/6) | Routes `stock`, `planning`, and `support` tickets accurately |
| **Policy & Overbought Guardrails (`evals`)** | 6 | 100% (6/6) | Rejects `> £1,000` POs, unknown vendors, and `OVERBOUGHT` SKUs |
