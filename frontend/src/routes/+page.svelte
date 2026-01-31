<script lang="ts">
	import { onMount } from 'svelte';
	import nouvelleDiscussion from '$lib/assets/nouvelle-discussion.svg';
	import reglage from '$lib/assets/reglage.png';
	import { formatMessage } from '$lib/format';
	import 'highlight.js/styles/github-dark.css';
	import { fly } from 'svelte/transition';
	import trois_points from '$lib/assets/trois-points.png';
	import { handleStream } from '$lib/lecture_reponse';
	let messages = $state([
		{
			role: 'assistant',
			think: '',
			content: 'Salut ! je suis ton assistant J.E.A.N-H.E.U.D.E',
			status: ''
		}
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
		messages = [{ role: 'user', think: '', content: currentMessage, status: '' }, ...messages];
		messages = [
			{ role: 'assistant', think: '', content: '', status: ' Je réfléchit ...' },
			...messages
		];
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
			}, 3000);
		}

		if (session_id) sessionActive = parseInt(session_id);

		const reader = reponse.body?.getReader();

		if (reader) {
			await handleStream(reader, (think, content, status) => {
				messages[0].think = think;
				messages[0].content = content;
				messages[0].status = status;
			});
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
		messages = [
			{
				role: 'assistant',
				think: '',
				content: "Nouvelle discussion ! Comment puis-je t'aider ?",
				status: ''
			}
		];
	}
</script>

<div class="container-global">
	<div class="historique-windows">
		<h2 class="historique-titre">Historique des conversations</h2>

		<div class="liste-scrollable">
			{#each historiques as historique (historique.id)}
				<div class="historique-message">
					<button
						class="message-historique"
						class:active={sessionActive === historique.id}
						onclick={() => ChargerConversation(historique.id)}
					>
						{historique.resume}
					</button>
					<button class="trois-point"><img src={trois_points} aria-hidden="true" alt="" /></button>
				</div>
			{/each}
		</div>

		<div class="bas-historique">
			<button class="reglage"><img src={reglage} aria-hidden="true" alt="" /></button>
		</div>
	</div>
	<div class="chat-box">
		<div class="chat-widows">
			{#each messages as msg (msg)}
				<div class="message {msg.role}">
					{#if msg.think}
						<div class="thinking-container">
							<details open={!msg.content}>
								<summary class="status-summary">
									<div class="status-indicator">
										{#if !msg.content}<span class="pulse-dot"></span>{/if}
										{msg.status || 'Jean-Heude réfléchit...'}
									</div>
								</summary>
								<div class="thinking-content">
									{msg.think}
								</div>
							</details>
						</div>
					{/if}

					{#if msg.content}
						<div class="content-bubble">
							<!-- eslint-disable-next-line svelte/no-at-html-tags -->
							{@html formatMessage(msg.content)}
						</div>
					{:else if msg.role === 'assistant' && !msg.think}
						<div class="dot-typing-container">
							<span class="dot-typing"></span>
						</div>
					{/if}
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
	/* Style pour les liens dans la bulle assistant (pour les news) */
	:global(.assistant .content-bubble a) {
		color: #1a2238;
		text-decoration: underline;
		font-weight: bold;
	}

	/* On s'assure que les paragraphes n'ont pas de marges inutiles */
	:global(.content-bubble p) {
		margin: 0 0 10px 0;
	}
	:global(.content-bubble p:last-child) {
		margin-bottom: 0;
	}
	/* --- RÉFLEXION VERSION AGENT --- */
	.thinking-container {
		margin-bottom: 15px;
		width: 100%;
		animation: slideIn 0.3s ease-out;
	}

	.thinking-container details {
		background-color: rgba(17, 24, 39, 0.6);
		border: 1px solid rgba(231, 100, 79, 0.4);
		border-radius: 12px;
		padding: 5px; /* Plus compact */
		color: #94a3b8;
		font-family: 'Fira Code', monospace;
		transition: all 0.3s ease;
	}

	/* Le bandeau de statut (Summary) */
	.thinking-container summary {
		cursor: pointer;
		padding: 8px 12px;
		outline: none;
		list-style: none;
		display: flex;
		align-items: center;
		gap: 12px;
		font-size: 0.85rem;
		color: #e7644f;
	}

	/* Le petit point qui pulse pendant la réflexion */
	.pulse-dot {
		width: 8px;
		height: 8px;
		background-color: #e7644f;
		border-radius: 50%;
		box-shadow: 0 0 8px rgba(231, 100, 79, 0.8);
		animation: pulse-glow 1.5s infinite ease-in-out;
		flex-shrink: 0;
	}

	@keyframes pulse-glow {
		0%,
		100% {
			transform: scale(1);
			opacity: 1;
		}
		50% {
			transform: scale(1.4);
			opacity: 0.5;
		}
	}

	/* Contenu de la réflexion (Détails) */
	.thinking-content {
		margin-top: 5px;
		padding: 10px 15px;
		border-top: 1px dashed rgba(231, 100, 79, 0.2);
		font-style: italic;
		line-height: 1.5;
		font-size: 0.8rem;
		max-height: 200px; /* On limite pour éviter de casser le scroll */
		overflow-y: auto;
	}

	/* Animation pour l'apparition des messages */
	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
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
		height: 100vh;
		width: 20%;
		background-color: #111827;

		color: #f3f4f6;
		display: flex;
		flex-direction: column;
	}
	.liste-scrollable {
		flex: 1; /* Prend tout l'espace disponible */
		overflow-y: auto; /* Active le scroll ici seulement */
		width: 100%;
	}

	.historique-titre {
		padding-left: 5%;
		font-size: 35px;
	}
	.message-historique {
		all: unset;
		display: flex;
		width: 100%; /* Passe à 100% pour que le clic fonctionne partout */
		padding: 10px 15px;
		font-size: 18px; /* 25px était peut-être un peu grand */
		cursor: pointer;
		/* Supprime overflow-x et overflow-y ici */
	}

	.historique-message:hover {
		overflow-x: hidden;

		background-color: #1a2238;
		border-radius: 7px;

		box-shadow:
			0 0 10px rgba(255, 154, 139, 0.4),
			0 0 20px rgba(255, 154, 139, 0.2);
	}
	.historique-message {
		display: flex;
		overflow-x: hidden;
	}
	.historique-message:hover .trois-point {
		opacity: 1; /* Devient visible au survol */
	}
	.trois-point {
		all: unset;
		opacity: 0;
	}
	.trois-point:hover {
		transform: scale(1.2);
	}
	.trois-point img {
		width: 20px;
		height: 20px;
		/* Si ton SVG est noir, ceci peut le rendre blanc/clair */
		filter: invert(1);
	}
	.reglage {
		all: unset;
		cursor: pointer;
		display: flex;
		margin: 0; /* On retire les margin auto ici */
	}

	.reglage img {
		width: 30px;
		height: 30px;

		filter: invert(1);
	}
	.reglage:hover {
		transform: scale(1.3);
	}
	.bas-historique {
		display: flex;
		align-items: center; /* Centre l'icône verticalement */
		justify-content: flex-end; /* Colle l'icône à droite */
		width: 100%;
		height: 60px; /* Utilise une hauteur fixe plutôt que 10% */
		padding: 0 15px;
		background-color: #111827;
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
	:global(.message pre) {
		background-color: #0d1117;
		padding: 15px;
		border-radius: 8px;
		overflow-x: auto;
		margin: 10px 0;
		border: 1px solid #30363d;
	}
	:global(.message code) {
		font-family: 'Fira Code', 'Courier New', monospace;
		font-size: 0.9em;
		color: #e6edf3;
	}
	:global(.message :not(pre) > code) {
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
		width: 90%;
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
