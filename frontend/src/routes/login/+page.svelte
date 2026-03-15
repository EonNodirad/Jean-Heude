<script>
	import { currentUser, authToken } from '$lib/stores';
	import { goto } from '$app/navigation';
	import { PUBLIC_URL_SERVEUR_PYTHON } from '$env/static/public';

	let pseudo = '';
	let password = '';
	let errorMessage = '';
	let loading = false;

	const API_URL = PUBLIC_URL_SERVEUR_PYTHON || 'http://localhost:8000';

	async function handleLogin() {
		errorMessage = '';
		loading = true;
		try {
			const res = await fetch(`${API_URL}/api/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ user_id: pseudo, password: password })
			});

			if (res.ok) {
				const data = await res.json();
				$currentUser = data.user_id;
				$authToken = data.access_token;
				// eslint-disable-next-line svelte/no-navigation-without-resolve
				await goto('/');
			} else {
				const data = await res.json();
				errorMessage = data.detail || 'Erreur de connexion';
			}
		} catch {
			errorMessage = 'Serveur injoignable.';
		} finally {
			loading = false;
		}
	}

	async function handleRegister() {
		errorMessage = '';
		loading = true;
		try {
			const res = await fetch(`${API_URL}/api/register`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ user_id: pseudo, password: password })
			});

			if (res.ok) {
				const data = await res.json();
				$currentUser = data.user_id;
				$authToken = data.access_token;
				// eslint-disable-next-line svelte/no-navigation-without-resolve
				await goto('/');
			} else {
				const data = await res.json();
				errorMessage = data.detail || 'Erreur lors de la création';
			}
		} catch {
			errorMessage = 'Serveur injoignable.';
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') handleLogin();
	}
</script>

<div class="page">
	<div class="card">
		<div class="logo">J.E.A.N</div>
		<h1 class="title">Connexion</h1>
		<p class="subtitle">Ton assistant local</p>

		{#if errorMessage}
			<div class="error-box">{errorMessage}</div>
		{/if}

		<div class="fields">
			<input
				type="text"
				bind:value={pseudo}
				placeholder="Pseudo"
				disabled={loading}
				onkeydown={handleKeydown}
			/>
			<input
				type="password"
				bind:value={password}
				placeholder="Mot de passe"
				disabled={loading}
				onkeydown={handleKeydown}
			/>
		</div>

		<div class="buttons">
			<button onclick={handleLogin} disabled={loading} class="btn-primary">
				{loading ? '...' : 'Se connecter'}
			</button>
			<button onclick={handleRegister} disabled={loading} class="btn-secondary">
				Créer un compte
			</button>
		</div>
	</div>
</div>

<style>
	:global(body) {
		margin: 0;
		padding: 0;
		background-color: #1a2238;
	}

	.page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 16px;
		background-color: #1a2238;
	}

	.card {
		background-color: #111827;
		border: 1px solid rgba(231, 100, 79, 0.2);
		border-radius: 20px;
		padding: 40px 36px;
		width: 100%;
		max-width: 380px;
		box-shadow: 0 8px 40px rgba(0, 0, 0, 0.4);
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.logo {
		font-size: 1.8rem;
		font-weight: 900;
		color: #e7644f;
		letter-spacing: 0.2em;
		text-align: center;
	}

	.title {
		margin: 0;
		font-size: 1.4rem;
		font-weight: 700;
		color: #f3f4f6;
		text-align: center;
	}

	.subtitle {
		margin: 0 0 8px 0;
		font-size: 0.85rem;
		color: #6b7280;
		text-align: center;
	}

	.error-box {
		background-color: rgba(231, 100, 79, 0.15);
		border: 1px solid rgba(231, 100, 79, 0.4);
		border-radius: 10px;
		color: #f87171;
		font-size: 0.9rem;
		padding: 10px 14px;
		text-align: center;
	}

	.fields {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	input {
		background-color: #1e293b;
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 12px;
		color: #f3f4f6;
		font-size: 1rem;
		padding: 12px 16px;
		outline: none;
		transition: border-color 0.2s;
		width: 100%;
		box-sizing: border-box;
	}
	input::placeholder {
		color: #4b5563;
	}
	input:focus {
		border-color: rgba(231, 100, 79, 0.6);
	}
	input:disabled {
		opacity: 0.5;
	}

	.buttons {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 4px;
	}

	button {
		border: none;
		border-radius: 12px;
		font-size: 1rem;
		font-weight: 600;
		padding: 13px;
		cursor: pointer;
		transition:
			transform 0.15s,
			opacity 0.15s;
		width: 100%;
	}
	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	button:not(:disabled):hover {
		transform: scale(1.02);
	}
	button:not(:disabled):active {
		transform: scale(0.98);
	}

	.btn-primary {
		background-color: #e7644f;
		color: #fff;
	}
	.btn-secondary {
		background-color: transparent;
		border: 1px solid rgba(255, 255, 255, 0.1);
		color: #9ca3af;
	}
	.btn-secondary:hover {
		border-color: rgba(231, 100, 79, 0.4);
		color: #f3f4f6;
	}

	@media (max-width: 480px) {
		.card {
			padding: 28px 20px;
		}
	}
</style>
