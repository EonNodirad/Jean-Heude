import { env } from '$env/dynamic/public';

class AudioQueue {
	private audioCtx: AudioContext | null = null;
	private nextStartTime: number = 0;

	// --- NOUVEAU : Le garde-barrière ---
	private processingChain: Promise<void> = Promise.resolve();

	public isPlaying = $state(false);
	public isBuffering = $state(false);

	private initAudioContext() {
		if (!this.audioCtx) {
			console.log('🔊 [AudioCtx] Initialisation du moteur...');
			this.audioCtx = new AudioContext({
				sampleRate: 24000
			});
		}
		if (this.audioCtx.state === 'suspended') this.audioCtx.resume();
	}

	add = (audioId: string) => {
		console.log(`%c📡 [Queue] ID reçu et mis en attente : ${audioId}`, 'color: #38bdf8');
		this.initAudioContext();

		// On enchaîne : "Quand la tâche précédente est finie, lance celle-là"
		this.processingChain = this.processingChain.then(() => this.streamAudio(audioId));
	};

	private async streamAudio(audioId: string) {
		let leftover: Uint8Array | null = null;

		try {
			this.isBuffering = true;
			console.log(
				`%c📥 [Fetch] Début du traitement séquentiel pour : ${audioId}`,
				'color: #fbbf24'
			);

			const response = await fetch(`/api/tts/${audioId}`);
			const reader = response.body?.getReader();
			if (!reader) return;

			// On cale le curseur sur le temps réel s'il est à la traîne
			if (this.nextStartTime < this.audioCtx!.currentTime) {
				this.nextStartTime = this.audioCtx!.currentTime;
			}

			while (true) {
				const { done, value } = await reader.read();
				if (done && !leftover) break;

				let chunk: Uint8Array | null = value ?? null;

				// --- Logique du reliquat (inchangée) ---
				if (leftover) {
					const combined: Uint8Array = new Uint8Array(leftover.length + (chunk?.length || 0));
					combined.set(leftover);
					if (chunk) combined.set(chunk, leftover.length);
					chunk = combined;
					leftover = null;
				}
				if (!chunk || chunk.length === 0) {
					if (done) break;
					continue;
				}
				if (chunk.length % 2 !== 0) {
					leftover = chunk.slice(-1);
					chunk = chunk.slice(0, -1);
				}
				if (chunk.length === 0) continue;
				// ---------------------------------------

				this.isBuffering = false;
				this.isPlaying = true;

				const pcmData = new Int16Array(chunk.buffer, chunk.byteOffset, chunk.length / 2);
				const floatData = new Float32Array(pcmData.length);
				for (let i = 0; i < pcmData.length; i++) floatData[i] = pcmData[i] / 32768.0;

				const audioBuffer = this.audioCtx!.createBuffer(1, floatData.length, 24000);
				audioBuffer.getChannelData(0).set(floatData);

				const source = this.audioCtx!.createBufferSource();
				source.buffer = audioBuffer;
				source.connect(this.audioCtx!.destination);

				const startTime = this.nextStartTime;
				source.start(startTime);
				this.nextStartTime += audioBuffer.duration;

				console.log(
					`%c🎵 [Play] ${audioId.split('-')[0]}... programmé à ${startTime.toFixed(2)}s`,
					'color: #4ade80'
				);

				source.onended = () => {
					// On ne repasse à false que si plus rien n'est prévu dans le futur proche
					if (this.audioCtx && this.audioCtx.currentTime >= this.nextStartTime - 0.2) {
						this.isPlaying = false;
					}
				};
			}
			console.log(`%c✅ [Done] Fin du stream pour : ${audioId}`, 'color: #4ade80');
		} catch (e) {
			console.error(`❌ [Error] ${audioId}:`, e);
			this.isBuffering = false;
		}
	}

	stop = () => {
		console.log('🛑 [Stop] Reset total de la file.');
		if (this.audioCtx) {
			this.audioCtx.close();
			this.audioCtx = null;
		}
		this.processingChain = Promise.resolve(); // On vide la file d'attente
		this.isPlaying = false;
		this.isBuffering = false;
		this.nextStartTime = 0;
	};
}

export const audioQueue = new AudioQueue();
