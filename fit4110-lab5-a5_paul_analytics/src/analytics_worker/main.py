import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("WORKER_SERVICE_NAME", "a5-analytics-worker")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0-team-analytics")

app = FastAPI(title="A5 Analytics Worker", version=SERVICE_VERSION)


class AnalyzeRequest(BaseModel):
    event_type: str = Field(alias="eventType")
    data: dict[str, Any]
    model_config = {"populate_by_name": True}


class AnalyzeResponse(BaseModel):
    category: str
    risk_score: float
    explanation: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    severity = str(payload.data.get("severity", "")).lower()
    decision = str(payload.data.get("decision", "")).lower()

    if severity in {"critical", "high"} or decision in {"deny", "denied", "reject", "rejected"}:
        return AnalyzeResponse(category="high-risk", risk_score=0.9, explanation="High severity or denied policy decision")
    if payload.event_type == "alert.created" or severity == "medium":
        return AnalyzeResponse(category="needs-review", risk_score=0.6, explanation="New alert requires review")
    if payload.event_type == "alert.resolved":
        return AnalyzeResponse(category="resolved", risk_score=0.1, explanation="Alert has been resolved")
    return AnalyzeResponse(category="normal", risk_score=0.2, explanation="No high-risk signal detected")
