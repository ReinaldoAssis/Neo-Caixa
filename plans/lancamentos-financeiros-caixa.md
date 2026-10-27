# Lançamentos financeiros a partir do caixa restaurante

Data: 2026-10-27 · Branch: `master` · Escopo: **somente caixa restaurante**

## Objetivo

Atalho no caixa restaurante para lançar no gerenciador financeiro do Cloudfy
(`#/H02SF0201E`):

1. **Transferência MOEDAS**: `CAIXA ADM` → `MOEDAS`, descrição `MOEDAS`,
   valor = soma das moedas de todos os caixas restaurante da data, data = data
   do caixa.
2. **Despesas**: cada nota de despesa do caixa vira um pagamento opcional no
   financeiro, com descrição própria.

A ferramenta "checar caixa adm" citada na conversa fica **fora de escopo**.

## Decisões (grilling 2026-10-27)

| Tema | Decisão |
| --- | --- |
| Escopo | Só caixa restaurante; sem tela nova em Ferramentas |
| Notas de despesa | Lista itemizada `{id, descricao, valor, legado?}` substitui `dinheiro_ajuste` |
| DINHEIRO real | `contagem + soma(notas)`; input somente leitura |
| Notas no split | Por turno; modal de revisão junta T1+T2 |
| Seleção | Checkbox por item no modal; padrão marcado; não persiste |
| Legado | `dinheiro_ajuste` antigo migra para item `AJUSTE MANUAL`, desmarcado |
| MOEDAS | Uma por data, soma de todos os caixas restaurante da data |
| Override MOEDAS | Não; valor/data calculados |
| T2 depois | Complemento da diferença; se a soma diminuir, bloqueia e pede revisão |
| Execução | Headless, preenche e clica Salvar |
| Janela headed aberta | Bloqueia e pede para fechar (exceto debug) |
| Duplicidade | Bloqueia por chave; "Relançar" explícito com confirmação |
| Status do caixa | Rascunho e conciliado; arquivado bloqueia |
| Histórico | Tabela `lancamentos_financeiros` só com lançamentos/tentativas |
| Config | Campos em ConfigPosto > Automação Cloudfy, com defaults |
| Fornecedor / nº doc / data doc | Vazios; se o Cloudfy exigir fornecedor, configurar o padrão e relançar (execução headless) |

## Modelo de dados

`conciliacoes` (restaurante):

- `despesas_notas: [{id, descricao, valor, legado?}]` (topo, caixa não dividido)
- `turnos["1"|"2"].despesas_notas` (caixa dividido)
- `dinheiro_ajuste` continua existindo como **soma** das notas (compatibilidade
  com export/resultado/testes)
- `dinheiro_real = total_contagens + dinheiro_ajuste`

`lancamentos_financeiros`:

```
{
  chave, tipo: "transferencia_moedas" | "despesa",
  caixa_id, turno, nota_id,
  data, descricao, valor,
  status: "lancado" | "erro",
  erro, criado_em, atualizado_em, lancado_em
}
```

Chaves:

- MOEDAS cheia: `transferencia_moedas|<data>`
- MOEDAS complemento: `transferencia_moedas|<data>|delta|<total>`
- Despesa: `despesa|<caixa_id>|<turno>|<nota_id>`

Pendentes são derivados dos caixas + histórico; o histórico é imutável por
snapshot.

## Backend

`app/modules/conciliador/financeiro.py`:

- normalização de notas, migração do ajuste legado
- soma de moedas da data
- `pendentes_caixa(database, caixa_id)` → itens + resumo
- `selecionar_por_chaves(...)` → valida e monta payload de automação
- `registrar_resultado(...)` → upsert por chave

Endpoints:

- `GET /api/conciliador/financeiro/caixa/{id}/pendentes`
- `POST /api/conciliador/financeiro/lancar` `{caixa_id, chaves[], forcar?}`

`_normalize_restaurante` passa a normalizar `despesas_notas` (topo e turnos),
derivar `dinheiro_ajuste` e preservar o legado.

## Automação

`automacao.py`:

- `FINANCEIRO_URL = .../#/H02SF0201E`
- `abrir_financeiro` (login se preciso, espera os botões)
- `lancar_transferencia_financeira`
- `lancar_pagamento_financeiro`
- `executar_lancamentos_financeiros`

Preenchimento por `skn-id`:

| Campo | `skn-id` |
| --- | --- |
| Descrição | `Components.FI030_VC_LANC` |
| Valor | `Components.FI030_VL_LANC` |
| Data transferência | `Components.FI030_DT_TRANSF` |
| Conta origem | `Components.FI030_NR_CONTAOR` |
| Conta destino | `Components.FI030_NR_CONTADE` |
| Vencimento | `Components.FI030_DT_VENC` |
| Pagar conta | `Components.FI030_IT_PAGO` |
| Dt. pagamento | `Components.FI030_DT_PAGREC` |
| Categoria | `Components.FI030_NR_CAT` |
| Conta | `Components.FI030_NR_CONTA` |
| Centro de custo | `Components.AD030_NR_CC` |
| Tipo documento | `Components.FI060_IT_TPDOC` |
| Fornecedor | `Components.FI030_NR_PESSOA` |

Selectize: clicar no controle, digitar filtro, escolher opção por texto
(exato > sufixo ` : TEXTO` > contém). Salvar e esperar o modal fechar; se
continuar aberto, coletar campos com `.md-input-danger` e devolver erro.

`automacao_sessao.py`:

- `lancar_financeiro(...)`: exige headless (bloqueia se `_headed` e não debug),
  navega uma vez e executa os itens em sequência; falha de um item não aborta os
  demais (exceto sessão perdida).
- `otimizar_automacao=False` mantém o comportamento antigo (fecha browser no
  fim).

## Frontend

`Importacao.svelte`:

- card **Lançamentos financeiros** depois da Contagem de Dinheiro:
  - resumo MOEDAS do dia + status
  - lista de notas (descrição/valor/remover, total)
  - botão **Revisar e lançar**
- modal de revisão:
  - MOEDAS (pendente/lançado/complemento/divergente)
  - despesas por turno, checkbox por item
  - legado desmarcado
  - status, erro, "Relançar"
- DINHEIRO real somente leitura; composição `contagem + notas`
- migração de `dinheiro_ajuste` legado ao carregar

`ConfigPosto.svelte`: card de configuração do financeiro com os defaults.

`Resultado.svelte` / `export.py`: listar as notas em Informações
Complementares em vez de "ajuste manual".

## Config

`config_posto.py`:

```
financeiro_origem = "CAIXA ADM"
financeiro_destino = "MOEDAS"
financeiro_descricao_moedas = "MOEDAS"
financeiro_categoria = "02.03.01 Fornecedores"
financeiro_conta = "CAIXA ADM"
financeiro_centro_custo = "LAGOA CAFE CONVENIENCIA"
financeiro_tipo_documento = "DINHEIRO"
financeiro_fornecedor = ""
```

## Testes

- `tests/test_financeiro.py`: notas, legado, soma de moedas, pendentes,
  dedupe, complemento T2, chaves, `_normalize_restaurante` com topo e turnos,
  DINHEIRO = contagem + notas e preservação do valor lançado em relançamento
  que falhou.
- HTML falso em `tests/fixtures/cloudfy_financeiro.html` + script de smoke
  (`scripts/smoke_financeiro.py`) para validar seletores sem credenciais.
- `pytest -q` e `npm run build`.

## Status da implementação (2026-10-27)

Implementado:

- `financeiro.py`: notas, migração do legado, soma de moedas do dia, pendentes,
  histórico, dedupe, complemento de T2 e bloqueio de caixa arquivado/sem data.
- `__init__.py`: `_normalize_restaurante` itemiza as despesas; endpoints
  `GET /financeiro/caixa/{id}/pendentes` e `POST /financeiro/lancar`.
- `automacao.py`: `H02SF0201E`, Novo pagamento/Nova transferência, selectize por
  texto, toggle Pagar conta, Salvar e verificação do fechamento do modal.
- `automacao_sessao.py`: `lancar_financeiro` headless; bloqueia se a janela
  visível do Auto Lançar estiver aberta (exceto debug).
- `Importacao.svelte`: card de lançamentos + modal de revisão; DINHEIRO real
  somente leitura = contagem + notas; migração do legado; relançar.
- `ConfigPosto.svelte`: campos do financeiro.
- `Resultado.svelte` / `export.py`: notas nas Informações Complementares.
- Testes: `tests/test_financeiro.py` (16), bloco headed em
  `tests/test_automacao_sessao.py`; `scripts/smoke_financeiro.py` com HTML falso
  em `tests/fixtures/cloudfy_financeiro.html`.

Verificação local:

- `pytest -q`: **63 passed**.
- `npm run build`: OK.
- `svelte-check`: 4 erros antigos fora do escopo, nenhum novo.
- Endpoints com TinyDB temporário: save restaurante → `dinheiro_ajuste` 42,5,
  `dinheiro_real` 155; pendentes 3 itens (MOEDAS 12,5 / GAS 30 / ÁGUA 12,5);
  lançamento fake grava histórico e some das pendências; relançar funciona.
- UI headless: card renderiza, DINHEIRO 155 somente leitura, adicionar nota
  ENERGIA 10 → DINHEIRO 165, modal de revisão lista MOEDAS + 3 despesas e
  total selecionado R$ 65,00; sem `pageerror`.
- Smoke do Cloudfy falso: transferência (MOEDAS, 123,45, 27/10/2026, CAIXA ADM →
  MOEDAS) e pagamento (GAS, 30,00, vencimento/pagamento 27/10/2026, pagar conta
  ligado, categoria/conta/centro/tipo corretos).

Pendente: smoke real com credenciais para confirmar selectize/datepicker e se
algum campo obrigatório (ex.: fornecedor) precisa de configuração.

## Riscos

1. Selectize do Cloudfy pode carregar opções por consulta assíncrona; o helper
   digita filtro e espera a opção. Validar no smoke real.
2. Data em datepicker AngularJS pode exigir blur; preencher + `Tab` e conferir.
3. "Pagar conta" pode vir ligado por padrão; checar o checkbox antes de clicar.
4. Salvar pode abrir confirmação nativa; handler de diálogo aceita e guarda a
   mensagem.
5. Se o Cloudfy salvar e a resposta falhar, o registro pode não ser gravado;
   conferir no financeiro antes de relançar.
6. Execução headless: se o fornecedor for obrigatório, não há janela para
   completar; configurar `financeiro_fornecedor` e relançar.
7. O botão Salvar real usa `href=""`; se o Cloudfy não der `preventDefault`, a
   página pode recarregar. O smoke real precisa confirmar que o próximo item
   continua na mesma página.
8. Se Nr. documento/Dt. documento forem obrigatórios no Cloudfy, o formulário
   falha; avaliar preencher com um valor padrão configurável.
