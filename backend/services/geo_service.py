"""
GIS Service — parse GeoJSON / Shapefile, store layers, manage map tags,
and typed emergency geo features with Haversine proximity routing.
"""

import io
import json
import math
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from db import get_db, db_available


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_geojson(file_bytes: bytes) -> Dict[str, Any]:
    data = json.loads(file_bytes.decode("utf-8"))

    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
    elif data.get("type") == "Feature":
        features = [data]
        data = {"type": "FeatureCollection", "features": features}
    else:
        features = [{"type": "Feature", "geometry": data, "properties": {}}]
        data = {"type": "FeatureCollection", "features": features}

    return {
        "geojson": data,
        "feature_count": len(features),
        "bounds": _bounds(features),
        "crs": "EPSG:4326",
    }


def parse_shapefile(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    try:
        import shapefile  # pyshp
    except ImportError:
        return {"error": "pyshp not installed", "geojson": None, "feature_count": 0}

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, filename)
        with open(path, "wb") as fh:
            fh.write(file_bytes)
        try:
            sf = shapefile.Reader(path)
        except Exception as e:
            return {"error": str(e), "geojson": None, "feature_count": 0}

        fields = [f[0] for f in sf.fields[1:]]
        features = [
            {
                "type": "Feature",
                "geometry": sr.shape.__geo_interface__,
                "properties": dict(zip(fields, sr.record)),
            }
            for sr in sf.shapeRecords()
        ]

    geojson = {"type": "FeatureCollection", "features": features}
    return {
        "geojson": geojson,
        "feature_count": len(features),
        "bounds": _bounds(features),
        "crs": "EPSG:4326",
    }


def _bounds(features: list) -> Optional[List[float]]:
    coords = []
    for f in features:
        geom = f.get("geometry") or {}
        coords.extend(_extract_coords(geom))
    if not coords:
        return None
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [min(lons), min(lats), max(lons), max(lats)]


def _extract_coords(geom: dict) -> list:
    gtype = geom.get("type", "")
    raw = geom.get("coordinates", [])
    if gtype == "Point":
        return [raw[:2]] if raw else []
    if gtype in ("LineString", "MultiPoint"):
        return [c[:2] for c in raw]
    if gtype in ("Polygon", "MultiLineString"):
        return [c[:2] for ring in raw for c in ring]
    if gtype == "MultiPolygon":
        return [c[:2] for poly in raw for ring in poly for c in ring]
    if gtype == "GeometryCollection":
        result = []
        for g in geom.get("geometries", []):
            result.extend(_extract_coords(g))
        return result
    return []


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def store_geo_layer(
    file_id: str,
    workspace_id: str,
    geo_data: dict,
    geo_category: Optional[str] = None,
) -> None:
    if not db_available() or not geo_data.get("geojson"):
        return
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO geo_layers (layer_id, file_id, workspace_id, geojson_data, feature_count, geo_category)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (file_id) DO UPDATE
                SET geojson_data   = EXCLUDED.geojson_data,
                    feature_count  = EXCLUDED.feature_count,
                    geo_category   = EXCLUDED.geo_category
            """,
            (
                str(uuid.uuid4()),
                file_id,
                workspace_id,
                json.dumps(geo_data["geojson"]),
                geo_data["feature_count"],
                geo_category,
            ),
        )


def get_layers(workspace_id: str) -> List[dict]:
    if not db_available():
        return []
    with get_db() as cur:
        cur.execute(
            """
            SELECT gl.layer_id, gl.file_id, gl.feature_count, gl.geojson_data,
                   gl.geo_category, f.filename
            FROM geo_layers gl
            JOIN files f ON f.file_id = gl.file_id
            WHERE gl.workspace_id = %s
            """,
            (workspace_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]

    result = []
    for r in rows:
        gj = r["geojson_data"]
        if isinstance(gj, str):
            gj = json.loads(gj)
        result.append(
            {
                "layer_id": r["layer_id"],
                "file_id": r["file_id"],
                "filename": r["filename"],
                "feature_count": r["feature_count"],
                "geojson": gj,
                "geo_category": r.get("geo_category"),
            }
        )
    return result


def get_tags(workspace_id: str) -> List[dict]:
    if not db_available():
        return []
    with get_db() as cur:
        cur.execute(
            "SELECT * FROM map_tags WHERE workspace_id = %s ORDER BY created_at DESC",
            (workspace_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def add_tag(
    workspace_id: str,
    label: str,
    lat: float,
    lng: float,
    tag_type: str = "point",
    color: str = "#ef4444",
    file_id: Optional[str] = None,
) -> dict:
    tag_id = str(uuid.uuid4())
    tag = dict(
        tag_id=tag_id,
        workspace_id=workspace_id,
        file_id=file_id,
        label=label,
        lat=lat,
        lng=lng,
        tag_type=tag_type,
        color=color,
    )
    if db_available():
        with get_db() as cur:
            cur.execute(
                """
                INSERT INTO map_tags
                    (tag_id, workspace_id, file_id, label, lat, lng, tag_type, color)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (tag_id, workspace_id, file_id, label, lat, lng, tag_type, color),
            )
    return tag


def delete_tag(tag_id: str) -> None:
    if not db_available():
        return
    with get_db() as cur:
        cur.execute("DELETE FROM map_tags WHERE tag_id = %s", (tag_id,))


# ---------------------------------------------------------------------------
# Emergency geo features — typed POIs for proximity routing
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two WGS-84 coordinates (Haversine formula)."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def add_geo_feature(
    workspace_id: str,
    feature_type: str,
    label: str,
    lat: float,
    lng: float,
    floor: Optional[str] = None,
    metadata: Optional[dict] = None,
    file_id: Optional[str] = None,
) -> dict:
    feature_id = str(uuid.uuid4())
    meta_json = json.dumps(metadata or {})
    feat = dict(
        feature_id=feature_id,
        workspace_id=workspace_id,
        feature_type=feature_type,
        label=label,
        lat=lat,
        lng=lng,
        floor=floor,
        metadata=metadata or {},
        file_id=file_id,
    )
    if db_available():
        with get_db() as cur:
            cur.execute(
                """
                INSERT INTO geo_features
                    (feature_id, workspace_id, feature_type, label, lat, lng, floor, metadata, file_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (feature_id, workspace_id, feature_type, label, lat, lng, floor, meta_json, file_id),
            )
    return feat


def delete_geo_entities_for_file(file_id: str) -> None:
    """Delete all geo_features and geo_layers rows linked to the given file."""
    if not db_available():
        return
    with get_db() as cur:
        cur.execute("DELETE FROM geo_features WHERE file_id = %s", (file_id,))
        cur.execute("DELETE FROM geo_layers WHERE file_id = %s", (file_id,))


def list_geo_features(
    workspace_id: str, feature_type: Optional[str] = None
) -> List[dict]:
    if not db_available():
        return []
    with get_db() as cur:
        if feature_type:
            cur.execute(
                "SELECT * FROM geo_features WHERE workspace_id = %s AND feature_type = %s "
                "ORDER BY created_at DESC",
                (workspace_id, feature_type),
            )
        else:
            cur.execute(
                "SELECT * FROM geo_features WHERE workspace_id = %s ORDER BY created_at DESC",
                (workspace_id,),
            )
        rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        if isinstance(r.get("metadata"), str):
            try:
                r["metadata"] = json.loads(r["metadata"])
            except Exception:
                r["metadata"] = {}
    return rows


def delete_geo_feature(feature_id: str) -> None:
    if not db_available():
        return
    with get_db() as cur:
        cur.execute("DELETE FROM geo_features WHERE feature_id = %s", (feature_id,))


_NON_ROUTING_TYPES = {"camera", "building"}


def find_nearest_feature(
    workspace_id: str,
    feature_type: str,
    lat: float,
    lng: float,
) -> Optional[dict]:
    """
    Return the nearest geo_feature of `feature_type` in `workspace_id`.

    Fallback order:
      1. Exact feature_type match (expected: 'shelter')
      2. Any routing-relevant feature (excludes camera/building)
    Returns None if the workspace has no usable emergency features.
    """
    if feature_type == "none" or not db_available():
        return None

    # 1. Exact match
    rows = list_geo_features(workspace_id, feature_type)

    # 2. Last resort: any routing feature (skip cameras / buildings)
    if not rows:
        all_rows = list_geo_features(workspace_id)
        rows = [r for r in all_rows if r.get("feature_type") not in _NON_ROUTING_TYPES]

    if not rows:
        return None

    best = min(rows, key=lambda r: _haversine_m(lat, lng, r["lat"], r["lng"]))
    best["distance_m"] = round(_haversine_m(lat, lng, best["lat"], best["lng"]), 1)
    return best
