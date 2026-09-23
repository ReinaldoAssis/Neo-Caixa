<script lang="ts">
  import { onMount } from "svelte";
  import {
    ArrowLeft,
    Calculator,
    Loader2,
    Plus,
    Trash2,
    UserPlus,
  } from "lucide-svelte";
  import Select from "./Select.svelte";

  interface Funcionario {
    id: string;
    nome: string;
    saldo: number;
    total_debitos: number;
    total_pagamentos: number;
    lancamentos: number;
  }

  interface Lancamento {
    _id: string;
    id: string;
    funcionario_id: string;
    tipo: "DEBITO" | "PAGAMENTO";
    valor: number;
    referente_a: string;
    data: string;
  }

  interface Props {
    onVoltar: () => void;
  }

  let { onVoltar }: Props = $props();

  let funcionarios = $state<Funcionario[]>([]);
  let selecionado = $state<Funcionario | null>(null);
  let lancamentos = $state<Lancamento[]>([]);
  let loading = $state(true);
  let salvandoFunc = $state(false);
  let salvandoLanc = $state(false);
  let erro = $state("");

  let novoNome = $state("");
  let novoTipo = $state("DEBITO");
  let novoValor = $state("");
  let novoReferente = $state("");

  onMount(carregarFuncionarios);

  async function carregarFuncionarios() {
    loading = true;
    try {
      const res = await fetch("/api/conciliador/saldos/funcionarios");
      if (res.ok) {
        funcionarios = await res.json();
        if (selecionado) {
          selecionado =
            funcionarios.find((f) => f.id === selecionado?.id) ?? null;
        }
        if (!selecionado && funcionarios.length > 0) {
          await selecionar(funcionarios[0]);
        }
      }
    } catch {
      erro = "Erro de conexao.";
    } finally {
      loading = false;
    }
  }

  async function carregarLancamentos(id: string) {
    try {
      const res = await fetch(
        `/api/conciliador/saldos/funcionarios/${encodeURIComponent(id)}/lancamentos`
      );
      lancamentos = res.ok ? await res.json() : [];
    } catch {
      lancamentos = [];
    }
  }

  async function selecionar(f: Funcionario) {
    selecionado = f;
    erro = "";
    await carregarLancamentos(f.id);
  }

  async function adicionarFuncionario() {
    if (!novoNome.trim()) return;
    salvandoFunc = true;
    erro = "";
    try {
      const res = await fetch("/api/conciliador/saldos/funcionarios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: novoNome }),
      });
      const data = await res.json();
      if (!res.ok) {
        erro = data.detail || "Erro ao cadastrar funcionario.";
        return;
      }
      novoNome = "";
      await carregarFuncionarios();
      const criado = funcionarios.find((f) => f.id === data.id);
      if (criado) await selecionar(criado);
    } catch {
      erro = "Erro de conexao.";
    } finally {
      salvandoFunc = false;
    }
  }

  async function removerFuncionario(f: Funcionario) {
    if (!confirm(`Remover ${f.nome} e todos os seus lancamentos?`)) return;
    await fetch(
      `/api/conciliador/saldos/funcionarios/${encodeURIComponent(f.id)}`,
      { method: "DELETE" }
    );
    if (selecionado?.id === f.id) {
      selecionado = null;
      lancamentos = [];
    }
    await carregarFuncionarios();
  }

  async function lancar() {
    if (!selecionado) return;
    const valor = avaliar(novoValor) ?? parseNumero(novoValor);
    if (valor === null || valor <= 0) {
      erro = "Informe um valor valido.";
      return;
    }
    if (!novoReferente.trim()) {
      erro = "Informe a que o lancamento se refere.";
      return;
    }
    salvandoLanc = true;
    erro = "";
    try {
      const res = await fetch("/api/conciliador/saldos/lancamentos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          funcionario_id: selecionado.id,
          tipo: novoTipo,
          valor,
          referente_a: novoReferente,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        erro = data.detail || "Erro ao lancar.";
        return;
      }
      novoValor = "";
      novoReferente = "";
      await carregarLancamentos(selecionado.id);
      await carregarFuncionarios();
    } catch {
      erro = "Erro de conexao.";
    } finally {
      salvandoLanc = false;
    }
  }

  async function removerLancamento(l: Lancamento) {
    if (!confirm("Excluir este lancamento?")) return;
    await fetch(
      `/api/conciliador/saldos/lancamentos/${encodeURIComponent(l.id)}`,
      { method: "DELETE" }
    );
    if (selecionado) {
      await carregarLancamentos(selecionado.id);
      await carregarFuncionarios();
    }
  }

  function inputKeydown(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      const resultado = avaliar(novoValor);
      if (resultado !== null) {
        novoValor = formatarNumero(resultado);
      }
    }
  }

  let previewValor = $derived(avaliar(novoValor));

  function formatarNumero(v: number): string {
    return (Math.round(v * 100) / 100).toString().replace(".", ",");
  }

  function parseNumero(texto: string): number | null {
    if (!texto) return null;
    const v = Number(texto.replace(/\s+/g, "").replace(",", "."));
    return Number.isFinite(v) ? v : null;
  }

  // Avaliador seguro de expressoes: + - * / ( ) e decimais (virgula ou ponto).
  function avaliar(expr: string): number | null {
    if (!expr) return null;
    const s = expr.replace(/\s+/g, "").replace(/,/g, ".");
    if (!/^[0-9+\-*/().]+$/.test(s)) return null;
    let i = 0;

    function parseExpr(): number {
      let v = parseTerm();
      while (s[i] === "+" || s[i] === "-") {
        const op = s[i++];
        const r = parseTerm();
        v = op === "+" ? v + r : v - r;
      }
      return v;
    }

    function parseTerm(): number {
      let v = parseFactor();
      while (s[i] === "*" || s[i] === "/") {
        const op = s[i++];
        const r = parseFactor();
        v = op === "*" ? v * r : v / r;
      }
      return v;
    }

    function parseFactor(): number {
      if (s[i] === "+") {
        i++;
        return parseFactor();
      }
      if (s[i] === "-") {
        i++;
        return -parseFactor();
      }
      if (s[i] === "(") {
        i++;
        const v = parseExpr();
        if (s[i] === ")") i++;
        return v;
      }
      const start = i;
      while (i < s.length && /[0-9.]/.test(s[i])) i++;
      if (start === i) throw new Error("expressao invalida");
      return parseFloat(s.slice(start, i));
    }

    try {
      const v = parseExpr();
      if (i !== s.length || !Number.isFinite(v)) return null;
      return Math.round(v * 100) / 100;
    } catch {
      return null;
    }
  }

  function formatMoney(value: number): string {
    const formatted = (value || 0).toFixed(2).replace(".", ",");
    return `R$ ${formatted.replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
  }
</script>

<div class="flex h-full overflow-hidden">
  <!-- Funcionarios -->
  <aside class="flex w-72 flex-col border-r">
    <div class="flex items-center gap-2 border-b px-3 py-3">
      <button
        onclick={onVoltar}
        class="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-accent"
        title="Voltar"
      >
        <ArrowLeft class="h-4 w-4" />
      </button>
      <h1 class="text-base font-bold">Saldos de caixa</h1>
    </div>

    <div class="flex items-center gap-2 border-b px-3 py-2">
      <input
        type="text"
        bind:value={novoNome}
        placeholder="Nome do funcionario"
        class="min-w-0 flex-1 rounded-md border bg-background px-2 py-1.5 text-sm"
        onkeydown={(e) => { if (e.key === "Enter") adicionarFuncionario(); }}
      />
      <button
        onclick={adicionarFuncionario}
        disabled={salvandoFunc || !novoNome.trim()}
        class="inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        title="Cadastrar funcionario"
      >
        {#if salvandoFunc}
          <Loader2 class="h-4 w-4 animate-spin" />
        {:else}
          <UserPlus class="h-4 w-4" />
        {/if}
      </button>
    </div>

    <div class="flex-1 overflow-auto">
      {#if loading}
        <div class="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
          <Loader2 class="h-4 w-4 animate-spin" />
          Carregando...
        </div>
      {:else if funcionarios.length === 0}
        <p class="p-4 text-sm text-muted-foreground">
          Nenhum funcionario cadastrado.
        </p>
      {:else}
        {#each funcionarios as f}
          <button
            type="button"
            onclick={() => selecionar(f)}
            class="flex w-full items-center justify-between gap-2 border-b px-3 py-2 text-left hover:bg-accent/50"
            class:bg-accent={selecionado?.id === f.id}
          >
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-medium">{f.nome}</span>
              <span class="block text-xs text-muted-foreground">
                {f.lancamentos} lancamento(s)
              </span>
            </span>
            <span
              class="whitespace-nowrap text-sm font-semibold"
              class:text-red-600={f.saldo > 0.005}
              class:text-green-600={f.saldo < -0.005}
            >
              {formatMoney(f.saldo)}
            </span>
          </button>
        {/each}
      {/if}
    </div>
  </aside>

  <!-- Detalhe -->
  <section class="flex min-w-0 flex-1 flex-col overflow-hidden">
    {#if !selecionado}
      <div class="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
        Selecione ou cadastre um funcionario.
      </div>
    {:else}
      <div class="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 class="text-lg font-bold">{selecionado.nome}</h2>
          <p class="text-xs text-muted-foreground">
            Debitos {formatMoney(selecionado.total_debitos)} -
            Pagamentos {formatMoney(selecionado.total_pagamentos)}
          </p>
        </div>
        <div class="text-right">
          <p class="text-xs text-muted-foreground">Saldo devedor</p>
          <p
            class="text-xl font-bold"
            class:text-red-600={selecionado.saldo > 0.005}
            class:text-green-600={selecionado.saldo < -0.005}
          >
            {formatMoney(selecionado.saldo)}
          </p>
        </div>
        <button
          onclick={() => selecionado && removerFuncionario(selecionado)}
          class="inline-flex h-8 w-8 items-center justify-center rounded-md border text-red-600 hover:bg-red-50"
          title="Remover funcionario"
        >
          <Trash2 class="h-4 w-4" />
        </button>
      </div>

      <div class="flex flex-wrap items-end gap-3 border-b bg-muted/20 px-4 py-3">
        <label class="flex flex-col gap-1 text-xs text-muted-foreground">
          Tipo
          <Select bind:value={novoTipo}>
            <option value="DEBITO">Saldo devedor</option>
            <option value="PAGAMENTO">Pagamento</option>
          </Select>
        </label>
        <label class="flex flex-col gap-1 text-xs text-muted-foreground">
          Valor
          <div class="relative">
            <input
              type="text"
              bind:value={novoValor}
              placeholder="100/4"
              class="w-36 rounded-md border bg-background px-2 py-1.5 text-sm"
              onkeydown={inputKeydown}
            />
            {#if previewValor !== null}
              <span class="absolute -bottom-4 left-0 text-[11px] text-primary">
                = {formatMoney(previewValor)}
              </span>
            {/if}
          </div>
        </label>
        <label class="flex flex-col gap-1 text-xs text-muted-foreground">
          Referente a
          <input
            type="text"
            bind:value={novoReferente}
            placeholder="Quebra de caixa"
            class="w-64 rounded-md border bg-background px-2 py-1.5 text-sm"
            onkeydown={(e) => { if (e.key === "Enter") lancar(); }}
          />
        </label>
        <button
          onclick={lancar}
          disabled={salvandoLanc}
          class="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {#if salvandoLanc}
            <Loader2 class="h-4 w-4 animate-spin" />
          {:else}
            <Plus class="h-4 w-4" />
          {/if}
          Lancar
        </button>
        <span class="flex items-center gap-1 text-[11px] text-muted-foreground">
          <Calculator class="h-3.5 w-3.5" />
          Contas inline: 100/4, 20*5, 10-2
        </span>
      </div>

      {#if erro}
        <div class="border-b bg-red-50 px-4 py-2 text-sm text-red-700">{erro}</div>
      {/if}

      <div class="flex-1 overflow-auto">
        {#if lancamentos.length === 0}
          <p class="p-6 text-sm text-muted-foreground">
            Nenhum lancamento para este funcionario.
          </p>
        {:else}
          <table class="w-full text-sm">
            <thead>
              <tr class="sticky top-0 border-b bg-muted/50 text-left">
                <th class="px-4 py-2">Data</th>
                <th class="px-4 py-2">Tipo</th>
                <th class="px-4 py-2">Referente a</th>
                <th class="px-4 py-2 text-right">Valor</th>
                <th class="px-4 py-2 text-right">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {#each lancamentos as l}
                <tr class="border-b hover:bg-accent/40">
                  <td class="px-4 py-2 whitespace-nowrap">{l.data}</td>
                  <td class="px-4 py-2">
                    <span
                      class="rounded-full px-2 py-0.5 text-xs"
                      class:bg-red-100={l.tipo === "DEBITO"}
                      class:text-red-700={l.tipo === "DEBITO"}
                      class:bg-green-100={l.tipo === "PAGAMENTO"}
                      class:text-green-700={l.tipo === "PAGAMENTO"}
                    >
                      {l.tipo === "DEBITO" ? "Saldo devedor" : "Pagamento"}
                    </span>
                  </td>
                  <td class="px-4 py-2">{l.referente_a}</td>
                  <td
                    class="px-4 py-2 text-right whitespace-nowrap"
                    class:text-red-600={l.tipo === "DEBITO"}
                    class:text-green-600={l.tipo === "PAGAMENTO"}
                  >
                    {formatMoney(l.valor)}
                  </td>
                  <td class="px-4 py-2 text-right">
                    <button
                      onclick={() => removerLancamento(l)}
                      class="rounded px-2 py-0.5 text-xs text-red-600 hover:bg-red-50"
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    {/if}
  </section>
</div>
