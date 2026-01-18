import { json } from '@sveltejs/kit'
import type { RequestHandler } from './$types'


export const POST: RequestHandler = async ({ request }) => {
    // 1. Lire les donées evoyée par le frontend
    const message = await request.json()
    const messageRecu = message.content
    if (!messageRecu || messageRecu.trim() === "") {
        return json({ error: "message vide" }, { status: 400 })
    }

    return json({ reply: 'message bien reçu par le serveur' });
}
