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
- [x] Recalcular scores de respostas salvas com replay sem acessar/importar Ollama; gravar resumo atualizado sem alterar o JSONL de origem.
- [x] Gerar relatório HTML local e autocontido com agregados por variante/família, comparação pareada descritiva e resultados por caso.

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

## Verificações da execução anterior (antes do replay, 2026-09-26)

- [x] Suíte: `py -3.13 -m unittest discover -s tests -p "test_*.py" -v` — 14 testes passaram.
- [x] Dataset: `py -3.13 scripts/prompt_eval.py validate` — 150 registros, 100 `dev`, 50 `test`.
- [x] Smoke local: uma inferência `qwen3:4b/json_schema`, saída e resumo em `results/` (ignorados pelo Git).
- [x] Archify visual-check: HTML aprovado em 1440×900, 1600×1000, 1920×1080 e 2048×1320; sem overflow. Captura revisada; sidecars temporários removidos.
- [x] Privacidade e publicação: `AGENTS.md`, dados de origem privados e resultados locais ficaram fora do stage.

## Requisitos do AGENTS.md fora da primeira fatia

No corte inicial de replay, IDs/manifest, retomada, registro, comparação estatística e CI foram adiados. A implementação posterior está registrada em **Runtime auditável e CI**, abaixo. `AGENTS.md` é uma instrução local e permanece fora do stage/publicação.

## Verificações da fatia de replay e relatório (2026-09-26)

- [x] Suíte completa: `py -3.13 -m unittest discover -s tests -p "test_*.py" -v` — 21 testes passaram.
- [x] `py -3.13 scripts/prompt_eval.py validate` — 150 registros, 100 `dev` e 50 `test`.
- [x] Teste de replay via CLI com fixture sintética — resumo e HTML gerados sem importar Ollama; JSONL de origem inalterado.
- [x] Archify validate/deliver — 9 verificações, 0 erros e 0 avisos; SHA-256 do HTML entregue registrado na saída da execução local.
- [x] Archify visual-check — a inspeção automatizada inicial desta fatia expirou; na atualização runtime, o navegador passou em quatro viewports e a captura 1440×900 foi revisada.
## Critério de encerramento desta entrega

A fatia local de replay e relatório foi aceita após suas verificações específicas. A aceitação da camada de runtime aparece separadamente abaixo. Commit e publicação remota são etapas separadas; a avaliação via Hugging Face é opcional e não bloqueia o caminho Ollama local.

## Runtime auditável e CI — 2026-09-26

- [x] Criar runs em `results/<run_id>/` com manifest atômico, configuração, timestamps, versão do Python e hashes do dataset e prompts.
- [x] Persistir respostas por caso; retry limitado para falhas transitórias; retomar sem repetir respostas terminais e preservar histórico das tentativas.
- [x] Manter estados `running`, `incomplete`, `interrupted` e `completed`; apenas runs completos recebem resumo e relatório.
- [x] Indexar e filtrar manifests com SQLite local reconstruível.
- [x] Comparar dois runs compatíveis por casos pareados, delta e intervalo bootstrap determinístico, sem p-valores.
- [x] Adicionar CI Python 3.13 para unittest, validação do dataset e import/compile sem inferência.
- [x] Archify visual-check do diagrama runtime atualizado passou em quatro viewports sem overflow; captura desktop revisada.
- [x] Suíte local completa: 28 testes passaram; validação do dataset retornou 150 registros (100 dev, 50 test); compileall e `git diff --check` concluídos.
- [x] Smoke CLI de run e retomada com Ollama simulado; os artefatos de run foram criados e a resposta terminal não foi repetida.
- [x] Archify validate/deliver: 9/9 verificações, sem erros ou avisos; visual-check automatizado passou em quatro viewports.
- [ ] Inferência Ollama e benchmark dev/holdout completos não foram executados nesta atualização.
