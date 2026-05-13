"""
Couche de persistance — Supabase (cloud) avec fallback local JSON.
- Sur Streamlit Cloud → Supabase (PostgreSQL hébergé)
- En local Docker     → fichier sessions.json (fallback)
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


def _get_supabase_creds() -> tuple:
    """
    Récupère SUPABASE_URL et SUPABASE_KEY.
    Priorité : variables d'environnement (.env / Docker) → st.secrets (Streamlit Cloud).
    Ne plante JAMAIS — retourne ("", "") si introuvable.
    """
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    # Si les deux sont dans .env / Docker env → on s'arrête là
    if url and key:
        return url, key

    # Sinon on essaie st.secrets (Streamlit Cloud)
    # IMPORTANT : accéder à st.secrets["KEY"] et non .get() pour éviter l'erreur silencieuse
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            s_url = st.secrets.get("SUPABASE_URL", "")
            s_key = st.secrets.get("SUPABASE_KEY", "")
            if s_url and s_key:
                return s_url.strip(), s_key.strip()
    except Exception as e:
        log.debug(f"st.secrets non disponible : {e}")

    return url, key  # peut être ("", "") si rien trouvé


def _get_supabase_client():
    """
    Crée et retourne un client Supabase.
    Retourne None si credentials absents ou si le package supabase n'est pas installé.
    """
    url, key = _get_supabase_creds()
    if not url or not key:
        log.debug("Supabase non configuré — utilisation du fallback local")
        return None
    try:
        from supabase import create_client
        client = create_client(url, key)
        log.debug("Client Supabase créé avec succès")
        return client
    except ImportError:
        log.warning("Package supabase non installé — fallback local")
        return None
    except Exception as e:
        log.error(f"Erreur création client Supabase : {e}")
        return None


def get_status_supabase() -> str:
    """Retourne 'connecte' / 'local' + message descriptif."""
    url, key = _get_supabase_creds()
    if not url or not key:
        return "local"
    client = _get_supabase_client()
    return "connecte" if client else "erreur"


# ─── Helper JSON local ────────────────────────────────────────────────────────
def _lire_json(path: Path) -> list:
    try:
        if path.exists() and path.stat().st_size > 2:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"Erreur lecture {path} : {e}")
    return []


def _ecrire_json(path: Path, data: list) -> bool:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception as e:
        log.error(f"Erreur écriture {path} : {e}")
        return False


# ─── Sessions ─────────────────────────────────────────────────────────────────
def sauvegarder_session(data: dict) -> bool:
    client = _get_supabase_client()
    if client:
        try:
            row = {
                "timestamp":         data["timestamp"],
                "etudiant_code":     data["etudiant"],
                "groupe":            data.get("groupe", "experimental"),
                "niveau_academique": data.get("niveau_academique", ""),
                "theme":             data.get("theme", ""),
                "mode":              data.get("mode", "agent"),
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
            log.info(f"✅ Session sauvegardée Supabase ({data['etudiant']})")
            return True
        except Exception as e:
            log.error(f"Erreur Supabase sauvegarder_session : {e} — fallback local")

    # Fallback local
    sessions = _lire_json(SESSIONS_FILE)
    sessions.append(data)
    ok = _ecrire_json(SESSIONS_FILE, sessions)
    if ok:
        log.info(f"✅ Session sauvegardée localement ({len(sessions)} total)")
    return ok


def charger_sessions() -> list:
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
                    "diagnostic":        json.loads(row.get("diagnostic") or "{}"),
                    "evaluation":        json.loads(row.get("evaluation") or "{}"),
                    "phase_fading":      json.loads(row.get("phase_fading") or "{}"),
                })
            log.info(f"✅ {len(sessions)} sessions chargées depuis Supabase")
            return sessions
        except Exception as e:
            log.error(f"Erreur Supabase charger_sessions : {e} — fallback local")

    return _lire_json(SESSIONS_FILE)


def charger_sessions_etudiant(code: str) -> list:
    return sorted(
        [s for s in charger_sessions() if s.get("etudiant", "").lower() == code.lower()],
        key=lambda s: s.get("timestamp", "")
    )


# ─── Inscriptions ─────────────────────────────────────────────────────────────
def enregistrer_inscription(code: str, prenom: str, niveau: str,
                              groupe: str, consentement: bool) -> bool:
    client = _get_supabase_client()
    row = {
        "code": code, "prenom": prenom, "niveau": niveau,
        "groupe": groupe, "consentement": consentement,
        "date_inscription": datetime.now().isoformat(),
    }
    if client:
        try:
            client.table("inscriptions").upsert(row).execute()
            log.info(f"✅ Inscription Supabase : {code}")
            return True
        except Exception as e:
            log.error(f"Erreur Supabase enregistrer_inscription : {e}")

    f = DATA_DIR / "inscriptions.json"
    existants = [e for e in _lire_json(f) if e.get("code") != code]
    existants.append(row)
    return _ecrire_json(f, existants)


def get_inscription(code: str) -> dict:
    client = _get_supabase_client()
    if client:
        try:
            res = client.table("inscriptions").select("*").eq("code", code).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            log.error(f"Erreur Supabase get_inscription : {e}")

    f = DATA_DIR / "inscriptions.json"
    for i in _lire_json(f):
        if i.get("code") == code:
            return i
    return {}


# ─── Questionnaires ───────────────────────────────────────────────────────────
def enregistrer_questionnaire(code: str, type_q: str, reponses: dict) -> bool:
    client = _get_supabase_client()
    row = {
        "code": code, "type": type_q,
        "timestamp": datetime.now().isoformat(),
        "reponses": json.dumps(reponses, ensure_ascii=False),
    }
    if client:
        try:
            client.table("questionnaires").insert(row).execute()
            log.info(f"✅ Questionnaire Supabase : {code} / {type_q}")
            return True
        except Exception as e:
            log.error(f"Erreur Supabase enregistrer_questionnaire : {e}")

    f = DATA_DIR / "questionnaires.json"
    existants = _lire_json(f)
    existants.append(row)
    return _ecrire_json(f, existants)


def a_complete_questionnaire(code: str, type_q: str) -> bool:
    client = _get_supabase_client()
    if client:
        try:
            res = client.table("questionnaires").select("id").eq("code", code).eq("type", type_q).execute()
            return len(res.data) > 0
        except Exception as e:
            log.error(f"Erreur Supabase a_complete_questionnaire : {e}")

    f = DATA_DIR / "questionnaires.json"
    return any(
        q.get("code") == code and q.get("type") == type_q
        for q in _lire_json(f)
    )
