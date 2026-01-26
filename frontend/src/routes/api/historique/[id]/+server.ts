import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const GET: RequestHandler = async ({ params }) => {
	// SvelteKit récupère automatiquement l'ID du dossier [id]
	const { id } = params;

	try {
		// Le serveur SvelteKit parle au serveur Python (pas de CORS ici !)
		const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/history/${id}`);

		if (!response.ok) {
			return json({ error: 'Conversation introuvable' }, { status: 404 });
		}

		const data = await response.json();
		return json(data);
	} catch {
		return json({ error: 'Erreur de connexion au serveur Python' }, { status: 500 });
	}
};
