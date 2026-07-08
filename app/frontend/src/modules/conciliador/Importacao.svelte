<script lang="ts">
  import { onMount } from "svelte";
  import ContagemDinheiro from "./ContagemDinheiro.svelte";
  import Select from "./Select.svelte";

  interface Props {
    tipo: "posto" | "restaurante";
    conciliacaoId: string | null;
    onVoltar: () => void;
    onResultado: (c: any) => void;
    onSalvo: () => void;
  }

  let { tipo, conciliacaoId, onVoltar, onResultado, onSalvo }: Props = $props();

  let postoCategories = $state<string[]>([
    "PREMMIA_CARTAO", "PREMMIA_PIX", "PREMMIA_VALE", "PREMMIA_CUPOM",
    "FITCARD", "PAG_PIX", "AMEX", "ELO_CREDITO", "ELO_DEBITO",
    "MASTERCARD_CREDITO", "MASTERCARD_DEBITO", "VISA_CREDITO", "VISA_DEBITO",
  ]);
  let postoLabels = $state<Record<string, string>>({
    PREMMIA_CARTAO: "PREMMIA CARTAO", PREMMIA_PIX: "PREMMIA PIX",
    PREMMIA_VALE: "PREMMIA VALE", PREMMIA_CUPOM: "PREMMIA CUPOM",
    FITCARD: "FITCARD", PAG_PIX: "PAG PIX", AMEX: "AMERICAN EXP",
    ELO_CREDITO: "ELO CREDITO", ELO_DEBITO: "ELO DEBITO",
    MASTERCARD_CREDITO: "MASTERCARD CREDITO", MASTERCARD_DEBITO: "MASTERCARD DEBITO",
    VISA_CREDITO: "VISA CREDITO", VISA_DEBITO: "VISA DEBITO",
  });

  async function loadPostoConfig() {
    try {
      const res = await fetch("/api/conciliador/config/posto");
      if (res.ok) {
        const cfg = await res.json();
        if (Array.isArray(cfg.categorias) && cfg.categorias.length) {
          postoCategories = cfg.categorias;
          postoLabels = cfg.labels || {};
        }
      }
    } catch {
      // keep defaults
    }
  }

  const restCategories = [
    "PIX", "ELO_DEBITO", "MAESTRO", "VC_ELECTRON", "AMEX",
    "ELO_CR", "MASTERCARD", "VISA", "DINHEIRO",
  ];
  const restLabels: Record<string, string> = {
    PIX: "PIX", ELO_DEBITO: "ELO DEBITO", MAESTRO: "MAESTRO",
    VC_ELECTRON: "VC ELECTRON", AMEX: "AMEX", ELO_CR: "ELO CR",
    MASTERCARD: "MASTERCARD", VISA: "VISA", DINHEIRO: "DINHEIRO",
  };
  const restClassif: Record<string, string> = {
    PIX: "DEBITO", ELO_DEBITO: "DEBITO", MAESTRO: "DEBITO",
    VC_ELECTRON: "DEBITO", AMEX: "CREDITO", ELO_CR: "CREDITO",
    MASTERCARD: "CREDITO", VISA: "CREDITO", DINHEIRO: "DINHEIRO",
  };

  let data = $state(new Date().toISOString().slice(0, 10));
  let status = $state("rascunho");
  let readonly = $derived(status === "conciliado");
  let turno = $state("Todos");

  let categorias = $state<Record<string, { sistema: number; site?: number; real?: number }>>({});
  let sistemaVars = $state<Record<string, string>>({});

  let fitcardTotal = $state("");
  let sangria = $state(0);
  let notasPrazo = $state(0);
  let despesas = $state(0);

  let contagensDinheiro = $state<any[]>([]);
  let lancamentosAvulsos = $state<any[]>([]);
  let observacoes = $state("");

  let loading = $state(false);
  let errorMessage = $state("");
  let statusCaixa = $state("");
  let statusPagbank = $state("");
  let statusPremmia = $state("");
  let statusRestPagbank = $state("");

  let savedId = $state<string | null>(null);

  // Time range modal for restaurante
  let showTimeModal = $state(false);
  let timeModalHoraIni = $state("");
  let timeModalHoraFim = $state("");
  let pendingFile: File | null = null;
  let timeModalPromise = $state<{ resolve: (v: { ini: string; fim: string } | null) => void } | null>(null);

  function askTimeRange(file: File): Promise<{ ini: string; fim: string } | null> {
    return new Promise((resolve) => {
      pendingFile = file;
      timeModalHoraIni = "";
      timeModalHoraFim = "";
      timeModalPromise = { resolve };
      showTimeModal = true;
    });
  }

  function confirmTimeRange() {
    const ini = timeModalHoraIni.trim();
    const fim = timeModalHoraFim.trim();
    if (!ini || !fim) { errorMessage = "Informe ambos os horarios"; return; }
    if (!/^\d{2}:\d{2}$/.test(ini) || !/^\d{2}:\d{2}$/.test(fim)) {
      errorMessage = "Formato invalido. Use hh:mm";
      return;
    }
    showTimeModal = false;
    timeModalPromise?.resolve({ ini, fim });
    timeModalPromise = null;
  }

  function cancelTimeRange() {
    showTimeModal = false;
    timeModalPromise?.resolve(null);
    timeModalPromise = null;
    pendingFile = null;
  }

  function formatHora(val: string) {
    const digits = val.replace(/\D/g, "").slice(0, 4);
    if (digits.length >= 3) return digits.slice(0, 2) + ":" + digits.slice(2);
    return digits;
  }

  $effect(() => {
    if (conciliacaoId) {
      savedId = conciliacaoId;
    }
  });

  onMount(async () => {
    if (tipo === "posto") {
      await loadPostoConfig();
    }
    initCategories();
    if (conciliacaoId) {
      loadConciliacao(conciliacaoId);
    }
  });

  function initCategories() {
    const cats: Record<string, any> = {};
    if (tipo === "restaurante") {
      for (const key of restCategories) {
        cats[key] = { sistema: 0, real: 0 };
        sistemaVars[key] = "";
      }
    } else {
      for (const key of postoCategories) {
        cats[key] = { sistema: 0, site: 0 };
      }
    }
    categorias = cats;
  }

  async function loadConciliacao(id: string) {
    loading = true;
    try {
      const res = await fetch(`/api/conciliador/conciliacoes/${id}`);
      if (!res.ok) throw new Error("Nao encontrada");
      const doc = await res.json();
      savedId = doc._id || doc.id;
      data = doc.data || "";
      status = doc.status || "rascunho";
      categorias = doc.categorias || {};
      contagensDinheiro = doc.contagens_dinheiro || [];
      lancamentosAvulsos = doc.lancamentos_avulsos || [];
      observacoes = doc.observacoes || "";

      if (tipo === "posto") {
        fitcardTotal = doc.fitcard_total ? String(doc.fitcard_total).replace(".", ",") : "";
        sangria = doc.sangria || 0;
        notasPrazo = doc.notas_a_prazo || 0;
        despesas = doc.despesas || 0;
        initPostoSistemaVars();
      } else {
        turno = doc.turno === 1 ? "T1" : doc.turno === 2 ? "T2" : "Todos";
        initRestSistemaVars();
        initRestRealLabels();
      }
    } catch (e: any) {
      errorMessage = e.message;
    } finally {
      loading = false;
    }
  }

  function initPostoSistemaVars() {
    for (const key of postoCategories) {
      const val = categorias[key]?.sistema || 0;
      sistemaVars[key] = val ? String(val).replace(".", ",") : "";
    }
  }

  function initRestSistemaVars() {
    for (const key of restCategories) {
      const val = categorias[key]?.sistema || 0;
      sistemaVars[key] = val ? String(val).replace(".", ",") : "";
    }
  }

  function initRestRealLabels() {}

  function parseMoney(text: string): number {
    if (!text || !text.trim()) return 0;
    let cleaned = text.replace("R$", "").replace(/\s/g, "").trim();
    cleaned = cleaned.replace(/[^\d,.\-]/g, "");
    if (cleaned.includes(",")) {
      cleaned = cleaned.replace(/\./g, "").replace(",", ".");
    }
    const val = parseFloat(cleaned);
    return isNaN(val) ? 0 : Math.round(val * 100) / 100;
  }

  function formatMoney(value: number): string {
    const formatted = value.toFixed(2).replace(".", ",");
    return `R$ ${formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }

  function formatReal(variavel: string) {
    const v = formatMoney(variavel);
    return v.replace(".", ",");
  }

  // File uploads
  async function uploadFile(endpoint: string, file: File): Promise<any> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`/api/conciliador${endpoint}`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Erro na importacao");
    }
    return res.json();
  }

  async function handleCaixaUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    loading = true;
    try {
      const result = await uploadFile("/parser/caixa", file);
      statusCaixa = `${result.total_saidas ? formatMoney(result.total_saidas) : ""} - detectado`;
      for (const key of postoCategories) {
        categorias[key].sistema = result.categorias?.[key]?.sistema || 0;
      }
      sangria = result.sangria || 0;
      notasPrazo = result.notas_a_prazo || 0;
      despesas = result.despesas || 0;
      initPostoSistemaVars();
    } catch (e: any) {
      errorMessage = e.message;
    } finally {
      loading = false;
    }
  }

  async function handlePagbankUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    loading = true;
    try {
      const result = await uploadFile("/parser/pagbank", file);
      statusPagbank = `${result.registros_aprovados} registros aprovados`;
      for (const key of postoCategories) {
        categorias[key].site = result.categorias?.[key]?.site || 0;
      }
    } catch (e: any) {
      errorMessage = e.message;
    } finally {
      loading = false;
    }
  }

  async function handlePremmiaUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    loading = true;
    try {
      const result = await uploadFile("/parser/premmia", file);
      statusPremmia = `Formato ${result.formato}. ${result.transacoes_processadas} transacoes`;
      for (const key of postoCategories) {
        if (result.categorias?.[key]?.site) {
          categorias[key].site = (categorias[key].site || 0) + result.categorias[key].site;
        }
      }
    } catch (e: any) {
      errorMessage = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleRestPagbankUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    let horaIni: string | null = null;
    let horaFim: string | null = null;

    if (turno === "T1" || turno === "T2") {
      const range = await askTimeRange(file);
      if (!range) { input.value = ""; return; }
      horaIni = range.ini;
      horaFim = range.fim;
    }

    loading = true;
    try {
      const params = new URLSearchParams();
      if (horaIni) params.set("hora_ini", horaIni);
      if (horaFim) params.set("hora_fim", horaFim);
      const qs = params.toString();
      const endpoint = `/parser/pagbank-restaurante${qs ? "?" + qs : ""}`;
      const result = await uploadFile(endpoint, file);
      statusRestPagbank = `${result.registros_aprovados} registros aprovados`;
      for (const key of restCategories) {
        if (key === "DINHEIRO") continue;
        categorias[key].real = result.categorias?.[key]?.real || 0;
      }
    } catch (e: any) {
      errorMessage = e.message;
    } finally {
      loading = false;
    }
  }

  function handleFitcardChange(e: Event) {
    fitcardTotal = (e.target as HTMLInputElement).value;
    const val = parseMoney(fitcardTotal);
    if (tipo === "posto") {
      categorias["FITCARD"] = { ...categorias["FITCARD"], sistema: categorias["FITCARD"].sistema, site: val };
    }
  }

  function handleRestSistemaChange(key: string, e: Event) {
    sistemaVars[key] = (e.target as HTMLInputElement).value;
    const val = parseMoney(sistemaVars[key]);
    categorias[key] = { ...categorias[key], sistema: val };
    categorias = categorias; // trigger reactivity
  }

  function getRestDiff(key: string): number {
    const real = categorias[key]?.real || 0;
    const sistema = categorias[key]?.sistema || 0;
    return Math.round((real - sistema) * 100) / 100;
  }

  function getRestTotalDiff(): number {
    let total = 0;
    for (const key of restCategories) {
      total += getRestDiff(key);
    }
    return Math.round(total * 100) / 100;
  }

  function handleContagemChange() {
    if (tipo === "restaurante") {
      const geral = contagensDinheiro.find((c: any) => c.label === "Geral");
      const dinheiroReal = geral?.total || 0;
      categorias["DINHEIRO"] = { ...categorias["DINHEIRO"], sistema: categorias["DINHEIRO"].sistema, real: dinheiroReal };
      categorias = categorias;
    }
  }

  // Lancamentos avulsos
  let avulsoTipo = $state("RECEITA");
  let avulsoColuna = $state("sistema");
  let avulsoDesc = $state("");
  let avulsoValor = $state("");
  let avulsoCat = $state("");
  let avulsoNovaCat = $state("");
  let showNovaCat = $state(false);

  $effect(() => {
    if (avulsoCat === "Nova categoria...") {
      showNovaCat = true;
    } else {
      showNovaCat = false;
      avulsoNovaCat = "";
    }
  });

  function addAvulso() {
    const valor = parseMoney(avulsoValor);
    if (valor <= 0) { errorMessage = "Valor deve ser maior que zero"; return; }
    if (avulsoCat === "Nova categoria...") {
      if (!avulsoNovaCat.trim()) { errorMessage = "Informe o nome da nova categoria"; return; }
      lancamentosAvulsos = [...lancamentosAvulsos, {
        id: crypto.randomUUID(),
        descricao: avulsoDesc,
        valor,
        tipo: avulsoTipo,
        coluna: avulsoColuna,
        categoria_vinculada: null,
        categoria_nova: avulsoNovaCat.toUpperCase(),
      }];
    } else {
      let key = avulsoCat;
      if (tipo === "posto") {
        const entry = Object.entries(postoLabels).find(([, v]) => v === avulsoCat);
        if (entry) key = entry[0];
      } else {
        const entry = Object.entries(restLabels).find(([, v]) => v === avulsoCat);
        if (entry) key = entry[0];
      }
      lancamentosAvulsos = [...lancamentosAvulsos, {
        id: crypto.randomUUID(),
        descricao: avulsoDesc,
        valor,
        tipo: avulsoTipo,
        coluna: avulsoColuna,
        categoria_vinculada: key,
        categoria_nova: null,
      }];
    }
    avulsoDesc = "";
    avulsoValor = "";
  }

  function removeAvulso(idx: number) {
    lancamentosAvulsos = lancamentosAvulsos.filter((_, i) => i !== idx);
  }

  function getCatLabel(cat: any): string {
    if (cat.categoria_vinculada) {
      if (tipo === "posto") return postoLabels[cat.categoria_vinculada] || cat.categoria_vinculada;
      return restLabels[cat.categoria_vinculada] || cat.categoria_vinculada;
    }
    return cat.categoria_nova || "(nova)";
  }

  async function saveDraft() {
    loading = true;
    const payload = buildPayload("rascunho");
    try {
      const method = savedId ? "POST" : "POST";
      const res = await fetch("/api/conciliador/conciliacoes", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Erro ao salvar");
      const result = await res.json();
      savedId = result.id;
      onSalvo();
    } catch (e: any) {
      errorMessage = e.message;
    } finally {
      loading = false;
    }
  }

  function buildPayload(st: string) {
    const base: any = {
      id: savedId || undefined,
      data,
      status: st,
      tipo,
      categorias,
      contagens_dinheiro: contagensDinheiro,
      lancamentos_avulsos: lancamentosAvulsos,
      observacoes,
    };
    if (tipo === "posto") {
      base.fitcard_total = parseMoney(fitcardTotal);
      base.sangria = sangria;
      base.notas_a_prazo = notasPrazo;
      base.despesas = despesas;
    } else {
      base.turno = turno === "T1" ? 1 : turno === "T2" ? 2 : null;
    }
    return base;
  }

  function verResultado() {
    const payload = buildPayload(status === "conciliado" ? "conciliado" : "rascunho");
    onResultado(payload);
  }

  const catOptions = $derived(tipo === "posto"
    ? postoCategories.map(k => postoLabels[k]).concat(["Nova categoria..."])
    : restCategories.map(k => restLabels[k]).concat(["Nova categoria..."]));
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <button
      onclick={onVoltar}
      class="inline-flex h-8 items-center rounded-md border px-3 text-sm hover:bg-accent"
    >
      Voltar ao Historico
    </button>
    <h1 class="text-lg font-semibold">
      {readonly ? "Caixa Conciliado" : "Caixa em Edicao"} - {tipo === "posto" ? "Posto" : "Restaurante"}
    </h1>
    {#if readonly}
      <button
        onclick={async () => {
          if (savedId) {
            const res = await fetch(`/api/conciliador/conciliacoes/${savedId}/restaurar`, { method: "POST" });
            if (res.ok) { status = "rascunho"; }
          }
        }}
        class="ml-auto inline-flex h-8 items-center rounded-md bg-primary px-3 text-sm text-primary-foreground"
      >
        Reabrir para edicao
      </button>
    {/if}
  </div>

  {#if errorMessage}
    <div class="mx-4 mt-3 rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
      {errorMessage}
      <button class="ml-2 font-bold" onclick={() => (errorMessage = "")}>x</button>
    </div>
  {/if}

  {#if loading}
    <div class="mx-4 mt-2 h-1 w-full overflow-hidden rounded bg-muted">
      <div class="h-full w-1/3 animate-progress rounded bg-primary"></div>
    </div>
  {/if}

  <!-- Time Range Modal -->
  {#if showTimeModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onclick={cancelTimeRange}>
      <div class="w-96 rounded-lg border bg-background p-6 shadow-xl" onclick={(e) => e.stopPropagation()}>
        <h3 class="mb-4 text-sm font-semibold">Horario de Importacao - {turno}</h3>
        <p class="mb-4 text-sm text-muted-foreground">{turno} - Informe o intervalo de horario:</p>
        <div class="space-y-3">
          <div class="flex items-center gap-3">
            <label class="w-28 text-sm">Horario Inicial</label>
            <input
              type="text"
              value={timeModalHoraIni}
              oninput={(e) => { timeModalHoraIni = formatHora((e.target as HTMLInputElement).value); }}
              placeholder="hh:mm"
              class="w-24 rounded-md border bg-background px-3 py-1.5 text-sm"
            />
          </div>
          <div class="flex items-center gap-3">
            <label class="w-28 text-sm">Horario Final</label>
            <input
              type="text"
              value={timeModalHoraFim}
              oninput={(e) => { timeModalHoraFim = formatHora((e.target as HTMLInputElement).value); }}
              placeholder="hh:mm"
              class="w-24 rounded-md border bg-background px-3 py-1.5 text-sm"
            />
          </div>
        </div>
        <div class="mt-6 flex justify-end gap-3">
          <button
            onclick={cancelTimeRange}
            class="inline-flex h-8 items-center rounded-md border px-3 text-sm hover:bg-accent"
          >
            Cancelar
          </button>
          <button
            onclick={confirmTimeRange}
            class="inline-flex h-8 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90"
          >
            Confirmar
          </button>
        </div>
      </div>
    </div>
  {/if}

  <div class="flex-1 overflow-auto p-4">
    <!-- Date -->
    <div class="mb-4 rounded-lg border p-4">
      <h3 class="mb-3 text-sm font-semibold">A - Data da Conciliacao</h3>
      <div class="flex items-center gap-4">
        <label class="text-sm">Data</label>
        <input
          type="date"
          bind:value={data}
          disabled={readonly}
          class="rounded-md border px-3 py-1.5 text-sm"
        />
        {#if tipo === "restaurante"}
          <label class="ml-4 text-sm">Turno</label>
          <Select bind:value={turno} disabled={readonly}>
            <option>T1</option>
            <option>T2</option>
            <option>Todos</option>
          </Select>
        {/if}
      </div>
    </div>

    {#if tipo === "posto"}
      <!-- Posto: Caixa CSV -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">B - Relatorio do Sistema Interno (CAIXA CSV)</h3>
        <div class="flex items-center gap-3">
          <span class="flex-1 text-sm text-muted-foreground">{statusCaixa || "Nenhum arquivo importado"}</span>
          <input type="file" accept=".csv" onchange={handleCaixaUpload} disabled={readonly} class="hidden" id="caixa-file" />
          <label for="caixa-file" class="inline-flex h-8 cursor-pointer items-center rounded-md border px-3 text-sm hover:bg-accent">
            Selecionar Arquivo
          </label>
          <button
            disabled={readonly}
            onclick={() => { statusCaixa = "Nenhum arquivo importado"; for (const k of postoCategories) categorias[k].sistema = 0; }}
            class="inline-flex h-8 items-center rounded-md border px-3 text-sm hover:bg-accent"
          >
            Remover
          </button>
        </div>
      </div>

      <!-- Posto: PagBank CSV -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">C - Relatorio PagBank (CSV)</h3>
        <div class="flex items-center gap-3">
          <span class="flex-1 text-sm text-muted-foreground">{statusPagbank || "Nenhum arquivo importado"}</span>
          <input type="file" accept=".csv" onchange={handlePagbankUpload} disabled={readonly} class="hidden" id="pagbank-file" />
          <label for="pagbank-file" class="inline-flex h-8 cursor-pointer items-center rounded-md border px-3 text-sm hover:bg-accent">
            Selecionar Arquivo
          </label>
          <button
            disabled={readonly}
            onclick={() => { statusPagbank = "Nenhum arquivo importado"; for (const k of postoCategories) categorias[k].site = 0; }}
            class="inline-flex h-8 items-center rounded-md border px-3 text-sm hover:bg-accent"
          >
            Remover
          </button>
        </div>
      </div>

      <!-- Posto: FitCard -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">D - FitCard</h3>
        <label class="text-sm">Valor total do FitCard (lado do site):</label>
        <input
          type="text"
          value={fitcardTotal}
          oninput={handleFitcardChange}
          disabled={readonly}
          placeholder="0,00"
          class="ml-3 rounded-md border px-3 py-1.5 text-sm"
        />
      </div>

      <!-- Posto: Premmia -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">E - Relatorio Premmia (XLS)</h3>
        <div class="flex items-center gap-3">
          <span class="flex-1 text-sm text-muted-foreground">{statusPremmia || "Nenhum arquivo importado"}</span>
          <input type="file" accept=".xls,.XLS,.csv" onchange={handlePremmiaUpload} disabled={readonly} class="hidden" id="premmia-file" />
          <label for="premmia-file" class="inline-flex h-8 cursor-pointer items-center rounded-md border px-3 text-sm hover:bg-accent">
            Selecionar Arquivo
          </label>
          <button
            disabled={readonly}
            onclick={() => { statusPremmia = "Nenhum arquivo importado"; for (const k of postoCategories) categorias[k].site = 0; }}
            class="inline-flex h-8 items-center rounded-md border px-3 text-sm hover:bg-accent"
          >
            Remover
          </button>
        </div>
      </div>
    {:else}
      <!-- Restaurante: PagBank CSV -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">B - Relatorio PagBank (CSV) - Preenche coluna REAL</h3>
        <div class="flex items-center gap-3">
          <span class="flex-1 text-sm text-muted-foreground">{statusRestPagbank || "Nenhum arquivo importado"}</span>
          <input type="file" accept=".csv" onchange={handleRestPagbankUpload} disabled={readonly} class="hidden" id="rest-pagbank-file" />
          <label for="rest-pagbank-file" class="inline-flex h-8 cursor-pointer items-center rounded-md border px-3 text-sm hover:bg-accent">
            Selecionar Arquivo
          </label>
          <button
            disabled={readonly}
            onclick={() => { statusRestPagbank = "Nenhum arquivo importado"; for (const k of restCategories) { if (k !== "DINHEIRO") categorias[k].real = 0; } }}
            class="inline-flex h-8 items-center rounded-md border px-3 text-sm hover:bg-accent"
          >
            Remover
          </button>
        </div>
      </div>

      <!-- Restaurante: Manual system values -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">C - Conciliacao (Sistema = manual, Real = auto)</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left">
                <th class="pb-2 pr-4">Categoria</th>
                <th class="pb-2 pr-4">Classif.</th>
                <th class="pb-2 pr-4">Sistema (R$)</th>
                <th class="pb-2 pr-4">Real (R$)</th>
                <th class="pb-2">Diferença (R$)</th>
              </tr>
            </thead>
            <tbody>
              {#each restCategories as key}
                <tr class="border-b">
                  <td class="py-2 pr-4">{restLabels[key]}</td>
                  <td class="py-2 pr-4 text-muted-foreground">{restClassif[key]}</td>
                  <td class="py-2 pr-4">
                    <input
                      type="text"
                      value={sistemaVars[key] || ""}
                      oninput={(e) => handleRestSistemaChange(key, e)}
                      disabled={readonly}
                      placeholder="0,00"
                      class="w-28 rounded-md border px-2 py-1 text-sm"
                    />
                  </td>
                  <td class="py-2 pr-4">{categorias[key]?.real ? formatMoney(categorias[key].real!) : "-"}</td>
                  <td class="py-2">
                    <span class={Math.abs(getRestDiff(key)) < 0.005 ? "text-green-600" : "text-red-600"}>
                      {getRestDiff(key) ? formatMoney(getRestDiff(key)) : "-"}
                    </span>
                  </td>
                </tr>
              {/each}
              <tr class="font-bold">
                <td colspan="4" class="pt-3 text-right">Diferença Total:</td>
                <td class="pt-3">
                  <span class={Math.abs(getRestTotalDiff()) < 0.005 ? "text-blue-600" : "text-red-600"}>
                    {formatMoney(getRestTotalDiff())}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    {/if}

    <!-- Contagem de Dinheiro -->
    <div class="mb-4 rounded-lg border p-4">
      <h3 class="mb-3 text-sm font-semibold">
        {tipo === "posto" ? "Contagem de Dinheiro" : "Contagem de Dinheiro (alimenta DINHEIRO real)"}
      </h3>
      <ContagemDinheiro
        {readonly}
        bind:contagens={contagensDinheiro}
        onChange={handleContagemChange}
      />
    </div>

    <!-- Lancamentos Avulsos -->
    <div class="mb-4 rounded-lg border p-4">
      <h3 class="mb-3 text-sm font-semibold">
        {tipo === "posto" ? "F" : "D"} - Lancamentos Avulsos
      </h3>
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <Select bind:value={avulsoTipo} disabled={readonly}>
          <option>RECEITA</option>
          <option>DESPESA</option>
        </Select>
        <Select bind:value={avulsoColuna} disabled={readonly}>
          <option value="sistema">sistema</option>
          {#if tipo === "posto"}
            <option value="site">site</option>
          {:else}
            <option value="real">real</option>
          {/if}
        </Select>
        <input
          type="text"
          bind:value={avulsoDesc}
          disabled={readonly}
          placeholder="Descricao"
          class="rounded-md border px-2 py-1 text-sm"
        />
        <input
          type="text"
          bind:value={avulsoValor}
          disabled={readonly}
          placeholder="Valor"
          class="w-28 rounded-md border px-2 py-1 text-sm"
        />
        <Select bind:value={avulsoCat} disabled={readonly}>
          {#each catOptions as opt}
            <option>{opt}</option>
          {/each}
        </Select>
        {#if showNovaCat}
          <input
            type="text"
            bind:value={avulsoNovaCat}
            disabled={readonly}
            placeholder="Nome da nova categoria"
            class="rounded-md border px-2 py-1 text-sm"
          />
        {/if}
        <button
          onclick={addAvulso}
          disabled={readonly}
          class="inline-flex h-8 items-center rounded-md bg-primary px-3 text-sm text-primary-foreground hover:bg-primary/90"
        >
          Adicionar
        </button>
      </div>
      {#if lancamentosAvulsos.length > 0}
        <table class="w-full text-sm border">
          <thead>
            <tr class="bg-muted">
              <th class="px-3 py-1.5 text-left">Tipo</th>
              <th class="px-3 py-1.5 text-left">Coluna</th>
              <th class="px-3 py-1.5 text-left">Descricao</th>
              <th class="px-3 py-1.5 text-right">Valor</th>
              <th class="px-3 py-1.5 text-left">Categoria</th>
              <th class="px-3 py-1.5"></th>
            </tr>
          </thead>
          <tbody>
            {#each lancamentosAvulsos as avulso, idx}
              <tr class="border-t">
                <td class="px-3 py-1.5">{avulso.tipo}</td>
                <td class="px-3 py-1.5">{avulso.coluna}</td>
                <td class="px-3 py-1.5">{avulso.descricao}</td>
                <td class="px-3 py-1.5 text-right">{formatMoney(avulso.valor)}</td>
                <td class="px-3 py-1.5">{getCatLabel(avulso)}</td>
                <td class="px-3 py-1.5">
                  <button
                    disabled={readonly}
                    onclick={() => removeAvulso(idx)}
                    class="text-xs text-red-600 hover:underline"
                  >
                    Remover
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  </div>

  <!-- Footer -->
  <div class="flex items-center gap-3 border-t px-4 py-3">
    <button
      onclick={saveDraft}
      disabled={loading}
      class="inline-flex h-9 items-center rounded-md border px-4 text-sm hover:bg-accent disabled:opacity-50"
    >
      Salvar Rascunho
    </button>
    <button
      onclick={verResultado}
      disabled={loading}
      class="ml-auto inline-flex h-9 items-center rounded-md bg-primary px-6 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
    >
      Ver Resultado
    </button>
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
