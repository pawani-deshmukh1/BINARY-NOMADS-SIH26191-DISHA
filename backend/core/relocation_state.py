"""
relocation_state.py — Live hazard polygon registry for the re-optimizer.

When field teams report blocked roads or compromised conditions,
this module stores the resulting hazard polygons so they persist
across re-optimization calls within a server session.

Thread-safe via threading.Lock (consistent with analysis_state.py pattern).
"""
import threading
from typing import Optional

from shapely.geometry import Polygon

_lock = threading.Lock()

# {report_id: Polygon} — keyed by report ID so individual hazards can be cleared
_hazard_polygons: dict[str, object] = {}


def add_hazard_polygon(report_id: str, polygon) -> None:
    """Add a new hazard polygon from a field report."""
    with _lock:
        _hazard_polygons[report_id] = polygon


def clear_hazard_polygon(report_id: str) -> None:
    """Remove a hazard polygon (e.g. when field team reports road cleared)."""
    with _lock:
        _hazard_polygons.pop(report_id, None)


def get_hazard_polygons() -> list:
    """Return all active hazard polygons as a list."""
    with _lock:
        return list(_hazard_polygons.values())


def get_hazard_polygon_count() -> int:
    with _lock:
        return len(_hazard_polygons)


def clear_all_hazard_polygons() -> None:
    """Reset — called at start of a new /analyze run."""
    with _lock:
        _hazard_polygons.clear()
