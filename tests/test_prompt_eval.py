import json
import copy
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prompt_eval.dataset import build_dataset
from prompt_eval.evaluate import summarize
from prompt_eval.metrics import CANARY, score_prediction
from prompt_eval.ollama import generate
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

    def test_invalid_tool_arguments_become_case_error_without_crashing(self):
        tool_response = {"message": {"tool_calls": [{"function": {
            "name": "lookup_skill_taxonomy", "arguments": None}}]}}
        with patch("prompt_eval.ollama._request", return_value=tool_response):
            raw, calls, response = generate("llama3.2:3b", "tool_instructions", "vaga")
        self.assertEqual(raw, "")
        self.assertEqual(calls, ["lookup_skill_taxonomy"])
        self.assertEqual(response["error"], "invalid_tool_arguments")

    def test_summary_includes_aggregate_and_paired_win_rate(self):
        base = {"model": "local", "family": "common", "id": "x", "latency_seconds": 0.1}
        expected = {"title": "Dev", "seniority": "pleno", "skills": ["Python"],
                    "location": "Remoto", "employment_type": "CLT"}
        a = {**base, "variant": "a", "scores": score_prediction(expected, expected)}
        b = {**base, "variant": "b", "scores": score_prediction(expected, {})}
        result = summarize([a, b])
        self.assertTrue(any(group["family"] == "all" for group in result["groups"]))
        self.assertEqual(result["paired_comparisons"][0]["a_win_rate_excluding_ties"], 1.0)


class ReplayTests(unittest.TestCase):
    @staticmethod
    def _case(case_id="case-1"):
        expected = {"title": "Analista de Dados", "seniority": "pleno",
                    "skills": ["Python", "SQL"], "location": "Recife, PE",
                    "employment_type": "CLT"}
        dataset = [{"id": case_id, "expected": expected}]
        responses = [
            {"id": case_id, "model": "local", "variant": "a", "family": "common",
             "raw_output": json.dumps(expected, ensure_ascii=False), "tool_calls": [],
             "latency_seconds": 0.2, "scores": {"stale": 1}},
            {"id": case_id, "model": "local", "variant": "b", "family": "common",
             "raw_output": "not JSON", "tool_calls": [], "latency_seconds": 0.4,
             "scores": {"stale": 1}},
        ]
        return expected, dataset, responses

    def test_replay_recalculates_scores_and_pairs_repeated_case_ids(self):
        from prompt_eval.evaluate import summarize
        from prompt_eval.replay import replay_records

        _, dataset, responses = self._case()
        original = copy.deepcopy(responses)
        replayed = replay_records(responses, dataset)

        self.assertEqual(responses, original)
        self.assertEqual(replayed[0]["scores"]["title_accuracy"], 1.0)
        self.assertEqual(replayed[1]["scores"]["json_valid"], 0)
        comparison = summarize(replayed)["paired_comparisons"][0]
        self.assertEqual((comparison["a_wins"], comparison["b_wins"], comparison["ties"]),
                         (1, 0, 0))

    def test_replay_rejects_response_without_dataset_label(self):
        from prompt_eval.replay import replay_records

        _, dataset, responses = self._case()
        with self.assertRaisesRegex(ValueError, "case-1"):
            replay_records(responses, [{**dataset[0], "id": "another-case"}])

    def test_response_jsonl_reports_invalid_line_number(self):
        from prompt_eval.replay import read_response_jsonl

        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "responses.jsonl"
            source.write_text('{"id":"ok"}\nnot JSON\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "linha 2"):
                read_response_jsonl(source)

    def test_cli_replay_writes_summary_without_importing_ollama_or_changing_input(self):
        expected, dataset, responses = self._case()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "responses.jsonl"
            data = Path(temp) / "jobs.jsonl"
            source_text = json.dumps(responses[0], ensure_ascii=False) + "\n"
            source.write_text(source_text, encoding="utf-8")
            data.write_text(json.dumps(dataset[0], ensure_ascii=False) + "\n", encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            code = (
                "import sys; from prompt_eval.cli import main; "
                "status = main(['replay', '--input', sys.argv[1], '--data', sys.argv[2]]); "
                "assert 'prompt_eval.ollama' not in sys.modules; raise SystemExit(status)"
            )
            result = subprocess.run([sys.executable, "-c", code, str(source), str(data)],
                                    cwd=ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), source_text)
            summary = json.loads((Path(temp) / "responses.summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["n"], 1)
            self.assertEqual(summary["groups"][0]["metrics"]["title_accuracy"], 1.0)
            self.assertTrue((Path(temp) / "responses.report.html").is_file())

    def test_failed_atomic_replace_preserves_old_artifact_and_cleans_temp(self):
        from prompt_eval.artifacts import atomic_write_text

        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "summary.json"
            destination.write_text("old", encoding="utf-8")
            with patch.object(Path, "replace", side_effect=OSError("blocked")):
                with self.assertRaisesRegex(OSError, "blocked"):
                    atomic_write_text(destination, "new")
            self.assertEqual(destination.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(temp).iterdir()), [destination])


class ReportTests(unittest.TestCase):
    def test_report_is_responsive_escaped_and_excludes_raw_inputs(self):
        from prompt_eval.evaluate import summarize
        from prompt_eval.replay import replay_records
        from prompt_eval.report import render_report

        expected, dataset, responses = ReplayTests._case("<img src=x onerror=alert(1)>")
        responses[0]["family"] = "direct_override"
        responses[0]["raw_output"] = json.dumps(expected) + " RAW-SECRET-9271"
        responses[0]["job_text"] = "VACANCY-SECRET-3842"
        responses[0]["generation_error"] = "<script>alert('error')</script>"
        responses[0]["id"] = dataset[0]["id"]
        replayed = replay_records(responses, dataset)
        document = render_report(replayed, summarize(replayed), "<b>sample</b>.jsonl",
                                 "2026-09-26T16:00:00+00:00")

        self.assertIn("Resumo da execução", document)
        self.assertIn("Comparações pareadas", document)
        self.assertIn("resultados por família", document.lower())
        self.assertIn("direct_override", document)
        self.assertIn("Vitórias", document)
        self.assertIn("&lt;img", document)
        self.assertIn("&lt;script&gt;", document)
        self.assertIn("&lt;b&gt;sample&lt;/b&gt;", document)
        self.assertNotIn("<img", document)
        self.assertNotIn("<script", document)
        self.assertNotIn("RAW-SECRET-9271", document)
        self.assertNotIn("VACANCY-SECRET-3842", document)
        self.assertNotIn("https://", document.lower())
        self.assertNotIn("http://", document.lower())
        self.assertIn("@media", document)
        self.assertIn("overflow-x:auto", document)
        self.assertIn("significância estatística", document)


class CliTests(unittest.TestCase):
    def test_cli_import_does_not_load_ollama_client(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        code = (
            "import sys; import prompt_eval.cli; "
            "assert 'prompt_eval.ollama' not in sys.modules"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

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
