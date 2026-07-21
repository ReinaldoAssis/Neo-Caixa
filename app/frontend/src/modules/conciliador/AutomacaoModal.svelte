<script lang="ts">
  import { onMount } from "svelte";
  import { Bot, Loader2, RefreshCw } from "lucide-svelte";
  import { getCaixas, isFetched, isLoading, getError, clearError, fetchCaixas } from "./automacaoCache.svelte";

  interface Pagamento {
    tipo: string;
    bandeira: string;
    subtipo: string;
    valor_vndpos: string;
    valor_vndtef: string;
  }

  interface ImportResult {
    resumo: any;
    dinheiro: string;
    pagamentos: Pagamento[];
  }

  interface Props {
    onClose: () => void;
    onImport: (result: ImportResult) => void;
    onLancar?: (caixaIdx: number) => void;
    mode?: "importar" | "lancar";
  }

  let { onClose, onImport, onLancar, mode = "importar" }: Props = $props();

  let importing = $state(false);
  let selectedIdx = $state<number | null>(null);

  let caixas = $derived(getCaixas());
  let loading = $derived(isLoading());
  let error = $derived(getError());
  let fetched = $derived(isFetched());

  onMount(() => {
    if (!isFetched()) {
      fetchCaixas();
    }
  });

  function atualizar() {
    fetchCaixas();
  }

  async function confirmar() {
    if (selectedIdx === null) return;
    if (mode === "lancar") {
      onLancar?.(selectedIdx);
      onClose();
      return;
    }
    importing = true;
    const errMsg = getError();
    try {
      const res = await fetch("/api/conciliador/automacao/importar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caixa_idx: selectedIdx }),
      });
      if (!res.ok) {
        const err = await res.json();
        clearError();
        return;
      }
      const data = await res.json();
      onImport(data as ImportResult);
      onClose();
    } catch (e: any) {
      // silent
    } finally {
      importing = false;
    }
  }
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onclick={onClose} role="dialog">
  <div class="w-[700px] max-h-[80vh] flex flex-col rounded-lg border bg-background shadow-xl" onclick={(e) => e.stopPropagation()}>
    <div class="flex items-center justify-between border-b px-4 py-3">
      <div class="flex items-center gap-2">
        <Bot class="h-5 w-5 text-primary" />
        <h3 class="font-semibold">{mode === "lancar" ? "Auto Lancar Cloudfy" : "Automacao Cloudfy"}</h3>
      </div>
      <button onclick={onClose} class="text-muted-foreground hover:text-foreground text-lg leading-none">&times;</button>
    </div>

    <div class="flex-1 overflow-auto p-4">
      {#if loading || importing}
        <div class="mx-4 mb-3 h-1 overflow-hidden rounded bg-muted">
          <div class="h-full w-1/3 animate-progress rounded bg-primary"></div>
        </div>
      {/if}
      {#if loading}
        <div class="flex items-center justify-center gap-2 py-12">
          <Loader2 class="h-5 w-5 animate-spin text-primary" />
          <span class="text-sm text-muted-foreground">Buscando caixas no Cloudfy...</span>
        </div>
      {:else if importing}
        <div class="flex items-center justify-center gap-2 py-12">
          <Loader2 class="h-5 w-5 animate-spin text-primary" />
          <span class="text-sm text-muted-foreground">{mode === "lancar" ? "Abrindo Cloudfy..." : "Importando dados do caixa..."}</span>
        </div>
      {:else if error && caixas.length === 0}
        <div class="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
          <button class="ml-2 font-bold" onclick={clearError}>&times;</button>
        </div>
        <button
          onclick={atualizar}
          class="mt-3 inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
        >
          Tentar novamente
        </button>
      {:else}
        {#if error && caixas.length > 0}
          <div class="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">
            {error}
            <button class="ml-2 font-bold" onclick={clearError}>&times;</button>
          </div>
        {/if}
        <p class="mb-3 text-sm text-muted-foreground">
          {caixas.length} caixa(s) pendente(s). Selecione um para {mode === "lancar" ? "lancar" : "importar"}.
        </p>
        <div class="overflow-x-auto border">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b bg-muted/50 text-left">
                <th class="px-3 py-2 w-8"></th>
                <th class="px-3 py-2">Data</th>
                <th class="px-3 py-2">Caixa</th>
                <th class="px-3 py-2">Turno</th>
                <th class="px-3 py-2">Operador</th>
                <th class="px-3 py-2">Fechamento</th>
                <th class="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {#each caixas as c, i}
                <tr
                  class="border-b cursor-pointer hover:bg-accent/50"
                  class:bg-accent={selectedIdx === i}
                  onclick={() => (selectedIdx = i)}
                >
                  <td class="px-3 py-2">
                    <input type="radio" name="caixa" checked={selectedIdx === i} />
                  </td>
                  <td class="px-3 py-2">{c.data}</td>
                  <td class="px-3 py-2">{c.pdv}</td>
                  <td class="px-3 py-2">{c.turno}</td>
                  <td class="px-3 py-2">{c.movto}</td>
                  <td class="px-3 py-2 text-muted-foreground">{c.horario_fechamento || "-"}</td>
                  <td class="px-3 py-2">
                    <span class="inline-block rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">
                      {c.status}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

    {#if caixas.length > 0 && !loading && !importing}
      <div class="flex items-center justify-between border-t px-4 py-3">
        <button
          onclick={atualizar}
          disabled={loading}
          class="inline-flex h-8 items-center gap-1.5 border px-3 text-sm hover:bg-accent disabled:opacity-50"
        >
          <RefreshCw class="h-3.5 w-3.5" />
          Atualizar lista
        </button>
        <button
          onclick={confirmar}
          disabled={selectedIdx === null || importing}
          class="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {mode === "lancar" ? "Lancar selecionado" : "Importar selecionado"}
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  @keyframes progress {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(400%); }
  }
  .animate-progress {
    animation: progress 1.5s infinite;
  }
</style>
