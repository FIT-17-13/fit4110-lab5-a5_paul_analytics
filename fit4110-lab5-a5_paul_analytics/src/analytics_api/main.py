import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

SERVICE_NAME = os.getenv("SERVICE_NAME", "a5-analytics-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.5.0-team-analytics")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://lab05:lab05pass@db:5432/analyticsdb",
)
WORKER_URL = os.getenv("WORKER_URL", "http://analytics-worker:9000")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def problem(status_code: int, title: str, detail: str, instance: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    return body


def connect_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def initialise_database(max_attempts: int = 20) -> None:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with connect_db() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analytics_events (
                        event_id UUID PRIMARY KEY,
                        event_type VARCHAR(100) NOT NULL,
                        event_version VARCHAR(20) NOT NULL,
                        occurred_at TIMESTAMPTZ NOT NULL,
                        correlation_id VARCHAR(120) NOT NULL,
                        source VARCHAR(120) NOT NULL,
                        data JSONB NOT NULL,
                        risk_score DOUBLE PRECISION NOT NULL DEFAULT 0,
                        category VARCHAR(50) NOT NULL DEFAULT 'normal',
                        received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_analytics_events_type ON analytics_events(event_type)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_analytics_events_received_at ON analytics_events(received_at DESC)"
                )
                conn.commit()
            return
        except Exception as exc:  # startup retry for Compose readiness
            last_error = exc
            time.sleep(min(attempt, 3))
    raise RuntimeError(f"Database is not ready: {last_error}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialise_database()
    yield


app = FastAPI(
    title="A5 Analytics Service - FIT4110 Lab 05",
    version=SERVICE_VERSION,
    description="Nhận event từ Core Business, lưu PostgreSQL và gọi analytics worker trong Docker Compose.",
    lifespan=lifespan,
)


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    detail: str
    instance: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    database: str
    worker: str


class CoreEventData(BaseModel):
    decision: str | None = None
    severity: str | None = None
    policy_id: str | None = Field(default=None, alias="policyId")
    alert_id: str | None = Field(default=None, alias="alertId")
    value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "allow"}


class CoreEvent(BaseModel):
    event_id: uuid.UUID = Field(alias="eventId")
    event_type: Literal["policy.decision.created", "alert.created", "alert.resolved"] = Field(alias="eventType")
    event_version: str = Field(default="1.0.0", alias="eventVersion")
    occurred_at: datetime = Field(alias="occurredAt")
    correlation_id: str = Field(min_length=1, alias="correlationId")
    source: str = Field(min_length=1)
    data: CoreEventData

    model_config = {"populate_by_name": True}


class EventAccepted(BaseModel):
    event_id: uuid.UUID
    accepted: bool
    category: str
    risk_score: float
    received_at: datetime


class EventItem(BaseModel):
    event_id: uuid.UUID
    event_type: str
    event_version: str
    occurred_at: datetime
    correlation_id: str
    source: str
    data: dict[str, Any]
    risk_score: float
    category: str
    received_at: datetime


class SummaryResponse(BaseModel):
    total_events: int
    by_type: dict[str, int]
    by_category: dict[str, int]
    average_risk_score: float


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    content = exc.detail if isinstance(exc.detail, dict) else problem(exc.status_code, "Request failed", str(exc.detail))
    content.setdefault("instance", request.url.path)
    return JSONResponse(status_code=exc.status_code, content=content, media_type="application/problem+json")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []))
    detail = f"{location}: {first.get('msg', 'Invalid request')}" if location else "Invalid request"
    return JSONResponse(
        status_code=422,
        content=problem(422, "Validation error", detail, request.url.path),
        media_type="application/problem+json",
    )


def verify_token(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail=problem(401, "Unauthorized", "Missing or invalid bearer token"))


async def worker_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{WORKER_URL}/health")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    db_status = "ok"
    try:
        with connect_db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        db_status = "unavailable"

    worker_status = "ok" if await worker_health() else "unavailable"
    overall = "ok" if db_status == "ok" and worker_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        database=db_status,
        worker=worker_status,
    )


@app.post(
    "/events/core",
    response_model=EventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_token)],
    tags=["events"],
    responses={401: {"model": ProblemDetails}, 409: {"model": ProblemDetails}, 503: {"model": ProblemDetails}},
)
async def receive_core_event(payload: CoreEvent) -> EventAccepted:
    worker_payload = {
        "eventType": payload.event_type,
        "data": payload.data.model_dump(by_alias=True, exclude_none=True),
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            worker_response = await client.post(f"{WORKER_URL}/analyze", json=worker_payload)
            worker_response.raise_for_status()
            analysis = worker_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=problem(503, "Worker unavailable", str(exc))) from exc

    received_at = datetime.now(timezone.utc)
    try:
        with connect_db() as conn:
            conn.execute(
                """
                INSERT INTO analytics_events (
                    event_id, event_type, event_version, occurred_at,
                    correlation_id, source, data, risk_score, category, received_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    payload.event_id,
                    payload.event_type,
                    payload.event_version,
                    payload.occurred_at,
                    payload.correlation_id,
                    payload.source,
                    payload.data.model_dump_json(by_alias=True, exclude_none=True),
                    analysis["risk_score"],
                    analysis["category"],
                    received_at,
                ),
            )
            conn.commit()
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status_code=409, detail=problem(409, "Duplicate event", f"Event {payload.event_id} already exists")) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=problem(503, "Database unavailable", str(exc))) from exc

    return EventAccepted(
        event_id=payload.event_id,
        accepted=True,
        category=analysis["category"],
        risk_score=analysis["risk_score"],
        received_at=received_at,
    )


@app.get("/events/recent", response_model=list[EventItem], dependencies=[Depends(verify_token)], tags=["events"])
def recent_events(limit: int = Query(default=10, ge=1, le=100)) -> list[EventItem]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT event_id, event_type, event_version, occurred_at, correlation_id,
                   source, data, risk_score, category, received_at
            FROM analytics_events
            ORDER BY received_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [EventItem(**row) for row in rows]


@app.get("/analytics/summary", response_model=SummaryResponse, dependencies=[Depends(verify_token)], tags=["analytics"])
def analytics_summary() -> SummaryResponse:
    with connect_db() as conn:
        total_row = conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(AVG(risk_score), 0) AS average FROM analytics_events"
        ).fetchone()
        type_rows = conn.execute(
            "SELECT event_type, COUNT(*) AS count FROM analytics_events GROUP BY event_type"
        ).fetchall()
        category_rows = conn.execute(
            "SELECT category, COUNT(*) AS count FROM analytics_events GROUP BY category"
        ).fetchall()

    return SummaryResponse(
        total_events=total_row["total"],
        by_type={row["event_type"]: row["count"] for row in type_rows},
        by_category={row["category"]: row["count"] for row in category_rows},
        average_risk_score=round(float(total_row["average"]), 4),
    )
