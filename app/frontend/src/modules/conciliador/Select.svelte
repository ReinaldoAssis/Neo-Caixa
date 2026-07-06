<script lang="ts">
  import { ChevronDown } from "lucide-svelte";
  import type { Snippet } from "svelte";

  interface Props {
    value?: string;
    disabled?: boolean;
    class?: string;
    children: Snippet;
    [key: string]: any;
  }

  let { value = $bindable(""), disabled = false, class: cls = "", children, ...rest }: Props = $props();
</script>

<div class="relative inline-flex {cls}">
  <select
    bind:value
    {disabled}
    {...rest}
    class="h-8 w-full appearance-none rounded-md border bg-background px-3 pr-8 text-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
  >
    {@render children()}
  </select>
  <ChevronDown class="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
</div>
