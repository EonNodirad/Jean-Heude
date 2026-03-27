/**
 * Point d'entrée de l'extension VS Code Jean-Heude.
 */
import * as vscode from 'vscode';
import { loadCredentials, loadServerUrl, isTokenExpired } from './auth.js';
import { JHChatViewProvider, DiffContentProvider } from './panel.js';

export function activate(context: vscode.ExtensionContext): void {
  // Provider de contenu in-memory pour les diffs
  const diffProvider = new DiffContentProvider();
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(DiffContentProvider.scheme, diffProvider),
  );

  // Charger les credentials (peut être null → l'utilisateur loginera via /login)
  const creds = loadCredentials();
  const serverUrl = creds?.server_url ?? loadServerUrl();

  // Si les credentials sont expirés, on les ignore mais on garde l'URL serveur
  const validCreds = (creds && !isTokenExpired(creds.token)) ? creds : null;
  if (!validCreds) {
    vscode.window.showWarningMessage(
      'Jean-Heude : non connecté. Tape /login dans le chat pour te connecter.',
    );
  }

  // Toujours enregistrer le provider (même sans credentials)
  const provider = new JHChatViewProvider(context.extensionUri, validCreds, serverUrl, diffProvider);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('jh.chatView', provider, {
      webviewOptions: { retainContextWhenHidden: true },
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('jh.openPanel', () => {
      vscode.commands.executeCommand('jh.chatView.focus');
    }),
  );
}

export function deactivate(): void {}
