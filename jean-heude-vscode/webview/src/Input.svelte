<script lang="ts">
  import { postMessage } from './vscode';

  interface Props {
    sessionId: number | null;
    model: string;
    disabled?: boolean;
    onMessageSent: (text: string) => void;
    onCommandSent: (text: string) => void;
  }

  let { sessionId, model, disabled = false, onMessageSent, onCommandSent }: Props = $props();

  let text = $state('');
  let textareaEl: HTMLTextAreaElement | undefined = $state();

  function send(): void {
    const trimmed = text.trim();
    if (!trimmed) return;

    const isCommand = trimmed.startsWith('/');

    // Les commandes passent même si le streaming est actif (ex: /interrupt, /clear)
    if (!isCommand && disabled) return;

    text = '';
    if (textareaEl) textareaEl.style.height = 'auto';

    if (isCommand) {
      postMessage({ type: 'command', text: trimmed });
      onCommandSent(trimmed);
    } else {
      postMessage({ type: 'send_message', text: trimmed, sessionId, model });
      onMessageSent(trimmed);
    }
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function autoResize(e: Event): void {
    const el = e.target as HTMLTextAreaElement;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  function interrupt(): void {
    postMessage({ type: 'interrupt' });
  }
</script>

<div class="input-area">
  <textarea
    bind:this={textareaEl}
    bind:value={text}
    onkeydown={handleKeydown}
    oninput={autoResize}
    placeholder={disabled ? 'Jean-Heude réfléchit… (tape /commande pour piloter)' : 'Message… (Entrée envoie, Maj+Entrée saut de ligne, / pour commandes)'}
    rows="1"
    disabled={disabled && !text.startsWith('/')}
  ></textarea>

  <div class="controls">
    {#if disabled}
      <button class="btn-stop" onclick={interrupt} title="Interrompre">⏹</button>
    {:else}
      <button class="btn-send" onclick={send} disabled={!text.trim()} title="Envoyer (Entrée)">
        ↑
      </button>
    {/if}
  </div>
</div>

<style>
  .input-area {
    display: flex;
    align-items: flex-end;
    gap: 6px;
    padding: 8px;
    border-top: 1px solid var(--vscode-panel-border, #3c3c3c);
    background: var(--vscode-sideBar-background);
  }

  textarea {
    flex: 1;
    background: var(--vscode-input-background, #3c3c3c);
    color: var(--vscode-input-foreground, #cccccc);
    border: 1px solid var(--vscode-input-border, transparent);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.9em;
    font-family: var(--vscode-font-family, sans-serif);
    resize: none;
    min-height: 32px;
    max-height: 200px;
    line-height: 1.4;
    outline: none;
  }

  textarea:focus {
    border-color: var(--vscode-focusBorder, #007fd4);
  }

  textarea:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  textarea::placeholder {
    color: var(--vscode-input-placeholderForeground, #5a5a5a);
  }

  .controls {
    display: flex;
    align-items: flex-end;
    padding-bottom: 2px;
  }

  .btn-send, .btn-stop {
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 1em;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.15s;
  }

  .btn-send {
    background: var(--vscode-button-background, #0e639c);
    color: var(--vscode-button-foreground, #fff);
  }

  .btn-send:hover:not(:disabled) {
    background: var(--vscode-button-hoverBackground, #1177bb);
  }

  .btn-send:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-stop {
    background: var(--vscode-errorForeground, #f14c4c);
    color: #fff;
  }

  .btn-stop:hover {
    opacity: 0.85;
  }
</style>
