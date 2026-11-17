import logging
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential
from src.db import export_department_workbook, increment_stock, log_audit_event
from src.state import OpsState, OrderAssessment
from src.tools import generate_purchase_order_pdf

load_dotenv()
logger = logging.getLogger(__name__)

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
    api_key=os.getenv("LLM_API_KEY") or os.getenv("GITHUB_TOKEN", "dummy-key"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    temperature=0,
)

BASE_POLICIES = (
    "SPEND & SUPPLIER POLICY:\n"
    "- Approved vendor: TechSupply Ltd. Spend cap: £1,000 per PO.\n"
    "- Orders exceeding £1,000, unapproved vendors, or items marked OVERBOUGHT/SLOW-MOVING "
    "must be scored <= 3/10 with recommendation REJECT.\n"
    "BASELINE METRICS: Daily £450 | Weekly £3,150 | Monthly £13,500 | Yearly £162,000."
)


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_random_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _invoke_with_retry(runnable, prompt: str):
    return runnable.invoke(prompt)


def sync_memory_and_metrics(state: OpsState) -> dict:
    req = state["incoming_request"]
    log_audit_event("MemoryAgent", f"Ingested request: {req}")
    inventory_brief = export_department_workbook()
    return {"company_memory": f"{BASE_POLICIES}\n\n{inventory_brief}"}


def route_request(state: OpsState) -> dict:
    res = _invoke_with_retry(
        llm,
        "Classify this operational request into exactly one label: stock, planning, or support.\n"
        f"Request: {state['incoming_request']}",
    )
    label = res.content.strip().lower()
    route = "stock" if "stock" in label else "planning" if "planning" in label else "support"
    logger.info("Routed request to [%s]", route)
    return {"route": route}


def draft_stock_order(state: OpsState) -> dict:
    po_llm = llm.bind_tools([generate_purchase_order_pdf])
    response = _invoke_with_retry(
        po_llm,
        "Extract supplier, item (exact catalog name e.g. 'USB-C Docks'), quantity, and GBP total "
        f"from this request and call generate_purchase_order_pdf:\n{state['incoming_request']}",
    )

    pdf_path = "po_manual_review.pdf"
    order_item, order_qty = "", 0

    if response.tool_calls:
        args = response.tool_calls[0]["args"]
        order_item = args.get("item", "")
        order_qty = int(args.get("quantity", 0))
        pdf_path = generate_purchase_order_pdf.invoke(args)

    email_res = _invoke_with_retry(
        llm,
        f"Write a concise restock PO email for: {state['incoming_request']}. "
        f"Reference attached file {pdf_path}.",
    )
    return {
        "order_item": order_item,
        "order_qty": order_qty,
        "email_draft": email_res.content.strip(),
        "invoice_path": pdf_path,
    }


def evaluate_order_risk(state: OpsState) -> dict:
    rater = llm.with_structured_output(OrderAssessment)
    assessment: OrderAssessment = _invoke_with_retry(
        rater,
        "Audit this pending purchase order against company rules and current stock health "
        "(check the requested item's exact status in the inventory list below).\n"
        f"{state['company_memory']}\n\n"
        f"Request: {state['incoming_request']}\n"
        f"Draft Email: {state['email_draft']}",
    )
    summary = f"{assessment.score}/10 ({assessment.risk_level}) — {assessment.recommendation}: {assessment.reason}"
    logger.info("Supervisor risk rating: %s", summary)
    return {"boss_rating_text": summary, "boss_score": assessment.score}


def await_human_signoff(state: OpsState) -> dict:
    decision = interrupt(
        {
            "boss_rating": state["boss_rating_text"],
            "invoice_file": state["invoice_path"],
            "email_draft": state["email_draft"],
        }
    )
    approved = str(decision).strip().lower() in {"y", "yes", "approve"}
    return {"human_approved": approved}


def generate_forecast(state: OpsState) -> dict:
    res = _invoke_with_retry(
        llm,
        "Using the baseline metrics, stock sell-through health, and segment trends below, "
        "produce concise best-case and worst-case projections for Tomorrow, Next Week, "
        "Next Month, and Next Year.\n\n"
        f"{state['company_memory']}",
    )
    return {"forecast_report": res.content.strip()}


def finalize_decision(state: OpsState) -> dict:
    route = state.get("route", "support")

    if route == "stock":
        score = state.get("boss_score", 0)
        human_ok = state.get("human_approved", False)

        if human_ok and score >= 5:
            stock_msg = ""
            if state.get("order_item") and state.get("order_qty", 0) > 0:
                stock_msg = f" | {increment_stock(state['order_item'], state['order_qty'])}"
                export_department_workbook()
            verdict = f"APPROVED — Human signed off (Supervisor score {score}/10){stock_msg}"
        elif human_ok and score < 5:
            verdict = f"REJECTED — Policy guardrail blocked PO (Supervisor score {score}/10 < 5)"
        else:
            verdict = "REJECTED — Declined by human reviewer"
    elif route == "planning":
        verdict = "APPROVED — Multi-horizon forecast generated & Excel report updated"
    else:
        verdict = "APPROVED — Support ticket logged to audit trail"

    log_audit_event("SupervisorAgent", verdict, rating=state.get("boss_rating_text", "N/A"))
    return {"boss_verdict": verdict}
