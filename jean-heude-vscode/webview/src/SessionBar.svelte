<script lang="ts">
  import { postMessage } from './vscode';

  interface Session {
    id: number;
    resume: string;
    timestamp: string;
  }

  interface Props {
    sessions: Session[];
    currentSessionId: number | null;
    workingDir: string;
    onSessionChange: (id: number | null) => void;
  }

  let { sessions, currentSessionId, workingDir, onSessionChange }: Props = $props();

  function handleSessionSelect(e: Event): void {
    const val = (e.target as HTMLSelectElement).value;
    if (val === 'new') {
      postMessage({ type: 'new_session' });
      onSessionChange(null);
    } else {
      const id = parseInt(val, 10);
      postMessage({ type: 'set_session', sessionId: id });
      onSessionChange(id);
    }
  }

  function loadSessions(): void {
    postMessage({ type: 'get_sessions' });
  }
</script>

<div class="session-bar">
  <div class="session-select-wrap">
    <select onchange={handleSessionSelect} onfocus={loadSessions}>
      <option value="new" selected={currentSessionId === null}>✦ Nouvelle session</option>
      {#each sessions as s}
        <option value={s.id} selected={s.id === currentSessionId}>
          #{s.id} — {s.resume || '(sans titre)'}
        </option>
      {/each}
    </select>
  </div>
  <div class="cwd" title={workingDir}>
    📁 {workingDir.split('/').pop() || workingDir}
  </div>
</div>

<style>
  .session-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    border-bottom: 1px solid var(--vscode-panel-border, #3c3c3c);
    background: var(--vscode-sideBar-background);
    font-size: 0.82em;
  }

  .session-select-wrap {
    flex: 1;
    min-width: 0;
  }

  select {
    width: 100%;
    background: var(--vscode-dropdown-background, #3c3c3c);
    color: var(--vscode-dropdown-foreground, #cccccc);
    border: 1px solid var(--vscode-dropdown-border, #3c3c3c);
    border-radius: 3px;
    padding: 2px 4px;
    font-size: inherit;
    font-family: inherit;
    cursor: pointer;
  }

  select:focus {
    outline: 1px solid var(--vscode-focusBorder, #007fd4);
  }

  .cwd {
    color: var(--vscode-descriptionForeground, #8a8a8a);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100px;
    cursor: default;
  }
</style>
