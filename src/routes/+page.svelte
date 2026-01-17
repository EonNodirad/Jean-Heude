<script lang="ts">
	import { preventDefault } from 'svelte/legacy';

	let messages = [{ role: 'assistant', content: 'Salut ! je suis ton goat JEAN-Heude' }];
	let currentMessage = '';
	let attente = false;
	const attendre = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

	async function sendMessage() {
		if (currentMessage.trim() === '') return;
		attente = true;
		try {
			messages = [...messages, { role: 'user', content: currentMessage }];
		} finally {
			currentMessage = '';
			await attendre(2000);
			attente = false;
		}
	}
</script>

<h1 class="titre">salut c'est JEAN-Heude</h1>

<div class="chat-widows">
	{#each messages as msg}
		<p class={msg.role}>
			{msg.content}
		</p>
	{/each}
</div>

<form class="chatter" on:submit|preventDefault={sendMessage}>
	<input bind:value={currentMessage} placeholder="pose ta question ..." />
	<button class="button-go" disabled={attente} type="submit">Envoyer</button>
</form>

<style>
	.chat-widows {
		height: 300px;
		width: 400px;
		overflow-y: auto;
		border: 5px solid;
		margin: 0 auto;
		border-radius: 15px;
		padding: 15px;
	}
	.user {
		color: blue;
		background-color: #e46767;
		margin-left: auto;
		padding: 7px;
		border: 2px solid #000;
		border-radius: 50px;
		width: fit-content;
	}
	.assistant {
		color: blueviolet;
		background-color: aquamarine;
		margin-right: auto;
		padding: 7px;
		border-radius: 50px;
		border: 2px solid #000;
		width: fit-content;
	}
	.button-go {
		color: #e46767;
		background-color: black;
		border-radius: 20px;
		width: fit-content;
	}
	.button-go:disabled {
		background-color: grey;
	}
	.chatter {
		padding-top: 20px;
		margin: 0 auto;
		width: fit-content;
	}
	.titre {
		margin: 0 auto;
		padding-bottom: 60px;
		width: fit-content;
	}
</style>
