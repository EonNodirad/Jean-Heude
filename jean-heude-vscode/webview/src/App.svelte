<script lang="ts">
  import Chat from './Chat.svelte';
  import Input from './Input.svelte';
  import SessionBar from './SessionBar.svelte';

  // ── Types ────────────────────────────────────────────────────────────────────

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

  interface Session {
    id: number;
    resume: string;
    timestamp: string;
  }

  // ── État global ───────────────────────────────────────────────────────────────

  let items = $state<ChatItem[]>([]);
  let sessions = $state<Session[]>([]);
  let currentSessionId = $state<number | null>(null);
  let currentModel = $state('');
  let isStreaming = $state(false);
  let userId = $state('');
  let workingDir = $state('');

  // ── Messages depuis le host ───────────────────────────────────────────────────

  window.addEventListener('message', (event: MessageEvent) => {
    const msg = event.data as Record<string, unknown>;
    switch (msg.type) {

      case 'auth_state':
        userId = msg.userId as string;
        break;

      case 'working_dir':
        workingDir = msg.path as string;
        break;

      case 'message_start':
        isStreaming = true;
        items.push({ kind: 'text', id: crypto.randomUUID(), role: 'assistant', content: '', streaming: true });
        break;

      case 'token': {
        const last = items[items.length - 1];
        if (last?.kind === 'text' && last.streaming) last.content += msg.text as string;
        break;
      }

      case 'message_complete':
        isStreaming = false;
        {
          const last = items[items.length - 1];
          if (last?.kind === 'text') last.streaming = false;
        }
        if ((msg.sessionId as number | null) !== null) currentSessionId = msg.sessionId as number;
        if (msg.model) currentModel = msg.model as string;
        break;

      case 'tool_call':
        items.push({
          kind: 'tool_call',
          id: crypto.randomUUID(),
          callId: msg.callId as string,
          name: msg.name as string,
          args: (msg.args ?? {}) as Record<string, unknown>,
          output: null,
          error: null,
          pending: true,
        });
        break;

      case 'tool_result': {
        const callId = msg.callId as string;
        const card = items.find(i => i.kind === 'tool_call' && (i as ToolCallMessage).callId === callId) as ToolCallMessage | undefined;
        if (card) { card.output = (msg.output as string | null) ?? null; card.error = (msg.error as string | null) ?? null; card.pending = false; }
        break;
      }

      case 'error':
        isStreaming = false;
        {
          const last = items[items.length - 1];
          if (last?.kind === 'text') last.streaming = false;
        }
        items.push({ kind: 'system', id: crypto.randomUUID(), text: `⚠ ${msg.text as string}`, isError: true });
        break;

      case 'command_result':
        items.push({ kind: 'system', id: crypto.randomUUID(), text: msg.text as string, isError: (msg.isError as boolean) ?? false });
        break;

      case 'clear_chat':
        items = [];
        currentSessionId = null;
        isStreaming = false;
        break;

      case 'session_list':
        sessions = msg.sessions as Session[];
        break;
    }
  });

  // ── Actions ──────────────────────────────────────────────────────────────────

  function handleMessageSent(text: string): void {
    items.push({ kind: 'text', id: crypto.randomUUID(), role: 'user', content: text, streaming: false });
    isStreaming = true;
  }

  function handleCommandSent(text: string): void {
    items.push({ kind: 'system', id: crypto.randomUUID(), text: `> ${text}` });
  }

  function handleSessionChange(id: number | null): void {
    currentSessionId = id;
    items = [];
  }
</script>

<div class="app">
  <div class="header">
    <span class="brand">J.E.A.N-H.E.U.D.E</span>
    {#if userId}
      <span class="meta">{userId}</span>
    {/if}
    {#if currentModel}
      <span class="model">{currentModel.split(':')[0]}</span>
    {/if}
  </div>

  <SessionBar
    {sessions}
    {currentSessionId}
    {workingDir}
    onSessionChange={handleSessionChange}
  />

  <Chat {items} />

  <Input
    sessionId={currentSessionId}
    model={currentModel}
    disabled={isStreaming}
    onMessageSent={handleMessageSent}
    onCommandSent={handleCommandSent}
  />
</div>

<style>
  :global(*, *::before, *::after) { box-sizing: border-box; }

  :global(body) {
    margin: 0;
    padding: 0;
    background: var(--vscode-sideBar-background, #252526);
    color: var(--vscode-foreground, #cccccc);
    font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, sans-serif);
    font-size: var(--vscode-font-size, 13px);
    height: 100vh;
    overflow: hidden;
  }

  :global(#app) {
    height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .app {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--vscode-panel-border, #3c3c3c);
    background: var(--vscode-titleBar-activeBackground, #1e1e1e);
    font-size: 0.82em;
    flex-shrink: 0;
  }

  .brand {
    font-weight: 700;
    color: #e7644f;
    letter-spacing: 0.05em;
    font-size: 0.95em;
  }

  .meta { color: var(--vscode-descriptionForeground, #8a8a8a); }

  .model {
    margin-left: auto;
    color: var(--vscode-descriptionForeground, #8a8a8a);
    font-size: 0.9em;
    font-style: italic;
  }
</style>
