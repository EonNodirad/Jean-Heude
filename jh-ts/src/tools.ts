/**
 * Outils locaux exécutés côté client (machine de l'utilisateur).
 * Jean-Heude orchestre, le CLI exécute.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { readFile, writeFile, readdir } from 'fs/promises';
import { dirname, resolve, isAbsolute } from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { glob } from 'glob';

const execAsync = promisify(exec);

export interface ToolResult {
  output: string | null;
  error: string | null;
}

/** CWD de travail (peut être changé via --cwd) */
let workingDir = process.cwd();

export function setWorkingDir(dir: string): void {
  workingDir = resolve(dir);
}

export function getWorkingDir(): string {
  return workingDir;
}

/** Résout un chemin relatif au workingDir. Refuse les chemins absolus hors workingDir. */
function resolvePath(path: string): string {
  if (isAbsolute(path)) {
    const abs = resolve(path);
    if (!abs.startsWith(workingDir)) {
      throw new Error(`Accès refusé : chemin hors du répertoire de travail (${workingDir})`);
    }
    return abs;
  }
  return resolve(workingDir, path);
}

// ── read_file ──────────────────────────────────────────────────────────────

export async function readFile_(path: string): Promise<ToolResult> {
  try {
    const abs = resolvePath(path);
    const content = await readFile(abs, 'utf-8');
    return { output: content, error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

// ── write_file ─────────────────────────────────────────────────────────────

export async function writeFile_(path: string, content: string): Promise<ToolResult> {
  try {
    const abs = resolvePath(path);
    mkdirSync(dirname(abs), { recursive: true });
    await writeFile(abs, content, 'utf-8');
    const lines = content.split('\n').length;
    return { output: `Fichier écrit : ${abs} (${lines} lignes)`, error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

// ── edit_file ──────────────────────────────────────────────────────────────

export async function editFile(path: string, oldStr: string, newStr: string): Promise<ToolResult> {
  try {
    const abs = resolvePath(path);
    if (!existsSync(abs)) {
      return { output: null, error: `Fichier introuvable : ${path}` };
    }
    const content = await readFile(abs, 'utf-8');
    const occurrences = content.split(oldStr).length - 1;
    if (occurrences === 0) {
      return { output: null, error: `Chaîne introuvable dans ${path}` };
    }
    if (occurrences > 1) {
      return { output: null, error: `Ambiguïté : ${occurrences} occurrences trouvées. Fournir plus de contexte.` };
    }
    const updated = content.replace(oldStr, newStr);
    await writeFile(abs, updated, 'utf-8');
    return { output: `Fichier modifié : ${abs}`, error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

// ── glob_files ─────────────────────────────────────────────────────────────

export async function globFiles(pattern: string, dir?: string): Promise<ToolResult> {
  try {
    const cwd = dir ? resolvePath(dir) : workingDir;
    const files = await glob(pattern, { cwd, nodir: true });
    if (files.length === 0) {
      return { output: '(aucun fichier trouvé)', error: null };
    }
    return { output: files.sort().join('\n'), error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

// ── list_directory ─────────────────────────────────────────────────────────

export async function listDirectory(dir?: string): Promise<ToolResult> {
  try {
    const target = dir ? resolvePath(dir) : workingDir;
    const entries = await readdir(target, { withFileTypes: true });
    if (entries.length === 0) return { output: '(répertoire vide)', error: null };
    const lines = entries.map(e => `${e.isDirectory() ? 'd' : 'f'} ${e.name}`);
    return { output: lines.join('\n'), error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

// ── grep_files ─────────────────────────────────────────────────────────────

export async function grepFiles(pattern: string, path?: string, globPattern?: string): Promise<ToolResult> {
  try {
    const target = path ? resolvePath(path) : workingDir;
    const args = ['-rn', '--color=never', pattern];
    if (globPattern) args.push(`--include=${globPattern}`);
    args.push(target);

    const { stdout, stderr } = await execAsync(`grep ${args.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(' ')}`, {
      cwd: workingDir,
      timeout: 15_000,
    }).catch(err => {
      // grep exit code 1 = pas de match (pas une erreur)
      if (err.code === 1) return { stdout: '', stderr: '' };
      throw err;
    });

    const out = stdout.trim();
    if (!out) return { output: '(aucun résultat)', error: null };
    const lines = out.split('\n');
    const truncated = lines.length > 200 ? lines.slice(0, 200).join('\n') + `\n... (${lines.length - 200} lignes supplémentaires)` : out;
    return { output: truncated, error: stderr || null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

// ── run_bash ───────────────────────────────────────────────────────────────

export async function runBash(command: string, timeoutMs: number = 30_000): Promise<ToolResult> {
  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd: workingDir,
      timeout: timeoutMs,
      maxBuffer: 10 * 1024 * 1024,
    });
    const out = [stdout, stderr].filter(Boolean).join('\n').trim();
    return { output: out || '(commande terminée sans sortie)', error: null };
  } catch (e: unknown) {
    const err = e as { stdout?: string; stderr?: string; message?: string };
    const out = [err.stdout, err.stderr].filter(Boolean).join('\n').trim();
    return { output: out || null, error: err.message ?? String(e) };
  }
}

// ── Dispatcher ────────────────────────────────────────────────────────────

export type ToolName =
  | 'client_read_file'
  | 'client_write_file'
  | 'client_edit_file'
  | 'client_glob_files'
  | 'client_grep_files'
  | 'client_list_directory'
  | 'client_run_bash';

export const DESTRUCTIVE_TOOLS: ToolName[] = [
  'client_write_file',
  'client_edit_file',
  'client_run_bash',
];

export function isDestructive(name: string): boolean {
  return DESTRUCTIVE_TOOLS.includes(name as ToolName);
}

export async function execute(name: string, args: Record<string, unknown>): Promise<ToolResult> {
  switch (name) {
    case 'client_read_file':
      return readFile_(args.path as string);
    case 'client_write_file':
      return writeFile_(args.path as string, args.content as string);
    case 'client_edit_file':
      return editFile(args.path as string, args.old_str as string, args.new_str as string);
    case 'client_glob_files':
      return globFiles(args.pattern as string, args.dir as string | undefined);
    case 'client_grep_files':
      return grepFiles(
        args.pattern as string,
        args.path as string | undefined,
        args.glob as string | undefined,
      );
    case 'client_list_directory':
      return listDirectory(args.dir as string | undefined);
    case 'client_run_bash':
      return runBash(args.command as string, args.timeout_ms as number | undefined);
    default:
      return { output: null, error: `Outil inconnu : ${name}` };
  }
}
