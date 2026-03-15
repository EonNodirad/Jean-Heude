<script lang="ts">
	import { goto } from '$app/navigation';
	import trois_points from '$lib/assets/trois-points.png';
	import reglage from '$lib/assets/reglage.png';

	interface Historique {
		id: number;
		resume: string;
	}

	let {
		historiques,
		sessionActive,
		onLoadConversation,
		open = true,
		onClose
	} = $props<{
		historiques: Historique[];
		sessionActive: number | null;
		onLoadConversation: (id: number) => void;
		open?: boolean;
		onClose?: () => void;
	}>();

	let popupOuvert = $state(false);

	function togglePopup() {
		popupOuvert = !popupOuvert;
	}

	async function allerFichiers() {
		popupOuvert = false;
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		await goto('/files');
	}
</script>

<div class="historique-windows" class:open>
	<div class="historique-header">
		<h2 class="historique-titre">Historique</h2>
		<button class="close-btn" onclick={onClose} aria-label="Fermer">✕</button>
	</div>

	<div class="liste-scrollable">
		{#each historiques as historique (historique.id)}
			<div class="historique-message">
				<button
					class="message-historique"
					class:active={sessionActive === historique.id}
					onclick={() => onLoadConversation(historique.id)}
				>
					{historique.resume}
				</button>
				<button class="trois-point"><img src={trois_points} aria-hidden="true" alt="" /></button>
			</div>
		{/each}
	</div>

	<div class="bas-historique">
		<div class="reglage-wrapper">
			{#if popupOuvert}
				<div class="reglage-popup">
					<button class="popup-item" onclick={allerFichiers}>📁 Fichiers</button>
				</div>
			{/if}
			<button class="reglage" onclick={togglePopup}
				><img src={reglage} aria-hidden="true" alt="" /></button
			>
		</div>
	</div>
</div>

<style>
	.historique-windows {
		height: 100vh;
		width: 260px;
		min-width: 260px;
		background-color: #111827;
		color: #f3f4f6;
		display: flex;
		flex-direction: column;
		flex-shrink: 0;
	}

	.historique-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-right: 12px;
	}

	.close-btn {
		all: unset;
		cursor: pointer;
		font-size: 1.2rem;
		color: #9ca3af;
		display: none;
		padding: 4px 8px;
		border-radius: 6px;
		transition: color 0.2s;
	}
	.close-btn:hover {
		color: #f3f4f6;
	}

	@media (max-width: 768px) {
		.historique-windows {
			position: fixed;
			top: 0;
			left: 0;
			z-index: 200;
			transform: translateX(-100%);
			transition: transform 0.3s ease;
			width: 80%;
			max-width: 300px;
			box-shadow: 4px 0 20px rgba(0, 0, 0, 0.5);
		}
		.historique-windows.open {
			transform: translateX(0);
		}
		.close-btn {
			display: block;
		}
	}
	.liste-scrollable {
		flex: 1;
		overflow-y: auto;
		width: 100%;
	}

	.historique-titre {
		padding-left: 5%;
		font-size: 1.1rem;
		font-weight: 600;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: #9ca3af;
		margin: 16px 0 8px 0;
	}
	.message-historique {
		all: unset;
		display: flex;
		width: 100%;
		padding: 10px 15px;
		font-size: 18px;
		cursor: pointer;
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
		opacity: 1;
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
		filter: invert(1);
	}
	.reglage {
		all: unset;
		cursor: pointer;
		display: flex;
		margin: 0;
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
		align-items: center;
		justify-content: flex-end;
		width: 100%;
		height: 60px;
		padding: 0 15px;
		flex-shrink: 0;
		box-sizing: border-box;
	}

	.reglage-wrapper {
		position: relative;
	}

	.reglage-popup {
		position: absolute;
		bottom: calc(100% + 8px);
		right: 0;
		background: #1f2937;
		border: 1px solid #374151;
		border-radius: 8px;
		padding: 4px;
		min-width: 150px;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
		z-index: 300;
	}

	.popup-item {
		all: unset;
		display: block;
		width: 100%;
		padding: 8px 12px;
		font-size: 0.9rem;
		color: #f3f4f6;
		cursor: pointer;
		border-radius: 6px;
		box-sizing: border-box;
	}

	.popup-item:hover {
		background: #374151;
	}
</style>
