<script lang="ts">
  import { onMount } from "svelte";
  import { Bot, Loader2, RefreshCw } from "lucide-svelte";
  import {
    getCaixas,
    isFetched,
    isLoading,
    getError,
    clearError,
    fetchCaixas,
    fetchStatus,
    reconectarAutomacao,
    fecharNavegadorAutomacao,
    caixaChave,
    turnoCaixa,
    mesmaDataCaixa,
    type CaixaIdent,
    type AutomacaoStatus,
  } from "./automacaoCache.svelte";

  interface Pagamento {
    tipo: string;
    bandeira: string;
    subtipo: string;
    valor_vndpos: string;
    valor_vndtef: string;
  }

  interface ResultadoCaixa {
    ok: boolean;
    chave?: CaixaIdent;
    caixa?: {
      data?: string;
      turno?: string;
      pdv?: string;
      horario_fechamento?: string;
    };
    dinheiro?: string;
    pagamentos?: Pagamento[];
    erro?: string;
    tempo_ms?: number;
  }

  interface Props {
    onClose: () => void;
    onImport: (result: any) => string | null | void | Promise<string | null | void>;
    onLancar?: (caixa: CaixaIdent | null, caixaIdx: number | null) => void;
    mode?: "importar" | "lancar";
    formDate?: string;
  }

  let { onClose, onImport, onLancar, mode = "importar", formDate = "" }: Props = $props();

  let importing = $state(false);
  let selectedIdx = $state<number[]>([]);
  let acaoErro = $state("");
  let status = $state<AutomacaoStatus | null>(null);
  let resumo = $state<ResultadoCaixa[] | null>(null);
  let resumoErro = $state("");

  let caixas = $derived(getCaixas());
  let loading = $derived(isLoading());
  let error = $derived(getError());

  const STATUS_INFO: Record<string, { label: string; classe: string }> = {
    off: { label: "Sessao desligada", classe: "bg-muted text-muted-foreground" },
    warming: { label: "Aquecendo...", classe: "bg-yellow-100 text-yellow-700" },
    ready: { label: "Sessao pronta", classe: "bg-green-100 text-green-700" },
    headed: { label: "Janela aberta", classe: "bg-blue-100 text-blue-700" },
    error: { label: "Sessao com erro", classe: "bg-red-100 text-red-700" },
  };

  let info = $derived(STATUS_INFO[status?.state || "off"] || STATUS_INFO.off);
  let podeReconectar = $derived(!status || status.state === "error" || status.state === "off");
  let podeFecharNavegador = $derived(!!status?.browser_aberto || status?.state === "headed");
  let podeConfirmar = $derived(
    selectedIdx.length > 0 && !importing && resumo === null,
  );

  onMount(() => {
    if (!isFetched()) {
      fetchCaixas();
    }
    void atualizarStatus();
    const timer = setInterval(() => {
      void atualizarStatus();
    }, 4000);
    return () => clearInterval(timer);
  });

  async function atualizarStatus() {
    status = await fetchStatus();
  }

  async function reconectar() {
    acaoErro = "";
    const erro = await reconectarAutomacao();
    if (erro) acaoErro = erro;
    await atualizarStatus();
  }

  async function fecharNavegador() {
    acaoErro = "";
    const erro = await fecharNavegadorAutomacao();
    if (erro) acaoErro = erro;
    await atualizarStatus();
  }

  function atualizarLista() {
    resumo = null;
    resumoErro = "";
    selectedIdx = [];
    fetchCaixas();
  }

  function toggle(i: number) {
    if (mode === "lancar") {
      selectedIdx = [i];
      return;
    }
    selectedIdx = selectedIdx.includes(i)
      ? selectedIdx.filter((x) => x !== i)
      : [...selectedIdx, i];
  }

  function selecionarT1T2() {
    acaoErro = "";
    if (!formDate) {
      acaoErro =
        "Defina a data da conciliacao antes de usar o atalho T1+T2.";
      return;
    }
    const porTurno: Record<number, number> = {};
    caixas.forEach((caixa, i) => {
      const turno = turnoCaixa(caixa);
      if (!turno || porTurno[turno] !== undefined) return;
      if (mesmaDataCaixa(caixa.data, formDate)) porTurno[turno] = i;
    });
    const indices = Object.values(porTurno);
    if (indices.length === 0) {
      acaoErro = "Nenhum caixa T1/T2 encontrado para essa data.";
      return;
    }
    selectedIdx = indices;
  }

  async function confirmar() {
    if (!podeConfirmar) return;
    acaoErro = "";
    resumo = null;
    resumoErro = "";

    const selecionados = selectedIdx
      .map((i) => caixas[i])
      .filter((c) => Boolean(c));

    if (mode === "lancar") {
      const caixa = selecionados[0];
      onLancar?.(caixa ? caixaChave(caixa) : null, caixa ? caixa.row_index : null);
      onClose();
      return;
    }

    if (formDate) {
      const fora = selecionados.filter((c) => !mesmaDataCaixa(c.data, formDate));
      if (fora.length > 0) {
        acaoErro =
          `Caixa(s) fora da data ${formDate}: ` +
          fora.map((c) => `${c.data} (${c.turno || c.movto})`).join(", ") +
          ". Selecione caixas da data da conciliacao.";
        return;
      }
    }

    importing = true;
    try {
      const res = await fetch("/api/conciliador/automacao/importar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          caixas: selecionados.map((c) => caixaChave(c)),
          data: formDate || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        acaoErro = err.detail || "Erro ao importar caixas.";
        return;
      }
      const data = await res.json();
      const resultados: ResultadoCaixa[] = data.resultados || [];
      resumo = resultados;

      const algumOk = resultados.some((r) => r.ok);
      if (algumOk) {
        const erroAplicacao = await onImport(data);
        if (typeof erroAplicacao === "string") resumoErro = erroAplicacao;
      } else {
        resumoErro =
          resultados
            .map((r) => r.erro)
            .filter(Boolean)
            .join(" | ") || "Nenhum caixa importado.";
      }
    } catch (e: any) {
      acaoErro = e.message || "Erro de conexao.";
    } finally {
      importing = false;
    }
  }

  function concluir() {
    onClose();
  }
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onclick={onClose} role="dialog">
  <div class="w-[760px] max-h-[85vh] flex flex-col rounded-lg border bg-background shadow-xl" onclick={(e) => e.stopPropagation()}>
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

      {#if acaoErro}
        <div class="mb-3 rounded-md bg-red-50 p-2 text-sm text-red-700">
          {acaoErro}
          <button class="ml-2 font-bold" onclick={() => (acaoErro = "")}>&times;</button>
        </div>
      {/if}

      {#if resumo}
        <div class="mb-3 border">
          <div class="flex items-center justify-between border-b bg-muted/50 px-3 py-2 text-sm font-medium">
            <span>Resultado</span>
            <span class="text-xs text-muted-foreground">
              {resumo.filter((r) => r.ok).length}/{resumo.length} caixa(s)
            </span>
          </div>
          <div class="divide-y">
            {#each resumo as item}
              <div class="flex items-center justify-between px-3 py-2 text-sm">
                <span>
                  {item.caixa?.data || item.chave?.data || "?"}
                  · T{item.caixa?.turno || item.chave?.turno || "?"}
                  {#if item.caixa?.pdv}
                    · PDV {item.caixa.pdv}
                  {/if}
                </span>
                {#if item.ok}
                  <span class="text-xs text-green-700">
                    ok · {item.tempo_ms ?? 0}ms
                  </span>
                {:else}
                  <span class="text-xs text-red-600">{item.erro || "falhou"}</span>
                {/if}
              </div>
            {/each}
          </div>
          {#if resumoErro}
            <p class="border-t px-3 py-2 text-xs text-red-600">{resumoErro}</p>
          {/if}
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
          <span class="text-sm text-muted-foreground">
            {mode === "lancar" ? "Abrindo Cloudfy..." : "Importando dados do caixa..."}
          </span>
        </div>
      {:else if error && caixas.length === 0}
        <div class="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
          <button class="ml-2 font-bold" onclick={clearError}>&times;</button>
        </div>
        <button
          onclick={atualizarLista}
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
        <div class="mb-3 flex items-center justify-between">
          <p class="text-sm text-muted-foreground">
            {caixas.length} caixa(s) pendente(s). Selecione para {mode === "lancar" ? "lancar" : "importar"}.
          </p>
          {#if mode === "importar"}
            <button
              onclick={selecionarT1T2}
              disabled={importing}
              class="inline-flex h-8 items-center border px-3 text-xs hover:bg-accent disabled:opacity-50"
            >
              Selecionar T1+T2 da data
            </button>
          {/if}
        </div>
        <div class="overflow-x-auto border">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b bg-muted/50 text-left">
                <th class="w-8 px-3 py-2"></th>
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
                  class="cursor-pointer border-b hover:bg-accent/50"
                  class:bg-accent={selectedIdx.includes(i)}
                  onclick={() => toggle(i)}
                >
                  <td class="px-3 py-2">
                    <input
                      type={mode === "lancar" ? "radio" : "checkbox"}
                      name="caixa"
                      class="pointer-events-none"
                      checked={selectedIdx.includes(i)}
                      readonly
                    />
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

    <div class="flex items-center justify-between gap-2 border-t px-4 py-3">
      <div class="flex items-center gap-2">
        <button
          onclick={atualizarLista}
          disabled={loading || importing}
          class="inline-flex h-8 items-center gap-1.5 border px-3 text-sm hover:bg-accent disabled:opacity-50"
        >
          <RefreshCw class="h-3.5 w-3.5" />
          Atualizar lista
        </button>
        {#if podeReconectar && !importing}
          <button
            onclick={reconectar}
            class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
          >
            Reconectar
          </button>
        {/if}
        {#if podeFecharNavegador && !importing}
          <button
            onclick={fecharNavegador}
            class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
          >
            Fechar navegador
          </button>
        {/if}
      </div>

      <div class="flex items-center gap-3">
        <span class="inline-block rounded-full px-2 py-0.5 text-xs {info.classe}">
          {info.label}
        </span>
        {#if resumo}
          <button
            onclick={concluir}
            class="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90"
          >
            Concluir
          </button>
        {:else}
          <button
            onclick={confirmar}
            disabled={!podeConfirmar}
            class="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {#if mode === "lancar"}
              Lancar selecionado
            {:else if selectedIdx.length > 1}
              Importar {selectedIdx.length} selecionados
            {:else}
              Importar selecionado
            {/if}
          </button>
        {/if}
      </div>
    </div>
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
