import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const GET: RequestHandler = async ({ params, fetch }) => {
    const { id } = params;

    try {
        // SvelteKit (côté serveur) peut appeler http://backend:8000 s'il est dans Docker,
        // ou localhost:8000 s'il est lancé normalement.
        const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/tts/${id}`);

        if (!response.ok) {
            throw new Error(`Le backend a renvoyé ${response.status}`);
        }

        // On renvoie le flux binaire directement à l'AudioContext du client
        return new Response(response.body, {
            headers: {
                'Content-Type': 'application/octet-stream',
                'Cache-Control': 'no-cache'
            }
        });
    } catch (err) {
        console.error('❌ Erreur Proxy TTS:', err);
        throw error(500, 'Impossible de récupérer le flux audio');
    }
};
