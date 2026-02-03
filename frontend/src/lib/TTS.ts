// src/lib/TTS.ts (ou AudioQueue.ts)
class AudioQueue {
    // On ne stocke plus des IDs, mais des URLs déjà téléchargées (Blobs)
    private readyToPlayQueue: string[] = [];
    private isPlaying = false;
    private audio: HTMLAudioElement | null = null;

    // 1. Dés qu'un ID arrive, on lance le fetch SANS ATTENDRE
    add = async (audioId: string) => {
        console.log(`%c📡 [Stream] ID reçu: ${audioId} -> Téléchargement lancé`, "color: #e7644f;");

        // On lance le fetch en arrière-plan
        this.fetchAndBuffer(audioId);
    }

    private fetchAndBuffer = async (audioId: string) => {
        const start = performance.now();
        const url = await this.fetchWithRetry(audioId);

        if (url) {
            console.log(`%c📥 [Buffer] Audio prêt pour ${audioId} (${Math.round(performance.now() - start)}ms)`, "color: #38bdf8;");
            this.readyToPlayQueue.push(url);

            // Si rien ne joue, on lance la lecture de la file
            if (!this.isPlaying) {
                this.playNext();
            }
        }
    }

    private fetchWithRetry = async (audioId: string, retries = 10): Promise<string> => {
        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(`http://localhost:8000/api/tts/${audioId}`);
                if (response.ok && response.headers.get("content-type")?.includes("audio")) {
                    const blob = await response.blob();
                    return URL.createObjectURL(blob);
                }
            } catch (e) { /* ignore */ }
            await new Promise(r => setTimeout(r, 100)); // Polling rapide
        }
        return "";
    }

    private playNext = () => {
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
    }

    stop = () => {
        if (this.audio) { this.audio.pause(); this.audio = null; }
        this.readyToPlayQueue.forEach(url => URL.revokeObjectURL(url));
        this.readyToPlayQueue = [];
        this.isPlaying = false;
    }
}

export const audioQueue = new AudioQueue();
