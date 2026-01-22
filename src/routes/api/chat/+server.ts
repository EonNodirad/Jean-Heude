import { json } from '@sveltejs/kit'
import type { RequestHandler } from './$types'


export const POST: RequestHandler = async ({ request }) => {
    // 1. Lire les donées evoyée par le frontend
    const { content, session_id } = await request.json()
    if (!content || content.trim() === "") {
        return json({ error: "message vide" }, { status: 400 })
    }
    //2 demande de l'IA
    let demande = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content, session_id: session_id })
    })
    let reponseIA = await demande.json()
    return json({ reply: reponseIA.response, session_id: reponseIA.session_id });
}

