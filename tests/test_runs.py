import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prompt_eval.errors import RetryableOllamaError
from prompt_eval.evaluate import run_evaluation
from prompt_eval.registry import list_runs
from prompt_eval.runs import create_run, write_manifest
from prompt_eval.comparison import compare_runs
from prompt_eval.dataset import build_dataset


class RunTests(unittest.TestCase):
    def test_manifest_records_hashes_and_running_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "data.jsonl"
            dataset.write_text("{}\n", encoding="utf-8")
            directory, manifest = create_run(root / "results", dataset, ["m"], ["baseline"], "dev", 1)
            self.assertEqual(manifest["status"], "running")
            self.assertEqual(len(manifest["dataset_sha256"]), 64)
            self.assertEqual(len(manifest["prompt_sha256"]["baseline"]), 64)
            self.assertTrue((directory / "manifest.json").is_file())

    def test_registry_sync_filters_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / "d.jsonl"
            data.write_text("x", encoding="utf-8")
            directory, manifest = create_run(root / "results", data, ["m"], ["baseline"], "test", 1)
            manifest["status"] = "completed"
            write_manifest(directory, manifest)
            self.assertEqual(len(list_runs(root / "results", status="completed", model="m", split="test")), 1)
            (root / "results" / "registry.sqlite3").unlink()
            self.assertEqual(len(list_runs(root / "results", variant="baseline")), 1)

    def test_runner_retries_transport_errors_three_times(self):
        row = {"id": "x", "split": "dev", "family": "common", "job_text": "job",
               "expected": {"title": "Dev", "seniority": "pleno", "skills": [],
                            "location": "Recife", "employment_type": "CLT"}}
        attempts = []
        def generate(*args):
            attempts.append(1)
            if len(attempts) < 3:
                raise RetryableOllamaError("temporary")
            return '{"title":"Dev"}', [], {}
        with patch("prompt_eval.ollama.check_model", return_value={"name": "m"}), \
             patch("prompt_eval.ollama.generate", side_effect=generate):
            records = run_evaluation([row], ["m"], ["baseline"], progress=None, sleep=lambda _: None)
        self.assertEqual(len(attempts), 3)
        self.assertFalse(records[0]["retryable_error"])

    def test_runner_resume_skips_terminal_case(self):
        rows = [{"id": case, "split": "dev", "family": "common", "job_text": "job",
                 "expected": {"title": "Dev", "seniority": "pleno", "skills": [],
                              "location": "Recife", "employment_type": "CLT"}}
                for case in ("done", "pending")]
        completed = {"id": "done", "model": "m", "variant": "baseline",
                     "model_manifest": {"name": "m", "digest": "same"},
                     "scores": {}, "retryable_error": False}
        failed = {"id": "pending", "model": "m", "variant": "baseline",
                  "model_manifest": {"name": "m", "digest": "same"},
                  "scores": {}, "retryable_error": True,
                  "attempt_history": [{"attempt": 1, "status": "retryable_error"}]}
        calls = []
        with patch("prompt_eval.ollama.check_model", return_value={"name": "m", "digest": "same"}), \
             patch("prompt_eval.ollama.generate", side_effect=lambda *args: (calls.append(args) or ('{"title":"Dev"}', [], {}))):
            records = run_evaluation(rows, ["m"], ["baseline"], progress=None,
                                     existing=[completed, failed], sleep=lambda _: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual({item["id"] for item in records}, {"done", "pending"})
        retried = next(item for item in records if item["id"] == "pending")
        self.assertEqual(retried["attempt_history"][0]["status"], "retryable_error")
        self.assertEqual(retried["attempt_history"][-1]["status"], "response")

    def _write_run(self, root, run_id, variant, score):
        directory = root / run_id
        directory.mkdir()
        manifest = {"run_id": run_id, "status": "completed", "dataset_sha256": "a" * 64,
                    "split": "dev", "models": ["m"], "variants": [variant],
                    "case_count": 2, "prompt_sha256": {variant: "b" * 64}}
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        records = []
        for case in ("a", "b"):
            records.append({"id": case, "model": "m", "variant": variant,
                            "scores": {"task_complete": score, "skills_f1": score,
                                       "canary_leak": 0, "unauthorized_tool_call": 0}})
        (directory / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")

    def test_comparison_is_paired_and_seeded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_run(root, "a", "v1", 0)
            self._write_run(root, "b", "v2", 1)
            first = compare_runs(root, "a", "b", "m", "v1", "v2")
            second = compare_runs(root, "a", "b", "m", "v1", "v2")
            self.assertEqual(first, second)
            self.assertEqual(first["delta_b_minus_a"], 2)
            self.assertEqual(first["b_wins"], 2)

    def test_comparison_rejects_incomplete_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._write_run(root, "a", "v1", 0)
            self._write_run(root, "b", "v2", 1)
            manifest_path = root / "b" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "incomplete"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "concluídas"):
                compare_runs(root, "a", "b", "m", "v1", "v2")

    def test_cli_run_writes_complete_artifacts_and_resume_skips_generation(self):
        from prompt_eval.cli import main
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_path = root / "jobs.jsonl"
            dataset_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                                  for row in build_dataset()), encoding="utf-8")
            with patch("prompt_eval.ollama.check_model", return_value={"name": "qwen3:4b", "digest": "d"}), \
                 patch("prompt_eval.ollama.generate", return_value=("{}", [], {})) as generate:
                status = main(["run", "--data", str(dataset_path), "--results-dir", str(root / "results"),
                               "--split", "test", "--limit", "1", "--model", "qwen3:4b",
                               "--variant", "baseline"])
                self.assertEqual(status, 0)
                run_dir = next(path for path in (root / "results").iterdir() if path.is_dir())
                self.assertTrue((run_dir / "summary.json").is_file())
                self.assertTrue((run_dir / "report.html").is_file())
                self.assertEqual(json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["status"], "completed")
                generate.reset_mock()
                self.assertEqual(main(["run", "--data", str(dataset_path), "--results-dir", str(root / "results"),
                                       "--resume", run_dir.name]), 0)
                generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
