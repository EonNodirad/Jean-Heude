import { json } from "@sveltejs/kit";
import { P as PUBLIC_URL_SERVEUR_PYTHON } from "../../../../chunks/public.js";
const GET = async () => {
  try {
    const response = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/history`);
    if (!response.ok) {
      return json({ error: "Impossible de charger l'historique" }, { status: 500 });
    }
    const data = await response.json();
    return json(data);
  } catch {
    return json({ error: "Connexion au serveur Python échouée" }, { status: 500 });
  }
};
export {
  GET
};
