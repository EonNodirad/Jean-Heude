<script lang="ts">
  interface Props {
    name: string;
    args: Record<string, unknown>;
    output?: string | null;
    error?: string | null;
    pending?: boolean;
  }

  let { name, args, output = null, error = null, pending = false }: Props = $props();

  const displayName = $derived(name.replace(/^client_/, ''));

  function formatArgs(a: Record<string, unknown>): string {
    return Object.entries(a)
      .map(([k, v]) => {
        const s = typeof v === 'string'
          ? `"${v.length > 40 ? v.slice(0, 40) + '…' : v}"`
          : JSON.stringify(v);
        return `${k}=${s}`;
      })
      .join(', ');
  }

  const argsStr = $derived(formatArgs(args));
  const previewLines = $derived((output ?? '').split('\n').slice(0, 3).join('\n'));
  const totalLines = $derived((output ?? '').split('\n').length);
</script>

<div class="tool-card" class:pending class:error={!!error}>
  <div class="tool-header">
    <span class="tool-icon">{pending ? '⏳' : error ? '✗' : '⚙'}</span>
    <span class="tool-name">{displayName}</span>
    <span class="tool-args">({argsStr})</span>
  </div>

  {#if output && !pending}
    <div class="tool-output">
      <pre>{previewLines}{totalLines > 3 ? `\n… (${totalLines} lignes)` : ''}</pre>
    </div>
  {/if}

  {#if error}
    <div class="tool-error">✗ {error}</div>
  {/if}
</div>

<style>
  .tool-card {
    margin: 4px 0;
    padding: 6px 10px;
    border-left: 2px solid var(--vscode-editorInfo-foreground, #3794ff);
    background: var(--vscode-editor-background, #1e1e1e);
    border-radius: 0 4px 4px 0;
    font-size: 0.85em;
  }

  .tool-card.pending {
    border-left-color: var(--vscode-editorWarning-foreground, #cca700);
    opacity: 0.8;
  }

  .tool-card.error {
    border-left-color: var(--vscode-editorError-foreground, #f14c4c);
  }

  .tool-header {
    display: flex;
    align-items: baseline;
    gap: 4px;
    font-family: var(--vscode-editor-font-family, monospace);
  }

  .tool-icon {
    font-size: 0.9em;
  }

  .tool-name {
    color: var(--vscode-symbolIcon-functionForeground, #dcdcaa);
    font-weight: 600;
  }

  .tool-args {
    color: var(--vscode-descriptionForeground, #8a8a8a);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .tool-output {
    margin-top: 4px;
  }

  .tool-output pre {
    margin: 0;
    font-size: 0.9em;
    color: var(--vscode-descriptionForeground, #8a8a8a);
    white-space: pre-wrap;
    word-break: break-all;
  }

  .tool-error {
    margin-top: 4px;
    color: var(--vscode-editorError-foreground, #f14c4c);
    font-size: 0.9em;
  }
</style>
