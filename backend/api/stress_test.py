"""
stress_test.py — What-If Stress Testing API (Innovation 4)

Lets an Incident Commander inject failure scenarios before deployment
and see how the relocation plan degrades — without touching real state.

POST /stress-test/inject
  Body: StressScenario
  Returns: {before_plan, after_plan, delta}

GET /stress-test/scenarios
  Returns available scenario templates for the UI.
"""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from copy import deepcopy

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stress-test", tags=["Stress Tester"])


class StressScenario(BaseModel):
    # Road failure
    block_road_lat: Optional[float] = None
    block_road_lng: Optional[float] = None
    block_road_radius_m: float = 200.0

    # Shelter capacity reduction
    shelter_capacity_reduction_pct: float = 0.0   # 0–100
    target_site_id: Optional[str] = None          # which site to reduce

    # Transport fleet reduction
    bus_fleet_reduction_pct: float = 0.0          # 0–100 (affects wave capacity)

    # Rainfall spike multiplier (re-runs GloFAS with extra risk)
    rainfall_spike_multiplier: float = 1.0        # 1.0 = no change, 2.0 = double

    region: str = "assam"


@router.get("/scenarios")
def get_scenario_templates():
    """Returns pre-built stress scenario templates for the dashboard dropdown."""
    return {
        "templates": [
            {
                "id": "bridge_blocked",
                "label": "🌉 NH-37 Bridge Blocked",
                "description": "Main road to Nagaon cut off. Forces optimizer to find alternate routes.",
                "params": {
                    "block_road_lat": 26.18,
                    "block_road_lng": 91.75,
                    "block_road_radius_m": 500,
                }
            },
            {
                "id": "shelter_30pct",
                "label": "🏫 Primary Shelter -30% Capacity",
                "description": "Nagaon Stadium partially damaged. Reduces intake capacity.",
                "params": {
                    "shelter_capacity_reduction_pct": 30,
                    "target_site_id": "EZ-A02",
                }
            },
            {
                "id": "bus_fleet_50pct",
                "label": "🚌 Bus Fleet -50%",
                "description": "Half the transport fleet is unavailable. Evacuation waves doubled.",
                "params": {
                    "bus_fleet_reduction_pct": 50,
                }
            },
            {
                "id": "extreme_rain",
                "label": "🌧️ Rainfall Spike +90%",
                "description": "Sudden intensification of monsoon. Flood zones expand significantly.",
                "params": {
                    "rainfall_spike_multiplier": 1.9,
                }
            },
            {
                "id": "cascade",
                "label": "🔴 Cascade Failure",
                "description": "Bridge blocked + shelter at 50% + bus fleet at 40%. Worst-case.",
                "params": {
                    "block_road_lat": 26.18,
                    "block_road_lng": 91.75,
                    "block_road_radius_m": 500,
                    "shelter_capacity_reduction_pct": 50,
                    "target_site_id": "EZ-A02",
                    "bus_fleet_reduction_pct": 60,
                }
            },
        ]
    }


@router.post("/inject")
def inject_stress_scenario(scenario: StressScenario):
    """
    Run the optimizer against a failure scenario WITHOUT changing live state.
    Returns a before/after comparison with impact metrics.
    """
    try:
        from core.optimization import compute_relocation_plan, _load_demo_habitations
        from core.analysis_state import get_last_cop, get_last_relocation
        from core.relocation_state import get_hazard_polygons
        from core.vulnerability import score_all_habitations
        from core.settings import get_settings
        from shapely.geometry import Point, shape

        settings = get_settings()
        tiers = settings.relocation_tiers

        # ── Baseline plan ────────────────────────────────────────────────────
        before_plan = get_last_relocation() or {}

        # ── Build modified inputs ────────────────────────────────────────────
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
            habitations = []

        # Existing hazard polygons (from real field reports)
        hazard_polys = list(get_hazard_polygons())

        # Inject road blockage
        if scenario.block_road_lat and scenario.block_road_lng:
            radius_deg = scenario.block_road_radius_m / 111_000
            blocked = Point(scenario.block_road_lng, scenario.block_road_lat).buffer(radius_deg)
            hazard_polys.append(blocked)

        # Build evac sites with modified capacity
        from core.optimization import _DEFAULT_EVAC_SITES
        stress_sites = deepcopy(_DEFAULT_EVAC_SITES)

        if scenario.shelter_capacity_reduction_pct > 0 and scenario.target_site_id:
            for s in stress_sites:
                if s["id"] == scenario.target_site_id:
                    reduction = scenario.shelter_capacity_reduction_pct / 100.0
                    s["capacity_remaining"] = int(s["capacity_remaining"] * (1.0 - reduction))
                    s["capacity_persons"] = s["capacity_remaining"]

        # Red zones as shapely
        rz_polygons = []
        for rz in red_zones:
            if "geometry" in rz:
                try:
                    rz_polygons.append(shape(rz["geometry"]))
                except Exception:
                    pass
        all_hazards = rz_polygons + hazard_polys

        # ── Run stressed optimizer ───────────────────────────────────────────
        stressed_plan = compute_relocation_plan(
            habitations=habitations if habitations else None,
            evac_sites=stress_sites,
            immediate_threshold=tiers.immediate_threshold,
            short_term_threshold=tiers.short_term_threshold,
            hazard_polygons=all_hazards if all_hazards else None,
        )
        after_result = stressed_plan.to_dict()

        # ── Compute wave impact of bus fleet reduction ───────────────────────
        wave_impact = {}
        if scenario.bus_fleet_reduction_pct > 0:
            reduction = scenario.bus_fleet_reduction_pct / 100.0
            effective_capacity = int(800 * (1.0 - reduction))
            original_waves = len(before_plan.get("evacuation_waves", []))
            stressed_waves = len(after_result.get("evacuation_waves", []))
            wave_impact = {
                "original_road_capacity_per_hr": 800,
                "stressed_road_capacity_per_hr": effective_capacity,
                "original_waves": original_waves,
                "stressed_waves": max(stressed_waves, round(original_waves / (1.0 - reduction))),
                "hours_delay": round((max(stressed_waves, round(original_waves / (1.0 - reduction))) - original_waves) * 2, 1),
            }

        # ── Build delta summary ──────────────────────────────────────────────
        before_assigned = len(before_plan.get("assignments", []))
        after_assigned = len(after_result.get("assignments", []))
        before_unassigned = len(before_plan.get("unassigned", []))
        after_unassigned = len(after_result.get("unassigned", []))

        before_pop = before_plan.get("summary", {}).get("total_population_at_risk", 0)
        after_pop = after_result.get("summary", {}).get("total_population_at_risk", 0)

        delta = {
            "assignments_change": after_assigned - before_assigned,
            "unassigned_change": after_unassigned - before_unassigned,
            "population_unprotected_delta": after_unassigned - before_unassigned,
            "severity": (
                "CRITICAL" if (after_unassigned - before_unassigned) > 5
                else "HIGH" if (after_unassigned - before_unassigned) > 2
                else "MODERATE" if (after_unassigned - before_unassigned) > 0
                else "RESILIENT"
            ),
            "wave_impact": wave_impact,
            "isolated_habitations": after_result.get("unassigned", []),
        }

        logger.info(
            f"[StressTest] Scenario injected — severity: {delta['severity']}, "
            f"unassigned delta: {delta['unassigned_change']}"
        )

        return {
            "status": "success",
            "scenario": scenario.model_dump(),
            "before": {
                "assigned_count": before_assigned,
                "unassigned_count": before_unassigned,
                "total_population": before_pop,
                "waves": len(before_plan.get("evacuation_waves", [])),
            },
            "after": {
                "assigned_count": after_assigned,
                "unassigned_count": after_unassigned,
                "total_population": after_pop,
                "waves": len(after_result.get("evacuation_waves", [])),
                "assignments": after_result.get("assignments", [])[:20],  # top 20 for UI
                "unassigned": after_result.get("unassigned", []),
            },
            "delta": delta,
        }

    except Exception as e:
        logger.error(f"[StressTest] Injection failed: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
