"""Run identifiers, immutable configuration fingerprints, and manifests."""

import hashlib
import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import atomic_write_text
from .prompts import PROMPTS


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prompt_hashes(variants):
    unknown = sorted(set(variants) - PROMPTS.keys())
    if unknown:
        raise ValueError(f"Variantes de prompt desconhecidas: {', '.join(unknown)}.")
    return {name: hashlib.sha256(PROMPTS[name].encode("utf-8")).hexdigest() for name in variants}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_run(results_dir, dataset_path, models, variants, split, case_count, limit=None):
    hashes = prompt_hashes(variants)
    dataset_hash = sha256_file(dataset_path)
    run_id = uuid.uuid4().hex
    directory = Path(results_dir) / run_id
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"run_id": run_id, "status": "running", "created_at": now(),
                "updated_at": now(), "completed_at": None, "models": list(models),
                "variants": list(variants), "split": split, "case_count": case_count,
                "expected_responses": case_count * len(models) * len(variants),
                "limit": limit, "python_version": platform.python_version(),
                "dataset_path": str(Path(dataset_path).resolve()),
                "dataset_sha256": dataset_hash,
                "prompt_sha256": hashes}
    write_manifest(directory, manifest)
    return directory, manifest


def write_manifest(directory, manifest):
    manifest["updated_at"] = now()
    atomic_write_text(Path(directory) / "manifest.json",
                      json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def load_manifest(directory):
    try:
        value = json.loads((Path(directory) / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Manifest inválido em {directory}: {error}") from None
    required = {"run_id", "status", "models", "variants", "split", "case_count",
                "dataset_sha256", "prompt_sha256"}
    if (not isinstance(value, dict) or not required <= value.keys()
            or not isinstance(value.get("run_id"), str)
            or not isinstance(value.get("models"), list)
            or not isinstance(value.get("variants"), list)
            or not isinstance(value.get("prompt_sha256"), dict)
            or value.get("status") not in {"running", "incomplete", "interrupted", "completed"}):
        raise ValueError(f"Manifest inválido em {directory}.")
    return value
