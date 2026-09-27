"""
dependency_graph.py — Impact & Dependency Intelligence Engine (Innovation 2 & 6)

Models cross-system operational dependencies during disaster operations:
- Power Grid (Substations, Transformers)
- Drainage & Dewatering (Pumps, Sluice Gates)
- Telecommunications (Cell Towers, Repeaters)
- Transport Infrastructure (Bridges, Primary Arteries)
- Emergency Facilities (Shelters, Hospitals)
- Response Teams (NDRF/SDRF, GMC, APDCL, Health)

Enables "Simulate Failure" to trace cascading impacts across connected agencies
before or during deployment.
"""

from typing import Dict, List, Any, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)

# Master Operational Asset Graph for Guwahati / Kamrup Metropolitan
DEPENDENCY_NODES: List[Dict[str, Any]] = [
    # ── Power Infrastructure (APDCL) ──────────────────────────────────────────
    {
        "id": "PWR-DISPUR-SUB",
        "name": "Dispur 33/11kV Substation",
        "type": "POWER_SUBSTATION",
        "agency": "APDCL (Power Dept)",
        "coordinates": [91.7890, 26.1420],
        "status": "OPERATIONAL",
        "capacity": "25 MVA",
        "serves": "Dispur, Anil Nagar, Bharalu Basin Pumping"
    },
    {
        "id": "PWR-PANDU-SUB",
        "name": "Pandu Ghat Power Feeder",
        "type": "POWER_SUBSTATION",
        "agency": "APDCL (Power Dept)",
        "coordinates": [91.7050, 26.1750],
        "status": "OPERATIONAL",
        "capacity": "15 MVA",
        "serves": "Maligaon, Western Drains, Telecom Hub"
    },

    # ── Dewatering & Silt Clearance (GMC / PWD) ──────────────────────────────
    {
        "id": "PMP-ANIL-NAGAR",
        "name": "Anil Nagar Heavy Dewatering Station",
        "type": "DEWATERING_PUMP",
        "agency": "GMC (Guwahati Municipal)",
        "coordinates": [91.7290, 26.1510],
        "status": "OPERATIONAL",
        "capacity": "1200 LPS",
        "serves": "Anil Nagar Low Depression (47.2m DEM)"
    },
    {
        "id": "PMP-BHARALU-SLUICE",
        "name": "Bharalu River Mouth Sluice & Pump Gate",
        "type": "SLUICE_PUMP_GATE",
        "agency": "Water Resources Dept (WRD)",
        "coordinates": [91.7442, 26.1620],
        "status": "OPERATIONAL",
        "capacity": "3000 LPS",
        "serves": "Guwahati Central Core Basin Discharge"
    },
    {
        "id": "PMP-MALIGAON-SILT",
        "name": "Maligaon Sediment Dredging Station",
        "type": "SILT_CLEARANCE_STATION",
        "agency": "PWD (Roads & Drainage)",
        "coordinates": [91.7180, 26.1730],
        "status": "OPERATIONAL",
        "capacity": "45 Tonnes/hr",
        "serves": "North-South Main Hill Cutting Drain"
    },

    # ── Communications Infrastructure (DOT / Telcos) ─────────────────────────
    {
        "id": "COM-TOWER-GHY-01",
        "name": "Kamakhya Hill Primary Telecom Relay",
        "type": "COMMUNICATION_TOWER",
        "agency": "Telco Grid / State Emergency Comms",
        "coordinates": [91.7080, 26.1660],
        "status": "OPERATIONAL",
        "capacity": "12000 Concurrency",
        "serves": "Field Teams VHF & Mobile Data Sector West"
    },
    {
        "id": "COM-TOWER-GHY-02",
        "name": "Dispur Secretariat Cellular Mast",
        "type": "COMMUNICATION_TOWER",
        "agency": "Telco Grid / State Emergency Comms",
        "coordinates": [91.7920, 26.1450],
        "status": "OPERATIONAL",
        "capacity": "25000 Concurrency",
        "serves": "Field Ops Team A, B, Command Center telemetry"
    },

    # ── Transport Corridors & Bridges (PWD / Traffic Police) ──────────────────
    {
        "id": "BRG-NH37-BHARALU",
        "name": "NH-37 Bharalu River Bridge",
        "type": "CRITICAL_BRIDGE",
        "agency": "PWD / Assam Police Traffic",
        "coordinates": [91.7500, 26.1580],
        "status": "OPERATIONAL",
        "capacity": "4 Lane Primary Artery",
        "serves": "Main East-West Evacuation Route"
    },
    {
        "id": "COR-GS-ROAD-SOUTH",
        "name": "GS Road Southern Evac Corridor",
        "type": "EVACUATION_CORRIDOR",
        "agency": "Assam Police Traffic Wing",
        "coordinates": [91.7750, 26.1350],
        "status": "OPERATIONAL",
        "capacity": "Green Corridor Ambulance & Bus Lane",
        "serves": "Direct transit from flooded wards to High Ground"
    },

    # ── Shelters & Relief Facilities (District Administration) ───────────────
    {
        "id": "SHT-SARUSAJAI-STADIUM",
        "name": "Sarusajai National Stadium Relief Hub",
        "type": "PRIMARY_SHELTER",
        "agency": "District Administration / Revenue",
        "coordinates": [91.7650, 26.1150],
        "status": "OPERATIONAL",
        "capacity": "5,000 Persons",
        "serves": "Mass relocation intake, central rations stockpile"
    },
    {
        "id": "SHT-COTTON-COLLEGE",
        "name": "Cotton University High-Ground Camp",
        "type": "SECONDARY_SHELTER",
        "agency": "District Administration / Education",
        "coordinates": [91.7480, 26.1900],
        "status": "OPERATIONAL",
        "capacity": "1,500 Persons",
        "serves": "North Guwahati vulnerable residents"
    },

    # ── Medical Trauma Care (Health & Family Welfare) ─────────────────────────
    {
        "id": "MED-GMCH-CENTRAL",
        "name": "Guwahati Medical College & Hospital (GMCH)",
        "type": "EMERGENCY_HOSPITAL",
        "agency": "Health Department / Medical Emergency",
        "coordinates": [91.7720, 26.1550],
        "status": "OPERATIONAL",
        "capacity": "350 Critical Flood Beds",
        "serves": "Trauma, leptospirosis, drowning resuscitation"
    },

    # ── Rescue Staging & Response Units (NDRF / SDRF / Fire) ──────────────────
    {
        "id": "RSC-NDRF-AZARA-BASE",
        "name": "1st Bn NDRF Staging Base, Azara",
        "type": "RESCUE_BASE",
        "agency": "NDRF (National Disaster Response Force)",
        "coordinates": [91.6171, 26.1235],
        "status": "OPERATIONAL",
        "capacity": "8 Deep-Water Inflatable Boat Teams",
        "serves": "Urban Waterborne Search & Extraction"
    },
    {
        "id": "RSC-SDRF-PANDU-BOAT",
        "name": "SDRF Water Wing Riverine Staging",
        "type": "RESCUE_STAGING",
        "agency": "SDRF / Fire & Emergency Services",
        "coordinates": [91.7010, 26.1790],
        "status": "OPERATIONAL",
        "capacity": "4 Rescue Patrol Craft",
        "serves": "Deepor Beel & River Outfall Rescues"
    }
]

# Directed dependencies: source -> target
# If source FAILS, target is COMPROMISED / DEGRADED
DEPENDENCY_EDGES: List[Dict[str, Any]] = [
    # Power Grid -> Dewatering Pumps & Sluice Gates
    {
        "source": "PWR-DISPUR-SUB",
        "target": "PMP-ANIL-NAGAR",
        "dependency_type": "POWER",
        "criticality": "HIGH",
        "impact_summary": "Loss of grid power disables automatic high-volume dewatering. Anil Nagar depression water level rises +0.5m/hr."
    },
    {
        "source": "PWR-DISPUR-SUB",
        "target": "PMP-BHARALU-SLUICE",
        "dependency_type": "POWER",
        "criticality": "CRITICAL",
        "impact_summary": "Loss of power trips main sluice gate bypass pumps. City stormwater backs up directly into Bharalu commercial strip."
    },
    {
        "source": "PWR-PANDU-SUB",
        "target": "PMP-MALIGAON-SILT",
        "dependency_type": "POWER",
        "criticality": "HIGH",
        "impact_summary": "Sediment dredging station shuts down. Active earth cutting slopes choke western drainage corridor within 90 minutes."
    },
    {
        "source": "PWR-DISPUR-SUB",
        "target": "COM-TOWER-GHY-02",
        "dependency_type": "POWER",
        "criticality": "MEDIUM",
        "impact_summary": "Cellular mast falls back to diesel generator (4-hour runtime). Field Ops Team B telemetry becomes precarious."
    },

    # Telecommunications -> Field Rescue Teams
    {
        "source": "COM-TOWER-GHY-01",
        "target": "RSC-SDRF-PANDU-BOAT",
        "dependency_type": "TELEMETRY",
        "criticality": "HIGH",
        "impact_summary": "Loss of cellular & VHF relay prevents dynamic coordinate dispatches. Patrol crafts operate on blind dead-reckoning."
    },
    {
        "source": "COM-TOWER-GHY-02",
        "target": "RSC-NDRF-AZARA-BASE",
        "dependency_type": "TELEMETRY",
        "criticality": "CRITICAL",
        "impact_summary": "Command Center cannot transmit live Hungarian allocation orders to Azara deployment convoys."
    },

    # Dewatering Pumps -> Road Corridors & Bridges
    {
        "source": "PMP-BHARALU-SLUICE",
        "target": "BRG-NH37-BHARALU",
        "dependency_type": "INUNDATION_CONTROL",
        "criticality": "CRITICAL",
        "impact_summary": "Uncontrolled Bharalu overflow floods NH-37 bridge underpasses with >1.2m water, severing the 4-lane arterial."
    },
    {
        "source": "PMP-ANIL-NAGAR",
        "target": "COR-GS-ROAD-SOUTH",
        "dependency_type": "INUNDATION_CONTROL",
        "criticality": "HIGH",
        "impact_summary": "Severe backwater from Anil Nagar ponds into GS Road connection, blocking southern evacuation wave vehicles."
    },

    # Critical Bridges & Corridors -> Shelters & Hospitals
    {
        "source": "BRG-NH37-BHARALU",
        "target": "SHT-SARUSAJAI-STADIUM",
        "dependency_type": "ACCESS_CORRIDOR",
        "criticality": "CRITICAL",
        "impact_summary": "Primary 5,000-person relief camp becomes inaccessible to western habitations. Forces split relocation to tertiary shelters."
    },
    {
        "source": "COR-GS-ROAD-SOUTH",
        "target": "MED-GMCH-CENTRAL",
        "dependency_type": "AMBULANCE_TRANSIT",
        "criticality": "CRITICAL",
        "impact_summary": "Ambulances carrying critical flood victims face 45-minute detours through congested hillside alleys."
    },

    # Drainage Silt Station -> Pumping Efficiency
    {
        "source": "PMP-MALIGAON-SILT",
        "target": "PMP-BHARALU-SLUICE",
        "dependency_type": "DEBRIS_CASCADE",
        "criticality": "HIGH",
        "impact_summary": "Silt build-up travels downstream, clogging impeller screens at Bharalu Sluice and cutting pumping efficiency by 60%."
    }
]


class DependencyIntelligenceEngine:
    """
    Graph engine for cross-agency operational dependencies.
    Provides forward cascade analysis, root cause tracing, and mitigation recommendations.
    """

    def __init__(self):
        self.nodes = {n["id"]: n for n in DEPENDENCY_NODES}
        self.adj: Dict[str, List[Dict[str, Any]]] = {n["id"]: [] for n in DEPENDENCY_NODES}
        self.reverse_adj: Dict[str, List[Dict[str, Any]]] = {n["id"]: [] for n in DEPENDENCY_NODES}

        for edge in DEPENDENCY_EDGES:
            src = edge["source"]
            tgt = edge["target"]
            if src in self.adj:
                self.adj[src].append(edge)
            if tgt in self.reverse_adj:
                self.reverse_adj[tgt].append(edge)

    def get_full_graph(self) -> Dict[str, Any]:
        """Returns the full dependency graph with live statuses for visualization."""
        return {
            "status": "success",
            "nodes": list(self.nodes.values()),
            "edges": DEPENDENCY_EDGES,
            "agencies_involved": list(set(n["agency"] for n in self.nodes.values())),
            "total_nodes": len(self.nodes),
            "total_dependencies": len(DEPENDENCY_EDGES)
        }

    def simulate_failure(self, trigger_node_id: str) -> Dict[str, Any]:
        """
        Calculates cascading failure propagation when an asset is knocked out.
        Returns multi-tier cascade, affected agencies, and prescribed corrective actions.
        """
        if trigger_node_id not in self.nodes:
            return {"status": "error", "message": f"Asset {trigger_node_id} not found in dependency graph"}

        trigger_node = self.nodes[trigger_node_id]

        visited = set()
        queue = deque([(trigger_node_id, 0, None)])  # (node_id, depth, edge)
        cascading_impacts: List[Dict[str, Any]] = []
        affected_agencies = set()
        affected_agencies.add(trigger_node["agency"])

        severity_level = "CRITICAL" if trigger_node["type"] in ["POWER_SUBSTATION", "CRITICAL_BRIDGE"] else "HIGH"

        while queue:
            curr_id, depth, edge_used = queue.popleft()
            if curr_id in visited:
                continue
            visited.add(curr_id)

            curr_node = self.nodes[curr_id]
            affected_agencies.add(curr_node["agency"])

            if depth > 0:
                cascading_impacts.append({
                    "node_id": curr_id,
                    "name": curr_node["name"],
                    "type": curr_node["type"],
                    "agency": curr_node["agency"],
                    "cascade_depth": depth,
                    "caused_by": edge_used["source"],
                    "dependency_type": edge_used["dependency_type"],
                    "criticality": edge_used.get("criticality", "HIGH"),
                    "impact_summary": edge_used["impact_summary"]
                })

            for edge in self.adj.get(curr_id, []):
                nxt_id = edge["target"]
                if nxt_id not in visited:
                    queue.append((nxt_id, depth + 1, edge))

        # Generate Prescribed Cross-Agency Corrective Actions
        corrective_actions = self._generate_corrective_actions(trigger_node, cascading_impacts)

        return {
            "status": "success",
            "trigger_asset": trigger_node,
            "cascade_count": len(cascading_impacts),
            "severity": severity_level,
            "affected_agencies": list(affected_agencies),
            "cascading_impacts": cascading_impacts,
            "cross_agency_corrective_actions": corrective_actions
        }

    def _generate_corrective_actions(self, trigger_node: Dict[str, Any], cascades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Synthesizes actionable, multi-agency SOP tasks to contain the cascade."""
        actions = []
        t_id = trigger_node["id"]

        if "PWR-" in t_id:
            actions.append({
                "agency": "APDCL (Power Dept)",
                "action": f"Deploy 500kVA Mobile Diesel Generator to backup affected pump stations.",
                "priority": "IMMEDIATE (0–15 mins)",
                "target_location": "Anil Nagar & Bharalu Pumping Stations"
            })
            actions.append({
                "agency": "GMC (Guwahati Municipal)",
                "action": "Switch dewatering pump stations to secondary diesel auxiliary engine mode.",
                "priority": "IMMEDIATE (0–20 mins)",
                "target_location": "PMP-ANIL-NAGAR & PMP-BHARALU-SLUICE"
            })
            actions.append({
                "agency": "Water Resources Dept (WRD)",
                "action": "Manually lock Bharalu sluice gates to prevent backwater ingress during pump outage.",
                "priority": "HIGH (T+30 mins)",
                "target_location": "Bharalu River Mouth"
            })

        elif "BRG-" in t_id or "COR-" in t_id:
            actions.append({
                "agency": "Assam Police Traffic Wing",
                "action": "Close access ramps 1km prior to blockage and establish Green Corridor via secondary ring road.",
                "priority": "IMMEDIATE (0–10 mins)",
                "target_location": "NH-37 Diversion Points"
            })
            actions.append({
                "agency": "District Administration / DISHA",
                "action": "Trigger Hungarian Re-Optimizer: Divert remaining wave evacuees from Sarusajai to Cotton University shelter.",
                "priority": "IMMEDIATE (Automated Plan B)",
                "target_location": "SHT-COTTON-COLLEGE"
            })
            actions.append({
                "agency": "Health Department / 108 Emergency",
                "action": "Reroute incoming trauma ambulances to Secondary Medical Facility at Maligaon.",
                "priority": "HIGH (T+15 mins)",
                "target_location": "GMCH Alternative Ambulance Corridors"
            })

        else:
            actions.append({
                "agency": trigger_node["agency"],
                "action": f"Dispatch technical emergency maintenance crew to inspect and stabilize {trigger_node['name']}.",
                "priority": "HIGH",
                "target_location": trigger_node["name"]
            })

        # Add NDRF contingency if rescue was in the cascade
        has_rescue_affected = any("RSC-" in c["node_id"] for c in cascades)
        if has_rescue_affected:
            actions.append({
                "agency": "NDRF / SDRF",
                "action": "Switch tactical field comms to High-Frequency VHF Channel 4 (bypass compromised cellular mast).",
                "priority": "IMMEDIATE",
                "target_location": "Azara Command Vehicle"
            })

        return actions


# Singleton instance
dependency_engine = DependencyIntelligenceEngine()
