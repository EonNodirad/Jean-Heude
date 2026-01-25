# Jean-Heude

**J.E.A.N-H.E.U.D.E** is an AI orchestrator designed to be **100% local** and **fully-open-source**.
By leveraging cuting-edge community projects, it provides a sovereign AI experience wihout compromising on privacy or performance.

# Key Feature

- **Total Sovereignty:** 100% local execution—your data never leaves your machine.
- **Unified Memory:** Powered by **Mem0**, allowing the AI to maintain a persistent and intelligent context across sessions.
- **Open Source:** Built entirely on transparent, extensible, and community-driven tools.

# Technical stack

The architecture is split into specialized layers for maximum efficiency:

- **Frontend:** Built with **SvelteKit** for a fast, modern, and reactive user interface.
- **Backend:** Developed in **Python**, handling the core logic and orchestration.
- **Vector Database:** Integration with **Qdrant** (running via Docker) to power the Mem0 memory layer.
- **Inference Engine:** Utilizes **Ollama** to serve both Large Language Models (LLMs) and Embedding models.

# Infrastructure Requirements

To get Jean-Heude up and running, you will need the following components:

1. **Ollama:** To manage and run your local models.
2. **Docker:** Specifically to host the **Qdrant** server for vector storage.
3. **Python 3.x:** To run the backend orchestrator.
4. **Node.js:** For the SvelteKit frontend environment.

# Actual Version

**V3.5** : adding markdown format in the chat thanks to **markdownit**

# Future feature

**V4** : using little IA for choosing the best IA in the pool depending on the context
