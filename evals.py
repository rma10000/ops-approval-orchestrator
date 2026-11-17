import time
from src.agents import evaluate_order_risk, route_request, sync_memory_and_metrics

ROUTING_CASES = [
    ("Restock 20 USB-C Docks from TechSupply Ltd for £320.", "stock"),
    ("Order 50 wireless keyboards before Friday.", "stock"),
    ("Give me best and worst case sales predictions for next month.", "planning"),
    ("Run our yearly revenue and inventory forecast.", "planning"),
    ("Customer #104 needs a copy of their VAT invoice.", "support"),
    ("How do I reset my account password?", "support"),
]

POLICY_CASES = [
    ("Restock 25 USB-C Docks from TechSupply Ltd for £400.", True),
    ("Order 15 Wireless Keyboards from TechSupply Ltd for £300.", True),
    ("Restock 40 USB-C Docks from TechSupply Ltd for £1,450.", False),
    ("Order 20 extra 27-inch Monitors from TechSupply Ltd for £700.", False),
    ("Order 15 Webcam Pro 4K units from TechSupply Ltd for £450.", False),
    ("Restock 10 USB-C Docks from UnknownGadgets Co for £200.", False),
]


def run_evals(delay_sec: int = 5) -> None:
    route_hits = 0
    for text, expected in ROUTING_CASES:
        pred = route_request({"incoming_request": text})["route"]
        ok = pred == expected
        route_hits += int(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] Route '{text[:40]}...' -> {pred}")
        time.sleep(delay_sec)

    base_state = sync_memory_and_metrics({"incoming_request": "eval-init"})
    policy_hits = 0
    for text, should_approve in POLICY_CASES:
        res = evaluate_order_risk(
            {
                "incoming_request": text,
                "company_memory": base_state["company_memory"],
                "email_draft": f"Draft PO for: {text}",
            }
        )
        ok = (res["boss_score"] >= 5) == should_approve
        policy_hits += int(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] Policy '{text[:40]}...' -> {res['boss_rating_text']}")
        time.sleep(delay_sec)

    print("\n================ BENCHMARK SUMMARY ================")
    print(f"Intent Routing Accuracy   : {route_hits}/{len(ROUTING_CASES)} ({route_hits/len(ROUTING_CASES)*100:.0f}%)")
    print(f"Policy Guardrail Accuracy : {policy_hits}/{len(POLICY_CASES)} ({policy_hits/len(POLICY_CASES)*100:.0f}%)")
    print("===================================================")


if __name__ == "__main__":
    run_evals(delay_sec=5)
