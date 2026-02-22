import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const GET: RequestHandler = async ({ params, fetch }) => {
    // 1. On récupère le nom du fichier depuis l'URL (ex: 1234-abcd.jpg)
    const fileName = params.file;

    if (!fileName) {
        throw error(400, 'Nom de fichier manquant');
    }

    try {
        // 2. On va chercher l'image sur le serveur Python en secret
        const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/uploads/${fileName}`);

        if (!response.ok) {
            throw error(response.status, 'Image introuvable sur le backend Jean-Heude');
        }

        // 3. On renvoie le fichier brut au navigateur
        return new Response(response.body, {
            headers: {
                // On garde le bon type (ex: image/jpeg)
                'Content-Type': response.headers.get('Content-Type') || 'image/jpeg',
                // Petite optimisation : on dit au navigateur de garder l'image en cache !
                'Cache-Control': 'public, max-age=86400'
            }
        });
    } catch (err) {
        console.error('❌ Erreur Proxy Image:', err);
        throw error(500, 'Erreur de communication avec le serveur d\'images');
    }
};
