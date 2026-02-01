import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';
import { error } from 'console';

export const GET: RequestHandler = async ({ url }) => {

    const text = url.searchParams.get('text');
    if (!text) {
        throw error(400, 'Texte manquant');
    }
    try {
        // On appelle ton backend Python (FastAPI)
        const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/tts?text=${encodeURIComponent(text)}`);

        if (!response.ok) {
            throw new Error('Erreur backend Python');
        }

        // On récupère le flux binaire (WAV)
        const audioBuffer = await response.arrayBuffer();

        // On le renvoie tel quel au frontend
        return new Response(audioBuffer, {
            headers: {
                'Content-Type': 'audio/wav',
                'Cache-Control': 'no-cache'
            }
        });
    } catch (err) {
        console.error('Erreur proxy TTS:', err);
        throw error(500, 'Impossible de générer l\'audio');
    }
};
