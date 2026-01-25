import { json } from '@sveltejs/kit';
import { PUBLIC_URL_SERVEUR_PYTHON } from '$env/static/public';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
	try {
		const response = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/history`);
		if (!response.ok) {
			return json({ error: "Impossible de charger l'historique" }, { status: 500 });
		}
		const data = await response.json();
		return json(data);
	} catch {
		return json({ error: 'Connexion au serveur Python échouée' }, { status: 500 });
	}
};
