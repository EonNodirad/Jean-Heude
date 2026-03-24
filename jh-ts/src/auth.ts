/**
 * Auth : login/logout, stockage JWT dans ~/.config/jh/token.json
 */
import { readFileSync, writeFileSync, unlinkSync, existsSync, chmodSync } from 'fs';
import { TOKEN_FILE } from './config.js';

export interface Credentials {
  token: string;
  user_id: string;
  is_admin: boolean;
  server_url: string;
}

export function loadCredentials(): Credentials | null {
  if (!existsSync(TOKEN_FILE)) return null;
  try {
    return JSON.parse(readFileSync(TOKEN_FILE, 'utf-8')) as Credentials;
  } catch {
    return null;
  }
}

function saveCredentials(creds: Credentials): void {
  writeFileSync(TOKEN_FILE, JSON.stringify(creds, null, 2), 'utf-8');
  chmodSync(TOKEN_FILE, 0o600);
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
  } catch {
    // Ignorer les erreurs réseau au logout
  }
  if (existsSync(TOKEN_FILE)) unlinkSync(TOKEN_FILE);
}
