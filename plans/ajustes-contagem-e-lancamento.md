# Ajustes contagem R$ 200 + lançamento de cartões (2026-11-04)

Branch: `master` (após `bab5d17`)

## 1. Nome da nota de R$ 200 sai do caixa posto

- `ContagemDinheiro.svelte` ganhou a prop `mostrarNomes` (default `true`).
- `Importacao.svelte` e `ContagemAvulsa.svelte` passam
  `mostrarNomes={tipo !== "posto"}`.
- No posto o campo "Nome (opcional)" some; o serial continua. O dado
  `nomes_200` permanece no documento (histórico/PDF de caixas antigos).
- Restaurante mantém o campo.

## 2. Aba com nota de R$ 200 precisa de nome próprio

Regra: com `serial_200_mode = "obrigatorio_todas"`, toda contagem com
`notas["200"] > 0` cujo nome é **padrão numérico gerado** (`"1"`, `"2"`, ...)
ou vazio precisa ser renomeada. `"Geral"` é permitida (é a aba automática).

- Backend: `services.validate_contagens` gera erro
  `"... renomeie a aba que tem notas de R$ 200 ..."`.
- `/api/conciliador/validar-contagens` já bloqueia o "Conciliar".
- Frontend: `ContagemDinheiro` destaca a aba em vermelho e mostra aviso com os
  nomes das abas pendentes; regra aplicada no posto e no restaurante
  (configuração de serial é global).
- Modo `opcional_geral` / `opcional_todas`: regra não se aplica.

## 3. Auto Lançar cartões — dois edge cases

### 3.1 Sistema tem valor, real zero

Antes `_lancar_pagamentos` pulava `real == 0`, deixando a conciliação do
cartão vazia no Cloudfy. Agora:

- `automacao.valor_conciliacao_categoria(categoria)`:
  - real > 0 → `real` formatado (`"50,00"`);
  - real == 0 e sistema != 0 → `"0,00"` (preenche zero);
  - real == 0 e sistema == 0 → `None` (nada a lançar).
- `_lancar_pagamentos` usa o helper.

### 3.2 Real tem valor, sistema zero (sem linha no Cloudfy)

O Cloudfy não abre linha de conciliação para categoria sem valor no sistema,
então a automação não tem onde preencher. Continua manual, mas agora avisado:

- `Importacao.svelte` carrega o mapeamento (`/config/mapeamento`) no `onMount`.
- `restSemSistema` lista categorias mapeadas (exceto `DINHEIRO`/`PIX_CNPJ`)
  com `real > 0` e `sistema <= 0`.
- Card âmbar na seção "C - Conciliacao" mostra os nomes e valores.
- `handleAutomacaoLancar` pede confirmação listando as categorias antes de
  abrir o Cloudfy; a janela do Auto Lançar fica aberta para correção manual.
- Futuro: configurar automação para incluir essas categorias.

## Verificação

- `pytest -q`: 101 passed (6 novos de aba/serial + 3 de valor de lançamento).
- `npm run build`: OK.
- `svelte-check`: mesmos 4 erros antigos, nenhum novo.
