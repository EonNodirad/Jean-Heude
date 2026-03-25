/**
 * Gestion du protocole clavier Kitty.
 * Kitty envoie des séquences d'échappement étendues (\x1b[9u, \x1b[13u…)
 * que Node.js readline interprète comme du texte brut.
 * Solution : désactiver le mode étendu avant chaque saisie, restaurer après.
 */

const isTTY = (process.stdout as NodeJS.WriteStream).isTTY;

/** Désactive le protocole clavier étendu de Kitty. */
export function disableKitty(): void {
  if (isTTY) process.stdout.write('\x1b[>0u');
}

/** Restaure le protocole clavier Kitty (pop la pile). */
export function restoreKitty(): void {
  if (isTTY) process.stdout.write('\x1b[<u');
}

/**
 * Pose une question en ligne en désactivant Kitty pendant la saisie.
 * Retourne la réponse de l'utilisateur.
 */
export function askLine(rl: import('readline').Interface, question: string): Promise<string> {
  return new Promise((resolve, reject) => {
    disableKitty();
    try {
      rl.question(question, (answer) => {
        restoreKitty();
        resolve(answer);
      });
    } catch (e) {
      restoreKitty();
      reject(e);
    }
  });
}

/**
 * Saisie de mot de passe (masquée) en désactivant Kitty.
 */
export function askPassword(question: string): Promise<string> {
  return new Promise((resolve) => {
    disableKitty();
    process.stdout.write(question);

    const stdin = process.stdin as NodeJS.ReadStream;
    if (stdin.isTTY) {
      stdin.setRawMode(true);
    }
    stdin.setEncoding('utf8');
    stdin.resume();

    let buf = '';
    const onData = (data: Buffer | string) => {
      const ch = data.toString();
      if (ch === '\r' || ch === '\n') {
        if (stdin.isTTY) stdin.setRawMode(false);
        stdin.pause();
        stdin.removeListener('data', onData);
        process.stdout.write('\n');
        restoreKitty();
        resolve(buf);
      } else if (ch === '\u0003') {
        // Ctrl+C
        process.exit(0);
      } else if (ch === '\u007f' || ch === '\b') {
        // Backspace
        if (buf.length > 0) buf = buf.slice(0, -1);
      } else if (ch.charCodeAt(0) >= 32) {
        // Ignorer les séquences d'échappement (commence par \x1b)
        if (!ch.startsWith('\x1b')) buf += ch;
      }
    };
    stdin.on('data', onData);
  });
}
