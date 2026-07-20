<script lang="ts">
  import { onMount } from "svelte";

  interface Grupo {
    key: string;
    label: string;
    sistema: string[];
    pagbank: { bandeira: string; forma: string }[];
    premmia: string[];
  }

  let grupos = $state<Grupo[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let feedback = $state("");
  let feedbackType = $state<"ok" | "err">("ok");

  let contagemTabBehavior = $state<"icone" | "icone_fixo">("icone");
  let savingBehavior = $state(false);

  let serial200Mode = $state<"obrigatorio_todas" | "opcional_geral" | "opcional_todas">("obrigatorio_todas");
  let savingSerial = $state(false);

  let cloudfyLogin = $state("");
  let cloudfySenha = $state("");
  let cloudfyDebug = $state(false);
  let savingCloudfy = $state(false);

  let cloudfyMap = $state<Record<string, string>>({});
  let savingMap = $state(false);
  let cloudfyPadrao = $state<Record<string, string>>({});

  let activeTab = $state<"geral" | "grupos" | "equivalencias">("geral");

  // ─── Auto-update ───
  let updChecking = $state(false);
  let updDownloading = $state(false);
  let updApplying = $state(false);
  let updInfo = $state<any>(null);
  let updError = $state("");
  let updDownloadedPath = $state("");
  let updStatus = $state("");

  async function checkUpdates() {
    updChecking = true;
    updError = "";
    updInfo = null;
    updDownloadedPath = "";
    updStatus = "";
    try {
      const res = await fetch("/api/update/check");
      const data = await res.json();
      updInfo = data;
      if (data.error) {
        updError = data.error;
      } else if (!data.update_available) {
        updStatus = `Voce ja esta na versao mais recente (${data.current_version}).`;
      }
    } catch (e: any) {
      updError = e.message || "Falha ao checar atualizacoes.";
    } finally {
      updChecking = false;
    }
  }

  async function downloadUpdate() {
    if (!updInfo?.download_url) return;
    updDownloading = true;
    updError = "";
    updStatus = "Baixando atualizacao...";
    try {
      const res = await fetch("/api/update/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ download_url: updInfo.download_url, asset_name: updInfo.asset_name }),
      });
      const data = await res.json();
      if (data.downloaded) {
        updDownloadedPath = data.path;
        updStatus = "Download concluido. Clique em Instalar para aplicar.";
      } else {
        updError = data.error || "Falha no download.";
        updStatus = "";
      }
    } catch (e: any) {
      updError = e.message || "Falha no download.";
      updStatus = "";
    } finally {
      updDownloading = false;
    }
  }

  async function installUpdate() {
    if (!updDownloadedPath) return;
    if (!confirm("O aplicativo sera fechado e reaberto para instalar a atualizacao. Continuar?")) return;
    updApplying = true;
    updError = "";
    updStatus = "Instalando... o app sera reiniciado.";
    try {
      const res = await fetch("/api/update/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: updDownloadedPath }),
      });
      const data = await res.json();
      if (!data.applied) {
        updError = data.error || "Falha ao instalar.";
        updStatus = "";
      }
    } catch (e: any) {
      // Connection likely drops as the app exits — treat as expected.
      updStatus = "Instalando... o app sera reiniciado.";
    } finally {
      updApplying = false;
    }
  }

  onMount(load);

  async function load() {
    loading = true;
    try {
      const res = await fetch("/api/conciliador/config/posto");
      if (res.ok) {
        const cfg = await res.json();
        grupos = (cfg.grupos || []).map(normalizeGrupo);
      }
      const sres = await fetch("/api/conciliador/config/settings");
      if (sres.ok) {
        const s = await sres.json();
        if (s.contagem_tab_behavior === "icone_fixo" || s.contagem_tab_behavior === "icone") {
          contagemTabBehavior = s.contagem_tab_behavior;
        }
        if (["obrigatorio_todas", "opcional_geral", "opcional_todas"].includes(s.serial_200_mode)) {
          serial200Mode = s.serial_200_mode;
        }
        cloudfyLogin = s.cloudfy_login || "";
        cloudfySenha = s.cloudfy_senha || "";
        cloudfyDebug = s.cloudfy_debug || false;
      }
      const mres = await fetch("/api/conciliador/config/mapeamento");
      if (mres.ok) {
        const m = await mres.json();
        cloudfyMap = m.mapeamento || {};
        cloudfyPadrao = m.padrao || {};
      }
    } catch {
      grupos = [];
    } finally {
      loading = false;
    }
  }

  async function saveBehavior(value: "icone" | "icone_fixo") {
    contagemTabBehavior = value;
    savingBehavior = true;
    try {
      const res = await fetch("/api/conciliador/config/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contagem_tab_behavior: value }),
      });
      if (!res.ok) throw new Error("Erro ao salvar comportamento");
      flash("Comportamento da aba de contagem atualizado.");
    } catch (e: any) {
      flash(e.message, "err");
    } finally {
      savingBehavior = false;
    }
  }

  async function saveSerialMode(value: "obrigatorio_todas" | "opcional_geral" | "opcional_todas") {
    serial200Mode = value;
    savingSerial = true;
    try {
      const res = await fetch("/api/conciliador/config/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ serial_200_mode: value }),
      });
      if (!res.ok) throw new Error("Erro ao salvar comportamento do serial");
      flash("Comportamento do serial das notas de 200 atualizado.");
    } catch (e: any) {
      flash(e.message, "err");
    } finally {
      savingSerial = false;
    }
  }

  async function saveCloudfy() {
    savingCloudfy = true;
    try {
      const res = await fetch("/api/conciliador/config/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cloudfy_login: cloudfyLogin,
          cloudfy_senha: cloudfySenha,
          cloudfy_debug: cloudfyDebug,
        }),
      });
      if (!res.ok) throw new Error("Erro ao salvar configuracoes Cloudfy");
      flash("Credenciais Cloudfy salvas.");
    } catch (e: any) {
      flash(e.message, "err");
    } finally {
      savingCloudfy = false;
    }
  }

  async function saveMap() {
    savingMap = true;
    try {
      const res = await fetch("/api/conciliador/config/mapeamento", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mapeamento: cloudfyMap }),
      });
      if (!res.ok) throw new Error("Erro ao salvar mapeamento.");
      flash("Mapeamento Cloudfy salvo.");
    } catch (e: any) {
      flash(e.message, "err");
    } finally {
      savingMap = false;
    }
  }

  function resetMap() {
    cloudfyMap = { ...cloudfyPadrao };
  }

  const restCategories = [
    "PIX", "ELO_DEBITO", "MAESTRO", "VC_ELECTRON",
    "AMEX", "ELO_CR", "MASTERCARD", "VISA",
  ];

  function normalizeGrupo(g: any): Grupo {
    return {
      key: g.key || "",
      label: g.label || g.key || "",
      sistema: Array.isArray(g.sistema) ? [...g.sistema] : [],
      pagbank: Array.isArray(g.pagbank)
        ? g.pagbank.map((p: any) => ({ bandeira: p.bandeira || "", forma: p.forma || "" }))
        : [],
      premmia: Array.isArray(g.premmia) ? [...g.premmia] : [],
    };
  }

  function flash(msg: string, type: "ok" | "err" = "ok") {
    feedback = msg;
    feedbackType = type;
    if (type === "ok") setTimeout(() => (feedback = ""), 3000);
  }

  function addGrupo() {
    grupos = [
      ...grupos,
      { key: "", label: "", sistema: [], pagbank: [], premmia: [] },
    ];
  }

  function removeGrupo(idx: number) {
    grupos = grupos.filter((_, i) => i !== idx);
  }

  function addSistema(gi: number) {
    grupos[gi].sistema = [...grupos[gi].sistema, ""];
  }
  function removeSistema(gi: number, si: number) {
    grupos[gi].sistema = grupos[gi].sistema.filter((_, i) => i !== si);
  }

  function addPremmia(gi: number) {
    grupos[gi].premmia = [...grupos[gi].premmia, ""];
  }
  function removePremmia(gi: number, si: number) {
    grupos[gi].premmia = grupos[gi].premmia.filter((_, i) => i !== si);
  }

  function addPagbank(gi: number) {
    grupos[gi].pagbank = [...grupos[gi].pagbank, { bandeira: "", forma: "" }];
  }
  function removePagbank(gi: number, pi: number) {
    grupos[gi].pagbank = grupos[gi].pagbank.filter((_, i) => i !== pi);
  }

  async function save() {
    saving = true;
    feedback = "";
    try {
      const payload = {
        grupos: grupos.map((g) => ({
          key: g.key,
          label: g.label,
          sistema: g.sistema.filter((s) => s.trim()),
          premmia: g.premmia.filter((s) => s.trim()),
          pagbank: g.pagbank.filter((p) => p.bandeira.trim() || p.forma.trim()),
        })),
      };
      const res = await fetch("/api/conciliador/config/posto", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Erro ao salvar");
      }
      const cfg = await res.json();
      grupos = (cfg.grupos || []).map(normalizeGrupo);
      flash("Configuracao salva com sucesso.");
    } catch (e: any) {
      flash(e.message, "err");
    } finally {
      saving = false;
    }
  }

  async function resetDefault() {
    if (!confirm("Restaurar a configuracao padrao? As alteracoes atuais serao perdidas.")) return;
    saving = true;
    try {
      const res = await fetch("/api/conciliador/config/posto/reset", { method: "POST" });
      if (!res.ok) throw new Error("Erro ao restaurar");
      const cfg = await res.json();
      grupos = (cfg.grupos || []).map(normalizeGrupo);
      flash("Configuracao restaurada ao padrao.");
    } catch (e: any) {
      flash(e.message, "err");
    } finally {
      saving = false;
    }
  }
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex items-center gap-3 border-b px-4 py-3">
    <div>
      <h1 class="text-lg font-bold">Configuracoes</h1>
      <p class="text-xs text-muted-foreground">
        Configuracoes gerais do conciliador (posto e restaurante)
      </p>
    </div>
    {#if activeTab === "grupos"}
      <div class="ml-auto flex gap-2">
        <button
          onclick={resetDefault}
          disabled={saving}
          class="inline-flex h-8 items-center border px-3 text-sm hover:bg-accent disabled:opacity-50"
        >
          Restaurar padrao
        </button>
        <button
          onclick={save}
          disabled={saving}
          class="inline-flex h-8 items-center bg-primary px-4 text-sm text-primary-foreground hover:bg-primary-hover disabled:opacity-50"
        >
          {saving ? "Salvando..." : "Salvar"}
        </button>
      </div>
    {/if}
  </div>

  <!-- Config sub-tabs -->
  <div class="flex border-b px-4">
    <button
      onclick={() => (activeTab = "geral")}
      class="px-4 py-2 text-sm font-medium transition-colors"
      class:border-b-2={activeTab === "geral"}
      class:border-primary={activeTab === "geral"}
      class:text-foreground={activeTab === "geral"}
      class:text-muted-foreground={activeTab !== "geral"}
    >
      Geral
    </button>
    <button
      onclick={() => (activeTab = "grupos")}
      class="px-4 py-2 text-sm font-medium transition-colors"
      class:border-b-2={activeTab === "grupos"}
      class:border-primary={activeTab === "grupos"}
      class:text-foreground={activeTab === "grupos"}
      class:text-muted-foreground={activeTab !== "grupos"}
    >
      Grupos Posto
    </button>
    <button
      onclick={() => (activeTab = "equivalencias")}
      class="px-4 py-2 text-sm font-medium transition-colors"
      class:border-b-2={activeTab === "equivalencias"}
      class:border-primary={activeTab === "equivalencias"}
      class:text-foreground={activeTab === "equivalencias"}
      class:text-muted-foreground={activeTab !== "equivalencias"}
    >
      Equivalencias
    </button>
  </div>

  {#if feedback}
    <div
      class="toast-in mx-4 mt-3 border px-4 py-2 text-sm"
      class:bg-green-50={feedbackType === "ok"}
      class:text-green-700={feedbackType === "ok"}
      class:border-green-200={feedbackType === "ok"}
      class:bg-red-50={feedbackType === "err"}
      class:text-red-700={feedbackType === "err"}
      class:border-red-200={feedbackType === "err"}
    >
      {feedback}
    </div>
  {/if}

  <div class="flex-1 overflow-auto p-4">
    {#if loading}
      <div class="flex h-full items-center justify-center">
        <p class="text-muted-foreground">Carregando...</p>
      </div>
    {:else}
      {#if activeTab === "geral"}
      <div class="space-y-4">
        <!-- Comportamento aba de contagem -->
        <div class="border p-4">
          <h2 class="text-sm font-semibold">Comportamento aba de contagem</h2>
          <p class="mb-3 text-xs text-muted-foreground">
            Define como criar novas abas de contagem de dinheiro
          </p>
          <div class="flex flex-wrap gap-2">
            <button
              onclick={() => saveBehavior("icone")}
              disabled={savingBehavior}
              class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
              class:border-primary={contagemTabBehavior === "icone"}
              class:bg-accent={contagemTabBehavior === "icone"}
              class:text-primary={contagemTabBehavior === "icone"}
              class:font-semibold={contagemTabBehavior === "icone"}
            >
              Ícone
            </button>
            <button
              onclick={() => saveBehavior("icone_fixo")}
              disabled={savingBehavior}
              class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
              class:border-primary={contagemTabBehavior === "icone_fixo"}
              class:bg-accent={contagemTabBehavior === "icone_fixo"}
              class:text-primary={contagemTabBehavior === "icone_fixo"}
              class:font-semibold={contagemTabBehavior === "icone_fixo"}
            >
              Ícone Fixo
            </button>
          </div>
          <p class="mt-2 text-xs text-muted-foreground">
            {contagemTabBehavior === "icone"
              ? "Ícone: botão + junto das abas (comportamento atual)."
              : "Ícone Fixo: botão fixo em um canto, facilita múltiplos cliques."}
          </p>
        </div>

        <!-- Serial Nota de 200 -->
        <div class="border p-4">
          <h2 class="text-sm font-semibold">Serial Nota de 200</h2>
          <p class="mb-3 text-xs text-muted-foreground">
            Define a obrigatoriedade do serial das notas de R$ 200 nas contagens
          </p>
          <div class="flex flex-wrap gap-2">
            <button
              onclick={() => saveSerialMode("obrigatorio_todas")}
              disabled={savingSerial}
              class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
              class:border-primary={serial200Mode === "obrigatorio_todas"}
              class:bg-accent={serial200Mode === "obrigatorio_todas"}
              class:text-primary={serial200Mode === "obrigatorio_todas"}
              class:font-semibold={serial200Mode === "obrigatorio_todas"}
            >
              Obrigatório em todas as contagens
            </button>
            <button
              onclick={() => saveSerialMode("opcional_geral")}
              disabled={savingSerial}
              class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
              class:border-primary={serial200Mode === "opcional_geral"}
              class:bg-accent={serial200Mode === "opcional_geral"}
              class:text-primary={serial200Mode === "opcional_geral"}
              class:font-semibold={serial200Mode === "opcional_geral"}
            >
              Opcional apenas na contagem geral
            </button>
            <button
              onclick={() => saveSerialMode("opcional_todas")}
              disabled={savingSerial}
              class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
              class:border-primary={serial200Mode === "opcional_todas"}
              class:bg-accent={serial200Mode === "opcional_todas"}
              class:text-primary={serial200Mode === "opcional_todas"}
              class:font-semibold={serial200Mode === "opcional_todas"}
            >
              Opcional em todas as contagens
            </button>
          </div>
          <p class="mt-2 text-xs text-muted-foreground">
            {serial200Mode === "obrigatorio_todas"
              ? "Serial obrigatório para cada nota de R$ 200 em qualquer contagem."
              : serial200Mode === "opcional_geral"
                ? "Serial opcional na contagem Geral, mas obrigatório nas demais contagens."
                : "Serial opcional em todas as contagens."}
          </p>
        </div>

        <!-- Cloudfy -->
        <div class="border p-4">
          <h2 class="text-sm font-semibold">Automacao Cloudfy</h2>
          <p class="mb-3 text-xs text-muted-foreground">
            Credenciais de acesso ao sistema Cloudfy para automacao de importacao
          </p>
          <div class="space-y-3">
            <div class="flex items-center gap-3">
              <label class="w-24 text-sm">Login</label>
              <input
                type="text"
                bind:value={cloudfyLogin}
                placeholder="usuario@email.com"
                class="w-64 rounded-md border bg-background px-3 py-1.5 text-sm"
              />
            </div>
            <div class="flex items-center gap-3">
              <label class="w-24 text-sm">Senha</label>
              <input
                type="password"
                bind:value={cloudfySenha}
                placeholder="Senha Cloudfy"
                class="w-64 rounded-md border bg-background px-3 py-1.5 text-sm"
              />
            </div>
            <div class="flex items-center gap-3">
              <label class="w-24 text-sm">Modo debug</label>
              <label class="flex items-center gap-2 text-sm">
                <input type="checkbox" bind:checked={cloudfyDebug} />
                Abrir navegador visivel (debug)
              </label>
            </div>
            <button
              onclick={saveCloudfy}
              disabled={savingCloudfy}
              class="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {savingCloudfy ? "Salvando..." : "Salvar credenciais"}
            </button>
          </div>
        </div>

        <!-- Atualizacoes -->
        <div class="border p-4">
          <h2 class="text-sm font-semibold">Atualizacoes</h2>
          <p class="mb-3 text-xs text-muted-foreground">
            Verifica novas versoes no repositorio oficial (ReinaldoAssis/Neo-Caixa)
          </p>
          <div class="flex flex-wrap items-center gap-2">
            <button
              onclick={checkUpdates}
              disabled={updChecking || updDownloading || updApplying}
              class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent disabled:opacity-50"
            >
              {updChecking ? "Checando..." : "Checar por atualizacoes"}
            </button>

            {#if updInfo?.update_available}
              {#if !updDownloadedPath}
                <button
                  onclick={downloadUpdate}
                  disabled={updDownloading}
                  class="inline-flex h-9 items-center bg-primary px-4 text-sm text-primary-foreground hover:bg-primary-hover disabled:opacity-50"
                >
                  {updDownloading ? "Baixando..." : `Baixar versao ${updInfo.latest_version}`}
                </button>
              {:else}
                <button
                  onclick={installUpdate}
                  disabled={updApplying}
                  class="inline-flex h-9 items-center bg-primary px-4 text-sm text-primary-foreground hover:bg-primary-hover disabled:opacity-50"
                >
                  {updApplying ? "Instalando..." : "Instalar e reiniciar"}
                </button>
              {/if}
            {/if}
          </div>

          {#if updInfo}
            <div class="mt-3 text-xs">
              <p class="text-muted-foreground">
                Versao atual: <span class="font-medium text-foreground">{updInfo.current_version}</span>
                {#if updInfo.latest_version}
                  · Ultima versao: <span class="font-medium text-foreground">{updInfo.latest_version}</span>
                {/if}
              </p>
              {#if updInfo.update_available}
                <p class="mt-1 font-medium text-primary">Nova versao disponivel!</p>
                {#if updInfo.release_notes}
                  <pre class="mt-2 max-h-40 overflow-auto whitespace-pre-wrap border bg-muted/30 p-2 text-[11px] text-muted-foreground">{updInfo.release_notes}</pre>
                {/if}
              {/if}
            </div>
          {/if}

          {#if updStatus}
            <p class="mt-2 text-xs text-green-700">{updStatus}</p>
          {/if}
          {#if updError}
            <p class="mt-2 text-xs text-red-600">{updError}</p>
          {/if}
        </div>
      </div>
      {:else}
      <div class="space-y-4">
        <h2 class="text-sm font-semibold">Grupos de conciliação (Posto)</h2>
        <p class="text-xs text-muted-foreground">
          Defina quais descricoes dos relatorios somam em cada grupo de conciliacao
        </p>
        {#each grupos as grupo, gi}
          <div class="border">
            <div class="flex flex-wrap items-center gap-3 border-b bg-muted/40 px-4 py-2">
              <div class="flex items-center gap-2">
                <label class="text-xs font-medium text-muted-foreground">Chave</label>
                <input
                  type="text"
                  bind:value={grupo.key}
                  placeholder="EX: VISA_CREDITO"
                  class="w-40 border bg-background px-2 py-1 text-sm uppercase"
                />
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs font-medium text-muted-foreground">Rotulo</label>
                <input
                  type="text"
                  bind:value={grupo.label}
                  placeholder="EX: VISA CREDITO"
                  class="w-48 border bg-background px-2 py-1 text-sm"
                />
              </div>
              <button
                onclick={() => removeGrupo(gi)}
                class="ml-auto inline-flex h-7 items-center border border-red-300 px-2 text-xs text-red-600 hover:bg-red-50"
              >
                Remover grupo
              </button>
            </div>

            <div class="grid grid-cols-1 gap-4 p-4 lg:grid-cols-3">
              <!-- Sistema (Caixa CSV) -->
              <div>
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Caixa (Sistema)
                  </span>
                  <button
                    onclick={() => addSistema(gi)}
                    class="text-xs text-primary hover:underline"
                  >
                    + adicionar
                  </button>
                </div>
                <div class="space-y-1">
                  {#each grupo.sistema as _, si}
                    <div class="flex items-center gap-1">
                      <input
                        type="text"
                        bind:value={grupo.sistema[si]}
                        placeholder="BR PREMMIA CARTAO"
                        class="flex-1 border bg-background px-2 py-1 text-sm"
                      />
                      <button
                        onclick={() => removeSistema(gi, si)}
                        class="px-1.5 text-xs text-red-500 hover:text-red-700"
                      >
                        x
                      </button>
                    </div>
                  {/each}
                  {#if grupo.sistema.length === 0}
                    <p class="text-xs text-muted-foreground">Nenhuma descricao</p>
                  {/if}
                </div>
              </div>

              <!-- PagBank (Site) -->
              <div>
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    PagBank (Site)
                  </span>
                  <button
                    onclick={() => addPagbank(gi)}
                    class="text-xs text-primary hover:underline"
                  >
                    + adicionar
                  </button>
                </div>
                <div class="space-y-1">
                  {#each grupo.pagbank as _, pi}
                    <div class="flex items-center gap-1">
                      <input
                        type="text"
                        bind:value={grupo.pagbank[pi].bandeira}
                        placeholder="Bandeira (VISA)"
                        class="flex-1 border bg-background px-2 py-1 text-sm"
                      />
                      <input
                        type="text"
                        bind:value={grupo.pagbank[pi].forma}
                        placeholder="Forma (CREDITO)"
                        class="flex-1 border bg-background px-2 py-1 text-sm"
                      />
                      <button
                        onclick={() => removePagbank(gi, pi)}
                        class="px-1.5 text-xs text-red-500 hover:text-red-700"
                      >
                        x
                      </button>
                    </div>
                  {/each}
                  {#if grupo.pagbank.length === 0}
                    <p class="text-xs text-muted-foreground">Nenhum par bandeira/forma</p>
                  {/if}
                </div>
              </div>

              <!-- Premmia (Site) -->
              <div>
                <div class="mb-2 flex items-center justify-between">
                  <span class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Premmia (Site)
                  </span>
                  <button
                    onclick={() => addPremmia(gi)}
                    class="text-xs text-primary hover:underline"
                  >
                    + adicionar
                  </button>
                </div>
                <div class="space-y-1">
                  {#each grupo.premmia as _, si}
                    <div class="flex items-center gap-1">
                      <input
                        type="text"
                        bind:value={grupo.premmia[si]}
                        placeholder="CARTAO APP"
                        class="flex-1 border bg-background px-2 py-1 text-sm"
                      />
                      <button
                        onclick={() => removePremmia(gi, si)}
                        class="px-1.5 text-xs text-red-500 hover:text-red-700"
                      >
                        x
                      </button>
                    </div>
                  {/each}
                  {#if grupo.premmia.length === 0}
                    <p class="text-xs text-muted-foreground">Nenhuma forma</p>
                  {/if}
                </div>
              </div>
            </div>
          </div>
        {/each}

        <button
          onclick={addGrupo}
          class="inline-flex h-9 items-center border border-dashed px-4 text-sm text-muted-foreground hover:bg-accent"
        >
          + Adicionar grupo
        </button>
      </div>
      {:else if activeTab === "equivalencias"}
      <div class="space-y-4">
        <h2 class="text-sm font-semibold">Mapeamento Cloudfy &rarr; Sistema</h2>
        <p class="text-xs text-muted-foreground">
          Define qual categoria do sistema cada subtipo do Cloudfy representa.
          O mapeamento usa o valor da coluna <strong>subtipo</strong> na conciliacao de cartoes.
        </p>
        <div class="border">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b bg-muted/50 text-left">
                <th class="px-4 py-2">Subtipo Cloudfy</th>
                <th class="px-4 py-2">Categoria Sistema</th>
              </tr>
            </thead>
            <tbody>
              {#each Object.keys(cloudfyPadrao) as subtipo}
                {@const key = subtipo}
                <tr class="border-b">
                  <td class="px-4 py-2 font-medium">{subtipo}</td>
                  <td class="px-4 py-2">
                    <select
                      value={cloudfyMap[key] || ""}
                      onchange={(e) => {
                        cloudfyMap = { ...cloudfyMap, [key]: (e.target as HTMLSelectElement).value };
                      }}
                      class="border bg-background px-3 py-1.5 text-sm"
                    >
                      <option value="">-- selecionar --</option>
                      {#each restCategories as cat}
                        <option value={cat}>{cat}</option>
                      {/each}
                    </select>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="flex gap-2">
          <button
            onclick={saveMap}
            disabled={savingMap}
            class="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {savingMap ? "Salvando..." : "Salvar mapeamento"}
          </button>
          <button
            onclick={resetMap}
            class="inline-flex h-9 items-center border px-4 text-sm hover:bg-accent"
          >
            Restaurar padrao
          </button>
        </div>
      </div>
      {/if}
    {/if}
  </div>
</div>
