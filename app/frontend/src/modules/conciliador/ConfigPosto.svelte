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

  onMount(load);

  async function load() {
    loading = true;
    try {
      const res = await fetch("/api/conciliador/config/posto");
      if (res.ok) {
        const cfg = await res.json();
        grupos = (cfg.grupos || []).map(normalizeGrupo);
      }
    } catch {
      grupos = [];
    } finally {
      loading = false;
    }
  }

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
      <h1 class="text-lg font-bold">Configuracao de Grupos - Posto</h1>
      <p class="text-xs text-muted-foreground">
        Defina quais descricoes dos relatorios somam em cada grupo de conciliacao
      </p>
    </div>
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
      <div class="space-y-4">
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
    {/if}
  </div>
</div>
