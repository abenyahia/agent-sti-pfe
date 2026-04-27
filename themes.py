"""
Thèmes pédagogiques — contextes disciplinaires différents.
Chaque thème adapte les prompts du diagnostic et de la reformulation.
"""

THEMES = {
    "Enseignement": {
        "icon": "📚",
        "description": "Apprentissage académique : concepts, théories, exercices, méthodes disciplinaires",
        "system_hint": (
            "L'étudiant pose une question d'apprentissage académique "
            "(cours, théorie, exercice, méthodologie disciplinaire). "
            "Adapte la reformulation pour cibler la compréhension conceptuelle, "
            "l'application de méthodes, ou l'analyse critique selon le niveau Bloom."
        ),
        "bloom_strategies": {
            1: "Définition conceptuelle avec schéma mental et exemples du cours",
            2: "Explication du fonctionnement illustrée sur un exercice type",
            3: "Application pas à pas de la méthode sur un exemple précis",
            4: "Analyse structurée avec comparaison de méthodes",
            5: "Évaluation critique des approches avec critères justifiés",
            6: "Synthèse créative produisant une nouvelle méthode/solution",
        },
        "exemple_question": "Explique-moi comment fonctionne le tri rapide",
    },
    "Soft Skills / Résolution de problème": {
        "icon": "🧩",
        "description": "Compétences transversales : résolution de problèmes, communication, leadership, gestion du temps, esprit critique",
        "system_hint": (
            "L'étudiant pose une question de soft skills ou de résolution de problème "
            "(communication, leadership, prise de décision, gestion d'équipe, "
            "négociation, créativité, résolution de conflits). "
            "Adapte la reformulation pour cibler des réponses pratiques avec "
            "études de cas, mises en situation, frameworks d'action."
        ),
        "bloom_strategies": {
            1: "Définition du concept comportemental avec exemple de situation",
            2: "Explication de la compétence illustrée par un mini-cas réel",
            3: "Mise en situation concrète avec étapes d'action détaillées",
            4: "Analyse d'un cas difficile avec grille de lecture structurée",
            5: "Évaluation de plusieurs stratégies face à un dilemme avec pros/cons",
            6: "Création d'un plan d'action personnalisé pour une situation complexe",
        },
        "exemple_question": "Comment gérer un conflit avec un collègue difficile ?",
    },
}


def get_theme(name: str) -> dict:
    """Retourne la configuration d'un thème (avec fallback)."""
    return THEMES.get(name, THEMES["Enseignement"])


def get_bloom_strategy(theme_name: str, bloom_level: int) -> str:
    """Retourne la stratégie Bloom adaptée au thème."""
    theme = get_theme(theme_name)
    return theme["bloom_strategies"].get(bloom_level, theme["bloom_strategies"][2])
