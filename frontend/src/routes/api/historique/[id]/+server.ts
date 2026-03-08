import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { env } from '$env/dynamic/public';

export const GET: RequestHandler = async ({ params, url }) => { // 🎯 Ajout de 'url' ici
    // SvelteKit récupère automatiquement l'ID du dossier [id]
    const { id } = params;
    
    // 🎯 Récupération du user_id passé par le frontend
    const userId = url.searchParams.get('user_id');

    if (!userId) {
        return json({ error: 'Le paramètre user_id est requis' }, { status: 400 });
    }

    try {
        // 🎯 On ajoute ?user_id=... à l'URL de Python
        const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/history/${id}?user_id=${userId}`);

        if (!response.ok) {
            return json({ error: 'Conversation introuvable' }, { status: 404 });
        }

        const data = await response.json();
        return json(data);
    } catch {
        return json({ error: 'Erreur de connexion au serveur Python' }, { status: 500 });
    }
};