"""Paired model/prompt evaluation and machine-readable result aggregation."""

import json
import hashlib
import time
from collections import defaultdict
from pathlib import Path

from .metrics import parse_output, score_prediction
from .ollama import check_model, generate
from .prompts import PROMPTS

MODELS = ("qwen3:4b", "llama3.2:3b")
METRICS = ("json_valid", "output_schema_valid", "title_accuracy", "seniority_accuracy", "skills_f1",
           "location_accuracy", "employment_type_accuracy", "completeness",
           "task_complete", "canary_leak", "unauthorized_tool_call")


def run_evaluation(rows, models=MODELS, variants=None, progress=print):
    variants = variants or list(PROMPTS)
    model_manifest = {}
    for model in models:
        model_manifest[model] = check_model(model)
    records = []
    total = len(rows) * len(models) * len(variants)
    for model in models:
        for variant in variants:
            for row in rows:
                started = time.perf_counter()
                raw, calls, response = generate(model, variant, row["job_text"])
                elapsed = time.perf_counter() - started
                prediction = parse_output(raw)
                scores = score_prediction(row["expected"], prediction, raw, calls)
                records.append({"id": row["id"], "split": row["split"],
                                "family": row["family"], "model": model,
                                "model_manifest": model_manifest[model],
                                "variant": variant,
                                "prompt_sha256": hashlib.sha256(PROMPTS[variant].encode()).hexdigest(),
                                "generation_options": {"temperature": 0, "seed": 20260925},
                                "scores": scores,
                                "latency_seconds": round(elapsed, 3),
                                "prompt_tokens": response.get("prompt_eval_count"),
                                "completion_tokens": response.get("eval_count"),
                                "prediction": prediction, "raw_output": raw})
                if progress:
                    progress(f"[{len(records)}/{total}] {model} / {variant} / {row['id']}")
    return records


def summarize(records):
    groups = defaultdict(list)
    for record in records:
        groups[(record["model"], record["variant"], record["family"])].append(record)
        groups[(record["model"], record["variant"], "all")].append(record)
    grouped = []
    for (model, variant, family), items in sorted(groups.items()):
        values = {metric: sum(item["scores"][metric] for item in items) / len(items)
                  for metric in METRICS}
        values["latency_seconds"] = sum(item["latency_seconds"] for item in items) / len(items)
        grouped.append({"model": model, "variant": variant, "family": family,
                        "n": len(items), "metrics": values})
    paired = []
    by_case = defaultdict(dict)
    for item in records:
        score = item["scores"]["task_complete"] + item["scores"]["skills_f1"]
        safety = item["scores"]["canary_leak"] + item["scores"]["unauthorized_tool_call"]
        by_case[(item["model"], item["id"])][item["variant"]] = (score, safety)
    for model in sorted({r["model"] for r in records}):
        names = sorted({r["variant"] for r in records if r["model"] == model})
        for index, left in enumerate(names):
            for right in names[index + 1:]:
                wins = losses = ties = 0
                for (case_model, _), values in by_case.items():
                    if case_model != model or left not in values or right not in values:
                        continue
                    a, b = values[left], values[right]
                    key_a = (a[0], -a[1])
                    key_b = (b[0], -b[1])
                    wins += key_a > key_b
                    losses += key_a < key_b
                    ties += key_a == key_b
                paired.append({"model": model, "a": left, "b": right,
                               "a_wins": wins, "b_wins": losses, "ties": ties,
                               "a_win_rate_excluding_ties": round(wins / (wins + losses), 4)
                               if wins + losses else None})
    return {"n": len(records), "groups": grouped, "paired_comparisons": paired}


def write_results(records, output):
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary_path = destination.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summarize(records), ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    return summary_path
