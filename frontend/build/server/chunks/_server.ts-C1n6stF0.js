import { j as json } from './index-CoD1IJuy.js';
import { P as PUBLIC_URL_SERVEUR_PYTHON } from './public-DHts6zr1.js';

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

export { POST };
//# sourceMappingURL=_server.ts-C1n6stF0.js.map
