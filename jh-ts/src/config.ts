/**
 * Config ~/.config/jh/config.toml
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import TOML from '@iarna/toml';

export const CONFIG_DIR = join(homedir(), '.config', 'jh');
export const CONFIG_FILE = join(CONFIG_DIR, 'config.toml');
export const TOKEN_FILE = join(CONFIG_DIR, 'token.json');
export const HISTORY_FILE = join(CONFIG_DIR, 'history');

export interface JHConfig {
  server: {
    url: string;
  };
  stt: {
    url: string;
  };
  display: {
    markdown: boolean;
  };
  defaults: {
    session: 'last' | 'new';
  };
}

const DEFAULT_CONFIG: JHConfig = {
  server: { url: 'http://localhost:8000' },
  stt: { url: 'http://localhost:8001' },
  display: { markdown: true },
  defaults: { session: 'last' },
};

export function loadConfig(): JHConfig {
  mkdirSync(CONFIG_DIR, { recursive: true });

  if (!existsSync(CONFIG_FILE)) {
    const tomlStr =
      `[server]\nurl = "http://localhost:8000"\n\n[display]\nmarkdown = true\n\n[defaults]\nsession = "last"\n`;
    writeFileSync(CONFIG_FILE, tomlStr, 'utf-8');
    return DEFAULT_CONFIG;
  }

  try {
    const raw = readFileSync(CONFIG_FILE, 'utf-8');
    const parsed = TOML.parse(raw) as Partial<JHConfig>;
    const rawUrl = (parsed.server?.url as string) ?? DEFAULT_CONFIG.server.url;
    const serverUrl = rawUrl.startsWith('http') ? rawUrl : `http://${rawUrl}`;
    return {
      server: { url: serverUrl },
      stt: { url: ((parsed as Record<string, Record<string, string>>)['stt']?.url) ?? DEFAULT_CONFIG.stt.url },
      display: { markdown: (parsed.display?.markdown as boolean) ?? DEFAULT_CONFIG.display.markdown },
      defaults: { session: (parsed.defaults?.session as 'last' | 'new') ?? DEFAULT_CONFIG.defaults.session },
    };
  } catch {
    return DEFAULT_CONFIG;
  }
}

/** Écrit la config dans ~/.config/jh/config.toml */
export function saveConfig(config: JHConfig): void {
  mkdirSync(CONFIG_DIR, { recursive: true });
  const tomlStr = [
    `[server]`,
    `url = "${config.server.url}"`,
    ``,
    `[stt]`,
    `url = "${config.stt.url}"`,
    ``,
    `[display]`,
    `markdown = ${config.display.markdown}`,
    ``,
    `[defaults]`,
    `session = "${config.defaults.session}"`,
    ``,
  ].join('\n');
  writeFileSync(CONFIG_FILE, tomlStr, 'utf-8');
}

/** Retourne l'URL WS correspondant à l'URL HTTP du serveur */
export function wsUrl(httpUrl: string): string {
  return httpUrl.replace(/^http/, 'ws');
}
