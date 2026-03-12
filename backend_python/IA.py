import os
import re
import logging
import hashlib
import json
import numpy as np
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "anchor_vectors_cache.json"
ANCHORS_FILE = Path(__file__).parent / "task_anchors.py"

from ollama import AsyncClient
from dotenv import load_dotenv

load_dotenv()
remote_host = os.getenv("URL_SERVER_OLLAMA")

client = AsyncClient(host=remote_host)
logger = logging.getLogger("jean_heude.IA")

system_message = 'You are a helpful assistant name Jean-Heude'
model_used = 'llama3.1:8b'

def create_message(message, role):
    return {
        'role': role,
        'content': message
    }

def chat(chat_message, model_used):
    ollama_response = client.chat(model=model_used, stream=False, messages=chat_message)
    assistant_message = ollama_response['message']['content']
    return assistant_message


from task_anchors import TASK_ANCHORS


class Orchestrator:
    def __init__(self):
        self.remote_host = os.getenv("URL_SERVER_OLLAMA", "http://localhost:11434")
        self.client = AsyncClient(host=self.remote_host)
        # Cache capacités modèles
        self._capabilities_cache: dict = {}
        # Cache embeddings des ancres (calculés une seule fois)
        self._anchor_cache: dict[str, list[list[float]]] = {}

    async def get_model_details(self, model_name: str):
        """Récupère et cache les capacités techniques d'un modèle."""
        if model_name in self._capabilities_cache:
            return self._capabilities_cache[model_name]

        try:
            info = await self.client.show(model_name)
            caps = info.get("capabilities", [])
            details = info.get("details", {})

            data = {
                "name": model_name,
                "can_think": "thinking" in caps,
                "can_use_tools": "tools" in caps,
                "size": details.get("parameter_size", "unknown"),
                "family": details.get("family", "unknown")
            }
            self._capabilities_cache[model_name] = data
            return data
        except Exception as e:
            logger.warning("Erreur d'inspection pour %s : %s", model_name, e)
            return None

    async def get_local_models(self):
        """Liste tous les modèles locaux installés sur Ollama."""
        try:
            resp = await self.client.list()
            models = []
            for m in resp.get('models', []):
                name = m.get('model') or m.get('name')
                if name:
                    models.append(name)
            return models
        except Exception as e:
            logger.error("Erreur lors de la récupération des modèles : %s", e)
            return []

    async def _get_anchor_embeddings(self) -> dict[str, list[list[float]]]:
        """Charge les ancres depuis le cache fichier, ou les calcule si besoin."""
        if self._anchor_cache:
            return self._anchor_cache

        current_hash = hashlib.sha256(ANCHORS_FILE.read_bytes()).hexdigest()

        # Chargement depuis le cache si task_anchors.py n'a pas changé
        if CACHE_FILE.exists():
            try:
                data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                if data.get("hash") == current_hash:
                    self._anchor_cache = data["vectors"]
                    logger.info("[Orchestrateur] Ancres chargées depuis le cache (%d catégories).", len(self._anchor_cache))
                    return self._anchor_cache
                logger.info("[Orchestrateur] task_anchors.py a changé, recalcul des ancres...")
            except Exception as e:
                logger.warning("[Orchestrateur] Cache corrompu, recalcul : %s", e)

        # Calcul des embeddings (premier lancement ou après modification des ancres)
        from tools import _get_tool_embedding
        logger.info("[Orchestrateur] Calcul des ancres sémantiques...")
        for category, texts in TASK_ANCHORS.items():
            vecs = []
            for text in texts:
                v = await _get_tool_embedding(text)
                if v:
                    vecs.append(v)
            self._anchor_cache[category] = vecs

        # Sauvegarde pour les prochains démarrages
        try:
            CACHE_FILE.write_text(
                json.dumps({"hash": current_hash, "vectors": self._anchor_cache}, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info("[Orchestrateur] Cache des ancres sauvegardé.")
        except Exception as e:
            logger.warning("[Orchestrateur] Impossible de sauvegarder le cache : %s", e)

        return self._anchor_cache

    async def _classify_task(self, message: str) -> dict:
        """Classifie sémantiquement le message via similarité cosinus avec les ancres."""
        from tools import _get_tool_embedding

        msg_vec = await _get_tool_embedding(message)
        if not msg_vec:
            # Fallback basique si l'embedding est indisponible
            logger.warning("[Orchestrateur] Embedding indisponible, fallback longueur.")
            return {"needs_tools": False, "is_complex": len(message) > 300}

        anchors = await self._get_anchor_embeddings()
        msg_arr = np.array(msg_vec, dtype=np.float32)
        msg_norm = msg_arr / (np.linalg.norm(msg_arr) + 1e-9)

        scores: dict[str, float] = {}
        for category, vecs in anchors.items():
            if not vecs:
                scores[category] = 0.0
                continue
            sims = []
            for v in vecs:
                v_arr = np.array(v, dtype=np.float32)
                v_norm = v_arr / (np.linalg.norm(v_arr) + 1e-9)
                sims.append(float(np.dot(msg_norm, v_norm)))
            scores[category] = sum(sims) / len(sims)

        score_tools = scores.get("needs_tools", 0)
        score_complex = scores.get("complex_reasoning", 0)
        score_simple = scores.get("simple_reply", 0)

        # Seuil minimum : la différence doit être significative pour conclure complex/tools.
        # nomic-embed-text étant entraîné majoritairement en anglais, les scores FR sont proches.
        MARGIN = 0.04

        msg_len = len(message)

        # Seuil adaptatif selon la longueur du message.
        # nomic-embed-text discrimine mal les courtes phrases françaises.
        if msg_len < 50:
            # Très court → quasi certain que c'est conversationnel, sauf signal fort
            threshold_complex = MARGIN * 4   # 0.16
            threshold_tools   = MARGIN * 3   # 0.12
        elif msg_len < 120:
            threshold_complex = MARGIN * 2   # 0.08
            threshold_tools   = MARGIN * 1.5 # 0.06
        else:
            threshold_complex = MARGIN       # 0.04
            threshold_tools   = MARGIN       # 0.04

        needs_tools = (score_tools - score_simple) > threshold_tools
        is_complex  = (score_complex - score_simple) > threshold_complex

        logger.debug("[Orchestrateur] Scores sémantiques : %s (margin=%.2f)", scores, MARGIN)
        return {"needs_tools": needs_tools, "is_complex": is_complex}

    @staticmethod
    def _parse_size(size_str: str) -> int:
        """Extrait le nombre de paramètres en milliards (ex: '8B' → 8, '70B' → 70)."""
        m = re.search(r'(\d+(?:\.\d+)?)\s*[Bb]', size_str or "")
        return int(float(m.group(1))) if m else 0

    async def choose_model(self, user_message: str, available_tools: list) -> str:
        """
        Choisit le modèle le plus adapté via classification sémantique + scoring déterministe.
        Remplace l'ancien routeur LLM pour réduire la latence.
        """
        all_models = await self.get_local_models()

        blacklist = ["embed", "classification", "rerank", "vision", "deepcoder:14b", "qwen3-vl"]
        enriched = []
        for m in all_models:
            if any(w in m.lower() for w in blacklist):
                continue
            details = await self.get_model_details(m)
            if details:
                enriched.append(details)

        if not enriched:
            return "llama3.1:8b"

        # Classification sémantique du message
        classification = await self._classify_task(user_message)
        # Si des outils sont effectivement disponibles, la classification module leur nécessité
        has_tools = bool(available_tools) and classification["needs_tools"]
        is_complex = classification["is_complex"]

        # Filtre éliminatoire si outils requis :
        # garder uniquement les modèles thinking OU les ≥ 30B (avec support outils)
        candidates = enriched
        if has_tools:
            filtered = [
                m for m in enriched
                if m["can_use_tools"] and (m["can_think"] or self._parse_size(m["size"]) >= 30)
            ]
            if filtered:
                candidates = filtered
            else:
                # Fallback 1 : modèles avec outils au moins
                candidates = [m for m in enriched if m["can_use_tools"]] or enriched

        def score(model: dict) -> int:
            s = 0
            if has_tools and model["can_use_tools"]:
                s += 40
            if is_complex and model["can_think"]:
                s += 30
            size = self._parse_size(model["size"])
            if size >= 30:
                s += 20
            elif size >= 7:
                s += 10
            return s

        ranked = sorted(candidates, key=lambda m: (score(m), self._parse_size(m["size"])), reverse=True)
        chosen = ranked[0]["name"]

        logger.info(
            "[Orchestrateur] Classification : needs_tools=%s, is_complex=%s → choix : %s",
            has_tools, is_complex, chosen
        )
        return chosen
