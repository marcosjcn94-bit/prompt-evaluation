import json
import copy
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prompt_eval.dataset import build_dataset
from prompt_eval.evaluate import summarize
from prompt_eval.metrics import CANARY, score_prediction
from prompt_eval.prompts import render_prompt, tool_result
from prompt_eval.cli import validate_dataset


class DatasetTests(unittest.TestCase):
    def test_dataset_is_reproducible_and_has_approved_split(self):
        first = build_dataset(seed=17)
        second = build_dataset(seed=17)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 150)
        self.assertEqual(sum(row["split"] == "dev" for row in first), 100)
        self.assertEqual(sum(row["split"] == "test" for row in first), 50)
        self.assertEqual(sum(row["family"] == "common" for row in first), 100)
        self.assertEqual(sum(row["family"] != "common" for row in first), 50)

    def test_adversarial_families_are_balanced(self):
        rows = [row for row in build_dataset(seed=17) if row["family"] != "common"]
        counts = {}
        for row in rows:
            counts[row["family"]] = counts.get(row["family"], 0) + 1
        self.assertEqual(sorted(counts.values()), [10, 10, 10, 10, 10])

    def test_attack_case_stays_with_its_source_in_the_same_split(self):
        rows = build_dataset(seed=17)
        by_id = {row["id"]: row for row in rows}
        for row in rows:
            if row["family"] != "common":
                self.assertEqual(row["split"], by_id[row["source_id"]]["split"])

    def test_validation_rejects_wrong_skill_type_and_family_counts(self):
        rows = build_dataset(seed=17)
        malformed = copy.deepcopy(rows)
        malformed[0]["expected"]["skills"] = "Python"
        with self.assertRaisesRegex(ValueError, "skills"):
            validate_dataset(malformed)
        malformed = copy.deepcopy(rows)
        malformed[0]["family"] = "unknown"
        with self.assertRaisesRegex(ValueError, "famílias"):
            validate_dataset(malformed)

    def test_tool_cases_include_aliases_with_canonical_gold_labels(self):
        rows = build_dataset(seed=17)
        cases = [row for row in rows if any(alias in row["job_text"] for alias in ("JS", "K8s", "ML"))]
        self.assertTrue(cases)
        for row in cases:
            canonical = {"JS": "JavaScript", "K8s": "Kubernetes", "ML": "Machine Learning"}
            self.assertTrue(any(skill in row["expected"]["skills"] for alias, skill in canonical.items()
                                if alias in row["job_text"]))


class MetricTests(unittest.TestCase):
    def test_field_metrics_score_normalized_values(self):
        expected = {"title": "Analista de Dados", "skills": ["Python", "SQL"]}
        actual = {"title": " analista de dados ", "skills": ["SQL", "Python"]}
        scores = score_prediction(expected, actual)
        self.assertEqual(scores["title_accuracy"], 1.0)
        self.assertEqual(scores["skills_f1"], 1.0)

    def test_invalid_json_is_scored_as_format_failure(self):
        scores = score_prediction({"title": "Dev"}, None)
        self.assertEqual(scores["json_valid"], 0)
        self.assertEqual(scores["title_accuracy"], 0.0)

    def test_canary_and_unapproved_tool_calls_are_visible(self):
        scores = score_prediction({}, {}, f"leak: {CANARY}", ["send_email"])
        self.assertEqual(scores["canary_leak"], 1)
        self.assertEqual(scores["unauthorized_tool_call"], 1)

    def test_malformed_skill_value_is_scored_without_aborting(self):
        expected = {"title": "Dev", "seniority": "pleno", "skills": ["Python"],
                    "location": "Remoto", "employment_type": "CLT"}
        for value in (None, "Python"):
            prediction = {**expected, "skills": value}
            scores = score_prediction(expected, prediction)
            self.assertEqual(scores["json_valid"], 1)
            self.assertEqual(scores["output_schema_valid"], 0)
            self.assertEqual(scores["task_complete"], 0)

    def test_json_schema_variant_does_not_claim_tool_access(self):
        self.assertNotIn("lookup_skill_taxonomy", render_prompt("json_schema", "vaga"))

    def test_tool_normalizes_a_single_string_argument_as_one_skill(self):
        self.assertEqual(json.loads(tool_result({"skills": "K8s"})), ["Kubernetes"])

    def test_summary_includes_aggregate_and_paired_win_rate(self):
        base = {"model": "local", "family": "common", "id": "x", "latency_seconds": 0.1}
        expected = {"title": "Dev", "seniority": "pleno", "skills": ["Python"],
                    "location": "Remoto", "employment_type": "CLT"}
        a = {**base, "variant": "a", "scores": score_prediction(expected, expected)}
        b = {**base, "variant": "b", "scores": score_prediction(expected, {})}
        result = summarize([a, b])
        self.assertTrue(any(group["family"] == "all" for group in result["groups"]))
        self.assertEqual(result["paired_comparisons"][0]["a_win_rate_excluding_ties"], 1.0)


class CliTests(unittest.TestCase):
    def test_missing_ollama_gives_actionable_message_and_no_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "results.jsonl"
            env = os.environ.copy()
            env.update({"PATH": temp, "PYTHONPATH": str(ROOT / "src"),
                        "OLLAMA_HOST": "http://127.0.0.1:1"})
            command = [sys.executable, "-m", "prompt_eval.cli", "run", "--output", str(output), "--model", "missing:model"]
            result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Ollama", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("http://127.0.0.1:1", result.stderr)


if __name__ == "__main__":
    unittest.main()
