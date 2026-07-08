<script lang="ts">
  import Historico from "./Historico.svelte";
  import Importacao from "./Importacao.svelte";
  import Resultado from "./Resultado.svelte";
  import ConfigPosto from "./ConfigPosto.svelte";

  type Tipo = "posto" | "restaurante";
  type View = "historico" | "importacao" | "resultado";

  let activeTipo = $state<Tipo>("posto");
  let showConfig = $state(false);

  let postoView = $state<View>("historico");
  let postoId = $state<string | null>(null);
  let postoConciliacao = $state<any>(null);

  let restView = $state<View>("historico");
  let restId = $state<string | null>(null);
  let restConciliacao = $state<any>(null);

  function showImportacao(t: Tipo, id: string | null = null) {
    if (t === "posto") {
      postoView = "importacao";
      postoId = id;
      postoConciliacao = null;
    } else {
      restView = "importacao";
      restId = id;
      restConciliacao = null;
    }
  }

  function showResultado(t: Tipo, c: any) {
    if (t === "posto") {
      postoConciliacao = c;
      postoView = "resultado";
    } else {
      restConciliacao = c;
      restView = "resultado";
    }
  }

  function backToHistorico(t: Tipo) {
    if (t === "posto") {
      postoView = "historico";
      postoId = null;
      postoConciliacao = null;
    } else {
      restView = "historico";
      restId = null;
      restConciliacao = null;
    }
  }

  function backToImportacao(t: Tipo, c: any) {
    if (t === "posto") {
      postoConciliacao = c;
      postoView = "importacao";
    } else {
      restConciliacao = c;
      restView = "importacao";
    }
  }

  function novoPosto() {
    activeTipo = "posto";
    showImportacao("posto");
  }

  function novoRestaurante() {
    activeTipo = "restaurante";
    showImportacao("restaurante");
  }
</script>

<div class="flex h-full flex-col overflow-hidden">
  <!-- Top header with tabs and action buttons -->
  <div class="flex items-center border-b">
    <div class="flex">
      <button
        onclick={() => { activeTipo = "posto"; }}
        class="px-4 py-2.5 text-sm font-medium transition-colors"
        class:border-b-2={activeTipo === "posto"}
        class:border-primary={activeTipo === "posto"}
        class:text-foreground={activeTipo === "posto"}
        class:text-muted-foreground={activeTipo !== "posto"}
      >
        Posto
      </button>
      <button
        onclick={() => { activeTipo = "restaurante"; showConfig = false; }}
        class="px-4 py-2.5 text-sm font-medium transition-colors"
        class:border-b-2={activeTipo === "restaurante"}
        class:border-primary={activeTipo === "restaurante"}
        class:text-foreground={activeTipo === "restaurante"}
        class:text-muted-foreground={activeTipo !== "restaurante"}
      >
        Restaurante
      </button>
    </div>
    <div class="ml-auto flex gap-2 px-4">
      {#if activeTipo === "posto"}
        <button
          onclick={() => (showConfig = !showConfig)}
          class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent"
          class:bg-accent={showConfig}
          class:text-primary={showConfig}
        >
          {showConfig ? "Voltar" : "Configuracoes"}
        </button>
      {/if}
      <button
        onclick={novoPosto}
        class="inline-flex h-8 items-center bg-primary px-3 text-sm text-primary-foreground hover:bg-primary-hover"
      >
        + Novo Posto
      </button>
      <button
        onclick={novoRestaurante}
        class="inline-flex h-8 items-center bg-primary px-3 text-sm text-primary-foreground hover:bg-primary-hover"
      >
        + Novo Restaurante
      </button>
    </div>
  </div>

  <!-- Config view (posto) -->
  {#if activeTipo === "posto" && showConfig}
    <ConfigPosto />
  {:else if activeTipo === "posto"}
    {#if postoView === "historico"}
      <Historico
        tipo="posto"
        onNovo={() => showImportacao("posto")}
        onAbrir={(id) => showImportacao("posto", id)}
      />
    {:else if postoView === "importacao"}
      <Importacao
        tipo="posto"
        conciliacaoId={postoId}
        onVoltar={() => backToHistorico("posto")}
        onResultado={(c) => showResultado("posto", c)}
        onSalvo={() => backToHistorico("posto")}
      />
    {:else if postoView === "resultado"}
      <Resultado
        caixa={postoConciliacao}
        tipo="posto"
        onVoltar={() => backToImportacao("posto", postoConciliacao)}
        onSalvo={() => backToHistorico("posto")}
      />
    {/if}
  {:else}
    <!-- Restaurante content -->
    {#if restView === "historico"}
      <Historico
        tipo="restaurante"
        onNovo={() => showImportacao("restaurante")}
        onAbrir={(id) => showImportacao("restaurante", id)}
      />
    {:else if restView === "importacao"}
      <Importacao
        tipo="restaurante"
        conciliacaoId={restId}
        onVoltar={() => backToHistorico("restaurante")}
        onResultado={(c) => showResultado("restaurante", c)}
        onSalvo={() => backToHistorico("restaurante")}
      />
    {:else if restView === "resultado"}
      <Resultado
        caixa={restConciliacao}
        tipo="restaurante"
        onVoltar={() => backToImportacao("restaurante", restConciliacao)}
        onSalvo={() => backToHistorico("restaurante")}
      />
    {/if}
  {/if}
</div>
