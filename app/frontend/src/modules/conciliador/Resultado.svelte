<script lang="ts">
  import { onMount } from "svelte";
  import { ArrowLeft, FileDown } from "lucide-svelte";
  import Select from "./Select.svelte";

  interface Props {
    caixa: any;
    tipo: "posto" | "restaurante";
    onVoltar: () => void;
    onSalvo: () => void;
  }

  let { caixa, tipo, onVoltar, onSalvo }: Props = $props();

  let rows = $state<any[]>([]);
  let extra = $state<any>({});
  let loading = $state(true);
  let caixaId = $state("");

  let postoLabels = $state<Record<string, string>>({
    PREMMIA_CARTAO: "PREMMIA CARTAO", PREMMIA_PIX: "PREMMIA PIX",
    PREMMIA_VALE: "PREMMIA VALE", PREMMIA_CUPOM: "PREMMIA CUPOM",
    FITCARD: "FITCARD", PAG_PIX: "PAG PIX", AMEX: "AMERICAN EXP",
    ELO_CREDITO: "ELO CREDITO", ELO_DEBITO: "ELO DEBITO",
    MASTERCARD_CREDITO: "MASTERCARD CREDITO", MASTERCARD_DEBITO: "MASTERCARD DEBITO",
    VISA_CREDITO: "VISA CREDITO", VISA_DEBITO: "VISA DEBITO",
  });
  let postoCategories = $state<string[]>(Object.keys(postoLabels));

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

  const restLabels: Record<string, string> = {
    PIX: "PIX", ELO_DEBITO: "ELO DEBITO", MAESTRO: "MAESTRO",
    VC_ELECTRON: "VC ELECTRON", AMEX: "AMEX", ELO_CR: "ELO CR",
    MASTERCARD: "MASTERCARD", VISA: "VISA", DINHEIRO: "DINHEIRO",
  };
  const restCategories = Object.keys(restLabels);

  let lancamentosAvulsos = $state<any[]>(caixa.lancamentos_avulsos || []);
  let avulsoTipo = $state("RECEITA");
  let avulsoColuna = $state("sistema");
  let avulsoDesc = $state("");
  let avulsoValor = $state("");

  onMount(async () => {
    lancamentosAvulsos = caixa.lancamentos_avulsos || [];
    if (tipo === "posto") {
      await loadPostoConfig();
    }
    if (caixa.id || caixa._id) {
      caixaId = String(caixa.id || caixa._id);
      loadResultado();
    } else {
      buildFromPayload();
      loading = false;
    }
  });

  async function loadResultado() {
    loading = true;
    try {
      const res = await fetch(`/api/conciliador/conciliacoes/${caixaId}/resultado`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        rows = data.rows || [];
        extra = data;
      }
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  function buildFromPayload() {
    rows = [];
    const cats = caixa.categorias || {};
    const avulsos = lancamentosAvulsos;
    const contagens = caixa.contagens_dinheiro || [];

    if (tipo === "posto") {
      for (const key of postoCategories) {
        const v = cats[key] || { sistema: 0, site: 0 };
        const sistema = v.sistema || 0;
        const site = v.site || 0;
        const diff = sistema - site;
        rows.push({ key, label: postoLabels[key], sistema, site, diferenca: Math.round(diff * 100) / 100, status: Math.abs(diff) < 0.005 ? "OK" : "DIVERGENTE" });
      }
      for (const av of avulsos) {
        if (av.categoria_nova) {
          const delta = av.tipo === "RECEITA" ? av.valor : -av.valor;
          const s = av.coluna !== "site" ? delta : 0;
          const si = av.coluna === "site" ? delta : 0;
          rows.push({ key: av.categoria_nova, label: av.categoria_nova, sistema: Math.round(s * 100) / 100, site: Math.round(si * 100) / 100, diferenca: Math.round((s - si) * 100) / 100, status: Math.abs(s - si) < 0.005 ? "OK" : "DIVERGENTE" });
        }
      }
      extra = {
        sangria: caixa.sangria || 0,
        notas_a_prazo: caixa.notas_a_prazo || 0,
        despesas: caixa.despesas || 0,
      };
    } else {
      const geral = contagens.find((c: any) => c.label === "Geral");
      const dinheiroReal = geral?.total || 0;
      for (const key of restCategories) {
        const v = cats[key] || { sistema: 0, real: 0 };
        const sistema = v.sistema || 0;
        const real = key === "DINHEIRO" ? dinheiroReal : (v.real || 0);
        const diff = sistema - real;
        rows.push({ key, label: restLabels[key], sistema, real, diferenca: Math.round(diff * 100) / 100, status: Math.abs(diff) < 0.005 ? "OK" : "DIVERGENTE" });
      }
      for (const av of avulsos) {
        if (av.categoria_nova) {
          const delta = av.tipo === "RECEITA" ? av.valor : -av.valor;
          const s = av.coluna !== "real" ? delta : 0;
          const r = av.coluna === "real" ? delta : 0;
          rows.push({ key: av.categoria_nova, label: av.categoria_nova, sistema: Math.round(s * 100) / 100, real: Math.round(r * 100) / 100, diferenca: Math.round((s - r) * 100) / 100, status: Math.abs(s - r) < 0.005 ? "OK" : "DIVERGENTE" });
        }
      }
    }
  }

  function formatMoney(value: number): string {
    if (!value && value !== 0) return "-";
    const formatted = value.toFixed(2).replace(".", ",");
    return `R$ ${formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }

  function formatDate(iso: string): string {
    if (!iso) return "-";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }

  function parseMoney(text: string): number {
    if (!text || !text.trim()) return 0;
    let cleaned = text.replace("R$", "").replace(/\s/g, "").trim();
    cleaned = cleaned.replace(/[^\d,.\-]/g, "");
    if (cleaned.includes(",")) cleaned = cleaned.replace(/\./g, "").replace(",", ".");
    const val = parseFloat(cleaned);
    return isNaN(val) ? 0 : Math.round(val * 100) / 100;
  }

  function addAvulso() {
    const valor = parseMoney(avulsoValor);
    if (valor <= 0) return;
    lancamentosAvulsos = [...lancamentosAvulsos, {
      id: crypto.randomUUID(),
      descricao: avulsoDesc,
      valor,
      tipo: avulsoTipo,
      coluna: avulsoColuna,
      categoria_vinculada: null,
      categoria_nova: null,
    }];
    avulsoDesc = "";
    avulsoValor = "";
    buildFromPayload();
  }

  function removeAvulso(idx: number) {
    lancamentosAvulsos = lancamentosAvulsos.filter((_: any, i: number) => i !== idx);
    buildFromPayload();
  }

  const totalDiff = $derived(rows.reduce((sum: number, r: any) => sum + (r.diferenca || 0), 0));

  async function save() {
    const payload = { ...caixa, lancamentos_avulsos: lancamentosAvulsos };
    let id = caixaId;
    if (!id) {
      const res = await fetch("/api/conciliador/conciliacoes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, status: "conciliado" }),
      });
      if (res.ok) {
        const data = await res.json();
        id = data.id;
        caixaId = id;
      }
    } else {
      await fetch(`/api/conciliador/conciliacoes/${caixaId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, id: caixaId }),
      });
      await fetch(`/api/conciliador/conciliacoes/${caixaId}/conciliar`, { method: "POST" });
    }
    onSalvo();
  }

  async function exportPdf() {
    if (!caixaId) {
      const res = await fetch("/api/conciliador/conciliacoes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...caixa, lancamentos_avulsos: lancamentosAvulsos, status: "rascunho" }),
      });
      if (res.ok) {
        const data = await res.json();
        caixaId = data.id;
      }
    }
    if (!caixaId) return;
    try {
      const res = await fetch(`/api/conciliador/conciliacoes/${caixaId}/export/pdf`);
      if (!res.ok) throw new Error("Erro ao gerar PDF");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `CaixaPos_${tipo}_${caixa.data || "export"}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message);
    }
  }
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <button
      onclick={onVoltar}
      class="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-accent"
      title="Voltar"
    >
      <ArrowLeft class="h-4 w-4" />
    </button>
    <h1 class="text-lg font-semibold">
      Resultado - {caixa?.data ? formatDate(caixa.data) : ""} {tipo === "restaurante" ? "(Restaurante)" : "(Posto)"}
    </h1>
  </div>

  <div class="flex-1 overflow-auto p-4">
    {#if loading}
      <div class="flex h-full items-center justify-center">
        <p class="text-muted-foreground">Carregando...</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b bg-muted/50 text-left">
              <th class="px-4 py-2">Categoria</th>
              {#if tipo === "restaurante"}
                <th class="px-4 py-2">Classif.</th>
              {/if}
              <th class="px-4 py-2 text-right">Sistema (R$)</th>
              <th class="px-4 py-2 text-right">{tipo === "restaurante" ? "Real (R$)" : "Site (R$)"}</th>
              <th class="px-4 py-2 text-right">Diferenca (R$)</th>
              <th class="px-4 py-2 text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {#each rows as row}
              <tr class="border-b">
                <td class="px-4 py-2">{row.label}</td>
                {#if tipo === "restaurante"}
                  <td class="px-4 py-2 text-muted-foreground">{row.classificacao || ""}</td>
                {/if}
                <td class="px-4 py-2 text-right">{formatMoney(row.sistema)}</td>
                <td class="px-4 py-2 text-right">{formatMoney(tipo === "restaurante" ? row.real : row.site)}</td>
                <td class="px-4 py-2 text-right">
                  <span class={row.status === "OK" ? "text-green-600" : "text-red-600"}>
                    {formatMoney(row.diferenca)}
                  </span>
                </td>
                <td class="px-4 py-2 text-center">
                  <span
                    class="inline-block rounded-full px-2 py-0.5 text-xs"
                    class:bg-green-100={row.status === "OK"}
                    class:text-green-700={row.status === "OK"}
                    class:bg-red-100={row.status !== "OK"}
                    class:text-red-700={row.status !== "OK"}
                  >
                    {row.status}
                  </span>
                </td>
              </tr>
            {/each}
            <tr class="border-t-2 font-bold">
              <td colspan={tipo === "restaurante" ? 3 : 2} class="px-4 py-3 text-right">
                Diferença Total:
              </td>
              <td class="px-4 py-3 text-right">
                <span class={Math.abs(totalDiff) < 0.005 ? "text-green-600" : "text-red-600"}>
                  {formatMoney(Math.round(totalDiff * 100) / 100)}
                </span>
              </td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>

      {#if tipo === "posto" && extra}
        <div class="mt-6 rounded-lg border p-4">
          <h3 class="mb-2 font-semibold">Informacoes Complementares</h3>
          <p class="text-sm">Sangria: {formatMoney(extra.sangria)}</p>
          <p class="text-sm">Notas a Prazo: {formatMoney(extra.notas_a_prazo)}</p>
          <p class="text-sm">Despesas do Posto: {formatMoney(extra.despesas)}</p>
        </div>
      {/if}

      <!-- Lancamentos Avulsos na tela de resultado -->
      <div class="mt-6 rounded-lg border p-4">
        <h3 class="mb-3 text-sm font-semibold">Lancamentos Avulsos</h3>
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <Select bind:value={avulsoTipo}>
            <option>RECEITA</option>
            <option>DESPESA</option>
          </Select>
          <Select bind:value={avulsoColuna}>
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
            placeholder="Descricao"
            class="rounded-md border bg-background px-2 py-1 text-sm"
          />
          <input
            type="text"
            bind:value={avulsoValor}
            placeholder="Valor"
            class="w-28 rounded-md border bg-background px-2 py-1 text-sm"
          />
          <button
            onclick={addAvulso}
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
                  <td class="px-3 py-1.5">
                    <button
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
    {/if}
  </div>

  <div class="flex items-center gap-3 border-t px-4 py-3">
    <button
      onclick={save}
      class="inline-flex h-9 items-center rounded-md border px-4 text-sm hover:bg-accent"
    >
      Salvar Conciliacao
    </button>
    <button
      onclick={exportPdf}
      class="ml-auto inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90"
    >
      <FileDown class="h-4 w-4" />
      Exportar PDF
    </button>
  </div>
</div>
