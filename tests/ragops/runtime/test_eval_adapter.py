"""Unit tests for Member 1's /internal/eval/* envelopes and adapter logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest

pytest.importorskip("fastapi")


def test_runtime_identity_structure() -> None:
    from api.app.routes.eval_adapter import _build_runtime_identity
    from api.app.config import Settings

    settings = Settings(
        collection="rahbar_a",
        top_k=5,
        temperature=0.2,
        relevance_floor=0.35,
        cache_threshold=0.90,
        prompt_version="v1",
        embed_model="nomic-embed-text",
        embed_version="sha256:abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd",
    )

    mock_state = MagicMock()
    mock_state.retriever.get_collection_metadata.return_value = {
        "committed_revision": "2",
        "embed_digest": "sha256:abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd",
        "dimension": 768,
        "corpus_sha256": "0" * 64,
        "vector_sha256": "1" * 64,
        "pipeline_sha256": "2" * 64,
    }

    identity = _build_runtime_identity(settings, mock_state)
    assert identity["collection"] == "rahbar_a"
    assert identity["revision"] == "2"
    assert identity["provenance"] == "real"
    assert identity["embedding"]["model"] == "nomic-embed-text"
    assert identity["embedding"]["digest"] == "sha256:abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd"
    assert identity["embedding"]["dimension"] == 768
    assert len(identity["corpus_sha256"]) == 64
    assert len(identity["pipeline_sha256"]) == 64
    assert identity["vector_sha256"] == "1" * 64

    config = json.loads(identity["config_json"])
    assert config["top_k"] == 5
    assert config["temperature"] == 0.2


def test_eval_adapter_routes_with_fastapi(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app.main import app

    monkeypatch.setenv("EVAL_INTERNAL_ENABLED", "true")

    with TestClient(app) as client:
        r_id = client.get("/internal/eval/identity")
        assert r_id.status_code == 200
        id_data = r_id.json()
        assert id_data["schema_version"] == "1.0"
        assert "identity" in id_data
        assert "provider" in id_data
        # Ensure top_k is NOT inside provider.parameters
        assert "top_k" not in id_data["provider"]["parameters"]
        assert "temperature" in id_data["provider"]["parameters"]

        r_ret = client.post("/internal/eval/retrieve", json={"question": "What is the probation policy?"})
        assert r_ret.status_code == 200
        ret_data = r_ret.json()
        assert "retrieval" in ret_data
        assert ret_data["retrieval"]["query"] == "What is the probation policy?"
        assert isinstance(ret_data["retrieval"]["passages"], list)

        r_ask = client.post("/internal/eval/ask", json={"question": "What is the probation policy?"})
        assert r_ask.status_code == 200
        ask_data = r_ask.json()
        assert "query_evidence" in ask_data
        assert "trace" in ask_data
        ev = ask_data["query_evidence"]
        assert "retrieval" in ev
        assert "answer" in ev
        assert "citations" in ev
        assert "stage_latencies_ms" in ev
