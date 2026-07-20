<script lang="ts">
  import { ArrowLeft, Bot } from "lucide-svelte";

  import { onMount } from "svelte";
  import ContagemDinheiro from "./ContagemDinheiro.svelte";
  import Select from "./Select.svelte";
  import AutomacaoModal from "./AutomacaoModal.svelte";

  interface Props {
    tipo: "posto" | "restaurante";
    conciliacaoId: string | null;
    onVoltar: () => void;
    onResultado: (c: any) => void;
    onSalvo: () => void;
    onIdChange?: (id: string) => void;
    reloadKey?: number;
  }

  let { tipo, conciliacaoId, onVoltar, onResultado, onSalvo, onIdChange, reloadKey = 0 }: Props = $props();

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

  let contagemTabBehavior = $state<"icone" | "icone_fixo">("icone");
  let serial200Mode = $state<"obrigatorio_todas" | "opcional_geral" | "opcional_todas">("obrigatorio_todas");

  async function loadModuleSettings() {
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
      // keep default
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

  // ─── Split interno (restaurante, turno "Todos") ───
  let splitMode = $state(false);
  let splitTime = $state("");
  let activeTurno = $state(1);
  let turnoStore = $state<Record<number, {
    categorias: Record<string, any>;
    sistemaVars: Record<string, string>;
    contagens: any[];
    avulsos: any[];
  }>>({ 1: null as any, 2: null as any });
  let showSplitModal = $state(false);
  let splitModalTime = $state("");

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
  let premmiaLancamentos = $state<any[]>([]);

  let savedId = $state<string | null>(null);
  let hydrated = $state(false);
  let autosaveTimer: ReturnType<typeof setTimeout> | null = null;
  let autosaving = $state(false);
  let lastSavedAt = $state("");
  let savingInFlight = false;
  let toastMessage = $state("");
  let toastTimer: ReturnType<typeof setTimeout> | null = null;

  let showAutomacao = $state(false);

  function showToast(msg: string) {
    toastMessage = msg;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toastMessage = ""), 2500);
  }

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
    await loadModuleSettings();
    if (tipo === "posto") {
      await loadPostoConfig();
    }
    initCategories();
    if (conciliacaoId) {
      await loadConciliacao(conciliacaoId);
    }
    hydrated = true;
  });

  let lastReloadKey = 0;
  $effect(() => {
    const key = reloadKey;
    if (!hydrated) return;
    if (key === lastReloadKey) return;
    lastReloadKey = key;
    const id = savedId || conciliacaoId;
    if (id) {
      // Cancel any pending stale autosave before reloading fresh data.
      if (autosaveTimer) clearTimeout(autosaveTimer);
      loadConciliacao(id);
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
      premmiaLancamentos = doc.premmia_lancamentos || [];

      if (tipo === "posto") {
        fitcardTotal = doc.fitcard_total ? String(doc.fitcard_total).replace(".", ",") : "";
        sangria = doc.sangria || 0;
        notasPrazo = doc.notas_a_prazo || 0;
        despesas = doc.despesas || 0;
        statusCaixa = doc.status_caixa || "";
        statusPagbank = doc.status_pagbank || "";
        statusPremmia = doc.status_premmia || "";
        initPostoSistemaVars();
        handleContagemChange();
      } else {
        if (doc.split_mode && doc.turnos) {
          splitMode = true;
          splitTime = doc.split_time || "";
          turnoStore[1] = doc.turnos["1"] || emptyRestTurno();
          turnoStore[2] = doc.turnos["2"] || emptyRestTurno();
          activeTurno = 1;
          loadTurno(1);
          initRestSistemaVars();
          turno = "Todos";
        } else {
          turno = doc.turno === 1 ? "T1" : doc.turno === 2 ? "T2" : "Todos";
          initRestSistemaVars();
          initRestRealLabels();
        }
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
    cleaned = evalExpression(cleaned);
    cleaned = cleaned.replace(/[^\d,.\-]/g, "");
    if (cleaned.includes(",")) {
      cleaned = cleaned.replace(/\./g, "").replace(",", ".");
    }
    const val = parseFloat(cleaned);
    return isNaN(val) ? 0 : Math.round(val * 100) / 100;
  }

  function evalExpression(text: string): string {
    // Detect arithmetic expression: number op number  (e.g. "10,5+11,45")
    const match = text.match(/^([\d,.]+)\s*([+\-])\s*([\d,.]+)$/);
    if (!match) return text;
    const a = parseMoneyNum(match[1]);
    const op = match[2];
    const b = parseMoneyNum(match[3]);
    if (isNaN(a) || isNaN(b)) return text;
    const result = op === "+" ? a + b : a - b;
    return String(Math.round(result * 100) / 100).replace(".", ",");
  }

  function parseMoneyNum(s: string): number {
    let cleaned = s.replace(/\s/g, "").trim();
    if (cleaned.includes(",")) cleaned = cleaned.replace(/\./g, "").replace(",", ".");
    const val = parseFloat(cleaned);
    return isNaN(val) ? NaN : val;
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
        const isSangria = key === "SANGRIA" || (postoLabels[key] || "").toUpperCase() === "SANGRIA";
        if (!isSangria) {
          categorias[key].site = result.categorias?.[key]?.site || 0;
        }
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
      premmiaLancamentos = result.lancamentos || [];
      for (const key of postoCategories) {
        const isSangria = key === "SANGRIA" || (postoLabels[key] || "").toUpperCase() === "SANGRIA";
        if (!isSangria && result.categorias?.[key]?.site) {
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

    if (splitMode) {
      loading = true;
      try {
        const result = await uploadFile(
          `/parser/pagbank-restaurante-split?split_time=${encodeURIComponent(splitTime)}`,
          file,
        );
        applySplitReais(result);
        statusRestPagbank =
          `Dividido em ${splitTime} — T1: ${result.turno1?.registros_aprovados || 0} / T2: ${result.turno2?.registros_aprovados || 0} registros`;
      } catch (err: any) {
        errorMessage = err.message;
      } finally {
        loading = false;
      }
      return;
    }

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

  // ─── Split interno (restaurante) ───
  function emptyGeralContagem() {
    return {
      id: crypto.randomUUID(),
      label: "Geral",
      editado: false,
      notas: { "200": 0, "100": 0, "50": 0, "20": 0, "10": 0, "5": 0, "2": 0 },
      seriais_200: [] as string[],
      moedas: 0,
      depositos: 0,
      total: 0,
    };
  }

  function emptyRestTurno() {
    const cats: Record<string, any> = {};
    const vars: Record<string, string> = {};
    for (const key of restCategories) {
      cats[key] = { sistema: 0, real: 0 };
      vars[key] = "";
    }
    return { categorias: cats, sistemaVars: vars, contagens: [emptyGeralContagem()], avulsos: [] };
  }

  function snapshotActiveTurno() {
    turnoStore[activeTurno] = {
      categorias: JSON.parse(JSON.stringify(categorias)),
      sistemaVars: { ...sistemaVars },
      contagens: JSON.parse(JSON.stringify(contagensDinheiro)),
      avulsos: JSON.parse(JSON.stringify(lancamentosAvulsos)),
    };
  }

  function loadTurno(n: number) {
    const s = turnoStore[n];
    if (!s) return;
    categorias = s.categorias;
    sistemaVars = s.sistemaVars;
    contagensDinheiro = s.contagens;
    lancamentosAvulsos = s.avulsos;
  }

  function switchTurno(n: number) {
    if (n === activeTurno) return;
    snapshotActiveTurno();
    activeTurno = n;
    loadTurno(n);
  }

  function openSplitModal() {
    splitModalTime = splitTime || "";
    showSplitModal = true;
  }

  function confirmSplit() {
    const t = splitModalTime.trim();
    if (!/^\d{2}:\d{2}$/.test(t)) { errorMessage = "Formato invalido. Use hh:mm"; return; }
    splitTime = t;
    // Turno 1 recebe os dados atuais; Turno 2 comeca vazio
    turnoStore[1] = {
      categorias: JSON.parse(JSON.stringify(categorias)),
      sistemaVars: { ...sistemaVars },
      contagens: JSON.parse(JSON.stringify(contagensDinheiro)),
      avulsos: JSON.parse(JSON.stringify(lancamentosAvulsos)),
    };
    turnoStore[2] = emptyRestTurno();
    activeTurno = 1;
    splitMode = true;
    showSplitModal = false;
  }

  function disableSplit() {
    snapshotActiveTurno();
    // Mantém turno 1 como dados principais
    loadTurno(1);
    splitMode = false;
    activeTurno = 1;
  }

  function applySplitReais(result: any) {
    const store1 = turnoStore[1] || emptyRestTurno();
    const store2 = turnoStore[2] || emptyRestTurno();
    for (const key of restCategories) {
      if (key === "DINHEIRO") continue;
      store1.categorias[key] = { ...store1.categorias[key], real: result.turno1?.categorias?.[key]?.real || 0 };
      store2.categorias[key] = { ...store2.categorias[key], real: result.turno2?.categorias?.[key]?.real || 0 };
    }
    turnoStore[1] = store1;
    turnoStore[2] = store2;
    loadTurno(activeTurno);
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

  function getRestRealWithAvulsos(key: string): number {
    let real = categorias[key]?.real || 0;
    for (const av of lancamentosAvulsos) {
      if (av.categoria_vinculada === key && av.coluna === "real") {
        const delta = av.tipo === "RECEITA" ? av.valor : -av.valor;
        real += delta;
      }
    }
    return Math.round(real * 100) / 100;
  }

  function getRestSistemaWithAvulsos(key: string): number {
    let sistema = categorias[key]?.sistema || 0;
    for (const av of lancamentosAvulsos) {
      if (av.categoria_vinculada === key && av.coluna !== "real") {
        const delta = av.tipo === "RECEITA" ? av.valor : -av.valor;
        sistema += delta;
      }
    }
    return Math.round(sistema * 100) / 100;
  }

  function getPostoDiff(key: string): number {
    const site = getPostoSiteWithAvulsos(key);
    const sistema = getPostoSistemaWithAvulsos(key);
    return Math.round((site - sistema) * 100) / 100;
  }

  function getPostoSiteWithAvulsos(key: string): number {
    let site = categorias[key]?.site || 0;
    for (const av of lancamentosAvulsos) {
      if (av.categoria_vinculada === key && av.coluna === "site") {
        const delta = av.tipo === "RECEITA" ? av.valor : -av.valor;
        site += delta;
      }
    }
    return Math.round(site * 100) / 100;
  }

  function getPostoSistemaWithAvulsos(key: string): number {
    let sistema = categorias[key]?.sistema || 0;
    for (const av of lancamentosAvulsos) {
      if (av.categoria_vinculada === key && av.coluna !== "site") {
        const delta = av.tipo === "RECEITA" ? av.valor : -av.valor;
        sistema += delta;
      }
    }
    return Math.round(sistema * 100) / 100;
  }

  function getPostoTotalDiff(): number {
    let total = 0;
    for (const key of postoCategories) {
      total += getPostoDiff(key);
    }
    return Math.round(total * 100) / 100;
  }

  function handlePostoSistemaChange(key: string, e: Event) {
    sistemaVars[key] = (e.target as HTMLInputElement).value;
    const val = parseMoney(sistemaVars[key]);
    categorias[key] = { ...categorias[key], sistema: val, site: categorias[key].site };
    categorias = categorias;
  }

  function handleContagemChange() {
    if (tipo === "restaurante") {
      const geral = contagensDinheiro.find((c: any) => c.label === "Geral");
      const dinheiroReal = geral?.total || 0;
      categorias["DINHEIRO"] = { ...categorias["DINHEIRO"], sistema: categorias["DINHEIRO"].sistema, real: dinheiroReal };
      categorias = categorias;
    } else {
      const geral = contagensDinheiro.find((c: any) => c.label === "Geral");
      const cashTotal = geral?.total || 0;
      for (const key of postoCategories) {
        if (key === "SANGRIA" || postoLabels[key]?.toUpperCase() === "SANGRIA") {
          categorias[key] = { ...categorias[key], sistema: categorias[key].sistema, site: cashTotal };
          categorias = categorias;
          break;
        }
      }
    }
  }

  async function handleAutomacaoImport(result: any) {
    if (tipo !== "restaurante") return;

    let mapping: Record<string, string> = {};
    try {
      const res = await fetch("/api/conciliador/config/mapeamento");
      if (res.ok) {
        const data = await res.json();
        mapping = data.mapeamento || {};
      }
    } catch {
      // usa mapeamento vazio, nenhum pagamento mapeado
    }

    const dinheiroVal = parseMoney(result.dinheiro || "0");
    categorias["DINHEIRO"] = { ...categorias["DINHEIRO"], real: dinheiroVal };

    const pagamentos: any[] = result.pagamentos || [];
    for (const pg of pagamentos) {
      const subtipoCloudfy = (pg.subtipo || "").trim();
      const key = mapping[subtipoCloudfy];
      if (!key) continue;
      const pos = parseMoney(pg.valor_vndpos || "0");
      const tef = parseMoney(pg.valor_vndtef || "0");
      const total = Math.round((pos + tef) * 100) / 100;
      const current = categorias[key] || { sistema: 0, real: 0 };
      categorias[key] = { ...current, real: Math.round((current.real + total) * 100) / 100 };
    }

    categorias = categorias;
    initRestSistemaVars();
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
    const avulsoTurno = tipo === "restaurante" && splitMode ? activeTurno : null;
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
        turno: avulsoTurno,
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
        turno: avulsoTurno,
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
    const id = await persistNow();
    loading = false;
    if (id) {
      showToast("Rascunho salvo com sucesso.");
    } else {
      errorMessage = "Erro ao salvar rascunho.";
    }
  }

  async function saveAndFinalize() {
    loading = true;
    try {
      const val = await fetch("/api/conciliador/validar-contagens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contagens: contagensDinheiro }),
      });
      if (val.ok) {
        const result = await val.json();
        if (!result.valid) {
          errorMessage = result.errors.join(" | ");
          loading = false;
          return;
        }
      }
    } catch {
      // if validation endpoint fails, proceed
    }
    const payload = buildPayload("conciliado");
    try {
      const res = await fetch("/api/conciliador/conciliacoes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Erro ao salvar");
      const result = await res.json();
      savedId = result.id;
      status = "conciliado";
      onSalvo();
    } catch (e: any) {
      errorMessage = e.message;
    } finally {
      loading = false;
    }
  }

  function mergeTurnoCategorias() {
    const merged: Record<string, any> = {};
    for (const key of restCategories) {
      const c1 = turnoStore[1]?.categorias?.[key] || { sistema: 0, real: 0 };
      const c2 = turnoStore[2]?.categorias?.[key] || { sistema: 0, real: 0 };
      merged[key] = {
        sistema: Math.round(((c1.sistema || 0) + (c2.sistema || 0)) * 100) / 100,
        real: Math.round(((c1.real || 0) + (c2.real || 0)) * 100) / 100,
      };
    }
    return merged;
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
      base.premmia_lancamentos = premmiaLancamentos;
      base.status_caixa = statusCaixa;
      base.status_pagbank = statusPagbank;
      base.status_premmia = statusPremmia;
    } else if (splitMode) {
      snapshotActiveTurno();
      base.turno = null;
      base.split_mode = true;
      base.split_time = splitTime;
      base.turnos = {
        "1": turnoStore[1],
        "2": turnoStore[2],
      };
      // Combina os dois turnos para totais/histórico
      base.categorias = mergeTurnoCategorias();
      base.contagens_dinheiro = [
        ...(turnoStore[1]?.contagens || []),
        ...(turnoStore[2]?.contagens || []),
      ];
      base.lancamentos_avulsos = [
        ...(turnoStore[1]?.avulsos || []),
        ...(turnoStore[2]?.avulsos || []),
      ];
    } else {
      base.turno = turno === "T1" ? 1 : turno === "T2" ? 2 : null;
    }
    return base;
  }

  async function verResultado() {
    await persistNow();
    const payload = buildPayload(status === "conciliado" ? "conciliado" : "rascunho");
    onResultado(payload);
  }

  async function persistNow(): Promise<string | null> {
    if (readonly) return savedId;
    if (savingInFlight) return savedId;
    savingInFlight = true;
    autosaving = true;
    try {
      const payload = buildPayload("rascunho");
      const res = await fetch("/api/conciliador/conciliacoes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const result = await res.json();
        if (result.id && result.id !== savedId) {
          savedId = result.id;
          onIdChange?.(result.id);
        }
        lastSavedAt = new Date().toLocaleTimeString();
      }
    } catch {
      // silent - autosave is best-effort
    } finally {
      autosaving = false;
      savingInFlight = false;
    }
    return savedId;
  }

  function scheduleAutosave() {
    if (!hydrated || readonly) return;
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => { if (!savingInFlight) persistNow(); }, 800);
  }

  $effect(() => {
    // Track all persisted state so any change triggers a debounced autosave.
    void data;
    void turno;
    void JSON.stringify(categorias);
    void JSON.stringify(contagensDinheiro);
    void JSON.stringify(lancamentosAvulsos);
    void JSON.stringify(premmiaLancamentos);
    void fitcardTotal;
    void sangria;
    void notasPrazo;
    void despesas;
    void observacoes;
    scheduleAutosave();
  });

  const catOptions = $derived(tipo === "posto"
    ? postoCategories.map(k => postoLabels[k]).concat(["Nova categoria..."])
    : restCategories.map(k => restLabels[k]).concat(["Nova categoria..."]));
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <button
      onclick={onVoltar}
      class="inline-flex h-8 w-8 items-center justify-center border hover:bg-accent"
      title="Voltar ao Historico"
    >
      <ArrowLeft class="h-4 w-4" />
    </button>
    <h1 class="text-lg font-semibold">
      {readonly ? "Caixa Conciliado" : "Caixa em Edicao"} - {tipo === "posto" ? "Posto" : "Restaurante"}
    </h1>
    {#if readonly}
      <button
        onclick={async () => {
          if (savedId) {
            const res = await fetch(`/api/conciliador/conciliacoes/${savedId}/reabrir`, { method: "POST" });
            if (res.ok) {
              status = "rascunho";
            } else {
              const err = await res.json().catch(() => ({}));
              errorMessage = err.detail || "Nao foi possivel reabrir o caixa.";
            }
          }
        }}
        class="ml-auto inline-flex h-8 items-center bg-primary px-3 text-sm text-primary-foreground hover:bg-primary-hover"
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

  {#if toastMessage}
    <div class="toast-in fixed bottom-6 right-6 z-50 rounded-md bg-green-600 px-4 py-2 text-sm text-white shadow-lg">
      {toastMessage}
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

  <!-- Split Modal -->
  {#if showSplitModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onclick={() => (showSplitModal = false)}>
      <div class="w-96 border bg-background p-6 shadow-xl" onclick={(e) => e.stopPropagation()}>
        <h3 class="mb-2 text-sm font-semibold">Dividir internamente por horario</h3>
        <p class="mb-4 text-sm text-muted-foreground">
          Informe o horario de divisao. Tudo antes desse horario será Turno 1, o restante Turno 2.
        </p>
        <div class="flex items-center gap-3">
          <label class="w-28 text-sm">Horario</label>
          <input
            type="text"
            value={splitModalTime}
            oninput={(e) => { splitModalTime = formatHora((e.target as HTMLInputElement).value); }}
            placeholder="hh:mm"
            class="w-24 border bg-background px-3 py-1.5 text-sm"
          />
        </div>
        <div class="mt-6 flex justify-end gap-3">
          <button
            onclick={() => (showSplitModal = false)}
            class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
          >
            Cancelar
          </button>
          <button
            onclick={confirmSplit}
            class="inline-flex h-8 items-center bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90"
          >
            Dividir
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
          <Select bind:value={turno} disabled={readonly || splitMode}>
            <option>T1</option>
            <option>T2</option>
            <option>Todos</option>
          </Select>
          {#if turno === "Todos" && !splitMode && !readonly}
            <button
              onclick={openSplitModal}
              class="ml-2 inline-flex h-8 items-center border border-primary px-3 text-sm text-primary hover:bg-accent"
            >
              Dividir internamente
            </button>
          {/if}
          {#if splitMode}
            <span class="ml-2 text-sm text-muted-foreground">Dividido em {splitTime}</span>
            {#if !readonly}
              <button
                onclick={disableSplit}
                class="ml-2 inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
              >
                Desfazer divisao
              </button>
            {/if}
          {/if}
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
            onclick={() => { statusPagbank = "Nenhum arquivo importado"; for (const k of postoCategories) { const isSangria = k === "SANGRIA" || (postoLabels[k] || "").toUpperCase() === "SANGRIA"; if (!isSangria) categorias[k].site = 0; } }}
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
          onkeydown={(e) => { if (e.key==='Enter') { e.preventDefault(); const t=e.target as HTMLInputElement; const evaled=evalExpression(t.value); if (evaled!==t.value) { t.value=evaled; handleFitcardChange(e as any); } } }}
          disabled={readonly}
          placeholder="0,00"
          class="ml-3 rounded-md border px-3 py-1.5 text-sm"
        />
      </div>

      <!-- Posto: Premmia -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">E - Relatorio Premmia (XLS/XLSX)</h3>
        <div class="flex items-center gap-3">
          <span class="flex-1 text-sm text-muted-foreground">{statusPremmia || "Nenhum arquivo importado"}</span>
          <input type="file" accept=".xls,.XLS,.xlsx,.XLSX,.csv" onchange={handlePremmiaUpload} disabled={readonly} class="hidden" id="premmia-file" />
          <label for="premmia-file" class="inline-flex h-8 cursor-pointer items-center border px-3 text-sm hover:bg-accent">
            Selecionar Arquivo
          </label>
          <button
            disabled={readonly}
            onclick={() => { statusPremmia = "Nenhum arquivo importado"; premmiaLancamentos = []; for (const k of postoCategories) { const isSangria = k === "SANGRIA" || (postoLabels[k] || "").toUpperCase() === "SANGRIA"; if (!isSangria) categorias[k].site = 0; } }}
            class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
          >
            Remover
          </button>
        </div>

        {#if premmiaLancamentos.length > 0}
          {@const premmiaKeys = ["PREMMIA_CARTAO", "PREMMIA_PIX", "PREMMIA_VALE", "PREMMIA_CUPOM"]}
          {@const grouped = premmiaKeys.reduce((acc: Record<string, any[]>, k: string) => {
            acc[k] = premmiaLancamentos
              .filter((l: any) => l.categoria === k && l.aceito)
              .sort((a: any, b: any) => (a.data_hora || "").localeCompare(b.data_hora || ""));
            return acc;
          }, {} as Record<string, any[]>)}
          {@const maxRows = Math.max(...premmiaKeys.map(k => grouped[k].length), 0)}
          <div class="mt-3 max-h-72 overflow-auto border">
            <table class="w-full text-xs">
              <thead class="sticky top-0 bg-muted">
                <tr class="text-left">
                  {#each premmiaKeys as key}
                    <th class="px-2 py-1.5">{postoLabels[key] || key}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each Array(maxRows) as _, rowIdx}
                  <tr class="border-t">
                    {#each premmiaKeys as key}
                      {@const item = grouped[key][rowIdx]}
                      <td class="px-2 py-1 text-right tabular-nums">
                        {#if item}
                          {formatMoney(item.valor)}
                        {:else}
                          <span class="text-muted-foreground">-</span>
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
              <tfoot class="sticky bottom-0 bg-muted font-semibold">
                <tr class="border-t">
                  {#each premmiaKeys as key}
                    {@const total = grouped[key].reduce((s: number, l: any) => s + l.valor, 0)}
                    <td class="px-2 py-1.5 text-right tabular-nums">{formatMoney(total)}</td>
                  {/each}
                </tr>
                <tr class="border-t text-[10px] text-muted-foreground">
                  {#each premmiaKeys as key}
                    <td class="px-2 py-1.5 text-right">{grouped[key].length} lanc.</td>
                  {/each}
                </tr>
              </tfoot>
            </table>
          </div>
        {/if}
      </div>

      <!-- Posto: Conciliacao (secao C) -->
      <div class="mb-4 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">F - Conciliacao (Sistema = manual/editavel, Site = relatorios)</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b text-left">
                <th class="pb-2 pr-4">Categoria</th>
                <th class="pb-2 pr-4">Sistema (R$)</th>
                <th class="pb-2 pr-4">Site (R$)</th>
                <th class="pb-2">Diferenca (R$)</th>
              </tr>
            </thead>
            <tbody>
              {#each postoCategories as key}
                {@const siteVal = getPostoSiteWithAvulsos(key)}
                {@const sistemaVal = getPostoSistemaWithAvulsos(key)}
                {@const diffVal = getPostoDiff(key)}
                <tr class="border-b">
                  <td class="py-2 pr-4">{postoLabels[key] || key}</td>
                  <td class="py-2 pr-4">
                    <input
                      type="text"
                      value={sistemaVars[key] || ""}
                      oninput={(e) => handlePostoSistemaChange(key, e)}
                      onkeydown={(e) => { if (e.key==='Enter') { e.preventDefault(); const t=e.target as HTMLInputElement; const evaled=evalExpression(t.value); if (evaled!==t.value) { t.value=evaled; handlePostoSistemaChange(key, {target:t} as any); } } }}
                      disabled={readonly}
                      placeholder="0,00"
                      class="w-28 rounded-md border px-2 py-1 text-sm"
                    />
                  </td>
                  <td class="py-2 pr-4">{formatMoney(siteVal)}</td>
                  <td class="py-2">
                    <span class={Math.abs(diffVal) < 0.005 ? "text-green-600" : diffVal >= 0 ? "text-primary" : "text-red-600"}>
                      {formatMoney(diffVal)}
                    </span>
                  </td>
                </tr>
              {/each}
              <tr class="font-bold">
                <td class="pt-3 text-right">Diferenca (Site - Sistema):</td>
                <td class="pt-3"></td>
                <td class="pt-3"></td>
                <td class="pt-3">
                  <span class={Math.abs(getPostoTotalDiff()) < 0.005 ? "text-green-600" : getPostoTotalDiff() >= 0 ? "text-primary" : "text-red-600"}>
                    {formatMoney(getPostoTotalDiff())}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
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
        {#if splitMode}
          <p class="mt-2 text-xs text-muted-foreground">
            O relatorio importado é dividido automaticamente: transacoes antes de {splitTime} vao para o Turno 1, o restante para o Turno 2.
          </p>
        {/if}
      </div>

      {#if splitMode}
        <!-- Turno tabs -->
        <div class="mb-4 flex items-center gap-1 border-b">
          <button
            onclick={() => switchTurno(1)}
            class="inline-flex items-center border border-b-0 px-4 py-1.5 text-sm transition-colors"
            class:bg-background={activeTurno === 1}
            class:font-semibold={activeTurno === 1}
            class:text-primary={activeTurno === 1}
            class:border-primary={activeTurno === 1}
            class:bg-muted={activeTurno !== 1}
            class:text-muted-foreground={activeTurno !== 1}
          >
            Turno 1
          </button>
          <button
            onclick={() => switchTurno(2)}
            class="inline-flex items-center border border-b-0 px-4 py-1.5 text-sm transition-colors"
            class:bg-background={activeTurno === 2}
            class:font-semibold={activeTurno === 2}
            class:text-primary={activeTurno === 2}
            class:border-primary={activeTurno === 2}
            class:bg-muted={activeTurno !== 2}
            class:text-muted-foreground={activeTurno !== 2}
          >
            Turno 2
          </button>
        </div>
      {/if}

      <!-- Restaurante: Manual system values -->
      <div class="mb-4 rounded-lg border p-4">
        <div class="mb-3 flex items-center gap-2">
          <h3 class="text-sm font-semibold">
            C - Conciliacao (Sistema = manual, Real = auto){splitMode ? ` — Turno ${activeTurno}` : ""}
          </h3>
          {#if !readonly}
            <button
              onclick={() => (showAutomacao = true)}
              class="ml-auto inline-flex h-7 items-center gap-1.5 rounded-md bg-primary px-3 text-xs text-primary-foreground hover:bg-primary/90"
            >
              <Bot class="h-3.5 w-3.5" />
              Automacao
            </button>
          {/if}
        </div>
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
                {@const realVal = getRestRealWithAvulsos(key)}
                {@const sistemaVal = getRestSistemaWithAvulsos(key)}
                {@const diffVal = Math.round((realVal - sistemaVal) * 100) / 100}
                <tr class="border-b">
                  <td class="py-2 pr-4">{restLabels[key]}</td>
                  <td class="py-2 pr-4 text-muted-foreground">{restClassif[key]}</td>
                  <td class="py-2 pr-4">
                    <input
                      type="text"
                      value={sistemaVars[key] || ""}
                      oninput={(e) => handleRestSistemaChange(key, e)}
                      onkeydown={(e) => { if (e.key==='Enter') { e.preventDefault(); const t=e.target as HTMLInputElement; const evaled=evalExpression(t.value); if (evaled!==t.value) { t.value=evaled; handleRestSistemaChange(key, {target:t} as any); } } }}
                      disabled={readonly}
                      placeholder="0,00"
                      class="w-28 rounded-md border px-2 py-1 text-sm"
                    />
                  </td>
                  <td class="py-2 pr-4">{formatMoney(realVal)}</td>
                  <td class="py-2">
                    <span class={Math.abs(diffVal) < 0.005 ? "text-green-600" : diffVal >= 0 ? "text-primary" : "text-red-600"}>
                      {formatMoney(diffVal)}
                    </span>
                  </td>
                </tr>
              {/each}
              <tr class="font-bold">
                <td colspan="4" class="pt-3 text-right">Diferença (Real&nbsp;-&nbsp;Sistema):</td>
                <td class="pt-3">
                  <span class={Math.abs(getRestTotalDiff()) < 0.005 ? "text-green-600" : getRestTotalDiff() >= 0 ? "text-primary" : "text-red-600"}>
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
        {tipo === "posto" ? "Contagem de Dinheiro" : `Contagem de Dinheiro (alimenta DINHEIRO real)${splitMode ? ` — Turno ${activeTurno}` : ""}`}
      </h3>
      <ContagemDinheiro
        {readonly}
        bind:contagens={contagensDinheiro}
        onChange={handleContagemChange}
        tabBehavior={contagemTabBehavior}
        serialMode={serial200Mode}
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
      disabled={loading || readonly}
      class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
    >
      Salvar Rascunho
    </button>
    {#if !readonly}
      <span class="text-xs text-muted-foreground">
        {autosaving ? "Salvando..." : lastSavedAt ? `Rascunho salvo automaticamente ${lastSavedAt}` : "Salvamento automatico ativo"}
      </span>
    {/if}
    <button
      onclick={saveAndFinalize}
      disabled={loading || readonly}
      class="inline-flex h-9 items-center border border-primary px-4 text-sm text-primary hover:bg-accent disabled:opacity-50"
    >
      Salvar e Finalizar
    </button>
    <button
      onclick={verResultado}
      disabled={loading}
      class="ml-auto inline-flex h-9 items-center bg-primary px-6 text-sm text-primary-foreground hover:bg-primary-hover disabled:opacity-50"
    >
      Ver Resultado
    </button>
  </div>

  {#if showAutomacao}
    <AutomacaoModal
      onClose={() => (showAutomacao = false)}
      onImport={(result) => handleAutomacaoImport(result)}
    />
  {/if}
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
