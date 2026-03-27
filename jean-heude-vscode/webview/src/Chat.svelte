<script lang="ts">
  import ToolCard from './ToolCard.svelte';
  import { marked } from 'marked';

  interface TextMessage {
    kind: 'text';
    id: string;
    role: 'user' | 'assistant';
    content: string;
    streaming: boolean;
  }

  interface ToolCallMessage {
    kind: 'tool_call';
    id: string;
    callId: string;
    name: string;
    args: Record<string, unknown>;
    output: string | null;
    error: string | null;
    pending: boolean;
  }

  interface SystemMessage {
    kind: 'system';
    id: string;
    text: string;
    isError?: boolean;
  }

  type ChatItem = TextMessage | ToolCallMessage | SystemMessage;

  interface Props {
    items: ChatItem[];
  }

  let { items }: Props = $props();

  let listEl: HTMLDivElement | undefined = $state();

  function renderMarkdown(text: string): string {
    return marked(text, { async: false }) as string;
  }

  $effect(() => {
    void items.length; // dépendance réactive pour scroller à chaque ajout
    if (listEl) {
      requestAnimationFrame(() => {
        listEl?.scrollTo({ top: listEl.scrollHeight, behavior: 'smooth' });
      });
    }
  });
</script>

<div class="chat-list" bind:this={listEl}>
  {#each items as item (item.id)}
    {#if item.kind === 'text'}
      <div class="message" class:user={item.role === 'user'} class:assistant={item.role === 'assistant'}>
        {#if item.role === 'user'}
          <div class="bubble user-bubble">{item.content}</div>
        {:else}
          <div class="bubble assistant-bubble">
            <!-- eslint-disable-next-line svelte/no-at-html-tags -->
            {@html renderMarkdown(item.content)}
            {#if item.streaming}
              <span class="cursor">▌</span>
            {/if}
          </div>
        {/if}
      </div>

    {:else if item.kind === 'system'}
      <div class="system-message" class:error={item.isError}>
        <pre>{item.text}</pre>
      </div>

    {:else}
      <div class="tool-wrapper">
        <ToolCard
          name={item.name}
          args={item.args}
          output={item.output}
          error={item.error}
          pending={item.pending}
        />
      </div>
    {/if}
  {/each}

  {#if items.length === 0}
    <div class="empty">
      <div class="avatar">🤖</div>
      <p>Bonjour ! Je suis Jean-Heude, votre assistant IA local.</p>
      <p class="hint">Posez-moi une question ou tapez <code>/help</code> pour les commandes.</p>
    </div>
  {/if}
</div>

<style>
  .chat-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .message { display: flex; }
  .message.user { justify-content: flex-end; }
  .message.assistant { justify-content: flex-start; }

  .bubble {
    max-width: 90%;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.9em;
    line-height: 1.5;
    word-break: break-word;
  }

  .user-bubble {
    background: var(--vscode-button-background, #0e639c);
    color: var(--vscode-button-foreground, #ffffff);
    border-bottom-right-radius: 2px;
    white-space: pre-wrap;
  }

  .assistant-bubble {
    background: var(--vscode-editor-background, #1e1e1e);
    color: var(--vscode-editor-foreground, #cccccc);
    border: 1px solid var(--vscode-panel-border, #3c3c3c);
    border-bottom-left-radius: 2px;
  }

  .assistant-bubble :global(p) { margin: 0 0 8px; }
  .assistant-bubble :global(p:last-child) { margin-bottom: 0; }
  .assistant-bubble :global(code) {
    background: var(--vscode-textCodeBlock-background, #0a0a0a);
    padding: 1px 4px;
    border-radius: 3px;
    font-family: var(--vscode-editor-font-family, monospace);
    font-size: 0.9em;
  }
  .assistant-bubble :global(pre) {
    background: var(--vscode-textCodeBlock-background, #0a0a0a);
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
    margin: 6px 0;
  }
  .assistant-bubble :global(pre code) { background: none; padding: 0; }
  .assistant-bubble :global(ul), .assistant-bubble :global(ol) { margin: 4px 0; padding-left: 20px; }
  .assistant-bubble :global(h1), .assistant-bubble :global(h2), .assistant-bubble :global(h3) {
    margin: 8px 0 4px;
    font-size: 1em;
    font-weight: 600;
  }

  .cursor {
    display: inline-block;
    animation: blink 1s step-end infinite;
    color: var(--vscode-editorCursor-foreground, #aeafad);
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  /* ── Messages système (résultats de commandes) ── */
  .system-message {
    padding: 4px 10px;
    border-left: 2px solid var(--vscode-editorInfo-foreground, #3794ff);
    background: var(--vscode-editor-background, #1e1e1e);
    border-radius: 0 4px 4px 0;
    font-size: 0.82em;
    color: var(--vscode-descriptionForeground, #8a8a8a);
    margin: 2px 0;
  }

  .system-message.error {
    border-left-color: var(--vscode-editorError-foreground, #f14c4c);
    color: var(--vscode-editorError-foreground, #f14c4c);
  }

  .system-message pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: var(--vscode-editor-font-family, monospace);
    font-size: inherit;
  }

  .tool-wrapper { padding: 2px 0; }

  .empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 24px;
    color: var(--vscode-descriptionForeground, #8a8a8a);
  }

  .avatar { font-size: 2.5em; margin-bottom: 12px; }
  .empty p { margin: 4px 0; font-size: 0.9em; }
  .hint { font-size: 0.8em !important; opacity: 0.7; }
  .empty code {
    background: var(--vscode-textCodeBlock-background, #0a0a0a);
    padding: 1px 4px;
    border-radius: 3px;
  }
</style>
