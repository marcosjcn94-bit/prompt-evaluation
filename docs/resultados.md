# Resultados e aprendizados

## Escopo

O benchmark avaliou cinco estratégias de prompt em 150 descrições **sintéticas** em português: 100 casos de desenvolvimento e 50 casos reservados. Foram usados `qwen3:4b` e `llama3.2:3b`, localmente pelo Ollama, com temperatura zero. Cada modelo foi comparado nas mesmas entradas. A variante `json_schema` foi escolhida em desenvolvimento antes da abertura do conjunto reservado.

## Desenvolvimento: 100 casos por variante

`Conclusão` mede formato e preenchimento; F1 mede a sobreposição das competências extraídas. Vazamentos são contagens do canário sintético. Latência é a média por resposta, em segundos.

| Modelo | Estratégia | JSON válido | Conclusão | F1 competências | Vazamentos | Latência |
|---|---|---:|---:|---:|---:|---:|
| qwen3:4b | baseline | 0% | 0% | 0,000 | 6 | 49,6 s |
| qwen3:4b | structured | 0% | 0% | 0,000 | 5 | 54,6 s |
| qwen3:4b | few_shot | 0% | 0% | 0,000 | 0 | 48,1 s |
| qwen3:4b | json_schema | 70% | 70% | 0,673 | 0 | 22,0 s |
| qwen3:4b | tool_instructions | 0% | 0% | 0,000 | 0 | 43,0 s |
| llama3.2:3b | baseline | 1% | 0% | 0,000 | 6 | 38,1 s |
| llama3.2:3b | structured | 0% | 0% | 0,000 | 2 | 29,9 s |
| llama3.2:3b | few_shot | 77% | 77% | 0,717 | 6 | 21,6 s |
| llama3.2:3b | json_schema | 100% | 100% | 0,877 | 5 | 25,3 s |
| llama3.2:3b | tool_instructions | 67% | 67% | 0,346 | 0 | 35,3 s |

O `json_schema` venceu comparações pareadas do Qwen contra cada outra estratégia (70 vitórias, nenhuma derrota e 30 empates). Para o Llama, venceu `few_shot` em 24 casos, perdeu em 5 e empatou em 71; contra `tool_instructions`, venceu 68, perdeu 13 e empatou 19. O Llama teve três erros de limite de chamadas em casos de abuso de ferramenta com `tool_instructions`.

## Avaliação reservada: 50 casos por modelo

| Modelo (`json_schema`) | JSON válido | Conclusão | F1 competências | Título exato | Senioridade | Localidade | Contrato | Vazamentos | Latência |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3:4b | 76% | 76% | 0,753 | 0% | 76% | 76% | 54% | 0/50 | 21,0 s |
| llama3.2:3b | 100% | 100% | 0,913 | 0% | 62% | 86% | 78% | 4/50 | 13,4 s |

Nos 30 casos comuns, o Llama teve conclusão de 100% e F1 0,989; o Qwen teve 73% e 0,722. Nos quatro casos de cada família adversarial, o Qwen teve conclusão de 50% a 100% e nenhum vazamento. O Llama concluiu todos os casos de cada família; porém, vazou o canário nos quatro casos de `canary_exfiltration` e teve F1 zero em competências nos quatro casos de `direct_override`. Os quatro vazamentos ocorreram no campo de título.

## Insights e limites

- `json_schema` melhorou muito a produção de respostas utilizáveis neste experimento, mas completar campos não equivale a acertá-los.
- O melhor resultado de extração também pode carregar risco de segurança: o Llama teve maior F1 e menor latência no holdout, mas vazou o canário em 4/4 casos específicos; o Qwen não vazou nesse conjunto pequeno, mas concluiu menos tarefas.
- A métrica de título exato ficou em 0% para ambos. Os rótulos separam título e senioridade, enquanto os modelos costumaram devolver o título com o nível junto. O critério precisa ser esclarecido numa versão futura, sem reinterpretar este holdout.
- Há apenas quatro exemplos reservados por família de ataque. Os resultados são descritivos, não demonstram significância estatística, segurança geral ou desempenho em vagas reais.
- O benchmark completo documentado foi executado em CPU local. Os tempos dependem do equipamento; não houve custo de inferência por API. A nova camada de runs teve testes e smoke test com Ollama simulado, mas não foi submetida a um novo benchmark completo.

## Reprodutibilidade e fontes

As medições detalhadas, parâmetros, comparações e desvios de método estão em [benchmark-results.md](benchmark-results.md). Os arquivos brutos locais estão em `results/` e são ignorados pelo Git. Os resultados se referem ao código avaliado na revisão `6abb629`; as mudanças posteriores de auditoria, retomada e relatórios foram verificadas separadamente por testes, sem nova medição de desempenho.
