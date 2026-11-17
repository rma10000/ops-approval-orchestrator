import logging
import time
import uuid
from langgraph.types import Command
from src.graph import build_ops_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

EVENTS = [
    "USB-C Docks dropped to 6 units. Restock 30 units from TechSupply Ltd for £480.",
    "Supplier promo: order 25 extra 27-inch Monitors from TechSupply Ltd for £850.",
    "Customer #882 requested a VAT invoice copy for last week's wireless keyboard order.",
    "Run daily, weekly, monthly, and yearly forecast using updated stock health.",
]


def run_simulation(interval_sec: int = 8) -> None:
    graph = build_ops_graph()

    for idx, payload in enumerate(EVENTS, start=1):
        config = {"configurable": {"thread_id": f"evt-{uuid.uuid4().hex[:6]}"}}
        logger.info("Event %d/%d: %s", idx, len(EVENTS), payload)

        state = graph.invoke({"incoming_request": payload}, config=config)

        if state.get("__interrupt__"):
            interrupt_obj = state["__interrupt__"][0] if isinstance(state["__interrupt__"], list) else state["__interrupt__"]
            prompt_data = interrupt_obj.value
            print("\n--- HUMAN SIGN-OFF REQUIRED ---")
            print(f"Supervisor Rating : {prompt_data['boss_rating']}")
            print(f"Attachment        : {prompt_data['invoice_file']}")
            print(f"Email Draft       :\n{prompt_data['email_draft']}\n")

            choice = input("Approve purchase order? [y/N]: ")
            state = graph.invoke(Command(resume=choice), config=config)

        if state.get("forecast_report"):
            print(f"\n--- FORECAST REPORT ---\n{state['forecast_report']}\n")

        logger.info("Outcome: %s\n", state["boss_verdict"])

        if idx < len(EVENTS):
            time.sleep(interval_sec)


if __name__ == "__main__":
    run_simulation()
