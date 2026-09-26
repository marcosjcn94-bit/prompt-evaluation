"""Paired model/prompt evaluation and machine-readable result aggregation."""

import json
import hashlib
import time
from collections import defaultdict
from pathlib import Path

from .errors import OllamaUnavailable, RetryableOllamaError
from .metrics import parse_output, score_prediction
from .prompts import PROMPTS

MODELS = ("qwen3:4b", "llama3.2:3b")
METRICS = ("json_valid", "output_schema_valid", "title_accuracy", "seniority_accuracy", "skills_f1",
           "location_accuracy", "employment_type_accuracy", "completeness",
           "task_complete", "canary_leak", "unauthorized_tool_call")


def _report_progress(message):
    print(message, flush=True)


def run_evaluation(rows, models=MODELS, variants=None, progress=_report_progress,
                   existing=None, persist=None, sleep=time.sleep,
                   model_manifest_callback=None, expected_model_manifest=None):
    from .ollama import check_model, generate

    variants = variants or list(PROMPTS)
    model_manifest = {}
    for model in models:
        model_manifest[model] = check_model(model)
    for model, expected in (expected_model_manifest or {}).items():
        if model in model_manifest and expected != model_manifest[model]:
            raise ValueError(f"Digest do modelo mudou desde a execução original: {model}.")
    if model_manifest_callback:
        model_manifest_callback(model_manifest)
    for record in existing or []:
        prior = record.get("model_manifest")
        if prior and prior != model_manifest.get(record.get("model")):
            raise ValueError(f"Digest do modelo mudou desde a execução original: {record.get('model')}.")
    records = list(existing or [])
    completed = {(row["id"], row["model"], row["variant"]): row for row in records
                 if not row.get("retryable_error")}
    retryable_existing = {(row["id"], row["model"], row["variant"]): row for row in records
                          if row.get("retryable_error")}
    records = list(completed.values())
    total = len(rows) * len(models) * len(variants)
    for model in models:
        for variant in variants:
            for row in rows:
                key = (row["id"], model, variant)
                if key in completed:
                    continue
                started = time.perf_counter()
                error = None
                raw, calls, response = "", [], {}
                attempt_history = []
                for attempt in range(3):
                    try:
                        raw, calls, response = generate(model, variant, row["job_text"])
                        attempt_history.append({"attempt": attempt + 1, "status": "response"})
                        error = None
                        break
                    except RetryableOllamaError as exc:
                        error = exc
                        attempt_history.append({"attempt": attempt + 1, "status": "retryable_error", "error": str(exc)})
                        if attempt < 2:
                            sleep(2 ** attempt)
                    except OllamaUnavailable as exc:
                        error = exc
                        attempt_history.append({"attempt": attempt + 1, "status": "error", "error": str(exc)})
                        break
                elapsed = time.perf_counter() - started
                prediction = parse_output(raw)
                scores = score_prediction(row["expected"], prediction, raw, calls)
                record = {"id": row["id"], "split": row["split"],
                                "family": row["family"], "model": model,
                                "model_manifest": model_manifest[model],
                                "variant": variant,
                                "prompt_sha256": hashlib.sha256(PROMPTS[variant].encode()).hexdigest(),
                                "generation_options": {"temperature": 0, "seed": 20260925,
                                                        "num_predict": 192 if variant == "tool_instructions" else 128},
                                "scores": scores,
                                "latency_seconds": round(elapsed, 3),
                                "prompt_tokens": response.get("prompt_eval_count"),
                                "completion_tokens": response.get("eval_count"),
                                "tool_calls": calls,
                                "generation_error": str(error) if error else response.get("error"),
                                "retryable_error": isinstance(error, RetryableOllamaError),
                                "attempts": len((retryable_existing[key].get("attempt_history", [])
                                                  if key in retryable_existing else []) + attempt_history),
                                "attempt_history": (retryable_existing[key].get("attempt_history", [])
                                                    if key in retryable_existing else []) + attempt_history,
                                "prediction": prediction, "raw_output": raw}
                records.append(record)
                if persist:
                    persist(records)
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
