/**
 * Affichage terminal : streaming tokens, tool calls, Markdown, bannière.
 */
import chalk from 'chalk';
import { marked } from 'marked';
// @ts-ignore — marked-terminal n'a pas toujours des types
import TerminalRenderer from 'marked-terminal';

marked.setOptions({ renderer: new TerminalRenderer() });

// ── Tokens streaming ──────────────────────────────────────────────────────

export function printToken(chunk: string): void {
  process.stdout.write(chunk);
}

// ── Markdown ──────────────────────────────────────────────────────────────

export function renderMarkdown(text: string): void {
  const rendered = marked(text) as string;
  process.stdout.write('\n' + rendered);
}

// ── Diff visuel ───────────────────────────────────────────────────────────

export function printDiff(oldStr: string, newStr: string): void {
  const oldLines = oldStr.split('\n');
  const newLines = newStr.split('\n');

  console.log(chalk.dim('  ┌─ diff ──────────────────────────────────────────'));
  for (const line of oldLines) {
    console.log(chalk.red(`  - ${line}`));
  }
  for (const line of newLines) {
    console.log(chalk.green(`  + ${line}`));
  }
  console.log(chalk.dim('  └─────────────────────────────────────────────────'));
}

// ── Tool calls ────────────────────────────────────────────────────────────

export function printToolCall(name: string, args: Record<string, unknown>): void {
  const clientName = name.replace(/^client_/, '');
  const argsStr = formatArgs(args);
  console.log(chalk.dim('\n') + chalk.hex('#e7644f').bold(`⚙ ${clientName}`) + chalk.dim(`(${argsStr})`));
}

export function printToolResult(name: string, output: string | null, error: string | null): void {
  if (error) {
    console.log(chalk.red(`  ✗ ${error}`));
    return;
  }
  if (!output) return;
  const lines = output.split('\n');
  const preview = lines.slice(0, 3).join('\n');
  const suffix = lines.length > 3 ? chalk.dim(` … (${lines.length} lignes)`) : '';
  console.log(chalk.dim(`  → ${preview.replace(/\n/g, '\n    ')}`) + suffix);
}

export function printToolSkipped(name: string): void {
  const clientName = name.replace(/^client_/, '');
  console.log(chalk.yellow(`  ⊘ ${clientName} — non exécuté (mode plan)`));
}

function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([k, v]) => {
      const str = typeof v === 'string' ? `"${v.length > 40 ? v.slice(0, 40) + '…' : v}"` : JSON.stringify(v);
      return `${k}=${str}`;
    })
    .join(', ');
}

// ── Permissions ───────────────────────────────────────────────────────────

export async function askPermission(name: string, args: Record<string, unknown>): Promise<boolean> {
  const clientName = name.replace(/^client_/, '');
  const argsStr = formatArgs(args);
  process.stdout.write(
    chalk.yellow(`\n⚠ Exécuter `) +
    chalk.yellow.bold(`${clientName}(${argsStr})`) +
    chalk.yellow(` ? `) +
    chalk.dim(`[y/N] `),
  );

  // Désactiver Kitty keyboard pour la saisie
  if ((process.stdout as NodeJS.WriteStream).isTTY) process.stdout.write('\x1b[>0u');

  return new Promise((resolve) => {
    const stdin = process.stdin as NodeJS.ReadStream;
    if (stdin.isTTY) stdin.setRawMode(true);
    stdin.setEncoding('utf8');
    stdin.resume();
    stdin.once('data', (data) => {
      if (stdin.isTTY) stdin.setRawMode(false);
      stdin.pause();
      if ((process.stdout as NodeJS.WriteStream).isTTY) process.stdout.write('\x1b[<u');
      const answer = data.toString().replace(/\x1b\[[^a-zA-Z]*[a-zA-Z]/g, '').trim().toLowerCase();
      process.stdout.write('\n');
      resolve(answer === 'y' || answer === 'yes' || answer === 'o' || answer === 'oui');
    });
  });
}

// ── Messages ──────────────────────────────────────────────────────────────

export function printError(msg: string): void {
  console.error(chalk.red.bold(`✗ ${msg}`));
}

export function printInfo(msg: string): void {
  console.log(chalk.dim.cyan(msg));
}

export function printSuccess(msg: string): void {
  console.log(chalk.green.bold(`✓ ${msg}`));
}

export function printSystem(msg: string): void {
  console.log(chalk.italic.dim(`⚙ ${msg}`));
}

export function printWorkingDir(dir: string): void {
  console.log(chalk.dim(`📁 ${dir}`));
}

// ── Avatar + Bannière ─────────────────────────────────────────────────────

export function printBanner(userId: string, server: string, model: string = ''): void {
  const b     = chalk.cyan;
  const hat   = chalk.white.bold;
  const eyec  = chalk.hex('#FF8C00').bold;
  const must  = chalk.hex('#8B4513').bold;
  const ant   = chalk.yellow;
  const rv    = chalk.dim;
  const brand = chalk.hex('#e7644f').bold;

  const avatar = [
    `     ${ant('●')}               ${ant('≋≋')}`,
    `     ${ant('│')}    ${hat('._______.')}   ${ant('≋')}`,
    `     ${ant('│')}   ${hat('/ ⚙   ♦  \\')}  ${ant('≋')}`,
    `     ${ant('│')}  ${hat('(___________)')}`,
    `    ${hat('(___________________)')}`,
    `    ${b('(')} ${rv('·  ·  ·  ·  ·  ·  ·')} ${b(')')}`,
    `   ${b('(')}  ${rv('·')}  ${b('.----------.')}  ${rv('·')}  ${b(')')}`,
    `  ${b('(')}  ${rv('·')}  ${b('|')} ${eyec('.--------.')} ${b('|')}  ${rv('·')}  ${b(')')}`,
    `  ${b('(')}  ${rv('·')}  ${b('|')}${eyec('(((  O  )))')}${b('|')}  ${rv('·')}  ${b(')')}`,
    `  ${b('(')}  ${rv('·')}  ${b('|')} ${eyec("'--------'")} ${b('|')}  ${rv('·')}  ${b(')')}`,
    `   ${b('(')}  ${rv('·')}  ${b("'----------'")}  ${rv('·')}  ${b(')')}`,
    `    ${b('(')} ${rv('·  ·  ·  ·  ·  ·  ·')} ${b(')')}`,
    `     ${b('(___________________)')}`,
    `        ${must('~~~~~~~~~~~~~~~~')}`,
    `     ${must('~~~~\\')}            ${must('/~~~~')}`,
    `   ${must('~~~~~~~')}              ${must('~~~~~~~')}`,
    ` ${must('~~~~~~~~~~')}              ${must('~~~~~~~~~~')}`,
  ];

  for (const line of avatar) {
    process.stdout.write(line + '\n');
  }

  process.stdout.write('\n');
  process.stdout.write(
    '  ' + brand('J.E.A.N-H.E.U.D.E') +
    chalk.dim(`  ${userId} @ ${server}`) +
    (model ? chalk.dim.cyan(`  (${model})`) : '') + '\n',
  );
  process.stdout.write(
    chalk.dim('  Tape ') + chalk.dim.bold('/help') +
    chalk.dim(' · Ctrl+C interrompt · Ctrl+D quitte\n\n'),
  );
}

// ── Spinner d'attente ─────────────────────────────────────────────────────

const THINKING_MSGS = [
  'je réfléchis…',
  'laisse-moi le temps…',
  'un instant…',
  'je cogite…',
  'je cherche…',
  'patience…',
  'analyse en cours…',
  'je traite ça…',
  'hm, voyons…',
  'c\'est complexe…',
  'je consulte ma mémoire…',
  'mes neurones chauffent…',
  'presque…',
  'quelques secondes encore…',
  'laisse-moi assembler ça…',
  'traitement en profondeur…',
];

/**
 * Affiche des phrases d'attente rotatives toutes les 4-5s.
 * Retourne une fonction stop() qui efface la ligne.
 */
export function startThinkingSpinner(): () => void {
  if (!process.stdout.isTTY) return () => {};

  let idx = Math.floor(Math.random() * THINKING_MSGS.length);
  let stopped = false;

  const write = () => {
    if (stopped) return;
    const msg = THINKING_MSGS[idx % THINKING_MSGS.length];
    idx++;
    process.stdout.write('\r\x1b[2K' + chalk.dim.italic(`  ${msg}`));
  };

  write();
  const interval = setInterval(() => {
    if (stopped) return;
    write();
  }, 4000 + Math.floor(Math.random() * 1000));

  return () => {
    if (stopped) return;
    stopped = true;
    clearInterval(interval);
    process.stdout.write('\r\x1b[2K');
  };
}

// ── Barre d'input ─────────────────────────────────────────────────────────

export function printInputHints(pendingImage: string | null = null): void {
  const cols = Math.min(process.stdout.columns || 80, 100);
  const img  = pendingImage ? chalk.yellow(` 🖼 ${pendingImage}`) : '';
  const left = [
    chalk.dim('Ctrl+R') + chalk.dim.italic(' parler'),
    chalk.dim('/attach') + chalk.dim.italic(' <img>'),
    chalk.dim('/help'),
  ].join(chalk.dim('  ·  '));
  const inner = left + img;
  // Largeur visible (sans ANSI) pour la bordure
  const visLen = stripAnsi(inner).length;
  const fill = Math.max(0, cols - 4 - visLen);
  process.stdout.write(
    chalk.dim('  ╭' + '─'.repeat(cols - 4) + '╮\n') +
    chalk.dim('  │ ') + inner + ' '.repeat(fill) + chalk.dim(' │\n') +
    chalk.dim('  ╰' + '─'.repeat(cols - 4) + '╯\n'),
  );
}

/** Retire les séquences ANSI d'une chaîne pour mesurer la longueur visible. */
function stripAnsi(str: string): string {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1b\[[0-9;]*[mGKHF]/g, '').replace(/\x1b\][^\x07]*\x07/g, '');
}

// ── Table des sessions ────────────────────────────────────────────────────

export function printSessionsTable(sessions: Array<Record<string, unknown>>): void {
  console.log(chalk.bold('\nSessions :'));
  for (const s of sessions.slice(0, 20)) {
    const id = String(s['id'] ?? '?').padEnd(6);
    const ts = String(s['timestamp'] ?? '').slice(0, 16).replace('T', ' ');
    const resume = String(s['resume'] ?? '—').slice(0, 60);
    console.log(`  ${chalk.cyan(id)}  ${chalk.dim(ts)}  ${resume}`);
  }
}

// ── Aide ──────────────────────────────────────────────────────────────────

export function printHelp(mode: string): void {
  console.log(`
${chalk.hex('#e7644f').bold('Slash commands :')}

  ${chalk.bold('/clear')}               Nouvelle session
  ${chalk.bold('/sessions')}            Lister les sessions et en changer
  ${chalk.bold('/history [N]')}         Afficher les N derniers messages (défaut: 10)
  ${chalk.bold('/export')}              Exporter la session en Markdown
  ${chalk.bold('/model [nom|list]')}    Changer de modèle, vide = auto, list = liste les dispo
  ${chalk.bold('/server [url]')}        Voir/changer le serveur backend (sauvegardé)
  ${chalk.bold('/permissions [mode]')}  Mode : ask | auto | plan (actuel: ${chalk.cyan(mode)})
  ${chalk.bold('/cwd [chemin]')}        Voir/changer le répertoire de travail
  ${chalk.bold('/attach <chemin>')}     Joindre une image au prochain message
  ${chalk.bold('/detach')}              Annuler l'image en attente
  ${chalk.bold('/voice')}               Enregistrer un message vocal (STT → agent)
  ${chalk.bold('/login')}               Se connecter avec un autre compte (puis relancer jh)
  ${chalk.bold('/logout')}              Se déconnecter
  ${chalk.bold('/help')}                Cette aide
  ${chalk.bold('/quit')} | ${chalk.bold('/exit')}        Quitter
`);
}
