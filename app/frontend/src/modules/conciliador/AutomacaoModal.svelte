<script lang="ts">
  import { Bot, Loader2 } from "lucide-svelte";

  interface CaixaItem {
    data: string;
    pdv: string;
    turno: string;
    movto: string;
    status: string;
    row_index: number;
  }

  interface Pagamento {
    tipo: string;
    bandeira: string;
    subtipo: string;
    valor_vndpos: string;
    valor_vndtef: string;
  }

  interface ImportResult {
    resumo: CaixaItem;
    dinheiro: string;
    pagamentos: Pagamento[];
  }

  interface Props {
    onClose: () => void;
    onImport: (result: ImportResult) => void;
  }

  let { onClose, onImport }: Props = $props();

  let loading = $state(false);
  let importing = $state(false);
  let error = $state("");
  let caixas = $state<CaixaItem[]>([]);
  let selectedIdx = $state<number | null>(null);

  async function listar() {
    loading = true;
    error = "";
    caixas = [];
    try {
      const res = await fetch("/api/conciliador/automacao/listar", { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        error = err.detail || "Erro ao listar caixas.";
        return;
      }
      const data = await res.json();
      caixas = data.caixas || [];
      if (caixas.length === 0) {
        error = "Nenhum caixa pendente encontrado.";
      }
    } catch (e: any) {
      error = e.message || "Erro de conexao.";
    } finally {
      loading = false;
    }
  }

  async function importar() {
    if (selectedIdx === null) return;
    importing = true;
    error = "";
    try {
      const res = await fetch("/api/conciliador/automacao/importar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caixa_idx: selectedIdx }),
      });
      if (!res.ok) {
        const err = await res.json();
        error = err.detail || "Erro ao importar caixa.";
        return;
      }
      const data = await res.json();
      onImport(data as ImportResult);
      onClose();
    } catch (e: any) {
      error = e.message || "Erro de conexao.";
    } finally {
      importing = false;
    }
  }
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onclick={onClose} role="dialog">
  <div class="w-[640px] max-h-[80vh] flex flex-col rounded-lg border bg-background shadow-xl" onclick={(e) => e.stopPropagation()}>
    <div class="flex items-center justify-between border-b px-4 py-3">
      <div class="flex items-center gap-2">
        <Bot class="h-5 w-5 text-primary" />
        <h3 class="font-semibold">Automacao Cloudfy</h3>
      </div>
      <button onclick={onClose} class="text-muted-foreground hover:text-foreground">&times;</button>
    </div>

    <div class="flex-1 overflow-auto p-4">
      {#if !caixas.length && !loading && !error}
        <div class="flex flex-col items-center gap-3 py-8">
          <Bot class="h-10 w-10 text-muted-foreground" />
          <p class="text-sm text-muted-foreground">
            Clique em "Buscar caixas" para listar os caixas pendentes no Cloudfy.
          </p>
          <button
            onclick={listar}
            class="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90"
          >
            Buscar caixas
          </button>
        </div>
      {:else if loading}
        <div class="flex items-center justify-center gap-2 py-12">
          <Loader2 class="h-5 w-5 animate-spin text-primary" />
          <span class="text-sm text-muted-foreground">Buscando caixas no Cloudfy...</span>
        </div>
      {:else if importing}
        <div class="flex items-center justify-center gap-2 py-12">
          <Loader2 class="h-5 w-5 animate-spin text-primary" />
          <span class="text-sm text-muted-foreground">Importando dados do caixa...</span>
        </div>
      {:else if error}
        <div class="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
          <button class="ml-2 font-bold" onclick={() => (error = "")}>&times;</button>
        </div>
        <button
          onclick={listar}
          class="mt-3 inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
        >
          Tentar novamente
        </button>
      {:else}
        <p class="mb-3 text-sm text-muted-foreground">
          {caixas.length} caixa(s) pendente(s). Selecione um para importar.
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
          onclick={listar}
          class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
        >
          Atualizar lista
        </button>
        <button
          onclick={importar}
          disabled={selectedIdx === null}
          class="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          Importar selecionado
        </button>
      </div>
    {/if}
  </div>
</div>
