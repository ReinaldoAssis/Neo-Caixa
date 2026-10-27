# Otimização da automação Cloudfy

Data: 2026-10-27 · Branch: `master`

## Objetivo

Derrubar o custo por rodada da automação Cloudfy (hoje ~36-40s por importação)
reutilizando uma sessão de navegador entre rodadas, removendo sleeps fixos e
permitindo importar T1+T2 numa só passada.

## Decisões (grilling 2026-10-27)

| Tema | Decisão |
| --- | --- |
| Escopo da sessão | Toda automação Cloudfy (listar, importar, lançar, descontos) |
| Ciclo de vida | Boot → quit do app; recria/relogin 1x se cair |
| Config | Toggle único `otimizar_automacao`, default **ON**, em ConfigPosto > Automação Cloudfy; vale posto+restaurante; OFF = comportamento antigo |
| Debug | `cloudfy_debug` continua: janela visível (inclusive no warm de boot) |
| Warm | Boot: login + conciliador pronto, headless; falha silenciosa com status; reaquece ao salvar credenciais |
| Janela no lançar | Relaunch headed com `storage_state` (sem login); fallback chrome→chromium; senão erro |
| Pós-lançamento | Janela fica aberta até o usuário fechar ou clicar "Fechar navegador" |
| Esperas | Só sinal de dado (DOM/URL, `wait_for_function`, `expect_page`, `expect_download`); zero `wait_for_timeout` |
| Extras | Tabela em 1 `page.evaluate`, `expect_page` no lugar de poll, assets bloqueados no headless, timing por etapa + `/automacao/status` |
| Multi-import | Seleção múltipla na tabela; T1→turno 1, T2→turno 2; mesmo turno soma; split arma com fechamento do T1 |
| Turno do caixa | Coluna `turno`, fallback `movto` (T1/T2) |
| Falha no lote | Continua e reporta por caixa; aborta só se a sessão cair (relogin + retry 1x) |
| Identidade | Chave estável (data/pdv/turno/movto) em vez de índice |
| Lançar multi | Só 1 caixa no modo lançar |
| Data divergente | Bloqueia caixa fora da data do formulário (import e lançar) |
| Lista | Cache do front como hoje (só "Atualizar lista" relê) |
| Seleção | Checkbox + atalho "Selecionar T1+T2 de `<data>`" |
| Concorrência | Mutex no backend; 2º pedido = 409 "Automação ocupada" |
| Cookies | Session state só em RAM |
| Só T2 | Erro "selecione o T1" quando o split não está armado |
| Progresso | Spinner + resumo por caixa (tempo/erro) no fim |
| Metas | listar ≤2s · import ≤4s · lote T1+T2 ≤7s · lançar até janela pronta ≤8s |
| Commits | 1 commit |
| Validação | Testes mock agora; smoke real quando houver credenciais |

## Arquitetura

```
FastAPI (thread) ──> automacao_sessao.SESSAO (singleton)
                         │ threading.Lock (mutex)
                         │ thread "automacao-loop" + loop asyncio persistente
                         └── playwright: pw, browser, context, page
```

- `automacao_sessao.py`: dono do browser. Estados `off | warming | ready |
  headed | error`. `run_coroutine_threadsafe` para conversar com o loop.
- `automacao.py`: operações de página puras (recebem `page`/`context`) +
  parsers testáveis + API pública síncrona que delega para `SESSAO`.
- `otimizar_automacao=False`: mesmo código, mas fecha o browser no fim de cada
  chamada (comportamento antigo).
- Warm: `app/api.py` no startup chama `warm_from_settings(database)`; shutdown
  fecha o browser.
- Lançar: `storage_state()` → close → launch headed → `new_context(storage_state=...)`.
  Se cair na tela de login, relogin visível automático.
- `POST /automacao/navegador/fechar` fecha a janela e volta para headless na
  próxima rodada.

## API

- `POST /automacao/listar` → `{total, caixas[]}` (re-lê a tabela a cada chamada)
- `POST /automacao/importar`
  - novo: `{caixas: [{data,pdv,turno,movto,row_index?}], data?: "YYYY-MM-DD"}`
    → `{resultados: [{chave, ok, caixa, dinheiro, pagamentos, tempo_ms, erro?}], total}`
  - legado: `{caixa_idx}` → resposta antiga `{resumo, dinheiro, pagamentos}`
- `POST /automacao/lancar` → aceita `caixa` (chave) + `data`; `caixa_idx` continua
- `GET /automacao/status` → `{state, detail, headed, browser_aberto, timings_ms}`
- `POST /automacao/reconectar` → fecha, reaquece e devolve status
- `POST /automacao/navegador/fechar` → fecha browser headed

## Prontidão (sem sleeps)

| Etapa | Sinal |
| --- | --- |
| Login | `#loginControllerLoginId` presente → fill/Enter → `!location.hash.includes('login')` |
| Conciliador | linhas `sknDataProviderFiltered` com células preenchidas; "Mostrar todos" clicado por JS antes |
| Detalhe | popup via `expect_page`; linhas `RS_FORMASPAGTO` com conteúdo |
| Conciliação | popup via `expect_page`; linhas `RS_PAGAMENTOS` com ≥8 `td` |
| Dinheiro | span `CC077_VL_CALC` da linha DINHEIRO |
| Download | `expect_download` (já existia) |

Erro de etapa: timeout 15s, retry 1x quando a sessão caiu, mensagem clara.

## Frontend

- `automacaoCache.svelte.ts`: helpers de chave/normalização de data; cache atual.
- `AutomacaoModal.svelte`: checkbox (import), radio (lançar), atalho T1+T2,
  badge de status + Reconectar + Fechar navegador, resumo por caixa.
- `Importacao.svelte`: aplica lote por turno, arma split (`split_time` =
  fechamento do T1; se CSV já importado, divide na hora), bloqueia data
  divergente, só T2 sem split = erro.
- `ConfigPosto.svelte`: checkbox "Otimizar login da automação".

## Testes

- `tests/test_automacao_lote.py`: normalização de data, turno, resolução por
  chave/índice, validação de data, parsers de linhas.
- `tests/test_automacao_sessao.py`: loop dedicado sobe/desce, status inicial,
  mutex ocupado.
- Smoke real (pendente de credenciais): `scripts/bench_automacao.py` mede
  listar/importar/lote/lançar e imprime os tempos.

## Riscos

1. `storage_state` pode não carregar a sessão AngularJS do Cloudfy; fallback é
   relogin visível no lançar.
2. Bloquear `font` no headless pode afetar ícones Material; se quebrar, remover
   só `font` do bloqueio.
3. Default ON liga Chrome em memória no boot para todos os usuários; OFF volta
   ao comportamento antigo sem mudança de código.

## Status da implementação (2026-10-27)

Implementado neste commit:

- `automacao_sessao.py` (novo): thread + loop dedicado, browser persistente,
  warm no boot via `app/api.py`, troca headless↔headed com `storage_state`,
  mutex, estados e `/automacao/status`.
- `automacao.py` reescrito: ops de página sem lifecycle de browser, esperas por
  sinal de dado (`wait_for_function`, `expect_page`, `expect_download`),
  extração em 1 `evaluate`, remoção dos sleeps fixos, assets bloqueados no
  headless, timings por etapa, chaves estáveis/turno/data e parsers puros.
- Endpoints: `importar` em lote (chave estável + data), `lancar` com chave/data,
  `status`, `reconectar`, `navegador/fechar`; `descontos/sync` usa a sessão.
- Config `otimizar_automacao` (default ON) + checkbox em ConfigPosto.
- `AutomacaoModal`: multi-seleção, atalho T1+T2 da data, badge de sessão,
  reconectar, fechar navegador, resumo por caixa com tempo/erro.
- `Importacao`: lote por turno, armado de split com fechamento do T1, bloqueio
  de data divergente e "só T2" sem split.
- `scripts/bench_automacao.py` para medir as metas com credenciais reais.
- Testes: 46 passed.

Validação local sem credenciais (Cloudfy falso em HTML):

- listar 2 caixas: ~0,12s; segunda rodada reusa sessão (sem `login`).
- lote T1+T2: 1,5s + 0,23s (popup do 1º detalhe paga o carregamento).
- lançamento completo: preenche DINHEIRO e VISA CREDITO, clica Confirmar,
  janela permanece aberta, `fechar navegador` encerra.
- `storage_state` restaura cookie + localStorage entre relaunches.
- troca headless→headed: ~1,2s; headed→headless: ~1,5s.

Pendente: smoke real no Cloudfy (credenciais), validar `storage_state` da
sessão AngularJS e possíveis ajustes de seletor.

## Correção 2026-10-27 — T2 igual ao T1

Sintoma: no lote T1+T2 o T2 vinha com os mesmos valores do T1 e, às vezes,
não aparecia importado.

Causa raiz confirmada no Cloudfy real (`automacao`):

- O detalhe do caixa e a conciliação de cartões abrem **inline na mesma aba**
  (`#/H02SF0108B`), não em popup.
- `_abrir_popup` esperava 10s por uma nova aba, desistia e devolvia a mesma
  página. O detalhe do T1 continuava aberto.
- O lote usava `row_index` e a lista estava escondida; a abertura do T2 caía
  no detalhe do T1, lendo DINHEIRO/pagamentos do T1.
- A falha do T2 era silenciosa no front se o T1 tivesse dado ok.

Correção em `automacao.py` / `automacao_sessao.py`:

- `_abrir_pagina_ou_inline`: aceita popup **ou** conteúdo inline; poll tolera
  reload/contexto destruído; sem espera fixa de 10s.
- Filtro de linhas **visíveis** em `JS_LISTAR`, `JS_DINHEIRO`,
  `JS_PAGAMENTOS`, prontidão e contadores.
- `Voltar` visível: conciliação → detalhe → lista. `garantir_lista` recupera
  com reload se necessário.
- `abrir_detalhes` volta para a lista no `finally`; `executar_lancamento`
  continua deixando a janela aberta.
- `importar` relê a lista e resolve a **chave estável** antes de cada caixa;
  T2 ausente vira erro explícito em vez de reutilizar T1.
- Front: importação parcial passa a mostrar `Importacao parcial: ...`.

Verificação real (2026-10-27, credenciais de automação):

- T1 26/10: DINHEIRO 632,35; T2 26/10: DINHEIRO 755,30.
- T2 sozinho: 755,30. Lote repetido 2x: T1 632,35 / T2 755,30.
- Tempos por caixa: ~1,2–1,7s; detalhe/conciliação inline ~0,15s.
- Auto Lançar inline validado até o preenchimento de DINHEIRO e 8 formas de
  pagamento, sem clicar Confirmar.
- UI E2E com TinyDB temporário: importação 2/2, split armado em 14:03,
  T1 sistema 632,35 e T2 sistema 755,30.
