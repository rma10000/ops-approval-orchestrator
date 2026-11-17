from typing import Literal, TypedDict
from pydantic import BaseModel, Field


class OrderAssessment(BaseModel):
    score: int = Field(ge=1, le=10, description="Policy compliance score from 1 to 10")
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    recommendation: Literal["APPROVE", "REJECT"]
    reason: str = Field(description="Concise rationale grounded in spend caps and stock health")


class OpsState(TypedDict, total=False):
    incoming_request: str
    route: Literal["stock", "planning", "support"]
    company_memory: str
    order_item: str
    order_qty: int
    email_draft: str
    invoice_path: str
    boss_rating_text: str
    boss_score: int
    human_approved: bool
    forecast_report: str
    boss_verdict: str
