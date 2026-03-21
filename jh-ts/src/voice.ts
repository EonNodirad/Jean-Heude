/**
 * Enregistrement audio via arecord.
 * La transcription + réponse IA est gérée par le backend via /stt.
 */
import { spawn } from 'child_process';
import { readFileSync, unlinkSync, existsSync } from 'fs';
import chalk from 'chalk';

/**
 * Enregistre le micro et retourne le buffer WAV brut.
 */
export async function recordAudio(): Promise<Buffer> {
  const tmpFile = `/tmp/jh_voice_${process.pid}.wav`;

  if (existsSync(tmpFile)) unlinkSync(tmpFile);

  process.stdout.write(
    '\n' + chalk.red.bold('🎙 Enregistrement...') +
    chalk.dim(' (appuie sur Entrée pour arrêter)\n'),
  );

  const recorder = spawn('arecord', [
    '-f', 'S16_LE',
    '-r', '16000',
    '-c', '1',
    tmpFile,
  ], { stdio: 'ignore' });

  recorder.on('error', () => {
    process.stdout.write(chalk.red('✗ arecord introuvable. Installe alsa-utils.\n'));
  });

  await waitForEnter();
  recorder.kill('SIGTERM');
  await sleep(250);

  if (!existsSync(tmpFile)) {
    throw new Error('Aucun fichier audio enregistré (arecord a échoué ?)');
  }

  try {
    return readFileSync(tmpFile);
  } finally {
    try { unlinkSync(tmpFile); } catch { /* ignore */ }
  }
}

function waitForEnter(): Promise<void> {
  return new Promise((resolve) => {
    const stdin = process.stdin as NodeJS.ReadStream;

    const handler = (data: Buffer) => {
      const ch = data[0];
      // CR (13) ou LF (10) = Entrée
      if (ch === 13 || ch === 10) {
        stdin.removeListener('data', handler);
        if (stdin.isTTY) stdin.setRawMode(false);
        stdin.pause();
        resolve();
      }
    };

    if (stdin.isTTY) stdin.setRawMode(true);
    stdin.resume();
    stdin.on('data', handler);
  });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
