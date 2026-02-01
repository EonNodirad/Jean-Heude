class AudioQueue {
    private queue: string[] = [];
    private isPlaying = false;
    private audio: HTMLAudioElement | null = null;

    async add(audioId: string) {
        this.queue.push(audioId);
        if (!this.isPlaying) {
            this.playNext();
        }
    }

    private async fetchWithRetry(audioId: string, retries = 5): Promise<string> {
        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(`http://localhost:8000/api/tts/${audioId}`);
                if (response.ok) {
                    const blob = await response.blob();
                    return URL.createObjectURL(blob);
                }
            } catch (e) { console.error("Tentative échouée", i); }

            // Attendre 200ms avant la prochaine tentative si le serveur n'est pas prêt
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        return "";
    }
    private async playNext() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            return;
        }

        this.isPlaying = true;
        const audioId = this.queue.shift()!;

        try {
            const url = await this.fetchWithRetry(audioId);

            if (!url) {
                this.playNext();
                return;
            }

            this.audio = new Audio(url);

            // --- CRITIQUE : Relancer la file à la fin du son ---
            this.audio.onended = () => {
                URL.revokeObjectURL(url); // Libère la RAM
                this.playNext();
            };

            // Gestion des erreurs de lecture (ex: autoplay bloqué)
            await this.audio.play().catch(err => {
                console.warn("Autoplay bloqué ou erreur de lecture:", err);
                // Si ça bloque, on passe au suivant après un petit délai
                setTimeout(() => this.playNext(), 1000);
            });

        } catch (err) {
            console.error("Erreur de lecture", err);
            this.playNext();
        }
    }
    stop() {
        if (this.audio) {
            this.audio.pause();
            this.audio = null;
        }
        this.queue = [];
        this.isPlaying = false;
    }
}


export const audioQueue = new AudioQueue();
