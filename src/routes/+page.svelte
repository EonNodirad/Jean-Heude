<script>
	let messages = [{ role: 'assistant', content: 'Salut ! je suis ton goat JEAN-Heude' }];
	let currentMessage = '';
</script>

<h1>salut c'est JEAN-Heude</h1>

<div class="chat-widows">
	{#each messages as msg}
		<p class={msg.role}>
			<strong>{msg.role === 'user' ? 'Toi' : 'IA'}</strong>
			{msg.content}
		</p>
	{/each}
</div>

<style>
	.chat-widows {
	}
</style>
