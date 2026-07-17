<script lang="ts">
  interface Props {
    readonly: boolean;
    contagens: any[];
    onChange?: () => void;
    tabBehavior?: "icone" | "icone_fixo";
    serialMode?: "obrigatorio_todas" | "opcional_geral" | "opcional_todas";
  }

  let { readonly = false, contagens = $bindable([] as any[]), onChange, tabBehavior = "icone", serialMode = "obrigatorio_todas" }: Props = $props();

  const denominations = [200, 100, 50, 20, 10, 5, 2];
  let activeTab = $state(0);

  function serialRequired(contagem: any): boolean {
    if (serialMode === "opcional_todas") return false;
    if (serialMode === "opcional_geral") return contagem?.label !== "Geral";
    return true;
  }

  if (contagens.length === 0) {
    contagens = [{
      id: crypto.randomUUID(),
      label: "Geral",
      editado: false,
      notas: Object.fromEntries(denominations.map(d => [String(d), 0])),
      seriais_200: [] as string[],
      moedas: "",
      depositos: "",
      total: 0,
    }];
  }

  const activeContagem = $derived(contagens[activeTab]);

  function tabClass(idx: number): string {
    const base = "inline-flex items-center gap-1 border border-b-0 px-3 py-1 text-sm transition-colors";
    if (idx === activeTab) return base + " bg-background font-semibold text-primary border-primary";
    return base + " bg-muted/50 text-muted-foreground";
  }

  function nextLabel(): string {
    let max = 0;
    for (const c of contagens) {
      if (c.label === "Geral") continue;
      const n = parseInt(String(c.label).trim(), 10);
      if (!isNaN(n) && n > max) max = n;
    }
    return String(max + 1);
  }

  function formatMoney(value: number): string {
    if (!value && value !== 0) return "-";
    const formatted = value.toFixed(2).replace(".", ",");
    return `R$ ${formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }

  function parseDecimal(v: any): number {
    if (typeof v === "number") return isNaN(v) ? 0 : v;
    if (v === null || v === undefined) return 0;
    let s = String(v).trim();
    if (!s) return 0;
    if (s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
    const n = parseFloat(s);
    return isNaN(n) ? 0 : Math.round(n * 100) / 100;
  }

  function evalExpr(v: string): string {
    const m = v.match(/^([\d,.]+)\s*([+\-])\s*([\d,.]+)$/);
    if (!m) return v;
    const a = parseDecimal(m[1]), b = parseDecimal(m[3]);
    const r = m[2] === "+" ? a + b : a - b;
    return String(Math.round(r * 100) / 100).replace(".", ",");
  }

  function sanitizeDecimal(v: string): string {
    let s = v.replace(/[^\d,]/g, "");
    const i = s.indexOf(",");
    if (i !== -1) s = s.slice(0, i + 1) + s.slice(i + 1).replace(/,/g, "");
    return s;
  }

  function recalculate(contagem: any) {
    const notas = contagem.notas || {};
    let total = 0;
    for (const denom of denominations) {
      const qty = parseInt(notas[String(denom)] || "0") || 0;
      total += qty * denom;
    }
    total += parseDecimal(contagem.moedas);
    total += parseDecimal(contagem.depositos);
    contagem.total = Math.round(total * 100) / 100;
    syncSerials(contagem);
    refreshGeral();
    contagens = [...contagens];
    if (onChange) onChange();
  }

  function syncSerials(contagem: any) {
    const qty200 = parseInt(contagem.notas?.["200"] || "0") || 0;
    const seriais = contagem.seriais_200 || [];
    while (seriais.length < qty200) seriais.push("");
    while (seriais.length > qty200) seriais.pop();
    contagem.seriais_200 = seriais;
  }

  function refreshGeral() {
    const geral = contagens.find((c: any) => c.label === "Geral" && !c.editado);
    if (!geral) return;

    const totalNotas: Record<string, number> = {};
    for (const d of denominations) totalNotas[String(d)] = 0;
    let totalMoedas = 0;
    let totalDepositos = 0;
    const allSerials: string[] = [];

    for (const c of contagens) {
      if (c === geral) continue;
      for (const d of denominations) {
        totalNotas[String(d)] = (totalNotas[String(d)] || 0) + (parseInt(c.notas?.[String(d)] || "0") || 0);
      }
      totalMoedas += parseDecimal(c.moedas);
      totalDepositos += parseDecimal(c.depositos);
      if (c.seriais_200) allSerials.push(...c.seriais_200.filter((s: string) => s));
    }

    let grand = 0;
    for (const d of denominations) {
      grand += (totalNotas[String(d)] || 0) * d;
      geral.notas = { ...geral.notas, [String(d)]: totalNotas[String(d)] };
    }
    grand += totalMoedas + totalDepositos;
    geral.moedas = Math.round(totalMoedas * 100) / 100;
    geral.depositos = Math.round(totalDepositos * 100) / 100;
    geral.total = Math.round(grand * 100) / 100;
    geral.seriais_200 = allSerials;
  }

  function addContagem() {
    const c = {
      id: crypto.randomUUID(),
      label: nextLabel(),
      notas: Object.fromEntries(denominations.map(d => [String(d), 0])),
      seriais_200: [] as string[],
      moedas: "",
      depositos: "",
      total: 0,
    };
    contagens = [...contagens, c];
    activeTab = contagens.length - 1;
    refreshGeral();
  }

  function removeContagem(idx: number) {
    if (idx === 0) return;
    contagens = contagens.filter((_: any, i: number) => i !== idx);
    if (activeTab >= contagens.length) activeTab = contagens.length - 1;
    refreshGeral();
    if (onChange) onChange();
  }

  function removeActive() {
    if (activeTab === 0) return;
    removeContagem(activeTab);
  }

  function toggleGeralEdit() {
    const geral = contagens[0];
    if (!geral) return;
    geral.editado = !geral.editado;
    if (!geral.editado) refreshGeral();
    contagens = contagens;
  }

  function handleNotaChange(contagem: any, denom: number, e: Event) {
    const val = (e.target as HTMLInputElement).value.replace(/\D/g, "");
    contagem.notas = { ...contagem.notas, [String(denom)]: val };
    recalculate(contagem);
  }
</script>

<div class="space-y-2">
  <!-- Tab buttons -->
  <div class="flex items-center gap-2">
    <div class="flex flex-1 flex-wrap items-center gap-1 border-b">
      {#each contagens as contagem, idx}
        <button
          onclick={() => (activeTab = idx)}
          class={tabClass(idx)}
        >
          {contagem.label}
        </button>
      {/each}
      {#if !readonly && tabBehavior === "icone"}
        <button
          onclick={addContagem}
          class="inline-flex h-7 w-7 items-center justify-center text-sm text-muted-foreground hover:bg-accent"
          title="Nova Contagem"
        >
          +
        </button>
      {/if}
    </div>
    {#if !readonly && tabBehavior === "icone_fixo"}
      <button
        onclick={addContagem}
        class="inline-flex h-8 shrink-0 items-center gap-1 bg-primary px-3 text-sm text-primary-foreground hover:bg-primary-hover"
        title="Nova Contagem"
      >
        + Nova Contagem
      </button>
    {/if}
  </div>

  {#if activeContagem}
    <div class="border p-3">
      <div class="mb-2 flex items-center gap-2">
        {#if activeContagem.label !== "Geral" || activeContagem.editado}
          <input
            type="text"
            bind:value={activeContagem.label}
            disabled={readonly}
            class="border bg-background px-2 py-1 text-sm font-semibold w-28"
          />
        {:else}
          <span class="font-semibold">{activeContagem.label}</span>
          <span class="text-xs text-muted-foreground">(soma automatica das demais contagens)</span>
        {/if}
        {#if !readonly && activeTab !== 0}
          <button
            onclick={removeActive}
            class="ml-auto inline-flex h-7 items-center gap-1 border border-red-300 px-2 text-xs text-red-600 hover:bg-red-50"
            title="Excluir esta contagem"
          >
            Excluir contagem
          </button>
        {/if}
      </div>

      <table class="w-full text-sm">
        <thead>
          <tr class="border-b text-left text-muted-foreground">
            <th class="pb-1 pr-4 font-medium">Cedula</th>
            <th class="pb-1 pr-4 font-medium">Valor Unit.</th>
            <th class="pb-1 pr-4 font-medium">Qtde.</th>
            <th class="pb-1 pr-4 text-right font-medium">Subtotal</th>
          </tr>
        </thead>
        <tbody>
          {#each denominations as denom}
            <tr class="border-b">
              <td class="py-0.5 pr-4">R$ {denom}</td>
              <td class="py-0.5 pr-4 text-muted-foreground">{formatMoney(denom)}</td>
              <td class="py-0.5 pr-4">
                <input
                  type="text"
                  value={activeContagem.notas[String(denom)] || "0"}
                  oninput={(e) => handleNotaChange(activeContagem, denom, e)}
                  disabled={readonly || (activeContagem.label === "Geral" && !activeContagem.editado)}
                  class="w-16 border bg-background px-2 py-0.5 text-sm"
                />
              </td>
              <td class="py-0.5 text-right tabular-nums">{formatMoney((parseInt(activeContagem.notas[String(denom)] || "0") || 0) * denom)}</td>
            </tr>
          {/each}
          <tr class="border-b">
            <td class="py-0.5 pr-4">Moedas</td>
            <td></td>
            <td class="py-0.5 pr-4">
              <input
                type="text"
                inputmode="decimal"
                value={activeContagem.moedas || ""}
                oninput={(e) => { const t = e.target as HTMLInputElement; const v = sanitizeDecimal(t.value); activeContagem.moedas = v; recalculate(activeContagem); }}
                onkeydown={(e) => { if (e.key !== "Enter") return; e.preventDefault(); const t = e.target as HTMLInputElement; const r = evalExpr(t.value); if (r !== t.value) { t.value = r; activeContagem.moedas = sanitizeDecimal(r); recalculate(activeContagem); } }}
                disabled={readonly || (activeContagem.label === "Geral" && !activeContagem.editado)}
                placeholder="0,00"
                class="w-24 border bg-background px-2 py-0.5 text-sm"
              />
            </td>
            <td></td>
          </tr>
          <tr class="border-b">
            <td class="py-0.5 pr-4">Depositos</td>
            <td></td>
            <td class="py-0.5 pr-4">
              <input
                type="text"
                inputmode="decimal"
                value={activeContagem.depositos || ""}
                oninput={(e) => { const t = e.target as HTMLInputElement; const v = sanitizeDecimal(t.value); activeContagem.depositos = v; recalculate(activeContagem); }}
                onkeydown={(e) => { if (e.key !== "Enter") return; e.preventDefault(); const t = e.target as HTMLInputElement; const r = evalExpr(t.value); if (r !== t.value) { t.value = r; activeContagem.depositos = sanitizeDecimal(r); recalculate(activeContagem); } }}
                disabled={readonly || (activeContagem.label === "Geral" && !activeContagem.editado)}
                placeholder="0,00"
                class="w-24 border bg-background px-2 py-0.5 text-sm"
              />
            </td>
            <td></td>
          </tr>
          <tr class="border-t-2 border-primary/30 bg-primary/5 font-bold">
            <td class="py-1 pr-4" colspan="3">Total (Moedas: {formatMoney(activeContagem.moedas || 0)})</td>
            <td class="py-1 text-right tabular-nums text-primary">{formatMoney(activeContagem.total)}</td>
          </tr>
        </tbody>
      </table>

      <!-- Seriais R$ 200 -->
      <div class="mt-2">
        <p class="mb-1 text-xs text-muted-foreground">
          {#if activeContagem.label !== "Geral" || activeContagem.editado}
            Seriais das notas de R$ 200 ({activeContagem.seriais_200?.length || 0})
            {serialRequired(activeContagem) ? "" : "(opcional)"}:
          {:else}
            Seriais somados de todas as contagens ({activeContagem.seriais_200?.length || 0}):
          {/if}
        </p>
        {#if (activeContagem.seriais_200 || []).length > 0}
          <div class="flex flex-wrap gap-1">
            {#each activeContagem.seriais_200 as serial, si}
              {#if activeContagem.label !== "Geral" || activeContagem.editado}
                <input
                  type="text"
                  bind:value={activeContagem.seriais_200[si]}
                  disabled={readonly}
                  maxlength={5}
                  placeholder="00000"
                  class="w-16 border bg-background px-2 py-0.5 text-sm"
                />
              {:else}
                <span class="bg-muted px-2 py-0.5 text-sm">{serial}</span>
              {/if}
            {/each}
          </div>
        {:else}
          <span class="text-xs text-muted-foreground">Nenhuma nota de R$ 200</span>
        {/if}
      </div>
    </div>
  {/if}

  {#if !readonly}
    <div class="flex gap-3">
      <button
        onclick={toggleGeralEdit}
        class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
      >
        {contagens[0]?.editado ? "Reverter ao automatico" : "Editar Geral"}
      </button>
    </div>
  {/if}
</div>
