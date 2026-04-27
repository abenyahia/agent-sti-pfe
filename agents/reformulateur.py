import anthropic
from dotenv import load_dotenv
from config import get_api_key
from themes import get_theme, get_bloom_strategy

load_dotenv()

PROFILS_ACADEMIQUES = {
    "Bac":       "lycéen en terminale, vocabulaire simple, exemples du quotidien, aucune notion universitaire supposée",
    "Licence 1": "étudiant L1, premières notions universitaires, exemples simples et concrets",
    "Licence 2": "étudiant L2, bases disciplinaires acquises, commence à maîtriser les concepts fondamentaux",
    "Licence 3": "étudiant L3, bonne maîtrise de la discipline, peut aborder des problèmes complexes",
    "Master 1":  "étudiant M1, maîtrise avancée, capable d'analyse critique et de synthèse",
    "Master 2":  "étudiant M2 ou futur professionnel, niveau expert, problèmes ouverts et recherche",
    "Doctorat":  "doctorant, niveau recherche, questions ouvertes, littérature scientifique, rigueur formelle",
}


def reformuler(requete_originale: str, diagnostic: dict,
               niveau_academique: str = "Licence 1",
               theme: str = "Enseignement") -> str:
    bloom_actuel = diagnostic.get("bloom_level", 2)
    bloom_cible  = min(bloom_actuel + 1, 6)
    strategie    = get_bloom_strategy(theme, bloom_cible)
    theme_config = get_theme(theme)
    domaine      = diagnostic.get("detected_domain", "général")
    contexte_manquant = ", ".join(diagnostic.get("missing_context", []))
    profil       = PROFILS_ACADEMIQUES.get(niveau_academique, PROFILS_ACADEMIQUES["Licence 1"])

    system = f"""Tu es un tuteur pédagogique expert en ingénierie pédagogique.
Reformule la requête de l'étudiant pour qu'elle génère une réponse plus formative.

CONTEXTE THÉMATIQUE : {theme} — {theme_config['description']}
{theme_config['system_hint']}

Profil de l'étudiant : {profil}
Niveau Bloom cible : {bloom_cible} — {strategie}
Domaine détecté : {domaine}
Contexte à enrichir : {contexte_manquant}

Règles :
- Adapte le vocabulaire et la complexité au profil ci-dessus
- Ajoute le contexte manquant et précise le format de réponse attendu
- Cible le niveau Bloom {bloom_cible}
- Retourne UNIQUEMENT la requête reformulée, sans introduction ni commentaire"""

    client = anthropic.Anthropic(api_key=get_api_key())
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": f"Requête originale : {requete_originale}"}]
    )
    return r.content[0].text.strip()
