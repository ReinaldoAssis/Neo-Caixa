<script lang="ts">
  import { onMount } from "svelte";
  import { Calculator } from "lucide-svelte";
  import Select from "./Select.svelte";

  interface Props {
    tipo: "posto" | "restaurante";
    onNovo: () => void;
    onAbrir: (id: string) => void;
    onNovaContagem: () => void;
    onAbrirContagem: (id: string) => void;
  }

  let { tipo, onNovo, onAbrir, onNovaContagem, onAbrirContagem }: Props = $props();

  let conciliacoes = $state<any[]>([]);
  let search = $state("");
  let statusFilter = $state("ativos");
  let loading = $state(true);

  onMount(() => {
    load();
  });

  async function load() {
    loading = true;
    try {
      const params = new URLSearchParams();
      params.set("tipo", tipo);
      if (statusFilter === "ativos") params.set("status", "ativos");
      else if (statusFilter !== "todos") params.set("status", statusFilter);
      if (search) params.set("data", search);

      const res = await fetch(`/api/conciliador/conciliacoes?${params.toString()}`);
      if (res.ok) {
        conciliacoes = await res.json();
      }
    } catch {
      conciliacoes = [];
    } finally {
      loading = false;
    }
  }

  function formatMoney(value: number): string {
    if (!value) return "-";
    const formatted = value.toFixed(2).replace(".", ",");
    return `R$ ${formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }

  function formatDate(iso: string): string {
    if (!iso) return "-";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }

  function turnoStr(turno: number | null): string {
    if (turno === 1) return "T1";
    if (turno === 2) return "T2";
    return "-";
  }

  function statusLabel(st: string): string {
    const labels: Record<string, string> = {
      rascunho: "rascunho", conciliado: "conciliado", arquivado: "arquivado",
    };
    return labels[st] || st;
  }

  async function excluir(id: string) {
    if (!confirm("Tem certeza que deseja EXCLUIR esta conciliacao?")) return;
    await fetch(`/api/conciliador/conciliacoes/${id}`, { method: "DELETE" });
    load();
  }

  async function arquivar(id: string) {
    await fetch(`/api/conciliador/conciliacoes/${id}/arquivar`, { method: "POST" });
    load();
  }

  async function restaurar(id: string) {
    await fetch(`/api/conciliador/conciliacoes/${id}/restaurar`, { method: "POST" });
    load();
  }

  function openItem(item: any) {
    if (item.status === "arquivado") {
      alert("Este caixa esta arquivado. Restaure-o para editar.");
      return;
    }
    const id = item._id || item.id || item.doc_id;
    if (item.kind === "contagem") {
      onAbrirContagem(String(id));
    } else {
      onAbrir(String(id));
    }
  }
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <h1 class="text-lg font-bold">
      {tipo === "posto" ? "Posto - Historico" : "Restaurante - Historico"}
    </h1>
    <button
      onclick={onNovo}
      class="ml-auto inline-flex h-8 items-center rounded-md bg-primary px-3 text-sm text-primary-foreground hover:bg-primary/90"
    >
      + Novo
    </button>
    <button
      onclick={onNovaContagem}
      class="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-accent"
      title="Nova contagem de dinheiro (sem caixa)"
    >
      <Calculator class="h-4 w-4" />
    </button>
  </div>

  <div class="flex flex-wrap items-center gap-3 border-b px-4 py-3">
    <label class="text-sm">Data</label>
    <input
      type="date"
      bind:value={search}
      class="rounded-md border bg-background px-3 py-1.5 text-sm"
    />
    <label class="ml-2 text-sm">Status</label>
    <Select bind:value={statusFilter}>
      <option value="ativos">Ativos</option>
      <option value="todos">Todos</option>
      <option value="rascunho">Rascunho</option>
      <option value="conciliado">Conciliado</option>
      <option value="arquivado">Arquivado</option>
    </Select>
    <button
      onclick={load}
      class="inline-flex h-8 items-center rounded-md border px-3 text-sm hover:bg-accent"
    >
      Buscar
    </button>
  </div>

  <div class="flex-1 overflow-auto">
    {#if loading}
      <div class="flex h-full items-center justify-center">
        <p class="text-muted-foreground">Carregando...</p>
      </div>
    {:else if conciliacoes.length === 0}
      <div class="flex h-full items-center justify-center">
        <p class="text-muted-foreground">Nenhuma conciliacao encontrada</p>
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead>
          <tr class="sticky top-0 border-b bg-muted/50 text-left">
            <th class="px-4 py-2">Data</th>
            {#if tipo === "restaurante"}
              <th class="px-4 py-2">Turno</th>
            {/if}
            <th class="px-4 py-2 text-right">Valor Sistema</th>
            <th class="px-4 py-2 text-right">Valor {tipo === "restaurante" ? "Real" : "Site"}</th>
            {#if tipo === "restaurante"}
              <th class="px-4 py-2 text-right">Dinheiro</th>
              <th class="px-4 py-2 text-right">Moedas</th>
            {/if}
            <th class="px-4 py-2 text-right">Diferenca</th>
            <th class="px-4 py-2">Status</th>
            <th class="px-4 py-2 text-right">Acoes</th>
          </tr>
        </thead>
        <tbody>
          {#each conciliacoes as item}
            {@const isArchived = item.status === "arquivado"}
            <tr
              class="cursor-pointer border-b hover:bg-accent/50"
              class:text-muted-foreground={isArchived}
              ondblclick={() => openItem(item)}
            >
              <td class="px-4 py-2">
                {formatDate(item.data)}
                {#if item.kind === "contagem"}
                  <span class="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">contagem</span>
                {/if}
              </td>
              {#if tipo === "restaurante"}
                <td class="px-4 py-2">{item.kind === "contagem" ? "-" : turnoStr(item.turno)}</td>
              {/if}
              <td class="px-4 py-2 text-right">{formatMoney(item.total_sistema)}</td>
              <td class="px-4 py-2 text-right">
                {tipo === "restaurante" ? formatMoney(item.total_real) : formatMoney(item.total_site)}
              </td>
              {#if tipo === "restaurante"}
                <td class="px-4 py-2 text-right">{formatMoney(item.dinheiro_notas || 0)}</td>
                <td class="px-4 py-2 text-right">{formatMoney(item.dinheiro_moedas || 0)}</td>
              {/if}
              <td class="px-4 py-2 text-right">
                <span class={(item.diferenca_total ?? 0) >= -0.005 ? "text-primary" : "text-red-600"}>
                  {formatMoney(item.diferenca_total)}
                </span>
              </td>
              <td class="px-4 py-2">{statusLabel(item.status)}</td>
              <td class="px-4 py-2 text-right">
                <div class="flex justify-end gap-1">
                  <button
                    onclick={() => openItem(item)}
                    class="rounded px-2 py-0.5 text-xs hover:bg-accent"
                  >
                    Abrir
                  </button>
                  {#if !isArchived}
                    <button
                      onclick={() => arquivar(item._id || item.id || item.doc_id)}
                      class="rounded px-2 py-0.5 text-xs hover:bg-accent"
                    >
                      Arquivar
                    </button>
                  {:else}
                    <button
                      onclick={() => restaurar(item._id || item.id || item.doc_id)}
                      class="rounded px-2 py-0.5 text-xs hover:bg-accent"
                    >
                      Restaurar
                    </button>
                  {/if}
                  <button
                    onclick={() => excluir(item._id || item.id || item.doc_id)}
                    class="rounded px-2 py-0.5 text-xs text-red-600 hover:bg-red-50"
                  >
                    Excluir
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <div class="border-t px-4 py-2 text-sm text-muted-foreground">
    {conciliacoes.length} registro(s) exibido(s)
  </div>
</div>
