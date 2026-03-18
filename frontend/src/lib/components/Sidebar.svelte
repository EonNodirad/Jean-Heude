<script lang="ts">
	import { goto } from '$app/navigation';
	import trois_points from '$lib/assets/trois-points.png';
	import reglage from '$lib/assets/reglage.png';
	import { isAdmin, authToken, currentUser } from '$lib/stores';
	import { PUBLIC_URL_SERVEUR_PYTHON } from '$env/static/public';

	const API = PUBLIC_URL_SERVEUR_PYTHON || 'http://localhost:8000';

	async function logout() {
		popupOuvert = false;
		// Révocation côté backend (best-effort)
		const token = $authToken;
		if (token) {
			try {
				await fetch(`${API}/api/logout`, {
					method: 'POST',
					headers: { Authorization: `Bearer ${token}` }
				});
			} catch { /* silencieux */ }
		}
		$currentUser = null;
		$authToken = null;
		$isAdmin = false;
		await goto('/login');
	}

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
	let modalLienOuvert = $state(false);
	let linkCode = $state('');
	let linkCodeExpiry = $state('');
	let linkLoading = $state(false);

	function togglePopup() {
		popupOuvert = !popupOuvert;
	}

	async function ouvrirModalLien() {
		popupOuvert = false;
		linkCode = '';
		linkCodeExpiry = '';
		modalLienOuvert = true;
	}

	async function genererCode() {
		linkLoading = true;
		try {
			const res = await fetch(`${API}/api/generate-link-code`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${$authToken}` }
			});
			const data = await res.json();
			linkCode = data.code;
			const exp = new Date(Date.now() + data.expires_in_seconds * 1000);
			linkCodeExpiry = exp.toLocaleTimeString();
		} catch {
			linkCode = 'Erreur';
		} finally {
			linkLoading = false;
		}
	}

	async function allerFichiers() {
		popupOuvert = false;
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		await goto('/files');
	}

	async function allerAdmin() {
		popupOuvert = false;
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		await goto('/admin');
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
					<button class="popup-item" onclick={ouvrirModalLien}>🔗 Lier Telegram / Discord</button>
					{#if $isAdmin}
						<button class="popup-item popup-item--admin" onclick={allerAdmin}>🛡️ Dashboard Admin</button>
					{/if}
					<hr class="popup-divider" />
					<button class="popup-item popup-item--logout" onclick={logout}>⏻ Déconnexion</button>
				</div>
			{/if}
			<button
				class="reglage"
				class:reglage--admin={$isAdmin}
				onclick={togglePopup}
				title="Paramètres"
			>
				<img src={reglage} aria-hidden="true" alt="" />
			</button>
		</div>
	</div>
</div>

{#if modalLienOuvert}
	<div class="modal-overlay" onclick={() => (modalLienOuvert = false)}>
		<div class="modal-lien" onclick={(e) => e.stopPropagation()}>
			<button class="modal-close" onclick={() => (modalLienOuvert = false)}>✕</button>
			<h2 class="modal-titre">🔗 Lier Telegram / Discord</h2>
			<p class="modal-desc">
				Génère un code à usage unique (<strong>10 min</strong>), puis envoie-le sur la plateforme :
			</p>
			<div class="modal-cmds">
				<code>/link &lt;code&gt;</code>
			</div>
			<button class="modal-btn" onclick={genererCode} disabled={linkLoading}>
				{linkLoading ? 'Génération...' : 'Générer un code'}
			</button>
			{#if linkCode && linkCode !== 'Erreur'}
				<div class="code-box">
					<span class="code-val">{linkCode}</span>
					<span class="code-exp">expire à {linkCodeExpiry}</span>
				</div>
			{:else if linkCode === 'Erreur'}
				<p class="modal-error">Impossible de générer le code. Réessaie.</p>
			{/if}
		</div>
	</div>
{/if}

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
	.reglage--admin img {
		filter: invert(55%) sepia(80%) saturate(500%) hue-rotate(330deg);
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

	.popup-item--admin {
		color: #f59e0b;
	}

	.popup-divider {
		border: none;
		border-top: 1px solid #374151;
		margin: 4px 0;
	}

	.popup-item--logout {
		color: #f87171;
	}

	/* Modal lien plateforme */
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 500;
	}
	.modal-lien {
		position: relative;
		background: #111827;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 16px;
		padding: 28px 28px 24px;
		width: 90%;
		max-width: 380px;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}
	.modal-close {
		all: unset;
		cursor: pointer;
		position: absolute;
		top: 14px;
		right: 16px;
		color: #6b7280;
		font-size: 1rem;
	}
	.modal-close:hover { color: #f3f4f6; }
	.modal-titre {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 700;
		color: #f3f4f6;
	}
	.modal-desc {
		margin: 0;
		font-size: 0.85rem;
		color: #9ca3af;
		line-height: 1.5;
	}
	.modal-cmds {
		background: #0f172a;
		border-radius: 8px;
		padding: 10px 14px;
	}
	.modal-cmds code {
		font-size: 0.9rem;
		color: #e7644f;
	}
	.modal-btn {
		all: unset;
		cursor: pointer;
		background: #e7644f;
		color: #fff;
		font-weight: 600;
		padding: 10px 18px;
		border-radius: 10px;
		font-size: 0.9rem;
		text-align: center;
		transition: opacity 0.15s;
	}
	.modal-btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.modal-btn:not(:disabled):hover { opacity: 0.85; }
	.code-box {
		background: #0f172a;
		border: 1px solid rgba(231, 100, 79, 0.3);
		border-radius: 12px;
		padding: 14px 18px;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.code-val {
		font-size: 1.8rem;
		font-weight: 900;
		letter-spacing: 0.3em;
		color: #e7644f;
	}
	.code-exp {
		font-size: 0.75rem;
		color: #6b7280;
	}
	.modal-error {
		margin: 0;
		font-size: 0.85rem;
		color: #f87171;
	}
</style>
