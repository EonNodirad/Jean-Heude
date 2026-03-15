<script lang="ts">
	import { formatMessage } from '$lib/format';
	import { audioQueue } from '$lib/TTS.svelte';

	interface Message {
		role: string;
		think: string;
		content: string;
		status: string;
		image?: string | null;
	}

	let { msg } = $props<{ msg: Message }>();
</script>

<div class="message {msg.role}">
	{#if msg.think}
		<div class="thinking-container">
			<details open={!msg.content}>
				<summary class="status-summary">
					<div class="status-indicator">
						<span class="pulse-dot"></span>
						{#if audioQueue.isBuffering && !audioQueue.isPlaying}
							Synthèse vocale en cours...
						{:else}
							{msg.status || 'Jean-Heude réfléchit...'}
						{/if}
					</div>
				</summary>
				<div class="thinking-content">
					{msg.think}
				</div>
			</details>
		</div>
	{/if}

	{#if msg.content || msg.image}
		<div class="content-bubble">
			{#if msg.role === 'user'}
				<p style="white-space: pre-wrap; margin: 0 0 10px 0;">{msg.content}</p>

				{#if msg.image}
					<img
						src={msg.image}
						alt="Upload"
						style="max-width: 250px; border-radius: 10px; margin-top: 10px; display: block;"
					/>
				{/if}
			{:else}
				<!-- eslint-disable-next-line -->
				{@html formatMessage(msg.content)}
			{/if}
		</div>
	{:else if msg.role === 'assistant' && !msg.think}
		<div class="dot-typing-container">
			<span class="dot-typing"></span>
		</div>
	{/if}
</div>

<style>
	/* Style pour les liens dans la bulle assistant (pour les news) */
	:global(.assistant .content-bubble a) {
		color: #38bdf8;
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
		max-height: 200px;
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

	.user {
		color: #111827;
		background-color: #e7644f;
		margin-left: auto;
		margin-right: 20px;
		padding: 12px 18px;
		margin-bottom: 15px;
		border-radius: 20px 20px 4px 20px;
		max-width: 75%;
		width: fit-content;
		box-shadow: 0 2px 12px rgba(231, 100, 79, 0.3);
		transition: transform 0.2s ease-in-out;
	}
	.user:hover {
		transform: scale(1.01);
		box-shadow: 0 4px 20px rgba(231, 100, 79, 0.5);
	}
	.assistant {
		color: #f3f4f6;
		background-color: #1e293b;
		border: 1px solid rgba(231, 100, 79, 0.2);
		margin-right: auto;
		margin-bottom: 15px;
		padding: 20px;
		border-radius: 20px 20px 20px 4px;
		width: fit-content;
		max-width: 85%;
		box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
		transition: transform 0.2s ease-in-out;
	}
	.assistant:hover {
		transform: scale(1.01);
		box-shadow: 0 4px 20px rgba(231, 100, 79, 0.2);
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
</style>
