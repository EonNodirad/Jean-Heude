import aiosqlite

async def run(action: str, task_id: int, new_prompt: str = None, new_cron: str = None, new_channel: str = None) -> str:
    """Met à jour ou supprime une tâche selon l'ID."""
    try:
        async with aiosqlite.connect("memory/tasks.db") as db:
            if action == "delete":
                await db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
                await db.commit()
                return f"✅ La tâche [ID: {task_id}] a été supprimée de ton agenda de manière permanente."
            
            elif action == "update":
                # On récupère l'ancienne tâche pour ne pas écraser ce qu'on ne veut pas modifier
                cursor = await db.execute("SELECT prompt, cron_expression, channel FROM scheduled_tasks WHERE id = ?", (task_id,))
                row = await cursor.fetchone()
                
                if not row:
                    return f"❌ Erreur : Impossible de trouver la tâche avec l'ID {task_id}."
                
                # Si un champ n'est pas fourni, on garde l'ancien
                final_prompt = new_prompt if new_prompt else row[0]
                final_cron = new_cron if new_cron else row[1]
                final_channel = new_channel if new_channel else row[2]
                
                await db.execute(
                    "UPDATE scheduled_tasks SET prompt = ?, cron_expression = ?, channel = ? WHERE id = ?",
                    (final_prompt, final_cron, final_channel, task_id)
                )
                await db.commit()
                return f"✅ La tâche [ID: {task_id}] a été mise à jour avec succès dans l'agenda."
                
            else:
                return "❌ Action non reconnue. Utilise 'update' ou 'delete'."
    except Exception as e:
        return f"❌ Erreur lors de la modification de l'agenda : {e}"
