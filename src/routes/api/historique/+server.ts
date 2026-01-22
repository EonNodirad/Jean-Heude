import { json } from '@sveltejs/kit'
import type { RequestHandler } from './$types'

export const GET: RequestHandler = async () => {
    try {
        const response = await fetch('http://localhost:8000/history')
        if (!response.ok) {
            return json({ error: "Impossible de charger l'historique" }, { status: 500 });
        }
        const data = await response.json();
        return json(data)
    }
    catch (error) {
        return json({ error: "Connexion au serveur Python échouée" }, { status: 500 });
    }
};


