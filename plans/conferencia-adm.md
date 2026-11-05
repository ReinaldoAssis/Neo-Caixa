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

- Caixa: **dinheiro em espécie** de todos os caixas restaurante não arquivados
  da data. Espécie = `dinheiro_real - dinheiro_moedas`; **moedas ficam fora**
  do cálculo. Contagens avulsas são ignoradas.
- `dinheiro_moedas` vem do documento; se faltar (caixa antigo), é derivado da
  soma de `moedas` das contagens `Geral`.
- `bate` quando `|extrato - caixa| <= 0,005`; senão `nao_bate`.
- Sem caixa na data: mostra extrato + aviso, sem veredito.
- Se a soma das linhas não fechar com `VL_TOTAL`, sinaliza
  `extrato_inconsistente` e continua.
- A tela mostra `caixa_moedas` como valor ignorado, para deixar a exclusão
  explícita.

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

## Ajuste 2026-10-28 — moedas fora do cálculo

- `conferencia_adm.dinheiro_especie_caixa(doc) = dinheiro_real_caixa - moedas_caixa`.
- `conferencia_adm.moedas_caixa(doc)`: usa `dinheiro_moedas`; fallback soma
  `moedas` das contagens `Geral`.
- Resultado e histórico ganharam `caixa_moedas`.

## Ajuste 2026-11-05 — espécie contada + modos de comparação

### Dinheiro do caixa

- `dinheiro_especie_caixa` passou a usar **as contagens** (`total - moedas` das
  contagens `Geral`), e não `dinheiro_real`.
- Motivo: `dinheiro_real = contagens + dinheiro_ajuste` (notas de despesa).
  A conferência mostrava R$ 1.315 quando o caixa fechado tinha R$ 1.043; a
  diferença era o ajuste das notas de despesa. Agora só entra o dinheiro em
  espécie contado.
- Fallback para documentos antigos sem contagens: `dinheiro_notas`, depois
  `dinheiro_real - moedas`.

### Dois modos (toggle)

1. **Extrato completo** (padrão): comportamento anterior; compara o `VL_TOTAL`
   do extrato CAIXA ADM com o caixa em espécie.
2. **Selecionar itens**: lê o extrato e devolve as linhas sem gravar histórico.
   O usuário marca/desmarca itens; `Comparar selecionados` envia as linhas e os
   índices escolhidos, e a comparação usa a soma dos itens marcados.

API:

- `POST /conferencia-adm` `{data, modo:"completo"}` → lê Cloudfy, avalia e
  registra.
- `POST /conferencia-adm` `{data, modo:"selecionar"}` → lê Cloudfy e retorna
  `aguardando_selecao: true` + `linhas` + resumo do caixa (não registra).
- `POST /conferencia-adm` `{data, modo:"selecionar", extrato, selecionadas}`
  → avalia sem abrir o Cloudfy e registra.

Resultado/histórico:

- Campos novos: `modo`, `selecionadas`, `total_comparado`.
- `diferenca = total_comparado - caixa_total`.
- Histórico mostra "N itens" e, ao expandir, marca os itens usados.
