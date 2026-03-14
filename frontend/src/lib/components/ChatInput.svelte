<script lang="ts">
	import nouvelleDiscussion from '$lib/assets/nouvelle-discussion.svg';
	import trombone from '$lib/assets/trombone.png';
	import micro from '$lib/assets/les-ondes-radio.png';
	import type {} from 'svelte'; // Svelte 5 trigger
	import type { createRecorder } from '$lib/voice.svelte';

	let {
		currentMessage = $bindable(''),
		attente,
		recorder,
		onSendMessage,
		onNewChat,
		onFileSelect,
		onClearImage,
		previewUrl
	} = $props<{
		currentMessage: string;
		attente: boolean;
		recorder: ReturnType<typeof createRecorder>;
		onSendMessage: (e: Event | null, file: File | null) => Promise<void>;
		onNewChat: () => void;
		onFileSelect: (file: File | null, url: string | null) => void;
		onClearImage: () => void;
		previewUrl: string | null;
	}>();

	let fileInput: HTMLInputElement;
	let localSelectedFile: File | null = $state(null);

	function triggerFileInput() {
		fileInput.click();
	}

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		if (target.files && target.files.length > 0) {
			localSelectedFile = target.files[0];
			const url = URL.createObjectURL(localSelectedFile);
			onFileSelect(localSelectedFile, url);
		}
	}

	function handleClearImage() {
		localSelectedFile = null;
		if (fileInput) fileInput.value = '';
		onClearImage();
	}

	function handleSubmit(e: Event) {
		e.preventDefault();
		onSendMessage(e, localSelectedFile);
		handleClearImage();
	}
</script>

<form class="chatter" onsubmit={handleSubmit}>
	{#if previewUrl}
		<div class="image-preview-container">
			<img src={previewUrl} alt="Preview" class="preview-img" />
			<button type="button" class="close-preview" onclick={handleClearImage}>×</button>
		</div>
	{/if}

	<input
		type="file"
		accept="image/*"
		style="display: none;"
		bind:this={fileInput}
		onchange={handleFileSelect}
	/>
	<button type="button" class="attach-btn" onclick={triggerFileInput} disabled={attente}>
		<img src={trombone} aria-hidden="true" alt="" />
	</button>

	<input
		class="chat"
		bind:value={currentMessage}
		placeholder="pose ta question ..."
		disabled={attente}
	/>
	<button class="button-go" disabled={attente} type="submit">Envoyer</button>
	<button
		type="button"
		class="new-chat"
		aria-label="Commencer une nouvelle discussion"
		title="Nouvelle discussion"
		onclick={onNewChat}
	>
		<img src={nouvelleDiscussion} aria-hidden="true" alt="" />
	</button>
	<button
		type="button"
		class="mic-btn"
		class:recording={recorder.isRecording}
		onmousedown={recorder.start}
		onmouseup={recorder.stop}
		onmouseleave={recorder.stop}
	>
		{#if recorder.isRecording}
			🔴
		{:else}
			<img src={micro} aria-hidden="true" alt="" />
		{/if}
	</button>
</form>

<style>
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
		transform: scale(1.2);
	}
	.chatter {
		background-color: #0f172a;
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 50px;
		display: flex;
		padding: 7px 0 7px 0;
		align-items: center;
		justify-content: center;
		margin: 0 auto 12px auto;
		width: 90%;
		max-width: 860px;
		color: #f3f4f6;
		position: relative;
	}

	@media (max-width: 768px) {
		.chatter {
			width: 96%;
			border-radius: 30px;
			margin-bottom: 8px;
		}
		.chatter:hover {
			transform: none;
		}
	}
	.chat {
		all: unset;
		padding-bottom: 5px;
		flex-grow: 1;
		border-radius: 20px;
		padding: 10px 15px;
		outline: none;
		width: 100%;
	}
	.chatter:hover {
		transform: scale(1.02);
		box-shadow: 0 0 15px rgba(255, 154, 139, 0.6);
	}
	.mic-btn {
		all: unset;
		padding-right: 10px;
		padding-left: 3px;
	}
	.mic-btn img {
		width: 30px;
		height: 30px;
		filter: invert(1);
	}
	.mic-btn:hover {
		transform: scale(1.3);
	}
	.new-chat {
		all: unset;
		display: flex;
		justify-content: center;
		align-items: center;
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s ease;
		padding-left: 3px;
	}
	.new-chat img {
		width: 30px;
		height: 30px;
		filter: invert(1);
	}
	.new-chat:hover {
		transform: scale(1.3);
	}
	.new-chat:active {
		transform: scale(0.95);
	}
	.attach-btn {
		all: unset;
		cursor: pointer;
		padding: 0 10px;
		font-size: 1.5rem;
		transition: transform 0.2s;
		color: #f3f4f6;
	}
	.attach-btn:hover:not(:disabled) {
		transform: scale(1.2);
	}
	.attach-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.attach-btn img {
		width: 30px;
		height: 30px;
		filter: invert(1);
	}
	.image-preview-container {
		position: absolute;
		bottom: 70px;
		left: 20px;
		background: rgba(17, 24, 39, 0.9);
		padding: 5px;
		border-radius: 10px;
		border: 1px solid rgba(231, 100, 79, 0.4);
		display: flex;
		align-items: start;
	}
	.preview-img {
		max-height: 80px;
		border-radius: 5px;
	}
	.close-preview {
		all: unset;
		background: #e7644f;
		color: white;
		border-radius: 50%;
		width: 20px;
		height: 20px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		margin-left: -10px;
		margin-top: -5px;
		font-weight: bold;
		font-size: 12px;
	}
</style>
