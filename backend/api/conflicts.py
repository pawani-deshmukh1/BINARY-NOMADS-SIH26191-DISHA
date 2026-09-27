"""
conflicts.py — Verification Priority & Decision Confidence Router (Innovations 3, 5 & 8)

Endpoints:
  GET  /api/conflicts/priority-queue — Priority ranked list of contradictory observations needing ground verification
  GET  /api/conflicts/confidence     — Real-time data-aware decision confidence score (0–100%) and factors
  POST /api/conflicts/resolve        — Commander marks conflict resolved based on field scout verification
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from core.conflict_detector import conflict_engine

router = APIRouter(prefix="/api/conflicts", tags=["Evidence Conflict & Decision Confidence"])


class ResolveConflictRequest(BaseModel):
    conflict_id: str
    resolution_notes: str
    winner: str = "FIELD_OBSERVATION"  # Which source was deemed correct


@router.get("/priority-queue")
def get_priority_queue():
    """
    Returns prioritized verification queue. Ranks conflicting reports
    by severity, affected population, data latency, and road criticality.
    """
    return conflict_engine.get_verification_priority_queue()


@router.get("/confidence")
def get_decision_confidence(
    rainfall_mm_hr: float = Query(0.0, description="Current live rainfall rate"),
    river_level_m: float = Query(48.0, description="Current river gauge stage")
):
    """
    Returns mathematical decision confidence (0–100%) reflecting sensor freshness,
    satellite latency, active unverified conflicts, and resolution-aware safeguards.
    """
    return conflict_engine.calculate_decision_confidence(rainfall_mm_hr, river_level_m)


@router.post("/resolve")
def resolve_conflict(req: ResolveConflictRequest):
    """
    Marks a conflict resolved after field verification. Boosts overall decision confidence.
    """
    result = conflict_engine.resolve_conflict(req.conflict_id, req.resolution_notes, req.winner)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result
