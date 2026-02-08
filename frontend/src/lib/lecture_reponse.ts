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
	let streamBuffer = '';
	const decoder = new TextDecoder();
	const processedAudioIds = new Set();
	let lastStatus = 'Analyse...';

	while (true) {
		const result = await reader.read();
		if (result.done) break;

		streamBuffer += decoder.decode(result.value, { stream: true });

		// 1. Extraction des IDs Audio (on ne change pas ce qui marche)
		const regex = /\|\|AUDIO_ID:(.*?)\|\|/g;
		let match;
		while ((match = regex.exec(streamBuffer)) !== null) {
			const audioId = match[1];
			if (!processedAudioIds.has(audioId)) {
				audioQueue.add(audioId);
				processedAudioIds.add(audioId);
			}
		}

		// 2. Séparation Pensée / Réponse
		// On nettoie les tags IDs pour ne pas polluer l'affichage
		const cleanFullText = streamBuffer.replace(/\|\|AUDIO_ID:.*?\|\|/g, '');

		// On découpe par le caractère spécial ¶
		const parts = cleanFullText.split('¶');

		let thinking = '';
		let response = '';

		if (parts.length > 1) {
			// S'il y a des ¶, tout ce qui est avant le dernier ¶ est de la pensée
			// (L'IA peut envoyer plusieurs blocs de pensée)
			response = parts.pop() || ''; // Le dernier élément après le dernier ¶
			thinking = parts.join(' ').replace(/[¶]/g, ''); // Tout le reste
		} else {
			// S'il n'y a pas (ou plus) de ¶, tout est de la réponse
			response = parts[0];
		}

		// 3. Mise à jour du Status (optionnel)
		for (const action of ACTIONS) {
			if (action.detect.some((k) => thinking.toLowerCase().includes(k))) {
				lastStatus = action.label;
			}
		}

		updateCallback(thinking, response, lastStatus);
	}
}
