import { audioQueue } from '$lib/TTS.svelte';

const ACTIONS = [
	{
		detect: ['recherche', 'cherche', 'google', 'duckduckgo', 'web'],
		label: "Recherche d'informations",
		icon: '🔍'
	},
	{ detect: ['calcule', 'addition', 'multipli', 'math'], label: 'Calcul mathématique', icon: '🧮' },
	{ detect: ['heure', 'date', 'temps', 'moment'], label: "Vérification de l'heure", icon: '🕒' },
	{ detect: ['fichier', 'lire', 'document', 'folder'], label: 'Lecture des fichiers', icon: '📁' },
	{
		detect: ['code', 'python', 'script', 'programmation'],
		label: 'Génération de code',
		icon: '💻'
	},
	{
		detect: ['mémoire', 'souvient', 'historique', 'utilisateur'],
		label: 'Consultation des souvenirs',
		icon: '🧠'
	}
];

export async function handleStream(
	reader: ReadableStreamDefaultReader<Uint8Array>,
	updateCallback: (thinking: string, response: string, status: string) => void
) {
	audioQueue.stop();
	const decoder = new TextDecoder();
	const processedAudioIds = new Set();

	// On garde nos deux boîtes séparées, exactement comme le WebSocket !
	let thinking = '';
	let response = '';
	let lastStatus = 'Analyse...';

	while (true) {
		const result = await reader.read();
		if (result.done) break;

		// On décode UNIQUEMENT le petit morceau qui vient d'arriver
		let chunkText = decoder.decode(result.value, { stream: true });

		// 1. Extraction des IDs Audio dans ce morceau
		const regex = /\|\|AUDIO_ID:(.*?)\|\|/g;
		let match;
		while ((match = regex.exec(chunkText)) !== null) {
			const audioId = match[1];
			if (!processedAudioIds.has(audioId)) {
				audioQueue.add(audioId);
				processedAudioIds.add(audioId);
			}
		}

		// On nettoie les IDs audio du morceau
		chunkText = chunkText.replace(/\|\|AUDIO_ID:.*?\|\|/g, '');

		// 2. LE TRI (Le cœur de la solution !)
		// Ton backend envoie "¶" devant CHAQUE morceau de pensée.
		if (!chunkText) {
			// Si le morceau est totalement vide, on ne fait rien
			continue;
		} else if (chunkText.includes('¶') || chunkText.includes('<think>')) {
			// C'est de la pensée ! On nettoie les symboles et on l'ajoute à la bonne boîte.
			thinking += chunkText.replace(/¶|<\/?think>/g, '');
		} else if (chunkText.trim() !== '') {
			// Pas de "¶" ? C'est que c'est la réponse finale !
			response += chunkText.replace(/<\/think>/g, '');
		}

		// 3. Mise à jour du Status visuel
		for (const action of ACTIONS) {
			if (action.detect.some((k) => thinking.toLowerCase().includes(k))) {
				lastStatus = action.label;
			}
		}

		// 4. On envoie les DEUX boîtes à ton affichage Svelte
		updateCallback(thinking, response, lastStatus);
	}
}
