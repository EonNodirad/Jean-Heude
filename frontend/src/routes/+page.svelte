<script lang="ts">
	import { onMount } from 'svelte';
	import nouvelleDiscussion from '$lib/assets/nouvelle-discussion.svg';
	import { formatMessage } from '$lib/format';
	import 'highlight.js/styles/github-dark.css';
	import { fly } from 'svelte/transition';
	let messages = $state([
		{ role: 'assistant', content: 'Salut ! je suis ton assistant J.E.A.N-H.E.U.D.E' }
	]);
	let sessionActive = $state<number | null>(null);
	interface Historique {
		id: number;
		resume: string;
	}

	let historiques = $state<Historique[]>([]);

	let modelChoisi = $state('');
	let voirModel = $state(false);

	let currentMessage = $state('');
	let attente = $state(false);
	onMount(async () => {
		await rafraichirSession();
	});
	async function sendMessage(e: Event) {
		e.preventDefault();
		if (currentMessage.trim() === '') return;
		attente = true;
		messages = [{ role: 'user', content: currentMessage }, ...messages];

		let reponse = await fetch('/api/chat', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ content: currentMessage, session_id: sessionActive })
		});
		const session_id = reponse.headers.get('x-session-id');
		const model_chosen = reponse.headers.get('x-chosen-model');

		if (model_chosen) {
			modelChoisi = model_chosen;
			voirModel = true;

			setTimeout(() => {
				voirModel = false;
			}, 4000);
		}

		if (session_id) sessionActive = parseInt(session_id);

		const decoder = new TextDecoder();
		const reader = reponse.body?.getReader();

		messages = [{ role: 'assistant', content: '' }, ...messages];
		while (true) {
			const result = await reader?.read();
			if (!result || result.done) break;

			const rep = decoder.decode(result.value, { stream: true });

			messages[0].content += rep;

			messages = messages;
		}

		currentMessage = '';
		attente = false;
		await rafraichirSession();
	}
	async function ChargerConversation(id: number) {
		if (attente) return;

		console.log('🔵 Tentative de chargement de la session :', id);
		sessionActive = id;

		const res = await fetch(`api/historique/${id}`);
		if (res.ok) {
			const data = await res.json();

			messages = [...data].reverse();

			console.log('🟢 Interface mise à jour avec', messages.length, 'messages');
		} else {
			console.error('🔴 Erreur serveur Python :', res.status);
		}
	}
	async function rafraichirSession() {
		const h = await fetch('/api/historique');
		if (h.ok) {
			historiques = await h.json();
		}
	}

	function nouveauChat() {
		sessionActive = null;
		messages = [{ role: 'assistant', content: "Nouvelle discussion ! Comment puis-je t'aider ?" }];
	}
</script>

<div class="container-global">
	<div class="historique-windows">
		<h2 class="historique-titre">Historique des conversations</h2>
		{#each historiques as historique (historique.id)}
			<button
				class="message-historique"
				class:active={sessionActive === historique.id}
				onclick={() => ChargerConversation(historique.id)}
			>
				{historique.resume}
			</button>
		{/each}
	</div>
	<div class="chat-box">
		<div class="chat-widows">
			{#each messages as msg (msg)}
				<div class={msg.role}>
					<div class="message-content">
						<!-- eslint-disable-next-line svelte/no-at-html-tags -->
						{@html formatMessage(msg.content)}
					</div>
				</div>
			{/each}
		</div>
		<form class="chatter" onsubmit={sendMessage}>
			<input class="chat" bind:value={currentMessage} placeholder="pose ta question ..." />
			<button class="button-go" disabled={attente} type="submit">Envoyer</button>
			<button
				class="new-chat"
				aria-label="Commencer une nouvelle discussion"
				title="Nouvelle discussion"
				onclick={() => nouveauChat()}
			>
				<img src={nouvelleDiscussion} aria-hidden="true" alt="" /></button
			>
		</form>
	</div>
	{#if voirModel}
		<div transition:fly={{ y: 20, duration: 400 }} class="model_choisi">
			<span class="text-choisi"
				>Meilleur modèle pour votre requête : <strong>{modelChoisi}</strong></span
			>
		</div>
	{/if}
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
	.chat-box {
		height: 100%;
		width: 80%;
	}
	.historique-windows {
		height: 100%;
		width: 20%;
		background-color: #111827;
		display: inline-block;

		overflow-y: auto;
		color: #f3f4f6;
	}

	.historique-titre {
		padding-left: 5%;
		font-size: 35px;
	}
	.message-historique {
		all: unset;
		overflow-x: hidden;
		display: block;
		width: 100vw;
		padding: 4% 5% 4% 5%;
		font-size: 25px;
		cursor: pointer;
	}
	.message-historique:hover {
		overflow-x: hidden;

		transform: scale(1.02);
		background-color: #1a2238;
		border-radius: 7px;
		margin-left: 5%;
		margin-right: 5%;
		box-shadow:
			0 0 10px rgba(255, 154, 139, 0.4),
			0 0 20px rgba(255, 154, 139, 0.2);
	}
	.chat-widows {
		padding: 12px;
		height: 90%;
		width: 100%;
		overflow-y: auto;
		margin: 0 auto;
		border-radius: 15px;

		display: flex;
		/* On inverse l'ordre : le premier élément HTML sera en bas */
		flex-direction: column-reverse;
	}

	.user {
		color: black;
		background-color: #e7644f;
		margin-left: auto;
		padding: 7px;
		margin-bottom: 15px;
		border-radius: 50px;
		max-width: 85%;
		width: fit-content;
		box-shadow:
			0 0 30px rgba(255, 154, 139, 0.4),
			0 0 30px rgba(255, 154, 139, 0.2);
		transition: transform 0.2s ease-in-out;
	}
	.user:hover {
		transform: scale(1.02);
		box-shadow: 0 0 15px rgba(255, 154, 139, 0.6);
	}
	.assistant {
		color: black;
		background-color: #e7644f;
		margin-right: 0 auto;
		margin-bottom: 15px;
		padding: 20px;
		border-radius: 50px;
		width: fit-content;
		max-width: 85%;
		box-shadow:
			0 0 30px rgba(255, 154, 139, 0.4),
			0 0 30px rgba(255, 154, 139, 0.2);

		transition: transform 0.2s ease-in-out;
	}
	.assistant:hover {
		transform: scale(1.02); /* La bulle grossit légèrement au survol */
		box-shadow: 0 0 15px rgba(255, 154, 139, 0.6);
	}
	:global(.message-content pre) {
		background-color: #0d1117;
		padding: 15px;
		border-radius: 8px;
		overflow-x: auto;
		margin: 10px 0;
		border: 1px solid #30363d;
	}
	:global(.message-content code) {
		font-family: 'Fira Code', 'Courier New', monospace;
		font-size: 0.9em;
		color: #e6edf3;
	}
	:global(.message-content :not(pre) > code) {
		background-color: rgba(110, 118, 129, 0.4);
		padding: 0.2em 0.4em;
		border-radius: 6px;
	}
	.button-go {
		all: unset;
		border-radius: 20px;
		width: fit-content;
		cursor: pointer;
	}
	.button-go:disabled {
		background-color: grey;
	}
	.button-go:hover {
		transform: scale(1.2); /* Petit effet de zoom */
	}
	.chatter {
		background-color: black;
		border-radius: 50px;
		display: flex;
		padding: 7px 0 7px 0;
		align-items: center;
		justify-content: center;
		margin: 0 auto;
		width: 100%;
		color: #f3f4f6;
	}
	.chat {
		all: unset;
		padding-bottom: 5px;
		flex-grow: 1;
		border-radius: 20px;
		padding: 10px 20px;
		outline: none;
		width: 100%;
	}
	.chatter:hover {
		transform: scale(1.02);
		box-shadow: 0 0 15px rgba(255, 154, 139, 0.6);
	}

	.new-chat {
		all: unset;
		width: 45px;
		height: 45px;

		/* On centre l'icône à l'intérieur */
		display: flex;
		justify-content: center;
		align-items: center;

		/* Style visuel */
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s ease;
		padding: 0;
	}

	.new-chat img {
		width: 30px;
		height: 30px;
		/* Si ton SVG est noir, ceci peut le rendre blanc/clair */
		filter: invert(1);
	}

	.new-chat:hover {
		transform: scale(1.3); /* Petit effet de zoom */
	}

	/* Effet quand on clique */
	.new-chat:active {
		transform: scale(0.95);
	}

	.model_choisi {
		position: fixed;
		bottom: 100px; /* Ajuste selon la position de ta barre de message */
		left: 50%;
		transform: translateX(-50%);
		background: #1e293b; /* Ardoise foncé */
		color: #f8fafc;
		padding: 10px 20px;
		border-radius: 9999px;
		border: 1px solid #38bdf8; /* Bordure cyan */
		box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
		display: flex;
		align-items: center;
		gap: 10px;
		z-index: 50;
		font-family: sans-serif;
		font-size: 0.9rem;
	}
</style>
