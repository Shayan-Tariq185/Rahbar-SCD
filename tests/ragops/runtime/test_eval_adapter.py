"""Unit tests for Member 1's /internal/eval/* envelopes and adapter logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest

pytest.importorskip("fastapi")


def test_runtime_identity_structure() -> None:
    from api.app.routes.eval_adapter import _build_runtime_identity

    mock_settings = MagicMock()
    mock_settings.collection = "rahbar_a"
    mock_settings.top_k = 5
    mock_settings.temperature = 0.2
    mock_settings.relevance_floor = 0.35
    mock_settings.cache_threshold = 0.90
    mock_settings.prompt_version = "v1"
    mock_settings.embed_model = "nomic-embed-text"
    mock_settings.embed_version = "sha256:abc12345"
    mock_settings.chunk_size = 500
    mock_settings.chunk_overlap = 50

    mock_state = MagicMock()
    mock_state.retriever.get_collection_metadata.return_value = {
        "committed_revision": "2",
        "embed_digest": "sha256:abc12345",
        "dimension": 768,
    }

    identity = _build_runtime_identity(mock_settings, mock_state)
    assert identity["collection"] == "rahbar_a"
    assert identity["revision"] == "2"
    assert identity["provenance"] == "real"
    assert identity["embedding"]["model"] == "nomic-embed-text"
    assert identity["embedding"]["digest"] == "sha256:abc12345"
    assert identity["embedding"]["dimension"] == 768
    assert len(identity["corpus_sha256"]) == 64
    assert len(identity["pipeline_sha256"]) == 64
    config = json.loads(identity["config_json"])
    assert config["top_k"] == 5


def test_eval_adapter_routes_with_fastapi() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app.main import app
    from api.app.config import get_settings

    settings = get_settings()
    settings.eval_internal_enabled = True

    with TestClient(app) as client:
        r_id = client.get("/internal/eval/identity")
        assert r_id.status_code == 200
        id_data = r_id.json()
        assert id_data["schema_version"] == "1.0"
        assert "identity" in id_data
        assert id_data["provider"]["name"] not in (None, "stub", "fixture")
