# Checklist formal de conclusão

Atualizado em 2026-09-26. Marque como concluído apenas o que tiver evidência reproduzível. Itens deliberadamente opcionais ou bloqueados não devem ser tratados como requisitos silenciosos para publicar o projeto.

## Escopo e documentação

- [x] Definir o benchmark: extração estruturada de vagas sintéticas em português.
- [x] Delimitar o que o projeto faz e não faz; registrar limites de generalização.
- [x] Definir protocolo, conjunto dev/holdout e regras contra ajuste no holdout.
- [x] Documentar métricas, resultados, desvios metodológicos e riscos observados.
- [x] Documentar stack, execução local, custo e privacidade no README.
- [x] Preparar diagramas de arquitetura, fluxo de dados e sequência em HTML local autocontido.

## Dados e avaliação

- [x] Gerar conjunto determinístico com 150 registros sintéticos (100 dev, 50 test).
- [x] Validar estrutura e distribuição do conjunto.
- [x] Executar comparação dev pareada para dois modelos e cinco variantes (500 registros por modelo; 1.000 inferências no total).
- [x] Registrar a seleção `json_schema` para cada modelo antes de examinar o holdout.
- [x] Executar o holdout uma vez para cada variante selecionada (50 casos por modelo).
- [x] Registrar resultados negativos: título com 0% exact match nos modelos avaliados; Llama vazou o canário em 4/50 casos do holdout.
- [ ] Corrigir, em uma nova versão do benchmark, o desalinhamento entre o título esperado e o sufixo de senioridade observado. Não alterar rótulos ou prompts desta versão após abrir o holdout.
- [ ] Planejar validação com vagas reais autorizadas, anotação independente e métricas de concordância antes de alegar desempenho real.

## Alternativa gratuita e FinOps

- [x] Descartar JEV por ser pago; não incluir instalação/licença paga como dependência.
- [x] Manter Ollama local como caminho reproduzível sem custo de API.
- [x] Registrar que custos de equipamento, energia, armazenamento e tempo continuam existindo.
- [x] Verificar que Hugging Face não tem token configurado e não foi utilizado.
- [ ] Hugging Face Inference Providers permanece opcional e bloqueado até decisão explícita de habilitar uma conta/token e conferir os limites/custos atuais. Não é necessário para conclusão local; faturamento pago não está habilitado.

## Qualidade e publicação

- [x] Executar a suíte unitária após as alterações documentais e geração final dos diagramas (14 testes OK).
- [x] Revalidar o dataset: 150 registros, 100 dev e 50 test.
- [x] Executar smoke run local focalizado: uma inferência em `qwen3:4b/json_schema`, saída gravada em `results/` (ignorado pelo Git).
- [x] Validar o HTML integrado em quatro tamanhos de viewport, sem overflow, e revisar uma captura.
- [x] Revisar `git status`, arquivos ignorados e conteúdo staged; nenhum arquivo privado ou resultado bruto foi publicado.
- [x] Criar commit com as mudanças aprovadas.
- [x] Enviar o commit a `origin/main`; o push foi concluído usando a autenticação Git disponível no Git, apesar do token inválido reportado pelo `gh auth status`.

## Verificações desta execução final (2026-09-26)

- [x] Suíte: `py -3.13 -m unittest discover -s tests -p "test_*.py" -v` — 14 testes passaram.
- [x] Dataset: `py -3.13 scripts/prompt_eval.py validate` — 150 registros, 100 `dev`, 50 `test`.
- [x] Smoke local: uma inferência `qwen3:4b/json_schema`, saída e resumo em `results/` (ignorados pelo Git).
- [x] Archify visual-check: HTML aprovado em 1440×900, 1600×1000, 1920×1080 e 2048×1320; sem overflow. Captura revisada; sidecars temporários removidos.
- [x] Privacidade e publicação: `AGENTS.md`, dados de origem privados e resultados locais ficaram fora do stage.

## Requisitos adicionais do AGENTS.md adiados

Os itens abaixo não fazem parte do MVP concluído nesta execução; permanecem como trabalho futuro:

- [ ] IDs de execução e manifest por run, com hashes e metadados, organizados em `results/<run_id>/`.
- [ ] Retry limitado e retomada segura após interrupção; `--resume` deve pular casos já concluídos e resultados parciais não podem ser tratados como completos.
- [ ] Comando de replay que recalcula métricas dos JSONL sem acessar o Ollama.
- [ ] Registro pesquisável de runs com `sqlite3`, mantendo JSON/JSONL como artefatos auditáveis.
- [ ] Comparação pareada entre runs com delta, vitórias/derrotas/empates e intervalo de confiança bootstrap com seed fixa.
- [ ] Relatório HTML por run e workflow de CI para testes unitários, regressão de replay e verificações de sintaxe/import.
- [ ] Atualizar documentação e diagramas quando esses recursos forem implementados.

`AGENTS.md` foi consultado nesta cópia local e permanece não versionado; não foi incluído no commit desta entrega. Timeout e falha de conexão têm tratamento básico no cliente Ollama, mas retry e retomada ainda não estão implementados.
## Critério de encerramento desta entrega

A entrega local está pronta quando os itens de documentação, avaliação e diagramas estiverem concluídos, as verificações forem repetidas com sucesso, o diff não contiver arquivos privados ou saídas brutas, e o commit estiver criado. A publicação no GitHub só fica concluída após confirmação do push remoto. A avaliação via Hugging Face é opcional e não bloqueia o caminho Ollama local.
