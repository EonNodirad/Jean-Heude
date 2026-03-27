/**
 * Client WebSocket bidirectionnel vers le backend Jean-Heude.
 * Adapté depuis jh-ts/src/client.ts pour l'extension VS Code.
 */
import { EventEmitter } from 'events';
import WebSocket from 'ws';
import { Credentials, wsUrl } from './auth.js';

export interface TokenEvent { content: string }
export interface DoneEvent { session_id: number | null; model: string }
export interface ErrorEvent { content: string }
export interface SystemEvent { content: string }
export interface ToolCallEvent { call_id: string; name: string; args: Record<string, unknown> }

export class JHClient extends EventEmitter {
  readonly serverUrl: string;
  readonly creds: Credentials;
  private ws: WebSocket | null = null;
  private _requestInFlight = false;
  lastSessionId: number | null = null;
  lastModel: string = '';

  constructor(serverUrl: string, creds: Credentials) {
    super();
    this.serverUrl = serverUrl;
    this.creds = creds;
  }

  private connect(): Promise<WebSocket> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve(this.ws);
    }

    return new Promise((resolve, reject) => {
      const url = `${wsUrl(this.serverUrl)}/ws/${this.creds.user_id}?token=${this.creds.token}`;
      const ws = new WebSocket(url, { handshakeTimeout: 10_000 });

      ws.once('open', () => {
        this.ws = ws;
        resolve(ws);
      });

      ws.once('error', (err) => reject(err));

      ws.on('message', (raw: Buffer | string) => {
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(raw.toString()) as Record<string, unknown>;
        } catch {
          return;
        }

        const type = msg.type as string;

        if (type === 'token') {
          this.emit('token', { content: (msg.content ?? '') as string });
        } else if (type === 'done') {
          this._requestInFlight = false;
          this.lastSessionId = (msg.session_id as number) ?? null;
          this.lastModel = (msg.model as string) ?? '';
          this.emit('done', { session_id: this.lastSessionId, model: this.lastModel });
        } else if (type === 'error') {
          this._requestInFlight = false;
          this.emit('error', { content: (msg.content ?? 'Erreur inconnue') as string });
        } else if (type === 'system') {
          this.emit('system', { content: (msg.content ?? '') as string });
        } else if (type === 'tool_call') {
          this.emit('tool_call', {
            call_id: msg.call_id as string,
            name: msg.name as string,
            args: (msg.args ?? {}) as Record<string, unknown>,
          });
        }
      });

      ws.on('close', () => {
        if (this._requestInFlight) {
          this._requestInFlight = false;
          this.emit('disconnect');
        }
        this.ws = null;
      });
    });
  }

  async sendMessage(
    content: string,
    sessionId: number | null,
    model: string = '',
    workingDir?: string,
    projectContext?: string,
  ): Promise<void> {
    this._requestInFlight = true;
    const ws = await this.connect();
    const payload: Record<string, unknown> = {
      type: 'message',
      user_id: this.creds.user_id,
      session_id: sessionId,
      content,
      capabilities: ['client_tools'],
    };
    if (model) payload.model = model;
    if (workingDir) payload.working_dir = workingDir;
    if (projectContext) payload.project_context = projectContext;
    ws.send(JSON.stringify(payload));
  }

  sendInterrupt(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'interrupt', user_id: this.creds.user_id }));
    }
  }

  async sendToolResult(callId: string, output: string | null, error: string | null): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({
      type: 'tool_result',
      user_id: this.creds.user_id,
      call_id: callId,
      content: output,
      error,
    }));
  }

  async getModels(): Promise<string[]> {
    const resp = await fetch(`${this.serverUrl}/api/models`, {
      headers: { Authorization: `Bearer ${this.creds.token}` },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json() as { models: string[] };
    return data.models ?? [];
  }

  async getSessions(): Promise<Array<Record<string, unknown>>> {
    const resp = await fetch(`${this.serverUrl}/history`, {
      headers: { Authorization: `Bearer ${this.creds.token}` },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json() as Promise<Array<Record<string, unknown>>>;
  }

  async getSessionHistory(sessionId: number): Promise<Array<Record<string, unknown>>> {
    const resp = await fetch(`${this.serverUrl}/history/${sessionId}`, {
      headers: { Authorization: `Bearer ${this.creds.token}` },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json() as Promise<Array<Record<string, unknown>>>;
  }

  close(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
