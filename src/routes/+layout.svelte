<script lang="ts">
  import '../app.css';
  let { children } = $props();
</script>

<svelte:head>
  <title>Canada Food Twin</title>
</svelte:head>

{@render children()}
