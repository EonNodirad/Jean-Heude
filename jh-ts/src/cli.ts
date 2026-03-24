/**
 * Loop interactive agentique principale.
 */
import * as readline from 'readline';
import * as fs from 'fs';
import * as path from 'path';
import chalk from 'chalk';
import { JHConfig, HISTORY_FILE, CONFIG_DIR, saveConfig } from './config.js';
import { JHClient, ToolCallEvent } from './client.js';
import * as tools from './tools.js';
import * as R from './renderer.js';
import { askLine as kittyAskLine, askPassword } from './kitty.js';
import { recordAudio } from './voice.js';
import * as auth from './auth.js';

export type PermissionMode = 'ask' | 'auto' | 'plan';

// ── Readline avec historique ──────────────────────────────────────────────

function createRL(): readline.Interface {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
  // historyFile est supporté par Node.js mais absent des types TS
  const opts = {
    input: process.stdin,
    output: process.stdout,
    terminal: true,
    historySize: 500,
    historyFile: HISTORY_FILE,
  } as readline.ReadLineOptions;
  return readline.createInterface(opts);
}


// ── Loop interactive ──────────────────────────────────────────────────────

export async function interactiveLoop(
  config: JHConfig,
  client: JHClient,
  initialSessionId: number | null,
  initialModel: string,
  permissionMode: PermissionMode,
  cwd: string,
): Promise<void> {
  tools.setWorkingDir(cwd);

  let activeClient = client;
  let currentSessionId = initialSessionId;
  let currentModel = initialModel;
  let pendingImage: string | null = null;

  // Restaurer la dernière session si configuré
  if (currentSessionId === null && config.defaults.session === 'last') {
    try {
      const sessions = await activeClient.getSessions();
      if (sessions.length > 0) {
        currentSessionId = sessions[0]['id'] as number;
        R.printInfo(`Session #${currentSessionId} reprise : ${String(sessions[0]['resume'] ?? '').slice(0, 60)}`);
      }
    } catch {
      // Ignorer si pas de sessions
    }
  }

  R.printBanner(activeClient.creds.user_id, config.server.url, currentModel);
  R.printWorkingDir(tools.getWorkingDir());

  const rl = createRL();

  const askLine = (): Promise<string | null> =>
    new Promise((resolve) => {
      R.printInputHints(pendingImage);
      kittyAskLine(rl, chalk.cyan('❯') + ' ').then(resolve);
      rl.once('close', () => resolve(null));
    });

  // eslint-disable-next-line no-constant-condition
  while (true) {
    let text: string | null;
    try {
      text = await askLine();
    } catch {
      break;
    }

    if (text === null) {
      R.printInfo('\nAu revoir !');
      break;
    }

    text = text.trim();
    if (!text) continue;

    // ── Slash commands ──
    if (text.startsWith('/')) {
      const result = await handleCommand(
        text, activeClient, currentSessionId, currentModel, permissionMode, rl, config,
        (img) => { pendingImage = img; },
        () => pendingImage,
      );
      currentSessionId = result.sessionId;
      currentModel = result.model;
      permissionMode = result.permissionMode;
      if (result.newClient) {
        activeClient.close();
        activeClient = result.newClient;
        currentSessionId = null;
        R.printBanner(activeClient.creds.user_id, activeClient.config.server.url, currentModel);
      }
      if (result.quit) break;
      continue;
    }

    // ── Message vers Jean-Heude ──
    process.stdout.write('\n');
    let fullResponse = '';

    try {
      if (pendingImage) {
        const imgPath = pendingImage;
        pendingImage = null;
        R.printInfo(`📸 Envoi avec image : ${imgPath}`);
        await runMultimodalTurn(activeClient, text, imgPath, currentSessionId, currentModel, permissionMode, (chunk) => {
          R.printToken(chunk);
          fullResponse += chunk;
        });
      } else {
        await runAgenticTurn(activeClient, text, currentSessionId, currentModel, permissionMode, (chunk) => {
          R.printToken(chunk);
          fullResponse += chunk;
        });
      }
    } catch (e) {
      process.stdout.write('\n');
      R.printError(String(e));
      continue;
    }

    process.stdout.write('\n');

    // Mettre à jour session_id
    if (activeClient.lastSessionId != null) currentSessionId = activeClient.lastSessionId;
    if (activeClient.lastModel) currentModel = activeClient.lastModel;
  }

  rl.close();
  activeClient.close();
}

// ── Mode one-shot ─────────────────────────────────────────────────────────

export async function oneShot(
  config: JHConfig,
  client: JHClient,
  message: string,
  sessionId: number | null,
  model: string,
  permissionMode: PermissionMode,
  cwd: string,
): Promise<void> {
  tools.setWorkingDir(cwd);
  const isPiped = !process.stdout.isTTY;
  let fullResponse = '';
  try {
    await runAgenticTurn(client, message, sessionId, model, permissionMode, (chunk) => {
      if (isPiped) {
        process.stderr.write(chunk);
      } else {
        R.printToken(chunk);
      }
      fullResponse += chunk;
    });
    if (isPiped) {
      process.stdout.write(fullResponse);
    } else {
      process.stdout.write('\n');
      if (config.display.markdown && fullResponse.trim()) {
        R.renderMarkdown(fullResponse);
      }
    }
  } catch (e) {
    process.stdout.write('\n');
    R.printError(String(e));
    process.exit(1);
  } finally {
    client.close();
  }
}

// ── Boucle agentique (un tour) ────────────────────────────────────────────

async function runAgenticTurn(
  client: JHClient,
  message: string,
  sessionId: number | null,
  model: string,
  permissionMode: PermissionMode,
  onToken: (chunk: string) => void,
): Promise<void> {
  return new Promise(async (resolve, reject) => {
    let interrupted = false;
    let stopThinking: (() => void) | null = null;

    const clearThinking = () => { stopThinking?.(); stopThinking = null; };

    const sigintHandler = () => {
      if (interrupted) return;
      interrupted = true;
      clearThinking();
      process.stdout.write('\n');
      R.printInfo('Interruption…');
      client.sendInterrupt();
      cleanup();
      resolve();
    };

    process.once('SIGINT', sigintHandler);

    const cleanup = () => {
      clearThinking();
      process.removeListener('SIGINT', sigintHandler);
      client.removeListener('tool_call', toolCallHandler);
      client.removeListener('done', doneHandler);
      client.removeListener('error', errorHandler);
      client.removeListener('disconnect', disconnectHandler);
    };

    // Écouter les tool_calls de façon concurrente pendant le streaming
    const toolCallHandler = async (event: ToolCallEvent) => {
      clearThinking();
      process.stdout.write('\n');
      R.printToolCall(event.name, event.args);

      if (permissionMode === 'plan') {
        R.printToolSkipped(event.name);
        await client.sendToolResult(event.call_id, '(non exécuté - mode plan)', null);
        return;
      }

      if (permissionMode === 'ask' && tools.isDestructive(event.name)) {
        if (event.name === 'client_edit_file' && event.args.old_str && event.args.new_str) {
          R.printDiff(event.args.old_str as string, event.args.new_str as string);
        }
        const ok = await R.askPermission(event.name, event.args);
        if (!ok) {
          R.printInfo('Refusé.');
          await client.sendToolResult(event.call_id, null, 'Refusé par l\'utilisateur');
          return;
        }
      }

      const result = await tools.execute(event.name, event.args);
      R.printToolResult(event.name, result.output, result.error);
      await client.sendToolResult(event.call_id, result.output, result.error);
    };

    const doneHandler = () => {
      cleanup();
      resolve();
    };

    const errorHandler = (event: { content: string }) => {
      cleanup();
      reject(new Error(event.content));
    };

    const disconnectHandler = () => {
      cleanup();
      reject(new Error('Connexion perdue — réponse incomplète'));
    };

    client.on('token', (event: { content: string }) => {
      // Effacer le spinner au premier token
      clearThinking();
      const chunk = event.content.replace(/\|\|AUDIO_ID:.*?\|\|/g, '');
      if (chunk && !chunk.startsWith('¶')) {
        onToken(chunk);
      }
    });

    client.on('system', (event: { content: string }) => {
      clearThinking();
      process.stdout.write('\n');
      R.printSystem(event.content);
    });

    client.once('done', doneHandler);
    client.once('error', errorHandler);
    client.once('disconnect', disconnectHandler);
    client.on('tool_call', toolCallHandler);

    try {
      await client.sendMessage(message, sessionId, model, tools.getWorkingDir());
      stopThinking = R.startThinkingSpinner();
    } catch (e) {
      cleanup();
      reject(e);
    }
  });
}

// ── Tour multimodal (image) ────────────────────────────────────────────────

async function runMultimodalTurn(
  client: JHClient,
  message: string,
  imagePath: string,
  sessionId: number | null,
  model: string,
  permissionMode: PermissionMode,
  onToken: (chunk: string) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    let interrupted = false;
    let stopThinking: (() => void) | null = null;

    const clearThinking = () => { stopThinking?.(); stopThinking = null; };

    const sigintHandler = () => {
      if (interrupted) return;
      interrupted = true;
      clearThinking();
      process.stdout.write('\n');
      R.printInfo('Interruption…');
      cleanup();
      resolve();
    };

    process.once('SIGINT', sigintHandler);

    const cleanup = () => {
      clearThinking();
      process.removeListener('SIGINT', sigintHandler);
      client.removeListener('token', tokenHandler);
      client.removeListener('done', doneHandler);
      client.removeListener('error', errorHandler);
    };

    const tokenHandler = (event: { content: string }) => {
      clearThinking();
      const chunk = event.content.replace(/\|\|AUDIO_ID:.*?\|\|/g, '');
      if (chunk && !chunk.startsWith('¶')) onToken(chunk);
    };

    const doneHandler = () => { cleanup(); resolve(); };
    const errorHandler = (event: { content: string }) => { cleanup(); reject(new Error(event.content)); };

    client.on('token', tokenHandler);
    client.once('done', doneHandler);
    client.once('error', errorHandler);

    // Démarrer le spinner AVANT l'envoi, pas dans .then() (qui s'exécute trop tard)
    stopThinking = R.startThinkingSpinner();
    client.sendMultimodal(message, imagePath, sessionId, model)
      .catch((e) => { cleanup(); reject(e); });
  });
}

// ── Tour vocal ────────────────────────────────────────────────────────────

async function runVoiceTurn(
  client: JHClient,
  audioBuffer: Buffer,
  sessionId: number | null,
  model: string,
  onToken: (chunk: string) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    let interrupted = false;
    let stopThinking: (() => void) | null = null;

    const clearThinking = () => { stopThinking?.(); stopThinking = null; };

    const sigintHandler = () => {
      if (interrupted) return;
      interrupted = true;
      clearThinking();
      process.stdout.write('\n');
      R.printInfo('Interruption…');
      cleanup();
      resolve();
    };

    process.once('SIGINT', sigintHandler);

    const cleanup = () => {
      clearThinking();
      process.removeListener('SIGINT', sigintHandler);
      client.removeListener('token', tokenHandler);
      client.removeListener('done', doneHandler);
      client.removeListener('error', errorHandler);
    };

    const tokenHandler = (event: { content: string }) => {
      clearThinking();
      const chunk = event.content.replace(/\|\|AUDIO_ID:.*?\|\|/g, '');
      if (chunk && !chunk.startsWith('¶')) onToken(chunk);
    };

    const doneHandler = () => { cleanup(); resolve(); };
    const errorHandler = (event: { content: string }) => { cleanup(); reject(new Error(event.content)); };

    client.on('token', tokenHandler);
    client.once('done', doneHandler);
    client.once('error', errorHandler);

    stopThinking = R.startThinkingSpinner();
    client.sendVoice(audioBuffer, sessionId, model)
      .catch((e) => { cleanup(); reject(e); });
  });
}

// ── Slash commands ─────────────────────────────────────────────────────────

interface CommandResult {
  sessionId: number | null;
  model: string;
  permissionMode: PermissionMode;
  quit: boolean;
  newClient?: JHClient;
}

async function handleCommand(
  text: string,
  client: JHClient,
  sessionId: number | null,
  model: string,
  permissionMode: PermissionMode,
  rl: readline.Interface,
  config?: JHConfig,
  setPendingImage?: (img: string | null) => void,
  getPendingImage?: () => string | null,
): Promise<CommandResult> {
  const parts = text.trim().split(/\s+/);
  const cmd = parts[0].toLowerCase();
  const arg = parts.slice(1).join(' ');

  const noChange: CommandResult = { sessionId, model, permissionMode, quit: false };

  switch (cmd) {
    case '/help':
      R.printHelp(permissionMode);
      return noChange;

    case '/quit':
    case '/exit':
      R.printInfo('Au revoir !');
      return { ...noChange, quit: true };

    case '/clear':
      R.printInfo('Nouvelle session démarrée.');
      return { ...noChange, sessionId: null };

    case '/model': {
      if (arg === 'list') {
        try {
          const models = await client.getModels();
          if (models.length === 0) {
            R.printInfo('Aucun modèle disponible.');
          } else {
            console.log('');
            for (const m of models) {
              const active = m === model ? ' ◀ actuel' : '';
              console.log(`  ${m}${active}`);
            }
          }
        } catch (e) {
          R.printError(`Impossible de lister les modèles : ${e}`);
        }
        return noChange;
      }
      if (arg) {
        R.printSuccess(`Modèle forcé : ${arg}`);
        return { ...noChange, model: arg };
      }
      // /model vide → backend choisit automatiquement
      R.printSuccess('Modèle : automatique (choix du backend)');
      return { ...noChange, model: '' };
    }

    case '/server': {
      if (arg) {
        const url = arg.replace(/\/$/, '');
        client.config.server.url = url;
        if (config) {
          config.server.url = url;
          saveConfig(config);
        }
        R.printSuccess(`Serveur : ${url} (sauvegardé)`);
        R.printInfo('  Note : relance `jh login` si tu changes de compte sur ce serveur.');
      } else {
        R.printInfo(`Serveur actuel : ${client.config.server.url}`);
      }
      return noChange;
    }

    case '/logout': {
      try {
        await auth.logout(client.config.server.url, client.creds.token);
        R.printSuccess('Déconnecté. Utilise /login pour te reconnecter.');
      } catch (e) {
        R.printError(`Erreur logout : ${e}`);
      }
      return noChange;
    }

    case '/login': {
      const serverUrl = client.config.server.url;
      R.printInfo(`Connexion à ${serverUrl}`);
      try {
        const userId = (await kittyAskLine(rl, 'Pseudo : ')).trim();
        const password = await askPassword('Mot de passe : ');
        const creds = await auth.login(serverUrl, userId, password);
        R.printSuccess(`Connecté en tant que ${creds.user_id}`);
        if (creds.is_admin) R.printInfo('(compte administrateur)');
        const newClient = new JHClient(client.config, creds);
        return { ...noChange, newClient, sessionId: null };
      } catch (e) {
        R.printError(String(e));
        return noChange;
      }
    }

    case '/permissions': {
      const modes: PermissionMode[] = ['ask', 'auto', 'plan'];
      if (arg && modes.includes(arg as PermissionMode)) {
        R.printSuccess(`Mode de permissions : ${arg}`);
        return { ...noChange, permissionMode: arg as PermissionMode };
      }
      R.printInfo(`Mode actuel : ${permissionMode} (ask | auto | plan)`);
      return noChange;
    }

    case '/cwd':
      if (arg) {
        const resolved = path.resolve(arg);
        if (fs.existsSync(resolved)) {
          tools.setWorkingDir(resolved);
          R.printSuccess(`Répertoire de travail : ${resolved}`);
        } else {
          R.printError(`Répertoire introuvable : ${resolved}`);
        }
      } else {
        R.printWorkingDir(tools.getWorkingDir());
      }
      return noChange;

    case '/sessions': {
      let sessions: Array<Record<string, unknown>> = [];
      try {
        sessions = await client.getSessions();
      } catch (e) {
        R.printError(`Impossible de charger les sessions : ${e}`);
        return noChange;
      }
      if (sessions.length === 0) {
        R.printInfo('Aucune session existante.');
        return noChange;
      }
      R.printSessionsTable(sessions);
      const answer = await kittyAskLine(rl, '\nID à reprendre (Entrée pour annuler) : ');
      const id = parseInt(answer.trim(), 10);
      if (!isNaN(id)) {
        R.printSuccess(`Session #${id} reprise.`);
        return { ...noChange, sessionId: id };
      }
      return noChange;
    }

    case '/history': {
      if (sessionId === null) {
        R.printInfo('Aucune session active.');
        return noChange;
      }
      const limit = parseInt(arg, 10) || 10;
      let messages: Array<Record<string, unknown>> = [];
      try {
        messages = await client.getSessionHistory(sessionId);
      } catch (e) {
        R.printError(`Impossible de charger l'historique : ${e}`);
        return noChange;
      }
      for (const msg of messages.slice(-limit)) {
        const role = String(msg['role'] ?? '?');
        const content = String(msg['content'] ?? '');
        const color = role === 'user' ? '\x1b[33m' : '\x1b[36m';
        console.log(`\n${color}${role}\x1b[0m\n${content}`);
      }
      return noChange;
    }

    case '/export': {
      if (sessionId === null) {
        R.printInfo('Aucune session active.');
        return noChange;
      }
      let messages: Array<Record<string, unknown>> = [];
      try {
        messages = await client.getSessionHistory(sessionId);
      } catch (e) {
        R.printError(`Impossible de charger la session : ${e}`);
        return noChange;
      }
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const filename = `jh_session_${sessionId}_${ts}.md`;
      const lines = [`# Session Jean-Heude #${sessionId}\n\n`];
      for (const msg of messages) {
        const role = String(msg['role'] ?? '?');
        const content = String(msg['content'] ?? '');
        lines.push(`**${role.charAt(0).toUpperCase() + role.slice(1)}**\n\n${content}\n\n---\n\n`);
      }
      fs.writeFileSync(filename, lines.join(''), 'utf-8');
      R.printSuccess(`Exporté dans : ${filename}`);
      return noChange;
    }

    case '/voice': {
      try {
        const audioBuffer = await recordAudio();
        process.stdout.write('\n');
        await runVoiceTurn(client, audioBuffer, sessionId, model, (chunk: string) => {
          R.printToken(chunk);
        });
        process.stdout.write('\n');
      } catch (e) {
        R.printError(String(e));
      }
      return noChange;
    }

    case '/attach': {
      if (!arg) {
        R.printError('Usage : /attach <chemin_image>');
        return noChange;
      }
      const resolved = path.resolve(arg);
      if (!fs.existsSync(resolved)) {
        R.printError(`Fichier introuvable : ${resolved}`);
        return noChange;
      }
      const ext = path.extname(resolved).toLowerCase();
      const allowed = ['.png', '.jpg', '.jpeg', '.gif', '.webp'];
      if (!allowed.includes(ext)) {
        R.printError(`Format non supporté : ${ext}. Utiliser : ${allowed.join(', ')}`);
        return noChange;
      }
      setPendingImage?.(resolved);
      R.printSuccess(`Image en attente : ${resolved}`);
      R.printInfo('  Tape ton message pour l\'envoyer avec l\'image.');
      return noChange;
    }

    case '/detach': {
      const current = getPendingImage?.();
      if (!current) {
        R.printInfo('Aucune image en attente.');
      } else {
        setPendingImage?.(null);
        R.printSuccess('Image annulée.');
      }
      return noChange;
    }

    default:
      R.printError(`Commande inconnue : ${cmd}. Tape /help.`);
      return noChange;
  }
}
