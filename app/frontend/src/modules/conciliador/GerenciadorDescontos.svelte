<script lang="ts">
  import { onMount } from "svelte";
  import { ArrowLeft, Check, Loader2, RefreshCw, Search, Trash2 } from "lucide-svelte";

  interface Desconto {
    _id: string;
    tipo: string;
    motivo: string;
    data: string;
    caixa: string;
    cupom: string;
    qtde_itens: string;
    valor: number;
    cliente: string;
    forma_pagamento: string;
    conferido: boolean;
  }

  interface Props {
    onVoltar: () => void;
  }

  let { onVoltar }: Props = $props();

  let descontos = $state<Desconto[]>([]);
  let loading = $state(true);
  let syncing = $state(false);
  let mensagem = $state("");
  let erro = $state("");

  let filtroDataIni = $state("");
  let filtroDataFim = $state("");
  let filtroCupom = $state("");
  let filtroCliente = $state("");
  let filtroMotivo = $state("");

  let menu = $state<{ x: number; y: number; d: Desconto } | null>(null);

  function abrirMenu(event: MouseEvent, d: Desconto) {
    event.preventDefault();
    menu = { x: event.clientX, y: event.clientY, d };
  }

  function fecharMenu() {
    menu = null;
  }

  async function excluir(d: Desconto) {
    fecharMenu();
    if (!confirm(`Excluir o cupom ${d.cupom} (${d.data})?`)) return;
    descontos = descontos.filter((item) => item._id !== d._id);
    try {
      const res = await fetch(
        `/api/conciliador/descontos/${encodeURIComponent(d._id)}`,
        { method: "DELETE" }
      );
      if (!res.ok) {
        await load();
      }
    } catch {
      await load();
    }
  }

  onMount(load);

  async function load() {
    loading = true;
    erro = "";
    try {
      const res = await fetch("/api/conciliador/descontos");
      if (res.ok) {
        descontos = await res.json();
      } else {
        erro = "Erro ao carregar descontos.";
      }
    } catch {
      erro = "Erro de conexao.";
    } finally {
      loading = false;
    }
  }

  async function sincronizar() {
    if (syncing) return;
    syncing = true;
    erro = "";
    mensagem = "";
    try {
      const res = await fetch("/api/conciliador/descontos/sync", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        erro = data.detail || "Erro ao sincronizar com o Cloudfy.";
        return;
      }
      mensagem = `${data.baixados} cupom(ns) baixado(s) - ${data.inseridos} novo(s), ${data.ignorados} ja existente(s).`;
      await load();
    } catch {
      erro = "Erro de conexao.";
    } finally {
      syncing = false;
    }
  }

  async function toggle(d: Desconto) {
    const alvo = !d.conferido;
    descontos = descontos.map((item) =>
      item._id === d._id ? { ...item, conferido: alvo } : item
    );
    try {
      const res = await fetch(
        `/api/conciliador/descontos/${encodeURIComponent(d._id)}/conferido`,
        { method: "POST" }
      );
      if (!res.ok) {
        descontos = descontos.map((item) =>
          item._id === d._id ? { ...item, conferido: !alvo } : item
        );
      }
    } catch {
      descontos = descontos.map((item) =>
        item._id === d._id ? { ...item, conferido: !alvo } : item
      );
    }
  }

  function isoFromBr(br: string): string {
    const [d, m, y] = (br || "").split("/");
    if (!d || !m || !y) return "";
    return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }

  let filtrados = $derived(
    descontos.filter((d) => {
      const iso = isoFromBr(d.data);
      if (filtroDataIni && iso && iso < filtroDataIni) return false;
      if (filtroDataFim && iso && iso > filtroDataFim) return false;
      if (filtroCupom && !d.cupom.includes(filtroCupom.trim())) return false;
      if (filtroCliente && !d.cliente.toLowerCase().includes(filtroCliente.trim().toLowerCase()))
        return false;
      if (filtroMotivo && !d.motivo.toLowerCase().includes(filtroMotivo.trim().toLowerCase()))
        return false;
      return true;
    })
  );

  let totalValor = $derived(filtrados.reduce((acc, d) => acc + (d.valor || 0), 0));
  let totalConferidos = $derived(filtrados.filter((d) => d.conferido).length);

  function formatMoney(value: number): string {
    const formatted = (value || 0).toFixed(2).replace(".", ",");
    return `R$ ${formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }

  function limparFiltros() {
    filtroDataIni = "";
    filtroDataFim = "";
    filtroCupom = "";
    filtroCliente = "";
    filtroMotivo = "";
  }
</script>

<svelte:window
  onclick={fecharMenu}
  onkeydown={(e) => { if (e.key === "Escape") fecharMenu(); }}
/>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <button
      onclick={onVoltar}
      class="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-accent"
      title="Voltar"
    >
      <ArrowLeft class="h-4 w-4" />
    </button>
    <h1 class="text-lg font-bold">Gerenciador de Descontos</h1>
    <button
      onclick={sincronizar}
      disabled={syncing}
      class="ml-auto inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      title="Puxar novos descontos do Cloudfy"
    >
      {#if syncing}
        <Loader2 class="h-4 w-4 animate-spin" />
        Buscando...
      {:else}
        <RefreshCw class="h-4 w-4" />
        Atualizar
      {/if}
    </button>
  </div>

  <div class="flex flex-wrap items-end gap-3 border-b px-4 py-3">
    <label class="flex flex-col gap-1 text-xs text-muted-foreground">
      Data inicial
      <input type="date" bind:value={filtroDataIni} class="rounded-md border bg-background px-2 py-1 text-sm text-foreground" />
    </label>
    <label class="flex flex-col gap-1 text-xs text-muted-foreground">
      Data final
      <input type="date" bind:value={filtroDataFim} class="rounded-md border bg-background px-2 py-1 text-sm text-foreground" />
    </label>
    <label class="flex flex-col gap-1 text-xs text-muted-foreground">
      Cupom
      <input type="text" bind:value={filtroCupom} placeholder="12345" class="w-28 rounded-md border bg-background px-2 py-1 text-sm text-foreground" />
    </label>
    <label class="flex flex-col gap-1 text-xs text-muted-foreground">
      Cliente
      <input type="text" bind:value={filtroCliente} placeholder="Nome" class="w-44 rounded-md border bg-background px-2 py-1 text-sm text-foreground" />
    </label>
    <label class="flex flex-col gap-1 text-xs text-muted-foreground">
      Motivo
      <input type="text" bind:value={filtroMotivo} placeholder="Desconto..." class="w-44 rounded-md border bg-background px-2 py-1 text-sm text-foreground" />
    </label>
    <button
      onclick={limparFiltros}
      class="inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-sm hover:bg-accent"
    >
      <Search class="h-3.5 w-3.5" />
      Limpar
    </button>
  </div>

  {#if erro}
    <div class="border-b bg-red-50 px-4 py-2 text-sm text-red-700">{erro}</div>
  {/if}
  {#if mensagem}
    <div class="border-b bg-green-50 px-4 py-2 text-sm text-green-700">{mensagem}</div>
  {/if}

  <div class="flex-1 overflow-auto">
    {#if loading}
      <div class="flex h-full items-center justify-center gap-2 text-muted-foreground">
        <Loader2 class="h-5 w-5 animate-spin" />
        Carregando descontos...
      </div>
    {:else if filtrados.length === 0}
      <div class="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <p>Nenhum desconto de venda a prazo encontrado.</p>
        <p class="text-xs">Clique em "Atualizar" para puxar os dados do Cloudfy.</p>
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead>
          <tr class="sticky top-0 border-b bg-muted/50 text-left">
            <th class="px-3 py-2">Tipo</th>
            <th class="px-3 py-2">Motivo</th>
            <th class="px-3 py-2">Data</th>
            <th class="px-3 py-2">Caixa</th>
            <th class="px-3 py-2">Cupom</th>
            <th class="px-3 py-2 text-right">Qtde. itens</th>
            <th class="px-3 py-2 text-right">Valor</th>
            <th class="px-3 py-2">Cliente</th>
            <th class="px-3 py-2">Forma de pagamento</th>
            <th class="px-3 py-2 text-center">Conferido</th>
          </tr>
        </thead>
        <tbody>
          {#each filtrados as d}
            <tr
              class="cursor-pointer border-b hover:bg-accent/50"
              class:bg-green-50={d.conferido}
              onclick={() => toggle(d)}
              oncontextmenu={(e) => abrirMenu(e, d)}
            >
              <td class="px-3 py-2">{d.tipo}</td>
              <td class="px-3 py-2">{d.motivo}</td>
              <td class="px-3 py-2 whitespace-nowrap">{d.data}</td>
              <td class="px-3 py-2">{d.caixa}</td>
              <td class="px-3 py-2">{d.cupom}</td>
              <td class="px-3 py-2 text-right">{d.qtde_itens}</td>
              <td class="px-3 py-2 text-right whitespace-nowrap">{formatMoney(d.valor)}</td>
              <td class="px-3 py-2">{d.cliente || "-"}</td>
              <td class="px-3 py-2">{d.forma_pagamento}</td>
              <td class="px-3 py-2 text-center">
                <span
                  class="inline-flex h-5 w-5 items-center justify-center rounded border"
                  class:bg-primary={d.conferido}
                  class:border-primary={d.conferido}
                  class:text-primary-foreground={d.conferido}
                >
                  {#if d.conferido}
                    <Check class="h-3.5 w-3.5" />
                  {/if}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <div class="flex items-center gap-4 border-t px-4 py-2 text-sm text-muted-foreground">
    <span>{filtrados.length} cupom(ns)</span>
    <span>{totalConferidos} conferido(s)</span>
    <span class="ml-auto font-medium text-foreground">Total: {formatMoney(totalValor)}</span>
  </div>
</div>

{#if menu}
  <div
    class="fixed z-50 min-w-40 rounded-md border bg-background py-1 shadow-lg"
    style="left: {menu.x}px; top: {menu.y}px;"
    onclick={(e) => e.stopPropagation()}
    role="menu"
  >
    <div class="border-b px-3 py-1.5 text-xs text-muted-foreground">
      Cupom {menu.d.cupom} - {menu.d.data}
    </div>
    <button
      type="button"
      class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
      onclick={() => excluir(menu.d)}
    >
      <Trash2 class="h-4 w-4" />
      Excluir
    </button>
  </div>
{/if}
