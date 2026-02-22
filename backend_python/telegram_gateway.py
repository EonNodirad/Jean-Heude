import os
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent_runner import AgentRunner
import html
from telegram.constants import ParseMode
from auth import init_auth_db, is_authorized, authorize_user, SECRET_PASSWORD

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

async def pair_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /pair MonMotDePasse"""
    chat_id = update.message.chat_id
    
    # Sécurité : On vérifie que c'est bien un message privé
    if update.message.chat.type != "private":
        await update.message.reply_text("⚠️ Par mesure de sécurité, la commande /pair ne s'utilise qu'en Message Privé !")
        return

    # On récupère les arguments tapés après /pair (ex: /pair 1234 -> args = ['1234'])
    if context.args and context.args[0] == SECRET_PASSWORD:
        authorize_user("telegram", str(chat_id))
        await update.message.reply_text("✅ **Authentification réussie.** Bonjour Maître. Mon système est à votre entière disposition.", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ **Mot de passe incorrect.** Accès refusé.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages texte envoyés au bot"""
    chat_id = update.message.chat_id
    if not is_authorized("telegram", str(chat_id)):
        return # S'il n'est pas autorisé, Jean-Heude l'ignore totalement
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
        print("❌ ERREUR : TELEGRAM_BOT_TOKEN introuvable !")
        return

    # On s'assure que la table de sécurité existe dans SQLite
    init_auth_db() 

    print("🚀 Démarrage de la Gateway Telegram...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Routeurs
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pair", pair_command)) # <--- NOUVELLE LIGNE ICI
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Jean-Heude est en ligne sur Telegram ! (Ctrl+C pour arrêter)")
    app.run_polling()

if __name__ == "__main__":
    main()
