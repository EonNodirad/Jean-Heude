import datetime

async def run(**kwargs):
    """Retourne la date et l'heure actuelle."""
    maintenant = datetime.datetime.now()
    
    # Formatage : JJ/MM/AAAA et HH:MM
    date_str = maintenant.strftime("%d/%m/%Y")
    heure_str = maintenant.strftime("%H:%M")
    
    return f"Nous sommes le {date_str} et il est {heure_str}."
