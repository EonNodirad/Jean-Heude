# Ancres sémantiques pour la classification des messages.
# Utilisé par IA.py (Orchestrator._classify_task) pour choisir le bon modèle LLM.
# ~40 exemples par catégorie, majoritairement en français.

TASK_ANCHORS: dict[str, list[str]] = {

    # =========================================================
    # NEEDS_TOOLS : la tâche nécessite un outil externe
    # (web, terminal, fichiers, APIs, bots, météo, etc.)
    # =========================================================
    "needs_tools": [
        # Recherche web
        "cherche sur internet les dernières nouvelles sur",
        "fais une recherche sur le web à propos de",
        "trouve des informations récentes sur",
        "recherche en ligne les actualités concernant",
        "donne-moi les résultats d'une recherche web sur",
        "quelles sont les dernières infos sur",
        "trouve-moi des sources sur ce sujet",
        "va chercher sur internet ce que c'est",
        "fais une recherche brave sur",
        "surveille ce site web et dis-moi s'il change",

        # Terminal / commandes système
        "exécute cette commande dans le terminal",
        "lance ce script bash",
        "ouvre un terminal et tape",
        "exécute ce programme en ligne de commande",
        "fais tourner ce processus",
        "démarre ce service système",
        "arrête ce processus",
        "quelle est la liste des processus actifs",
        "installe ce paquet avec apt",
        "lance cette commande sudo",

        # Fichiers / système de fichiers
        "lis le contenu de ce fichier",
        "écris ces données dans un fichier",
        "liste les fichiers du dossier",
        "crée un nouveau dossier",
        "déplace ce fichier vers",
        "supprime ce fichier",
        "montre-moi l'arborescence du projet",
        "copie ce répertoire",
        "modifie ce fichier de configuration",
        "archive ce dossier en zip",

        # APIs / données temps réel
        "quelle est la météo aujourd'hui à",
        "quel temps fait-il à Paris",
        "quel est le cours actuel de l'action",
        "donne-moi le prix du bitcoin maintenant",
        "récupère les données de cette API",
        "envoie un message sur Telegram",
        "poste ce message sur Discord",
        "notifie-moi quand ce site est disponible",

        # Anglais
        "search the web for information about",
        "run this terminal command",
        "fetch data from the internet",
        "read this file and tell me what's in it",
        "execute this script",
    ],

    # =========================================================
    # COMPLEX_REASONING : tâche intellectuelle exigeante
    # (code, maths, analyse, rédaction, architecture, etc.)
    # =========================================================
    "complex_reasoning": [
        # Code
        "écris-moi un script Python qui fait",
        "débogue ce code et explique l'erreur",
        "comment fonctionne cet algorithme",
        "optimise cette fonction pour qu'elle soit plus rapide",
        "refactorise ce code pour le rendre plus lisible",
        "explique-moi ce que fait cette portion de code",
        "implémente cette fonctionnalité en Python",
        "crée une classe avec ces méthodes",
        "écris les tests unitaires pour cette fonction",
        "trouve le bug dans ce code",
        "convertis ce code JavaScript en Python",
        "comment gérer cette exception proprement",

        # Mathématiques / logique
        "résous ce problème de mathématiques",
        "calcule l'intégrale de cette fonction",
        "démontre ce théorème",
        "prouve par récurrence que",
        "simplifie cette expression algébrique",
        "résous ce système d'équations",
        "explique la complexité algorithmique de",
        "calcule la dérivée de",

        # Analyse / raisonnement
        "analyse ces données et donne-moi les tendances",
        "compare ces deux approches et dis-moi laquelle est meilleure",
        "résume ce long document",
        "explique en détail le fonctionnement de",
        "quels sont les avantages et inconvénients de",
        "fais une analyse critique de",
        "donne-moi une explication approfondie de",
        "identifie les points clés de ce texte",

        # Rédaction / conception
        "rédige un rapport complet sur",
        "écris une documentation technique pour",
        "conçois une architecture logicielle pour",
        "propose un plan de projet pour",
        "rédige un email professionnel expliquant",
        "écris un article de blog sur",
        "crée un prompt système détaillé pour",

        # Anglais
        "write a Python function that",
        "debug this code and explain what's wrong",
        "explain how this algorithm works",
        "analyze this data and find patterns",
        "design a software architecture for",
    ],

    # =========================================================
    # SIMPLE_REPLY : conversation légère, question courte
    # (salutations, questions de base, bavardage, confirmations)
    # =========================================================
    "simple_reply": [
        # Salutations
        "bonjour",
        "bonsoir",
        "salut",
        "hey",
        "coucou",
        "bonjour Jean-Heude",
        "salut comment tu vas",
        "ça va ?",
        "comment ça va aujourd'hui",
        "tu vas bien ?",

        # Questions simples sur l'assistant
        "comment tu t'appelles",
        "c'est quoi ton nom",
        "tu es qui",
        "tu peux m'aider",
        "qu'est-ce que tu sais faire",
        "tu es une IA ?",
        "présente-toi",
        "tu es capable de quoi",

        # Réponses courtes / confirmations
        "merci",
        "merci beaucoup",
        "super",
        "parfait",
        "ok",
        "d'accord",
        "compris",
        "pas de problème",
        "c'est bon",
        "oui",
        "non",
        "peut-être",
        "je sais pas",
        "bonne idée",

        # Questions triviales
        "quelle heure est-il",
        "quel jour on est",
        "on est quel mois",
        "c'est quand Noël",
        "raconte-moi une blague",
        "dis-moi quelque chose d'amusant",
        "tu as une anecdote",

        # Anglais
        "hello",
        "hi there",
        "thanks",
        "what's your name",
        "tell me a joke",
    ],
}
