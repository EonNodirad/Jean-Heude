<script lang="ts">
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';
	import type { Message } from '$lib/chat.svelte';
	import type { createRecorder } from '$lib/voice.svelte';

	let {
		messages,
		currentMessage = $bindable(),
		attente,
		recorder,
		onSendMessage,
		onNewChat,
		onFileSelect,
		onClearImage,
		previewUrl,
		onOpenSidebar
	} = $props<{
		messages: Message[];
		currentMessage: string;
		attente: boolean;
		recorder: ReturnType<typeof createRecorder>;
		onSendMessage: (e: Event | null, file: File | null) => Promise<void>;
		onNewChat: () => void;
		onFileSelect: (file: File | null, url: string | null) => void;
		onClearImage: () => void;
		previewUrl: string | null;
		onOpenSidebar: () => void;
	}>();
</script>

<div class="chat-box">
	<div class="chat-topbar">
		<button class="burger-btn" onclick={onOpenSidebar} aria-label="Menu">☰</button>
	</div>
	<div class="chat-widows">
		{#each messages as msg (msg)}
			<ChatMessage {msg} />
		{/each}
	</div>

	<ChatInput
		bind:currentMessage
		{attente}
		{recorder}
		{onSendMessage}
		{onNewChat}
		{previewUrl}
		{onFileSelect}
		{onClearImage}
	/>
</div>

<style>
	.chat-box {
		height: 100%;
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}

	.chat-topbar {
		display: none;
		padding: 10px 16px;
		background-color: #111827;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
	}

	.burger-btn {
		all: unset;
		cursor: pointer;
		font-size: 1.4rem;
		color: #f3f4f6;
		line-height: 1;
	}
	.burger-btn:hover {
		color: #e7644f;
	}

	.chat-widows {
		padding: 12px 16px;
		flex: 1;
		width: 100%;
		overflow-y: auto;
		margin: 0 auto;
		border-radius: 15px;
		display: flex;
		flex-direction: column-reverse;
	}

	@media (max-width: 768px) {
		.chat-topbar {
			display: flex;
			align-items: center;
		}
		.chat-widows {
			padding: 8px 10px;
		}
	}
</style>
