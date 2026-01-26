import { j as json } from './index-CoD1IJuy.js';
import { P as PUBLIC_URL_SERVEUR_PYTHON } from './public-DHts6zr1.js';

const GET = async ({ params }) => {
  const { id } = params;
  try {
    const response = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/history/${id}`);
    if (!response.ok) {
      return json({ error: "Conversation introuvable" }, { status: 404 });
    }
    const data = await response.json();
    return json(data);
  } catch {
    return json({ error: "Erreur de connexion au serveur Python" }, { status: 500 });
  }
};

export { GET };
//# sourceMappingURL=_server.ts-bgq0MB-r.js.map
