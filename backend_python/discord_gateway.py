import os
import re
import discord
from dotenv import load_dotenv
from agent_runner import AgentRunner
from auth import init_auth_db, is_authorized, authorize_user, SECRET_PASSWORD

# 1. Chargement du Token
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# 2. Initialisation de ton cerveau IA
agent = AgentRunner()

# Dictionnaire pour lier un utilisateur Discord à une session SQLite
user_sessions = {}

# 3. Configuration des Intents (Obligatoire pour lire le texte)
intents = discord.Intents.default()
intents.message_content = True
init_auth_db() # Prépare la table de sécurité SQLite
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Se déclenche quand le bot est bien connecté aux serveurs de Discord"""
    print(f'🤖 Jean-Heude est connecté à Discord en tant que {client.user} !')

@client.event
async def on_message(message):
    """Se déclenche à chaque fois que quelqu'un poste un message"""
    # 1. On ignore les messages envoyés par le bot lui-même (sinon il se parle à l'infini)
    if message.author == client.user:
        return

    user_id = str(message.author.id)
    if message.content.startswith('/pair'):
        # On vérifie qu'il fait bien ça en Message Privé (DM) pour ne pas fuiter le mot de passe !
        if not isinstance(message.channel, discord.DMChannel):
            await message.delete() # Efface le message si c'est sur un salon public
            await message.channel.send("⚠️ Par mesure de sécurité, la commande /pair ne s'utilise qu'en Message Privé !")
            return

        parts = message.content.split()
        if len(parts) > 1 and parts[1] == SECRET_PASSWORD:
            authorize_user("discord", user_id)
            await message.channel.send("✅ **Authentification réussie.** Bonjour Maître. Mon système est à votre entière disposition.")
        else:
            await message.channel.send("❌ **Mot de passe incorrect.** Accès refusé.")
        return
    if not is_authorized("discord", user_id):
        # Si la personne n'est pas autorisée, Jean-Heude l'ignore silencieusement.
        # (On pourrait mettre un message, mais le silence évite le spam).
        return

    # ---> À partir d'ici, l'utilisateur est autorisé ! <---
    user_text = message.content.replace(f'<@{client.user.id}>', '').strip()
    # 2. On affiche "Jean-Heude est en train d'écrire..." sur Discord
    async with message.channel.typing():
        session_id = user_sessions.get(user_id)
        
        reponse_complete = ""
        
        # --- LE FILTRE ANTI-SVELTE ---
        async def discord_stream(token):
            nonlocal reponse_complete
            clean_token = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', token)
            if clean_token and not clean_token.startswith("¶"):
                reponse_complete += clean_token
                
        try:
            # 3. On fait réfléchir ton IA
            result = await agent.process_chat(user_text, session_id, discord_stream)
            user_sessions[user_id] = result["session_id"]
            
            # 4. SÉPARATION DU BROUILLON ET DE LA VERSION FINALE (Comme sur Telegram)
            parts = re.split(r'\*Utilisation de l\'outil :.*?\*', reponse_complete)
            reponse_finale = parts[-1]
            
            # 5. Nettoyage de la balise <think>
            final_text = re.sub(r'<think>.*?(</think>|$)', '', reponse_finale, flags=re.DOTALL).strip()
            
            # 6. On envoie proprement à Discord (Limite de 2000 caractères !)
            if final_text:
                for i in range(0, len(final_text), 2000):
                    await message.channel.send(final_text[i:i+2000])
            else:
                await message.channel.send("🤔 (Réflexion terminée, mais aucune réponse verbale).")
                
        except Exception as e:
            print(f"❌ Erreur Discord: {e}")
            await message.channel.send("Oups, mon cerveau a eu un court-circuit. 🧠💥")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERREUR : DISCORD_BOT_TOKEN introuvable dans le .env !")
    else:
        print("🚀 Démarrage de la Gateway Discord...")
        client.run(DISCORD_TOKEN)
