"""Strict artifact I/O shared by evaluation, gates and coverage."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]


def _constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(text: str) -> Any:
    return json.loads(text, parse_constant=_constant, object_pairs_hook=_pairs)


def read_json(path: Path) -> dict[str, Any]:
    value = loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected an object")
        rows.append(value)
    if not rows:
        raise ValueError(f"{path}: empty dataset")
    return rows


def read_config(path: Path) -> dict[str, Any]:
    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader: Any, node: Any) -> dict[str, Any]:
        return _pairs(loader.construct_pairs(node, deep=True))

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a configuration object")
    # YAML .nan/.inf are not valid measured values or thresholds.
    json.dumps(value, allow_nan=False)
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                            for row in rows), encoding="utf-8")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_id(prefix: str) -> str:
    return prefix + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def git_sha() -> str:
    import os

    value = os.environ.get("SOURCE_GIT_SHA")
    if not value:
        value = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         text=True).strip()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("SOURCE_GIT_SHA must identify the full source commit")
    return value


def schema_check(name: str, value: Any) -> None:
    value = loads(json.dumps(value, allow_nan=False))
    schema = read_json(ROOT / "config/schemas/h0.schema.json")
    validator = Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": schema["$defs"]}, format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda error: str(error.path))
    if errors:
        raise ValueError(f"{name} at {list(errors[0].path)}: {errors[0].message}")


def finite(value: Any, *, minimum: float | None = None,
           maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"expected a finite number, got {value!r}")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"number must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"number must be <= {maximum}")
    return number
