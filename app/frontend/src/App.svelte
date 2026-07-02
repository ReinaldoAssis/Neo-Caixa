<script lang="ts">
  import { onMount } from "svelte";

  let status = $state("Conectando...");
  let version = $state("");

  onMount(async () => {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      status = data.status === "ok" ? "Online" : "Erro";
      version = data.version;
    } catch {
      status = "Offline";
    }
  });
</script>

<div class="flex h-screen flex-col items-center justify-center gap-6 p-8">
  <div class="flex flex-col items-center gap-4">
    <div class="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-2xl font-bold text-primary-foreground">
      H
    </div>
    <h1 class="text-3xl font-semibold tracking-tight">Helena</h1>
    <p class="text-muted-foreground">Plataforma modular desktop</p>
  </div>

  <div class="flex items-center gap-2 rounded-lg border bg-muted px-4 py-2 text-sm">
    <span class="inline-block h-2 w-2 rounded-full {status === 'Online' ? 'bg-green-500' : 'bg-red-500'}"></span>
    <span>{status}</span>
    {#if version}
      <span class="text-muted-foreground">v{version}</span>
    {/if}
  </div>
</div>
