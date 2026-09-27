"""
dependencies.py — Impact & Dependency Intelligence Router (Innovation 2 & 6)

Endpoints:
  GET  /api/dependencies/graph            — Full operational asset dependency graph
  POST /api/dependencies/simulate-failure — Simulate single asset failure & return multi-tier cascade + cross-agency actions
  GET  /api/dependencies/assets           — List of key infrastructure assets for UI selector
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from core.dependency_graph import dependency_engine

router = APIRouter(prefix="/api/dependencies", tags=["Impact & Dependency Intelligence"])


class FailureSimulationRequest(BaseModel):
    asset_id: str
    scenario_notes: Optional[str] = None


@router.get("/graph")
def get_dependency_graph():
    """
    Returns the complete operational dependency graph:
    Nodes: Power, Pumps, Telecom, Bridges, Shelters, Hospitals, NDRF
    Edges: Directional operational dependencies with criticality ratings
    """
    return dependency_engine.get_full_graph()


@router.get("/assets")
def get_assets_list():
    """Returns quick lookup list of assets for dropdown selectors in the UI."""
    graph = dependency_engine.get_full_graph()
    assets = [
        {
            "id": n["id"],
            "name": n["name"],
            "type": n["type"],
            "agency": n["agency"],
            "coordinates": n["coordinates"]
        }
        for n in graph["nodes"]
    ]
    return {"status": "success", "assets": assets}


@router.post("/simulate-failure")
def simulate_failure(req: FailureSimulationRequest):
    """
    Simulates what happens if a specific asset fails.
    Traces multi-level downstream cascades and prescribes synchronized
    cross-agency corrective actions.
    """
    result = dependency_engine.simulate_failure(req.asset_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result
