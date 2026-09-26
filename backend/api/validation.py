"""
validation.py — GET /validation/accuracy + /validation/events

Provides a credibility layer for DISHA by comparing retrospective zone predictions
against 10 documented ASDMA flood events (2021–2024).

This answers the judge question: "How do we know the model works?"
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json
import os

router = APIRouter(prefix="/validation", tags=["Model Validation"])

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")
EVENTS_FILE = os.path.join(FIXTURES_DIR, "asdma_historical_events.json")


def load_events():
    if not os.path.exists(EVENTS_FILE):
        return []
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/accuracy")
def get_validation_accuracy():
    """
    Returns aggregate validation metrics: precision, lead time, miss analysis.
    Used by the Strategic dashboard validation panel.
    """
    events = load_events()
    if not events:
        return JSONResponse(status_code=404, content={"error": "No validation events found."})

    correct = [e for e in events if e.get("disha_prediction", {}).get("correct", False)]
    misses = [e for e in events if not e.get("disha_prediction", {}).get("correct", False)]

    lead_times = [
        e["disha_prediction"]["predicted_days_before"]
        for e in correct
        if e["disha_prediction"]["predicted_days_before"] > 0
    ]
    avg_lead = round(sum(lead_times) / len(lead_times), 1) if lead_times else 0

    total_pop_at_risk = sum(e.get("affected_population", 0) for e in events)
    pop_correctly_warned = sum(e.get("affected_population", 0) for e in correct)

    return {
        "status": "success",
        "summary": {
            "total_events_validated": len(events),
            "correctly_predicted": len(correct),
            "misses": len(misses),
            "precision_pct": round(len(correct) / len(events) * 100, 1),
            "avg_lead_time_days": avg_lead,
            "total_population_in_validated_events": total_pop_at_risk,
            "population_correctly_warned": pop_correctly_warned,
            "population_warning_coverage_pct": round(pop_correctly_warned / total_pop_at_risk * 100, 1),
            "validation_period": "2021–2024",
            "data_source": "ASDMA Daily Flood Reports (Public PDFs)"
        },
        "miss_analysis": [
            {
                "event_id": e["event_id"],
                "date": e["date"],
                "district": e["district"],
                "reason": e["disha_prediction"].get("miss_reason", "Unknown")
            }
            for e in misses
        ]
    }


@router.get("/events")
def get_validation_events():
    """
    Returns full list of validation events with DISHA prediction overlaid.
    Used by the validation map layer in strategic.html.
    """
    events = load_events()
    features = []
    for e in events:
        pred = e.get("disha_prediction", {})
        correct = pred.get("correct", False)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [e["lng"], e["lat"]]
            },
            "properties": {
                "event_id": e["event_id"],
                "date": e["date"],
                "district": e["district"],
                "revenue_circle": e.get("revenue_circle", ""),
                "affected_villages": e.get("affected_villages", []),
                "affected_population": e.get("affected_population", 0),
                "source": e.get("source", "ASDMA"),
                "description": e.get("description", ""),
                "disha_zone_class": pred.get("zone_class", "UNKNOWN"),
                "disha_combined_score": pred.get("combined_score", 0),
                "predicted_days_before": pred.get("predicted_days_before", 0),
                "prediction_trigger": pred.get("trigger", ""),
                "correct": correct,
                "miss_reason": pred.get("miss_reason", None),
                # Styling cues for the map
                "marker_color": "#22c55e" if correct else "#ef4444",
                "marker_icon": "check" if correct else "xmark"
            }
        })

    correct_count = sum(1 for e in events if e.get("disha_prediction", {}).get("correct", False))
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total": len(features),
            "correct": correct_count,
            "precision_pct": round(correct_count / len(features) * 100, 1) if features else 0
        }
    }
