/**
 * Client WebSocket bidirectionnel vers le backend Jean-Heude.
 * Connexion persistante par session, EventEmitter pour les events.
 */
import { EventEmitter } from 'events';
import WebSocket from 'ws';
import { JHConfig, wsUrl } from './config.js';
import { Credentials } from './auth.js';

export interface TokenEvent { content: string }
export interface DoneEvent { session_id: number | null; model: string }
export interface ErrorEvent { content: string }
export interface SystemEvent { content: string }
export interface ToolCallEvent { call_id: string; name: string; args: Record<string, unknown> }

export class JHClient extends EventEmitter {
  config: JHConfig;
  readonly creds: Credentials;
  private ws: WebSocket | null = null;
  lastSessionId: number | null = null;
  lastModel: string = '';

  constructor(config: JHConfig, creds: Credentials) {
    super();
    this.config = config;
    this.creds = creds;
  }

  /** Ouvre la connexion WebSocket (si pas déjà ouverte). */
  private connect(): Promise<WebSocket> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve(this.ws);
    }

    return new Promise((resolve, reject) => {
      const url = `${wsUrl(this.config.server.url)}/ws/${this.creds.user_id}?token=${this.creds.token}`;
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
          this.lastSessionId = (msg.session_id as number) ?? null;
          this.lastModel = (msg.model as string) ?? '';
          this.emit('done', { session_id: this.lastSessionId, model: this.lastModel });
        } else if (type === 'error') {
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
        this.ws = null;
      });
    });
  }

  /** Envoie un message et connecte si nécessaire. */
  async sendMessage(
    content: string,
    sessionId: number | null,
    model: string = '',
  ): Promise<void> {
    const ws = await this.connect();
    const payload: Record<string, unknown> = {
      type: 'message',
      user_id: this.creds.user_id,
      session_id: sessionId,
      content,
      capabilities: ['client_tools'],
    };
    if (model) payload.model = model;
    ws.send(JSON.stringify(payload));
  }

  /** Envoie le résultat d'un outil local au serveur. */
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

  /** Liste les modèles Ollama disponibles sur le serveur. */
  async getModels(): Promise<string[]> {
    const resp = await fetch(`${this.config.server.url}/api/models`, {
      headers: { Authorization: `Bearer ${this.creds.token}` },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json() as { models: string[] };
    return data.models ?? [];
  }

  /** Récupère la liste des sessions via HTTP. */
  async getSessions(): Promise<Array<Record<string, unknown>>> {
    const resp = await fetch(`${this.config.server.url}/history`, {
      headers: { Authorization: `Bearer ${this.creds.token}` },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json() as Promise<Array<Record<string, unknown>>>;
  }

  /** Récupère l'historique d'une session via HTTP. */
  async getSessionHistory(sessionId: number): Promise<Array<Record<string, unknown>>> {
    const resp = await fetch(`${this.config.server.url}/history/${sessionId}`, {
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
