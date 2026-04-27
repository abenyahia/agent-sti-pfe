"""
Couche de persistance — Supabase (cloud) avec fallback local JSON.
- Sur Streamlit Cloud → Supabase (PostgreSQL hébergé)
- En local Docker     → fichier sessions.json (fallback)

Le système détecte automatiquement la disponibilité de Supabase via les secrets/env.
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)
if not SESSIONS_FILE.exists():
    SESSIONS_FILE.write_text("[]", encoding="utf-8")


def _get_supabase_creds():
    """Récupère URL et clé Supabase depuis env ou st.secrets."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if url and key:
        return url, key
    try:
        import streamlit as st
        url = st.secrets.get("SUPABASE_URL", "") or url
        key = st.secrets.get("SUPABASE_KEY", "") or key
    except Exception:
        pass
    return url, key


def _get_supabase_client():
    """Initialise le client Supabase si les credentials sont disponibles."""
    url, key = _get_supabase_creds()
    if not (url and key):
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        log.warning(f"Supabase indisponible : {e}")
        return None


# ─── Persistance des sessions (interactions étudiant) ─────────────────────────
def sauvegarder_session(data: dict) -> bool:
    """
    Sauvegarde une session dans Supabase si dispo, sinon dans sessions.json local.
    """
    client = _get_supabase_client()
    if client:
        try:
            row = {
                "timestamp":         data["timestamp"],
                "etudiant_code":     data["etudiant"],          # code anonymisé
                "groupe":            data.get("groupe", "experimental"),
                "niveau_academique": data.get("niveau_academique", ""),
                "theme":             data.get("theme", ""),
                "mode":              data.get("mode", "agent"),  # 'controle' ou 'agent'
                "requete_originale": data["requete_originale"],
                "requete_enrichie":  data.get("requete_enrichie", ""),
                "reponse_sti":       data.get("reponse_sti", ""),
                "format_reponse":    data.get("format_reponse", ""),
                "diagnostic":        json.dumps(data.get("diagnostic", {}), ensure_ascii=False),
                "evaluation":        json.dumps(data.get("evaluation", {}), ensure_ascii=False),
                "phase_fading":      json.dumps(data.get("phase_fading", {}), ensure_ascii=False),
                "score_global":      data.get("evaluation", {}).get("score_global", 0),
                "bloom_level":       data.get("diagnostic", {}).get("bloom_level", 0),
            }
            client.table("sessions").insert(row).execute()
            log.info(f"Session sauvegardée Supabase ({data['etudiant']})")
            return True
        except Exception as e:
            log.error(f"Erreur Supabase, fallback local : {e}")

    # Fallback local
    try:
        sessions = []
        if SESSIONS_FILE.exists() and SESSIONS_FILE.stat().st_size > 2:
            try:
                sessions = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                sessions = []
        sessions.append(data)
        tmp = SESSIONS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(SESSIONS_FILE)
        log.info(f"Session sauvegardée localement ({len(sessions)} total)")
        return True
    except Exception as e:
        log.error(f"Erreur sauvegarde locale : {e}")
        return False


def charger_sessions() -> list:
    """Charge toutes les sessions (Supabase si dispo, sinon local)."""
    client = _get_supabase_client()
    if client:
        try:
            res = client.table("sessions").select("*").order("timestamp").execute()
            sessions = []
            for row in res.data:
                sessions.append({
                    "timestamp":         row.get("timestamp", ""),
                    "etudiant":          row.get("etudiant_code", ""),
                    "groupe":            row.get("groupe", "experimental"),
                    "niveau_academique": row.get("niveau_academique", ""),
                    "theme":             row.get("theme", ""),
                    "mode":              row.get("mode", "agent"),
                    "requete_originale": row.get("requete_originale", ""),
                    "requete_enrichie":  row.get("requete_enrichie", ""),
                    "reponse_sti":       row.get("reponse_sti", ""),
                    "format_reponse":    row.get("format_reponse", ""),
                    "diagnostic":        json.loads(row.get("diagnostic", "{}") or "{}"),
                    "evaluation":        json.loads(row.get("evaluation", "{}") or "{}"),
                    "phase_fading":      json.loads(row.get("phase_fading", "{}") or "{}"),
                })
            return sessions
        except Exception as e:
            log.error(f"Erreur lecture Supabase, fallback local : {e}")

    # Fallback local
    try:
        if SESSIONS_FILE.exists() and SESSIONS_FILE.stat().st_size > 2:
            return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"Erreur lecture : {e}")
    return []


def charger_sessions_etudiant(code: str) -> list:
    """Sessions d'un étudiant donné (par son code anonymisé)."""
    return sorted(
        [s for s in charger_sessions() if s.get("etudiant", "").lower() == code.lower()],
        key=lambda s: s.get("timestamp", "")
    )


# ─── Inscriptions étudiants (table 'inscriptions') ────────────────────────────
def enregistrer_inscription(code: str, prenom: str, niveau: str, groupe: str,
                              consentement: bool) -> bool:
    """Enregistre l'inscription initiale d'un étudiant avec son groupe (A/B)."""
    client = _get_supabase_client()
    row = {
        "code":          code,
        "prenom":        prenom,
        "niveau":        niveau,
        "groupe":        groupe,             # 'controle' ou 'experimental'
        "consentement":  consentement,
        "date_inscription": datetime.now().isoformat(),
    }
    if client:
        try:
            client.table("inscriptions").upsert(row).execute()
            return True
        except Exception as e:
            log.error(f"Erreur inscription Supabase : {e}")

    # Fallback local
    try:
        f = DATA_DIR / "inscriptions.json"
        existants = []
        if f.exists() and f.stat().st_size > 2:
            existants = json.loads(f.read_text(encoding="utf-8"))
        # Upsert : remplacer si code existe déjà
        existants = [e for e in existants if e.get("code") != code]
        existants.append(row)
        f.write_text(json.dumps(existants, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log.error(f"Erreur inscription locale : {e}")
        return False


def get_inscription(code: str) -> dict:
    """Récupère les infos d'inscription (groupe, niveau, etc.) depuis le code."""
    client = _get_supabase_client()
    if client:
        try:
            res = client.table("inscriptions").select("*").eq("code", code).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            log.error(f"Erreur lecture inscription Supabase : {e}")

    # Fallback local
    try:
        f = DATA_DIR / "inscriptions.json"
        if f.exists() and f.stat().st_size > 2:
            inscriptions = json.loads(f.read_text(encoding="utf-8"))
            for i in inscriptions:
                if i.get("code") == code:
                    return i
    except Exception:
        pass
    return {}


# ─── Questionnaires pré/post ─────────────────────────────────────────────────
def enregistrer_questionnaire(code: str, type_q: str, reponses: dict) -> bool:
    """Enregistre les réponses au questionnaire pré-test ou post-test."""
    client = _get_supabase_client()
    row = {
        "code":      code,
        "type":      type_q,                # 'pretest' ou 'posttest'
        "timestamp": datetime.now().isoformat(),
        "reponses":  json.dumps(reponses, ensure_ascii=False),
    }
    if client:
        try:
            client.table("questionnaires").insert(row).execute()
            return True
        except Exception as e:
            log.error(f"Erreur questionnaire Supabase : {e}")

    # Fallback local
    try:
        f = DATA_DIR / "questionnaires.json"
        existants = []
        if f.exists() and f.stat().st_size > 2:
            existants = json.loads(f.read_text(encoding="utf-8"))
        existants.append(row)
        f.write_text(json.dumps(existants, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log.error(f"Erreur questionnaire local : {e}")
        return False


def a_complete_questionnaire(code: str, type_q: str) -> bool:
    """Vérifie si l'étudiant a déjà complété un questionnaire donné."""
    client = _get_supabase_client()
    if client:
        try:
            res = client.table("questionnaires").select("id").eq("code", code).eq("type", type_q).execute()
            return len(res.data) > 0
        except Exception:
            pass

    try:
        f = DATA_DIR / "questionnaires.json"
        if f.exists() and f.stat().st_size > 2:
            qs = json.loads(f.read_text(encoding="utf-8"))
            return any(q.get("code") == code and q.get("type") == type_q for q in qs)
    except Exception:
        pass
    return False


# ─── Statistiques pour le dashboard enseignant ────────────────────────────────
def get_status_supabase() -> str:
    """Retourne 'connecte' / 'local' selon l'état."""
    return "connecte" if _get_supabase_client() else "local"
