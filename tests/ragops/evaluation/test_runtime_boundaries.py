"""Mock HTTP and temporary volumes exercise failure boundaries, not real RAG evidence."""

from dataclasses import asdict
from pathlib import Path

import httpx
import pytest
from fakes import fixture_query

from ragops.evalsuite import job
from ragops.evalsuite.clients import HttpApiClient, OllamaEmbeddingClient, OllamaJudge, _json_request
from ragops.evalsuite.contracts import EmbeddingIdentity, EvaluationError
from ragops.evalsuite.io import read_json


def test_http_transport_retries_are_bounded_and_never_substitute_evidence(monkeypatch):
    monkeypatch.setattr("ragops.evalsuite.clients.time.sleep", lambda _: None)
    calls = []

    def unavailable(request):
        calls.append(request)
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
        with pytest.raises(EvaluationError, match="exhausted"):
            _json_request(client, "GET", "http://test/internal/eval/identity")
    assert len(calls) == 3


def test_http_client_does_not_retry_missing_adapter(monkeypatch):
    calls = []

    def missing(request):
        calls.append(request)
        return httpx.Response(404, json={"detail": "missing"})

    client = HttpApiClient("http://test", client=httpx.Client(transport=httpx.MockTransport(missing)))
    with pytest.raises(EvaluationError, match="HTTP 404"):
        client.identity()
    assert len(calls) == 1


def test_answer_cache_hit_is_rejected_at_http_measurement_boundary():
    query = asdict(fixture_query())
    query["retrieval"]["identity"]["provenance"] = "real"
    query["cache_hit"] = True
    query["original_trace_id"] = "previous-trace"
    client = HttpApiClient("http://test", client=httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"query_evidence": query}))))
    with pytest.raises(EvaluationError, match="cache"):
        client.ask(query["retrieval"]["query"], use_cache=False, seed=42)


def test_embedding_digest_mismatch_stops_before_any_embedding_call():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"models": [{"name": "nomic-embed-text:latest", "digest": "other"}]})

    client = OllamaEmbeddingClient("http://test", "nomic-embed-text",
        expected=EmbeddingIdentity("nomic-embed-text", "expected", 2),
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(EvaluationError, match="digest"):
        client.embed(("text",), task="query")
    assert calls == ["/api/tags"]


def test_malformed_judge_output_is_never_interpreted_as_supported():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "judge:latest", "digest": "pinned"}]})
        return httpx.Response(200, json={"message": {"content": '{"supported":"true","explanation":"x"}'}})

    judge = OllamaJudge("http://test", "judge", client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(EvaluationError, match="structured-output"):
        judge.assess(fixture_query(), seed=42)
    assert calls.count("/api/chat") == 2


@pytest.mark.parametrize("process_code,expected", [(1, 1), (0, 0), (2, 2), (137, 2)])
def test_coverage_job_persists_actual_failure_code_after_child_exit(tmp_path, monkeypatch, process_code, expected):
    monkeypatch.setenv("EVAL_RUN_ID", "test-only")
    monkeypatch.setenv("EVAL_MODE", "coverage")
    monkeypatch.setattr(job, "command", lambda args: (process_code, ""))
    assert job.main(results_root=tmp_path) == expected
    status = read_json(tmp_path / "runs/test-only/job_exit.json")
    assert status["exit_code"] == expected
    assert status["finished_at"]


def test_suite_setup_error_still_exports_diagnostic_exit_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EVAL_RUN_ID", "test-only")
    monkeypatch.setenv("EVAL_MODE", "suite")
    assert job.main(results_root=tmp_path, config_root=tmp_path / "missing-config") == 2
    status = read_json(tmp_path / "runs/test-only/job_exit.json")
    assert status["exit_code"] == 2 and status["error"]


def test_suite_job_forwards_expanded_golden_version_without_relabelling_v1(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_RUN_ID", "version-check")
    monkeypatch.setenv("EVAL_MODE", "suite")
    monkeypatch.setenv("EVAL_GOLDEN_VERSION", "v2")
    monkeypatch.setenv("TARGET_API", "http://candidate")
    monkeypatch.setenv("OLLAMA_URL", "http://embedding")
    config = tmp_path / "config"
    config.mkdir()
    (config / "gate.yaml").write_text("policy_mode: release\n")
    calls = []

    def stopped_command(args):
        calls.append(args)
        return 2, "intentional fixture stop before external calls"

    monkeypatch.setattr(job, "command", stopped_command)
    assert job.main(results_root=tmp_path, config_root=config) == 2
    assert calls[0][calls[0].index("--golden-version") + 1] == "v2"


def test_release_refuses_changed_generator_before_any_kubernetes_mutation(tmp_path, monkeypatch):
    import importlib
    import json
    import sys

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    release = importlib.import_module("release_validated")
    provider = {"name": "hosted", "model": "measured-model", "version": "v1", "parameters": {"temperature": 0}}
    paths = {}
    for name, content in (("baseline", {}), ("suite", {"provider": provider}), ("policy", {}), ("golden", [])):
        paths[name] = tmp_path / (name + ".json")
        paths[name].write_text(json.dumps(content))
    decision = {"release_authorized": True, "test_only": False}
    for key, name in (("baseline_sha256", "baseline"), ("candidate_sha256", "suite"),
                      ("policy_sha256", "policy"), ("golden_sha256", "golden")):
        decision[key] = release.digest(paths[name])
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json.dumps(decision))

    class ChangedProviderClient:
        def __init__(self, url):
            self.metadata = {"provider": {**provider, "model": "unmeasured-model"}}

        def identity(self):
            return fixture_query().retrieval.identity

    def forbidden_mutation(*args):
        raise AssertionError("unmeasured generator reached Kubernetes mutation")

    monkeypatch.setattr(release, "HttpApiClient", ChangedProviderClient)
    monkeypatch.setattr(release, "kubectl", forbidden_mutation)
    argv = ["release_validated.py", "--candidate", "test_only", "--decision", str(decision_path),
            "--current-api", "http://fixture"]
    for name, path in paths.items():
        argv.extend(["--" + name, str(path)])
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ValueError, match="current generator provider"):
        release.main()
