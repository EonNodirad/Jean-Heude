import { json } from "@sveltejs/kit";
import { P as PUBLIC_URL_SERVEUR_PYTHON } from "../../../../chunks/public.js";
const POST = async ({ request }) => {
  const { content, session_id } = await request.json();
  if (!content || content.trim() === "") {
    return json({ error: "message vide" }, { status: 400 });
  }
  const demande = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, session_id })
  });
  const reponseIA = await demande.json();
  return json({ reply: reponseIA.response, session_id: reponseIA.session_id });
};
export {
  POST
};
