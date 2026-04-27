"""
Questionnaires pré-test et post-test pour l'expérimentation.
Items basés sur :
- MAI (Metacognitive Awareness Inventory, Schraw & Dennison 1994) — version réduite
- ASE (Academic Self-Efficacy, Pintrich) — auto-efficacité face au STI
- SUS (System Usability Scale) — pour le post-test uniquement
"""

# ─── Pré-test (à remplir AVANT la 1ère interaction avec l'app) ────────────────
PRETEST_ITEMS = {
    "metacognition": {
        "titre": "Conscience métacognitive",
        "description": "Indiquez à quel point chaque affirmation vous correspond (1=jamais, 5=toujours)",
        "questions": [
            "Avant de poser une question, je réfléchis à ce que je veux exactement savoir",
            "Je sais reformuler une question qui n'a pas reçu une bonne réponse",
            "Je suis conscient(e) des informations qui manquent dans mes questions",
            "Je peux évaluer si une réponse répond vraiment à ma question",
            "Je m'adapte selon le type d'outil que j'utilise (livre, prof, IA)",
        ],
    },
    "auto_efficacite": {
        "titre": "Auto-efficacité face aux outils IA / STI",
        "description": "À quel point êtes-vous d'accord avec ces affirmations (1=pas du tout, 5=tout à fait)",
        "questions": [
            "Je sais formuler des questions claires pour un outil d'IA",
            "Je sais comment obtenir une réponse précise d'un assistant IA",
            "Je peux évaluer la qualité des réponses d'un STI",
            "Je suis à l'aise pour interagir avec un système intelligent",
            "Je sais ce que je peux et ne peux pas attendre d'une IA",
        ],
    },
    "experience": {
        "titre": "Expérience préalable",
        "description": "Vos expériences passées avec les IA et STI",
        "questions_libres": [
            ("frequence_usage", "À quelle fréquence utilisez-vous des IA (ChatGPT, Claude, etc.) ?",
             ["Jamais", "Rarement", "1-2 fois par semaine", "Quotidiennement", "Plusieurs fois par jour"]),
            ("usage_principal", "Pour quel usage principal ?",
             ["Études", "Travail", "Loisir/curiosité", "Pas d'usage", "Autre"]),
        ],
    },
}

# ─── Post-test (à remplir APRÈS la dernière interaction, en fin de 6 semaines) ──
POSTTEST_ITEMS = {
    "metacognition": {
        "titre": "Conscience métacognitive (après expérimentation)",
        "description": "Mêmes questions que le pré-test, pour mesurer l'évolution",
        "questions": PRETEST_ITEMS["metacognition"]["questions"],  # mêmes items
    },
    "auto_efficacite": {
        "titre": "Auto-efficacité face aux outils IA / STI (après)",
        "description": "Évaluez à nouveau ces affirmations",
        "questions": PRETEST_ITEMS["auto_efficacite"]["questions"],
    },
    "sus": {
        "titre": "Utilisabilité du système (SUS)",
        "description": "À quel point êtes-vous d'accord (1=pas du tout, 5=tout à fait)",
        "questions": [
            "Je pense que j'aimerais utiliser ce système fréquemment",
            "J'ai trouvé ce système inutilement complexe",
            "J'ai trouvé ce système facile à utiliser",
            "Je pense avoir besoin de l'aide d'un technicien pour utiliser ce système",
            "J'ai trouvé que les fonctions du système sont bien intégrées",
            "Je pense qu'il y a trop d'incohérences dans ce système",
            "J'imagine que la plupart des gens apprendraient rapidement à utiliser ce système",
            "J'ai trouvé ce système très lourd à utiliser",
            "Je me suis senti(e) en confiance en utilisant ce système",
            "J'ai eu besoin d'apprendre beaucoup de choses avant de pouvoir utiliser ce système",
        ],
    },
    "ressenti": {
        "titre": "Ressenti général",
        "description": "Vos impressions sur l'expérience",
        "questions_libres": [
            ("apport_global", "L'application vous a-t-elle aidé(e) à mieux formuler vos questions ?",
             ["Pas du tout", "Un peu", "Moyennement", "Beaucoup", "Énormément"]),
            ("recommandation", "Recommanderiez-vous cet outil à un(e) camarade ?",
             ["Non, jamais", "Plutôt non", "Peut-être", "Plutôt oui", "Oui, certainement"]),
            ("commentaire_libre", "Vos commentaires libres (optionnel)", "text"),
        ],
    },
}


def calculer_score_metacognition(reponses: list) -> float:
    """Score MAI réduit sur 5 points (moyenne des items)."""
    if not reponses:
        return 0
    return round(sum(reponses) / len(reponses), 2)


def calculer_score_auto_efficacite(reponses: list) -> float:
    """Score auto-efficacité sur 5 points."""
    if not reponses:
        return 0
    return round(sum(reponses) / len(reponses), 2)


def calculer_score_sus(reponses: list) -> float:
    """
    Score SUS officiel sur 100.
    Items impairs (1,3,5,7,9) : score-1
    Items pairs (2,4,6,8,10)  : 5-score
    Total × 2.5
    """
    if len(reponses) != 10:
        return 0
    total = 0
    for i, r in enumerate(reponses):
        if i % 2 == 0:  # items impairs (index pair en 0-based)
            total += r - 1
        else:           # items pairs
            total += 5 - r
    return round(total * 2.5, 1)
