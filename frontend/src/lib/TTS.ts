// src/lib/TTS.ts (ou AudioQueue.ts)
import { env } from '$env/dynamic/public';
class AudioQueue {
	// On ne stocke plus des IDs, mais des URLs déjà téléchargées (Blobs)
	private readyToPlayQueue: string[] = [];
	public isPlaying = false;
	public isBuffering = false;
	private audio: HTMLAudioElement | null = null;
	private abortController: AbortController | null = null;

	// 1. Dés qu'un ID arrive, on lance le fetch SANS ATTENDRE
	add = async (audioId: string) => {
		if (!this.isPlaying) this.isBuffering = true;
		console.log(`%c📡 [Stream] ID reçu: ${audioId} -> Téléchargement lancé`, 'color: #e7644f;');
		if (this.abortController === null) {
			this.abortController = new AbortController();
		}
		// On lance le fetch en arrière-plan
		this.fetchAndBuffer(audioId);
	};

	private fetchAndBuffer = async (audioId: string) => {
		const start = performance.now();
		const url = await this.downloadAudio(audioId);

		if (url) {
			console.log(
				`%c📥 [Buffer] Audio prêt pour ${audioId} (${Math.round(performance.now() - start)}ms)`,
				'color: #38bdf8;'
			);
			this.readyToPlayQueue.push(url);

			// Si rien ne joue, on lance la lecture de la file
			if (!this.isPlaying) {
				this.playNext();
			}
		}
	};

	private downloadAudio = async (audioId: string): Promise<string> => {
		try {
			if (!this.abortController) {
				this.abortController = new AbortController();
			}
			const response = await fetch(`${env.PUBLIC_URL_SERVEUR_PYTHON}/api/tts/${audioId}`, { signal: this.abortController.signal });

			if (!response.ok) {
				console.error(`❌ Erreur serveur (${response.status}) pour l'ID ${audioId}`);
				return '';
			}
			const contentType = response.headers.get('content-type');

			if (contentType && contentType.includes('application/json')) {
				const errorData = await response.json();
				console.error("❌ Le serveur a renvoyé une erreur JSON :", errorData);
				return '';
			}

			if (!contentType || !contentType.includes('audio')) {
				console.error("❌ Format reçu invalide :", contentType);
				return '';
			}

			const blob = await response.blob();
			return URL.createObjectURL(blob);
		} catch (error: any) {
			if (error.name === "AbortError") {
				console.log("requête annulé")
			} else {
				console.error("📡 Erreur réseau :", error);
			}
			return '';
		}
	};

	private playNext = () => {
		if (this.readyToPlayQueue.length === 0) {
			this.isPlaying = false;
			this.isBuffering = false; // On arrête de bufferiser si c'est vide
			return;
		}

		this.isBuffering = false; // Dès qu'on joue, on ne bufferise plus
		this.isPlaying = true
		if (this.readyToPlayQueue.length === 0) {
			this.isPlaying = false;
			return;
		}

		this.isPlaying = true;
		const url = this.readyToPlayQueue.shift()!;
		this.audio = new Audio(url);

		this.audio.onended = () => {
			URL.revokeObjectURL(url); // Libère la RAM
			this.playNext(); // Joue le suivant qui est DÉJÀ dans le buffer
		};

		this.audio.play().catch(() => this.playNext());
	};

	stop = () => {
		this.isBuffering = false;
		this.abortController?.abort()
		this.abortController = null;
		if (this.audio) {
			this.audio.pause();
			this.audio = null;
		}
		this.readyToPlayQueue.forEach((url) => URL.revokeObjectURL(url));
		this.readyToPlayQueue = [];
		this.isPlaying = false;
	};
}

export const audioQueue = new AudioQueue();
