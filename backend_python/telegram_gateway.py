import os
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent_runner import AgentRunner
import html
from telegram.constants import ParseMode

# 1. Chargement du Token
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 2. Initialisation de ton cerveau IA
agent = AgentRunner()

# Dictionnaire pour lier un utilisateur Telegram à une session SQLite
user_sessions = {} 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /start"""
    await update.message.reply_text(
        "Salut ! Je suis J.E.A.N-H.E.U.D.E, prêt à t'aider depuis Telegram. 🤖\n"
        "Pose-moi ta question !"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages texte envoyés au bot"""
    chat_id = update.message.chat_id
    user_text = update.message.text
    
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    session_id = user_sessions.get(chat_id)
    
    reponse_complete = ""
    
    # --- LE FILTRE ANTI-SVELTE ---
    async def telegram_stream(token):
        nonlocal reponse_complete
        # 1. On détruit les balises audio
        clean_token = re.sub(r'\|\|AUDIO_ID:.*?\|\|', '', token)
        # 2. On ignore les morceaux qui commencent par ¶ (destinés au front-end)
        if clean_token and not clean_token.startswith("¶"):
            reponse_complete += clean_token
            
    try:
        result = await agent.process_chat(user_text, session_id, telegram_stream)
        user_sessions[chat_id] = result["session_id"]
        
        # 3. SÉPARATION DU BROUILLON ET DE LA VERSION FINALE
        # On coupe le texte géant à chaque fois qu'on voit "*Utilisation de l'outil :...*"
        # Et on ne garde que le tout dernier morceau (parts[-1]) qui contient la vraie réponse finale !
        parts = re.split(r'\*Utilisation de l\'outil :.*?\*', reponse_complete)
        reponse_finale = parts[-1]
        
        # 4. On nettoie le <think> UNIQUEMENT sur cette version finale
        final_text = re.sub(r'<think>.*?(</think>|$)', '', reponse_finale, flags=re.DOTALL).strip()
        
        # --- 🎨 NOUVEAU : Rendu visuel propre pour Telegram ---
        # 1. On protège les caractères spéciaux (<, >) pour que Telegram ne panique pas
        final_text = html.escape(final_text)
        # 2. On transforme le gras (**texte**) en balise HTML <b>texte</b>
        final_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', final_text)
        # 3. On transforme l'italique (*texte*) en balise HTML <i>texte</i>
        final_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', final_text)

        # 5. On envoie proprement à Telegram avec le mode HTML activé !
        if final_text:
            for i in range(0, len(final_text), 4000):
                await update.message.reply_text(
                    final_text[i:i+4000], 
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.message.reply_text("🤔 (Réflexion terminée, mais aucune réponse verbale).")
            
    except Exception as e:
        print(f"❌ Erreur Telegram: {e}")
        await update.message.reply_text("Oups, mon cerveau a eu un court-circuit. 🧠💥")

def main():
    if not TELEGRAM_TOKEN:
        print("❌ ERREUR : TELEGRAM_BOT_TOKEN introuvable dans le .env !")
        return

    print("🚀 Démarrage de la Gateway Telegram...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Jean-Heude est en ligne sur Telegram ! (Ctrl+C pour arrêter)")
    app.run_polling()

if __name__ == "__main__":
    main()
