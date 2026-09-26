"""Rebuildable SQLite index over run manifests."""

import json
import sqlite3
from pathlib import Path

from .runs import load_manifest


def sync_runs(results_dir):
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    database = root / "registry.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("""CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, status TEXT NOT NULL, models TEXT NOT NULL,
            variants TEXT NOT NULL, split TEXT NOT NULL, dataset_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL, manifest_path TEXT NOT NULL)""")
        connection.execute("DELETE FROM runs")
        for path in root.glob("*/manifest.json"):
            try:
                item = load_manifest(path.parent)
                connection.execute("""INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (item["run_id"], item.get("status", "unknown"),
                     json.dumps(item.get("models", [])), json.dumps(item.get("variants", [])),
                     item.get("split", ""), item.get("dataset_sha256", ""),
                     item.get("created_at", ""), str(path.resolve())))
            except (ValueError, KeyError):
                continue
        connection.commit()
    finally:
        connection.close()
    return database


def list_runs(results_dir, status=None, model=None, variant=None, split=None):
    database = sync_runs(results_dir)
    query = "SELECT run_id,status,models,variants,split,dataset_sha256,created_at FROM runs"
    clauses, values = [], []
    for field, value in (("status", status), ("split", split)):
        if value:
            clauses.append(f"{field}=?")
            values.append(value)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC, run_id"
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(query, values).fetchall()
    finally:
        connection.close()
    result = []
    for run_id, state, models, variants, split_value, digest, created in rows:
        parsed_models, parsed_variants = json.loads(models), json.loads(variants)
        if model and model not in parsed_models or variant and variant not in parsed_variants:
            continue
        result.append({"run_id": run_id, "status": state, "models": parsed_models,
                       "variants": parsed_variants, "split": split_value,
                       "dataset_sha256": digest, "created_at": created})
    return result
