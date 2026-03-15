import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const GET: RequestHandler = async ({ params, request }) => {
	const auth = request.headers.get('Authorization');
	if (!auth) return json({ error: 'Non authentifié' }, { status: 401 });
	try {
		const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/files/${params.path}`, {
			headers: { Authorization: auth }
		});
		const data = await response.json();
		return json(data, { status: response.status });
	} catch {
		return json({ error: 'Connexion au serveur Python échouée' }, { status: 500 });
	}
};

export const PUT: RequestHandler = async ({ params, request }) => {
	const auth = request.headers.get('Authorization');
	if (!auth) return json({ error: 'Non authentifié' }, { status: 401 });
	try {
		const body = await request.json();
		const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/files/${params.path}`, {
			method: 'PUT',
			headers: { Authorization: auth, 'Content-Type': 'application/json' },
			body: JSON.stringify(body)
		});
		const data = await response.json();
		return json(data, { status: response.status });
	} catch {
		return json({ error: 'Connexion au serveur Python échouée' }, { status: 500 });
	}
};

export const POST: RequestHandler = async ({ params, request }) => {
	const auth = request.headers.get('Authorization');
	if (!auth) return json({ error: 'Non authentifié' }, { status: 401 });
	try {
		const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/files/${params.path}`, {
			method: 'POST',
			headers: { Authorization: auth }
		});
		const data = await response.json();
		return json(data, { status: response.status });
	} catch {
		return json({ error: 'Connexion au serveur Python échouée' }, { status: 500 });
	}
};

export const DELETE: RequestHandler = async ({ params, request }) => {
	const auth = request.headers.get('Authorization');
	if (!auth) return json({ error: 'Non authentifié' }, { status: 401 });
	try {
		const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/files/${params.path}`, {
			method: 'DELETE',
			headers: { Authorization: auth }
		});
		const data = await response.json();
		return json(data, { status: response.status });
	} catch {
		return json({ error: 'Connexion au serveur Python échouée' }, { status: 500 });
	}
};
