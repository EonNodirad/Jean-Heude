<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { currentUser, authToken, isAdmin } from '$lib/stores';
	import { PUBLIC_URL_SERVEUR_PYTHON } from '$env/static/public';

	const API = PUBLIC_URL_SERVEUR_PYTHON || 'http://localhost:8000';
	const WS_BASE = API.replace(/^http/, 'ws');

	// ── Types ──────────────────────────────────────────────
	type User = { user_id: string; is_admin: number; created_at: string; last_active: string | null };
	type MetricRow = {
		model: string;
		total_requests: number;
		total_tokens: number;
		avg_latency_ms: number;
		error_count: number;
	};
	type Health = { status: string; services: Record<string, string> };
	type Session = {
		id: number;
		userID: string;
		resume: string;
		timestamp: string;
		message_count: number;
	};
	type LogEntry = { time: string; level: string; name: string; message: string; ping?: boolean };

	// ── État ──────────────────────────────────────────────
	let users = $state<User[]>([]);
	let metrics = $state<MetricRow[]>([]);
	let health = $state<Health | null>(null);
	let sessions = $state<Session[]>([]);
	let activeSessions = $state(0);
	let linkCode = $state('');
	let linkCodeExpiry = $state('');
	let loading = $state(true);
	let error = $state('');
	let activeTab = $state<'users' | 'stats' | 'health' | 'sessions' | 'logs' | 'link'>('users');
	let statsWindow = $state(24);
	let confirmDelete = $state<string | null>(null);
	let broadcastMsg = $state('');
	let broadcastStatus = $state('');

	// Logs
	let logs = $state<LogEntry[]>([]);
	let logLevelFilter = $state('');
	let logsWs: WebSocket | null = null;
	let logsConnected = $state(false);

	const navTabs: [string, string, string][] = [
		['users', 'Utilisateurs', '👥'],
		['stats', 'Statistiques', '📊'],
		['sessions', 'Sessions', '🗂️'],
		['health', 'Services', '🩺'],
		['logs', 'Logs', '📋'],
		['link', 'Lier compte', '🔗']
	];

	function headers() {
		return { Authorization: `Bearer ${$authToken}`, 'Content-Type': 'application/json' };
	}

	async function fetchAll() {
		loading = true;
		error = '';
		try {
			const [uRes, sRes, hRes, sessRes] = await Promise.all([
				fetch(`${API}/api/admin/users`, { headers: headers() }),
				fetch(`${API}/api/admin/stats?hours=${statsWindow}`, { headers: headers() }),
				fetch(`${API}/api/admin/health`, { headers: headers() }),
				fetch(`${API}/api/admin/sessions?limit=50`, { headers: headers() })
			]);
			if (uRes.status === 403) {
				void goto('/');
				return;
			}
			users = await uRes.json();
			const sData = await sRes.json();
			metrics = sData.metrics_by_model ?? [];
			activeSessions = sData.active_sessions_last_hour ?? 0;
			health = await hRes.json();
			sessions = sessRes.ok ? await sessRes.json() : [];
		} catch {
			error = 'Erreur de chargement des données.';
		} finally {
			loading = false;
		}
	}

	async function banUser(uid: string) {
		await fetch(`${API}/api/admin/users/${uid}/ban`, { method: 'POST', headers: headers() });
		await fetchAll();
	}

	async function deleteUser(uid: string) {
		await fetch(`${API}/api/admin/users/${uid}`, { method: 'DELETE', headers: headers() });
		confirmDelete = null;
		await fetchAll();
	}

	async function toggleAdmin(uid: string, current: number) {
		const newVal = current === 1 ? false : true;
		await fetch(`${API}/api/admin/users/${uid}/set-admin`, {
			method: 'POST',
			headers: headers(),
			body: JSON.stringify({ is_admin: newVal })
		});
		await fetchAll();
	}

	async function sendBroadcast() {
		if (!broadcastMsg.trim()) return;
		const res = await fetch(`${API}/api/admin/broadcast`, {
			method: 'POST',
			headers: headers(),
			body: JSON.stringify({ message: broadcastMsg })
		});
		if (res.ok) {
			broadcastStatus = '✅ Envoyé';
			broadcastMsg = '';
		} else {
			broadcastStatus = '❌ Erreur';
		}
		setTimeout(() => (broadcastStatus = ''), 3000);
	}

	async function generateLinkCode() {
		const res = await fetch(`${API}/api/generate-link-code`, {
			method: 'POST',
			headers: headers()
		});
		const data = await res.json();
		linkCode = data.code;
		const exp = new Date(Date.now() + data.expires_in_seconds * 1000);
		linkCodeExpiry = exp.toLocaleTimeString();
	}

	// ── Logs WebSocket ──
	function connectLogsWs() {
		if (logsWs) return;
		const url = `${WS_BASE}/ws/admin/logs?token=${$authToken}`;
		logsWs = new WebSocket(url);
		logsWs.onopen = () => {
			logsConnected = true;
		};
		logsWs.onclose = () => {
			logsConnected = false;
			logsWs = null;
		};
		logsWs.onmessage = (ev) => {
			const entry: LogEntry = JSON.parse(ev.data);
			if (entry.ping) return;
			if (logLevelFilter && entry.level !== logLevelFilter) return;
			logs = [...logs.slice(-499), entry];
		};
	}

	function disconnectLogsWs() {
		logsWs?.close();
		logsWs = null;
		logsConnected = false;
	}

	async function loadLogsOnce() {
		const lvl = logLevelFilter ? `&level=${logLevelFilter}` : '';
		const res = await fetch(`${API}/api/admin/logs?limit=200${lvl}`, { headers: headers() });
		if (res.ok) logs = await res.json();
	}

	function levelColor(lvl: string) {
		if (lvl === 'ERROR' || lvl === 'CRITICAL') return '#f87171';
		if (lvl === 'WARNING') return '#fbbf24';
		if (lvl === 'DEBUG') return '#6b7280';
		return '#a3e635';
	}

	function statusColor(s: string) {
		if (s === 'ok') return '#22c55e';
		if (s === 'not_configured') return '#6b7280';
		return '#ef4444';
	}

	function adminLabel(v: number) {
		if (v === -1) return { text: 'Banni', color: '#ef4444' };
		if (v === 1) return { text: 'Admin', color: '#f59e0b' };
		return { text: 'Utilisateur', color: '#9ca3af' };
	}

	function onTabChange(tab: typeof activeTab) {
		activeTab = tab;
		if (tab === 'logs') {
			loadLogsOnce();
			connectLogsWs();
		} else {
			disconnectLogsWs();
		}
	}

	onMount(async () => {
		if (!$currentUser || !$authToken || !$isAdmin) {
			void goto('/');
			return;
		}
		await fetchAll();
	});

	onDestroy(() => disconnectLogsWs());
</script>

<div class="admin-shell">
	<!-- Sidebar -->
	<aside class="sidebar">
		<div class="brand">J.E.A.N<br /><span>Admin</span></div>
		<nav>
			{#each navTabs as [id, label, icon] (id)}
				<button
					class="nav-item"
					class:active={activeTab === id}
					onclick={() => onTabChange(id as typeof activeTab)}
				>
					<span class="nav-icon">{icon}</span>{label}
				</button>
			{/each}
		</nav>
		<button
			class="back-btn"
			onclick={() => {
				void goto('/');
			}}>← Retour au chat</button
		>
	</aside>

	<!-- Main -->
	<main class="content">
		{#if loading}
			<div class="loader">Chargement…</div>
		{:else if error}
			<div class="error-box">{error}</div>
		{:else}
			<!-- ── Onglet Utilisateurs ── -->
			{#if activeTab === 'users'}
				<div class="section-header">
					<h1>Utilisateurs <span class="badge">{users.length}</span></h1>
					<button class="refresh-btn" onclick={fetchAll}>↻ Actualiser</button>
				</div>

				<!-- Broadcast -->
				<div class="broadcast-bar">
					<input
						class="broadcast-input"
						type="text"
						placeholder="Message système à tous les utilisateurs connectés…"
						bind:value={broadcastMsg}
						onkeydown={(e) => e.key === 'Enter' && sendBroadcast()}
					/>
					<button class="act-btn warn" onclick={sendBroadcast}>📢 Envoyer</button>
					{#if broadcastStatus}<span class="broadcast-status">{broadcastStatus}</span>{/if}
				</div>

				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>Pseudo</th><th>Rôle</th><th>Créé le</th><th>Dernière activité</th><th
									>Actions</th
								>
							</tr>
						</thead>
						<tbody>
							{#each users as u (u.user_id)}
								<tr class:banned={u.is_admin === -1}>
									<td class="uid">{u.user_id}</td>
									<td>
										<span class="role-badge" style="color:{adminLabel(u.is_admin).color}">
											{adminLabel(u.is_admin).text}
										</span>
									</td>
									<td class="muted">{u.created_at?.slice(0, 10) ?? '—'}</td>
									<td class="muted">{u.last_active?.slice(0, 16).replace('T', ' ') ?? 'jamais'}</td>
									<td class="actions">
										{#if u.user_id !== $currentUser}
											<button
												class="act-btn warn"
												onclick={() => toggleAdmin(u.user_id, u.is_admin)}
												title={u.is_admin === 1 ? 'Retirer admin' : 'Passer admin'}
											>
												{u.is_admin === 1 ? '⬇ Admin' : '⬆ Admin'}
											</button>
											{#if u.is_admin !== -1}
												<button class="act-btn danger-outline" onclick={() => banUser(u.user_id)}
													>Bannir</button
												>
											{/if}
											{#if confirmDelete === u.user_id}
												<button class="act-btn danger" onclick={() => deleteUser(u.user_id)}
													>Confirmer</button
												>
												<button class="act-btn neutral" onclick={() => (confirmDelete = null)}
													>Annuler</button
												>
											{:else}
												<button class="act-btn danger" onclick={() => (confirmDelete = u.user_id)}
													>Supprimer</button
												>
											{/if}
										{:else}
											<span class="muted">Vous</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			<!-- ── Onglet Statistiques ── -->
			{#if activeTab === 'stats'}
				<div class="section-header">
					<h1>Statistiques</h1>
					<div class="window-select">
						<span class="muted">Fenêtre :</span>
						{#each [6, 24, 168] as h (h)}
							<button
								class="pill"
								class:active={statsWindow === h}
								onclick={() => {
									statsWindow = h;
									fetchAll();
								}}
							>
								{h < 24 ? `${h}h` : h === 24 ? '24h' : '7j'}
							</button>
						{/each}
					</div>
				</div>

				<div class="stat-cards">
					<div class="stat-card">
						<div class="stat-label">Sessions actives (1h)</div>
						<div class="stat-value">{activeSessions}</div>
					</div>
					<div class="stat-card">
						<div class="stat-label">Requêtes totales</div>
						<div class="stat-value">{metrics.reduce((s, m) => s + m.total_requests, 0)}</div>
					</div>
					<div class="stat-card">
						<div class="stat-label">Tokens consommés</div>
						<div class="stat-value">
							{metrics.reduce((s, m) => s + (m.total_tokens ?? 0), 0).toLocaleString()}
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-label">Erreurs</div>
						<div class="stat-value error-val">
							{metrics.reduce((s, m) => s + (m.error_count ?? 0), 0)}
						</div>
					</div>
				</div>

				{#if metrics.length > 0}
					<h2 class="sub-title">Par modèle</h2>
					<div class="table-wrap">
						<table>
							<thead>
								<tr
									><th>Modèle</th><th>Requêtes</th><th>Tokens</th><th>Latence moy.</th><th
										>Erreurs</th
									></tr
								>
							</thead>
							<tbody>
								{#each metrics as m (m.model)}
									<tr>
										<td class="uid">{m.model || '—'}</td>
										<td>{m.total_requests}</td>
										<td>{(m.total_tokens ?? 0).toLocaleString()}</td>
										<td>{Math.round(m.avg_latency_ms ?? 0)} ms</td>
										<td class:error-val={m.error_count > 0}>{m.error_count}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{:else}
					<p class="empty">Aucune métrique pour cette période.</p>
				{/if}
			{/if}

			<!-- ── Onglet Sessions ── -->
			{#if activeTab === 'sessions'}
				<div class="section-header">
					<h1>Sessions <span class="badge">{sessions.length}</span></h1>
					<button class="refresh-btn" onclick={fetchAll}>↻ Actualiser</button>
				</div>
				<div class="table-wrap">
					<table>
						<thead>
							<tr
								><th>ID</th><th>Utilisateur</th><th>Résumé</th><th>Messages</th><th>Horodatage</th
								></tr
							>
						</thead>
						<tbody>
							{#each sessions as s (s.id)}
								<tr>
									<td class="muted">#{s.id}</td>
									<td class="uid">{s.userID}</td>
									<td class="muted resume">{s.resume}</td>
									<td>{s.message_count}</td>
									<td class="muted">{s.timestamp?.slice(0, 16).replace('T', ' ') ?? '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			<!-- ── Onglet Services ── -->
			{#if activeTab === 'health'}
				<div class="section-header">
					<h1>État des services</h1>
					<button class="refresh-btn" onclick={fetchAll}>↻ Actualiser</button>
				</div>
				{#if health}
					<div class="health-grid">
						{#each Object.entries(health.services) as [svc, status] (svc)}
							<div class="health-card">
								<div class="health-dot" style="background:{statusColor(status)}"></div>
								<div>
									<div class="health-name">{svc}</div>
									<div class="health-status" style="color:{statusColor(status)}">{status}</div>
								</div>
							</div>
						{/each}
					</div>
					<div class="overall" style="color:{statusColor(health.status)}">
						Statut global : <strong>{health.status.toUpperCase()}</strong>
					</div>
				{/if}
			{/if}

			<!-- ── Onglet Logs ── -->
			{#if activeTab === 'logs'}
				<div class="section-header">
					<h1>
						Logs temps réel
						<span class="ws-indicator" class:connected={logsConnected}
							>{logsConnected ? '● live' : '○ off'}</span
						>
					</h1>
					<div class="log-controls">
						<select class="log-select" bind:value={logLevelFilter} onchange={loadLogsOnce}>
							<option value="">Tous niveaux</option>
							<option value="DEBUG">DEBUG</option>
							<option value="INFO">INFO</option>
							<option value="WARNING">WARNING</option>
							<option value="ERROR">ERROR</option>
						</select>
						<button class="refresh-btn" onclick={loadLogsOnce}>↻</button>
						<button class="refresh-btn" onclick={() => (logs = [])}>🗑 Vider</button>
					</div>
				</div>
				<div class="log-console">
					{#each logs as entry, i (i)}
						<div class="log-line">
							<span class="log-time">{entry.time}</span>
							<span class="log-level" style="color:{levelColor(entry.level)}">{entry.level}</span>
							<span class="log-name">{entry.name}</span>
							<span class="log-msg">{entry.message}</span>
						</div>
					{/each}
					{#if logs.length === 0}
						<div class="log-empty">Aucun log pour l'instant.</div>
					{/if}
				</div>
			{/if}

			<!-- ── Onglet Lier compte ── -->
			{#if activeTab === 'link'}
				<div class="section-header"><h1>Lier Discord / Telegram</h1></div>
				<div class="link-card">
					<p class="link-desc">
						Génère un code à usage unique (valable <strong>10 minutes</strong>).<br />
						Sur Discord : <code>/link &lt;code&gt;</code> — Sur Telegram :
						<code>/link &lt;code&gt;</code>
					</p>
					<button class="btn-primary" onclick={generateLinkCode}>Générer un code</button>
					{#if linkCode}
						<div class="code-display">
							<span class="code-value">{linkCode}</span>
							<span class="code-exp">expire à {linkCodeExpiry}</span>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</main>
</div>

{#if confirmDelete}
	<div class="modal-overlay" onclick={() => (confirmDelete = null)}>
		<div class="modal" onclick={(e) => e.stopPropagation()}>
			<h2>Supprimer <strong>{confirmDelete}</strong> ?</h2>
			<p class="muted">Cette action est irréversible. Toutes les données seront perdues.</p>
			<div class="modal-actions">
				<button class="act-btn danger" onclick={() => deleteUser(confirmDelete!)}
					>Supprimer définitivement</button
				>
				<button class="act-btn neutral" onclick={() => (confirmDelete = null)}>Annuler</button>
			</div>
		</div>
	</div>
{/if}

<style>
	:global(body) {
		margin: 0;
		padding: 0;
		background: #0f172a;
		color: #f3f4f6;
		font-family: system-ui, sans-serif;
	}

	.admin-shell {
		display: flex;
		min-height: 100vh;
	}

	/* Sidebar */
	.sidebar {
		width: 220px;
		min-width: 220px;
		background: #111827;
		display: flex;
		flex-direction: column;
		padding: 24px 12px;
		border-right: 1px solid rgba(255, 255, 255, 0.06);
	}
	.brand {
		font-size: 1.4rem;
		font-weight: 900;
		color: #e7644f;
		letter-spacing: 0.15em;
		text-align: center;
		margin-bottom: 32px;
		line-height: 1.2;
	}
	.brand span {
		font-size: 0.75rem;
		font-weight: 400;
		color: #6b7280;
		letter-spacing: 0.05em;
	}
	nav {
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1;
	}
	.nav-item {
		all: unset;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 14px;
		border-radius: 10px;
		font-size: 0.9rem;
		color: #9ca3af;
		transition:
			background 0.15s,
			color 0.15s;
	}
	.nav-item:hover {
		background: #1e293b;
		color: #f3f4f6;
	}
	.nav-item.active {
		background: rgba(231, 100, 79, 0.15);
		color: #e7644f;
		font-weight: 600;
	}
	.nav-icon {
		font-size: 1.1rem;
	}
	.back-btn {
		all: unset;
		cursor: pointer;
		margin-top: 24px;
		font-size: 0.85rem;
		color: #6b7280;
		padding: 8px 14px;
		border-radius: 8px;
	}
	.back-btn:hover {
		color: #f3f4f6;
	}

	/* Content */
	.content {
		flex: 1;
		padding: 32px 40px;
		overflow-y: auto;
	}
	.loader {
		color: #6b7280;
		font-size: 1.1rem;
		margin-top: 80px;
		text-align: center;
	}
	.error-box {
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 10px;
		color: #f87171;
		padding: 14px 18px;
	}

	.section-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 24px;
	}
	h1 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 700;
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.badge {
		background: rgba(231, 100, 79, 0.2);
		color: #e7644f;
		font-size: 0.75rem;
		padding: 2px 8px;
		border-radius: 20px;
		font-weight: 600;
	}
	.refresh-btn {
		all: unset;
		cursor: pointer;
		color: #6b7280;
		font-size: 0.9rem;
		padding: 6px 12px;
		border-radius: 8px;
		border: 1px solid rgba(255, 255, 255, 0.08);
	}
	.refresh-btn:hover {
		color: #f3f4f6;
		border-color: rgba(255, 255, 255, 0.2);
	}

	/* Broadcast */
	.broadcast-bar {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 20px;
	}
	.broadcast-input {
		flex: 1;
		background: #111827;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 8px;
		padding: 8px 14px;
		color: #f3f4f6;
		font-size: 0.9rem;
		outline: none;
	}
	.broadcast-input:focus {
		border-color: rgba(231, 100, 79, 0.4);
	}
	.broadcast-status {
		font-size: 0.85rem;
		color: #22c55e;
	}

	/* Table */
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	th {
		text-align: left;
		padding: 10px 14px;
		color: #6b7280;
		font-weight: 600;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}
	td {
		padding: 12px 14px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		vertical-align: middle;
	}
	tr:hover td {
		background: rgba(255, 255, 255, 0.02);
	}
	tr.banned td {
		opacity: 0.5;
	}
	.uid {
		font-weight: 600;
		color: #f3f4f6;
	}
	.muted {
		color: #6b7280;
		font-size: 0.85rem;
	}
	.error-val {
		color: #f87171;
	}
	.role-badge {
		font-size: 0.8rem;
		font-weight: 600;
	}
	.resume {
		max-width: 280px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Action buttons */
	.actions {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}
	.act-btn {
		all: unset;
		cursor: pointer;
		font-size: 0.78rem;
		font-weight: 600;
		padding: 4px 10px;
		border-radius: 6px;
		transition: opacity 0.15s;
	}
	.act-btn:hover {
		opacity: 0.8;
	}
	.act-btn.warn {
		background: rgba(245, 158, 11, 0.15);
		color: #f59e0b;
	}
	.act-btn.danger {
		background: rgba(239, 68, 68, 0.2);
		color: #f87171;
	}
	.act-btn.danger-outline {
		background: transparent;
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #f87171;
	}
	.act-btn.neutral {
		background: rgba(255, 255, 255, 0.06);
		color: #9ca3af;
	}

	/* Stats */
	.stat-cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 16px;
		margin-bottom: 32px;
	}
	.stat-card {
		background: #111827;
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 14px;
		padding: 20px;
	}
	.stat-label {
		font-size: 0.8rem;
		color: #6b7280;
		margin-bottom: 8px;
	}
	.stat-value {
		font-size: 1.8rem;
		font-weight: 700;
		color: #f3f4f6;
	}
	.sub-title {
		margin: 0 0 16px;
		font-size: 1rem;
		font-weight: 600;
		color: #9ca3af;
	}
	.window-select {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.pill {
		all: unset;
		cursor: pointer;
		padding: 4px 12px;
		border-radius: 20px;
		font-size: 0.8rem;
		color: #6b7280;
		border: 1px solid rgba(255, 255, 255, 0.1);
		transition: all 0.15s;
	}
	.pill.active {
		background: rgba(231, 100, 79, 0.2);
		color: #e7644f;
		border-color: rgba(231, 100, 79, 0.4);
	}
	.empty {
		color: #6b7280;
		font-size: 0.9rem;
		margin-top: 24px;
	}

	/* Health */
	.health-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 16px;
		margin-bottom: 24px;
	}
	.health-card {
		background: #111827;
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 14px;
		padding: 18px 20px;
		display: flex;
		align-items: center;
		gap: 14px;
	}
	.health-dot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.health-name {
		font-weight: 600;
		font-size: 0.9rem;
		margin-bottom: 2px;
	}
	.health-status {
		font-size: 0.8rem;
	}
	.overall {
		margin-top: 8px;
		font-size: 1rem;
	}

	/* Logs */
	.log-controls {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.log-select {
		background: #111827;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 8px;
		color: #f3f4f6;
		padding: 6px 10px;
		font-size: 0.85rem;
		cursor: pointer;
	}
	.ws-indicator {
		font-size: 0.75rem;
		font-weight: 500;
		color: #6b7280;
		letter-spacing: 0.05em;
	}
	.ws-indicator.connected {
		color: #22c55e;
	}
	.log-console {
		background: #0a0f1a;
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 12px;
		padding: 16px;
		font-family: 'Fira Code', 'Courier New', monospace;
		font-size: 0.78rem;
		max-height: calc(100vh - 220px);
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.log-line {
		display: flex;
		gap: 12px;
		line-height: 1.5;
	}
	.log-time {
		color: #4b5563;
		flex-shrink: 0;
	}
	.log-level {
		font-weight: 700;
		flex-shrink: 0;
		width: 60px;
	}
	.log-name {
		color: #6b7280;
		flex-shrink: 0;
		max-width: 180px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.log-msg {
		color: #d1d5db;
		word-break: break-word;
	}
	.log-empty {
		color: #4b5563;
		text-align: center;
		padding: 40px 0;
	}

	/* Link */
	.link-card {
		background: #111827;
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 16px;
		padding: 28px;
		max-width: 480px;
	}
	.link-desc {
		color: #9ca3af;
		font-size: 0.9rem;
		line-height: 1.6;
		margin: 0 0 20px;
	}
	.link-desc code {
		background: rgba(255, 255, 255, 0.08);
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 0.85rem;
		color: #f3f4f6;
	}
	.btn-primary {
		all: unset;
		cursor: pointer;
		background: #e7644f;
		color: #fff;
		font-weight: 600;
		padding: 11px 22px;
		border-radius: 10px;
		font-size: 0.95rem;
		transition: opacity 0.15s;
	}
	.btn-primary:hover {
		opacity: 0.85;
	}
	.code-display {
		margin-top: 20px;
		background: #0f172a;
		border: 1px solid rgba(231, 100, 79, 0.3);
		border-radius: 12px;
		padding: 16px 20px;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.code-value {
		font-size: 2rem;
		font-weight: 900;
		letter-spacing: 0.3em;
		color: #e7644f;
	}
	.code-exp {
		font-size: 0.8rem;
		color: #6b7280;
	}

	/* Modal */
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 500;
	}
	.modal {
		background: #111827;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 16px;
		padding: 28px 32px;
		max-width: 420px;
		width: 90%;
	}
	.modal h2 {
		margin: 0 0 8px;
		font-size: 1.1rem;
	}
	.modal-actions {
		display: flex;
		gap: 10px;
		margin-top: 20px;
	}
</style>
