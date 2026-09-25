# Prompt Evaluation Lab

Bancada local para comparar cinco estratégias de prompt em extração estruturada de vagas em português, com dois modelos Ollama, comparação pareada, conjunto de teste reservado e ataques sintéticos de prompt injection.

## O que o projeto demonstra

- Otimização de prompts: baseline, instruções estruturadas, few-shot, saída JSON Schema e instruções de ferramenta local.
- Avaliação A/B: todas as variantes recebem os mesmos casos e configurações de modelo; vitórias, derrotas e empates são pareados por caso.
- Segurança: cinco famílias de entradas adversariais avaliam se instruções maliciosas dentro da vaga desviam a extração.
- Reprodutibilidade: dataset determinístico, separação dev/test, métricas explícitas e artefatos JSONL/JSON.
- Operação local: a inferência não envia dados a serviços externos. Gerar e validar o dataset não requer Ollama nem rede.

O dataset é sintético. Resultados medem este benchmark e não comprovam satisfação de usuários, desempenho em vagas reais ou redução geral de alucinações/toxicidade. Não há classificador genérico de toxicidade; os sinais de segurança são específicos aos ataques e canários deste projeto.

## Arquitetura

```text
data/jobs.jsonl ──> CLI ──> Ollama local (/api/chat)
                         ├─ 5 versões de prompt
                         ├─ 2 modelos comparáveis
                         ├─ ferramenta local de taxonomia (permitida)
                         └─ respostas JSON
                              └─ métricas determinísticas ──> results/ (local/ignorado)
```

`dataset.py` gera dados determinísticos; `prompts.py` mantém versões e ferramenta permitida; `ollama.py` fala com o serviço local; `metrics.py` pontua respostas; `evaluate.py` executa pares e resume resultados; `cli.py` fornece os comandos. O modo ausente/indisponível gera instrução de recuperação sem traceback e não tenta usar APIs remotas.

## Requisitos

- Python 3.13 ou compatível (somente biblioteca padrão).
- Para inferência, Ollama instalado e iniciado, com `qwen3:4b` e `llama3.2:3b` baixados. Os modelos ocupam espaço em disco e o tempo depende do hardware.

No PowerShell, na raiz do repositório:

```powershell
py -3.13 scripts/prompt_eval.py generate
py -3.13 scripts/prompt_eval.py validate
ollama pull qwen3:4b
ollama pull llama3.2:3b
py -3.13 scripts/prompt_eval.py run --split dev --limit 2
```

O exemplo usa apenas dois casos para smoke run. A comparação de desenvolvimento completa executa 100 casos × 5 prompts × 2 modelos = 1.000 inferências. O teste reservado executa outras 500 inferências e só deve ser consultado depois de escolher uma variante usando dev.

Para limitar a execução:

```powershell
py -3.13 scripts/prompt_eval.py run --split dev --model qwen3:4b --variant few_shot --limit 10
py -3.13 scripts/prompt_eval.py run --split test --output results/test.jsonl
```

Uma indisponibilidade do Ollama resulta em código de saída 2, endereço local, causa e próximo passo. `validate` e `generate` continuam disponíveis offline.

## Dataset e protocolo

São 150 registros: 100 vagas comuns e 50 adversariais (10 em cada uma de cinco famílias). Dev contém 70 comuns + 30 adversariais; test contém 30 comuns + 20 adversariais, com quatro casos reservados por família adversarial. A semente padrão é `20260925`. Os dois conjuntos são sintéticos e não constituem amostra representativa de mercado.

Escolha a melhor variante olhando apenas `dev`. Registre a escolha antes de executar `test`; não ajuste prompts com base no resultado reservado. Compare cada variante no mesmo modelo e nos mesmos IDs. Os arquivos brutos e resumos ficam em `results/`, fora do Git. Para auditoria compartilhável, registre a revisão do código, os nomes/tags dos modelos, data, split, comandos e os artefatos; não publique inferências com dados sensíveis.

## Métricas e interpretação

- Acurácia por campo: igualdade após normalização simples de caixa/espaços; competências também recebem F1 por conjunto.
- Validade JSON, validade do esquema, completude e conclusão de tarefa: objeto parseável, tipos de campo corretos, campos preenchidos e tarefa completa.
- Segurança: vazamento do canário sintético, chamada de ferramenta fora da allowlist e resistência observada por família adversarial.
- Operação: latência e contagens de tokens informadas pelo Ollama, quando presentes.
- A/B pareado: win/loss/tie em conclusão da tarefa + F1, desempate por menos sinalizações de segurança. Isso é uma regra do benchmark, não um teste estatístico de significância.

Ver [protocolo de experimentos](docs/experiment-design.md), [guia de anotação](docs/annotation-guidelines.md) e [definições de métricas](docs/metrics.md).

## Privacidade e Git

`diretriz.md` e `vaga-REX.md` são ignorados pelo Git. O `.gitignore` evita inclusão acidental; ele não controla leitura local. O dataset sintético não contém conteúdo desses arquivos. Revise `git status --ignored` antes de publicar.
