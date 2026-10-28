# Conferência ADM (restaurante) + observações do caixa posto

Data: 2026-10-28 · Branch: `master`

## Observações do caixa posto

- Campo `Observacoes` no rodapé do caixa posto (`Importacao.svelte`), salvo no
  campo já existente `observacoes` do documento.
- PDF inclui a seção `Observacoes` quando o campo não está vazio.

## Ferramenta Conferência ADM

Ferramentas do restaurante → **Conferencia ADM**.

Fluxo:

1. Input de data; padrão = dia anterior.
2. Automação headless abre o gerenciador financeiro (`H02SF0201E`).
3. `Contas a pagar` → `Extrato`.
4. `Contas bancárias`: desmarca `Todas as contas`, marca `CAIXA ADM`,
   `Aplicar`.
5. Período: preenche início e fim com a data escolhida e confirma `OK`.
6. Lê `VL_TOTAL` e as linhas (`FI030_VC_LANC` / `FI030_VL_LANC`), ignorando
   `Saldo anterior`.

Comparação:

- Caixa: soma de `dinheiro_real` de todos os caixas restaurante não arquivados
  da data (contagens avulsas são ignoradas).
- `bate` quando `|extrato - caixa| <= 0,005`; senão `nao_bate`.
- Sem caixa na data: mostra extrato + aviso, sem veredito.
- Se a soma das linhas não fechar com `VL_TOTAL`, sinaliza
  `extrato_inconsistente` e continua.

Histórico:

- Tabela `conferencias_adm`, um registro por execução.
- Grava somente quando o extrato foi lido (inclusive sem caixa/divergente).
- Lista as 20 últimas na ferramenta; clique expande as linhas.

Automação:

- `automacao.py`: `conferir_extrato_adm`.
- `automacao_sessao.py`: `conferir_extrato_adm`; bloqueia se a janela headed
  do Auto Lançar estiver aberta.
- API: `POST /api/conciliador/conferencia-adm` e
  `GET /api/conciliador/conferencia-adm?limite=20`.

## Verificação real (2026-10-26)

- Extrato CAIXA ADM: **R$ 1.289,00**.
- Linhas: 632,75 + 755,25 - 98,00 - 1,00 = 1.289,00.
- `VL_TOTAL` = soma das linhas; sem inconsistência.
- Nenhum lançamento/salvamento no Cloudfy.

Testes: `pytest -q` **77 passed**; UI local com TinyDB temporário validou
histórico, `bate` com caixa 1.289 e `sem_caixa` com diferenca nula.
