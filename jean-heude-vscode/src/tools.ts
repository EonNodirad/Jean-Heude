/**
 * Outils locaux exécutés côté extension VS Code.
 * Adapté depuis jh-ts/src/tools.ts.
 * write_file et edit_file exposent aussi des fonctions "preview" pour le diff VS Code.
 */
import { readFileSync, existsSync } from 'fs';
import { readFile, writeFile, readdir, mkdir } from 'fs/promises';
import { dirname, resolve, isAbsolute, basename } from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { glob } from 'glob';

const execAsync = promisify(exec);

export interface ToolResult {
  output: string | null;
  error: string | null;
}

export interface WritePreview {
  absPath: string;
  fileName: string;
  originalContent: string;
  newContent: string;
  isNewFile: boolean;
}

let workingDir = process.cwd();

export function setWorkingDir(dir: string): void {
  workingDir = resolve(dir);
}

export function getWorkingDir(): string {
  return workingDir;
}

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

// ── Fonctions preview (sans écriture) ────────────────────────────────────────

export function previewWriteFile(path: string, content: string): WritePreview {
  const absPath = resolvePath(path);
  const isNewFile = !existsSync(absPath);
  const originalContent = isNewFile ? '' : readFileSync(absPath, 'utf-8');
  return { absPath, fileName: basename(absPath), originalContent, newContent: content, isNewFile };
}

export function previewEditFile(
  path: string,
  oldStr: string,
  newStr: string,
): WritePreview | { error: string } {
  const absPath = resolvePath(path);
  if (!existsSync(absPath)) {
    return { error: `Fichier introuvable : ${path}` };
  }
  const original = readFileSync(absPath, 'utf-8');
  const occurrences = original.split(oldStr).length - 1;
  if (occurrences === 0) return { error: `Chaîne introuvable dans ${path}` };
  if (occurrences > 1) return { error: `Ambiguïté : ${occurrences} occurrences trouvées` };
  const newContent = original.replace(oldStr, newStr);
  return { absPath, fileName: basename(absPath), originalContent: original, newContent, isNewFile: false };
}

export async function applyWrite(absPath: string, content: string): Promise<ToolResult> {
  try {
    await mkdir(dirname(absPath), { recursive: true });
    await writeFile(absPath, content, 'utf-8');
    const lines = content.split('\n').length;
    return { output: `Fichier écrit : ${absPath} (${lines} lignes)`, error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

// ── Outils directs (lecture, glob, grep, bash) ────────────────────────────────

async function readFile_(path: string): Promise<ToolResult> {
  try {
    const abs = resolvePath(path);
    const content = await readFile(abs, 'utf-8');
    return { output: content, error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

async function globFiles(pattern: string, dir?: string): Promise<ToolResult> {
  try {
    const cwd = dir ? resolvePath(dir) : workingDir;
    const files = await glob(pattern, { cwd, nodir: true });
    if (files.length === 0) return { output: '(aucun fichier trouvé)', error: null };
    return { output: files.sort().join('\n'), error: null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

async function listDirectory(dir?: string): Promise<ToolResult> {
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

async function grepFiles(pattern: string, path?: string, globPattern?: string): Promise<ToolResult> {
  try {
    const target = path ? resolvePath(path) : workingDir;
    const args = ['-rn', '--color=never', pattern];
    if (globPattern) args.push(`--include=${globPattern}`);
    args.push(target);

    const { stdout, stderr } = await execAsync(
      `grep ${args.map(a => `'${a.replace(/'/g, "'\\''")}'`).join(' ')}`,
      { cwd: workingDir, timeout: 15_000 },
    ).catch(err => {
      if (err.code === 1) return { stdout: '', stderr: '' };
      throw err;
    });

    const out = stdout.trim();
    if (!out) return { output: '(aucun résultat)', error: null };
    const lines = out.split('\n');
    const truncated = lines.length > 200
      ? lines.slice(0, 200).join('\n') + `\n... (${lines.length - 200} lignes supplémentaires)`
      : out;
    return { output: truncated, error: stderr || null };
  } catch (e) {
    return { output: null, error: String(e) };
  }
}

async function runBash(command: string, timeoutMs: number = 30_000): Promise<ToolResult> {
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

// ── Dispatcher (outils non-destructifs uniquement) ────────────────────────────

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

/** Exécute un outil NON-destructif. Pour write/edit, utiliser previewWriteFile/applyWrite. */
export async function executeReadOnly(name: string, args: Record<string, unknown>): Promise<ToolResult> {
  switch (name) {
    case 'client_read_file':
      return readFile_(args.path as string);
    case 'client_glob_files':
      return globFiles(args.pattern as string, args.dir as string | undefined);
    case 'client_grep_files':
      return grepFiles(args.pattern as string, args.path as string | undefined, args.glob as string | undefined);
    case 'client_list_directory':
      return listDirectory(args.dir as string | undefined);
    default:
      return { output: null, error: `executeReadOnly: outil non supporté ici : ${name}` };
  }
}

export async function executeBash(command: string, timeoutMs?: number): Promise<ToolResult> {
  return runBash(command, timeoutMs);
}
