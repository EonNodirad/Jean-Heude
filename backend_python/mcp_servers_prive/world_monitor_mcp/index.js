#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

// L'URL où tourne ton dashboard World Monitor (modifie si besoin)
const WORLD_MONITOR_URL = process.env.WORLD_MONITOR_URL;

// 1. Initialisation du serveur
const server = new Server({
    name: "world-monitor-mcp",
    version: "1.0.0"
}, {
    capabilities: { tools: {} }
});

// 2. Déclaration des outils (C'est ce que Jean-Heude va découvrir tout seul !)
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            {
                name: "get_world_news",
                description: "Récupère les dernières actualités mondiales depuis le dashboard OSINT World Monitor.",
                inputSchema: { type: "object", properties: {}, required: [] }
            },
            {
                name: "get_osint_alerts",
                description: "Récupère les alertes de sécurité, géopolitiques et militaires critiques en cours.",
                inputSchema: { type: "object", properties: {}, required: [] }
            }
        ]
    };
});

// 3. Exécution des outils
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
        let endpoint = "";

        // On route vers la bonne API de ton World Monitor
        if (request.params.name === "get_world_news") {
            endpoint = "/api/news";
        } else if (request.params.name === "get_osint_alerts") {
            endpoint = "/api/alerts"; // Modifie selon les vraies routes de ton API
        } else {
            throw new Error("Outil MCP inconnu");
        }

        // On fait la requête HTTP vers ton dashboard local
        const response = await fetch(`${WORLD_MONITOR_URL}${endpoint}`);
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        // On récupère en texte brut pour être sûr que ça passe (JSON ou HTML)
        const rawData = await response.text();

        // ✂️ On tronque à 3000 caractères pour ne pas exploser le cerveau de Jean-Heude
        const cleanData = rawData.substring(0, 3000) + (rawData.length > 3000 ? "\n...[TRONQUÉ]" : "");

        return {
            content: [{ type: "text", text: cleanData }]
        };

    } catch (error) {
        return {
            isError: true,
            content: [{ type: "text", text: `❌ Impossible de joindre World Monitor : ${error.message}` }]
        };
    }
});

// 4. Lancement du serveur sur les flux standards
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("🌍 World Monitor MCP Server est en ligne et prêt à recevoir des requêtes stdio !");
