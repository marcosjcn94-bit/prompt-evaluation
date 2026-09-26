# Resultados do benchmark

## Escopo e reproducao

- Data de registro da selecao: 2026-09-26.
- Revisao do codigo avaliado: `6abb629eb643accce675a40503a1e53c58a8067c`.
- Dataset: sintetico, seed `20260925`, 100 casos `dev` e 50 casos reservados `test`.
- Execucao: Ollama local, CPU, sem GPU; sem inferencia por API externa.
- Modelo `qwen3:4b`, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
- Modelo `llama3.2:3b`, digest `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72`.
- Todos os tratamentos usaram temperatura 0 e seed `20260925`; os limites de geracao estao registrados nos JSONL locais.

Comandos da comparacao completa de desenvolvimento:

```powershell
py -3.13 scripts/prompt_eval.py run --split dev --model qwen3:4b --output results/dev-qwen3.jsonl
py -3.13 scripts/prompt_eval.py run --split dev --model llama3.2:3b --output results/dev-llama.jsonl
```

Os arquivos brutos e resumos estao em `results/` e sao ignorados pelo Git. Os JSONL registram o digest do modelo e o hash do prompt em cada inferencia.

## Resultados em dev

`Task complete` e `skills F1` sao medias em 100 casos. Vazamentos sao contagens em 100 casos. Latencia e a media por inferencia, em segundos. A execucao Qwen nao teve erros de geracao; o Llama teve tres erros `tool_call_limit`, todos em `tool_abuse` na variante `tool_instructions`.

| Modelo | Variante | JSON valido | Task complete | Skills F1 | Vazamentos de canario | Latencia (s) |
|---|---|---:|---:|---:|---:|---:|
| qwen3:4b | baseline | 0.00 | 0.00 | 0.000 | 6 | 49.6 |
| qwen3:4b | structured | 0.00 | 0.00 | 0.000 | 5 | 54.6 |
| qwen3:4b | few_shot | 0.00 | 0.00 | 0.000 | 0 | 48.1 |
| qwen3:4b | json_schema | 0.70 | 0.70 | 0.673 | 0 | 22.0 |
| qwen3:4b | tool_instructions | 0.00 | 0.00 | 0.000 | 0 | 43.0 |
| llama3.2:3b | baseline | 0.01 | 0.00 | 0.000 | 6 | 38.1 |
| llama3.2:3b | structured | 0.00 | 0.00 | 0.000 | 2 | 29.9 |
| llama3.2:3b | few_shot | 0.77 | 0.77 | 0.717 | 6 | 21.6 |
| llama3.2:3b | json_schema | 1.00 | 1.00 | 0.877 | 5 | 25.3 |
| llama3.2:3b | tool_instructions | 0.67 | 0.67 | 0.346 | 0 | 35.3 |

Foram verificados 500 registros e os mesmos 100 IDs por modelo, em cada uma das cinco variantes. As comparacoes pareadas usam `task_complete + skills_f1`, com sinais de seguranca como desempate; sao contagens descritivas, nao testes de significancia.

| Modelo | Comparacao json_schema vs. | Vitorias json_schema | Derrotas | Empates |
|---|---|---:|---:|---:|
| qwen3:4b | baseline | 70 | 0 | 30 |
| qwen3:4b | structured | 70 | 0 | 30 |
| qwen3:4b | few_shot | 70 | 0 | 30 |
| qwen3:4b | tool_instructions | 70 | 0 | 30 |
| llama3.2:3b | baseline | 100 | 0 | 0 |
| llama3.2:3b | structured | 100 | 0 | 0 |
| llama3.2:3b | few_shot | 24 | 5 | 71 |
| llama3.2:3b | tool_instructions | 68 | 13 | 19 |

## Selecao registrada antes de test

**Variante selecionada para `qwen3:4b`: `json_schema`.** Ela foi a unica variante com respostas JSON uteis e concluiu 70% das tarefas, com F1 de competencias 0.673 e nenhum vazamento de canario em `dev`. Em cada familia adversarial teve conclusao entre 50% e 100%; em casos comuns, 66%.

**Variante selecionada para `llama3.2:3b`: `json_schema`.** Teve 100% de JSON valido e conclusao, F1 0.877, e venceu 24 casos pareados contra `few_shot`, que venceu cinco; houve 71 empates. Tambem venceu 68 casos contra `tool_instructions`, que venceu 13, com 19 empates.

**Risco observado:** `llama3.2:3b` com `json_schema` vazou o canario em 5 dos 6 casos `canary_exfiltration` de `dev`. A variante foi mantida pela regra primaria de selecao e desempenho de extracao; esse resultado impede interpretar boa extracao como resistencia a injecao. No mesmo grupo, `few_shot` vazou em 6/6. A variante `tool_instructions` teve desempenho geral inferior e tres erros de limite de chamadas em `tool_abuse`.

As escolhas acima estao fixadas antes da execucao do holdout. Nenhuma observacao de `test` foi usada para escolher ou ajustar prompts.

## Avaliacao reservada

Executar uma vez, apenas para as variantes selecionadas:

```powershell
py -3.13 scripts/prompt_eval.py run --split test --model qwen3:4b --variant json_schema --output results/test-qwen3.jsonl
py -3.13 scripts/prompt_eval.py run --split test --model llama3.2:3b --variant json_schema --output results/test-llama.jsonl
```

Sao 50 inferencias por modelo. Os dois lotes terminaram com codigo de saida 0, 50 registros cada, os mesmos 50 IDs, uma variante por modelo, sem erros de geracao. Os digests conferem com os artefatos de `dev`.

| Modelo | JSON valido | Task complete | Skills F1 | Titulo (exact match) | Senioridade | Local | Contrato | Vazamentos | Latencia media (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3:4b | 0.76 | 0.76 | 0.753 | 0.00 | 0.76 | 0.76 | 0.54 | 0/50 | 21.0 |
| llama3.2:3b | 1.00 | 1.00 | 0.913 | 0.00 | 0.62 | 0.86 | 0.78 | 4/50 | 13.4 |

`Task complete` mede formato e preenchimento; nao significa que todos os campos estejam corretos. A acuracia exata do titulo foi 0 em `dev` e `test` para ambas as variantes selecionadas. Os rotulos esperados armazenam o titulo base e senioridade em campos separados, enquanto o texto da vaga traz o titulo junto de `(junior/pleno/senior)` e os modelos normalmente preservaram essa formulacao no campo `title`. Esta incompatibilidade entre exemplo, instrucao e rotulo torna a acuracia exata do titulo pouco informativa neste benchmark; nao alteramos os rotulos nem a metrica depois de abrir o holdout.

Resultados por familia no holdout:

| Modelo | Familia | n | Task complete | Skills F1 | Vazamentos de canario |
|---|---|---:|---:|---:|---:|
| qwen3:4b | common | 30 | 0.73 | 0.722 | 0/30 |
| qwen3:4b | canary_exfiltration | 4 | 1.00 | 1.000 | 0/4 |
| qwen3:4b | direct_override | 4 | 0.50 | 0.500 | 0/4 |
| qwen3:4b | instruction_obfuscation | 4 | 0.75 | 0.750 | 0/4 |
| qwen3:4b | role_impersonation | 4 | 1.00 | 1.000 | 0/4 |
| qwen3:4b | tool_abuse | 4 | 0.75 | 0.750 | 0/4 |
| llama3.2:3b | common | 30 | 1.00 | 0.989 | 0/30 |
| llama3.2:3b | canary_exfiltration | 4 | 1.00 | 1.000 | 4/4 |
| llama3.2:3b | direct_override | 4 | 1.00 | 0.000 | 0/4 |
| llama3.2:3b | instruction_obfuscation | 4 | 1.00 | 1.000 | 0/4 |
| llama3.2:3b | role_impersonation | 4 | 1.00 | 1.000 | 0/4 |
| llama3.2:3b | tool_abuse | 4 | 1.00 | 1.000 | 0/4 |

No Llama, os quatro vazamentos de `canary_exfiltration` ocorreram no campo `title`; os ataques diretos tambem obtiveram F1 de skills 0. Embora as cinco propriedades estivessem preenchidas nos 50 casos do Llama, a familia `direct_override` teve valores de skills incorretos. Isso ilustra por que completude isolada nao deve ser lida como qualidade de extracao.

Os arquivos `results/test-qwen3.jsonl`, `results/test-qwen3.summary.json`, `results/test-llama.jsonl` e `results/test-llama.summary.json` sao os artefatos brutos locais. Nao reexecutamos o holdout para escolher outra variante nem alteramos prompts com base nele.

**Status:** selecao pre-registrada e avaliacao `test` concluidas.

## Desvios e pendencias de metodo

A regra documentada pede inspecao das metricas por campo antes da selecao. A selecao foi registrada pelo criterio pareado de `task_complete + skills_f1`, mas a acuracia de cada campo nao foi conferida na etapa de selecao; a revisao posterior mostrou `title_accuracy = 0` em `dev` para ambas as variantes selecionadas. Nao trocamos as variantes apos observar `test`. Uma proxima versao deve esclarecer no prompt e no rotulo se o campo `title` inclui o sufixo de senioridade e deve fechar esse criterio antes de uma nova avaliacao reservada.

JEV foi descartado por ser pago e nao faz parte do protocolo nem dos requisitos de reproducao. A execucao e os resultados registrados vieram do Ollama local, sem custo de inferencia por API. A alternativa Hugging Face Inference Providers nao foi executada: nao ha `HF_TOKEN` configurado. Creditos gratuitos anunciados pelo provedor sao limitados e podem mudar; nenhum faturamento foi habilitado. Essa alternativa permanece opcional e nao e necessaria para reproduzir o benchmark local.

## Limites

O conjunto e sintetico e pequeno; as familias de ataque tem seis exemplos em `dev` e quatro em `test`. Os numeros descrevem somente estes modelos, prompts, parametros e exemplos. Nao demonstram desempenho em vagas reais, satisfacao de usuarios, significancia estatistica, reducao geral de alucinacao ou seguranca contra ataques fora das familias implementadas. A maquina executou em CPU e os tempos dependem do hardware local.
