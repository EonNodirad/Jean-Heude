import { json } from '@sveltejs/kit'
import type { RequestHandler } from './$types'


export const POST: RequestHandler = async ({ request }) => {
    // 1. Lire les donées evoyée par le frontend
    const message = await request.json()
    const messageRecu = message.content
    if (!messageRecu || messageRecu.trim() === "") {
        return json({ error: "message vide" }, { status: 400 })
    }
    //2 demande de l'IA
    let demande = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: messageRecu })
    })
    let reponseIA = await demande.json()
    return json({ reply: reponseIA.response });
}
