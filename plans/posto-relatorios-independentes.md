# Posto — relatórios independentes no lado Site

Data: 2026-11-04 · Branch: `master` (após `00c048c`)

## Sintoma

No caixa posto, remover o segundo/terceiro relatório e importar outro depois
não atualizava os valores corretamente. Também havia dependência de ordem
(PagBank depois de Premmia apagava os valores da Premmia).

## Causas

1. O lado `site` de todas as categorias era uma coluna única:
   - PagBank **sobrescrevia** `categorias[key].site`;
   - Premmia **somava** (`+=`) em cima do que existisse.
   Resultado dependia da ordem das importações; reimportar Premmia duplicava.
2. Os botões "Remover" zeravam `site` de **todas** as categorias, apagando o
   relatório vizinho.
3. O `<input type="file">` não era limpo depois do upload. Remover e escolher
   o **mesmo arquivo** de novo não disparava `change` e nada acontecia.
4. Remover o CAIXA CSV não zerava sangria/notas a prazo/despesas.

## Correção

Lado site do posto agora é calculado a partir de fontes separadas:

- `pagbankCats`, `premmiaCats`, `manualSite` (edição manual de Site).
- `recalcPostoSite()`: `site = pagbank + premmia` (+ campo FitCard quando for
  `FITCARD`), respeitando override manual; ao final chama
  `handleContagemChange()` para recalcular SANGRIA.
- Importar PagBank/Premmia **substitui** a fonte inteira (sem `+=`), então
  reimportar não duplica e a ordem não importa.
- Remover PagBank/Premmia limpa só a própria fonte e recalcula; o outro
  relatório permanece.
- Edições manuais de Site ficam em `manualSite` e são descartadas apenas para
  categorias afetadas quando aquele relatório é reimportado/removido.
- Remover CAIXA CSV zera sistema, sangria, notas a prazo e despesas.
- Os três inputs de arquivo são limpos após o upload, permitindo reescolher o
  mesmo arquivo (também no PagBank do restaurante).

Persistência (para remover/reimportar depois de reabrir o caixa):

- `pagbank_site`, `premmia_site`, `manual_site` no documento.
- Rascunho antigo sem essas fontes: separa o site salvo pela origem
  (`PREMMIA_*` → Premmia; demais → PagBank), usando os `status_*` quando só um
  relatório foi importado.

## Verificação (UI real, TinyDB temporário, API mockada)

- PagBank 100 + Premmia 50 → 100/50.
- Remover Premmia → VISA 100, PREMMIA PIX vazio.
- Reimportar Premmia → 100/50.
- Remover PagBank → PREMMIA 50, VISA vazio.
- Reimportar PagBank → 100/50.
- Remover os dois → vazio; importar Premmia antes de PagBank → 100/50.
- Input de arquivo com `value` vazio após upload.
- Fontes persistidas no TinyDB; reabrir o caixa pelo histórico restaura
  100/50 e remover Premmia mantém VISA 100.
- Sem `pageerror`.

`pytest -q`: 101 passed. `npm run build`: OK. `svelte-check`: mesmos 4 erros
antigos.
