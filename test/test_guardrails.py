import pandas as pd
from src.agents import finalize_decision
from src.db import _classify_stock


def test_blocks_low_rated_order_even_if_human_approves():
    state = {"route": "stock", "human_approved": True, "boss_score": 2}
    result = finalize_decision(state)
    assert result["boss_verdict"].startswith("REJECTED — Policy guardrail")


def test_approves_compliant_order_with_human_signoff():
    state = {"route": "stock", "human_approved": True, "boss_score": 9}
    result = finalize_decision(state)
    assert result["boss_verdict"].startswith("APPROVED")


def test_respects_human_rejection():
    state = {"route": "stock", "human_approved": False, "boss_score": 9}
    result = finalize_decision(state)
    assert result["boss_verdict"] == "REJECTED — Declined by human reviewer"


def test_stock_health_classifier():
    overbought = pd.Series(
        {"Current_Stock": 110, "Reorder_Threshold": 15, "Projected_Weekly_Sales": 15, "Actual_Weekly_Sales": 8}
    )
    critical = pd.Series(
        {"Current_Stock": 5, "Reorder_Threshold": 15, "Projected_Weekly_Sales": 12, "Actual_Weekly_Sales": 14}
    )
    assert _classify_stock(overbought) == "OVERBOUGHT"
    assert _classify_stock(critical) == "CRITICAL LOW"
