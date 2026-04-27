import anthropic
import json
import re
from dotenv import load_dotenv
from config import get_api_key

load_dotenv()


def _parse_json(raw: str) -> dict:
    """Parse robuste — retire les backticks markdown si présents."""
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    return json.loads(text)


SYSTEM_PROMPT = """Tu es un expert en taxonomie de Bloom et analyse pedagogique.
Analyse la requete de l'etudiant. Reponds avec UNIQUEMENT ce JSON (pas de backticks) :
{
  "bloom_level": 2,
  "bloom_label": "Comprendre",
  "ambiguity_score": 0.5,
  "detected_domain": "domaine detecte",
  "missing_context": ["element 1", "element 2"],
  "improvement_hints": ["conseil 1", "conseil 2"]
}
bloom_level : entier 1 a 6 (1=Memoriser 2=Comprendre 3=Appliquer 4=Analyser 5=Evaluer 6=Creer)
ambiguity_score : float 0-1 (0=clair, 1=tres ambigu)"""


def diagnostiquer(requete_etudiant: str) -> dict:
    client = anthropic.Anthropic(api_key=get_api_key())
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": requete_etudiant}]
        )
        return _parse_json(r.content[0].text)
    except Exception:
        return {
            "bloom_level": 2, "bloom_label": "Comprendre",
            "ambiguity_score": 0.5, "detected_domain": "Non déterminé",
            "missing_context": ["Contexte du cours", "Niveau attendu"],
            "improvement_hints": ["Préciser le contexte", "Ajouter des contraintes"]
        }
