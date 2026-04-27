# Agent Pédagogique Adaptatif STI — v2

Application de PFE Master Ingénierie Pédagogique.

## 🚀 Démarrage local en 5 minutes

### Prérequis
- Docker Desktop installé et lancé
- Une clé API Anthropic ([console.anthropic.com](https://console.anthropic.com))

### Installation

```bash
# 1. Décompresser le zip dans un dossier
unzip agent-sti-code-v2.zip
cd projet-sti-v2

# 2. Créer le fichier .env
cp .env.example .env
# Éditer .env et remplir au minimum ANTHROPIC_API_KEY

# 3. Lancer le conteneur
docker compose up --build -d

# 4. Ouvrir l'application
# → http://localhost:8501
```

## ⚙️ Configuration .env minimale (en local)

```bash
ANTHROPIC_API_KEY=sk-ant-votre-cle-ici
TEACHER_PASSWORD=mon-mot-de-passe-enseignant

# Supabase = OPTIONNEL en local
# Si vide, l'app utilise des fichiers JSON locaux dans ./data/
SUPABASE_URL=
SUPABASE_KEY=
```

## 📂 Données persistées en local

Les données sont stockées dans `./data/` (visible depuis votre PC) :

| Fichier | Contenu |
|---|---|
| `data/sessions.json` | Toutes les interactions étudiant-STI |
| `data/inscriptions.json` | Profils anonymisés des étudiants |
| `data/questionnaires.json` | Réponses aux pré/post-tests |

Le dossier est synchronisé en temps réel entre votre PC et le conteneur.

## 🎯 Workflow d'utilisation locale

### Pour tester avec un seul étudiant fictif

1. Aller sur http://localhost:8501
2. Page **Accueil** → entrer un code (ex: `STI-TEST`)
3. Compléter le formulaire de consentement
4. Aller dans **Questionnaire pré-test** → remplir les 13 questions
5. Aller dans **Poser une question** → poser 2-3 questions
6. Tester aussi le **Questionnaire post-test**

### Pour accéder à l'Espace enseignant

1. Menu de gauche → **Espace enseignant**
2. Mot de passe : celui défini dans `.env` (TEACHER_PASSWORD)
3. Vous voyez : vue d'ensemble, comparaison groupes, génération codes, export CSV

## 🔧 Commandes Docker utiles

```bash
# Démarrer
docker compose up -d

# Voir les logs en temps réel
docker compose logs -f

# Arrêter
docker compose down

# Rebuild après modification du code
docker compose down && docker compose up --build -d

# Réinitialiser toutes les données (⚠️ destructif)
rm -rf data/*.json
```

## 📊 Pour passer en production (cloud)

Voir le document **Guide_Deploiement_Cloud_PFE.docx** :
- Streamlit Community Cloud (gratuit)
- Supabase pour la persistance multi-utilisateurs
- Protocole expérimental complet

## 🎓 Documents associés

- `Guide_Deploiement_Cloud_PFE.docx` — guide de mise en ligne
- `Documents_Experimentation_PFE.docx` — consentement RGPD + questionnaires papier

## 📞 Architecture

```
projet-sti-v2/
├── interface.py              ← UI Streamlit (point d'entrée)
├── pipeline.py               ← Orchestrateur (mode contrôle ou agent)
├── config.py                 ← Lecture clé API
├── database.py               ← Persistance Supabase + fallback JSON
├── codes_etudiants.py        ← Génération codes anonymisés
├── questionnaires.py         ← Items pré/post-test
├── themes.py                 ← Thèmes Enseignement / Soft Skills
├── formatters.py             ← 6 formats multimodaux
└── agents/
    ├── diagnostiqueur.py     ← Analyse Bloom
    ├── reformulateur.py      ← Enrichissement ZPD N+1
    └── evaluateur.py         ← Scoring + feedback métacognitif
```
