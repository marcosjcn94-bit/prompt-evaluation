# Prompt Evaluation Lab

Laboratório local para comparar estratégias de prompting na extração de informações estruturadas de descrições sintéticas de vagas em português. Avalia qualidade de extração, formato, latência e alguns comportamentos diante de ataques sintéticos de prompt injection, com resultados reproduzíveis e artefatos auditáveis por execução.

**Problema.** Modelos de IA que extraem informações geram respostas diferentes a depender do texto de entrada. Avaliar a qualidade de extração, formato, latência e os riscos de diferentes prompts diante de ataques sintéticos de prompt injection, com resultados reproduzíveis e artefatos auditáveis por execução.

**Solução.** Desenvolvi um laboratório em Python para comparar cinco estratégias de prompt em 150 casos sintéticos — 100 de desenvolvimento e 50 reservados — com os modelos locais Qwen3 4B e Llama 3.2 3B via Ollama. Implementei métricas de formato e extração, casos de prompt injection em cinco famílias, persistência de execuções com manifest e hashes, retomada sem repetir respostas concluídas, replay offline, comparação pareada com bootstrap determinístico e relatório HTML autocontido.

**Impacto observado.** No conjunto reservado de 50 casos, a variante JSON Schema obteve 76% de tarefas completas e F1 de competências 0,753 com Qwen3; com Llama 3.2, 100% e 0,913, respectivamente. O Llama reproduziu um marcador sintético em 4 dos 4 casos reservados da família específica de exfiltração; o Qwen não o reproduziu nos 50 casos. Ambos tiveram 0% de acurácia exata no campo de título, conforme o critério adotado. Os resultados são descritivos e não demonstram desempenho em vagas reais, significância estatística ou segurança geral.

**Stack.** Python 3.13, Ollama, Qwen3 4B, Llama 3.2 3B, biblioteca padrão do Python, JSON/JSONL, SQLite, unittest e GitHub Actions.

## Arquitetura

<img width="5340" height="2320" alt="prompt-evaluation-lab-runtime" src="https://github.com/user-attachments/assets/188876bb-076e-4fa2-b773-5cc100d8c900" />

## FinOps: Custo R$ 0

- Custo de inferência do caminho padrão: zero em API; os modelos rodam localmente pelo Ollama / Nenhum serviço pago é necessário para repetir o benchmark local.

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
