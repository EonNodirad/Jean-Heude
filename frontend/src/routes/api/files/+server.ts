import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const GET: RequestHandler = async ({ request }) => {
	const auth = request.headers.get('Authorization');
	if (!auth) {
		return json({ error: 'Non authentifié' }, { status: 401 });
	}
	try {
		const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/files`, {
			headers: { Authorization: auth }
		});
		const data = await response.json();
		return json(data, { status: response.status });
	} catch {
		return json({ error: 'Connexion au serveur Python échouée' }, { status: 500 });
	}
};
