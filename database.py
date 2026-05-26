"""
Couche de persistance — Neon.tech PostgreSQL avec fallback local JSON.
Neon : PostgreSQL gratuit, jamais en pause.
Connection via DATABASE_URL dans Secrets Streamlit ou .env
"""
import os
import json
import logging
from typing import Optional
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


def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "").strip()
        if url:
            return url
    except Exception:
        pass
    return ""


def _get_conn():
    url = _get_database_url()
    if not url:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(url, connect_timeout=10)
        conn.autocommit = True
        return conn
    except ImportError:
        log.warning("psycopg2 non installe")
        return None
    except Exception as e:
        log.error(f"Connexion Neon echouee : {e}")
        return None


def get_status_db() -> str:
    if not _get_database_url():
        return "local"
    conn = _get_conn()
    if conn:
        conn.close()
        return "connecte"
    return "erreur"

def get_status_supabase() -> str:
    return get_status_db()


def _lire_json(path: Path) -> list:
    try:
        if path.exists() and path.stat().st_size > 2:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"Erreur lecture {path.name}: {e}")
    return []


def _ecrire_json(path: Path, data: list) -> bool:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception as e:
        log.error(f"Erreur ecriture {path.name}: {e}")
        return False


def sauvegarder_session(data: dict) -> bool:
    conn = _get_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sessions
                (timestamp,etudiant_code,groupe,niveau_academique,theme,mode,
                 requete_originale,requete_enrichie,reponse_sti,format_reponse,
                 diagnostic,evaluation,phase_fading,score_global,bloom_level)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["timestamp"], data["etudiant"],
                data.get("groupe","experimental"), data.get("niveau_academique",""),
                data.get("theme",""), data.get("mode","agent"),
                data["requete_originale"], data.get("requete_enrichie",""),
                data.get("reponse_sti",""), data.get("format_reponse",""),
                json.dumps(data.get("diagnostic",{}), ensure_ascii=False),
                json.dumps(data.get("evaluation",{}), ensure_ascii=False),
                json.dumps(data.get("phase_fading",{}), ensure_ascii=False),
                data.get("evaluation",{}).get("score_global",0),
                data.get("diagnostic",{}).get("bloom_level",0),
            ))
            conn.close()
            log.info(f"Session -> Neon ({data['etudiant']})")
            return True
        except Exception as e:
            log.error(f"Erreur Neon sauvegarder_session: {e}")
            try: conn.close()
            except: pass

    sessions = _lire_json(SESSIONS_FILE)
    sessions.append(data)
    ok = _ecrire_json(SESSIONS_FILE, sessions)
    if ok: log.info(f"Session -> local ({len(sessions)} total)")
    return ok


def charger_sessions() -> list:
    conn = _get_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""SELECT timestamp,etudiant_code,groupe,niveau_academique,
                theme,mode,requete_originale,requete_enrichie,reponse_sti,
                format_reponse,diagnostic,evaluation,phase_fading
                FROM sessions ORDER BY timestamp""")
            rows = cur.fetchall()
            conn.close()
            result = []
            for r in rows:
                def parse(v):
                    if isinstance(v, dict): return v
                    try: return json.loads(v or "{}")
                    except: return {}
                result.append({
                    "timestamp": r[0] or "", "etudiant": r[1] or "",
                    "groupe": r[2] or "experimental", "niveau_academique": r[3] or "",
                    "theme": r[4] or "", "mode": r[5] or "agent",
                    "requete_originale": r[6] or "", "requete_enrichie": r[7] or "",
                    "reponse_sti": r[8] or "", "format_reponse": r[9] or "",
                    "diagnostic": parse(r[10]), "evaluation": parse(r[11]),
                    "phase_fading": parse(r[12]),
                })
            log.info(f"{len(result)} sessions <- Neon")
            return result
        except Exception as e:
            log.error(f"Erreur Neon charger_sessions: {e}")
            try: conn.close()
            except: pass
    return _lire_json(SESSIONS_FILE)


def charger_sessions_etudiant(code: str) -> list:
    return sorted(
        [s for s in charger_sessions() if s.get("etudiant","").lower()==code.lower()],
        key=lambda s: s.get("timestamp","")
    )


def enregistrer_inscription(code, prenom, niveau, groupe, consentement) -> bool:
    conn = _get_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO inscriptions (code,prenom,niveau,groupe,consentement,date_inscription)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (code) DO UPDATE
                SET prenom=EXCLUDED.prenom, niveau=EXCLUDED.niveau,
                    groupe=EXCLUDED.groupe, consentement=EXCLUDED.consentement
            """, (code, prenom, niveau, groupe, consentement, datetime.now().isoformat()))
            conn.close()
            return True
        except Exception as e:
            log.error(f"Erreur Neon inscription: {e}")
            try: conn.close()
            except: pass
    f = DATA_DIR / "inscriptions.json"
    existants = [e for e in _lire_json(f) if e.get("code") != code]
    existants.append({"code":code,"prenom":prenom,"niveau":niveau,"groupe":groupe,
                       "consentement":consentement,"date_inscription":datetime.now().isoformat()})
    return _ecrire_json(f, existants)


def get_inscription(code: str) -> dict:
    conn = _get_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT code,prenom,niveau,groupe,consentement,date_inscription FROM inscriptions WHERE code=%s", (code,))
            row = cur.fetchone()
            conn.close()
            if row:
                return {"code":row[0],"prenom":row[1],"niveau":row[2],
                        "groupe":row[3],"consentement":row[4],"date_inscription":row[5]}
        except Exception as e:
            log.error(f"Erreur Neon get_inscription: {e}")
            try: conn.close()
            except: pass
    f = DATA_DIR / "inscriptions.json"
    for i in _lire_json(f):
        if i.get("code") == code: return i
    return {}


def enregistrer_questionnaire(code, type_q, reponses) -> bool:
    conn = _get_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO questionnaires (code,type,timestamp,reponses) VALUES (%s,%s,%s,%s)",
                (code, type_q, datetime.now().isoformat(), json.dumps(reponses, ensure_ascii=False)))
            conn.close()
            return True
        except Exception as e:
            log.error(f"Erreur Neon questionnaire: {e}")
            try: conn.close()
            except: pass
    f = DATA_DIR / "questionnaires.json"
    existants = _lire_json(f)
    existants.append({"code":code,"type":type_q,"timestamp":datetime.now().isoformat(),
                       "reponses":json.dumps(reponses, ensure_ascii=False)})
    return _ecrire_json(f, existants)


def a_complete_questionnaire(code, type_q) -> bool:
    conn = _get_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM questionnaires WHERE code=%s AND type=%s", (code, type_q))
            count = cur.fetchone()[0]
            conn.close()
            return count > 0
        except Exception as e:
            log.error(f"Erreur Neon a_complete_questionnaire: {e}")
            try: conn.close()
            except: pass
    f = DATA_DIR / "questionnaires.json"
    return any(q.get("code")==code and q.get("type")==type_q for q in _lire_json(f))


# ─── Codes pré-définis (groupe fixé par l'enseignant avant distribution) ──────
def preenregistrer_codes(codes: list) -> bool:
    """
    Enregistre les codes avec leur groupe AVANT distribution aux étudiants.
    codes = [{"code": "STI-K7M2", "groupe": "controle"}, ...]
    Appelé par l'espace enseignant au moment de la génération.
    """
    conn = _get_conn()
    if conn:
        try:
            cur = conn.cursor()
            for item in codes:
                cur.execute("""
                    INSERT INTO inscriptions (code, groupe, consentement, date_inscription)
                    VALUES (%s, %s, FALSE, %s)
                    ON CONFLICT (code) DO UPDATE
                    SET groupe = EXCLUDED.groupe
                """, (item["code"], item["groupe"], datetime.now().isoformat()))
            conn.close()
            log.info(f"✅ {len(codes)} codes pré-enregistrés dans Neon")
            return True
        except Exception as e:
            log.error(f"Erreur pré-enregistrement Neon : {e}")
            try: conn.close()
            except: pass

    # Fallback local
    f = DATA_DIR / "inscriptions.json"
    existants = _lire_json(f)
    for item in codes:
        existants = [e for e in existants if e.get("code") != item["code"]]
        existants.append({
            "code": item["code"],
            "groupe": item["groupe"],
            "consentement": False,
            "date_inscription": datetime.now().isoformat(),
        })
    return _ecrire_json(f, existants)


def get_groupe_predefini(code: str) -> Optional[str]:
    """
    Récupère le groupe pré-défini pour un code donné.
    Retourne 'controle', 'experimental', ou None si le code est inconnu.
    """
    inscription = get_inscription(code)
    groupe = inscription.get("groupe")
    if groupe in ("controle", "experimental"):
        return groupe
    return None
