"""
GIS Service — parse GeoJSON / Shapefile, store layers, manage map tags.
"""

import io
import json
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

def store_geo_layer(file_id: str, workspace_id: str, geo_data: dict) -> None:
    if not db_available() or not geo_data.get("geojson"):
        return
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO geo_layers (layer_id, file_id, workspace_id, geojson_data, feature_count)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (file_id) DO UPDATE
                SET geojson_data   = EXCLUDED.geojson_data,
                    feature_count  = EXCLUDED.feature_count
            """,
            (
                str(uuid.uuid4()),
                file_id,
                workspace_id,
                json.dumps(geo_data["geojson"]),
                geo_data["feature_count"],
            ),
        )


def get_layers(workspace_id: str) -> List[dict]:
    if not db_available():
        return []
    with get_db() as cur:
        cur.execute(
            """
            SELECT gl.layer_id, gl.file_id, gl.feature_count, gl.geojson_data,
                   f.filename
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
