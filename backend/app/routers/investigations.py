# Start, inspect, and authorize decisions on checkpointed investigations.
import logging
from contextlib import contextmanager
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy.engine import make_url

from backend.app.config import get_settings
from backend.app.security import limit_ai_requests, provider_status, require_decision_authorization
from backend.app.services.investigation import build_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/investigations", tags=["investigations"])


class InvestigationRequest(BaseModel):
    request: str = Field(min_length=1, max_length=500)
    product_id: Literal["luna-smartwatch"] = "luna-smartwatch"


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "request_revision"]
    notes: str = Field(default="", max_length=2000)


# Open a PostgreSQL checkpointer so graph state can survive application restarts.
@contextmanager
def graph_context():
    url = make_url(get_settings().database_url).set(drivername="postgresql")
    with PostgresSaver.from_conn_string(url.render_as_string(hide_password=False)) as saver:
        yield build_graph(saver)


# Translate persisted graph state into an API status, including the human approval pause.
def snapshot(graph, thread_id: str):
    state = graph.get_state({"configurable": {"thread_id": thread_id}})
    if not state.values:
        raise HTTPException(status_code=404, detail="Investigation not found")
    status = "failed" if any(task.error for task in state.tasks) else (
        "awaiting_review" if state.next == ("human_approval",) else (
            state.values.get("decision", {}).get("decision") or "in_progress"))
    return {"id": thread_id, "status": status, **state.values}


@router.post("", status_code=201, dependencies=[Depends(limit_ai_requests)])
def start_investigation(request: InvestigationRequest):
    question = request.request.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Request must not be blank")
    thread_id = str(uuid4())
    try:
        with graph_context() as graph:
            try:
                graph.invoke({"request": question, "product_id": request.product_id, "stage": "understand_investigation"},
                             {"configurable": {"thread_id": thread_id}})
            except Exception as exc:
                stage = "unknown"
                try:
                    pending = graph.get_state({"configurable": {"thread_id": thread_id}}).next
                    allowed = {"understand_investigation", "retrieve_evidence", "analyze_evidence", "draft_report", "human_approval"}
                    if pending and pending[0] in allowed:
                        stage = pending[0]
                except Exception:
                    pass
                logger.warning("Investigation failed; thread=%s stage=%s type=%s", thread_id, stage, type(exc).__name__)
                raise
            return snapshot(graph, thread_id)
    except Exception as exc:
        logger.warning("Investigation unavailable; thread=%s type=%s", thread_id, type(exc).__name__)
        raise HTTPException(status_code=provider_status(exc), detail=f"Investigation could not be completed. Check thread {thread_id}.") from None


@router.get("/authorization", dependencies=[Depends(limit_ai_requests), Depends(require_decision_authorization)])
def check_authorization():
    return {"authorized": True}


@router.get("/{investigation_id}")
def get_investigation(investigation_id: UUID):
    with graph_context() as graph:
        return snapshot(graph, str(investigation_id))


# Resume only an investigation that is waiting for an authorized human decision.
@router.post("/{investigation_id}/decision", dependencies=[Depends(limit_ai_requests), Depends(require_decision_authorization)])
def decide_investigation(investigation_id: UUID, decision: DecisionRequest):
    thread_id = str(investigation_id)
    with graph_context() as graph:
        current = snapshot(graph, thread_id)
        if current["status"] != "awaiting_review":
            raise HTTPException(status_code=409, detail="Investigation is not awaiting review")
        graph.invoke(Command(resume=decision.model_dump()), {"configurable": {"thread_id": thread_id}})
        return snapshot(graph, thread_id)
