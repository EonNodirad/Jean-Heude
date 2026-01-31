# Jean-Heude

**J.E.A.N-H.E.U.D.E** is an AI orchestrator designed to be **100% local** and **fully open-source**.

By leveraging cutting-edge community projects, it provides a sovereign AI experience without compromising on privacy or performance.

# 🚀 Key Features

- **Total Sovereignty:** 100% local execution—your data never leaves your machine.
    
- **Agentic Reasoning:** Real-time "Thinking" process visualization, allowing you to follow the AI's logic step-by-step (inspired by o1/DeepSeek-R1).
    
- **Tool Integration (MCP):** Powered by the **Model Context Protocol**, Jean-Heude can browse the web, check your files, or fetch real-time data.
    
- **Unified Memory:** Integration with **Mem0** and **Qdrant**, giving the AI persistent, long-term memory across all your sessions.
    
- **Dynamic Orchestration:** Automatically selects the best local model from your pool based on the complexity of your request.
    

# 🛠 Technical Stack

The architecture is split into specialized layers for maximum efficiency:

- **Frontend:** **SvelteKit** (Svelte 5) for a reactive, ultra-fast interface with real-time streaming status.
    
- **Backend:** **Python (FastAPI)** handling the core agentic logic and tool orchestration.
    
- **Memory Layer:** **Mem0** + **Qdrant** (running via Docker) for vector storage and semantic search.
    
- **Inference Engine:** **Ollama**, serving both Large Language Models (LLMs) and Embedding models.
    
- **Protocol:** **MCP (Model Context Protocol)** for standardized tool and server communication.
    

# 📦 Infrastructure Requirements

To get Jean-Heude up and running, you will need:

1. **Ollama:** To manage and run your local models (e.g., Qwen, Llama, Phi).
    
2. **Docker:** Specifically to host the **Qdrant** server for vector storage.
    
3. **Python 3.12+:** To run the backend orchestrator.
    
4. **Node.js 20+:** For the SvelteKit frontend environment.
    

# 📈 Version History

### **V4.0 (Current)** - **Agentic Loop:** Visual "Thinking" blocks in the UI with a real-time smart status summarizer.

- **MCP Support:** Full integration of Model Context Protocol for external tools.
    
- **Smart Model Selector:** Implementation of the `orchestrator` logic to choose between light and heavy models.
    
- **Asynchronous Streaming:** Full end-to-end async streaming from LLM to Frontend.
    

### **V3.5**

- **Markdown Support:** Rich text rendering in the chat using `markdown-it`.
    

# 🚧 Future Features

- **V4.5:** Integrated **TTS (Text-to-Speech)** and **STT (Speech-to-Text)** for full voice interaction.
    
- **V5:** Multi-agent collaboration (letting several models talk to each other to solve a task).
