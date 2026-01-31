let currentThinking = '';
let currentResponse = '';

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
	reader: ReadableStreamDefaultReader<Uint8Array<ArrayBuffer>>,
	updateCallback: (thinking: string, response: string, status: string) => void
) {
	currentThinking = '';
	currentResponse = '';
	const decoder = new TextDecoder();
	let lastStatus = 'Analyse de la demande...';
	while (true) {
		const result = await reader?.read();
		if (!result || result.done) break;

		const rep = decoder.decode(result.value, { stream: true });

		if (rep.includes('¶')) {
			const cleanText = rep.replace(/[¶]/g, '');
			currentThinking += cleanText;

			for (const action of ACTIONS) {
				if (
					action.detect.some((keyword: string) => currentThinking.toLowerCase().includes(keyword))
				) {
					lastStatus = `${action.icon} ${action.label}`;
				}
			}

			updateCallback(currentThinking, currentResponse, lastStatus);
		} else {
			currentResponse += rep;
			updateCallback(currentThinking, currentResponse, 'réponse finalisé');
		}
	}
}
