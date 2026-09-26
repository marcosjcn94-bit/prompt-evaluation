$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$archify = Join-Path $repoRoot ".agents/skills/archify/bin/archify.mjs"
$artifactDir = Join-Path $repoRoot "results/archify"
$outputDir = Join-Path $repoRoot "docs/architecture"
$outputFile = Join-Path $outputDir "interactive.html"

if (-not (Test-Path -LiteralPath $archify)) {
    throw "Archify nao encontrado. Instale localmente: npx -y skills add tt-a1i/archify --skill archify --agent codex --copy --yes"
}

$diagrams = @(
    @{ id = "architecture"; label = "Arquitetura"; type = "architecture"; source = "docs/architecture/source/runtime.architecture.json"; file = "runtime.html" },
    @{ id = "dataflow"; label = "Fluxo de dados"; type = "dataflow"; source = "docs/architecture/source/data-flow.dataflow.json"; file = "data-flow.html" },
    @{ id = "sequence"; label = "Sequencia"; type = "sequence"; source = "docs/architecture/source/run-sequence.sequence.json"; file = "run-sequence.html" }
)

New-Item -ItemType Directory -Force -Path $artifactDir, $outputDir | Out-Null
foreach ($diagram in $diagrams) {
    $source = $diagram.source
    $target = "results/archify/$($diagram.file)"
    & node $archify deliver $diagram.type $source $target --quality showcase --json
    if ($LASTEXITCODE -ne 0) {
        throw "Archify falhou ao gerar o diagrama '$($diagram.id)'."
    }
}

$embedded = foreach ($diagram in $diagrams) {
    $bytes = [System.IO.File]::ReadAllBytes((Join-Path $artifactDir $diagram.file))
    [ordered]@{
        id = $diagram.id
        label = $diagram.label
        base64 = [Convert]::ToBase64String($bytes)
    }
}
$json = ConvertTo-Json -InputObject @($embedded) -Depth 4 -Compress

$html = @'
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prompt Evaluation Lab — Diagramas interativos</title>
  <style>
    :root { color-scheme: light; font-family: Segoe UI, Arial, sans-serif; color: #142326; background: #f4f7f6; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; }
    header { min-height: 66px; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; gap: 20px; background: #fff; border-bottom: 1px solid #d7e1df; }
    h1 { margin: 0; font-size: 18px; }
    .privacy { color: #52666a; font-size: 13px; }
    nav { min-height: 44px; display: flex; gap: 8px; padding: 7px 20px; background: #fff; border-bottom: 1px solid #d7e1df; }
    nav button { border: 1px solid #b9c9c6; border-radius: 7px; background: #fff; color: #234148; padding: 8px 15px; font-size: 14px; cursor: pointer; }
    nav button[aria-selected="true"] { color: #fff; background: #14665f; border-color: #14665f; }
    main { padding: 0 12px 12px; }
    iframe { display: block; width: 100%; height: calc(100vh - 132px); min-height: 620px; border: 0; background: #fff; }
    @media (max-width: 640px) { header { align-items: flex-start; flex-direction: column; gap: 5px; } nav { overflow-x: auto; } iframe { min-height: 680px; height: calc(100vh - 150px); } }
  </style>
</head>
<body>
  <header>
    <h1>Prompt Evaluation Lab — diagramas do sistema</h1>
    <span class="privacy">Diagramas locais autocontidos; nenhum dado é enviado por esta página.</span>
  </header>
  <nav role="tablist" aria-label="Diagramas">
    <button type="button" role="tab" aria-selected="true" data-index="0">Arquitetura</button>
    <button type="button" role="tab" aria-selected="false" data-index="1">Fluxo de dados</button>
    <button type="button" role="tab" aria-selected="false" data-index="2">Sequência</button>
  </nav>
  <main>
    <iframe id="diagram" title="Diagrama de arquitetura" sandbox="allow-scripts allow-same-origin"></iframe>
  </main>
  <script id="diagram-data" type="application/json">__DIAGRAM_DATA__</script>
  <script>
    const diagrams = JSON.parse(document.getElementById('diagram-data').textContent);
    const frame = document.getElementById('diagram');
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const decode = value => new TextDecoder().decode(Uint8Array.from(atob(value), c => c.charCodeAt(0)));
    function selectDiagram(index) {
      const diagram = diagrams[index];
      frame.title = `Diagrama: ${diagram.label}`;
      frame.srcdoc = decode(diagram.base64);
      tabs.forEach((tab, i) => tab.setAttribute('aria-selected', String(i === index)));
    }
    tabs.forEach(tab => tab.addEventListener('click', () => selectDiagram(Number(tab.dataset.index))));
    selectDiagram(0);
  </script>
</body>
</html>
'@

$html = $html.Replace("__DIAGRAM_DATA__", $json)
[System.IO.File]::WriteAllText($outputFile, $html, [System.Text.UTF8Encoding]::new($false))
Write-Output "HTML integrado: $outputFile"
