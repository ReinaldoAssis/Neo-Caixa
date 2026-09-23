<script lang="ts">
  import { BadgePercent, Construction, FileSpreadsheet, Wrench } from "lucide-svelte";
  import GerenciadorDescontos from "./GerenciadorDescontos.svelte";

  type Ferramenta = "descontos" | null;

  let ativa = $state<Ferramenta>(null);

  const ferramentas = [
    {
      id: "descontos",
      label: "Gerenciador de Descontos",
      descricao: "Acompanhe os descontos de venda a prazo puxados do Cloudfy.",
      icon: BadgePercent,
      enabled: true,
    },
    {
      id: "placeholder-1",
      label: "Em breve",
      descricao: "Nova ferramenta de restaurante.",
      icon: FileSpreadsheet,
      enabled: false,
    },
    {
      id: "placeholder-2",
      label: "Em breve",
      descricao: "Nova ferramenta de restaurante.",
      icon: Construction,
      enabled: false,
    },
    {
      id: "placeholder-3",
      label: "Em breve",
      descricao: "Nova ferramenta de restaurante.",
      icon: Wrench,
      enabled: false,
    },
  ];
</script>

{#if ativa === "descontos"}
  <GerenciadorDescontos onVoltar={() => (ativa = null)} />
{:else}
  <div class="flex h-full flex-col overflow-auto">
    <div class="border-b px-4 py-3">
      <h1 class="text-lg font-bold">Restaurante - Ferramentas</h1>
      <p class="text-sm text-muted-foreground">
        Selecione uma ferramenta para abrir.
      </p>
    </div>

    <div class="grid flex-1 grid-cols-2 gap-4 p-4">
      {#each ferramentas as f}
        <button
          type="button"
          disabled={!f.enabled}
          onclick={() => { if (f.id === "descontos") ativa = "descontos"; }}
          class="flex flex-col items-start gap-3 rounded-lg border p-6 text-left transition-colors"
          class:hover:bg-accent={f.enabled}
          class:cursor-pointer={f.enabled}
          class:opacity-50={!f.enabled}
        >
          <span class="flex h-14 w-14 items-center justify-center rounded-md bg-primary/10 text-primary">
            <f.icon class="h-8 w-8" />
          </span>
          <span class="text-base font-semibold">{f.label}</span>
          <span class="text-sm text-muted-foreground">{f.descricao}</span>
        </button>
      {/each}
    </div>
  </div>
{/if}
