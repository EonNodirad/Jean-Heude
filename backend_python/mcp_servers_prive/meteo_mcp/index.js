import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

const server = new Server({
  name: "meteo-server",
  version: "1.0.0"
}, {
  capabilities: { tools: {} }
});

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [{
      name: "get_weather",
      description: "Donne la météo actuelle pour une latitude et longitude données.",
      inputSchema: {
        type: "object",
        properties: {
          latitude: { type: "number", description: "Latitude (ex: 48.85 pour Paris)" },
          longitude: { type: "number", description: "Longitude (ex: 2.35 pour Paris)" }
        },
        required: ["latitude", "longitude"]
      }
    }]
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "get_weather") {
    const { latitude, longitude } = request.params.arguments;
    try {
      const response = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current_weather=true`);
      const data = await response.json();
      return {
        content: [{ type: "text", text: `La température actuelle est de ${data.current_weather.temperature}°C.` }]
      };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: `Erreur API : ${error.message}` }] };
    }
  }
  throw new Error("Outil inconnu");
});

const transport = new StdioServerTransport();
await server.connect(transport);
