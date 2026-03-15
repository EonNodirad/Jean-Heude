import aiosqlite

async def run() -> str:
    """Lit l'agenda et renvoie la liste des tâches avec leurs IDs."""
    try:
        async with aiosqlite.connect("memory/tasks.db") as db:
            # On crée la table si elle n'existe pas encore
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    channel TEXT NOT NULL
                )
            """)
            
            cursor = await db.execute("SELECT id, prompt, cron_expression, channel FROM scheduled_tasks")
            rows = await cursor.fetchall()
            
            if not rows:
                return "📭 Ton agenda est actuellement vide. Aucune tâche n'est planifiée."
                
            result = "📅 Voici les tâches actuellement planifiées dans ton agenda :\n"
            for row in rows:
                result += f"- [ID: {row[0]}] | Action: '{row[1]}' | CRON: '{row[2]}' | Canal: '{row[3]}'\n"
            return result
            
    except Exception as e:
        return f"❌ Erreur lors de la lecture de l'agenda : {e}"
