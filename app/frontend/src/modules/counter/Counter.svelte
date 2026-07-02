<script lang="ts">
  let count = $state(0);
  let loading = $state(false);

  async function loadState() {
    try {
      const res = await fetch("/api/counter/state");
      const data = await res.json();
      count = data.count;
    } catch {
      count = 0;
    }
  }

  async function increment() {
    loading = true;
    try {
      const res = await fetch("/api/counter/increment", { method: "POST" });
      const data = await res.json();
      count = data.count;
    } catch {
      count += 1;
    } finally {
      loading = false;
    }
  }

  async function reset() {
    loading = true;
    try {
      const res = await fetch("/api/counter/reset", { method: "POST" });
      const data = await res.json();
      count = data.count;
    } catch {
      count = 0;
    } finally {
      loading = false;
    }
  }

  loadState();
</script>

<div class="flex flex-col items-center justify-center gap-6 p-8">
  <div class="flex flex-col items-center gap-2">
    <p class="text-sm font-medium text-muted-foreground">Contador</p>
    <p class="text-6xl font-bold tabular-nums tracking-tight">{count}</p>
  </div>

  <div class="flex gap-3">
    <button
      onclick={increment}
      disabled={loading}
      class="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-6 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
    >
      + Incrementar
    </button>
    <button
      onclick={reset}
      disabled={loading}
      class="inline-flex h-10 items-center justify-center rounded-lg border bg-background px-6 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-50"
    >
      Zerar
    </button>
  </div>
</div>
