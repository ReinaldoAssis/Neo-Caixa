<script lang="ts">
  import { onMount } from "svelte";
  import { ArrowLeft } from "lucide-svelte";
  import ContagemDinheiro from "./ContagemDinheiro.svelte";

  interface Props {
    tipo: "posto" | "restaurante";
    contagemId: string | null;
    onVoltar: () => void;
    onIdChange?: (id: string) => void;
  }

  let { tipo, contagemId, onVoltar, onIdChange }: Props = $props();

  let data = $state(new Date().toISOString().slice(0, 10));
  let observacoes = $state("");
  let contagens = $state<any[]>([]);
  let savedId = $state<string | null>(contagemId);
  let loading = $state(false);
  let hydrated = $state(false);
  let serial200Mode = $state<"obrigatorio_todas" | "opcional_geral" | "opcional_todas">("obrigatorio_todas");
  let contagemTabBehavior = $state<"icone" | "icone_fixo">("icone");

  let toastMessage = $state("");
  let toastTimer: ReturnType<typeof setTimeout> | null = null;
  let autosaveTimer: ReturnType<typeof setTimeout> | null = null;
  let savingInFlight = false;

  function showToast(msg: string) {
    toastMessage = msg;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toastMessage = ""), 2500);
  }

  function formatMoney(value: number): string {
    if (!value && value !== 0) return "-";
    const formatted = value.toFixed(2).replace(".", ",");
    return `R$ ${formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }

  const total = $derived(
    contagens.filter((c: any) => c.label === "Geral").reduce((s: number, c: any) => s + (c.total || 0), 0)
  );

  async function loadSettings() {
    try {
      const res = await fetch("/api/conciliador/config/settings");
      if (res.ok) {
        const s = await res.json();
        if (s.contagem_tab_behavior === "icone_fixo" || s.contagem_tab_behavior === "icone") {
          contagemTabBehavior = s.contagem_tab_behavior;
        }
        if (["obrigatorio_todas", "opcional_geral", "opcional_todas"].includes(s.serial_200_mode)) {
          serial200Mode = s.serial_200_mode;
        }
      }
    } catch {
      // keep defaults
    }
  }

  async function loadContagem(id: string) {
    loading = true;
    try {
      const res = await fetch(`/api/conciliador/conciliacoes/${id}`);
      if (res.ok) {
        const doc = await res.json();
        savedId = doc._id || doc.id;
        data = doc.data || data;
        observacoes = doc.observacoes || "";
        contagens = doc.contagens_dinheiro || [];
      }
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    await loadSettings();
    if (contagemId) {
      await loadContagem(contagemId);
    }
    hydrated = true;
  });

  function buildPayload() {
    return {
      id: savedId || undefined,
      kind: "contagem",
      tipo,
      data,
      status: "rascunho",
      observacoes,
      contagens_dinheiro: contagens,
    };
  }

  async function persistNow(): Promise<string | null> {
    if (savingInFlight) return savedId;
    savingInFlight = true;
    try {
      const res = await fetch("/api/conciliador/conciliacoes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      if (res.ok) {
        const result = await res.json();
        if (result.id && result.id !== savedId) {
          savedId = result.id;
          onIdChange?.(result.id);
        }
      }
    } catch {
      // best-effort
    } finally {
      savingInFlight = false;
    }
    return savedId;
  }

  $effect(() => {
    void data;
    void observacoes;
    void JSON.stringify(contagens);
    if (!hydrated) return;
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => { if (!savingInFlight) persistNow(); }, 800);
  });

  async function salvar() {
    loading = true;
    const id = await persistNow();
    loading = false;
    if (id) showToast("Contagem salva com sucesso.");
  }
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <button
      onclick={onVoltar}
      class="inline-flex h-8 w-8 items-center justify-center border hover:bg-accent"
      title="Voltar"
    >
      <ArrowLeft class="h-4 w-4" />
    </button>
    <h1 class="text-lg font-semibold">
      Contagem de Dinheiro - {tipo === "posto" ? "Posto" : "Restaurante"}
    </h1>
  </div>

  {#if toastMessage}
    <div class="toast-in fixed bottom-6 right-6 z-50 rounded-md bg-green-600 px-4 py-2 text-sm text-white shadow-lg">
      {toastMessage}
    </div>
  {/if}

  <div class="flex-1 overflow-auto p-4">
    <div class="mb-4 rounded-lg border p-4">
      <div class="flex items-center gap-4">
        <label class="text-sm">Data</label>
        <input
          type="date"
          bind:value={data}
          class="rounded-md border px-3 py-1.5 text-sm"
        />
        <span class="ml-auto text-sm font-semibold text-primary">Total: {formatMoney(total)}</span>
      </div>
    </div>

    <div class="mb-4 rounded-lg border p-4">
      <h3 class="mb-3 text-sm font-semibold">Contagem de Dinheiro</h3>
      <ContagemDinheiro
        readonly={false}
        bind:contagens={contagens}
        tabBehavior={contagemTabBehavior}
        serialMode={serial200Mode}
      />
    </div>

    <div class="mb-4 rounded-lg border p-4">
      <label class="mb-2 block text-sm font-semibold">Observacoes</label>
      <textarea
        bind:value={observacoes}
        rows="3"
        class="w-full rounded-md border bg-background px-3 py-2 text-sm"
      ></textarea>
    </div>
  </div>

  <div class="flex items-center gap-3 border-t px-4 py-3">
    <button
      onclick={salvar}
      disabled={loading}
      class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
    >
      Salvar
    </button>
    <span class="text-xs text-muted-foreground">Salvamento automatico ativo</span>
  </div>
</div>
