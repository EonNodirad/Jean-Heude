import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { PUBLIC_URL_SERVEUR_PYTHON } from '$env/static/public';

export const POST: RequestHandler = async ({ request }) => {
	// 1. Lire les donées evoyée par le frontend
	const { content, session_id } = await request.json();
	if (!content || content.trim() === '') {
		return json({ error: 'message vide' }, { status: 400 });
	}
	//2 demande de l'IA
	const demande = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/chat`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ content: content, session_id: session_id })
	});
	const reponseIA = await demande.json();
	return json({ reply: reponseIA.response, session_id: reponseIA.session_id });
};
