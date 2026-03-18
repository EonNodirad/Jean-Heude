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
  display: {
    markdown: boolean;
  };
  defaults: {
    session: 'last' | 'new';
  };
}

const DEFAULT_CONFIG: JHConfig = {
  server: { url: 'http://localhost:8000' },
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
    return {
      server: { url: (parsed.server?.url as string) ?? DEFAULT_CONFIG.server.url },
      display: { markdown: (parsed.display?.markdown as boolean) ?? DEFAULT_CONFIG.display.markdown },
      defaults: { session: (parsed.defaults?.session as 'last' | 'new') ?? DEFAULT_CONFIG.defaults.session },
    };
  } catch {
    return DEFAULT_CONFIG;
  }
}

/** Retourne l'URL WS correspondant à l'URL HTTP du serveur */
export function wsUrl(httpUrl: string): string {
  return httpUrl.replace(/^http/, 'ws');
}
