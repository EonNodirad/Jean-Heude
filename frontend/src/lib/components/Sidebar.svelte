<script lang="ts">
	import trois_points from '$lib/assets/trois-points.png';
	import reglage from '$lib/assets/reglage.png';

	interface Historique {
		id: number;
		resume: string;
	}

	let { historiques, sessionActive, onLoadConversation } = $props<{
		historiques: Historique[];
		sessionActive: number | null;
		onLoadConversation: (id: number) => void;
	}>();
</script>

<div class="historique-windows">
	<h2 class="historique-titre">Historique des conversations</h2>

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
		<button class="reglage"><img src={reglage} aria-hidden="true" alt="" /></button>
	</div>
</div>

<style>
	.historique-windows {
		height: 100vh;
		width: 20%;
		background-color: #111827;
		color: #f3f4f6;
		display: flex;
		flex-direction: column;
	}
	.liste-scrollable {
		flex: 1;
		overflow-y: auto;
		width: 100%;
	}

	.historique-titre {
		padding-left: 5%;
		font-size: 35px;
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
		background-color: #111827;
	}
</style>
