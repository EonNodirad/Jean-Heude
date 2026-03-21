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
  private _requestInFlight = false;
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

  /** Envoie un message et connecte si nécessaire. */
  async sendMessage(
    content: string,
    sessionId: number | null,
    model: string = '',
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
    ws.send(JSON.stringify(payload));
  }

  /**
   * Envoie un message avec une image via HTTP multipart /api/multimodal.
   * Émet les mêmes events que sendMessage : 'token', 'done', 'error'.
   */
  async sendMultimodal(
    content: string,
    imagePath: string,
    sessionId: number | null,
    model: string = '',
  ): Promise<void> {
    const { readFileSync } = await import('fs');
    const { extname } = await import('path');
    const imageBuffer = readFileSync(imagePath);
    const ext = extname(imagePath).toLowerCase().replace('.', '') || 'png';
    const mimeType = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;

    process.stderr.write(`[debug] image: ${imagePath} (${imageBuffer.length} octets, ${mimeType})\n`);

    const form = new FormData();
    form.append('prompt', content);
    form.append('image', new Blob([new Uint8Array(imageBuffer)], { type: mimeType }), `image.${ext}`);
    if (sessionId !== null) form.append('session_id', String(sessionId));
    if (model) form.append('model', model);

    const resp = await fetch(`${this.config.server.url}/api/multimodal`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.creds.token}` },
      body: form,
    });

    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      this.emit('error', { content: `Multimodal HTTP ${resp.status}: ${body}` });
      return;
    }

    process.stderr.write(`[debug] multimodal OK, session=${resp.headers.get('x-session-id')}\n`);

    // Lire x-session-id depuis les headers
    const sessionHeader = resp.headers.get('x-session-id');
    if (sessionHeader) this.lastSessionId = parseInt(sessionHeader, 10);
    const modelHeader = resp.headers.get('x-chosen-model');
    if (modelHeader) this.lastModel = modelHeader;

    // Streamer la réponse token par token
    if (!resp.body) {
      this.emit('done', { session_id: this.lastSessionId, model: this.lastModel });
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (chunk) this.emit('token', { content: chunk });
      }
    } finally {
      reader.releaseLock();
    }
    this.emit('done', { session_id: this.lastSessionId, model: this.lastModel });
  }

  /**
   * Envoie un enregistrement audio au backend /stt.
   * Le backend transcrit + fait tourner l'agent et renvoie un StreamingResponse.
   * Émet 'token', 'done', 'error' comme sendMessage.
   */
  async sendVoice(
    audioBuffer: Buffer,
    sessionId: number | null,
    model: string = '',
  ): Promise<void> {
    const form = new FormData();
    form.append('file', new Blob([new Uint8Array(audioBuffer)], { type: 'audio/wav' }), 'audio.wav');
    if (sessionId !== null) form.append('session_id', String(sessionId));

    const resp = await fetch(`${this.config.server.url}/stt`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.creds.token}` },
      body: form,
    });

    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      this.emit('error', { content: `STT HTTP ${resp.status}: ${body}` });
      return;
    }

    const sessionHeader = resp.headers.get('x-session-id');
    if (sessionHeader) this.lastSessionId = parseInt(sessionHeader, 10);
    const modelHeader = resp.headers.get('x-chosen-model');
    if (modelHeader) this.lastModel = modelHeader;

    if (!resp.body) {
      this.emit('done', { session_id: this.lastSessionId, model: this.lastModel });
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (chunk) this.emit('token', { content: chunk });
      }
    } finally {
      reader.releaseLock();
    }
    this.emit('done', { session_id: this.lastSessionId, model: this.lastModel });
  }

  /** Signale une interruption utilisateur (Ctrl+C) au backend. */
  sendInterrupt(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'interrupt', user_id: this.creds.user_id }));
    }
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
