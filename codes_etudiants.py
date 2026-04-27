"""
Gestion des identifiants étudiants et de l'assignation aux groupes.

Logique :
- Chaque étudiant reçoit un code unique anonymisé (ex: STI-K7M2)
- L'enseignant assigne manuellement chaque code au groupe A (contrôle) ou B (expérimental)
- L'étudiant entre son code à la 1ère connexion → l'app récupère son groupe
- Si le code n'existe pas, l'étudiant ne peut pas accéder

Cette anonymisation garantit la conformité RGPD pour la recherche universitaire.
"""
import secrets
import string


def generer_code_etudiant(prefix: str = "STI") -> str:
    """Génère un code unique non-devinable pour un étudiant. Ex: STI-K7M2"""
    chars = string.ascii_uppercase + string.digits
    # Évite les caractères ambigus 0/O/1/I
    chars = chars.replace("0", "").replace("O", "").replace("1", "").replace("I", "")
    suffix = "".join(secrets.choice(chars) for _ in range(4))
    return f"{prefix}-{suffix}"


def assignation_aleatoire_groupe(seed_code: str) -> str:
    """
    Assigne un groupe (A=controle, B=experimental) de façon déterministe
    basée sur le code étudiant. Permet une répartition ~50/50 reproductible.

    Note : pour un PFE rigoureux, l'enseignant devrait faire la randomisation
    a priori et stocker l'assignation dans Supabase. Cette fonction est un
    fallback si l'enseignant n'a pas pré-assigné.
    """
    # Hash simple : somme des codes ASCII modulo 2
    return "controle" if sum(ord(c) for c in seed_code) % 2 == 0 else "experimental"


# ─── Codes pré-générés pour démarrer l'expérimentation ────────────────────────
def generer_lot_codes(n_controle: int, n_experimental: int) -> list:
    """
    Génère un lot de codes prêts à distribuer aux étudiants.
    Retourne une liste de dicts : [{'code': 'STI-K7M2', 'groupe': 'controle'}, ...]
    L'enseignant les distribue physiquement aux étudiants.
    """
    codes = []
    for _ in range(n_controle):
        codes.append({"code": generer_code_etudiant(), "groupe": "controle"})
    for _ in range(n_experimental):
        codes.append({"code": generer_code_etudiant(), "groupe": "experimental"})
    return codes
