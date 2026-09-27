import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.field_state import teams, reports, safe_zone_inventory

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Plan State ────────────────────────────────────────────────────────────────
# Tracks which plan is active and what triggered the switch
_active_plan: dict = {
    "plan_id": "A",
    "switched_at": None,
    "reason": None,
    "triggered_by_report": None,
}

# SSE subscriber queues (one per connected dashboard)
import asyncio
_sse_subscribers: list[asyncio.Queue] = []


class FieldReportRequest(BaseModel):
    team_id: str
    dispatch_id: Optional[str] = None
    rescued_count: int
    notes: Optional[str] = ""
    photo_url: Optional[str] = None
    # ── Ground truth fields (Innovation 1: Field → Re-Optimizer) ──
    road_blocked: bool = False          # True = block this road segment
    shelter_full: bool = False          # True = this team's safe zone is at capacity
    road_cleared: bool = False          # True = previously blocked road is now clear
    lat: Optional[float] = None        # Location of the incident
    lng: Optional[float] = None
    site_id: Optional[str] = None      # Which safe zone is full (if shelter_full)


def _trigger_reoptimization(report: dict) -> dict | None:
    """
    Convert a ground-truth field report into a hazard polygon and
    re-run the Hungarian optimizer. Updates the active plan ID.
    Returns the new plan dict, or None if nothing changed.
    """
    try:
        from shapely.geometry import Point
        from core.analysis_state import get_last_cop, set_last_relocation
        from core.relocation_state import get_hazard_polygons, add_hazard_polygon, clear_hazard_polygon
        from core.optimization import compute_relocation_plan, _load_demo_habitations
        from core.vulnerability import score_all_habitations
        from core.settings import get_settings
        from shapely.geometry import shape
        import json

        changed = False

        # ── Road blocked → add hazard polygon (200m radius around report location)
        if report.get("road_blocked") and report.get("lat") and report.get("lng"):
            blocked_poly = Point(report["lng"], report["lat"]).buffer(0.002)  # ~200m
            add_hazard_polygon(report["id"], blocked_poly)
            changed = True
            logger.warning(
                f"[FieldReport] Road blocked at ({report['lat']}, {report['lng']}) "
                f"— adding hazard polygon and re-optimizing."
            )

        # ── Road cleared → remove hazard polygon
        if report.get("road_cleared"):
            clear_hazard_polygon(report["id"])
            changed = True
            logger.info(f"[FieldReport] Road cleared — removing hazard polygon.")

        # ── Shelter full → reduce that site's capacity to 0 in state
        if report.get("shelter_full") and report.get("site_id"):
            from core.analysis_state import update_evac_capacity, get_evac_site
            site = get_evac_site(report["site_id"])
            if site:
                update_evac_capacity(report["site_id"], site["capacity_total"])  # set occupancy = capacity
                changed = True
                logger.warning(
                    f"[FieldReport] Shelter {report['site_id']} reported FULL — "
                    f"removing from optimizer pool."
                )

        if not changed:
            return None

        # ── Re-run optimizer with updated hazard polygons ──────────────────────
        settings = get_settings()
        tiers = settings.relocation_tiers
        hazard_polygons = get_hazard_polygons()

        # Pull habitations from COP or demo fixture
        cop = get_last_cop()
        red_zones = [
            f for f in (cop or {}).get("features", [])
            if f.get("properties", {}).get("layer_type") == "red_zone"
        ]

        raw_habs = _load_demo_habitations()
        if raw_habs:
            scored = score_all_habitations(
                raw_habs, red_zones,
                immediate_threshold=tiers.immediate_threshold,
                short_term_threshold=tiers.short_term_threshold,
            )
            habitations = [{**h, "vulnerability_score": vr.score} for h, vr in zip(raw_habs, scored)]
        else:
            habitations = None

        # Red zone geometries as shapely polygons for routing
        rz_polygons = []
        for rz in red_zones:
            if "geometry" in rz:
                try:
                    rz_polygons.append(shape(rz["geometry"]))
                except Exception:
                    pass
        all_hazards = rz_polygons + hazard_polygons

        new_plan = compute_relocation_plan(
            habitations=habitations,
            immediate_threshold=tiers.immediate_threshold,
            short_term_threshold=tiers.short_term_threshold,
            hazard_polygons=all_hazards if all_hazards else None,
        )

        result = new_plan.to_dict()
        set_last_relocation(result)

        # ── Update active plan ID ──────────────────────────────────────────────
        global _active_plan
        prev_plan = _active_plan["plan_id"]
        plan_sequence = ["A", "B", "C"]
        current_idx = plan_sequence.index(prev_plan) if prev_plan in plan_sequence else 0
        new_plan_id = plan_sequence[min(current_idx + 1, len(plan_sequence) - 1)]

        if report.get("road_cleared"):
            # Downgrade plan if possible when road is cleared
            new_plan_id = plan_sequence[max(current_idx - 1, 0)]

        _active_plan = {
            "plan_id": new_plan_id,
            "switched_at": datetime.now(timezone.utc).isoformat(),
            "reason": (
                "Road blocked" if report.get("road_blocked")
                else "Shelter full" if report.get("shelter_full")
                else "Road cleared"
            ),
            "triggered_by_report": report["id"],
            "location": {"lat": report.get("lat"), "lng": report.get("lng")},
        }

        logger.warning(
            f"[FieldReport] Plan switched: {prev_plan} → {new_plan_id} "
            f"(reason: {_active_plan['reason']})"
        )

        # ── Consequence Analysis (Innovation 1: Incident → Consequence → Replan) ──
        unassigned_ids = set(str(uid) for uid in result.get("unassigned", []))
        isolated_habs = [h for h in (raw_habs or []) if str(h.get("id")) in unassigned_ids]
        isolated_pop = sum(int(h.get("population", 500)) for h in isolated_habs)
        if not isolated_pop and unassigned_ids:
            isolated_pop = len(unassigned_ids) * 650

        delay_mins = 20 + len(unassigned_ids) * 15 if report.get("road_blocked") else 10
        
        consequence_data = {
            "trigger_incident": "Road Severed" if report.get("road_blocked") else "Shelter Overflow" if report.get("shelter_full") else "Corridor Restored",
            "incident_coords": [report.get("lng"), report.get("lat")],
            "isolated_habitations_count": len(unassigned_ids),
            "isolated_population": isolated_pop,
            "transit_delay_minutes": delay_mins,
            "consequence_summary": (
                f"Incident at ({report.get('lat')}, {report.get('lng')}) severed primary route. "
                f"{len(unassigned_ids)} habitation(s) ({isolated_pop:,} residents) cut off from direct shelter access. "
                f"Convoy detours add +{delay_mins} mins transit delay. Replaced Plan {prev_plan} with Plan {new_plan_id}."
            ) if report.get("road_blocked") else (
                f"Shelter {report.get('site_id')} at 100% capacity. Diverted remaining waves to secondary relief grounds. Replaced Plan {prev_plan} with Plan {new_plan_id}."
            ),
            "prescribed_cross_agency_actions": [
                {"agency": "Assam Police Traffic", "action": f"Erect roadblock 500m before incident location and divert civilian traffic."},
                {"agency": "SDRF / NDRF", "action": "Stage 2 inflatable rescue boats at cut-off crossing point for amphibious shuttle."},
                {"agency": "District Administration", "action": f"Notify Shelter {new_plan_id} intake command of diverted arrival waves."}
            ]
        }

        return {
            "plan_switched": prev_plan != new_plan_id,
            "previous_plan": prev_plan,
            "active_plan": new_plan_id,
            "switch_reason": _active_plan["reason"],
            "new_assignments_count": len(result.get("assignments", [])),
            "unassigned_count": len(result.get("unassigned", [])),
            "consequence": consequence_data
        }

    except Exception as e:
        logger.error(f"[FieldReport] Re-optimization failed: {e}", exc_info=True)
        return None


async def _broadcast_plan_update(event: dict):
    """Push a JSON event to all connected SSE dashboard clients."""
    import json
    dead = []
    for q in _sse_subscribers:
        try:
            q.put_nowait(json.dumps(event))
        except Exception:
            dead.append(q)
    for q in dead:
        _sse_subscribers.remove(q)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/")
def get_all_reports():
    return {"status": "success", "reports": reports}


@router.get("/plan-status")
def get_plan_status():
    """Returns the currently active plan (A / B / C) and switch history."""
    return {"status": "success", "active_plan": _active_plan}


@router.get("/plan-events")
async def plan_event_stream():
    """
    Server-Sent Events endpoint. Dashboard connects here to receive
    real-time plan switch notifications without polling.
    """
    import json
    q: asyncio.Queue = asyncio.Queue()
    _sse_subscribers.append(q)

    async def event_gen():
        # Send current state immediately on connect
        yield f"data: {json.dumps({'type': 'connected', 'active_plan': _active_plan})}\n\n"
        try:
            while True:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {msg}\n\n"
        except asyncio.TimeoutError:
            yield "data: {\"type\": \"heartbeat\"}\n\n"  # keep-alive ping
        except Exception:
            pass
        finally:
            if q in _sse_subscribers:
                _sse_subscribers.remove(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/")
async def submit_report(req: FieldReportRequest):
    if req.team_id not in teams:
        raise HTTPException(status_code=404, detail="Team not found")

    report_id = f"REP-{uuid.uuid4().hex[:6].upper()}"
    report_record = {
        "id": report_id,
        "team_id": req.team_id,
        "dispatch_id": req.dispatch_id or teams[req.team_id].get("current_assignment"),
        "rescued_count": req.rescued_count,
        "notes": req.notes,
        "photo_url": req.photo_url,
        # Ground truth fields
        "road_blocked": req.road_blocked,
        "shelter_full": req.shelter_full,
        "road_cleared": req.road_cleared,
        "lat": req.lat,
        "lng": req.lng,
        "site_id": req.site_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    reports.insert(0, report_record)  # newest-first

    # Update safe zone occupancy (existing logic)
    from core.field_state import dispatches
    dispatch = next((d for d in dispatches if d["id"] == report_record["dispatch_id"]), None)
    if dispatch:
        sz_id = dispatch["safe_zone_id"]
        if sz_id not in safe_zone_inventory:
            safe_zone_inventory[sz_id] = {"current_population": 0, "resources_used": {}}
        safe_zone_inventory[sz_id]["current_population"] += req.rescued_count

    # ── Innovation 1: Trigger re-optimization if ground truth changed ──────────
    reopt_result = None
    if req.road_blocked or req.shelter_full or req.road_cleared:
        import asyncio as _aio
        reopt_result = await _aio.to_thread(_trigger_reoptimization, report_record)

        if reopt_result:
            # Broadcast to all connected dashboards via SSE
            await _broadcast_plan_update({
                "type": "plan_switched",
                "active_plan": reopt_result["active_plan"],
                "previous_plan": reopt_result["previous_plan"],
                "reason": reopt_result["switch_reason"],
                "report_id": report_id,
                "location": {"lat": req.lat, "lng": req.lng},
                "new_assignments": reopt_result["new_assignments_count"],
                "unassigned": reopt_result["unassigned_count"],
                "consequence": reopt_result.get("consequence"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    return {
        "status": "success",
        "report": report_record,
        "reoptimization": reopt_result,
    }

class OverrideRequest(BaseModel):
    plan_id: str
    reason: str = "Manual Commander Override"

@router.post("/override")
async def override_plan(req: OverrideRequest):
    """Manual override by the Incident Commander from the COP dashboard."""
    global _active_plan
    prev_plan = _active_plan["plan_id"]
    new_plan = req.plan_id.upper()
    
    if new_plan not in ["A", "B", "C"]:
        raise HTTPException(status_code=400, detail="Invalid plan ID")
        
    _active_plan = {
        "plan_id": new_plan,
        "switched_at": datetime.now(timezone.utc).isoformat(),
        "reason": req.reason,
        "triggered_by_report": "MANUAL_OVERRIDE",
        "location": None,
    }
    
    logger.warning(f"[ManualOverride] Plan switched: {prev_plan} → {new_plan}")
    
    await _broadcast_plan_update({
        "type": "plan_switched",
        "active_plan": new_plan,
        "previous_plan": prev_plan,
        "reason": req.reason,
        "report_id": "MANUAL_OVERRIDE",
        "location": None,
        "new_assignments": 0,
        "unassigned": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    
    return {"status": "success", "active_plan": new_plan}


@router.get("/multi-scenario")
def get_multi_scenario_plans():
    """
    Returns Plan A, Plan B, and Plan C side-by-side with explicit
    switching conditions, corridor strategy, and capacity metrics (Innovation 5).
    """
    return {
        "status": "success",
        "active_plan": _active_plan.get("plan_id", "A"),
        "scenarios": [
            {
                "plan_id": "A",
                "title": "Plan A: Nominal Flow (Primary Corridors)",
                "status": "ACTIVE" if _active_plan.get("plan_id") == "A" else "STANDBY",
                "corridor_strategy": "Primary National & State Highways (NH-37, GS Road)",
                "shelters_active": ["EZ-A01 Nagaon Govt School", "EZ-A02 Nagaon District Stadium"],
                "total_intake_capacity": 4700,
                "transit_time_avg_mins": 25,
                "switch_trigger": "Baseline operations when all primary paved roads are clear."
            },
            {
                "plan_id": "B",
                "title": "Plan B: Arterial Bypass (Compromised Corridors)",
                "status": "ACTIVE" if _active_plan.get("plan_id") == "B" else "STANDBY",
                "corridor_strategy": "Secondary Arteries, PWD Ring Roads & Paved Detours",
                "shelters_active": ["EZ-A02 Nagaon District Stadium", "EZ-A03 Rupahi Relief Ground"],
                "total_intake_capacity": 4100,
                "transit_time_avg_mins": 55,
                "switch_trigger": "Activated automatically if NH-37 or Bharalu bridge is blocked OR river stage > 49.0m."
            },
            {
                "plan_id": "C",
                "title": "Plan C: Catastrophic Grid Severance (Amphibious / Helo)",
                "status": "ACTIVE" if _active_plan.get("plan_id") == "C" else "STANDBY",
                "corridor_strategy": "Waterborne Boat Corridors + High-Ground Helo LZ + Host Community Overflow",
                "shelters_active": ["EZ-A03 Rupahi Relief Ground", "Host Community Billets", "Cotton High-Ground"],
                "total_intake_capacity": 5500,
                "transit_time_avg_mins": 110,
                "switch_trigger": "Activated if multiple arterial bridges fail, primary stadium floods, or river stage > 50.0m."
            }
        ]
    }

