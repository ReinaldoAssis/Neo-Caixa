<script lang="ts">
  import { onMount } from "svelte";
  import { initRouter, navigate, currentRoute } from "./lib/router.svelte.ts";
  import Counter from "./modules/counter/Counter.svelte";
  import Conciliador from "./modules/conciliador/Conciliador.svelte";

  let modules: Record<string, any> = $state({});
  let defaultModule = $state<string | null>(null);
  let sidebarOpen = $state(true);
  let ready = $state(false);

  async function loadModules() {
    try {
      const res = await fetch("/api/modules");
      const data = await res.json();
      modules = data.modules || {};
      defaultModule = data.default_module ?? null;
    } catch {
      modules = {};
      defaultModule = null;
    } finally {
      ready = true;
    }
  }

  onMount(() => {
    initRouter();
    loadModules();
  });

  $effect(() => {
    if (
      ready &&
      currentRoute.path === "/" &&
      defaultModule &&
      modules[defaultModule]?.menus?.[0]?.route
    ) {
      navigate(modules[defaultModule].menus[0].route);
    }
  });

  function moduleRoute(manifest: any): string {
    return manifest?.menus?.[0]?.route ?? "";
  }

  function moduleNameForRoute(route: string): string {
    for (const [, m] of Object.entries(modules) as any) {
      if (m.menus?.[0]?.route === route) return m.name;
    }
    return "M\u00f3dulo";
  }
</script>

<div class="flex h-screen overflow-hidden bg-background">
  <aside
    class="flex w-56 flex-col border-r bg-muted/30"
    class:hidden={!sidebarOpen}
  >
    <div class="flex h-14 items-center gap-2 border-b px-4">
      <div
        class="flex h-7 w-7 items-center justify-center bg-primary text-xs font-bold text-primary-foreground"
      >
        N
      </div>
      <span class="text-sm font-semibold">Neo Caixa</span>
    </div>
    <nav class="flex-1 overflow-auto p-2">
      {#each Object.entries(modules) as [slug, manifest]}
        {@const active = currentRoute.path === moduleRoute(manifest)}
        <button
          onclick={() => navigate(moduleRoute(manifest))}
          class="flex w-full items-center gap-2 border-l-2 px-3 py-2 text-sm transition-colors hover:bg-accent"
          class:border-primary={active}
          class:bg-accent={active}
          class:text-primary={active}
          class:font-semibold={active}
          class:border-transparent={!active}
        >
          <span>{manifest.name}</span>
          {#if slug === defaultModule}
            <span
              class="ml-auto bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
            >
              inicial
            </span>
          {/if}
        </button>
      {/each}
    </nav>
  </aside>

  <div class="flex flex-1 flex-col overflow-hidden">
    <header class="flex h-14 items-center gap-3 border-b px-4">
      <button
        onclick={() => (sidebarOpen = !sidebarOpen)}
        class="inline-flex h-8 w-8 items-center justify-center text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        aria-label="Toggle sidebar"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
        >
          <path d="M2.5 4h11M2.5 8h11M2.5 12h11" />
        </svg>
      </button>
      {#if currentRoute.path !== "/"}
        <span class="text-sm font-medium"
          >{moduleNameForRoute(currentRoute.path)}</span
        >
      {/if}
    </header>

    <main class="flex-1 overflow-auto">
      {#if !ready}
        <div class="flex h-full items-center justify-center">
          <p class="text-muted-foreground">Carregando...</p>
        </div>
      {:else if currentRoute.path === "/conciliador"}
        <Conciliador />
      {:else if currentRoute.path === "/counter"}
        <Counter />
      {:else if currentRoute.path === "/"}
        <div class="flex h-full items-center justify-center">
          <div class="flex flex-col items-center gap-4">
            <div
              class="flex h-16 w-16 items-center justify-center bg-primary text-2xl font-bold text-primary-foreground"
            >
              N
            </div>
            <h1 class="text-3xl font-semibold tracking-tight">Neo Caixa</h1>
            <p class="text-muted-foreground">
              Selecione um m\u00f3dulo no menu lateral
            </p>
          </div>
        </div>
      {:else}
        <div class="flex h-full items-center justify-center">
          <p class="text-muted-foreground">M\u00f3dulo n\u00e3o encontrado</p>
        </div>
      {/if}
    </main>
  </div>
</div>
