import os
import sqlite3
from typing import Literal
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from src.agents import (
    await_human_signoff,
    draft_stock_order,
    evaluate_order_risk,
    finalize_decision,
    generate_forecast,
    route_request,
    sync_memory_and_metrics,
)
from src.state import OpsState


def _select_branch(state: OpsState) -> Literal["stock", "planning", "finalize"]:
    route = state.get("route", "support")
    return route if route in {"stock", "planning"} else "finalize"


def build_ops_graph():
    workflow = StateGraph(OpsState)

    workflow.add_node("memory_metrics", sync_memory_and_metrics)
    workflow.add_node("router", route_request)
    workflow.add_node("stock", draft_stock_order)
    workflow.add_node("risk_rater", evaluate_order_risk)
    workflow.add_node("human_gate", await_human_signoff)
    workflow.add_node("planning", generate_forecast)
    workflow.add_node("finalize", finalize_decision)

    workflow.add_edge(START, "memory_metrics")
    workflow.add_edge("memory_metrics", "router")
    workflow.add_conditional_edges("router", _select_branch)

    workflow.add_edge("stock", "risk_rater")
    workflow.add_edge("risk_rater", "human_gate")
    workflow.add_edge("human_gate", "finalize")

    workflow.add_edge("planning", "finalize")
    workflow.add_edge("finalize", END)

    ckpt_path = os.getenv("CHECKPOINT_DB_PATH", "checkpoints.db")
    conn = sqlite3.connect(ckpt_path, check_same_thread=False)
    return workflow.compile(checkpointer=SqliteSaver(conn))
