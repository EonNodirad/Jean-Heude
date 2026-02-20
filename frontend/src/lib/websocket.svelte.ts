import { env } from '$env/dynamic/public';

export const chatState = $state({
    isConnected: false,
    isThinking: false,
    thinkStream: "",    // Flux des pensées
    contentStream: "",  // Flux du texte final
    sessionId: null as number | null,
    model: "",
    doneTrigger: 0
});

let ws: WebSocket | null = null;

export function connectGateway(clientId: string = "tauri_desktop") {
    const serverUrl = env.PUBLIC_URL_SERVEUR_PYTHON;
    if (!serverUrl) {
        console.error("❌ ERREUR : L'URL du serveur Python est introuvable !");
        return;
    }

    const wsUrl = serverUrl.replace(/^http/, 'ws');
    console.log("👉 URL finale générée :", wsUrl);
    ws = new WebSocket(`${wsUrl}/ws/${clientId}`);

    ws.onopen = () => {
        console.log("✅ Connecté à la Gateway Jean-Heude !");
        chatState.isConnected = true;
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "token") {
            let chunk = data.content;

            // 1. Si le morceau contient ¶ -> C'est une pensée !
            if (chunk.includes("¶")) {
                // On nettoie le ¶ pour l'affichage et on l'ajoute aux pensées
                chatState.thinkStream += chunk.replace(/¶/g, "");
            }
            // 2. Sinon -> C'est la réponse finale !
            else {
                // On retire les balises audio et on l'ajoute au contenu
                const cleanChunk = chunk.replace(/\|\|AUDIO_ID:.*?\|\|/g, "");
                chatState.contentStream += cleanChunk;
            }
        }
        else if (data.type === "done") {
            console.log("✅ Génération terminée !");
            chatState.isThinking = false;
            chatState.sessionId = data.session_id;
            chatState.model = data.model;
            chatState.doneTrigger += 1;
        }
    };

    ws.onclose = () => {
        console.log("❌ Déconnecté de la Gateway.");
        chatState.isConnected = false;
    };

    ws.onerror = (error) => {
        console.error("⚠️ Erreur WebSocket :", error);
    };
}

export function sendMessage(content: string) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.error("Impossible d'envoyer le message : WebSocket non connecté.");
        return;
    }

    chatState.isThinking = true;
    chatState.thinkStream = "";
    chatState.contentStream = "";

    ws.send(JSON.stringify({
        type: "message",
        content: content,
        session_id: chatState.sessionId
    }));
}
