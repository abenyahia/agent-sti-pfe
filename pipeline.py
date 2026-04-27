"""
Pipeline orchestrateur — version expérimentation PFE.

Deux modes :
- 'controle' : la requête va directement au STI (groupe témoin)
- 'agent'    : pipeline complet diagnostic + reformulation + évaluation (groupe expérimental)

Dans les deux modes, on enregistre toujours la session pour analyse comparative.
Pour le groupe contrôle, on calcule quand même le score de la question en arrière-plan.
"""
import anthropic
import logging
from datetime import datetime
from agents.diagnostiqueur import diagnostiquer
from agents.reformulateur import reformuler
from agents.evaluateur import evaluer, _scorer
from formatters import suggerer_format, generer_reponse_sti
from config import get_api_key
from database import (
    sauvegarder_session, charger_sessions, charger_sessions_etudiant,
    SESSIONS_FILE
)
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _get_client():
    return anthropic.Anthropic(api_key=get_api_key())


def calculer_phase_fading(score_global: float) -> dict:
    if score_global < 0.40:
        return {"phase": 1, "label": "Scaffolding complet",
                "description": "Reformulation automatique — l'agent guide fortement"}
    elif score_global < 0.62:
        return {"phase": 2, "label": "Scaffolding partiel",
                "description": "Hints proposés — l'étudiant valide avant envoi"}
    elif score_global < 0.80:
        return {"phase": 3, "label": "Accompagnement léger",
                "description": "Feedback métacognitif — l'étudiant formule seul"}
    else:
        return {"phase": 4, "label": "Autonomie confirmée",
                "description": "Question déjà de très bonne qualité"}


def interroger_sti_direct(requete: str) -> str:
    client = _get_client()
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system="Tu es un tuteur pédagogique expert. Réponds de façon structurée et adaptée.",
        messages=[{"role": "user", "content": requete}]
    )
    return r.content[0].text


def pipeline_controle(requete_etudiant: str, code_etudiant: str,
                       niveau_academique: str, theme: str) -> dict:
    """Mode contrôle : pas d'agent. La requête va direct au STI."""
    timestamp = datetime.now().isoformat()
    log.info(f"Mode CONTRÔLE — étudiant={code_etudiant}")

    reponse_sti = interroger_sti_direct(requete_etudiant)

    # Score de la question en arrière-plan (pour analyse stat ultérieure)
    score = _scorer(requete_etudiant)
    sessions_passees = charger_sessions_etudiant(code_etudiant)
    score_precedent = (sessions_passees[-1].get("evaluation", {}).get("score_global")
                       if sessions_passees else None)
    gain_etudiant = (round(score["score_global"] - score_precedent, 2)
                     if score_precedent is not None else None)

    evaluation_silencieuse = {
        "score_global":     score["score_global"],
        "score_precision":  score.get("precision",  0.5),
        "score_profondeur": score.get("profondeur", 0.5),
        "score_contexte":   score.get("contexte",   0.5),
        "gain_etudiant":    gain_etudiant,
    }

    result = {
        "timestamp":         timestamp,
        "etudiant":          code_etudiant,
        "groupe":            "controle",
        "mode":              "controle",
        "niveau_academique": niveau_academique,
        "theme":             theme,
        "requete_originale": requete_etudiant,
        "requete_enrichie":  "",
        "reponse_sti":       reponse_sti,
        "format_reponse":    "texte",
        "diagnostic":        {},
        "evaluation":        evaluation_silencieuse,
        "phase_fading":      {},
    }
    result["_sauvegarde_ok"] = sauvegarder_session(result)
    return result


def pipeline_agent(requete_etudiant: str, code_etudiant: str,
                    niveau_academique: str, theme: str,
                    format_choisi: str = None) -> dict:
    """Mode agent : pipeline complet."""
    timestamp = datetime.now().isoformat()
    log.info(f"Mode AGENT — étudiant={code_etudiant}, niveau={niveau_academique}, theme={theme}")

    diagnostic = diagnostiquer(requete_etudiant)
    requete_enrichie = reformuler(requete_etudiant, diagnostic, niveau_academique, theme)

    suggestion = suggerer_format(requete_etudiant)
    format_utilise = format_choisi if format_choisi else suggestion["format_suggere"]
    reponse = generer_reponse_sti(requete_enrichie, format_utilise)

    sessions_passees = charger_sessions_etudiant(code_etudiant)
    score_precedent = (sessions_passees[-1].get("evaluation", {}).get("score_global")
                       if sessions_passees else None)
    evaluation = evaluer(
        requete_originale=requete_etudiant,
        requete_enrichie=requete_enrichie,
        reponse_enrichie=reponse["contenu"],
        score_session_precedente=score_precedent,
    )
    phase = calculer_phase_fading(evaluation["score_global"])

    result = {
        "timestamp":         timestamp,
        "etudiant":          code_etudiant,
        "groupe":            "experimental",
        "mode":              "agent",
        "niveau_academique": niveau_academique,
        "theme":             theme,
        "requete_originale": requete_etudiant,
        "diagnostic":        diagnostic,
        "requete_enrichie":  requete_enrichie,
        "reponse_sti":       reponse["contenu"],
        "format_reponse":    reponse["format"],
        "format_meta":       reponse["meta"],
        "format_suggere":    suggestion["format_suggere"],
        "raison_format":     suggestion.get("raison", ""),
        "evaluation":        evaluation,
        "phase_fading":      phase,
    }
    result["_sauvegarde_ok"] = sauvegarder_session(result)
    return result


def pipeline_complet(requete_etudiant: str, code_etudiant: str,
                     niveau_academique: str = "Licence 1",
                     theme: str = "Enseignement",
                     format_choisi: str = None,
                     mode: str = "agent") -> dict:
    """Routeur principal."""
    if mode == "controle":
        return pipeline_controle(requete_etudiant, code_etudiant, niveau_academique, theme)
    return pipeline_agent(requete_etudiant, code_etudiant, niveau_academique, theme, format_choisi)
