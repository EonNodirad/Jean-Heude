import { handleStream } from '$lib/lecture_reponse';

export function createRecorder(callbacks: {
	getSessionId: () => number | null;
	onStream: (think: string, content: string, status: string) => void;
	onTranscriptionStart: () => void;
	onEnd: () => void;
	onModelChosen: (model: string) => void;
	onSessionCreated: (id: number) => void;
}) {
	let isRecording = $state(false);
	let mediaRecorder: MediaRecorder | null = null;
	let audioChunks: Blob[] = [];

	async function start() {
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			isRecording = true;
			audioChunks = [];
			mediaRecorder = new MediaRecorder(stream);

			mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
			mediaRecorder.onstop = async () => {
				const blob = new Blob(audioChunks, { type: 'audio/webm' });
				await send(blob);
				stream.getTracks().forEach((t) => t.stop());
			};
			mediaRecorder.start();
		} catch (err) {
			console.error('Microphone inaccessible', err);
		}
	}

	function stop() {
		if (isRecording && mediaRecorder) {
			isRecording = false;
			mediaRecorder.stop();
		}
	}

	async function send(blob: Blob) {
		callbacks.onTranscriptionStart();

		const formData = new FormData();
		formData.append('file', blob, 'voix.webm');
		// Note: le session_id devra être passé dynamiquement ici
		const currentId = callbacks.getSessionId();
		if (currentId) {
			formData.append('session_id', currentId.toString());
		}
		try {
			const response = await fetch('/api/stt', { method: 'POST', body: formData });

			const sessionId = response.headers.get('x-session-id');
			const model = response.headers.get('x-chosen-model');

			if (sessionId) callbacks.onSessionCreated(parseInt(sessionId));
			if (model) callbacks.onModelChosen(model);

			const reader = response.body?.getReader();
			if (reader) {
				await handleStream(reader, callbacks.onStream);
			}
		} catch (err) {
			console.error('Erreur STT:', err);
		} finally {
			callbacks.onEnd();
		}
	}

	return {
		get isRecording() {
			return isRecording;
		},
		start,
		stop
	};
}
