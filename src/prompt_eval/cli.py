"""Command line entry point. Dataset tasks work without a model service."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .dataset import read_dataset, write_dataset
from .errors import OllamaUnavailable
from .evaluate import MODELS, run_evaluation, summarize, write_results
from .prompts import PROMPTS
from .replay import read_response_jsonl, replay_records, write_summary
from .report import render_report, write_report
from .artifacts import atomic_write_text
from .runs import create_run, load_manifest, prompt_hashes, sha256_file, write_manifest
from .registry import list_runs

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data" / "jobs.jsonl"


def validate_dataset(rows):
    if len(rows) != 150:
        raise ValueError(f"Esperadas 150 vagas; encontradas {len(rows)}.")
    if sum(row.get("split") == "dev" for row in rows) != 100:
        raise ValueError("O conjunto dev deve conter 100 vagas.")
    if sum(row.get("split") == "test" for row in rows) != 50:
        raise ValueError("O conjunto test deve conter 50 vagas.")
    ids = [row.get("id") for row in rows]
    if len(set(ids)) != len(ids) or None in ids:
        raise ValueError("IDs ausentes ou duplicados.")
    required = {"title", "seniority", "skills", "location", "employment_type"}
    for row in rows:
        expected = row.get("expected")
        if not isinstance(row.get("job_text"), str) or not isinstance(expected, dict) or not required <= expected.keys():
            raise ValueError(f"Registro inválido: {row.get('id')}.")
        if any(not isinstance(expected[field], str) for field in required - {"skills"}):
            raise ValueError(f"Campo deve ser string em {row.get('id')}.")
        if not isinstance(expected["skills"], list) or not all(isinstance(skill, str) for skill in expected["skills"]):
            raise ValueError(f"Campo skills deve ser lista de strings em {row.get('id')}.")
    family_counts = {name: sum(row.get("family") == name for row in rows)
                     for name in {row.get("family") for row in rows}}
    expected_families = {"common": 100, "direct_override": 10, "role_impersonation": 10,
                         "canary_exfiltration": 10, "tool_abuse": 10,
                         "instruction_obfuscation": 10}
    if family_counts != expected_families:
        raise ValueError("Distribuição de famílias inválida.")
    by_id = {row["id"]: row for row in rows}
    expected_splits = {"common": {"dev": 70, "test": 30},
                       **{family: {"dev": 6, "test": 4} for family in expected_families if family != "common"}}
    for family, splits in expected_splits.items():
        for split, count in splits.items():
            actual = sum(row.get("family") == family and row.get("split") == split for row in rows)
            if actual != count:
                raise ValueError(f"Distribuição de split inválida para {family}/{split}.")
    for row in rows:
        if row["family"] != "common":
            source = by_id.get(row.get("source_id"))
            if not source or source["family"] != "common" or source["split"] != row["split"]:
                raise ValueError(f"source_id inválido em {row['id']}.")
    return {"rows": len(rows), "dev": 100, "test": 50,
            "families": {name: sum(row["family"] == name for row in rows)
                         for name in sorted({row["family"] for row in rows})}}


def parser():
    root = argparse.ArgumentParser(prog="prompt-eval",
        description="Avaliação reproduzível de prompts de extração em vagas sintéticas.")
    commands = root.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Gera o dataset sintético local.")
    generate.add_argument("--output", type=Path, default=DEFAULT_DATA)
    generate.add_argument("--seed", type=int, default=20260925)
    validate = commands.add_parser("validate", help="Valida dataset sem Ollama.")
    validate.add_argument("--data", type=Path, default=DEFAULT_DATA)
    run = commands.add_parser("run", help="Executa comparação pareada via Ollama local.")
    run.add_argument("--data", type=Path, default=DEFAULT_DATA)
    run.add_argument("--split", choices=("dev", "test", "all"))
    run.add_argument("--model", action="append", dest="models")
    run.add_argument("--variant", action="append", dest="variants")
    run.add_argument("--limit", type=int)
    run.add_argument("--output", type=Path, help="Espelha respostas em JSONL legado.")
    run.add_argument("--results-dir", type=Path, default=ROOT / "results")
    run.add_argument("--resume", metavar="RUN_ID")
    replay = commands.add_parser("replay", help="Recalcula métricas de respostas sem usar Ollama.")
    replay.add_argument("--input", type=Path, required=True)
    replay.add_argument("--data", type=Path, default=DEFAULT_DATA)
    runs = commands.add_parser("runs", help="Consulta o histórico local de execuções.")
    run_commands = runs.add_subparsers(dest="runs_command", required=True)
    list_command = run_commands.add_parser("list", help="Lista execuções indexadas.")
    list_command.add_argument("--results-dir", type=Path, default=ROOT / "results")
    list_command.add_argument("--status")
    list_command.add_argument("--model")
    list_command.add_argument("--variant")
    list_command.add_argument("--split")
    compare = commands.add_parser("compare", help="Compara duas execuções pareadas concluídas.")
    compare.add_argument("--run-a", required=True)
    compare.add_argument("--run-b", required=True)
    compare.add_argument("--model", required=True)
    compare.add_argument("--variant-a", required=True)
    compare.add_argument("--variant-b", required=True)
    compare.add_argument("--results-dir", type=Path, default=ROOT / "results")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            count = write_dataset(args.output, args.seed)
            print(f"Geradas {count} vagas sintéticas em {args.output}")
            return 0
        if args.command == "runs":
            print(json.dumps(list_runs(args.results_dir, args.status, args.model,
                                       args.variant, args.split), ensure_ascii=False, indent=2))
            return 0
        if args.command == "compare":
            from .comparison import compare_runs
            result = compare_runs(args.results_dir, args.run_a, args.run_b, args.model,
                                  args.variant_a, args.variant_b)
            output = args.results_dir / f"comparison-{args.run_a}-{args.run_b}.json"
            atomic_write_text(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        rows = read_dataset(args.data)
        if args.command == "validate":
            print(json.dumps(validate_dataset(rows), ensure_ascii=False, indent=2))
            return 0
        if args.command == "replay":
            manifest_path = args.input.parent / "manifest.json"
            if manifest_path.exists() and load_manifest(args.input.parent).get("status") != "completed":
                raise ValueError("Replay e relatório final exigem um run concluído.")
            records = read_response_jsonl(args.input)
            replayed = replay_records(records, rows)
            summary = write_summary(replayed, args.input)
            report = args.input.with_suffix(".report.html")
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            summary_data = json.loads(summary.read_text(encoding="utf-8"))
            document = render_report(replayed, summary_data, args.input.name, timestamp)
            write_report(report, document)
            print(f"Respostas: {args.input}\nResumo: {summary}\nRelatório: {report}")
            return 0
        validate_dataset(rows)
        if args.resume:
            run_dir = args.results_dir / args.resume
            manifest = load_manifest(run_dir)
            run_split = manifest.get("split")
            rows = rows if run_split == "all" else [row for row in rows if row["split"] == run_split]
            if manifest.get("limit"):
                rows = rows[:manifest["limit"]]
            models = args.models or manifest.get("models", [])
            variants = args.variants or manifest.get("variants", [])
            if (manifest.get("dataset_sha256") != sha256_file(args.data)
                    or manifest.get("models") != list(models)
                    or manifest.get("variants") != list(variants)
                    or manifest.get("prompt_sha256") != prompt_hashes(variants)
                    or (args.split and manifest.get("split") != args.split)
                    or (args.limit is not None and manifest.get("limit") != args.limit)
                    or manifest.get("case_count") != len(rows)):
                raise ValueError("Dataset/configuração diferente do run original; retomada recusada.")
            existing = read_response_jsonl(run_dir / "responses.jsonl") if (run_dir / "responses.jsonl").exists() else []
        else:
            split = args.split or "dev"
            if split != "all":
                rows = [row for row in rows if row["split"] == split]
            if args.limit:
                rows = rows[:args.limit]
            models = args.models or MODELS
            variants = args.variants or list(PROMPTS)
            if args.limit is not None and args.limit < 1:
                raise ValueError("--limit deve ser maior que zero.")
            if len(models) != len(set(models)) or len(variants) != len(set(variants)):
                raise ValueError("Não repita valores em --model ou --variant.")
            run_dir, manifest = create_run(args.results_dir, args.data, models, variants,
                                           split, len(rows), args.limit)
            existing = []

        print(f"Run: {run_dir}", flush=True)

        def persist(current):
            content = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in current)
            atomic_write_text(run_dir / "responses.jsonl", content)

        def persist_models(model_manifest):
            manifest["model_manifest"] = model_manifest
            write_manifest(run_dir, manifest)

        try:
            records = run_evaluation(rows, models, variants, existing=existing, persist=persist,
                                     model_manifest_callback=persist_models,
                                     expected_model_manifest=manifest.get("model_manifest", {}))
            persist(records)
            expected = len(rows) * len(models) * len(variants)
            unique_keys = {(item["id"], item["model"], item["variant"]) for item in records}
            if len(unique_keys) != expected:
                manifest["status"] = "incomplete"
                raise ValueError(f"Run parcial: {len(unique_keys)} de {expected} respostas terminais.")
            if any(item.get("retryable_error") for item in records):
                manifest["status"] = "incomplete"
            else:
                manifest["status"] = "completed"
                manifest["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                manifest["model_manifest"] = {item["model"]: item["model_manifest"]
                                               for item in records if item.get("model_manifest")}
                replayed = replay_records(records, rows)
                summary_path = run_dir / "summary.json"
                atomic_write_text(summary_path, json.dumps(summarize(replayed), ensure_ascii=False, indent=2) + "\n")
                timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                write_report(run_dir / "report.html", render_report(replayed, json.loads(summary_path.read_text(encoding="utf-8")), manifest["run_id"], timestamp))
            write_manifest(run_dir, manifest)
        except KeyboardInterrupt:
            manifest["status"] = "interrupted"
            write_manifest(run_dir, manifest)
            raise
        except Exception:
            manifest["status"] = "incomplete"
            write_manifest(run_dir, manifest)
            raise
        if args.output:
            if manifest["status"] == "completed":
                write_results(records, args.output)
            else:
                atomic_write_text(args.output, "".join(json.dumps(item, ensure_ascii=False) + "\n"
                                                               for item in records))
        print(f"Status: {manifest['status']}")
        return 0
    except (OllamaUnavailable, OSError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
