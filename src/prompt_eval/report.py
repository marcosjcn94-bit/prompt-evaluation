"""Standalone HTML report for a replayed prompt evaluation."""

import html
import math
from pathlib import Path

from .artifacts import atomic_write_text


def _escape(value) -> str:
    return html.escape(str(value), quote=True)


def _rate(value, digits=1) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.{digits}f}%".replace(".", ",")


def _number(value, digits=2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def _bar(value) -> str:
    number = float(value or 0)
    width = min(100.0, max(0.0, number * 100)) if math.isfinite(number) else 0.0
    return f'<span class="bar"><span style="width:{width:.1f}%"></span></span>'


def _metric(group, name):
    return group.get("metrics", {}).get(name)


def _mean(records, name):
    values = [record.get("scores", {}).get(name) for record in records]
    values = [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]
    return sum(values) / len(values) if values else None


def _mean_latency(records):
    values = [row.get("latency_seconds") for row in records]
    values = [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]
    return sum(values) / len(values) if values else None


def _metric_row(group):
    model = _escape(group.get("model", ""))
    variant = _escape(group.get("variant", ""))
    return (
        f"<tr><th scope=\"row\">{model} / {variant}</th>"
        f"<td>{group.get('n', 0)}</td>"
        f"<td>{_rate(_metric(group, 'json_valid'))}</td>"
        f"<td>{_rate(_metric(group, 'task_complete'))}</td>"
        f"<td>{_number(_metric(group, 'skills_f1'), 3)}"
        f"{_bar(_metric(group, 'skills_f1'))}</td>"
        f"<td>{round((_metric(group, 'canary_leak') or 0) * group.get('n', 0))}</td>"
        f"<td>{_number(_metric(group, 'latency_seconds'), 1)} s</td></tr>"
    )


def render_report(records: list[dict], summary: dict, source_name: str,
                  generated_at: str) -> str:
    """Render a complete report; dynamic content is escaped and raw inputs omitted."""
    total = len(records)
    cards = [
        ("Registros", str(total), "respostas avaliadas"),
        ("JSON válido", _rate(_mean(records, "json_valid")), "formato da resposta"),
        ("Tarefa completa", _rate(_mean(records, "task_complete")), "formato e preenchimento"),
        ("F1 de competências", _number(_mean(records, "skills_f1"), 3), "média por caso"),
        ("Latência média", f"{_number(_mean_latency(records), 1)} s", "por inferência"),
    ]
    card_markup = "\n".join(
        f'<article class="card"><span>{_escape(label)}</span>'
        f'<strong>{_escape(value)}</strong><small>{_escape(note)}</small></article>'
        for label, value, note in cards
    )

    overall = [group for group in summary.get("groups", []) if group.get("family") == "all"]
    overall_rows = "\n".join(_metric_row(group) for group in overall)
    paired_rows = "\n".join(
        "<tr>"
        f"<th scope=\"row\">{_escape(item.get('model', ''))}</th>"
        f"<td>{_escape(item.get('a', ''))} × {_escape(item.get('b', ''))}</td>"
        f"<td>{item.get('a_wins', 0)}</td><td>{item.get('b_wins', 0)}</td>"
        f"<td>{item.get('ties', 0)}</td>"
        f"<td>{_rate(item.get('a_win_rate_excluding_ties'))}</td></tr>"
        for item in summary.get("paired_comparisons", [])
    )
    family_groups = [group for group in summary.get("groups", []) if group.get("family") != "all"]
    family_rows = "\n".join(
        "<tr>"
        f"<td>{_escape(group.get('model', ''))}</td>"
        f"<td>{_escape(group.get('variant', ''))}</td>"
        f"<th scope=\"row\">{_escape(group.get('family', ''))}</th>"
        f"<td>{group.get('n', 0)}</td>"
        f"<td>{_rate(_metric(group, 'task_complete'))}</td>"
        f"<td>{_number(_metric(group, 'skills_f1'), 3)}</td>"
        f"<td>{round((_metric(group, 'canary_leak') or 0) * group.get('n', 0))}</td>"
        f"<td>{round((_metric(group, 'unauthorized_tool_call') or 0) * group.get('n', 0))}</td>"
        f"</tr>"
        for group in family_groups
    )
    case_rows = "\n".join(
        "<tr>"
        f"<th scope=\"row\">{_escape(record.get('id', ''))}</th>"
        f"<td>{_escape(record.get('model', ''))}</td>"
        f"<td>{_escape(record.get('variant', ''))}</td>"
        f"<td>{_escape(record.get('family', ''))}</td>"
        f"<td>{_rate(record.get('scores', {}).get('json_valid'))}</td>"
        f"<td>{_rate(record.get('scores', {}).get('task_complete'))}</td>"
        f"<td>{_number(record.get('scores', {}).get('skills_f1'), 3)}</td>"
        f"<td>{_number(record.get('latency_seconds'), 1)} s</td>"
        f"<td>{_escape(record.get('generation_error') or '—')}</td></tr>"
        for record in records
    )

    return f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatório — {_escape(source_name)}</title>
  <style>
    :root {{ color-scheme: light; --ink:#172438; --muted:#5e6c80; --paper:#f3f6fa;
      --card:#fff; --line:#dce4ee; --blue:#2359d1; --teal:#0b806f; --rose:#b33c58; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font:15px/1.55 system-ui,
      -apple-system,"Segoe UI",sans-serif; }}
    main {{ width:min(1440px,100%); margin:auto; padding:32px clamp(16px,4vw,56px) 64px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-end;
      border-bottom:1px solid var(--line); padding:12px 0 28px; }}
    .eyebrow {{ color:var(--blue); font-size:.75rem; font-weight:800; letter-spacing:.14em;
      text-transform:uppercase; }}
    h1 {{ margin:6px 0 2px; font-size:clamp(1.8rem,4vw,3rem); line-height:1.1; }}
    h2 {{ margin:0 0 16px; font-size:1.15rem; }}
    p, small, .muted {{ color:var(--muted); }}
    .meta {{ text-align:right; font-size:.85rem; }}
    .meta strong {{ color:var(--ink); display:block; overflow-wrap:anywhere; }}
    .cards {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px;
      margin:22px 0 30px; }}
    .card, section {{ background:var(--card); border:1px solid var(--line); border-radius:14px; }}
    .card {{ padding:18px; min-height:136px; display:flex; flex-direction:column; }}
    .card span {{ color:var(--muted); font-size:.82rem; }}
    .card strong {{ font-size:1.7rem; line-height:1.3; margin:8px 0 2px; }}
    .card small {{ margin-top:auto; }}
    section {{ padding:22px; margin:16px 0; }}
    .table-wrap {{ overflow-x:auto; }}
    table {{ border-collapse:collapse; width:100%; min-width:680px; font-size:.87rem; }}
    th,td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); }}
    thead th {{ color:var(--muted); font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; }}
    tbody tr:last-child th,tbody tr:last-child td {{ border-bottom:0; }}
    .bar {{ display:inline-block; width:68px; height:7px; margin-left:7px; background:#e5eaf2;
      border-radius:8px; vertical-align:middle; overflow:hidden; }}
    .bar span {{ display:block; height:100%; background:var(--teal); border-radius:8px; }}
    .note {{ border-left:4px solid var(--blue); padding:14px 16px; background:#edf3ff;
      border-radius:0 10px 10px 0; }}
    .danger {{ color:var(--rose); }}
    footer {{ padding:18px 2px; color:var(--muted); font-size:.82rem; }}
    @media(max-width:900px) {{ .cards {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
    @media(max-width:620px) {{ main {{ padding:18px 14px 40px; }} header {{ display:block; }}
      .meta {{ text-align:left; margin-top:16px; }} .cards {{ grid-template-columns:1fr 1fr; }}
      .card {{ min-height:118px; padding:14px; }} section {{ padding:16px; }} }}
    @media(max-width:360px) {{ .cards {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body><main>
  <header><div><div class="eyebrow">Prompt Evaluation Lab</div>
    <h1>Resumo da execução</h1><p>Replay das respostas armazenadas, sem nova inferência.</p></div>
    <div class="meta"><span>Arquivo de respostas</span><strong>{_escape(source_name)}</strong>
      <span>Gerado em {_escape(generated_at)}</span></div>
  </header>
  <div class="cards">{card_markup}</div>
  <section><h2>Comparação por modelo e variante</h2><div class="table-wrap"><table>
    <thead><tr><th>Modelo / variante</th><th>n</th><th>JSON válido</th><th>Tarefa completa</th>
      <th>F1 competências</th><th>Vazamentos</th><th>Latência média</th></tr></thead>
    <tbody>{overall_rows}</tbody></table></div></section>
  <section><h2>Comparações pareadas</h2><p>Vitórias, derrotas e empates por caso compartilhado.</p>
    <div class="table-wrap"><table><thead><tr><th>Modelo</th><th>Variantes</th><th>Vitórias A</th>
      <th>Vitórias B</th><th>Empates</th><th>Taxa A sem empates</th></tr></thead>
      <tbody>{paired_rows}</tbody></table></div></section>
  <section><h2>Resultados por família</h2><div class="table-wrap"><table><thead><tr>
    <th>Modelo</th><th>Variante</th><th>Família</th><th>n</th><th>Tarefa completa</th>
    <th>F1 competências</th><th>Vazamentos de canário</th><th>Chamadas não autorizadas</th>
    </tr></thead><tbody>{family_rows}</tbody></table></div></section>
  <section><h2>Casos avaliados</h2><div class="table-wrap"><table><thead><tr><th>ID</th>
    <th>Modelo</th><th>Variante</th><th>Família</th><th>JSON válido</th><th>Tarefa completa</th>
    <th>F1 competências</th><th>Latência</th><th>Erro</th></tr></thead>
    <tbody>{case_rows}</tbody></table></div></section>
  <section class="note"><strong>Como interpretar</strong><p>Este conjunto é sintético e pequeno.
    As comparações são descritivas; não demonstram significância estatística, causalidade,
    desempenho em vagas reais nem generalização para outros modelos ou ataques. “Tarefa completa”
    mede formato e preenchimento, não a correção semântica de todos os campos.</p></section>
  <footer>Relatório local. As respostas brutas e o texto integral das vagas não são exibidos.</footer>
</main></body></html>
'''


def write_report(path: Path, document: str) -> Path:
    """Persist a standalone report atomically."""
    destination = Path(path)
    atomic_write_text(destination, document)
    return destination
