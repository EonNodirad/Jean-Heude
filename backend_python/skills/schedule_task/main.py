import aiosqlite

async def run(prompt: str, cron_expression: str, channel: str) -> str:
    """Enregistre la tâche dans l'agenda de Jean-Heude."""
    
    # On s'assure que la table existe
    async with aiosqlite.connect("memory/tasks.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                channel TEXT NOT NULL
            )
        """)
        
        # On insère la nouvelle mission
        await db.execute(
            "INSERT INTO scheduled_tasks (prompt, cron_expression, channel) VALUES (?, ?, ?)",
            (prompt, cron_expression, channel)
        )
        await db.commit()
        
    return f"✅ Tâche planifiée avec succès ! J'exécuterai '{prompt}' avec le CRON '{cron_expression}' sur le canal '{channel}'."
