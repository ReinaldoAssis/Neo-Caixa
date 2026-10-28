<script lang="ts">
  import { onMount } from "svelte";
  import {
    AlertTriangle,
    ArrowLeft,
    CheckCircle2,
    ChevronDown,
    ChevronUp,
    Loader2,
    Search,
    XCircle,
  } from "lucide-svelte";

  interface LinhaExtrato {
    descricao: string;
    valor: number;
    data?: string;
  }

  interface Conferencia {
    id?: string;
    doc_id?: string;
    data: string;
    executado_em: string;
    extrato_total: number;
    extrato_total_texto: string;
    linhas: LinhaExtrato[];
    soma_linhas: number;
    extrato_inconsistente: boolean;
    caixa_total: number;
    caixa_moedas?: number;
    caixa_qtd: number;
    caixa_ids: string[];
    diferenca: number | null;
    status: "bate" | "nao_bate" | "sem_caixa" | string;
  }

  interface Props {
    onVoltar: () => void;
  }

  let { onVoltar }: Props = $props();

  function localISO(offsetDays = 0): string {
    const now = new Date();
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  let data = $state(localISO(-1));
  let loading = $state(false);
  let carregandoHistorico = $state(true);
  let erro = $state("");
  let resultado = $state<Conferencia | null>(null);
  let historico = $state<Conferencia[]>([]);
  let expandida = $state<string | null>(null);

  onMount(loadHistorico);

  async function loadHistorico() {
    carregandoHistorico = true;
    try {
      const res = await fetch("/api/conciliador/conferencia-adm?limite=20");
      if (res.ok) {
        const corpo = await res.json();
        historico = corpo.historico || [];
      }
    } catch {
      // historico nao bloqueia a ferramenta
    } finally {
      carregandoHistorico = false;
    }
  }

  async function conferir() {
    if (!data) {
      erro = "Informe a data.";
      return;
    }
    loading = true;
    erro = "";
    resultado = null;
    try {
      const res = await fetch("/api/conciliador/conferencia-adm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data }),
      });
      const corpo = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(corpo.detail || "Erro ao conferir o extrato.");
      }
      resultado = corpo;
      expandida = null;
      await loadHistorico();
    } catch (e: any) {
      erro = e?.message || "Erro de conexao.";
    } finally {
      loading = false;
    }
  }

  function formatMoney(value: number): string {
    const sinal = Number(value || 0) < 0 ? "-" : "";
    const formatted = Math.abs(Number(value || 0))
      .toFixed(2)
      .replace(".", ",")
      .replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${sinal}R$ ${formatted}`;
  }

  function formatDiferenca(value: number | null | undefined): string {
    return value === null || value === undefined ? "—" : formatMoney(value);
  }

  function formatDateBR(iso: string): string {
    if (!iso) return "-";
    const [ano, mes, dia] = iso.split("-");
    return `${dia}/${mes}/${ano}`;
  }

  function formatDateTime(iso: string): string {
    if (!iso) return "-";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function chave(item: Conferencia): string {
    return String(item.id || item.doc_id || item.executado_em || item.data);
  }

  function statusLabel(status: string): string {
    if (status === "bate") return "Bate";
    if (status === "nao_bate") return "Nao bate";
    if (status === "sem_caixa") return "Sem caixa";
    return status || "-";
  }

  function statusClass(status: string): string {
    if (status === "bate") {
      return "border-green-300 bg-green-50 text-green-800";
    }
    if (status === "nao_bate") {
      return "border-red-300 bg-red-50 text-red-800";
    }
    return "border-amber-300 bg-amber-50 text-amber-800";
  }
</script>

<div class="flex h-full flex-col overflow-auto">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <button
      type="button"
      onclick={onVoltar}
      class="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-accent"
      title="Voltar"
    >
      <ArrowLeft class="h-4 w-4" />
    </button>
    <div>
      <h1 class="text-lg font-bold">Conferencia ADM</h1>
      <p class="text-sm text-muted-foreground">
        Compara o extrato CAIXA ADM com o dinheiro do caixa restaurante.
      </p>
    </div>
  </div>

  <div class="space-y-4 p-4">
    <div class="rounded-lg border p-4">
      <div class="flex flex-wrap items-end gap-3">
        <label class="text-sm">
          <span class="mb-1 block text-muted-foreground">Data da conferencia</span>
          <input
            type="date"
            bind:value={data}
            disabled={loading}
            class="rounded-md border bg-background px-3 py-1.5 text-sm"
          />
        </label>
        <button
          type="button"
          onclick={conferir}
          disabled={loading || !data}
          class="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {#if loading}
            <Loader2 class="h-4 w-4 animate-spin" />
            Conferindo...
          {:else}
            <Search class="h-4 w-4" />
            Conferir
          {/if}
        </button>
        <span class="text-xs text-muted-foreground">
          Padrao: dia anterior. Nada e alterado no Cloudfy.
        </span>
      </div>

      {#if erro}
        <div class="mt-3 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {erro}
        </div>
      {/if}
    </div>

    {#if resultado}
      {@const classe = statusClass(resultado.status)}
      <div class="rounded-lg border p-4 {classe}">
        <div class="flex items-start gap-3">
          {#if resultado.status === "bate"}
            <CheckCircle2 class="mt-0.5 h-5 w-5 shrink-0" />
          {:else if resultado.status === "nao_bate"}
            <XCircle class="mt-0.5 h-5 w-5 shrink-0" />
          {:else}
            <AlertTriangle class="mt-0.5 h-5 w-5 shrink-0" />
          {/if}
          <div class="min-w-0">
            <p class="font-semibold">
              {statusLabel(resultado.status)} — {formatDateBR(resultado.data)}
            </p>
            {#if resultado.status === "sem_caixa"}
              <p class="text-sm">
                Nenhum caixa restaurante encontrado nesta data. Extrato lido:
                {formatMoney(resultado.extrato_total)}.
              </p>
            {:else}
              <p class="text-sm">
                Extrato {formatMoney(resultado.extrato_total)} × caixa em especie
                {formatMoney(resultado.caixa_total)} = diferenca
                {formatDiferenca(resultado.diferenca)}.
              </p>
            {/if}
          </div>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-4">
        <div class="rounded-md border p-3">
          <p class="text-xs text-muted-foreground">Extrato ADM</p>
          <p class="text-lg font-semibold">{formatMoney(resultado.extrato_total)}</p>
        </div>
        <div class="rounded-md border p-3">
          <p class="text-xs text-muted-foreground">Caixa em especie (sem moedas)</p>
          <p class="text-lg font-semibold">{formatMoney(resultado.caixa_total)}</p>
          <p class="text-xs text-muted-foreground">
            {resultado.caixa_qtd} caixa(s) na data
            {#if resultado.caixa_moedas}
              · {formatMoney(resultado.caixa_moedas)} em moedas ignorado
            {/if}
          </p>
        </div>
        <div class="rounded-md border p-3">
          <p class="text-xs text-muted-foreground">Diferenca</p>
          <p class="text-lg font-semibold">{formatDiferenca(resultado.diferenca)}</p>
        </div>
        <div class="rounded-md border p-3">
          <p class="text-xs text-muted-foreground">Linhas do extrato</p>
          <p class="text-lg font-semibold">{resultado.linhas.length}</p>
          <p class="text-xs text-muted-foreground">
            Soma {formatMoney(resultado.soma_linhas)}
          </p>
        </div>
      </div>

      {#if resultado.extrato_inconsistente}
        <div class="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          Extrato inconsistente: a soma das linhas
          ({formatMoney(resultado.soma_linhas)}) nao bate com o VL_TOTAL
          ({formatMoney(resultado.extrato_total)}).
        </div>
      {/if}

      <div class="rounded-lg border">
        <div class="border-b bg-muted/40 px-3 py-2 text-sm font-semibold">
          Linhas do extrato
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b text-left text-muted-foreground">
              <th class="px-3 py-2 font-medium">Descricao</th>
              <th class="px-3 py-2 text-right font-medium">Valor</th>
            </tr>
          </thead>
          <tbody>
            {#each resultado.linhas as linha}
              <tr class="border-t">
                <td class="px-3 py-1.5">{linha.descricao}</td>
                <td class="px-3 py-1.5 text-right tabular-nums">
                  {formatMoney(linha.valor)}
                </td>
              </tr>
            {:else}
              <tr>
                <td colspan="2" class="px-3 py-3 text-muted-foreground">
                  Nenhuma linha no extrato.
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <div class="rounded-lg border">
      <div class="flex items-center justify-between border-b bg-muted/40 px-3 py-2">
        <span class="text-sm font-semibold">Historico recente</span>
        <button
          type="button"
          onclick={loadHistorico}
          disabled={carregandoHistorico}
          class="text-xs text-primary hover:underline disabled:opacity-50"
        >
          Atualizar
        </button>
      </div>
      {#if carregandoHistorico}
        <p class="px-3 py-4 text-sm text-muted-foreground">Carregando...</p>
      {:else if historico.length === 0}
        <p class="px-3 py-4 text-sm text-muted-foreground">
          Nenhuma conferencia registrada.
        </p>
      {:else}
        <div class="divide-y">
          {#each historico as item (chave(item))}
            {@const aberta = expandida === chave(item)}
            <div>
              <button
                type="button"
                onclick={() => (expandida = aberta ? null : chave(item))}
                class="flex w-full flex-wrap items-center gap-2 px-3 py-2 text-left hover:bg-accent"
              >
                <span class="text-sm font-medium">{formatDateBR(item.data)}</span>
                <span class="text-xs text-muted-foreground">
                  {formatDateTime(item.executado_em)}
                </span>
                <span class="rounded px-2 py-0.5 text-[10px] font-medium {statusClass(item.status)}">
                  {statusLabel(item.status)}
                </span>
                <span class="ml-auto text-xs text-muted-foreground">
                  Extrato {formatMoney(item.extrato_total)} · Caixa
                  {formatMoney(item.caixa_total)} · Dif.
                  {formatDiferenca(item.diferenca)}
                </span>
                {#if aberta}
                  <ChevronUp class="h-4 w-4" />
                {:else}
                  <ChevronDown class="h-4 w-4" />
                {/if}
              </button>
              {#if aberta}
                <div class="border-t bg-muted/20 px-3 py-2">
                  {#if item.extrato_inconsistente}
                    <p class="mb-2 text-xs text-amber-700">
                      Soma das linhas {formatMoney(item.soma_linhas)} difere do
                      VL_TOTAL {formatMoney(item.extrato_total)}.
                    </p>
                  {/if}
                  <table class="w-full text-xs">
                    <tbody>
                      {#each item.linhas as linha}
                        <tr class="border-b last:border-b-0">
                          <td class="py-1">{linha.descricao}</td>
                          <td class="py-1 text-right tabular-nums">
                            {formatMoney(linha.valor)}
                          </td>
                        </tr>
                      {:else}
                        <tr>
                          <td class="py-1 text-muted-foreground">
                            Sem linhas salvas.
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>
