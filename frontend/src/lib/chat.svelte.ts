import { env } from '$env/dynamic/public';
import { get } from 'svelte/store';
import { handleStream } from '$lib/lecture_reponse';
import { connectGateway, sendMessage as sendWsMessage, chatState } from '$lib/websocket.svelte';
import { currentUser, authToken } from '$lib/stores';

const API_URL = env.PUBLIC_URL_SERVEUR_PYTHON || 'http://localhost:8000';

export interface Message {
    role: string;
    think: string;
    content: string;
    status: string;
    image?: string | null;
}

export interface Historique {
    id: number;
    resume: string;
}

export function createChatStore() {
    let messages = $state<Message[]>([
        {
            role: 'assistant',
            think: '',
            content: 'Salut ! je suis ton assistant J.E.A.N-H.E.U.D.E',
            image: '',
            status: ''
        }
    ]);
    let sessionActive = $state<number | null>(null);
    let historiques = $state<Historique[]>([]);
    let modelChoisi = $state('');
    let voirModel = $state(false);
    let currentMessage = $state('');
    let attente = $state(false);
    let selectedFile = $state<File | null>(null);
    let previewUrl = $state<string | null>(null);

    async function rafraichirSession() {
        const user = get(currentUser);
        const token = get(authToken);
        if (!user || !token) return;

        const h = await fetch(`${API_URL}/history`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (h.ok) {
            historiques = await h.json();
        }
    }

    async function sendMessageContent(e: Event | null, file: File | null) {
        if (e) e.preventDefault();
        if (currentMessage.trim() === '' && !file) return;

        attente = true;
        const promptFinall = currentMessage || (previewUrl ? 'Décris cette image.' : '');
        const imageAffiche = previewUrl;

        messages = [{ role: 'user', think: '', content: promptFinall, image: imageAffiche, status: '' }, ...messages];
        messages = [{ role: 'assistant', think: '', content: '', status: 'Analyse en cours...' }, ...messages];

        const promptToSend = currentMessage;
        const fileToSend = file;

        currentMessage = '';
        selectedFile = null;
        previewUrl = null;

        const user = get(currentUser);
        const token = get(authToken);

        if (fileToSend) {
            console.log('🚀 Envoi multimodal via HTTP...');
            const formData = new FormData();
            formData.append('prompt', promptToSend || 'Décris cette image.');
            formData.append('image', fileToSend);
            formData.append('user_id', user || '');

            if (sessionActive) formData.append('session_id', sessionActive.toString());

            try {
                const response = await fetch(`${API_URL}/api/multimodal`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                    body: formData
                });

                const newSessionId = response.headers.get('x-session-id');
                if (newSessionId) sessionActive = parseInt(newSessionId);

                const reader = response.body?.getReader();
                if (reader) {
                    await handleStream(reader, (think, content, status) => {
                        messages[0].think = think;
                        messages[0].content = content;
                        messages[0].status = status;
                    });
                }
            } catch (err) {
                console.error('Erreur envoi image:', err);
                messages[0].content = "Erreur lors de l'envoi de l'image.";
            } finally {
                attente = false;
                rafraichirSession();
            }
        } else {
            console.log('🚀 Envoi texte via WebSocket...');
            chatState.sessionId = sessionActive;
            sendWsMessage(promptToSend);
        }
    }

    async function ChargerConversation(id: number) {
        if (attente) return;
        sessionActive = id;
        chatState.sessionId = id;
        
        const token = get(authToken);

        const res = await fetch(`${API_URL}/history/${id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            messages = data.map((msg: any) => {
                let imageFinale = null;
                if (msg.image) imageFinale = API_URL + msg.image;

                return {
                    role: msg.role,
                    content: msg.content,
                    think: '',
                    status: '',
                    image: imageFinale
                };
            }).reverse();
        }
    }

    function nouveauChat() {
        sessionActive = null;
        const user = get(currentUser);
        messages = [
            {
                role: 'assistant',
                think: '',
                content: `Nouvelle discussion ! Comment puis-je t'aider ${user} ?`,
                status: ''
            }
        ];
    }

    // Effect logic to sync with generic websocket chatState 
    // This is a function that should be called in an $effect inside a svelte component
    function syncWithWebSocket() {
        if (chatState.isThinking && messages[0] && messages[0].role === 'assistant') {
            messages[0].think = chatState.thinkStream;
            messages[0].content = chatState.contentStream;
            messages[0].status = chatState.contentStream.length > 0 ? 'Génération de la réponse...' : 'Jean-Heude réfléchit...';
        }

        if (chatState.doneTrigger > 0) {
            attente = false;
            if (chatState.sessionId) sessionActive = chatState.sessionId;
            if (chatState.model) {
                modelChoisi = chatState.model;
                voirModel = true;
                setTimeout(() => (voirModel = false), 3000);
            }
            rafraichirSession();
            chatState.doneTrigger = 0;
        }
    }

    return {
        get messages() { return messages; },
        set messages(val) { messages = val; },
        get sessionActive() { return sessionActive; },
        set sessionActive(val) { sessionActive = val; },
        get historiques() { return historiques; },
        get modelChoisi() { return modelChoisi; },
        set modelChoisi(val) { modelChoisi = val; },
        get voirModel() { return voirModel; },
        set voirModel(val) { voirModel = val; },
        get currentMessage() { return currentMessage; },
        set currentMessage(val) { currentMessage = val; },
        get attente() { return attente; },
        set attente(val) { attente = val; },
        get selectedFile() { return selectedFile; },
        set selectedFile(val) { selectedFile = val; },
        get previewUrl() { return previewUrl; },
        set previewUrl(val) { previewUrl = val; },
        
        rafraichirSession,
        sendMessage: sendMessageContent,
        ChargerConversation,
        nouveauChat,
        syncWithWebSocket
    };
}
