import asyncio

async def run(command: str) -> str:
    """Exécute une commande terminal de manière asynchrone avec un filet de sécurité."""
    print(f"⚠️ [Skill Terminal] Exécution de la commande : {command}")
    
    try:
        # Lancement du processus en arrière-plan
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # ⏱️ TIMEOUT DE SÉCURITÉ : 30 secondes maximum
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            process.kill()
            return f"❌ Erreur : La commande '{command}' a pris trop de temps (plus de 30s) et a été tuée. Ne lance pas de processus bloquants."

        # Décodage propre (gère les accents sous Windows/Linux)
        output = stdout.decode('utf-8', errors='replace').strip()
        error_output = stderr.decode('utf-8', errors='replace').strip()

        # ✂️ TRONCATURE : On limite à 2000 caractères pour ne pas faire exploser la fenêtre de contexte LLM (ex: si l'IA fait 'dir C:\')
        max_length = 2000

        if process.returncode == 0:
            if not output:
                return "✅ Commande exécutée avec succès (aucune sortie console)."
            
            result = output[:max_length] + ("\n...[TRONQUÉ]" if len(output) > max_length else "")
            return f"✅ Succès:\n{result}"
        else:
            err_result = error_output[:max_length] + ("\n...[TRONQUÉ]" if len(error_output) > max_length else "")
            return f"❌ Erreur (Code {process.returncode}):\n{err_result}"

    except Exception as e:
        return f"❌ Erreur inattendue du système : {e}"
