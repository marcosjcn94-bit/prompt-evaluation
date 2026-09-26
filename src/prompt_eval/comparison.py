"""Descriptive paired comparison with a deterministic percentile bootstrap."""

import random
import statistics
from pathlib import Path

from .replay import read_response_jsonl
from .runs import load_manifest


def _quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def compare_runs(results_dir, run_a, run_b, model, variant_a, variant_b,
                 bootstrap_samples=2000, seed=20260925):
    root = Path(results_dir)
    directory_a, directory_b = root / run_a, root / run_b
    manifest_a, manifest_b = load_manifest(directory_a), load_manifest(directory_b)
    if manifest_a.get("status") != "completed" or manifest_b.get("status") != "completed":
        raise ValueError("A comparação exige duas execuções concluídas.")
    for field in ("dataset_sha256", "split"):
        if manifest_a.get(field) != manifest_b.get(field):
            raise ValueError(f"Execuções incompatíveis: {field} diferente.")
    if model not in manifest_a.get("models", []) or model not in manifest_b.get("models", []):
        raise ValueError("Modelo ausente em uma das execuções.")
    if variant_a not in manifest_a.get("variants", []) or variant_b not in manifest_b.get("variants", []):
        raise ValueError("Variante ausente em uma das execuções.")
    left = {item["id"]: item for item in read_response_jsonl(directory_a / "responses.jsonl")
            if item.get("model") == model and item.get("variant") == variant_a}
    right = {item["id"]: item for item in read_response_jsonl(directory_b / "responses.jsonl")
             if item.get("model") == model and item.get("variant") == variant_b}
    ids = sorted(left.keys() & right.keys())
    if len(ids) < 2 or set(left) != set(right):
        raise ValueError("É necessário ter ao menos dois casos com conjuntos de IDs idênticos.")
    scores_a, scores_b = [], []
    wins_a = wins_b = ties = 0
    for case_id in ids:
        a, b = left[case_id], right[case_id]
        score_a = a["scores"]["task_complete"] + a["scores"]["skills_f1"]
        score_b = b["scores"]["task_complete"] + b["scores"]["skills_f1"]
        safety_a = a["scores"]["canary_leak"] + a["scores"]["unauthorized_tool_call"]
        safety_b = b["scores"]["canary_leak"] + b["scores"]["unauthorized_tool_call"]
        key_a, key_b = (score_a, -safety_a), (score_b, -safety_b)
        wins_a += key_a > key_b
        wins_b += key_b > key_a
        ties += key_a == key_b
        scores_a.append(score_a)
        scores_b.append(score_b)
    deltas = [b - a for a, b in zip(scores_a, scores_b)]
    rng = random.Random(seed)
    boot = [statistics.mean(rng.choices(deltas, k=len(deltas))) for _ in range(bootstrap_samples)]
    return {"run_a": run_a, "run_b": run_b, "model": model,
            "variant_a": variant_a, "variant_b": variant_b, "n": len(ids),
            "mean_a": statistics.mean(scores_a), "mean_b": statistics.mean(scores_b),
            "delta_b_minus_a": statistics.mean(deltas), "a_wins": wins_a,
            "b_wins": wins_b, "ties": ties, "metric": "task_complete + skills_f1",
            "bootstrap_95_percentile": [_quantile(boot, .025), _quantile(boot, .975)],
            "bootstrap_samples": bootstrap_samples, "seed": seed,
            "interpretation": "Descritivo; intervalo bootstrap não é teste de significância."}
