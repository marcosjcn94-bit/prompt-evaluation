"""Command line entry point. Dataset tasks work without a model service."""

import argparse
import json
import sys
from pathlib import Path

from .dataset import read_dataset, write_dataset
from .evaluate import MODELS, run_evaluation, write_results
from .ollama import OllamaUnavailable
from .prompts import PROMPTS

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
    run.add_argument("--split", choices=("dev", "test", "all"), default="dev")
    run.add_argument("--model", action="append", dest="models")
    run.add_argument("--variant", action="append", dest="variants")
    run.add_argument("--limit", type=int)
    run.add_argument("--output", type=Path, default=ROOT / "results" / "run.jsonl")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            count = write_dataset(args.output, args.seed)
            print(f"Geradas {count} vagas sintéticas em {args.output}")
            return 0
        rows = read_dataset(args.data)
        if args.command == "validate":
            print(json.dumps(validate_dataset(rows), ensure_ascii=False, indent=2))
            return 0
        validate_dataset(rows)
        if args.split != "all":
            rows = [row for row in rows if row["split"] == args.split]
        if args.limit:
            rows = rows[:args.limit]
        records = run_evaluation(rows, args.models or MODELS, args.variants or list(PROMPTS))
        summary = write_results(records, args.output)
        print(f"Resultados: {args.output}\nResumo: {summary}")
        return 0
    except (OllamaUnavailable, FileNotFoundError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
