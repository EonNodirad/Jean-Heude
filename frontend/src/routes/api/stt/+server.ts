import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request, fetch }) => {
	try {
		// 1. On récupère le FormData envoyé par le client (Svelte)
		const formData = await request.formData();

		// 2. On le renvoie tel quel vers ton backend FastAPI (Jean-Heude principal)
		// Note : On utilise l'URL de ton iaserveur ou localhost:8000
		const response = await fetch('http://localhost:8000/stt', {
			method: 'POST',
			body: formData
		});

		if (!response.ok) {
			throw new Error(`Erreur backend: ${response.statusText}`);
		}

		// 3. On renvoie le flux (Stream) directement au client
		// Cela permet de voir Jean-Heude écrire sa réponse en direct
		return new Response(response.body, {
			headers: {
				'Content-Type': 'text/plain',
				// On transmet les headers importants (Session ID, Model)
				'X-Session-Id': response.headers.get('x-session-id') || '',
				'X-Chosen-Model': response.headers.get('x-chosen-model') || ''
			}
		});
	} catch (err) {
		console.error('Erreur Proxy STT:', err);
		throw error(500, 'Erreur lors de la communication avec Jean-Heude');
	}
};
