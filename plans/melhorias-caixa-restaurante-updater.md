# Plano — Auto-update + melhorias do caixa Restaurante

Status: **implementado** em 2026-10-27. Pendente somente a publicação da release
`v1.0.9` (tag/push) e o aviso de reabrir o app uma vez após o primeiro update.

## 0. Causa raiz confirmada

### Auto-updater (Windows)

`app/core/updater.py` gera um `.bat` e o executa com `subprocess.Popen`, herdando o
ambiente do processo atual. PyInstaller 6 onefile define, no ambiente:

- `_PYI_APPLICATION_HOME_DIR` (pasta `_MEI...` extraída)
- `_PYI_PARENT_PROCESS_LEVEL`
- `_PYI_ARCHIVE_FILE`
- `_MEIPASS` / `_MEIPASS2`

O `.bat` roda `start "" "<exe>"`. O novo bootloader vê `_PYI_PARENT_PROCESS_LEVEL`
e conclui que já é processo filho: **não extrai** e tenta carregar
`python312.dll` da pasta `_MEI` do processo antigo — que já foi apagada quando o
app encerrou. Resultado:

```
Failed to load Python DLL ... LoadLibrary: The specified module could not be found.
```

Evidências:

- Asset v1.0.8 baixado: sha256 `5cae1aaf...` = digest do release (download íntegro).
- Arquivo contém `PYTHON312.dll`, `VCRUNTIME140*.dll`, 344 entradas no archive.
- `strings` do bootloader 6.21 mostra os nomes das variáveis acima.
- `app/version.py` = `0.1.0`; releases até `v1.0.8` → sempre "atualização disponível".
- `_parse_version("v.0.1.6")` → `.0.1.6` → `(0, 0, 1)` (errado).

### Caixa Restaurante

| Sintoma | Causa no código |
|---|---|
| Atualizar moedas apaga soma feita no DINHEIRO | `handleContagemChange` sobrescreve `categorias.DINHEIRO.real`; backend `_normalize_restaurante` recomputa e `totals_restaurante` força DINHEIRO = total das contagens |
| Dividir só funciona se ativar antes de importar | `handleRestPagbankUpload` só divide quando `splitMode` já está ativo; CSV importado não é guardado |
| Sem botão automático | Só existe o modal manual de horário |
| Sem navegação por setas | Inputs de contagem só tratam `Enter` |
| Sem pasta padrão / auto-import | Não existe configuração nem varredura de pasta |
| Data inicia hoje | `new Date().toISOString().slice(0,10)` |

## 1. Decisões fechadas

1. Updater: corrigir env herdado + blindar troca (sha256, rename, rollback, retry). Onefile mantido, Windows e macOS.
2. Versão: bump `app/version.py` para `1.0.9`; parser de tag tolerante (`v`, `v.`, sufixos).
3. Primeiro update após o fix: reabrir o app manualmente **uma vez** (script antigo continua com env sujo). Avisar na release.
4. DINHEIRO: **delta somado sempre** (`real = total_contagem + ajuste`), com indicação por cor + badge; ajuste persistido no rascunho (topo e por turno).
5. Split pós-import: guardar o CSV em memória na sessão; rascunho reaberto sem CSV avisa e mantém comportamento atual.
6. Dividir caixa automático: cache de sessão da automação; sem cache/T1 → erro "operação falhou", sem rodar Playwright.
7. Setas: dentro da aba ativa (notas → moedas → depósitos), sem wrap, sem trocar aba.
8. Pasta CSV: Configurações > Geral, campo texto + "Testar pasta"; chave global `relatorio_csv_dir`.
9. Auto-import: ao abrir caixa novo e ao mudar a data; sobrescreve REAL (menos DINHEIRO); `pagMMDD.csv` case-insensitive, com e sem zero.
10. Data padrão: ontem (local), só restaurante novo. Testes pytest.

## 2. Auto-update

### `app/version.py`
- `__version__ = "1.0.9"`.

### `app/core/updater.py`

**Versão**
- `_normalize(tag)`: remover `v`/`V`, pontos e espaços iniciais; cortar sufixos não numéricos (`-beta`, `+build`).
- `_parse_version`: parse só dos 3 primeiros componentes numéricos; `v.0.1.6` → `(0,1,6)`.
- `is_newer` inalterado.

**Check**
- `check_for_update` passa a devolver também `download_size` e `download_sha256`
  (asset `size` e `digest` `sha256:...` do GitHub; `None` se ausente).

**Download**
- `download_update(url, asset_name, expected_size=None, sha256=None)`:
  - escreve em `<asset>.part`;
  - valida tamanho e sha256;
  - `os.replace(part, final)` (atômico);
  - apaga `.part` em erro.
- Rota `POST /api/update/download` aceita `size`/`sha256` (opcionais; retrocompatível).
- `ConfigPosto.svelte`: envia os novos campos ao baixar.

**Apply**
- Montar `clean_env` removendo `_PYI_*`, `_MEIPASS*` do `os.environ` e usar em
  `Popen(..., env=clean_env)`.
- Scripts também limpam as variáveis (defesa em profundidade) e mudam para a pasta
  do alvo (`cd /d` no Windows, `cd` no Unix).

**Windows (`apply_update.bat`)**
1. `set "_PYI_APPLICATION_HOME_DIR="` etc.
2. `timeout /t 2`.
3. Renomear alvo → `<alvo>.old` com retry (renomear exe em execução é permitido no Windows; evita corromper o arquivo).
4. Copiar novo exe → alvo.
5. Validar tamanho esperado.
6. `start "" /d "<pasta_alvo>" "<alvo>"`.
7. Apagar `.old`, logar em `updates/apply_update.log`.
8. Falha em qualquer passo: restaurar `.old` → alvo e abortar.

**macOS/Linux (`apply_update.sh`)**
- Mesmo fluxo: `mv` alvo → `.old`; `ditto` (mac `.app`) ou `cp`; `chmod +x`; `open`/exec; rollback; remover `.old`.
- `_prepare_new_artifact` continua extraindo zip; adicionar limpeza de extrações antigas.

**Risco assumido**
- Instalações atuais têm o `.bat` velho. No primeiro update pós-fix o relaunch ainda
  falha; usuário abre pelo atalho e aí a versão nova roda. Documentar na release.

## 3. Caixa Restaurante — DINHEIRO com ajuste

### Dados
- `conciliacao.dinheiro_ajuste: float` (topo; em modo split = soma dos turnos).
- `conciliacao.turnos["1"|"2"].dinheiro_ajuste: float`.
- Regra única: `DINHEIRO.real = total_contagens_dinheiro(contagens) + dinheiro_ajuste`.

### Backend
- `services.py`:
  - mover `_dinheiro_real_from_contagens` de `__init__.py` para
    `total_contagens_dinheiro(contagens)` (reutilizável/testável);
  - `build_conciliation_rows_restaurante(..., dinheiro_real)` continua recebendo o
    total já ajustado;
  - `totals_restaurante` inalterado.
- `__init__.py` `_normalize_restaurante`:
  - ler `dinheiro_ajuste` (default 0);
  - `dinheiro_real = total_contagens + ajuste`;
  - persistir `dinheiro_ajuste` e `dinheiro_real`;
  - não sobrescrever ajuste no autosave.
- `export.py`: em "Informações Complementares", linha
  `Ajuste manual DINHEIRO: R$ X` quando ajuste ≠ 0 (por turno no split).

### Frontend (`Importacao.svelte`)
- Estado `dinheiroAjuste`; `turnoStore[n].dinheiroAjuste`; snapshot/load incluem.
- `contagemTotal()` = soma das contagens `Geral` do turno ativo.
- `handleRestRealChange("DINHEIRO", e)`:
  - `ajuste = valor_digitado - contagemTotal()`;
  - `categorias.DINHEIRO.real = valor_digitado`.
- `handleContagemChange`:
  - `categorias.DINHEIRO.real = contagemTotal() + ajuste`;
  - `syncRealVars()`.
- `loadConciliacao`: restaurar ajuste do doc/turnos.
- `buildPayload`: enviar `dinheiro_ajuste` (topo e turnos) + `categorias` já calculadas.
- `mergeTurnoCategorias`: DINHEIRO real = soma dos turnos (já inclui ajuste).
- UI da linha DINHEIRO:
  - input em âmbar (`border-amber-500`, `text-amber-700`) quando `ajuste ≠ 0`;
  - badge/legenda: `contagem R$ X + ajuste R$ Y`;
  - link "usar valor da contagem" zera ajuste e recalcula.
- `Resultado.svelte`: nota de composição em "Informações Complementares".

## 4. Split interno

### Arquivos/sessão
- `lastRestFile: File | null` + `lastRestName` (upload manual).
- `autoImportFile: string | null` (nome do arquivo vindo da pasta).
- `statusRestPagbank` mostra origem (upload/pasta).

### Backend
- Refatorar `parse_restaurante_pagbank_split` para aceitar caminho
  (`_split_pagbank_path(path, split_time)`), mantendo o wrapper por bytes.
- Novo endpoint:
  `POST /api/conciliador/parser/pagbank-restaurante-split-arquivo`
  body `{ "filename": "pag1024.csv", "split_time": "14:05" }`.
  - valida `relatorio_csv_dir` configurado;
  - resolve `dir / filename` e garante que o pai é a pasta configurada (anti path traversal);
  - retorna mesma estrutura de `parse_restaurante_pagbank_split`.

### Frontend
- `executeSplit(time)`:
  - se `lastRestFile` → upload no endpoint de split;
  - senão se `autoImportFile` → endpoint por arquivo;
  - senão → aviso "Reimporte o CSV para dividir os valores" e mantém comportamento atual (T1 = dados atuais, T2 vazio).
- `confirmSplit()` (manual) chama `executeSplit`.
- Novo botão primário **"Dividir caixa"**:
  - lê `getCaixas()` do `automacaoCache`;
  - match: `data` do cache (`dd/mm/yyyy`) → ISO === `data` do caixa;
  - turno `"1"` (aceitar `"Turno 1"` também);
  - hora: extrair `HH:MM` de `horario_fechamento` (`19/07 14:05`);
  - sem match → `errorMessage = "Falha ao dividir: caixa do turno 1 de <data> não encontrado no cache da automação."` e aborta;
  - com match → `splitTime = hora`, `executeSplit(hora)`, toast `Dividido em HH:MM (T1 <pdv>)`.
- Botão secundário **"Dividir manualmente"** → modal atual.
- Ambos visíveis em `turno === "Todos" && !splitMode && !readonly`.
- Helpers de parse em `automacaoCache.svelte.ts` (`turno1Fechamento(dataISO)`).

## 5. Setas na contagem de dinheiro

`ContagemDinheiro.svelte`:
- cada input de qtde/moedas/depósitos recebe `data-nav` (ordem: 200,100,50,20,10,5,2,moedas,depósitos);
- handler `onkeydown`: `ArrowDown` foca próximo habilitado, `ArrowUp` anterior;
- `preventDefault`; sem wrap; campos desabilitados ignorados; `Enter` continua igual.

## 6. Pasta padrão + auto-import

### Configuração
- `config_posto.py`: `relatorio_csv_dir: ""` em `DEFAULT_SETTINGS`, `load_settings`, `save_settings`.
- `ConfigPosto.svelte` (aba Geral): card "Pasta do relatório CSV (Restaurante)" com
  input, **Salvar** e **Testar pasta**.
- Endpoint `GET /api/conciliador/config/pasta-csv/testar?path=...` →
  `{ok, total, exemplos[]}` (valida diretório e lista `pag*.csv`).

### Varredura (novo `app/modules/conciliador/relatorio_pasta.py`)
- `find_report_file(directory, iso_date) -> Path | None`
  - padrão `^pag(\d{3,4})\.csv$`, case-insensitive;
  - 4 dígitos = `MMDD`; 3 dígitos = `MDD`;
  - compara com mês/dia de `iso_date`.
- `read_report_file(directory, filename)` com validação de containment.

### Endpoint
- `GET /api/conciliador/restaurante/csv-auto?data=YYYY-MM-DD&split_time=HH:MM`
  - sem pasta configurada → `{found: false}`;
  - arquivo não encontrado → `{found: false}`;
  - encontrado → `{found: true, filename, split: bool, result}`;
  - `split_time` presente → usa parser de split; senão parser completo.

### Frontend
- `tryAutoImport()` em `Importacao.svelte`:
  - só restaurante, `!readonly`, `!loading`;
  - chama endpoint com `data` e `splitMode ? splitTime : ""`;
  - se `found`:
    - aplica REAL (exceto DINHEIRO) ou `applySplitReais`;
    - `autoImportFile = filename`; `statusRestPagbank = "Importado da pasta: <arquivo>"`;
    - toast;
  - sem arquivo → silencioso;
  - dedupe por chave `data|splitTime`.
- Gatilhos: `onMount` (caixa novo) e `$effect` observando `data` (debounce ~500 ms, só após `hydrated`).
- Não sobrescreve DINHEIRO; não roda em conciliado.

## 7. Data padrão (restaurante)

- `Importacao.svelte`: `let data = $state(tipo === "restaurante" ? yesterdayISO() : todayISO())`.
- `yesterdayISO()` usa componentes locais (sem `toISOString`).
- Só afeta caixa novo (`conciliacaoId == null`); rascunhos carregados mantêm a data salva.

## 8. Testes

- `pytest.ini` com `pythonpath = .`, `testpaths = tests`.
- `requirements-dev.txt`: `pytest`.
- `Makefile`: alvo `test`.
- Casos:
  - `tests/test_updater_version.py`: `v1.0.8`, `v.0.1.6`, `V2.0.0`, `1.0.9-beta`, comparação.
  - `tests/test_relatorio_pasta.py`: `pag1024.csv`, `PAG1024.CSV`, `pag924.csv`, data sem match, pasta inexistente.
  - `tests/test_restaurante_split.py`: CSV fixture com horários; T1/T2 por horário, DINHEIRO ignorado, status ≠ APROVADA.
  - `tests/test_dinheiro_ajuste.py`: `total_contagens_dinheiro` + ajuste; linha DINHEIRO com ajuste; split somando ajustes.

## 9. Ordem de execução

1. `requirements-dev.txt`, `pytest.ini`, testes de versão + pasta + split + ajuste (TDD).
2. `app/version.py` + `app/core/updater.py` + rota de download + `ConfigPosto` (payload sha256).
3. Backend restaurante: settings `relatorio_csv_dir`, testar pasta, `relatorio_pasta.py`, endpoint csv-auto, endpoint split-arquivo, `_normalize_restaurante`/`services` com ajuste.
4. Frontend restaurante: data ontem, ajuste DINHEIRO + badge, split (2 botões + reparse), setas, auto-import.
5. `Resultado.svelte` + `export.py` (nota de ajuste).
6. `npm run build` + `pytest` + smoke manual.
7. Release: tag `v1.0.9`; nota sobre reabrir manualmente uma vez.

## 10. Verificação manual

- Novo caixa Restaurante: data = ontem.
- Moedas 100 → DINHEIRO real 100; digitar `100+20` no DINHEIRO → 120, badge âmbar "contagem 100 + ajuste 20".
- Alterar moedas para 150 → DINHEIRO real 170, ajuste mantido.
- Salvar rascunho, reabrir → ajuste preservado; backend mantém 170.
- Importar CSV → "Dividir caixa" sem cache → erro; popular Automação → "Dividir caixa" → T1/T2 preenchidos e toast com horário.
- "Dividir manualmente" → modal atual funciona.
- Reabrir rascunho dividido sem CSV → aviso, divisão atual mantida.
- Configurar pasta com `pag<MMDD>.csv` da data → auto-preenche REAL; trocar data → reimporta arquivo correspondente; sem arquivo → nada.
- Setas ↑/↓ percorrem notas → moedas → depósitos.
- `pytest` e `npm run build` verdes.

## 11. Fora de escopo

- Persistir cache da automação no backend.
- Trocar empacotamento para onedir/instalador.
- Alterar regra de divisão por turno T1/T2 existente.
- Corrigir composição `notas` vs `depósitos` no `_dinheiro_breakdown`.

## 12. Execução — verificação

- `pytest -q`: **26 passed** (`tests/test_updater_version.py`, `test_relatorio_pasta.py`,
  `test_restaurante_split.py`, `test_dinheiro_ajuste.py`).
- `npm run build`: OK (bundle gerado em `app/frontend/dist`).
- Smoke HTTP (`uvicorn` + TestClient): `/api/health` 1.0.9; settings; testar pasta;
  `csv-auto`; `csv-auto?split_time`; `split-arquivo`; save/resultado/PDF.
- Smoke UI headless (Chrome + Playwright):
  - data padrão `2026-10-26` (ontem);
  - auto-import `pag1026.csv` → PIX 5, VISA 30;
  - setas: 7× ↓ do primeiro campo de nota chega em Moedas;
  - moedas 10 → DINHEIRO 10; manual 30 → badge `contagem R$ 10,00 + ajuste R$ 20,00`;
    moedas 15 → DINHEIRO 35;
  - dividir manualmente 14:00 → T1 VISA 10 / T2 VISA 20;
  - autosave persistiu `dinheiro_ajuste` 20 e turnos;
  - "Dividir caixa" sem cache → aviso de falha;
  - troca de data → auto-import do arquivo correspondente.
- `git diff --check`: limpo.

### Correção do build CI (Svelte 5.57.3)

- CI instala `svelte@^5.0.0` (resolvedor pegou 5.57.3) e o build local estava com
  5.56.4, que tolerava um `{:else}` seguido de `{:else if}` em `ConfigPosto.svelte`.
- Corrigido: `{:else}` (aba Grupos) → `{:else if activeTab === "grupos"}`.
- Validado com Svelte 5.57.3: `npm run build` OK; abas Geral/Grupos/Equivalencias
  renderizam; smoke completo do restaurante repetido com a mesma versão do CI.
