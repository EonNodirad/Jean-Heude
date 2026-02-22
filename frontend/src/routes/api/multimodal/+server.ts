import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const POST: RequestHandler = async ({ request, fetch }) => {
    try {
        // 1. On intercepte le FormData envoyé par ton +page.svelte (qui contient l'image et le prompt)
        const formData = await request.formData();

        // 2. On le transfère tel quel à ton serveur Python (Jean-Heude)
        const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/multimodal`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Erreur backend Python: ${response.statusText}`);
        }

        // 3. On renvoie le flux (Stream) continu au navigateur
        // pour que la réponse s'écrive lettre par lettre
        return new Response(response.body, {
            headers: {
                'Content-Type': 'text/plain',
                // On n'oublie pas de faire passer les headers de session pour l'historique !
                'X-Session-Id': response.headers.get('x-session-id') || '',
                'X-Chosen-Model': response.headers.get('x-chosen-model') || ''
            }
        });
    } catch (err) {
        console.error('❌ Erreur Proxy Multimodal:', err);
        throw error(500, 'Erreur lors de la communication visuelle avec Jean-Heude');
    }
};
