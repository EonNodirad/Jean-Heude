import os
import re
import discord
import base64
import uuid
import httpx
from dotenv import load_dotenv
from pathlib import Path
from agent_runner import AgentRunner
from auth import init_auth_db, create_global_account, link_platform_account, get_global_user_id

# 1. Chargement de l'environnement
load_dotenv()
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
STT_SERVER_URL = os.environ.get("STT_SERVER_URL", "http://localhost:8001/transcribe")

# 2. Initialisation
agent = AgentRunner()
user_sessions: dict[int, int] = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    init_auth_db()
    bot_name = client.user.name if client.user else "Bot"
    print(f'🤖 Jean-Heude est connecté à Discord en tant que {bot_name} !')

@client.event
async def on_message(message: discord.Message):
    """Se déclenche à chaque fois que quelqu'un poste un message"""
    
    # 🛡️ Gardes Pyright et sécurité basique
    if not message.author or message.author == client.user:
        return

    discord_user_id_str = str(message.author.id)
    discord_user_id_int = message.author.id
    msg_content = str(message.content or "").strip()

    # ==========================================
    # 🔐 GESTION DE L'AUTHENTIFICATION (/register et /login)
    # ==========================================
    if msg_content.startswith('/register'):
        if not isinstance(message.channel, discord.DMChannel):
            try: await message.delete() 
            except: pass
            await message.channel.send("⚠️ Par mesure de sécurité, crée ton compte en Message Privé !")
            return

        parts = msg_content.split()
        if len(parts) == 3:
            pseudo, mdp = parts[1], parts[2]
            if create_global_account(pseudo, mdp):
                link_platform_account("discord", discord_user_id_str, pseudo, mdp)
                await message.channel.send(f"✅ **Compte {pseudo} créé et lié !** Bonjour Maître.")
            else:
                await message.channel.send("❌ **Ce pseudo est déjà pris.**")
        else:
            await message.channel.send("⚠️ Usage : `/register <pseudo> <motdepasse>`")
        return

    if msg_content.startswith('/login'):
        if not isinstance(message.channel, discord.DMChannel):
            try: await message.delete() 
            except: pass
            await message.channel.send("⚠️ Par mesure de sécurité, connecte-toi en Message Privé !")
            return

        parts = msg_content.split()
        if len(parts) == 3:
            pseudo, mdp = parts[1], parts[2]
            if link_platform_account("discord", discord_user_id_str, pseudo, mdp):
                await message.channel.send(f"🔗 **Rebonjour {pseudo} !** Ton compte est maintenant lié à ce Discord.")
            else:
                await message.channel.send("❌ **Identifiants incorrects.**")
        else:
            await message.channel.send("⚠️ Usage : `/login <pseudo> <motdepasse>`")
        return

    # ==========================================
    # 🎯 VÉRIFICATION DE L'IDENTITÉ GLOBALE
    # ==========================================
    is_private = isinstance(message.channel, discord.DMChannel)
    bot_mention = f'<@{client.user.id}>' if client.user else ''
    
    if is_private:
        # 👤 CAS 1 : MESSAGE PRIVÉ (Accès au cerveau personnel ou invité)
        global_user_id = get_global_user_id("discord", discord_user_id_str)
        if not global_user_id:
            global_user_id = f"guest_discord_{discord_user_id_str}"
    else:
        # 👥 CAS 2 : SERVEUR PUBLIC (Accès au cerveau du serveur UNIQUEMENT)
        if not message.guild:
            return
            
        # On ignore s'il n'est pas mentionné
        if bot_mention not in msg_content:
            return
            
        # SÉCURITÉ : La mémoire utilisée sera CELLE DU SERVEUR
        global_user_id = f"serveur_discord_{message.guild.id}"

    # ---> À partir d'ici, le bot va répondre ! <---
    # On enlève la mention "@Jean-Heude" du texte
    user_text = msg_content.replace(bot_mention, '').strip()
    

    if global_user_id.startswith("serveur_discord_"):
        user_text = f"[{message.author.display_name} dit] : {user_text}"
    
    session_id = user_sessions.get(discord_user_id_int)
    image_b64 = None
    image_path = None
    file_to_delete = None

    # ==========================================
    # 📎 GESTION DES PIÈCES JOINTES (Voix & Images)
    # ==========================================
    if message.attachments:
        attachment = message.attachments[0] # On prend la première pièce jointe
        mime = str(attachment.content_type or "")
        
        # 🎙️ CAS 1 : MESSAGE VOCAL OU FICHIER AUDIO
        # (Discord envoie souvent les vocaux en video/ogg ou audio/ogg)
        if mime.startswith("audio/") or mime.startswith("video/ogg") or attachment.filename.endswith(".ogg"):
            temp_audio_path = f"temp_discord_audio_{uuid.uuid4().hex}.ogg"
            file_to_delete = temp_audio_path
            
            await attachment.save(Path(temp_audio_path))
            
            # Message temporaire (optionnel)
            temp_msg = await message.channel.send("*(J'écoute ton vocal... 🎧)*")
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as http_client:
                    with open(temp_audio_path, "rb") as f:
                        files = {"file": (temp_audio_path, f, "audio/ogg")}
                        response = await http_client.post(STT_SERVER_URL, files=files)
                        
                        if response.status_code == 200:
                            data = response.json()
                            transcribed_text = data.get("text", "").strip()
                            # On ajoute la transcription au texte tapé (s'il y en a)
                            user_text = f"{user_text}\n[Audio Transcrit]: {transcribed_text}".strip()
                        else:
                            raise Exception(f"Statut STT: {response.status_code}")
            except Exception as stt_err:
                print(f"❌ Erreur serveur STT: {stt_err}")
                await message.channel.send("Désolé, mon module auditif est hors ligne. 🙉")
                return
            finally:
                try: await temp_msg.delete() 
                except: pass

        # 🖼️ CAS 2 : IMAGE (Photo)
        elif mime.startswith("image/"):
            temp_image_path = f"temp_discord_img_{uuid.uuid4().hex}.jpg"
            image_path = temp_image_path
            file_to_delete = temp_image_path
            
            await attachment.save(Path(temp_image_path))
            with open(temp_image_path, "rb") as img_file:
                image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                
            if not user_text:
                user_text = "Peux-tu décrire cette image en détail ?"

    # ==========================================
    # 🧠 ENVOI AU CERVEAU (AgentRunner)
    # ==========================================
    # Si le message est totalement vide (ni texte, ni image, ni audio), on ignore
    if not user_text and not image_b64:
        return

    async with message.channel.typing():
        reponse_complete = ""
        
        async def discord_stream(token: str):
            nonlocal reponse_complete
            clean_token = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', token)
            if clean_token and not clean_token.startswith("¶"):
                reponse_complete += clean_token
                
        try:
            if image_b64:
                result = await agent.process_multimodal_chat(user_text, image_b64, image_path, session_id, global_user_id, discord_stream)
            else:
                result = await agent.process_chat(user_text, session_id, global_user_id, discord_stream)
                
            # 🛡️ Mise à jour de la session
            if isinstance(result, dict):
                new_session_id = result.get("session_id")
                if isinstance(new_session_id, int):
                    user_sessions[discord_user_id_int] = new_session_id
            
            # Nettoyage de la balise de réflexion
            parts = re.split(r'\*Utilisation de l\'outil :.*?\*', reponse_complete)
            reponse_finale = parts[-1]
            final_text = re.sub(r'<think>.*?(</think>|$)', '', reponse_finale, flags=re.DOTALL).strip()
            
            # 6. On envoie proprement à Discord (Limite stricte de 2000 caractères !)
            # Note : Discord gère nativement le Markdown (**gras**, *italique*), pas besoin de HTML ici.
            if final_text:
                for i in range(0, len(final_text), 2000):
                    await message.channel.send(final_text[i:i+2000])
            else:
                await message.channel.send("🤔 (Réflexion terminée, mais aucune réponse verbale).")
                
        except Exception as e:
            print(f"❌ Erreur Discord: {e}")
            await message.channel.send("Oups, mon cerveau a eu un court-circuit. 🧠💥")
            
        finally:
            # 🧹 NETTOYAGE DES FICHIERS
            if file_to_delete and os.path.exists(file_to_delete):
                os.remove(file_to_delete)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ ERREUR : DISCORD_BOT_TOKEN introuvable dans le .env !")
    else:
        print("🚀 Démarrage de la Gateway Discord...")
        client.run(DISCORD_TOKEN)