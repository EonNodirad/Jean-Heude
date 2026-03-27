/**
 * Auth : lecture/écriture du token CLI depuis ~/.config/jh/token.json
 * et de la config serveur depuis ~/.config/jh/config.toml.
 * Partage TOUT avec le CLI `jh` — une seule source de vérité.
 */
import { readFileSync, writeFileSync, existsSync, chmodSync, mkdirSync, unlinkSync } from 'fs';
import { join, dirname } from 'path';
import { homedir } from 'os';

const CONFIG_DIR  = join(homedir(), '.config', 'jh');
export const TOKEN_FILE  = join(CONFIG_DIR, 'token.json');
export const CONFIG_FILE = join(CONFIG_DIR, 'config.toml');

export interface Credentials {
  token: string;
  user_id: string;
  is_admin: boolean;
  server_url: string;
}

// ── Lecture ───────────────────────────────────────────────────────────────────

export function loadCredentials(): Credentials | null {
  if (!existsSync(TOKEN_FILE)) return null;
  try {
    return JSON.parse(readFileSync(TOKEN_FILE, 'utf-8')) as Credentials;
  } catch {
    return null;
  }
}

/** Lit l'URL serveur depuis config.toml (même valeur que le CLI). */
export function loadServerUrl(): string {
  const defaultUrl = 'http://localhost:8000';
  if (!existsSync(CONFIG_FILE)) return defaultUrl;
  try {
    const content = readFileSync(CONFIG_FILE, 'utf-8');
    const match = content.match(/^url\s*=\s*"?([^"\n]+)"?/m);
    if (!match) return defaultUrl;
    const raw = match[1].trim();
    return raw.startsWith('http') ? raw : `http://${raw}`;
  } catch {
    return defaultUrl;
  }
}

export function isTokenExpired(token: string): boolean {
  try {
    const [, payload] = token.split('.');
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf-8'));
    const exp: number = decoded.exp ?? 0;
    return Date.now() / 1000 > exp;
  } catch {
    return true;
  }
}

// ── Écriture ──────────────────────────────────────────────────────────────────

export function saveCredentials(creds: Credentials): void {
  mkdirSync(dirname(TOKEN_FILE), { recursive: true });
  writeFileSync(TOKEN_FILE, JSON.stringify(creds, null, 2), 'utf-8');
  chmodSync(TOKEN_FILE, 0o600);
}

/** Écrit l'URL serveur dans config.toml (partagé avec le CLI). */
export function saveServerUrl(url: string): void {
  mkdirSync(CONFIG_DIR, { recursive: true });
  if (!existsSync(CONFIG_FILE)) {
    writeFileSync(CONFIG_FILE,
      `[server]\nurl = "${url}"\n\n[display]\nmarkdown = true\n\n[defaults]\nsession = "last"\n`,
      'utf-8',
    );
    return;
  }
  let content = readFileSync(CONFIG_FILE, 'utf-8');
  if (/^url\s*=/m.test(content)) {
    content = content.replace(/^url\s*=.*/m, `url = "${url}"`);
  } else {
    content = content.replace(/\[server\]/, `[server]\nurl = "${url}"`);
  }
  writeFileSync(CONFIG_FILE, content, 'utf-8');
}

// ── Login / Logout ────────────────────────────────────────────────────────────

export async function login(serverUrl: string, userId: string, password: string): Promise<Credentials> {
  const resp = await fetch(`${serverUrl}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, password }),
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`Connexion échouée (${resp.status}) : ${body}`);
  }
  const data = await resp.json() as { access_token: string; user_id: string; is_admin: boolean };
  const creds: Credentials = {
    token: data.access_token,
    user_id: data.user_id,
    is_admin: data.is_admin ?? false,
    server_url: serverUrl,
  };
  saveCredentials(creds);
  return creds;
}

export async function logout(serverUrl: string, token: string): Promise<void> {
  try {
    await fetch(`${serverUrl}/api/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch { /* ignorer les erreurs réseau */ }
  if (existsSync(TOKEN_FILE)) unlinkSync(TOKEN_FILE);
}

/** Convertit http:// en ws:// */
export function wsUrl(httpUrl: string): string {
  return httpUrl.replace(/^http/, 'ws');
}
