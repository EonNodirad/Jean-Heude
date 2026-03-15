import { json } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url }) => {
	// 🎯 Ajout de 'url' ici
	// 🎯 Récupération du user_id passé par le frontend
	const userId = url.searchParams.get('user_id');

	if (!userId) {
		return json({ error: 'Le paramètre user_id est requis' }, { status: 400 });
	}

	try {
		// 🎯 On ajoute ?user_id=... à l'URL de Python
		const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/history?user_id=${userId}`);

		if (!response.ok) {
			return json({ error: "Impossible de charger l'historique" }, { status: 500 });
		}
		const data = await response.json();
		return json(data);
	} catch {
		return json({ error: 'Connexion au serveur Python échouée' }, { status: 500 });
	}
};
