<script lang="ts">
	import ChatMessage from '$lib/components/ChatMessage.svelte';
	import ChatInput from '$lib/components/ChatInput.svelte';

	let {
		messages,
		currentMessage = $bindable(),
		attente,
		recorder,
		onSendMessage,
		onNewChat,
		onFileSelect,
		onClearImage,
		previewUrl
	} = $props<{
		messages: any[];
		currentMessage: string;
		attente: boolean;
		recorder: any;
		onSendMessage: (e: Event | null, file: File | null) => Promise<void>;
		onNewChat: () => void;
		onFileSelect: (file: File | null, url: string | null) => void;
		onClearImage: () => void;
		previewUrl: string | null;
	}>();
</script>

<div class="chat-box">
	<div class="chat-widows">
		{#each messages as msg (msg)}
			<ChatMessage msg={msg} />
		{/each}
	</div>

	<ChatInput
		bind:currentMessage={currentMessage}
		attente={attente}
		recorder={recorder}
		onSendMessage={onSendMessage}
		onNewChat={onNewChat}
		previewUrl={previewUrl}
		onFileSelect={onFileSelect}
		onClearImage={onClearImage}
	/>
</div>

<style>
	.chat-box {
		height: 100%;
		width: 80%;
		display: flex;
		flex-direction: column;
	}

	.chat-widows {
		padding: 12px;
		height: 90%;
		width: 100%;
		overflow-y: auto;
		margin: 0 auto;
		border-radius: 15px;
		display: flex;
		flex-direction: column-reverse; /* Pour que les messages soient en bas d'abord */
	}
</style>
