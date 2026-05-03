"""
Readiness Report Service — gap analysis between SOPs and connected sensors.
"""

from typing import Dict, List
from db import get_db, db_available

# Which sensor types are covered by which SOP keywords
SENSOR_SOP_KEYWORDS: Dict[str, List[str]] = {
    "SMOKE":       ["fire", "smoke", "flame", "evacuation", "sprinkler", "extinguisher"],
    "FLOOD":       ["flood", "water", "drainage", "surge", "inundation"],
    "EARTHQUAKE":  ["earthquake", "seismic", "structural", "tremor", "richter"],
    "CCTV":        ["security", "surveillance", "cctv", "intrusion", "perimeter"],
    "TEMPERATURE": ["hvac", "temperature", "heat", "cold", "thermal"],
    "GAS":         ["gas", "chemical", "hazmat", "toxic", "leak"],
    "MEDICAL":     ["medical", "first aid", "cpr", "ambulance", "triage"],
    "API":         ["api", "integration", "webhook", "alert", "notification"],
}


def generate_report(workspace_id: str) -> dict:
    if not db_available():
        return _unavailable(workspace_id)

    with get_db() as cur:
        cur.execute(
            "SELECT file_id, filename, file_type, processing_status FROM files WHERE workspace_id = %s",
            (workspace_id,),
        )
        files = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT * FROM sensors WHERE workspace_id = %s",
            (workspace_id,),
        )
        sensors = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT content FROM document_chunks WHERE workspace_id = %s",
            (workspace_id,),
        )
        all_text = " ".join(r["content"].lower() for r in cur.fetchall())

    sensor_types = {s["sensor_type"] for s in sensors}
    file_types = {f["file_type"] for f in files}

    covered: List[str] = []
    gaps: List[str] = []
    warnings: List[str] = []

    # For each sensor category, check if we have a matching SOP document
    for stype, keywords in SENSOR_SOP_KEYWORDS.items():
        has_sensor = stype in sensor_types
        has_sop = any(kw in all_text for kw in keywords) if all_text else False

        if has_sensor and has_sop:
            covered.append(f"{stype} sensor ↔ matching SOP document")
        elif has_sensor and not has_sop:
            gaps.append(
                f"{stype} sensor connected but no matching SOP — "
                f"upload a protocol covering: {', '.join(keywords[:3])}"
            )
        elif not has_sensor and has_sop:
            warnings.append(
                f"SOP references {stype.lower()} scenarios but no {stype} sensor is connected"
            )

    # GIS coverage
    has_gis = any(f["file_type"] in ("geojson", "shapefile") for f in files)
    if has_gis:
        covered.append("GIS map data available")
    else:
        warnings.append("No GIS/map files — add floor plans or evacuation route maps")

    # NLP indexing status
    done_docs = [
        f for f in files
        if f["processing_status"] == "done" and f["file_type"] in ("pdf", "docx")
    ]
    pending_docs = [
        f for f in files
        if f["processing_status"] not in ("done", "error") and f["file_type"] in ("pdf", "docx")
    ]
    if done_docs:
        covered.append(f"{len(done_docs)} document(s) indexed and semantically searchable")
    if pending_docs:
        warnings.append(f"{len(pending_docs)} document(s) still being indexed (processing)")

    if not files:
        gaps.append("No documents uploaded — start by uploading SOPs and protocols")
    if not sensors:
        warnings.append("No sensors connected — add sensors to map them to SOPs")

    total = len(covered) + len(gaps) + len(warnings)
    score = round(len(covered) / total * 100) if total > 0 else 0

    return {
        "workspace_id": workspace_id,
        "score": score,
        "covered": covered,
        "gaps": gaps,
        "warnings": warnings,
        "total_files": len(files),
        "total_sensors": len(sensors),
        "file_types": sorted(file_types),
        "sensor_types": sorted(sensor_types),
    }


def _unavailable(workspace_id: str) -> dict:
    return {
        "workspace_id": workspace_id,
        "score": 0,
        "covered": [],
        "gaps": ["Database not connected — start PostgreSQL and set DATABASE_URL"],
        "warnings": [],
        "total_files": 0,
        "total_sensors": 0,
        "file_types": [],
        "sensor_types": [],
    }
