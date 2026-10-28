# Caixa Restaurante — PIX CNPJ (forma CHEQUE do Cloudfy)

Data: 2026-10-28 · Branch: `master` (apos `3d23f52`)

## Pedido

O Cloudfy lista a forma de pagamento **CHEQUE** no detalhe do caixa
restaurante (`RS_FORMASPAGTO`, `CC077_VC_TPPAG = CHEQUE`). Na operacao essa
forma e, na pratica, **PIX CNPJ**. O programa precisa de mais uma categoria no
caixa restaurante e a automacao deve ler o cheque do mesmo modo que le o
DINHEIRO.

## Decisoes

- Chave interna: `PIX_CNPJ`; rotulo: **PIX CNPJ**; classificacao: `DEBITO`.
  Fica entre `VISA` e `DINHEIRO` em `CATEGORIAS_RESTAURANTE`.
- `sistema` de `PIX_CNPJ` vem da linha **CHEQUE** (`span[ng-bind*="CC077_VL_CALC"]`)
  lida na importacao automatica do Cloudfy, igual ao DINHEIRO.
- `real` de `PIX_CNPJ` e digitado manualmente (nao existe no CSV PagBank de
  cartoes). Por isso a categoria e ignorada nas sobrescritas de REAL do
  PagBank, junto com `DINHEIRO` (`restManualReal` no frontend).
- No **Auto Lancar**, a conciliacao do CHEQUE recebe o `real` de `PIX_CNPJ`,
  como a conciliacao do DINHEIRO recebe o `real` do caixa. Se o valor for zero
  ou a linha CHEQUE nao existir, nada e preenchido e o lancamento segue.
  DINHEIRO continua obrigatorio (comportamento anterior).

## Implementacao

- `constants.py`: `CATEGORIAS_RESTAURANTE`, labels e classificacao.
- `automacao.py`:
  - `CaixaDetalhe.cheque`.
  - `parse_formas_pagamento_rows` + `parse_dinheiro_rows` / `parse_cheque_rows`.
  - `extrair_formas_pagamento` (um unico evaluate de `JS_DINHEIRO`).
  - `JS_INDEX_FORMA` e `_lancar_formas_pagamento` (DINHEIRO + CHEQUE).
  - `executar_lancamento(..., cheque_valor)`.
- `automacao_sessao.py`: `lancar(..., cheque_valor)` e `"cheque"` no resultado
  de `importar`.
- `__init__.py`: `/automacao/lancar` aceita `cheque_valor`.
- `Importacao.svelte`: categoria, `restManualReal`, `sistema` a partir de
  `resultado.cheque`, envio de `cheque_valor` no Auto Lancar.
- `Resultado.svelte`: rotulo `PIX CNPJ`.

## Verificacao

- `pytest -q`: 85 passed (8 novos em `tests/test_pix_cnpj.py`).
- `npm run build`: OK.
- `svelte-check`: os mesmos 4 erros antigos, nenhum novo.
- Conferencia ADM nao muda: continua comparando o extrato `CAIXA ADM` com a
  soma de `dinheiro_real` dos caixas restaurante.
