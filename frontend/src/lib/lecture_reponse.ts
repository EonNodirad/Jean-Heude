let currentThinking = "";
let currentResponse = "";


export async function handleStream(reader: ReadableStreamDefaultReader<Uint8Array<ArrayBuffer>>, updateCallback: (thinking: string, response: string) => void
) {
    currentThinking = "";
    currentResponse = "";
    const decoder = new TextDecoder();

    while (true) {
        const result = await reader?.read();
        if (!result || result.done) break;

        const rep = decoder.decode(result.value, { stream: true });

        if (rep.includes("¶")) {
            const cleanText = rep.replace(/[¶]/g, "");
            currentThinking += cleanText;
        } else { currentResponse += rep; }

        updateCallback(currentThinking, currentResponse);
    }
}
