/**
 * JHChatViewProvider — WebviewView (sidebar) Jean-Heude.
 * Gère la connexion WebSocket, le bridge host↔webview, le diff natif VS Code,
 * les commandes slash (y compris /login, /logout, /server) et le mode permissions.
 */
import * as vscode from 'vscode';
import { readFileSync, existsSync } from 'fs';
import { writeFile } from 'fs/promises';
import { join } from 'path';
import { JHClient, ToolCallEvent } from './jhclient.js';
import { Credentials, saveCredentials, saveServerUrl, login, logout, isTokenExpired } from './auth.js';
import * as tools from './tools.js';

// ── Provider de contenu in-memory pour les diffs ──────────────────────────────

export class DiffContentProvider implements vscode.TextDocumentContentProvider {
  static readonly scheme = 'jh-diff';
  private _content = new Map<string, string>();
  private _emitter = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this._emitter.event;

  set(uri: vscode.Uri, content: string): void {
    this._content.set(uri.toString(), content);
    this._emitter.fire(uri);
  }

  delete(uri: vscode.Uri): void {
    this._content.delete(uri.toString());
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    return this._content.get(uri.toString()) ?? '';
  }
}

// ── Messages host → webview ───────────────────────────────────────────────────

type ToWebview =
  | { type: 'auth_state'; connected: boolean; userId: string; server: string }
  | { type: 'message_start' }
  | { type: 'token'; text: string }
  | { type: 'message_complete'; sessionId: number | null; model: string }
  | { type: 'system'; text: string }
  | { type: 'tool_call'; callId: string; name: string; args: Record<string, unknown> }
  | { type: 'tool_result'; callId: string; output: string | null; error: string | null }
  | { type: 'error'; text: string }
  | { type: 'session_list'; sessions: Array<{ id: number; resume: string; timestamp: string }> }
  | { type: 'working_dir'; path: string }
  | { type: 'command_result'; text: string; isError?: boolean }
  | { type: 'clear_chat' };

// ── Texte d'aide ──────────────────────────────────────────────────────────────

const HELP_TEXT = `Commandes disponibles :
/help                  — cette aide
/clear                 — nouvelle session (vide le chat)
/login                 — se connecter (met à jour le token CLI aussi)
/logout                — se déconnecter
/server                — afficher le serveur actuel
/server <url>          — changer de serveur (ex: /server 192.168.1.81:8000)
/model                 — repasse en mode auto (backend choisit)
/model list            — liste les modèles disponibles
/model <nom>           — force un modèle (ex: /model qwen2.5:14b)
/permissions           — affiche le mode actuel
/permissions ask       — diff + confirmation pour écriture/bash
/permissions auto      — exécute sans confirmation
/permissions plan      — outils lecture seulement, décrit sans écrire
/cwd                   — affiche le répertoire de travail
/cwd <chemin>          — change le répertoire de travail
/sessions              — liste les sessions récentes
/history [N]           — N derniers messages de la session (défaut: 10)
/export                — exporte la session en .md dans le répertoire courant`;

// ── Provider principal ────────────────────────────────────────────────────────

export class JHChatViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private _client?: JHClient;
  private _creds: Credentials | null;
  private _serverUrl: string;
  private _currentSessionId: number | null = null;
  private _currentModel = '';
  private _permissionsMode: 'ask' | 'auto' | 'plan' = 'ask';

  constructor(
    private readonly _extensionUri: vscode.Uri,
    initialCreds: Credentials | null,
    initialServerUrl: string,
    private readonly _diffProvider: DiffContentProvider,
  ) {
    this._creds = initialCreds;
    this._serverUrl = initialServerUrl;
  }

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this._extensionUri, 'dist', 'webview')],
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    // Working dir initial = dossier workspace
    const wsFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (wsFolder) tools.setWorkingDir(wsFolder);

    if (this._creds) this._initClient();

    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (folder) {
        tools.setWorkingDir(folder);
        this._post({ type: 'working_dir', path: folder });
      }
    });

    // Messages webview → host
    webviewView.webview.onDidReceiveMessage(async (msg: Record<string, unknown>) => {
      switch (msg.type) {
        case 'send_message':
          await this._handleSendMessage(
            msg.text as string,
            (msg.sessionId as number | null) ?? this._currentSessionId,
            (msg.model as string) || this._currentModel,
          );
          break;
        case 'command':
          await this._handleCommand(msg.text as string);
          break;
        case 'get_sessions':
          await this._handleGetSessions();
          break;
        case 'set_session':
          this._currentSessionId = msg.sessionId as number;
          break;
        case 'new_session':
          this._currentSessionId = null;
          break;
        case 'set_working_dir': {
          const p = msg.path as string;
          tools.setWorkingDir(p);
          this._post({ type: 'working_dir', path: tools.getWorkingDir() });
          break;
        }
        case 'interrupt':
          this._client?.sendInterrupt();
          break;
      }
    });

    // État initial
    this._postAuthState();
    this._post({ type: 'working_dir', path: tools.getWorkingDir() });
  }

  // ── Client WS ────────────────────────────────────────────────────────────────

  private _initClient(): void {
    this._client?.close();
    if (!this._creds) return;

    this._client = new JHClient(this._serverUrl, this._creds);

    this._client.on('token', (ev: { content: string }) => {
      const text = ev.content.replace(/\|\|AUDIO_ID:.*?\|\|/g, '');
      if (text && !text.startsWith('¶')) this._post({ type: 'token', text });
    });

    this._client.on('system', (ev: { content: string }) => {
      this._post({ type: 'system', text: ev.content });
    });

    this._client.on('done', (ev: { session_id: number | null; model: string }) => {
      if (ev.session_id !== null) this._currentSessionId = ev.session_id;
      if (ev.model) this._currentModel = ev.model;
      this._post({ type: 'message_complete', sessionId: ev.session_id, model: ev.model });
    });

    this._client.on('error', (ev: { content: string }) => {
      this._post({ type: 'error', text: ev.content });
    });

    this._client.on('disconnect', () => {
      this._post({ type: 'error', text: 'Connexion perdue avec le backend Jean-Heude.' });
    });

    this._client.on('tool_call', async (ev: ToolCallEvent) => {
      await this._handleToolCall(ev);
    });
  }

  // ── Envoi de message ──────────────────────────────────────────────────────────

  private async _handleSendMessage(text: string, sessionId: number | null, model: string): Promise<void> {
    if (!this._client || !this._creds) {
      this._post({ type: 'command_result', text: 'Non connecté. Utilise /login pour te connecter.', isError: true });
      return;
    }
    const projectCtx = this._readProjectContext();
    this._post({ type: 'message_start' });
    try {
      await this._client.sendMessage(text, sessionId, model, tools.getWorkingDir(), projectCtx ?? undefined);
    } catch (e) {
      this._post({ type: 'error', text: String(e) });
    }
  }

  private _readProjectContext(): string | null {
    const dir = tools.getWorkingDir();
    const parts: string[] = [];
    for (const name of ['CLAUDE.md', 'README.md']) {
      const full = join(dir, name);
      if (existsSync(full)) {
        try { parts.push(`=== ${name} ===\n${readFileSync(full, 'utf-8').slice(0, 6000)}`); } catch { /* */ }
      }
    }
    return parts.length > 0 ? parts.join('\n\n') : null;
  }

  // ── Commandes slash ───────────────────────────────────────────────────────────

  private async _handleCommand(raw: string): Promise<void> {
    const parts = raw.trim().split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const arg = parts.slice(1).join(' ');

    switch (cmd) {
      case '/help':
        this._post({ type: 'command_result', text: HELP_TEXT });
        break;
      case '/clear':
        this._currentSessionId = null;
        this._post({ type: 'clear_chat' });
        this._post({ type: 'command_result', text: 'Nouvelle session démarrée.' });
        break;
      case '/login':
        await this._handleLogin();
        break;
      case '/logout':
        await this._handleLogout();
        break;
      case '/server':
        await this._handleServer(arg);
        break;
      case '/model':
        await this._handleModelCommand(arg);
        break;
      case '/permissions':
        this._handlePermissionsCommand(arg);
        break;
      case '/cwd':
        this._handleCwdCommand(arg);
        break;
      case '/sessions':
        await this._handleSessionsCommand();
        break;
      case '/history':
        await this._handleHistoryCommand(arg);
        break;
      case '/export':
        await this._handleExportCommand();
        break;
      default:
        this._post({ type: 'command_result', text: `Commande inconnue : "${cmd}". Tape /help.`, isError: true });
    }
  }

  // ── /login ────────────────────────────────────────────────────────────────────

  private async _handleLogin(): Promise<void> {
    const serverUrl = this._serverUrl;

    const userId = await vscode.window.showInputBox({
      title: `Connexion à ${serverUrl}`,
      prompt: 'Identifiant',
      placeHolder: 'noeda',
      ignoreFocusOut: true,
    });
    if (!userId) return;

    const password = await vscode.window.showInputBox({
      title: `Connexion à ${serverUrl}`,
      prompt: 'Mot de passe',
      password: true,
      ignoreFocusOut: true,
    });
    if (password === undefined) return;

    try {
      const newCreds = await login(serverUrl, userId, password);
      this._creds = newCreds;
      this._currentSessionId = null;
      this._initClient();
      this._post({ type: 'clear_chat' });
      this._postAuthState();
      this._post({
        type: 'command_result',
        text: `Connecté en tant que ${newCreds.user_id}${newCreds.is_admin ? ' (admin)' : ''}\nToken sauvegardé dans ~/.config/jh/token.json (partagé avec le CLI).`,
      });
    } catch (e) {
      this._post({ type: 'command_result', text: `Erreur de connexion : ${e}`, isError: true });
    }
  }

  // ── /logout ───────────────────────────────────────────────────────────────────

  private async _handleLogout(): Promise<void> {
    if (!this._creds) {
      this._post({ type: 'command_result', text: 'Déjà déconnecté.', isError: true });
      return;
    }
    try {
      await logout(this._serverUrl, this._creds.token);
      this._client?.close();
      this._client = undefined;
      this._creds = null;
      this._currentSessionId = null;
      this._post({ type: 'clear_chat' });
      this._postAuthState();
      this._post({ type: 'command_result', text: 'Déconnecté. Utilise /login pour te reconnecter.' });
    } catch (e) {
      this._post({ type: 'command_result', text: `Erreur logout : ${e}`, isError: true });
    }
  }

  // ── /server ───────────────────────────────────────────────────────────────────

  private async _handleServer(arg: string): Promise<void> {
    if (!arg) {
      this._post({ type: 'command_result', text: `Serveur actuel : ${this._serverUrl}` });
      return;
    }
    // Normaliser l'URL (ajouter http:// si manquant)
    const normalized = arg.startsWith('http') ? arg.replace(/\/$/, '') : `http://${arg.replace(/\/$/, '')}`;
    this._serverUrl = normalized;

    // Sauvegarder dans config.toml (partagé avec le CLI)
    saveServerUrl(normalized);

    // Mettre à jour le server_url dans les credentials si connecté
    if (this._creds) {
      this._creds = { ...this._creds, server_url: normalized };
      saveCredentials(this._creds);
      // Reconnecter avec le nouveau serveur
      this._initClient();
    }

    this._postAuthState();
    this._post({
      type: 'command_result',
      text: `Serveur changé : ${normalized}\nSauvegardé dans ~/.config/jh/config.toml (partagé avec le CLI).`,
    });
  }

  // ── Autres commandes ──────────────────────────────────────────────────────────

  private async _handleModelCommand(arg: string): Promise<void> {
    if (!arg) {
      this._currentModel = '';
      this._post({ type: 'command_result', text: 'Modèle : auto (backend choisit)' });
      this._post({ type: 'message_complete', sessionId: this._currentSessionId, model: '' });
      return;
    }
    if (arg === 'list') {
      if (!this._client) { this._post({ type: 'command_result', text: 'Non connecté.', isError: true }); return; }
      try {
        const models = await this._client.getModels();
        const marker = this._currentModel ? `(actuel: ${this._currentModel})` : '(mode auto)';
        this._post({ type: 'command_result', text: `Modèles ${marker}:\n  ${models.join('\n  ')}` });
      } catch (e) {
        this._post({ type: 'command_result', text: `Erreur : ${e}`, isError: true });
      }
      return;
    }
    this._currentModel = arg;
    this._post({ type: 'command_result', text: `Modèle forcé : ${arg}` });
    this._post({ type: 'message_complete', sessionId: this._currentSessionId, model: arg });
  }

  private _handlePermissionsCommand(arg: string): void {
    const valid = ['ask', 'auto', 'plan'] as const;
    if (!arg) {
      this._post({ type: 'command_result', text: `Mode permissions : ${this._permissionsMode}\n  ask  — diff + confirmation\n  auto — exécute directement\n  plan — lit seulement, décrit sans écrire` });
      return;
    }
    if (!valid.includes(arg as typeof valid[number])) {
      this._post({ type: 'command_result', text: `Mode invalide. Valeurs : ask, auto, plan`, isError: true });
      return;
    }
    this._permissionsMode = arg as 'ask' | 'auto' | 'plan';
    this._post({ type: 'command_result', text: `Mode permissions : ${arg}` });
  }

  private _handleCwdCommand(arg: string): void {
    if (!arg) {
      this._post({ type: 'command_result', text: `Répertoire actuel : ${tools.getWorkingDir()}` });
      return;
    }
    try {
      tools.setWorkingDir(arg);
      const actual = tools.getWorkingDir();
      this._post({ type: 'working_dir', path: actual });
      this._post({ type: 'command_result', text: `Répertoire changé : ${actual}` });
    } catch (e) {
      this._post({ type: 'command_result', text: `Erreur : ${e}`, isError: true });
    }
  }

  private async _handleSessionsCommand(): Promise<void> {
    if (!this._client) { this._post({ type: 'command_result', text: 'Non connecté.', isError: true }); return; }
    try {
      const raw = await this._client.getSessions();
      const lines = raw.slice(0, 20).map(s =>
        `  #${s['id']} — ${String(s['resume'] ?? '(sans titre)').slice(0, 60)}  ${String(s['timestamp'] ?? '').slice(0, 16).replace('T', ' ')}`
      );
      this._post({ type: 'command_result', text: `Sessions récentes :\n${lines.join('\n')}` });
      await this._handleGetSessions();
    } catch (e) {
      this._post({ type: 'command_result', text: `Erreur : ${e}`, isError: true });
    }
  }

  private async _handleHistoryCommand(arg: string): Promise<void> {
    if (!this._client) { this._post({ type: 'command_result', text: 'Non connecté.', isError: true }); return; }
    if (this._currentSessionId === null) {
      this._post({ type: 'command_result', text: 'Aucune session active.', isError: true });
      return;
    }
    const n = arg ? Math.max(1, parseInt(arg, 10) || 10) : 10;
    try {
      const msgs = await this._client.getSessionHistory(this._currentSessionId);
      const recent = msgs.slice(-n);
      const lines = recent.map(m => `${m['role'] === 'user' ? '→ Vous' : '← JH'}: ${String(m['content'] ?? '').slice(0, 120)}`);
      this._post({ type: 'command_result', text: `Derniers ${recent.length} messages :\n${lines.join('\n')}` });
    } catch (e) {
      this._post({ type: 'command_result', text: `Erreur : ${e}`, isError: true });
    }
  }

  private async _handleExportCommand(): Promise<void> {
    if (!this._client || this._currentSessionId === null) {
      this._post({ type: 'command_result', text: 'Aucune session active.', isError: true });
      return;
    }
    try {
      const msgs = await this._client.getSessionHistory(this._currentSessionId);
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const filename = `jh-session-${this._currentSessionId}-${ts}.md`;
      const fullPath = join(tools.getWorkingDir(), filename);
      const lines = [`# Session Jean-Heude #${this._currentSessionId}\n\n`];
      for (const m of msgs) {
        lines.push(`**${m['role'] === 'user' ? 'Vous' : 'Jean-Heude'}**\n\n${String(m['content'] ?? '')}\n\n---\n\n`);
      }
      await writeFile(fullPath, lines.join(''), 'utf-8');
      this._post({ type: 'command_result', text: `Session exportée : ${fullPath}` });
    } catch (e) {
      this._post({ type: 'command_result', text: `Erreur export : ${e}`, isError: true });
    }
  }

  // ── Tool calls ────────────────────────────────────────────────────────────────

  private async _handleToolCall(ev: ToolCallEvent): Promise<void> {
    this._post({ type: 'tool_call', callId: ev.call_id, name: ev.name, args: ev.args });

    let result: tools.ToolResult;
    try {
      if (ev.name === 'client_write_file') {
        result = await this._dispatchWrite(ev.args.path as string, ev.args.content as string);
      } else if (ev.name === 'client_edit_file') {
        result = await this._dispatchEdit(ev.args.path as string, ev.args.old_str as string, ev.args.new_str as string);
      } else if (ev.name === 'client_run_bash') {
        result = await this._dispatchBash(ev.args.command as string, ev.args.timeout_ms as number | undefined);
      } else {
        result = await tools.executeReadOnly(ev.name, ev.args);
      }
    } catch (e) {
      result = { output: null, error: String(e) };
    }

    this._post({ type: 'tool_result', callId: ev.call_id, output: result.output, error: result.error });
    await this._client?.sendToolResult(ev.call_id, result.output, result.error);
  }

  private async _dispatchWrite(path: string, content: string): Promise<tools.ToolResult> {
    if (this._permissionsMode === 'plan') return { output: `[PLAN] Aurait écrit : ${path} (${content.split('\n').length} lignes)`, error: null };
    let preview: tools.WritePreview;
    try { preview = tools.previewWriteFile(path, content); } catch (e) { return { output: null, error: String(e) }; }
    if (this._permissionsMode === 'auto') return tools.applyWrite(preview.absPath, preview.newContent);
    const approved = await this._showDiff(preview);
    if (!approved) return { output: null, error: 'Refusé par l\'utilisateur' };
    return tools.applyWrite(preview.absPath, preview.newContent);
  }

  private async _dispatchEdit(path: string, oldStr: string, newStr: string): Promise<tools.ToolResult> {
    if (this._permissionsMode === 'plan') return { output: `[PLAN] Aurait édité : ${path}`, error: null };
    let preview: tools.WritePreview | { error: string };
    try { preview = tools.previewEditFile(path, oldStr, newStr); } catch (e) { return { output: null, error: String(e) }; }
    if ('error' in preview) return { output: null, error: preview.error };
    if (this._permissionsMode === 'auto') return tools.applyWrite(preview.absPath, preview.newContent);
    const approved = await this._showDiff(preview);
    if (!approved) return { output: null, error: 'Refusé par l\'utilisateur' };
    return tools.applyWrite(preview.absPath, preview.newContent);
  }

  private async _dispatchBash(command: string, timeoutMs?: number): Promise<tools.ToolResult> {
    if (this._permissionsMode === 'plan') return { output: `[PLAN] Aurait exécuté : ${command}`, error: null };
    if (this._permissionsMode === 'auto') return tools.executeBash(command, timeoutMs);
    const choice = await vscode.window.showWarningMessage(`Jean-Heude veut exécuter :\n\`${command}\``, { modal: true }, 'Exécuter', 'Refuser');
    if (choice !== 'Exécuter') return { output: null, error: 'Refusé par l\'utilisateur' };
    return tools.executeBash(command, timeoutMs);
  }

  // ── Diff natif VS Code ────────────────────────────────────────────────────────

  private async _showDiff(preview: tools.WritePreview): Promise<boolean> {
    const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const beforeUri = vscode.Uri.from({ scheme: DiffContentProvider.scheme, path: `/before/${preview.fileName}`, query: `${key}-before` });
    const afterUri  = vscode.Uri.from({ scheme: DiffContentProvider.scheme, path: `/after/${preview.fileName}`,  query: `${key}-after` });

    this._diffProvider.set(beforeUri, preview.originalContent);
    this._diffProvider.set(afterUri, preview.newContent);

    await vscode.commands.executeCommand('vscode.diff', beforeUri, afterUri,
      preview.isNewFile ? `JH: Nouveau — ${preview.fileName}` : `JH: ${preview.fileName}`);

    const action = preview.isNewFile ? 'Créer' : 'Appliquer';
    const choice = await vscode.window.showInformationMessage(
      preview.isNewFile ? `Créer le fichier ${preview.fileName} ?` : `Appliquer les modifications à ${preview.fileName} ?`,
      action, 'Refuser',
    );

    this._diffProvider.delete(beforeUri);
    this._diffProvider.delete(afterUri);

    if (choice !== action) return false;

    const edit = new vscode.WorkspaceEdit();
    edit.createFile(vscode.Uri.file(preview.absPath), { overwrite: true, contents: Buffer.from(preview.newContent, 'utf-8') });
    await vscode.workspace.applyEdit(edit);
    return true;
  }

  // ── Sessions ──────────────────────────────────────────────────────────────────

  private async _handleGetSessions(): Promise<void> {
    if (!this._client) return;
    try {
      const raw = await this._client.getSessions();
      const sessions = raw.slice(0, 30).map(s => ({
        id: s['id'] as number,
        resume: String(s['resume'] ?? '').slice(0, 80),
        timestamp: String(s['timestamp'] ?? '').slice(0, 16).replace('T', ' '),
      }));
      this._post({ type: 'session_list', sessions });
    } catch (e) {
      this._post({ type: 'error', text: `Impossible de charger les sessions : ${e}` });
    }
  }

  // ── Utilitaires ───────────────────────────────────────────────────────────────

  private _postAuthState(): void {
    this._post({
      type: 'auth_state',
      connected: !!this._creds && !isTokenExpired(this._creds.token),
      userId: this._creds?.user_id ?? '',
      server: this._serverUrl,
    });
  }

  // ── HTML webview ──────────────────────────────────────────────────────────────

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const distUri = vscode.Uri.joinPath(this._extensionUri, 'dist', 'webview');
    let html = readFileSync(vscode.Uri.joinPath(distUri, 'index.html').fsPath, 'utf-8');

    html = html.replace(/(src|href)="(\/[^"]*?)"/g, (_match, attr, assetPath) => {
      const clean = assetPath.startsWith('/') ? assetPath.slice(1) : assetPath;
      return `${attr}="${webview.asWebviewUri(vscode.Uri.joinPath(distUri, clean))}"`;
    });

    const csp = [
      `default-src 'none'`,
      `script-src ${webview.cspSource} 'unsafe-eval'`,
      `style-src ${webview.cspSource} 'unsafe-inline'`,
      `img-src ${webview.cspSource} data:`,
      `font-src ${webview.cspSource}`,
    ].join('; ');

    html = html.replace('<head>', `<head>\n  <meta http-equiv="Content-Security-Policy" content="${csp}">`);
    return html;
  }

  private _post(msg: ToWebview): void {
    this._view?.webview.postMessage(msg);
  }

  dispose(): void {
    this._client?.close();
  }
}
