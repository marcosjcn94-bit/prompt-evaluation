# Prompt Evaluation Lab

O Prompt Evaluation Lab compara cinco estratégias de prompt para extrair campos estruturados de descrições sintéticas de vagas em português. Ele executa avaliações pareadas com dois modelos locais do Ollama, mede qualidade de extração, formato, latência e respostas a ataques sintéticos de prompt injection, e mantém resultados auditáveis em arquivos locais.

O projeto é uma bancada experimental e educativa: não analisa vagas reais, não recomenda candidatos, não toma decisões de contratação e não comprova desempenho em produção. O conjunto é sintético e pequeno; `task_complete` mede formato e preenchimento, não correção semântica. Os resultados não demonstram qualidade em dados reais, significância estatística, redução geral de alucinações nem proteção contra ataques fora das famílias testadas.

**Problema.** Pequenas mudanças na forma de pedir uma tarefa podem alterar muito o resultado de uma IA. Sem uma comparação justa, é difícil saber qual abordagem funciona melhor e quais riscos ela traz.

**Solução.** Criamos um laboratório que compara cinco formas de orientar a IA usando os mesmos exemplos, dois modelos locais e uma etapa final de avaliação reservada. Cada execução guarda evidências para consulta e repetição.

**Impacto observado.** Nos 50 exemplos reservados, um modelo preencheu todos os registros, mas revelou o sinal confidencial de teste em 4 casos; o outro não teve vazamentos, mas concluiu 38 tarefas. Os dois erraram o título conforme o critério exato usado. O estudo mostra que preencher mais campos não garante respostas corretas nem seguras; os números valem apenas para este conjunto sintético.

**Stack.** Python 3.13, Ollama executado no próprio computador e arquivos locais para dados e evidências. O projeto não exige serviços pagos nem envia exemplos a uma API externa; testes automatizados e relatórios ajudam a conferir os resultados.

## Arquitetura

A CLI gera e valida o conjunto local, ou envia casos ao Ollama em `localhost`. Cada avaliação cria `results/<run_id>/` com manifest, respostas JSONL e, quando completa, resumo JSON e relatório HTML. Respostas e manifest são atualizados atomicamente. `replay` continua aceitando JSONL legado e recalcula scores offline.

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
py -3.13 scripts/prompt_eval.py run --split dev --model qwen3:4b
py -3.13 scripts/prompt_eval.py run --split dev --model llama3.2:3b
```

A escolha de variantes deve usar somente `dev` e ser registrada antes do holdout. Neste estudo, `json_schema` foi pré-selecionada para ambos. A avaliação reservada executa 100 inferências no total (50 por modelo):

```powershell
py -3.13 scripts/prompt_eval.py run --split test --model qwen3:4b --variant json_schema
py -3.13 scripts/prompt_eval.py run --split test --model llama3.2:3b --variant json_schema
```

Não use o holdout para ajustar prompts ou escolher uma nova variante. Consulte o [resumo dos resultados e aprendizados](docs/resultados.md), os [resultados detalhados](docs/benchmark-results.md), o [protocolo de experimentos](docs/experiment-design.md), as [métricas](docs/metrics.md) e o [guia de anotação](docs/annotation-guidelines.md). O checklist de encerramento está em [docs/checklist-conclusao.md](docs/checklist-conclusao.md).

## Replay e relatório HTML

Cada `run` tenta novamente até três vezes falhas transitórias de conexão, timeout e HTTP 5xx, com esperas de 1 e 2 segundos. Respostas malformadas são pontuadas sem nova tentativa. Se restarem falhas transitórias, o run fica `incomplete`. Retome usando o ID mostrado pelo comando; casos com resposta terminal não são repetidos:

```powershell
py -3.13 scripts/prompt_eval.py run --resume <run_id>
py -3.13 scripts/prompt_eval.py runs list --status completed
```

Para comparar duas execuções completas e pareadas, use os respectivos IDs, modelo e variantes. O JSON de comparação inclui delta B−A e intervalo bootstrap percentile pareado de 95% (2.000 amostragens, seed fixa); é descritivo e não calcula p-valor:

```powershell
py -3.13 scripts/prompt_eval.py compare --run-a <id_a> --run-b <id_b> --model qwen3:4b --variant-a json_schema --variant-b json_schema
```

Para manter integração com scripts antigos, `--output <arquivo.jsonl>` grava um espelho legado além dos artefatos da execução.

O replay legado continua disponível sem repetir inferências:

```powershell
py -3.13 scripts/prompt_eval.py replay --input results/test-qwen3.jsonl
```

O comando usa `data/jobs.jsonl` por padrão. Para outro conjunto compatível, informe `--data <caminho.jsonl>`. Com `results/test-qwen3.jsonl`, o replay produz resumo e relatório HTML junto ao arquivo; o JSONL original permanece intacto. Abra o HTML diretamente no navegador: ele não usa servidor, JavaScript nem recursos externos.

O registro SQLite é um índice local reconstruível a partir dos manifests; JSON e JSONL seguem como evidência principal. Relatórios de runs são gerados somente depois de todas as respostas terminais. A avaliação continua limitada ao dataset sintético e não demonstra desempenho em vagas reais.

## Testes e privacidade

Execute a suíte com `py -3.13 -m unittest discover -s tests -p "test_*.py" -v`. O GitHub Actions também executa testes, replay e verificações de sintaxe/import sem Ollama ou download de modelos. `diretriz.md` e `vaga-REX.md` são arquivos privados ignorados pelo Git. O dataset do benchmark é sintético e não contém conteúdo desses arquivos. Antes de publicar, revise `git status --ignored` e confira os arquivos staged.
