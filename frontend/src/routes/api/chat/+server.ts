import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const POST: RequestHandler = async ({ request }) => {
	// 1. Lire les donées evoyée par le frontend
	const { content, session_id } = await request.json();
	if (!content || content.trim() === '') {
		return json({ error: 'message vide' }, { status: 400 });
	}
	//2 demande de l'IA
	const demande = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/chat`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ content: content, session_id: session_id })
	});
	const session = demande.headers.get('x-session-id');
	const model = demande.headers.get('x-chosen-model');
	const nouvHeader = new Headers();
	nouvHeader.set('Content-Type', 'text/plain');
	if (session) {
		nouvHeader.set('x-session-id', session);
	}
	if (model) {
		nouvHeader.set('x-chosen-model', model);
	}
	const myOption = { status: demande.status, statusText: demande.statusText, headers: nouvHeader };
	const response = new Response(demande.body, myOption);
	if (!demande.ok) {
		console.error(`[Serveur Python] Erreur ${demande.status}: ${demande.statusText}`);
	}
	return response;
};
