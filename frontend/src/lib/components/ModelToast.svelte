<script lang="ts">
	import { fly } from 'svelte/transition';

	let { voirModel, modelChoisi } = $props<{
		voirModel: boolean;
		modelChoisi: string;
	}>();
</script>

{#if voirModel}
	<div transition:fly={{ y: 20, duration: 400 }} class="model_choisi">
		<span class="text-choisi"
			>Meilleur modèle pour votre requête : <strong>{modelChoisi}</strong></span
		>
	</div>
{/if}

<style>
	.model_choisi {
		position: fixed;
		bottom: 100px;
		left: 50%;
		transform: translateX(-50%);
		background: #1e293b;
		color: #f8fafc;
		padding: 10px 20px;
		border-radius: 9999px;
		border: 1px solid #38bdf8;
		box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
		display: flex;
		align-items: center;
		gap: 10px;
		z-index: 50;
		font-family: sans-serif;
		font-size: 0.9rem;
	}
</style>
