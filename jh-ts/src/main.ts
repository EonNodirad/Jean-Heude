#!/usr/bin/env node
/**
 * Entry point du CLI Jean-Heude.
 */
import * as readline from 'readline';
import { Command } from 'commander';
import * as os from 'os';
import * as path from 'path';

import { loadConfig, saveConfig, wsUrl } from './config.js';
import * as auth from './auth.js';
import { JHClient } from './client.js';
import * as R from './renderer.js';
import { interactiveLoop, oneShot, PermissionMode } from './cli.js';
import { askLine, askPassword } from './kitty.js';

const program = new Command();

program
  .name('jh')
  .description('Jean-Heude CLI — agent conversationnel dans le terminal')
  .version('0.2.0')
  .argument('[message]', 'Message one-shot (optionnel)')
  .option('--new-session', 'Forcer une nouvelle session')
  .option('--session <id>', 'Reprendre une session spécifique', parseInt)
  .option('--model <nom>', 'Forcer un modèle Ollama')
  .option('--server <url>', 'URL du backend (surcharge config)')
  .option('--auto', 'Exécuter tous les outils sans confirmation')
  .option('--plan', 'Mode dry-run : afficher les tool_calls sans les exécuter')
  .option('--cwd <chemin>', 'Répertoire de travail pour les outils (défaut: répertoire courant)');

// ── jh login ──────────────────────────────────────────────────────────────

program
  .command('login')
  .description('Se connecter à Jean-Heude')
  .action(async () => {
    const conf = loadConfig();
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

    R.printInfo(`Connexion à ${conf.server.url}`);

    const userId = (await askLine(rl, 'Pseudo : ')).trim();
    rl.close();

    const password = await askPassword('Mot de passe : ');

    try {
      const creds = await auth.login(conf.server.url, userId, password);
      R.printSuccess(`Connecté en tant que ${creds.user_id}`);
      if (creds.is_admin) R.printInfo('(compte administrateur)');
    } catch (e) {
      R.printError(String(e));
      process.exit(1);
    }
  });

// ── jh logout ─────────────────────────────────────────────────────────────

program
  .command('logout')
  .description('Se déconnecter (révoque le token)')
  .action(async () => {
    const conf = loadConfig();
    const creds = auth.loadCredentials();
    if (creds) {
      await auth.logout(conf.server.url, creds.token);
      R.printSuccess('Déconnecté.');
    } else {
      R.printInfo('Aucune session active.');
    }
  });

// ── Main action ───────────────────────────────────────────────────────────

program.action(async (message: string | undefined, opts: {
  newSession?: boolean;
  session?: number;
  model?: string;
  server?: string;
  auto?: boolean;
  plan?: boolean;
  cwd?: string;
}) => {
  const conf = loadConfig();
  if (opts.server) {
    conf.server.url = opts.server.replace(/\/$/, '');
    saveConfig(conf);
  }

  const creds = auth.loadCredentials();
  if (!creds) {
    R.printError("Non connecté. Lance `jh login` d'abord.");
    process.exit(1);
  }

  if (auth.isTokenExpired(creds.token)) {
    R.printError('Token expiré. Lance `jh login` pour te reconnecter.');
    process.exit(1);
  }

  // Si le token a été créé sur un serveur différent, utiliser ce serveur
  if (creds.server_url && !opts.server && creds.server_url !== conf.server.url) {
    conf.server.url = creds.server_url;
  }

  let sessionId: number | null = null;
  if (opts.session) {
    sessionId = opts.session;
  } else if (opts.newSession) {
    sessionId = null;
  }

  const permissionMode: PermissionMode = opts.plan ? 'plan' : opts.auto ? 'auto' : 'ask';
  const model = opts.model ?? '';
  const cwd = opts.cwd ? path.resolve(opts.cwd) : process.cwd();

  const client = new JHClient(conf, creds);

  if (message) {
    await oneShot(conf, client, message, sessionId, model, permissionMode, cwd);
  } else {
    await interactiveLoop(conf, client, sessionId, model, permissionMode, cwd);
  }
});

program.parseAsync(process.argv).catch((e) => {
  R.printError(String(e));
  process.exit(1);
});
