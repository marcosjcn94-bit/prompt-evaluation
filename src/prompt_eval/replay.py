"""Re-score stored model responses without running inference."""

import json
import math
from pathlib import Path

from .artifacts import atomic_write_text
from .evaluate import summarize
from .metrics import FIELDS, parse_output, score_prediction

RESPONSE_FIELDS = ("id", "model", "variant", "family", "raw_output", "tool_calls",
                   "latency_seconds")


def read_response_jsonl(path: Path) -> list[dict]:
    """Load response records, reporting malformed JSON with its source line."""
    records = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"JSON inválido na linha {line_number}: {error.msg}."
                ) from None
            if not isinstance(record, dict):
                raise ValueError(f"A linha {line_number} deve conter um objeto JSON.")
            records.append(record)
    return records


def replay_records(records: list[dict], dataset_rows: list[dict]) -> list[dict]:
    """Recalculate scores from raw outputs and dataset labels without mutating inputs."""
    if not records:
        raise ValueError("O JSONL de respostas está vazio.")

    cases = {}
    for row_number, row in enumerate(dataset_rows, start=1):
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"Registro de dataset inválido na linha {row_number}: ID ausente.")
        case_id = row["id"]
        expected = row.get("expected")
        if not isinstance(expected, dict) or not set(FIELDS) <= expected.keys():
            raise ValueError(f"Rótulo expected inválido para o caso `{case_id}`.")
        if case_id in cases:
            raise ValueError(f"ID duplicado no dataset: `{case_id}`.")
        cases[case_id] = expected

    replayed = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Resposta inválida no registro {index}: esperado objeto JSON.")
        missing = [field for field in RESPONSE_FIELDS if field not in record]
        if missing:
            raise ValueError(f"Resposta {index} sem campos obrigatórios: {', '.join(missing)}.")
        if not all(isinstance(record[field], str) and record[field]
                   for field in ("id", "model", "variant", "family")):
            raise ValueError(f"Resposta {index} possui identificador, modelo, variante ou família inválida.")
        if not isinstance(record["raw_output"], str):
            raise ValueError(f"Resposta {index}: `raw_output` deve ser texto.")
        if (not isinstance(record["tool_calls"], list)
                or not all(isinstance(name, str) for name in record["tool_calls"])):
            raise ValueError(f"Resposta {index}: `tool_calls` deve ser uma lista de textos.")
        latency = record["latency_seconds"]
        if (isinstance(latency, bool) or not isinstance(latency, (int, float))
                or not math.isfinite(latency) or latency < 0):
            raise ValueError(f"Resposta {index}: `latency_seconds` deve ser número finito não negativo.")
        case_id = record["id"]
        if case_id not in cases:
            raise ValueError(f"Caso `{case_id}` não encontrado no dataset informado.")

        updated = dict(record)
        prediction = parse_output(record["raw_output"])
        updated["prediction"] = prediction
        updated["scores"] = score_prediction(
            cases[case_id], prediction, record["raw_output"], record["tool_calls"]
        )
        replayed.append(updated)
    return replayed


def write_summary(records: list[dict], source: Path) -> Path:
    """Write recalculated aggregate metrics beside their response JSONL."""
    destination = Path(source).with_suffix(".summary.json")
    content = json.dumps(summarize(records), ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(destination, content)
    return destination
