<script>
    import { currentUser } from '$lib/stores';
    import { goto } from '$app/navigation';
    import { env } from '$env/dynamic/public';

    let pseudo = '';
    let password = '';
    let errorMessage = '';

    const API_URL = env.PUBLIC_URL_SERVEUR_PYTHON || 'http://localhost:8000';


    async function handleLogin() {
        errorMessage = '';
        try {
            const res = await fetch(`${API_URL}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: pseudo, password: password })
            });

            if (res.ok) {
                $currentUser = pseudo; // Met à jour le store
                goto('/'); // Redirige vers le chat
            } else {
                const data = await res.json();
                errorMessage = data.detail || 'Erreur de connexion';
            }
        } catch (e) {
            errorMessage = 'Serveur injoignable.';
        }
    }

    async function handleRegister() {
        errorMessage = '';
        try {
            const res = await fetch(`${API_URL}/api/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: pseudo, password: password })
            });

            if (res.ok) {
                // Si le compte est créé, on le connecte direct
                $currentUser = pseudo;
                goto('/');
            } else {
                const data = await res.json();
                errorMessage = data.detail || 'Erreur lors de la création';
            }
        } catch (e) {
            errorMessage = 'Serveur injoignable.';
        }
    }
</script>

<div class="login-container">
    <h1>Connexion à Jean-Heude</h1>
    
    {#if errorMessage}
        <p class="error">{errorMessage}</p>
    {/if}

    <input type="text" bind:value={pseudo} placeholder="Ton pseudo (ex: noe_01)" />
    <input type="password" bind:value={password} placeholder="Mot de passe" />

    <div class="buttons">
        <button on:click={handleLogin}>Se connecter</button>
        <button on:click={handleRegister} class="secondary">Créer un compte</button>
    </div>
</div>

<style>
    /* Ajoute un peu de CSS basique ici pour centrer ta modale */
    .login-container { max-width: 400px; margin: 100px auto; display: flex; flex-direction: column; gap: 1rem; }
    input { padding: 10px; font-size: 1rem; }
    button { padding: 10px; cursor: pointer; background: #007bff; color: white; border: none; }
    .secondary { background: #6c757d; }
    .error { color: red; }
</style>