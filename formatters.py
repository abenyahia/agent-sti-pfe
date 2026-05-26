"""
Formatters : l'agent génère la réponse STI dans différents formats selon le besoin.
6 formats supportés :
- texte        : réponse structurée en prose
- tableau      : comparaison ou classification en tableau Markdown
- carte_mentale: diagramme Mermaid (arbre de concepts)
- audio        : texte concis optimisé pour la lecture vocale
- image        : mots-clés pour recherche d'image + emoji illustratif
- avatar       : feedback court que l'avatar lit à voix haute

L'agent peut suggérer un format, mais l'étudiant peut forcer son choix.
"""
import anthropic
import json
import re
from typing import Optional
from config import get_api_key


def _parse_json(raw: str) -> dict:
    """Parse robuste qui retire les backticks markdown."""
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    return json.loads(text)


# ─── Agent suggéreur de format ────────────────────────────────────────────────
SYSTEM_SUGGEST = """Tu es un expert en design pédagogique.
On te donne une question d'étudiant. Suggère le MEILLEUR format de réponse parmi :
- "texte"        : explication conceptuelle, narrative, théorique
- "tableau"      : comparaison, classification, avantages/inconvénients
- "carte_mentale": concepts hiérarchiques, relations entre idées, vue d'ensemble
- "image"        : réponse où un visuel ajoute beaucoup (anatomie, géographie, œuvre)

Réponds avec UNIQUEMENT ce JSON (pas de backticks) :
{"format_suggere": "texte", "raison": "courte justification"}"""


def suggerer_format(question: str) -> dict:
    """L'agent propose le format le plus adapté à la question."""
    client = anthropic.Anthropic(api_key=get_api_key())
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=SYSTEM_SUGGEST,
            messages=[{"role": "user", "content": f"Question : {question}"}]
        )
        return _parse_json(r.content[0].text)
    except Exception:
        return {"format_suggere": "texte", "raison": "format par défaut"}


# ─── Génération des réponses dans chaque format ───────────────────────────────

FORMAT_INSTRUCTIONS = {
    "texte": (
        "Réponds en prose structurée (introduction + explication + exemple + synthèse). "
        "Utilise des paragraphes courts. Pas de liste à puces, pas de tableau."
    ),
    "tableau": (
        "Réponds UNIQUEMENT avec un tableau Markdown comparatif, suivi d'une conclusion "
        "en 2 phrases maximum. Le tableau doit avoir 3 colonnes minimum et 4 lignes minimum. "
        "Format : | En-tête 1 | En-tête 2 | En-tête 3 | suivi de |---|---|---| puis des lignes."
    ),
    "carte_mentale": (
        "Réponds en générant une carte mentale au format Mermaid.js. "
        "Structure obligatoire :\n"
        "```mermaid\n"
        "mindmap\n"
        "  root((Concept central))\n"
        "    Branche1\n"
        "      Sous-branche1a\n"
        "      Sous-branche1b\n"
        "    Branche2\n"
        "      Sous-branche2a\n"
        "```\n"
        "Après le code Mermaid, ajoute une explication de 2-3 phrases."
    ),
    "audio": (
        "Réponds en texte concis et fluide (150 mots maximum), adapté à la lecture vocale. "
        "Évite les listes, les codes, les symboles. Utilise un ton conversationnel et des "
        "phrases courtes. Pas de markdown."
    ),
    "image": (
        "Réponds d'abord avec 3-5 MOTS-CLÉS en anglais pour illustrer visuellement le concept, "
        "au format : IMAGE_KEYWORDS: mot1, mot2, mot3\n"
        "Puis ajoute un EMOJI représentatif : EMOJI: 🎓\n"
        "Enfin, une explication textuelle de 3-4 phrases."
    ),
}


def generer_reponse_sti(question_enrichie: str, format_choisi: str = "texte") -> dict:
    """
    Génère la réponse STI dans le format demandé.
    Retourne dict avec : { 'format', 'contenu', 'meta' }
    """
    instructions = FORMAT_INSTRUCTIONS.get(format_choisi, FORMAT_INSTRUCTIONS["texte"])

    system = (
        "Tu es un tuteur pédagogique expert. Réponds de façon structurée, "
        "pédagogique et adaptée au niveau de l'étudiant. Utilise des exemples concrets.\n\n"
        f"FORMAT DE RÉPONSE IMPOSÉ : {format_choisi}\n"
        f"INSTRUCTIONS : {instructions}"
    )

    client = anthropic.Anthropic(api_key=get_api_key())
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": question_enrichie}]
    )
    contenu = r.content[0].text.strip()

    meta = {}
    if format_choisi == "image":
        # Extraire mots-clés et emoji
        kw_match = re.search(r"IMAGE_KEYWORDS:\s*([^\n]+)", contenu)
        em_match = re.search(r"EMOJI:\s*(\S+)", contenu)
        meta["keywords"] = kw_match.group(1).strip() if kw_match else "education learning"
        meta["emoji"] = em_match.group(1).strip() if em_match else "🎓"
        # Retirer les lignes méta du contenu affiché
        contenu = re.sub(r"IMAGE_KEYWORDS:\s*[^\n]+\n?", "", contenu)
        contenu = re.sub(r"EMOJI:\s*\S+\n?", "", contenu).strip()

    return {
        "format": format_choisi,
        "contenu": contenu,
        "meta": meta,
    }


# ─── Recherche d'image via Wikimedia Commons API (gratuit, sans clé) ─────────────
def chercher_image_wikimedia(keywords: str) -> Optional[str]:
    """
    Cherche une image sur Wikimedia Commons via l'API publique.
    Retourne l'URL de l'image ou None si introuvable.
    Avantages : 100% gratuit, pas de clé API, images libres de droits.
    """
    import urllib.parse
    import urllib.request
    import json

    try:
        q = urllib.parse.quote(keywords[:80])
        api_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&generator=search&gsrsearch={q}&gsrnamespace=6"
            "&prop=imageinfo&iiprop=url|mime&iiurlwidth=800"
            "&gsrlimit=3&format=json&origin=*"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": "PFE-STI/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            info = page.get("imageinfo", [{}])[0]
            mime = info.get("mime", "")
            url = info.get("thumburl") or info.get("url", "")
            # Exclure SVG et fichiers non-image
            if url and "image" in mime and "svg" not in mime:
                return url
    except Exception:
        pass
    return None


def url_image_unsplash(keywords: str) -> Optional[str]:
    """Alias maintenu pour compatibilité — utilise Wikimedia Commons."""
    return chercher_image_wikimedia(keywords)
