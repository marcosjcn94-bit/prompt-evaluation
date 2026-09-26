# Prompt Evaluation Lab

O Prompt Evaluation Lab compara cinco estratégias de prompt para extrair campos estruturados de descrições sintéticas de vagas em português. Ele executa avaliações pareadas com dois modelos locais do Ollama, mede qualidade de extração, formato, latência e respostas a ataques sintéticos de prompt injection, e mantém resultados auditáveis em arquivos locais.

O projeto é uma bancada experimental e educativa: não analisa vagas reais, não recomenda candidatos, não toma decisões de contratação e não comprova desempenho em produção. O conjunto é sintético e pequeno; `task_complete` mede formato e preenchimento, não correção semântica. Os resultados não demonstram qualidade em dados reais, significância estatística, redução geral de alucinações nem proteção contra ataques fora das famílias testadas.

**Problema.** Comparar prompts sem misturar diferenças de dados, modelo ou protocolo torna difícil saber se uma mudança realmente melhorou a extração.

**Solução.** Um benchmark determinístico compara as mesmas entradas entre cinco variantes de prompt, separa desenvolvimento de holdout e registra métricas e metadados por execução.

**Impacto observado.** No holdout reservado, `qwen3:4b` com `json_schema` concluiu 76% das tarefas e teve F1 de competências 0,753; `llama3.2:3b` concluiu 100% e teve F1 0,913, mas vazou o canário sintético em 4 de 50 casos. A acurácia exata do título foi 0% para ambos. Esses números se aplicam somente aos exemplos e configurações deste benchmark.

**Stack.** Python 3.13 e biblioteca padrão; Ollama local para inferência; JSONL/JSON para dados e resultados; unittest para testes; PowerShell e Node.js/Archify para gerar os diagramas HTML autocontidos.

## Arquitetura

A CLI gera e valida o conjunto local, ou envia casos ao Ollama em `localhost`. O avaliador aplica prompts, calcula métricas de forma determinística e grava JSONL e resumos em `results/`, diretório ignorado pelo Git. Não há API hospedada no caminho padrão.

O arquivo [diagramas interativos](docs/architecture/interactive.html) reúne arquitetura, fluxo de dados e sequência de execução. A prévia está em [architecture-preview.png](docs/architecture/architecture-preview.png), e as fontes Archify ficam em `docs/architecture/source/`.

## FinOps

- Custo de inferência do caminho padrão: zero em API; os modelos rodam localmente pelo Ollama. O custo real é o equipamento, energia, espaço em disco e tempo de execução.
- O download dos modelos exige espaço local; execução em CPU pode ser lenta.
- JEV foi descartado por ser pago. Nenhum serviço pago é necessário para repetir o benchmark local.
- A alternativa Hugging Face Inference Providers não foi usada: não há `HF_TOKEN` configurado e os créditos gratuitos anunciados pelo provedor são limitados e sujeitos a alteração. O projeto não configura faturamento nem depende dessa alternativa.
- Os resultados brutos ficam locais e são ignorados pelo Git, reduzindo publicação acidental de dados de execução.

## Como rodar localmente

Requisitos: Windows com PowerShell, Python 3.13 (ou versão compatível) e, para inferência, Ollama instalado. Não há dependências Python de terceiros.

```powershell
# Na raiz do repositório
py -3.13 scripts/prompt_eval.py generate
py -3.13 scripts/prompt_eval.py validate

# Instale os modelos uma vez; eles ocupam espaço em disco
ollama pull qwen3:4b
ollama pull llama3.2:3b

# Smoke run local com dois casos
py -3.13 scripts/prompt_eval.py run --split dev --limit 2
```

Para rodar a comparação completa de desenvolvimento, execute os comandos abaixo. São 1.000 inferências (100 casos × 5 prompts × 2 modelos):

```powershell
py -3.13 scripts/prompt_eval.py run --split dev --model qwen3:4b --output results/dev-qwen3.jsonl
py -3.13 scripts/prompt_eval.py run --split dev --model llama3.2:3b --output results/dev-llama.jsonl
```

A escolha de variantes deve usar somente `dev` e ser registrada antes do holdout. Neste estudo, `json_schema` foi pré-selecionada para ambos. A avaliação reservada executa 100 inferências no total (50 por modelo):

```powershell
py -3.13 scripts/prompt_eval.py run --split test --model qwen3:4b --variant json_schema --output results/test-qwen3.jsonl
py -3.13 scripts/prompt_eval.py run --split test --model llama3.2:3b --variant json_schema --output results/test-llama.jsonl
```

Não use o holdout para ajustar prompts ou escolher uma nova variante. Consulte [protocolo de experimentos](docs/experiment-design.md), [métricas](docs/metrics.md), [guia de anotação](docs/annotation-guidelines.md) e [resultados detalhados](docs/benchmark-results.md). O checklist de encerramento está em [docs/checklist-conclusao.md](docs/checklist-conclusao.md).

## Testes e privacidade

Execute a suíte com `py -3.13 -m unittest discover -s tests -p "test_*.py" -v`. `diretriz.md` e `vaga-REX.md` são arquivos privados ignorados pelo Git. O dataset do benchmark é sintético e não contém conteúdo desses arquivos. Antes de publicar, revise `git status --ignored` e confira os arquivos staged.
