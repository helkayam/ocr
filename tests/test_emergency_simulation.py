"""
Emergency simulation test suite.

Tests cover:
  1. Haversine distance calculation (pure function)
  2. find_nearest_feature — picks closest, falls back across types, returns None for empty
  3. extract_intent — parses structured output; falls back gracefully on LLM failure
  4. simulate() orchestration — mocks pipeline + intent + geo, asserts full output shape
"""
from __future__ import annotations

import json
import math
import sys
import os
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
# Run from project root: pytest tests/test_emergency_simulation.py
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "backend")
for _p in [_PROJECT_ROOT, _BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Haversine distance
# ─────────────────────────────────────────────────────────────────────────────

def _import_haversine():
    from services.geo_service import _haversine_m
    return _haversine_m


class TestHaversineDistance:
    def test_same_point_is_zero(self):
        h = _import_haversine()
        assert h(32.0, 34.0, 32.0, 34.0) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_tel_aviv_to_jerusalem(self):
        """Tel Aviv ↔ Jerusalem is roughly 55–60 km."""
        h = _import_haversine()
        dist = h(32.0853, 34.7818, 31.7683, 35.2137)  # approx coords
        assert 50_000 < dist < 70_000, f"Expected ~55–60 km, got {dist:.0f} m"

    def test_symmetry(self):
        h = _import_haversine()
        d1 = h(32.0, 34.0, 33.0, 35.0)
        d2 = h(33.0, 35.0, 32.0, 34.0)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_small_offset_roughly_correct(self):
        """1 degree of latitude ≈ 111 km."""
        h = _import_haversine()
        dist = h(32.0, 35.0, 33.0, 35.0)
        assert 100_000 < dist < 120_000


# ─────────────────────────────────────────────────────────────────────────────
# 2.  find_nearest_feature
# ─────────────────────────────────────────────────────────────────────────────

def _fake_feature(fid: str, ftype: str, label: str, lat: float, lng: float) -> dict:
    return {
        "feature_id": fid,
        "workspace_id": "ws-1",
        "feature_type": ftype,
        "label": label,
        "lat": lat,
        "lng": lng,
        "floor": None,
        "metadata": {},
    }


class TestFindNearestFeature:
    def test_returns_closest_shelter(self):
        from services.geo_service import find_nearest_feature

        features = [
            _fake_feature("f1", "shelter", "Far Shelter",    33.0, 35.0),
            _fake_feature("f2", "shelter", "Near Shelter",   32.01, 34.01),
            _fake_feature("f3", "shelter", "Medium Shelter", 32.1, 34.1),
        ]

        with patch("services.geo_service.list_geo_features", return_value=features):
            with patch("services.geo_service.db_available", return_value=True):
                result = find_nearest_feature("ws-1", "shelter", 32.0, 34.0)

        assert result is not None
        assert result["feature_id"] == "f2"
        assert result["label"] == "Near Shelter"
        assert "distance_m" in result
        assert result["distance_m"] > 0

    def test_fallback_to_any_feature_when_shelter_not_found(self):
        """When no shelters exist, fall back to any non-camera/building feature."""
        from services.geo_service import find_nearest_feature

        # A legacy feature type that might still exist in DB
        legacy_feat = _fake_feature("f1", "assembly_point", "Assembly Area", 32.05, 34.05)

        def fake_list(workspace_id: str, feature_type: Optional[str] = None):
            if feature_type == "shelter":
                return []
            return [legacy_feat]

        with patch("services.geo_service.list_geo_features", side_effect=fake_list):
            with patch("services.geo_service.db_available", return_value=True):
                result = find_nearest_feature("ws-1", "shelter", 32.0, 34.0)

        assert result is not None
        assert result["feature_id"] == "f1"

    def test_returns_none_when_no_features_at_all(self):
        from services.geo_service import find_nearest_feature

        with patch("services.geo_service.list_geo_features", return_value=[]):
            with patch("services.geo_service.db_available", return_value=True):
                result = find_nearest_feature("ws-1", "shelter", 32.0, 34.0)

        assert result is None

    def test_returns_none_for_target_type_none(self):
        from services.geo_service import find_nearest_feature

        with patch("services.geo_service.db_available", return_value=True):
            result = find_nearest_feature("ws-1", "none", 32.0, 34.0)

        assert result is None

    def test_distance_meters_under_1000(self):
        from services.geo_service import find_nearest_feature

        near = _fake_feature("f1", "shelter", "Shelter A", 32.001, 34.001)

        with patch("services.geo_service.list_geo_features", return_value=[near]):
            with patch("services.geo_service.db_available", return_value=True):
                result = find_nearest_feature("ws-1", "shelter", 32.0, 34.0)

        assert result is not None
        assert result["distance_m"] < 1000


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Intent extraction
# ─────────────────────────────────────────────────────────────────────────────

def _make_tool_call_response(args: dict) -> MagicMock:
    """Build a mock that mimics the OpenAI tool-call response shape."""
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(args)

    message = MagicMock()
    message.tool_calls = [tool_call]

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    return response


class TestExtractIntent:
    def test_parses_shelter_intent(self):
        from app.emergency.intent_extractor import extract_intent, IntentResult

        mock_resp = _make_tool_call_response(
            {"action": "proceed_to_shelter", "target_type": "shelter", "urgency": "critical"}
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("app.emergency.intent_extractor._get_client", return_value=(mock_client, "test-model")):
            result = extract_intent("יש אזעקה, יש להיכנס למקלט בהקדם האפשרי.")

        assert isinstance(result, IntentResult)
        assert result.action == "proceed_to_shelter"
        assert result.target_type == "shelter"
        assert result.urgency == "critical"

    def test_parses_non_spatial_intent(self):
        from app.emergency.intent_extractor import extract_intent

        mock_resp = _make_tool_call_response(
            {"action": "call_supervisor", "target_type": "none", "urgency": "medium"}
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("app.emergency.intent_extractor._get_client", return_value=(mock_client, "test-model")):
            result = extract_intent("דווח למנהל האחראי בהקדם.")

        assert result.target_type == "none"
        assert result.action == "call_supervisor"

    def test_falls_back_to_safe_defaults_on_api_error(self):
        from app.emergency.intent_extractor import extract_intent

        with patch(
            "app.emergency.intent_extractor._get_client",
            side_effect=EnvironmentError("No API key"),
        ):
            result = extract_intent("כלשהו טקסט")

        assert result.action == "proceed_to_shelter"
        assert result.target_type == "shelter"
        assert result.urgency == "critical"

    def test_falls_back_when_no_tool_call_returned(self):
        from app.emergency.intent_extractor import extract_intent

        message = MagicMock()
        message.tool_calls = []  # no tool call

        choice = MagicMock()
        choice.message = message

        response = MagicMock()
        response.choices = [choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        with patch("app.emergency.intent_extractor._get_client", return_value=(mock_client, "test-model")):
            result = extract_intent("כלשהו טקסט")

        assert result.urgency == "critical"

    def test_defaults_to_critical_on_ambiguous_input(self):
        """Verify that urgency resolves to critical when the LLM returns critical for vague input."""
        from app.emergency.intent_extractor import extract_intent

        mock_resp = _make_tool_call_response(
            {"action": "investigate", "target_type": "none", "urgency": "critical"}
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("app.emergency.intent_extractor._get_client", return_value=(mock_client, "test-model")):
            result = extract_intent("מצב לא ברור — ייתכן שיש בעיה.")

        assert result.urgency == "critical"


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Full simulation orchestration
# ─────────────────────────────────────────────────────────────────────────────

def _make_rag_response(answer: str = "יש לפנות מיד למקלט הקרוב ביותר."):
    """Build a minimal RAGResponse mock."""
    source = MagicMock()
    source.document_id = "doc-001"
    source.file_name = "protocol.pdf"
    source.page_num = 3
    source.chunk_id = "chunk-1"
    source.text_snippet = answer[:100]

    resp = MagicMock()
    resp.answer = answer
    resp.sources = [source]
    return resp


class TestSimulateOrchestration:
    def _get_mock_sensor(self, lat: Optional[float] = 32.0, lng: Optional[float] = 34.0) -> dict:
        return {
            "sensor_id": "sensor-001",
            "workspace_id": "ws-1",
            "name": "Lobby Siren",
            "sensor_type": "SIREN",
            "status": "active",
            "lat": lat,
            "lng": lng,
        }

    def test_returns_full_result_shape(self):
        from services.emergency_service import simulate

        sensor = self._get_mock_sensor()
        rag_resp = _make_rag_response()
        nearest_feat = {
            "feature_id": "f1", "feature_type": "shelter", "label": "Main Shelter",
            "lat": 32.01, "lng": 34.01, "distance_m": 1200.0, "distance_display": "1.2 km",
        }

        with (
            patch("services.emergency_service.sensor_service.get_sensor", return_value=sensor),
            patch("services.emergency_service.pipeline.ask_pipeline", return_value=rag_resp),
            patch(
                "services.emergency_service.extract_intent",
                return_value=MagicMock(
                    action="proceed_to_shelter", target_type="shelter", urgency="critical",
                    model_dump=lambda: {"action": "proceed_to_shelter", "target_type": "shelter", "urgency": "critical"},
                ),
            ),
            patch("services.emergency_service.geo_service.find_nearest_feature", return_value=nearest_feat),
            patch("services.emergency_service._log_event"),
        ):
            result = simulate("ws-1", "sensor-001", alert_level="critical")

        assert result["event_id"]
        assert result["sensor"]["sensor_id"] == "sensor-001"
        assert result["alert_level"] == "critical"
        assert result["rag_answer"] == rag_resp.answer
        assert result["intent"]["action"] == "proceed_to_shelter"
        assert result["nearest_feature"]["label"] == "Main Shelter"
        assert "יעד:" in result["directive"]
        assert "1.2 km" in result["directive"]

    def test_handles_missing_sensor_gracefully(self):
        from services.emergency_service import simulate

        with patch("services.emergency_service.sensor_service.get_sensor", return_value=None):
            with pytest.raises(ValueError, match="Sensor not found"):
                simulate("ws-1", "bad-sensor-id")

    def test_rag_failure_returns_default_answer(self):
        from services.emergency_service import simulate

        sensor = self._get_mock_sensor()

        with (
            patch("services.emergency_service.sensor_service.get_sensor", return_value=sensor),
            patch(
                "services.emergency_service.pipeline.ask_pipeline",
                side_effect=RuntimeError("LLM unavailable"),
            ),
            patch(
                "services.emergency_service.extract_intent",
                return_value=MagicMock(
                    action="proceed_to_shelter", target_type="shelter", urgency="critical",
                    model_dump=lambda: {"action": "proceed_to_shelter", "target_type": "shelter", "urgency": "critical"},
                ),
            ),
            patch("services.emergency_service.geo_service.find_nearest_feature", return_value=None),
            patch("services.emergency_service._log_event"),
        ):
            result = simulate("ws-1", "sensor-001")

        assert "המידע המבוקש לא נמצא" in result["rag_answer"]

    def test_no_geo_feature_produces_fallback_directive(self):
        from services.emergency_service import simulate

        sensor = self._get_mock_sensor()
        rag_resp = _make_rag_response()

        with (
            patch("services.emergency_service.sensor_service.get_sensor", return_value=sensor),
            patch("services.emergency_service.pipeline.ask_pipeline", return_value=rag_resp),
            patch(
                "services.emergency_service.extract_intent",
                return_value=MagicMock(
                    action="proceed_to_shelter", target_type="shelter", urgency="critical",
                    model_dump=lambda: {"action": "proceed_to_shelter", "target_type": "shelter", "urgency": "critical"},
                ),
            ),
            patch("services.emergency_service.geo_service.find_nearest_feature", return_value=None),
            patch("services.emergency_service._log_event"),
        ):
            result = simulate("ws-1", "sensor-001")

        assert result["nearest_feature"] is None
        assert "פינוי כללי" in result["directive"]

    def test_sensor_without_coords_skips_geo_routing(self):
        from services.emergency_service import simulate

        sensor = self._get_mock_sensor(lat=None, lng=None)
        rag_resp = _make_rag_response()

        with (
            patch("services.emergency_service.sensor_service.get_sensor", return_value=sensor),
            patch("services.emergency_service.pipeline.ask_pipeline", return_value=rag_resp),
            patch(
                "services.emergency_service.extract_intent",
                return_value=MagicMock(
                    action="proceed_to_shelter", target_type="shelter", urgency="critical",
                    model_dump=lambda: {"action": "proceed_to_shelter", "target_type": "shelter", "urgency": "critical"},
                ),
            ),
            patch("services.emergency_service.geo_service.find_nearest_feature") as mock_geo,
            patch("services.emergency_service._log_event"),
        ):
            result = simulate("ws-1", "sensor-001")

        mock_geo.assert_not_called()
        assert result["nearest_feature"] is None

    def test_distance_display_km_when_over_1000m(self):
        from services.emergency_service import _build_directive
        from app.emergency.intent_extractor import IntentResult

        intent = IntentResult(action="proceed_to_shelter", target_type="shelter", urgency="critical")
        sensor = {"name": "Sensor A", "sensor_id": "s1"}
        nearest = {
            "label": "Far Shelter",
            "feature_type": "shelter",
            "distance_m": 1500.0,
            "distance_display": "1.5 km",
        }

        directive = _build_directive(intent, nearest, sensor)
        assert "1.5 km" in directive

    def test_distance_display_meters_when_under_1000m(self):
        from services.emergency_service import _build_directive
        from app.emergency.intent_extractor import IntentResult

        intent = IntentResult(action="proceed_to_shelter", target_type="shelter", urgency="critical")
        sensor = {"name": "Sensor A", "sensor_id": "s1"}
        nearest = {
            "label": "Near Shelter",
            "feature_type": "shelter",
            "distance_m": 250.0,
            "distance_display": "250 m",
        }

        directive = _build_directive(intent, nearest, sensor)
        assert "250 m" in directive
