"""
conflict_detector.py — Evidence Conflict, Verification Priority & Decision Confidence Engine
(Innovations 3, 5 & 8)

Solves three critical operational gaps:
1. Evidence Conflict Engine: Detects ground truth vs. telemetry sensor vs. satellite contradictions.
2. Verification Priority Scoring: Computes an urgent ranking for commander dispatch based on
   severity, population exposure, and data latency.
3. Data-Aware Decision Confidence: Quantifies model certainty (0–100%) based on sensor age,
   satellite revisit latency, and conflicting ground signals.
4. Resolution-Aware Decision Making: Flags when macro-scale inputs are insufficient for
   micro-level street routing.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import math
import logging

logger = logging.getLogger(__name__)

class ConflictAndConfidenceEngine:
    """
    Engine analyzing multi-source information discrepancy, scoring verification priority,
    and calculating dynamic decision confidence.
    """

    def __init__(self):
        # Initial known observation conflicts (Guwahati & Assam focus)
        self.conflicts: List[Dict[str, Any]] = [
            {
                "id": "CONF-01",
                "title": "CWC Sensor vs Ground Observation: Bharalu Outfall",
                "location_name": "Bharalu River Mouth (MG Road)",
                "coordinates": [91.7442, 26.1620],
                "basin_id": "GHY_BHARALU_CORE",
                "source_a": {
                    "source": "CWC Hydro-Telemetry (Gauge GHY-04)",
                    "value": "Water Stage: 48.10m (0.4m below Danger Level)",
                    "timestamp": "12 mins ago",
                    "latency_minutes": 12,
                    "resolution": "Point Sensor (Hourly)",
                    "reliability": 0.95
                },
                "source_b": {
                    "source": "Crowdsourced Field Ops (Team-A1 & 4 Citizen SOS)",
                    "value": "Water depth 1.2m on street, backflow actively overflowing floodwalls",
                    "timestamp": "4 mins ago",
                    "latency_minutes": 4,
                    "resolution": "Ground In-Situ",
                    "reliability": 0.88
                },
                "discrepancy_type": "GAUGE_SENSOR_UNDERESTIMATION",
                "nature_of_conflict": "Silt accumulation at sensor casing is damping ultrasonic gauge reading, concealing acute local backwater surcharge.",
                "affected_population": 4800,
                "route_critical": True,
                "status": "UNVERIFIED",
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "CONF-02",
                "title": "Satellite Land-Use vs Field Encroachment: Deepor Beel Catchment",
                "location_name": "Deepor Beel Northern Buffer (Ward 14)",
                "coordinates": [91.6420, 26.1280],
                "basin_id": "GHY_DEEPOR_BEEL",
                "source_a": {
                    "source": "Sentinel-2 ESA WorldCover 2024 Base",
                    "value": "Classified as Natural Wetland / Water Retention Basin (Runoff C = 0.15)",
                    "timestamp": "Updated 6 months ago",
                    "latency_minutes": 259200,
                    "resolution": "10m Optical Satellite",
                    "reliability": 0.70
                },
                "source_b": {
                    "source": "Field Construction & Silt Inspection Report",
                    "value": "Heavy unapproved commercial landfill & earth grading. Concrete runoff coefficient C ~ 0.85",
                    "timestamp": "18 hours ago",
                    "latency_minutes": 1080,
                    "resolution": "Field Surveyor Geotagged Photo",
                    "reliability": 0.92
                },
                "discrepancy_type": "OUTDATED_SATELLITE_BASELINE",
                "nature_of_conflict": "Model underestimates runoff discharge by 40% because satellite layer still thinks the terrain is permeable marshland.",
                "affected_population": 2900,
                "route_critical": False,
                "status": "UNVERIFIED",
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "CONF-03",
                "title": "OSRM Routing Route Clear vs Mobile Scout Submerged Warning",
                "location_name": "NH-37 Maligaon Flyover Underpass",
                "coordinates": [91.7120, 26.1680],
                "basin_id": "GHY_BHARALU_CORE",
                "source_a": {
                    "source": "OpenStreetMap / National Highway Authority Feed",
                    "value": "Road status: OPEN / NOMINAL FLOW (Speed: 45 km/h)",
                    "timestamp": "25 mins ago",
                    "latency_minutes": 25,
                    "resolution": "Macro Road Graph",
                    "reliability": 0.80
                },
                "source_b": {
                    "source": "SAR Mobile Scout App (Team B2 Live GPS)",
                    "value": "Flash inundation 0.8m deep; 2 civilian cars stalled; underpass impassable for low-clearance vehicles",
                    "timestamp": "7 mins ago",
                    "latency_minutes": 7,
                    "resolution": "Ground Scout Real-time",
                    "reliability": 0.94
                },
                "discrepancy_type": "ROUTE_CLEARANCE_CONTRADICTION",
                "nature_of_conflict": "Standard traffic routing algorithm directing evacuation convoys directly into a flooded bottleneck.",
                "affected_population": 6500,
                "route_critical": True,
                "status": "VERIFIED_ACTION_TAKEN",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        ]

    def get_verification_priority_queue(self) -> Dict[str, Any]:
        """
        Calculates mathematical Verification Priority Score for every conflict:
        Score (0-100) = (Severity * 35) + (Population Factor * 35) + (Data Freshness Gap * 15) + (Route Criticality * 15)
        Returns queue sorted descending by priority score.
        """
        scored_conflicts = []

        for c in self.conflicts:
            pop = c.get("affected_population", 1000)
            pop_score = min(1.0, pop / 5000.0)  # max out at 5000 pop

            route_score = 1.0 if c.get("route_critical", False) else 0.3

            # Freshness gap penalty: higher delta between source latencies = higher urgency to clarify
            lat_a = c["source_a"]["latency_minutes"]
            lat_b = c["source_b"]["latency_minutes"]
            gap_hours = abs(lat_a - lat_b) / 60.0
            freshness_score = min(1.0, gap_hours / 24.0)

            # Severity score by conflict type
            sev_map = {
                "ROUTE_CLEARANCE_CONTRADICTION": 1.0,
                "GAUGE_SENSOR_UNDERESTIMATION": 0.9,
                "OUTDATED_SATELLITE_BASELINE": 0.7
            }
            severity = sev_map.get(c.get("discrepancy_type"), 0.75)

            raw_score = (severity * 35) + (pop_score * 35) + (freshness_score * 15) + (route_score * 15)
            final_score = round(min(100.0, max(10.0, raw_score)), 1)

            if final_score >= 80:
                priority_tier = "CRITICAL_VERIFY_NOW"
                badge_color = "#ef4444"
            elif final_score >= 60:
                priority_tier = "HIGH_PRIORITY"
                badge_color = "#f97316"
            else:
                priority_tier = "MODERATE"
                badge_color = "#f59e0b"

            scored = {
                **c,
                "priority_score": final_score,
                "priority_tier": priority_tier,
                "badge_color": badge_color,
                "recommended_verification_protocol": self._get_protocol(c["discrepancy_type"])
            }
            scored_conflicts.append(scored)

        scored_conflicts.sort(key=lambda x: x["priority_score"], reverse=True)

        return {
            "status": "success",
            "total_conflicts": len(scored_conflicts),
            "unverified_count": sum(1 for c in scored_conflicts if c["status"] == "UNVERIFIED"),
            "queue": scored_conflicts
        }

    def _get_protocol(self, conflict_type: str) -> str:
        if conflict_type == "ROUTE_CLEARANCE_CONTRADICTION":
            return "Dispatch Motorcycle Scout unit with Geotagged Camera; halt bus convoys at checkpoint 3."
        elif conflict_type == "GAUGE_SENSOR_UNDERESTIMATION":
            return "Send SDRF riverine patrol with manual staff gauge reading; re-calibrate telemetry offset."
        elif conflict_type == "OUTDATED_SATELLITE_BASELINE":
            return "Deploy Drone LiDAR/Optical mapping run (500m radius); update runoff composite coefficient C to 0.85."
        return "Task closest field unit to perform ground visual inspection."

    def calculate_decision_confidence(self, rainfall_mm_hr: float = 0.0, river_level_m: float = 48.0) -> Dict[str, Any]:
        """
        Data-Aware Decision Confidence Calculator (Innovation 5)
        Scores model trustworthiness 0–100% based on telemetry latency,
        satellite freshness, sensor coverage, and active unresolved conflicts.
        """
        # 1. Telemetry Freshness Score (CWC Gauge, Open-Meteo, Rain Sensors)
        telemetry_age_mins = 8  # Simulated average age of gauge updates
        if telemetry_age_mins <= 15:
            telemetry_score = 98.0
        elif telemetry_age_mins <= 60:
            telemetry_score = 85.0
        else:
            telemetry_score = 50.0

        # 2. Satellite SAR Freshness Score (Sentinel-1 pass)
        # In actual operations, SAR passes happen every 6-12 days unless on-demand
        sar_age_hours = 16.5
        if sar_age_hours <= 12:
            satellite_score = 92.0
        elif sar_age_hours <= 24:
            satellite_score = 80.0
        elif sar_age_hours <= 72:
            satellite_score = 65.0
        else:
            satellite_score = 40.0

        # 3. Ground Verification Density
        verified_conflicts = sum(1 for c in self.conflicts if c["status"] == "VERIFIED_ACTION_TAKEN")
        total_conflicts = len(self.conflicts)
        ground_score = 85.0 + (15.0 * (verified_conflicts / max(1, total_conflicts)))

        # 4. Extreme Weather Uncertainty Penalty
        weather_penalty = 0.0
        if rainfall_mm_hr > 70.0:
            weather_penalty = 12.0  # extreme rain introduces non-linear runoff chaos
        elif rainfall_mm_hr > 40.0:
            weather_penalty = 6.0

        # Conflict Penalty
        unverified_critical = sum(1 for c in self.conflicts if c["status"] == "UNVERIFIED" and c.get("route_critical", False))
        conflict_penalty = unverified_critical * 7.5

        # Weighted calculation
        overall_confidence = (telemetry_score * 0.40) + (satellite_score * 0.35) + (ground_score * 0.25) - weather_penalty - conflict_penalty
        overall_confidence = round(min(99.0, max(25.0, overall_confidence)), 1)

        if overall_confidence >= 80.0:
            tier = "HIGH_CONFIDENCE"
            banner = "Operational recommendations fully backed by live telemetry and verified field ground truth."
            color = "#22c55e"
        elif overall_confidence >= 60.0:
            tier = "MODERATE_CONFIDENCE"
            banner = "Relying on projected hydraulic models with partial sensor latency. Field scout confirmation recommended."
            color = "#f59e0b"
        else:
            tier = "LOW_CONFIDENCE_CAUTION"
            banner = "High telemetry latency or severe unverified ground conflicts. Commander manual ground scout required before heavy bus dispatch."
            color = "#ef4444"

        # Innovation 8: Resolution-Aware Decision Making Notice
        resolution_safeguards = [
            {
                "decision_domain": "Evacuation Bus Routing",
                "recommended_resolution": "Micro Street-Level (OSM Sub-segment + Scout verification)",
                "active_model_resolution": "Overpass OSMnx + 12m SRTM DEM",
                "resolution_fit": "OPTIMAL",
                "guidance": "Sufficiently fine-grained to detect road underpass chokes."
            },
            {
                "decision_domain": "Catchment Basin Runoff (UFRI)",
                "recommended_resolution": "Meso-Basin Level (100–500 Hectares)",
                "active_model_resolution": "Rational Method + Manning Channel Geometry",
                "resolution_fit": "OPTIMAL",
                "guidance": "Hydrological parameters calibrated specifically for Brahmaputra alluvial plain."
            },
            {
                "decision_domain": "Global River Discharge Inflow",
                "recommended_resolution": "Macro-Regional (0.1° GloFAS Grid)",
                "active_model_resolution": "Open-Meteo GloFAS v4 River Discharge (m³/s)",
                "resolution_fit": "CAUTION_MACRO_ONLY",
                "guidance": "GloFAS provides regional flood crest timing (~10km), but CANNOT resolve neighborhood street flooding. Do not use for street rescue dispatch without local DEM overlay."
            }
        ]

        return {
            "status": "success",
            "overall_confidence_pct": overall_confidence,
            "confidence_tier": tier,
            "color": color,
            "summary_banner": banner,
            "factors": {
                "telemetry_freshness": {
                    "score": telemetry_score,
                    "sensor_age_mins": telemetry_age_mins,
                    "status": "FRESH" if telemetry_age_mins <= 15 else "STALE"
                },
                "satellite_sar_freshness": {
                    "score": satellite_score,
                    "sar_pass_age_hours": sar_age_hours,
                    "status": "VALID_OBSERVATION"
                },
                "ground_truth_coverage": {
                    "score": ground_score,
                    "unverified_conflicts": total_conflicts - verified_conflicts
                },
                "conflict_deduction": conflict_penalty
            },
            "resolution_safeguards": resolution_safeguards
        }

    def resolve_conflict(self, conflict_id: str, resolution_notes: str, winner: str) -> Dict[str, Any]:
        """Commander marks a conflict resolved after field verification."""
        for c in self.conflicts:
            if c["id"] == conflict_id:
                c["status"] = "VERIFIED_ACTION_TAKEN"
                c["resolution_notes"] = resolution_notes
                c["resolved_winner"] = winner
                c["resolved_at"] = datetime.now(timezone.utc).isoformat()
                return {"status": "success", "resolved_conflict": c}
        return {"status": "error", "message": f"Conflict {conflict_id} not found"}


# Singleton instance
conflict_engine = ConflictAndConfidenceEngine()
