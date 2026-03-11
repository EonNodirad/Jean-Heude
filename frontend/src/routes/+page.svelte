<script lang="ts">
    import { onMount } from 'svelte';
    import Sidebar from '$lib/components/Sidebar.svelte';
    import ChatContainer from '$lib/components/ChatContainer.svelte';
    import ModelToast from '$lib/components/ModelToast.svelte';

    import { createRecorder } from '$lib/voice.svelte';
    import { connectGateway } from '$lib/websocket.svelte';

    import { currentUser, authToken } from '$lib/stores';
    import { goto } from '$app/navigation';
    
    // 🎯 Création et instanciation du store de Chat
    import { createChatStore } from '$lib/chat.svelte';
    const chat = createChatStore();

    const recorder = createRecorder({
        getSessionId: () => chat.sessionActive,
        getUserId: () => $currentUser || '',
        getToken: () => $authToken || '',
        onTranscriptionStart: () => {
            chat.attente = true;
            chat.messages = [{ role: 'assistant', think: '', content: '', status: 'Transcription...' }, ...chat.messages];
        },
        onStream: (think, content, status) => {
            chat.messages[0].think = think;
            chat.messages[0].content = content;
            chat.messages[0].status = status;
        },
        onEnd: () => {
            chat.attente = false;
            chat.rafraichirSession();
        },
        onModelChosen: (model) => {
            chat.modelChoisi = model; // TypeScript va l'ignorer ici si "modelChoisi" n'est pas bindable direct, on va plutôt l'utiliser en l'attribuant 
            chat.voirModel = true;
            setTimeout(() => (chat.voirModel = false), 3000);
        },
        onSessionCreated: (id) => (chat.sessionActive = id)
    });

    onMount(async () => {
        // 🔒 REDIRECTION SI NON CONNECTÉ
        if (!$currentUser || !$authToken) {
            goto('/login');
            return;
        }

        await chat.rafraichirSession();
        
        // 🔌 ON CONNECTE LE WEBSOCKET AVEC LE VRAI PSEUDO
        connectGateway($currentUser); 
    });

    $effect(() => {
        chat.syncWithWebSocket();
    });
</script>

<div class="container-global">
    <Sidebar 
        historiques={chat.historiques} 
        sessionActive={chat.sessionActive} 
        onLoadConversation={chat.ChargerConversation} 
    />

    <ChatContainer 
        messages={chat.messages}
        bind:currentMessage={chat.currentMessage}
        attente={chat.attente}
        recorder={recorder}
        onSendMessage={chat.sendMessage}
        onNewChat={chat.nouveauChat}
        onFileSelect={(file, url) => {
            chat.selectedFile = file;
            chat.previewUrl = url;
        }}
        onClearImage={() => {
            chat.selectedFile = null;
            chat.previewUrl = null;
        }}
        previewUrl={chat.previewUrl}
    />

    <ModelToast voirModel={chat.voirModel} modelChoisi={chat.modelChoisi} />
</div>

<style>
    :global(body) {
        margin: 0;
        padding: 0;
        overflow: hidden;
    }

    * {
        box-sizing: border-box;
    }

    .container-global {
        display: flex;
        height: 100vh;
        width: 100%;
        background-color: #1a2238;
        font-family: sans-serif;
    }
</style>
