<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { authToken } from '$lib/stores';
	import { get } from 'svelte/store';
	import { PUBLIC_URL_SERVEUR_PYTHON } from '$env/static/public';

	interface FileEntry {
		path: string;
		type: 'file' | 'dir';
	}

	let fichiers = $state<FileEntry[]>([]);
	let fichierActif = $state<string | null>(null);
	let contenu = $state('');
	let sauvegarde = $state(false);
	let erreur = $state('');
	let nouveauNom = $state('');
	let afficherNouveauFichier = $state(false);

	function getToken(): string {
		return `Bearer ${get(authToken)}`;
	}

	async function chargerFichiers() {
		try {
			const res = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/api/files`, {
				headers: { Authorization: getToken() }
			});
			if (res.status === 401) {
				// eslint-disable-next-line svelte/no-navigation-without-resolve
				await goto('/login');
				return;
			}
			const data = await res.json();
			fichiers = data;
		} catch {
			erreur = 'Impossible de charger la liste des fichiers.';
		}
	}

	async function ouvrirFichier(path: string) {
		erreur = '';
		try {
			const res = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/api/files/${path}`, {
				headers: { Authorization: getToken() }
			});
			if (!res.ok) {
				erreur = 'Impossible de lire ce fichier.';
				return;
			}
			const data = await res.json();
			fichierActif = path;
			contenu = data.content;
			sauvegarde = false;
		} catch {
			erreur = 'Erreur lors de la lecture du fichier.';
		}
	}

	async function sauvegarder() {
		if (!fichierActif) return;
		erreur = '';
		try {
			const res = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/api/files/${fichierActif}`, {
				method: 'PUT',
				headers: { Authorization: getToken(), 'Content-Type': 'application/json' },
				body: JSON.stringify({ content: contenu })
			});
			if (!res.ok) {
				erreur = 'Erreur lors de la sauvegarde.';
				return;
			}
			sauvegarde = true;
			setTimeout(() => (sauvegarde = false), 2000);
		} catch {
			erreur = 'Erreur lors de la sauvegarde.';
		}
	}

	async function creerFichier() {
		if (!nouveauNom.trim()) return;
		const nom = nouveauNom.trim().endsWith('.md') ? nouveauNom.trim() : nouveauNom.trim() + '.md';
		const chemin = `projects/${nom}`;
		erreur = '';
		try {
			const res = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/api/files/${chemin}`, {
				method: 'POST',
				headers: { Authorization: getToken() }
			});
			if (res.status === 409) {
				erreur = 'Ce fichier existe déjà.';
				return;
			}
			if (!res.ok) {
				erreur = 'Erreur lors de la création.';
				return;
			}
			nouveauNom = '';
			afficherNouveauFichier = false;
			await chargerFichiers();
			await ouvrirFichier(chemin);
		} catch {
			erreur = 'Erreur lors de la création du fichier.';
		}
	}

	async function supprimerFichier(path: string) {
		if (!confirm(`Supprimer ${path} ?`)) return;
		erreur = '';
		try {
			const res = await fetch(`${PUBLIC_URL_SERVEUR_PYTHON}/api/files/${path}`, {
				method: 'DELETE',
				headers: { Authorization: getToken() }
			});
			if (!res.ok) {
				erreur = 'Erreur lors de la suppression.';
				return;
			}
			if (fichierActif === path) {
				fichierActif = null;
				contenu = '';
			}
			await chargerFichiers();
		} catch {
			erreur = 'Erreur lors de la suppression.';
		}
	}

	function estSysteme(path: string): boolean {
		return path.startsWith('system/');
	}

	// Groupe les fichiers par dossier
	function grouper(fichiers: FileEntry[]): Record<string, FileEntry[]> {
		const groupes: Record<string, FileEntry[]> = {};
		for (const f of fichiers) {
			if (f.type === 'dir') continue;
			const slash = f.path.lastIndexOf('/');
			const dossier = slash >= 0 ? f.path.substring(0, slash) : '';
			if (!groupes[dossier]) groupes[dossier] = [];
			groupes[dossier].push(f);
		}
		return groupes;
	}

	onMount(() => {
		chargerFichiers();
	});

	let groupes = $derived(grouper(fichiers));
</script>

<div class="page">
	<header class="topbar">
		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
		<button class="retour" onclick={async () => await goto('/')}>← Retour</button>
		<h1 class="titre">Mes fichiers</h1>
	</header>

	<div class="contenu-principal">
		<!-- Arborescence gauche -->
		<aside class="arbre">
			{#each Object.entries(groupes) as [dossier, items] (dossier)}
				<div class="dossier-section">
					<div class="dossier-titre">📂 {dossier || 'racine'}</div>
					{#each items as item (item.path)}
						<div class="fichier-ligne" class:actif={fichierActif === item.path}>
							<button class="fichier-btn" onclick={() => ouvrirFichier(item.path)}>
								📄 {item.path.split('/').pop()}
							</button>
							{#if !estSysteme(item.path)}
								<button
									class="suppr-btn"
									onclick={() => supprimerFichier(item.path)}
									title="Supprimer">✕</button
								>
							{/if}
						</div>
					{/each}
				</div>
			{/each}

			<div class="nouveau-fichier-section">
				{#if afficherNouveauFichier}
					<div class="nouveau-form">
						<input
							type="text"
							bind:value={nouveauNom}
							placeholder="nom-du-fichier.md"
							onkeydown={(e) => e.key === 'Enter' && creerFichier()}
						/>
						<button onclick={creerFichier}>Créer</button>
						<button
							onclick={() => {
								afficherNouveauFichier = false;
								nouveauNom = '';
							}}>✕</button
						>
					</div>
				{:else}
					<button class="btn-nouveau" onclick={() => (afficherNouveauFichier = true)}
						>+ Nouveau fichier</button
					>
				{/if}
			</div>
		</aside>

		<!-- Éditeur droite -->
		<main class="editeur">
			{#if erreur}
				<div class="erreur">{erreur}</div>
			{/if}

			{#if fichierActif}
				<div class="editeur-header">
					<span class="fichier-nom">{fichierActif}</span>
					<button class="btn-sauvegarder" onclick={sauvegarder}>
						{sauvegarde ? '✓ Sauvegardé' : 'Sauvegarder'}
					</button>
				</div>
				<textarea class="zone-edition" bind:value={contenu} spellcheck="false"></textarea>
			{:else}
				<div class="placeholder">Sélectionne un fichier pour l'éditer.</div>
			{/if}
		</main>
	</div>
</div>

<style>
	.page {
		display: flex;
		flex-direction: column;
		height: 100vh;
		background: #0f172a;
		color: #f3f4f6;
		font-family: inherit;
	}

	.topbar {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 12px 20px;
		background: #111827;
		border-bottom: 1px solid #1f2937;
		flex-shrink: 0;
	}

	.retour {
		all: unset;
		cursor: pointer;
		color: #9ca3af;
		font-size: 0.9rem;
		padding: 6px 12px;
		border-radius: 6px;
		border: 1px solid #374151;
	}
	.retour:hover {
		color: #f3f4f6;
		border-color: #6b7280;
	}

	.titre {
		font-size: 1.1rem;
		font-weight: 600;
		color: #e5e7eb;
		margin: 0;
	}

	.contenu-principal {
		display: flex;
		flex: 1;
		overflow: hidden;
	}

	.arbre {
		width: 240px;
		min-width: 200px;
		background: #111827;
		border-right: 1px solid #1f2937;
		overflow-y: auto;
		padding: 12px 0;
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.dossier-section {
		margin-bottom: 8px;
	}

	.dossier-titre {
		padding: 4px 12px;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #6b7280;
		font-weight: 600;
	}

	.fichier-ligne {
		display: flex;
		align-items: center;
		padding: 0 8px;
		border-radius: 6px;
		margin: 1px 6px;
	}
	.fichier-ligne:hover {
		background: #1f2937;
	}
	.fichier-ligne.actif {
		background: #1e3a5f;
	}

	.fichier-btn {
		all: unset;
		flex: 1;
		cursor: pointer;
		padding: 6px 4px;
		font-size: 0.85rem;
		color: #d1d5db;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.fichier-ligne.actif .fichier-btn {
		color: #93c5fd;
	}

	.suppr-btn {
		all: unset;
		cursor: pointer;
		color: #6b7280;
		font-size: 0.75rem;
		padding: 2px 4px;
		border-radius: 4px;
		opacity: 0;
		transition: opacity 0.15s;
	}
	.fichier-ligne:hover .suppr-btn {
		opacity: 1;
	}
	.suppr-btn:hover {
		color: #ef4444;
	}

	.nouveau-fichier-section {
		padding: 8px 12px;
		margin-top: auto;
	}

	.btn-nouveau {
		all: unset;
		cursor: pointer;
		font-size: 0.85rem;
		color: #60a5fa;
		padding: 6px 8px;
		border-radius: 6px;
		border: 1px dashed #374151;
		width: 100%;
		box-sizing: border-box;
		text-align: center;
	}
	.btn-nouveau:hover {
		background: #1f2937;
	}

	.nouveau-form {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}
	.nouveau-form input {
		flex: 1;
		background: #1f2937;
		border: 1px solid #374151;
		border-radius: 6px;
		color: #f3f4f6;
		padding: 4px 8px;
		font-size: 0.85rem;
		min-width: 0;
	}
	.nouveau-form button {
		all: unset;
		cursor: pointer;
		background: #374151;
		color: #f3f4f6;
		padding: 4px 8px;
		border-radius: 6px;
		font-size: 0.8rem;
	}
	.nouveau-form button:hover {
		background: #4b5563;
	}

	.editeur {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		padding: 0;
	}

	.erreur {
		background: #7f1d1d;
		color: #fca5a5;
		padding: 8px 16px;
		font-size: 0.85rem;
	}

	.editeur-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 16px;
		background: #111827;
		border-bottom: 1px solid #1f2937;
		flex-shrink: 0;
	}

	.fichier-nom {
		font-size: 0.85rem;
		color: #9ca3af;
		font-family: monospace;
	}

	.btn-sauvegarder {
		all: unset;
		cursor: pointer;
		background: #1d4ed8;
		color: #fff;
		padding: 6px 14px;
		border-radius: 6px;
		font-size: 0.85rem;
		transition: background 0.2s;
	}
	.btn-sauvegarder:hover {
		background: #2563eb;
	}

	.zone-edition {
		flex: 1;
		width: 100%;
		background: #0f172a;
		color: #e2e8f0;
		border: none;
		outline: none;
		padding: 16px;
		font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
		font-size: 0.9rem;
		line-height: 1.6;
		resize: none;
		box-sizing: border-box;
	}

	.placeholder {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #4b5563;
		font-size: 0.9rem;
	}

	@media (max-width: 600px) {
		.arbre {
			width: 100%;
			min-width: unset;
			height: 200px;
			border-right: none;
			border-bottom: 1px solid #1f2937;
		}
		.contenu-principal {
			flex-direction: column;
		}
	}
</style>
