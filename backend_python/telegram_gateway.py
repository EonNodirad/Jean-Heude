import os
import re
import html
import base64
import uuid
import httpx  # 👈 On utilise httpx pour appeler ton serveur STT
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from agent_runner import AgentRunner
from auth import init_auth_db, create_global_account, link_platform_account, get_global_user_id

# 1. Chargement de l'environnement
load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
STT_SERVER_URL = os.environ.get("STT_SERVER_URL", "http://localhost:8001/transcribe") # 👈 Ton serveur STT

# 2. Initialisations
agent = AgentRunner()
user_sessions: dict[int, int] = {} 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    await update.message.reply_text(
        "Salut ! Je suis J.E.A.N-H.E.U.D.E, prêt à t'aider depuis Telegram. 🤖\n\n"
        "🔒 Pour me parler, tu dois être connecté.\n"
        "👉 Tape `/register <pseudo> <motdepasse>` pour créer un compte.\n"
        "👉 Ou `/login <pseudo> <motdepasse>` si tu as déjà un compte global."
    )

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.chat: return
    chat_id = update.message.chat_id
    if update.message.chat.type != "private":
        await update.message.reply_text("⚠️ Par mesure de sécurité, crée ton compte en Message Privé !")
        return

    args = context.args or []
    if len(args) == 2:
        pseudo, mdp = args[0], args[1]
        if create_global_account(pseudo, mdp):
            link_platform_account("telegram", str(chat_id), pseudo, mdp)
            await update.message.reply_text(f"✅ **Compte {pseudo} créé et lié !** Bonjour Maître.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ **Ce pseudo est déjà pris.**", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Usage correct : `/register <pseudo> <motdepasse>`", parse_mode="Markdown")

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.chat: return
    chat_id = update.message.chat_id
    if update.message.chat.type != "private":
        await update.message.reply_text("⚠️ Par mesure de sécurité, connecte-toi en Message Privé !")
        return

    args = context.args or []
    if len(args) == 2:
        pseudo, mdp = args[0], args[1]
        if link_platform_account("telegram", str(chat_id), pseudo, mdp):
            await update.message.reply_text(f"🔗 **Rebonjour {pseudo} !** Ton compte est maintenant lié à ce Telegram.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ **Identifiants incorrects.**", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Usage correct : `/login <pseudo> <motdepasse>`", parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère le Texte, l'Audio (Vocal via Serveur STT externe) et la Vision (Photos/Documents Image)"""
    if not update.message or not update.message.chat: return
        
    chat_id = update.message.chat_id
    
    # 🎯 1. VÉRIFICATION DE L'IDENTITÉ GLOBALE
    global_user_id = get_global_user_id("telegram", str(chat_id))
    if not global_user_id:
        await update.message.reply_text("🔒 Tu n'es pas connecté. Tape `/login <pseudo> <mdp>` ou `/register <pseudo> <mdp>`.")
        return 
        
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    session_id = user_sessions.get(chat_id)
    
    user_text = ""
    image_b64 = None
    image_path = None
    file_to_delete = None

    try:
        voice = update.message.voice
        photo = update.message.photo
        document = update.message.document

        # ==========================================
        # 🎙️ CAS 1 : MESSAGE VOCAL
        # ==========================================
        if voice is not None:
            file_id = voice.file_id
            tg_file = await context.bot.get_file(file_id)
            
            temp_audio_path = f"temp_audio_{uuid.uuid4().hex}.ogg"
            file_to_delete = temp_audio_path
            
            await tg_file.download_to_drive(temp_audio_path)
            await update.message.reply_text("*(J'écoute ton vocal... 🎧)*", parse_mode="Markdown")
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    with open(temp_audio_path, "rb") as f:
                        files = {"file": (temp_audio_path, f, "audio/ogg")}
                        response = await client.post(STT_SERVER_URL, files=files)
                        
                        if response.status_code == 200:
                            data = response.json()
                            user_text = data.get("text", "").strip()
                        else:
                            raise Exception(f"Statut STT: {response.status_code}")
            except Exception as stt_err:
                print(f"❌ Erreur connexion serveur STT: {stt_err}")
                await update.message.reply_text("Désolé, mon module auditif (Serveur STT) est hors ligne. 🙉")
                return
            
            if not user_text:
                await update.message.reply_text("Je n'ai pas compris ce vocal. Peux-tu répéter ?")
                return

        # ==========================================
        # 🖼️ CAS 2 : PHOTO OU DOCUMENT (Image)
        # ==========================================
        elif photo is not None and len(photo) > 0:
            file_id = photo[-1].file_id
            tg_file = await context.bot.get_file(file_id)
            
            temp_image_path = f"temp_img_{uuid.uuid4().hex}.jpg"
            image_path = temp_image_path
            file_to_delete = temp_image_path
            
            await tg_file.download_to_drive(temp_image_path)
            with open(temp_image_path, "rb") as img_file:
                image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                
            user_text = getattr(update.message, "caption", None)
            if not isinstance(user_text, str) or not user_text.strip():
                user_text = "Peux-tu décrire cette image en détail ?"

        elif document is not None:
            mime = getattr(document, "mime_type", "")
            if not isinstance(mime, str) or not mime.startswith("image/"):
                await update.message.reply_text("⚠️ Je ne sais lire que les images pour le moment (JPEG, PNG).")
                return
                
            file_id = document.file_id
            tg_file = await context.bot.get_file(file_id)
            
            temp_image_path = f"temp_img_{uuid.uuid4().hex}.jpg"
            image_path = temp_image_path
            file_to_delete = temp_image_path
            
            await tg_file.download_to_drive(temp_image_path)
            with open(temp_image_path, "rb") as img_file:
                image_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                
            user_text = getattr(update.message, "caption", None)
            if not isinstance(user_text, str) or not user_text.strip():
                user_text = "Peux-tu décrire cette image en détail ?"

        # ==========================================
        # 📝 CAS 3 : TEXTE CLASSIQUE
        # ==========================================
        else:
            user_text = getattr(update.message, "text", "")
            if not user_text:
                return

        # ------------------------------------------
        # 🧠 ENVOI AU CERVEAU (AgentRunner)
        # ------------------------------------------
        reponse_complete = ""
        
        async def telegram_stream(token: str):
            nonlocal reponse_complete
            clean_token = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', token)
            if clean_token and not clean_token.startswith("¶"):
                reponse_complete += clean_token
                
        if image_b64:
            result = await agent.process_multimodal_chat(user_text, image_b64, image_path, session_id, global_user_id, telegram_stream)
        else:
            result = await agent.process_chat(user_text, session_id, global_user_id, telegram_stream)
            
        # 🛡️ GARDE PYRIGHT POUR LE DICTIONNAIRE RESULT
        if isinstance(result, dict):
            new_session_id = result.get("session_id")
            if isinstance(new_session_id, int):
                user_sessions[chat_id] = new_session_id
        
        parts = re.split(r'\*Utilisation de l\'outil :.*?\*', reponse_complete)
        reponse_finale = parts[-1]
        final_text = re.sub(r'<think>.*?(</think>|$)', '', reponse_finale, flags=re.DOTALL).strip()
        
        final_text = html.escape(final_text)
        final_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', final_text)
        final_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', final_text)

        if final_text:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(final_text[i:i+4000], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("🤔 (Réflexion terminée, mais aucune réponse verbale).")
            
    except Exception as e:
        print(f"❌ Erreur Telegram: {e}")
        await update.message.reply_text("Oups, mon cerveau a eu un court-circuit. 🧠💥")
        
    finally:
        # 🧹 NETTOYAGE
        if file_to_delete and os.path.exists(file_to_delete):
            os.remove(file_to_delete)

def main():
    if not TELEGRAM_TOKEN:
        print("❌ ERREUR : TELEGRAM_BOT_TOKEN introuvable !")
        return

    init_auth_db() 
    print("🚀 Démarrage de la Gateway Telegram...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register_command)) 
    app.add_handler(CommandHandler("login", login_command))
    
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.VOICE | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND, 
        handle_message
    ))

    print("🤖 Jean-Heude est en ligne sur Telegram ! (Ctrl+C pour arrêter)")
    app.run_polling()

if __name__ == "__main__":
    main()