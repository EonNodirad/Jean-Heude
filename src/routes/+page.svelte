<script lang="ts">
	import { preventDefault } from 'svelte/legacy';
	import { onMount } from 'svelte';
	interface Session {
		id: number;
		resume: string;
		date: string;
	}
	let messages = [{ role: 'assistant', content: 'Salut ! je suis ton goat JEAN-Heude' }];
	let currentMessage = '';
	let attente = false;
	let sessionActive: number | null = null;
	let historiques: Session[] = [];

	const attendre = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));
	onMount(async () => {
		await rafraichirSession();
	});
	async function sendMessage() {
		if (currentMessage.trim() === '') return;
		attente = true;
		messages = [{ role: 'user', content: currentMessage }, ...messages];

		let reponse = await fetch('/api/chat', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ content: currentMessage, session_id: sessionActive })
		});
		let result = await reponse.json();
		if (!sessionActive && result.session_id) {
			sessionActive = result.session_id;
		}
		messages = [{ role: 'assistant', content: result.reply }, ...messages];
		currentMessage = '';
		attente = false;
		await rafraichirSession();
	}
	async function ChargerConversation(id: number) {
		sessionActive = id;
		const res = await fetch(`http://localhost:8000/history/${id}`);
		if (res.ok) {
			messages = await res.json();
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
		{#each historiques as historique}
			<button
				class="message-historique"
				class:active={sessionActive === historique.id}
				on:click={() => ChargerConversation(historique.id)}
			>
				{historique.resume}
			</button>
		{/each}
	</div>
	<div class="chat-widows">
		<form class="chatter" on:submit|preventDefault={sendMessage}>
			<input class="chat" bind:value={currentMessage} placeholder="pose ta question ..." />
			<button class="button-go" disabled={attente} type="submit">Envoyer</button>
			<button class="new-chat" on:click={() => nouveauChat()}> + nouveau </button>
		</form>
		{#each messages as msg}
			<p class={msg.role}>
				{msg.content}
			</p>
		{/each}
	</div>
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
		height: 100%;
		width: 80%;
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
		border-radius: 50px;
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
		margin-right: auto;
		padding: 7px;
		border-radius: 50px;
		width: fit-content;
		box-shadow:
			0 0 30px rgba(255, 154, 139, 0.4),
			0 0 30px rgba(255, 154, 139, 0.2);

		transition: transform 0.2s ease-in-out;
	}
	.assistant:hover {
		transform: scale(1.02); /* La bulle grossit légèrement au survol */
		box-shadow: 0 0 15px rgba(255, 154, 139, 0.6);
	}
	.button-go {
		color: black;
		background-color: #e7644f;
		border-radius: 20px;
		width: fit-content;
	}
	.button-go:disabled {
		background-color: grey;
	}
	.chatter {
		padding: 20px 0 10px 10%;
		padding-top: 20px;
		margin: 0 auto;
		width: 100%;
	}
	.chat {
		border-radius: 20px;
		padding-left: 10%;
		width: 80%;
	}
	.chat:hover {
		transform: scale(1.02);
		box-shadow: 0 0 15px rgba(255, 154, 139, 0.6);
	}
	.titre {
		margin: 0 auto;
		padding-bottom: 60px;
		width: fit-content;
	}
</style>
