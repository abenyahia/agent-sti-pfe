import anthropic
import json
import re
from dotenv import load_dotenv
from config import get_api_key

load_dotenv()


def _parse_json(raw: str) -> dict:
    """
    Parse robuste : gère les cas où le modèle emballe le JSON dans des backticks markdown.
    Ex: ```json { ... } ``` → extrait et parse correctement.
    """
    text = raw.strip()
    # Supprimer les blocs markdown ```json ... ``` ou ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    return json.loads(text)


SYSTEM_SCORE = """Tu es un évaluateur pédagogique expert en taxonomie de Bloom.
Évalue la qualité intrinsèque de cette question d'étudiant sur 3 critères.
Réponds avec UNIQUEMENT ce JSON (pas de backticks, pas d'explication) :
{"precision": 0.0, "profondeur": 0.0, "contexte": 0.0}
Critères :
- precision  (0 à 1) : question claire, non ambigüe, bien délimitée
- profondeur (0 à 1) : niveau cognitif Bloom visé (0=memoriser, 1=creer/evaluer)
- contexte   (0 à 1) : contexte fourni (domaine, cours, contraintes, format attendu)"""

SYSTEM_FEEDBACK = """Tu es un tuteur expert en metacognition et pedagogie.
On te donne la question originale d'un etudiant et la version enrichie par un agent.
Reponds avec UNIQUEMENT ce JSON (pas de backticks, pas d'explication, pas d'accents dans les cles) :
{"feedback_metacognitif": "...", "ce_qui_manquait": "...", "conseil_prochain": "...", "gain_qualitatif": "..."}
Valeurs possibles pour gain_qualitatif : gain important | gain modere | gain faible | aucun gain
Les valeurs des champs peuvent contenir des accents et du texte libre en francais."""


def _scorer(question: str) -> dict:
    """Score la qualité intrinsèque d'une question. 1 appel Haiku."""
    client = anthropic.Anthropic(api_key=get_api_key())
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=SYSTEM_SCORE,
            messages=[{"role": "user", "content": f"Question : {question}"}]
        )
        data = _parse_json(r.content[0].text)
    except Exception as e:
        data = {"precision": 0.5, "profondeur": 0.5, "contexte": 0.5}

    data["score_global"] = round(
        data.get("precision",  0.5) * 0.35 +
        data.get("profondeur", 0.5) * 0.40 +
        data.get("contexte",   0.5) * 0.25, 2
    )
    return data


def _feedback(requete_originale: str, requete_enrichie: str) -> dict:
    """Génère le feedback métacognitif. 1 appel Haiku."""
    client = anthropic.Anthropic(api_key=get_api_key())
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=SYSTEM_FEEDBACK,
            messages=[{"role": "user", "content":
                f"Question originale : {requete_originale}\n\n"
                f"Question enrichie par l'agent : {requete_enrichie}"}]
        )
        raw = r.content[0].text
        result = _parse_json(raw)

        # Vérifier que les clés attendues sont présentes
        required = ["feedback_metacognitif", "ce_qui_manquait", "conseil_prochain", "gain_qualitatif"]
        for k in required:
            if k not in result:
                result[k] = "Non disponible"
        return result

    except Exception as e:
        # Fallback avec message utile (pas générique)
        return {
            "feedback_metacognitif": (
                f"La reformulation a enrichi votre question en ajoutant du contexte "
                f"et en ciblant un niveau cognitif plus élevé."
            ),
            "ce_qui_manquait": (
                "Le contexte disciplinaire et le format de réponse attendu manquaient."
            ),
            "conseil_prochain": (
                "Précisez le cours concerné, le niveau attendu, et demandez "
                "une explication avec exemples ou une comparaison."
            ),
            "gain_qualitatif": "gain modéré"
        }


def evaluer(requete_originale: str, requete_enrichie: str,
            reponse_enrichie: str, score_session_precedente: float = None) -> dict:
    """
    Évaluation complète — 3 appels Haiku max, aucun appel STI en double.
    score_global     = score de la question ORIGINALE → curseur de progression
    gain_agent_pct   = apport de la reformulation sur cette session
    gain_etudiant_pct= progression vs session précédente du même étudiant
    """
    score_orig = _scorer(requete_originale)
    score_enr  = _scorer(requete_enrichie)
    feedback   = _feedback(requete_originale, requete_enrichie)

    gain_agent = round(score_enr["score_global"] - score_orig["score_global"], 2)

    if score_session_precedente is not None:
        gain_etudiant = round(score_orig["score_global"] - score_session_precedente, 2)
        gain_etudiant_pct = f"{'+' if gain_etudiant >= 0 else ''}{int(gain_etudiant * 100)}%"
    else:
        gain_etudiant     = None
        gain_etudiant_pct = "première session"

    return {
        "score_global":             score_orig["score_global"],
        "score_precision":          score_orig.get("precision",  0.5),
        "score_profondeur":         score_orig.get("profondeur", 0.5),
        "score_contexte":           score_orig.get("contexte",   0.5),
        "score_enrichi_global":     score_enr["score_global"],
        "score_enrichi_precision":  score_enr.get("precision",  0.5),
        "score_enrichi_profondeur": score_enr.get("profondeur", 0.5),
        "score_enrichi_contexte":   score_enr.get("contexte",   0.5),
        "gain_agent":               gain_agent,
        "gain_agent_pct":           f"{'+' if gain_agent >= 0 else ''}{int(gain_agent * 100)}%",
        "gain_etudiant":            gain_etudiant,
        "gain_etudiant_pct":        gain_etudiant_pct,
        "feedback_metacognitif":    feedback["feedback_metacognitif"],
        "ce_qui_manquait":          feedback["ce_qui_manquait"],
        "conseil_prochain":         feedback["conseil_prochain"],
        "gain_qualitatif":          feedback["gain_qualitatif"],
    }
