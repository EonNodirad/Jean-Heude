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
  // Remonter au début du bloc de réponse pour le remplacer
  const lines = text.split('\n').length;
  process.stdout.write(`\x1b[${lines}A\x1b[J`);
  const rendered = marked(text) as string;
  process.stdout.write(rendered);
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

// ── Bannière ──────────────────────────────────────────────────────────────

export function printBanner(userId: string, server: string, model: string = ''): void {
  process.stdout.write(
    chalk.hex('#e7644f').bold('J.E.A.N-H.E.U.D.E') +
    chalk.dim(` — ${userId} @ ${server}`) +
    (model ? chalk.dim.cyan(`  (${model})`) : '') +
    '\n',
  );
  process.stdout.write(chalk.dim('Tape ') + chalk.dim.bold('/help') + chalk.dim(' pour les commandes, Ctrl+D pour quitter.\n\n'));
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
  ${chalk.bold('/model [nom|list]')}     Changer de modèle, vide = auto, list = liste les modèles dispo
  ${chalk.bold('/server [url]')}        Voir/changer l'URL du serveur (ex: http://192.168.1.10:8000)
  ${chalk.bold('/history [N]')}         Afficher les N derniers messages (défaut: 10)
  ${chalk.bold('/export')}              Exporter la session en Markdown
  ${chalk.bold('/permissions [mode]')}  Mode : ask | auto | plan (actuel: ${chalk.cyan(mode)})
  ${chalk.bold('/cwd [chemin]')}        Voir/changer le répertoire de travail
  ${chalk.bold('/help')}                Cette aide
  ${chalk.bold('/quit')} | ${chalk.bold('/exit')}        Quitter
`);
}
