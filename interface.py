"""
Interface étudiant + dashboard enseignant — version expérimentation PFE.

Workflow étudiant :
1. Saisie du code anonymisé (donné par l'enseignant)
2. Première fois : consentement RGPD + questionnaire pré-test
3. Sessions normales selon le groupe (contrôle ou expérimental)
4. Après 6 semaines : invitation à compléter le questionnaire post-test

Workflow enseignant :
1. Page dédiée protégée par mot de passe (TEACHER_PASSWORD)
2. Génération de codes pour les étudiants
3. Suivi en temps réel des deux groupes
4. Export CSV pour analyse statistique externe
"""
import streamlit as st
import streamlit.components.v1 as components
import json
import io
import os
import pandas as pd
from datetime import datetime
from pipeline import pipeline_complet
from database import (
    charger_sessions, charger_sessions_etudiant, get_inscription,
    enregistrer_inscription, enregistrer_questionnaire, a_complete_questionnaire,
    get_status_supabase, SESSIONS_FILE
)
from codes_etudiants import generer_lot_codes, assignation_aleatoire_groupe
from questionnaires import (
    PRETEST_ITEMS, POSTTEST_ITEMS,
    calculer_score_metacognition, calculer_score_auto_efficacite, calculer_score_sus
)
from themes import THEMES
from formatters import url_image_unsplash

st.set_page_config(
    page_title="Étude PFE — Agent Pédagogique STI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main-title{font-size:1.9rem;font-weight:bold;color:#1B3A6B}
.box{padding:12px 16px;border-radius:6px;margin:6px 0}
.box-orange{background:#FEF9E7;border-left:4px solid #E67E22}
.box-blue{background:#EBF5FB;border-left:4px solid #2E6DB4}
.box-green{background:#EAFAF1;border-left:4px solid #27AE60}
.box-red{background:#FDEDEC;border-left:4px solid #C0392B}
.avatar-wrap{display:flex;align-items:flex-start;gap:14px;margin:12px 0}
.avatar-bubble{background:#EBF5FB;border-radius:0 16px 16px 16px;
               padding:12px 16px;font-size:0.95rem;color:#1B3A6B;
               border:1px solid #BDC3C7;max-width:85%;line-height:1.5}
.theme-card{padding:14px;border-radius:8px;margin:6px 0;
            background:linear-gradient(135deg,#EBF5FB,#D6EAF8);
            border-left:5px solid #2E6DB4}
.format-badge{display:inline-block;padding:4px 10px;border-radius:12px;
              background:#2E6DB4;color:white;font-size:0.8rem;margin-right:6px}
.code-pill{background:#1B3A6B;color:white;padding:8px 16px;border-radius:20px;
           font-family:monospace;font-size:1.1rem;font-weight:bold}
</style>
""", unsafe_allow_html=True)

NIVEAUX = ["Bac", "Licence 1", "Licence 2", "Licence 3", "Master 1", "Master 2", "Doctorat"]
NIVEAU_EMOJI = {"Bac": "🏫", "Licence 1": "📘", "Licence 2": "📗",
                "Licence 3": "📙", "Master 1": "🎓", "Master 2": "🏅", "Doctorat": "🔬"}
FORMATS = {
    "auto":          {"label": "🤖 Automatique", "icon": "🤖"},
    "texte":         {"label": "📝 Texte",        "icon": "📝"},
    "tableau":       {"label": "📊 Tableau",      "icon": "📊"},
    "carte_mentale": {"label": "🗺️ Carte mentale","icon": "🗺️"},
    "audio":         {"label": "🎧 Audio",        "icon": "🎧"},
    "image":         {"label": "🖼️ Image",        "icon": "🖼️"},
}

# Mot de passe enseignant — à modifier dans .env
TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD", "pfe2026")
try:
    TEACHER_PASSWORD = st.secrets.get("TEACHER_PASSWORD", TEACHER_PASSWORD)
except Exception:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSANTS RÉUTILISABLES
# ═══════════════════════════════════════════════════════════════════════════════
def avatar_svg(talking: bool = False) -> str:
    anim = '<animate attributeName="ry" values="6;3;6" dur="0.4s" repeatCount="indefinite"/>' if talking else ""
    mouth = (f'<ellipse cx="50" cy="72" rx="10" ry="6" fill="#F4A261">{anim}</ellipse>' if talking
             else '<path d="M40 70 Q50 76 60 70" stroke="#F4A261" stroke-width="2.5" fill="none" stroke-linecap="round"/>')
    return f"""
<svg width="80" height="100" viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
  <rect x="20" y="85" width="60" height="35" rx="12" fill="#2E6DB4"/>
  <polygon points="50,88 45,105 50,108 55,105" fill="#1B3A6B"/>
  <circle cx="50" cy="52" r="30" fill="#FDDBB4"/>
  <ellipse cx="50" cy="25" rx="30" ry="12" fill="#4A2C0A"/>
  <rect x="20" y="25" width="60" height="10" fill="#4A2C0A"/>
  <ellipse cx="38" cy="48" rx="5" ry="6" fill="white"/>
  <ellipse cx="62" cy="48" rx="5" ry="6" fill="white"/>
  <circle cx="39" cy="49" r="3" fill="#1B3A6B"/>
  <circle cx="63" cy="49" r="3" fill="#1B3A6B"/>
  <path d="M33 41 Q38 38 43 41" stroke="#4A2C0A" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M57 41 Q62 38 67 41" stroke="#4A2C0A" stroke-width="2" fill="none" stroke-linecap="round"/>
  <ellipse cx="50" cy="60" rx="3" ry="4" fill="#F4A261" opacity="0.6"/>
  {mouth}
</svg>"""

def avatar_message(message: str, talking: bool = True):
    st.markdown(f"""
<div class="avatar-wrap">
  <div style="flex-shrink:0">{avatar_svg(talking)}</div>
  <div class="avatar-bubble">🎙️ {message}</div>
</div>""", unsafe_allow_html=True)

def audio_tts(text: str, lang: str = "fr"):
    clean = text.strip()[:600]
    if not clean:
        return
    # gTTS — requiert internet (fonctionne sur Streamlit Cloud)
    try:
        from gtts import gTTS
        tts = gTTS(text=clean, lang=lang, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        st.audio(buf.read(), format="audio/mp3", autoplay=True)
        return
    except Exception:
        pass
    # Pas d'audio disponible — message discret
    st.caption("🔇 Audio temporairement indisponible")


def render_mermaid(code: str, height: int = 500):
    html = f"""
<div class="mermaid" style="background:white;padding:20px;border-radius:8px">
{code}
</div>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose' }});
</script>"""
    components.html(html, height=height, scrolling=True)


def extract_mermaid(text: str):
    import re
    m = re.search(r"```mermaid\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip(), text.replace(m.group(0), "").strip()
    return None, text


def render_reponse(result: dict, audio_on: bool):
    fmt = result.get("format_reponse", "texte")
    contenu = result.get("reponse_sti", "")
    meta = result.get("format_meta", {})
    st.markdown(f'<div><span class="format-badge">{FORMATS.get(fmt,{}).get("icon","📝")} '
                f'Format : {fmt}</span></div>', unsafe_allow_html=True)
    if fmt == "carte_mentale":
        mc, rest = extract_mermaid(contenu)
        if mc:
            render_mermaid(mc)
            if rest: st.markdown(rest)
        else:
            st.markdown(contenu)
    elif fmt == "tableau":
        st.markdown(contenu)
    elif fmt == "image":
        kw = meta.get("keywords", "education")
        emoji = meta.get("emoji", "🎓")
        col1, col2 = st.columns([1, 1])
        with col1:
            try:
                st.image(url_image_unsplash(kw), caption=f"Illustration : {kw}", use_container_width=True)
            except Exception:
                st.markdown(f"<div style='font-size:8rem;text-align:center'>{emoji}</div>", unsafe_allow_html=True)
        with col2:
            st.write(contenu)
    elif fmt == "audio":
        st.write(contenu)
        if audio_on:
            audio_tts(contenu)
    else:
        st.write(contenu)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION ÉTUDIANT (par code)
# ═══════════════════════════════════════════════════════════════════════════════
if "code_etudiant" not in st.session_state:
    st.session_state.code_etudiant = None
if "inscription" not in st.session_state:
    st.session_state.inscription = None


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Navigation et profil
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🎓 Étude PFE")
    st.caption("Master Ingénierie Pédagogique")
    st.markdown("---")

    if st.session_state.code_etudiant:
        ins = st.session_state.inscription
        st.markdown(f'<div class="code-pill">{st.session_state.code_etudiant}</div>',
                     unsafe_allow_html=True)
        if ins:
            st.caption(f"{NIVEAU_EMOJI.get(ins.get('niveau','Licence 1'),'')} {ins.get('niveau','')}")
            groupe = ins.get('groupe', 'experimental')
            color = "🔵" if groupe == "controle" else "🟢"
            st.caption(f"{color} Groupe : {groupe.capitalize()}")
        if st.button("🚪 Se déconnecter"):
            st.session_state.code_etudiant = None
            st.session_state.inscription = None
            st.rerun()
        st.markdown("---")

    page = st.radio("Navigation", [
        "🏠 Accueil",
        "🎓 Poser une question",
        "📋 Questionnaire pré-test",
        "📋 Questionnaire post-test",
        "🔍 Mon historique",
        "👨‍🏫 Espace enseignant",
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — ACCUEIL & INSCRIPTION
# ═══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Accueil":
    st.markdown('<p class="main-title">🎓 Étude sur l\'Agent Pédagogique Adaptatif</p>',
                unsafe_allow_html=True)
    st.markdown("---")

    if not st.session_state.code_etudiant:
        st.markdown("### 👋 Bienvenue dans cette étude")
        st.markdown("""
Cette plateforme vous accompagne dans l'utilisation d'un Système de Tutorat Intelligent (STI).
Vous allez interagir avec l'outil pendant **6 semaines**, à raison de **3 sessions par semaine** environ,
pour aider notre recherche en ingénierie pédagogique.
""")

        st.markdown("### 🔐 Connexion")
        col1, col2 = st.columns([2, 1])
        with col1:
            code = st.text_input("Entrez votre code (fourni par votre enseignant)",
                                  placeholder="Ex: STI-K7M2", max_chars=10).upper().strip()
        with col2:
            st.markdown("&nbsp;")
            connect = st.button("🚀 Se connecter", type="primary", use_container_width=True)

        if connect and code:
            inscription = get_inscription(code)
            if inscription and inscription.get("consentement"):
                # Connexion existante
                st.session_state.code_etudiant = code
                st.session_state.inscription = inscription
                st.success("✅ Connecté !")
                st.rerun()
            elif inscription and not inscription.get("consentement"):
                st.warning("⚠️ Vous devez compléter le formulaire de consentement.")
                st.session_state.code_etudiant = code
                st.session_state.inscription = inscription
                st.rerun()
            else:
                # Code non reconnu — première inscription
                st.session_state.code_etudiant = code
                st.session_state.inscription = None
                st.info("👋 Première connexion — veuillez compléter votre inscription ci-dessous")
                st.rerun()

    elif not st.session_state.inscription or not st.session_state.inscription.get("consentement"):
        # ── Formulaire de consentement + inscription ─────────────────────────
        st.markdown(f"### 📋 Inscription — Code : `{st.session_state.code_etudiant}`")

        with st.expander("📜 Consentement éclairé (à lire attentivement)", expanded=True):
            st.markdown("""
**Information sur l'étude**

Cette étude porte sur l'utilisation d'un Système de Tutorat Intelligent (STI) pour
améliorer la qualité de vos questions et votre apprentissage.

**Ce que nous collectons :**
- Vos questions textuelles et les réponses du système
- Des scores automatiques de qualité
- Vos réponses aux questionnaires pré et post-test
- Votre niveau académique et un code anonymisé (jamais votre nom complet)

**Ce que nous ne collectons pas :**
- Votre nom ou identité réelle (le code est anonyme)
- Votre adresse email
- Aucune donnée biométrique ou sensible

**Vos droits (RGPD) :**
- Vous pouvez retirer votre consentement à tout moment
- Vous pouvez demander la suppression de vos données (contactez le chercheur)
- Les données seront anonymisées et utilisées uniquement à des fins de recherche
- Aucune donnée ne sera revendue ou partagée à des tiers commerciaux

**Durée :** 6 semaines, environ 3 sessions par semaine de 10 minutes.
""")

        consentement = st.checkbox("✅ J'ai lu et je consens à participer à cette étude")
        prenom = st.text_input("Votre prénom (pour la personnalisation, ne sera pas publié)",
                                placeholder="Karim")
        niveau = st.selectbox("Votre niveau académique", NIVEAUX, index=1,
                               format_func=lambda n: f"{NIVEAU_EMOJI[n]} {n}")

        if st.button("✅ Valider mon inscription", type="primary"):
            if not consentement:
                st.error("Vous devez consentir pour participer.")
            elif not prenom.strip():
                st.error("Veuillez indiquer votre prénom.")
            else:
                groupe = assignation_aleatoire_groupe(st.session_state.code_etudiant)
                ok = enregistrer_inscription(
                    code=st.session_state.code_etudiant,
                    prenom=prenom.strip(),
                    niveau=niveau,
                    groupe=groupe,
                    consentement=True,
                )
                if ok:
                    st.session_state.inscription = get_inscription(st.session_state.code_etudiant)
                    st.success(f"✅ Inscription validée ! Vous êtes dans le groupe **{groupe}**.")
                    st.balloons()
                    st.info("👉 Étape suivante : compléter le questionnaire pré-test (page de gauche)")
                else:
                    st.error("❌ Erreur lors de l'enregistrement.")

    else:
        # ── Étudiant connecté et inscrit ──────────────────────────────────────
        ins = st.session_state.inscription
        avatar_message(
            f"Bonjour {ins.get('prenom','')} ! Bienvenue dans votre espace de l'étude. "
            f"Vous êtes connecté au groupe **{ins.get('groupe','')}**."
        )

        # Vérifier si le pré-test a été complété
        a_pretest = a_complete_questionnaire(st.session_state.code_etudiant, "pretest")
        a_posttest = a_complete_questionnaire(st.session_state.code_etudiant, "posttest")

        st.markdown("### 📅 Votre parcours dans l'étude")
        col1, col2, col3 = st.columns(3)
        with col1:
            if a_pretest:
                st.success("✅ Étape 1 : Pré-test complété")
            else:
                st.warning("⏳ Étape 1 : Pré-test à compléter")
                st.caption("👉 Allez dans 'Questionnaire pré-test'")
        with col2:
            sessions = charger_sessions_etudiant(st.session_state.code_etudiant)
            n = len(sessions)
            if n == 0:
                st.info("⏳ Étape 2 : Sessions (0 session)")
            elif n < 18:
                st.info(f"🚀 Étape 2 : Sessions ({n}/18 environ)")
            else:
                st.success(f"✅ Étape 2 : Sessions ({n} sessions)")
        with col3:
            if a_posttest:
                st.success("✅ Étape 3 : Post-test complété")
            elif n >= 15:
                st.warning("⏳ Étape 3 : Post-test à compléter")
            else:
                st.info("🔒 Étape 3 : Post-test (après quelques sessions)")

        if not a_pretest:
            st.markdown("---")
            st.markdown("### 📋 Avant de commencer")
            st.warning("""
Pour démarrer l'expérimentation, complétez d'abord le **questionnaire pré-test**.
Cela nous permet d'évaluer votre point de départ. Cliquez sur "Questionnaire pré-test"
dans le menu de gauche.
""")
        else:
            st.markdown("---")
            st.markdown("### 🎯 Vos consignes pour l'étude")
            st.markdown(f"""
- Pendant **6 semaines**, posez environ **3 questions par semaine** via la page "Poser une question"
- Variez les thèmes : académique, soft skills, résolution de problème
- Soyez naturel(le) — posez les questions comme vous le feriez normalement
- À la fin des 6 semaines, complétez le **questionnaire post-test**
""")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — POSER UNE QUESTION
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🎓 Poser une question":
    if not st.session_state.code_etudiant or not st.session_state.inscription:
        st.warning("🔐 Vous devez être connecté(e) — allez à la page Accueil")
        st.stop()

    ins = st.session_state.inscription
    if not a_complete_questionnaire(st.session_state.code_etudiant, "pretest"):
        st.warning("📋 Vous devez compléter le questionnaire pré-test avant de commencer")
        st.stop()

    code_etudiant = st.session_state.code_etudiant
    niveau_academique = ins.get("niveau", "Licence 1")
    groupe = ins.get("groupe", "experimental")
    mode = "controle" if groupe == "controle" else "agent"

    st.markdown('<p class="main-title">🎓 Poser une question</p>', unsafe_allow_html=True)
    st.markdown("---")

    # Bandeau d'info groupe
    if groupe == "controle":
        st.info("🔵 Vous êtes dans le **groupe contrôle** : vous interagissez directement avec le STI, sans agent intermédiaire.")
    else:
        st.success("🟢 Vous êtes dans le **groupe expérimental** : un agent enrichit vos questions et vous donne un feedback métacognitif.")

    # Sélecteur thème
    col_t, col_f, col_a = st.columns([2, 1, 1])
    with col_t:
        theme_choisi = st.radio(
            "🎯 Thème de la question",
            list(THEMES.keys()),
            format_func=lambda t: f"{THEMES[t]['icon']} {t}",
            horizontal=True,
        )
    with col_f:
        if mode == "agent":
            format_choisi = st.selectbox(
                "🎨 Format réponse", list(FORMATS.keys()),
                format_func=lambda f: FORMATS[f]["label"],
            )
        else:
            format_choisi = "auto"
            st.caption("Format texte (mode contrôle)")
    with col_a:
        audio_on = st.toggle("🔊 Audio", value=False)

    st.caption(f"💡 _{THEMES[theme_choisi]['description']}_  · Exemple : « {THEMES[theme_choisi]['exemple_question']} »")
    st.markdown("---")

    requete = st.text_area("💬 Votre question :", height=110,
                            placeholder=THEMES[theme_choisi]["exemple_question"])
    envoyer = st.button("🚀 Envoyer", type="primary")

    if envoyer:
        if not requete.strip():
            st.warning("Saisissez une question avant d'envoyer.")
            st.stop()

        with st.spinner("🔍 Traitement en cours..."):
            try:
                fmt_param = None if format_choisi == "auto" else format_choisi
                result = pipeline_complet(
                    requete_etudiant=requete,
                    code_etudiant=code_etudiant,
                    niveau_academique=niveau_academique,
                    theme=theme_choisi,
                    format_choisi=fmt_param,
                    mode=mode,
                )
            except Exception as e:
                st.error(f"❌ Erreur : {e}")
                st.stop()

        # ── Affichage selon le mode ───────────────────────────────────────────
        if mode == "controle":
            # Mode contrôle : seulement la réponse STI, rien d'autre
            st.markdown("### 💡 Réponse du STI")
            st.write(result["reponse_sti"])
            if audio_on:
                audio_tts(result["reponse_sti"][:500])
            if result.get("_sauvegarde_ok"):
                st.toast("💾 Session enregistrée", icon="✅")

        else:
            # Mode agent : pipeline complet avec feedback
            diag = result["diagnostic"]
            eval_ = result["evaluation"]
            phase = result["phase_fading"]
            score_actuel = eval_["score_global"]

            avatar_message(
                f"Niveau Bloom : {diag['bloom_label']}. "
                f"Score de votre question : {int(score_actuel*100)}%. "
                f"Format de réponse : {result['format_reponse']}.",
                talking=True
            )

            st.markdown("### 📊 Score")
            c1, c2, c3, c4 = st.columns(4)
            delta_txt = eval_.get("gain_etudiant_pct")
            if delta_txt == "première session":
                delta_txt = None
            gain_e = eval_.get("gain_etudiant")
            c1.metric("⭐ Score", f"{int(score_actuel*100)}%", delta=delta_txt,
                       delta_color="normal" if (gain_e is None or gain_e >= 0) else "inverse")
            c2.metric("🧠 Bloom", f"{diag['bloom_level']} - {diag['bloom_label']}")
            c3.metric("✨ Gain agent", eval_.get("gain_agent_pct", "N/A"))
            c4.metric("🔧 Phase", f"Phase {phase['phase']}")

            st.markdown("### 🔄 Question originale → enrichie")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**❶ Originale**")
                st.info(requete)
            with col_b:
                st.markdown("**❷ Enrichie**")
                st.success(result["requete_enrichie"])

            st.markdown("### 💡 Réponse du STI")
            render_reponse(result, audio_on)

            st.markdown("### 🧠 Feedback")
            st.markdown(f'<div class="box box-blue">📌 <b>Verdict :</b> {eval_.get("gain_qualitatif","")}</div>',
                         unsafe_allow_html=True)
            avatar_message(eval_.get("feedback_metacognitif", ""), talking=True)
            st.markdown(f'<div class="box box-orange">🔍 <b>Ce qui manquait :</b> '
                        f'{eval_.get("ce_qui_manquait","")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="box box-blue">💡 <b>Conseil :</b> '
                        f'{eval_.get("conseil_prochain","")}</div>', unsafe_allow_html=True)

            if audio_on:
                audio_tts(eval_.get("feedback_metacognitif", ""))

            if result.get("_sauvegarde_ok"):
                st.toast("💾 Session enregistrée", icon="✅")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — QUESTIONNAIRE PRÉ-TEST
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Questionnaire pré-test":
    if not st.session_state.code_etudiant or not st.session_state.inscription:
        st.warning("🔐 Vous devez être connecté(e)")
        st.stop()

    code = st.session_state.code_etudiant
    if a_complete_questionnaire(code, "pretest"):
        st.success("✅ Vous avez déjà complété le questionnaire pré-test. Merci !")
        st.markdown("👉 Vous pouvez maintenant aller à la page **'Poser une question'**")
        st.stop()

    st.markdown('<p class="main-title">📋 Questionnaire pré-test</p>', unsafe_allow_html=True)
    st.caption("À compléter AVANT de commencer les sessions avec le système.")
    st.markdown("---")

    avatar_message(
        "Bonjour ! Avant de commencer, nous avons besoin d'évaluer votre point de départ. "
        "Cela permettra de mesurer votre progression à la fin de l'étude. "
        "Toutes vos réponses sont anonymes."
    )

    reponses = {}

    # Métacognition
    st.markdown(f"### 1. {PRETEST_ITEMS['metacognition']['titre']}")
    st.caption(PRETEST_ITEMS['metacognition']['description'])
    meta_rep = []
    for i, q in enumerate(PRETEST_ITEMS['metacognition']['questions']):
        v = st.slider(f"{i+1}. {q}", 1, 5, 3, key=f"meta_{i}")
        meta_rep.append(v)
    reponses["metacognition"] = meta_rep

    # Auto-efficacité
    st.markdown(f"### 2. {PRETEST_ITEMS['auto_efficacite']['titre']}")
    st.caption(PRETEST_ITEMS['auto_efficacite']['description'])
    ae_rep = []
    for i, q in enumerate(PRETEST_ITEMS['auto_efficacite']['questions']):
        v = st.slider(f"{i+1}. {q}", 1, 5, 3, key=f"ae_{i}")
        ae_rep.append(v)
    reponses["auto_efficacite"] = ae_rep

    # Expérience préalable
    st.markdown(f"### 3. {PRETEST_ITEMS['experience']['titre']}")
    exp_rep = {}
    for key, label, options in PRETEST_ITEMS['experience']['questions_libres']:
        exp_rep[key] = st.radio(label, options, key=f"exp_{key}")
    reponses["experience"] = exp_rep

    if st.button("✅ Valider mes réponses", type="primary"):
        ok = enregistrer_questionnaire(code, "pretest", reponses)
        if ok:
            st.success("✅ Merci ! Votre pré-test est enregistré.")
            st.balloons()
            st.info("👉 Vous pouvez maintenant aller à la page **'Poser une question'**")
        else:
            st.error("❌ Erreur lors de l'enregistrement.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — QUESTIONNAIRE POST-TEST
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Questionnaire post-test":
    if not st.session_state.code_etudiant or not st.session_state.inscription:
        st.warning("🔐 Vous devez être connecté(e)")
        st.stop()

    code = st.session_state.code_etudiant
    if a_complete_questionnaire(code, "posttest"):
        st.success("✅ Vous avez déjà complété le post-test. Merci pour votre participation !")
        st.balloons()
        st.stop()

    n_sessions = len(charger_sessions_etudiant(code))
    if n_sessions < 5:
        st.warning(f"⏳ Vous n'avez fait que **{n_sessions} sessions**. "
                   f"Nous recommandons d'en faire au moins **15** avant de compléter le post-test.")

    st.markdown('<p class="main-title">📋 Questionnaire post-test</p>', unsafe_allow_html=True)
    st.caption("À compléter APRÈS les 6 semaines d'expérimentation.")
    st.markdown("---")

    avatar_message(
        f"Vous avez complété {n_sessions} sessions. Merci ! Voici le questionnaire final "
        "pour mesurer votre progression et recueillir votre ressenti."
    )

    reponses = {}

    st.markdown(f"### 1. {POSTTEST_ITEMS['metacognition']['titre']}")
    st.caption(POSTTEST_ITEMS['metacognition']['description'])
    meta_rep = []
    for i, q in enumerate(POSTTEST_ITEMS['metacognition']['questions']):
        v = st.slider(f"{i+1}. {q}", 1, 5, 3, key=f"pmeta_{i}")
        meta_rep.append(v)
    reponses["metacognition"] = meta_rep

    st.markdown(f"### 2. {POSTTEST_ITEMS['auto_efficacite']['titre']}")
    st.caption(POSTTEST_ITEMS['auto_efficacite']['description'])
    ae_rep = []
    for i, q in enumerate(POSTTEST_ITEMS['auto_efficacite']['questions']):
        v = st.slider(f"{i+1}. {q}", 1, 5, 3, key=f"pae_{i}")
        ae_rep.append(v)
    reponses["auto_efficacite"] = ae_rep

    st.markdown(f"### 3. {POSTTEST_ITEMS['sus']['titre']}")
    st.caption(POSTTEST_ITEMS['sus']['description'])
    sus_rep = []
    for i, q in enumerate(POSTTEST_ITEMS['sus']['questions']):
        v = st.slider(f"{i+1}. {q}", 1, 5, 3, key=f"sus_{i}")
        sus_rep.append(v)
    reponses["sus"] = sus_rep

    st.markdown(f"### 4. {POSTTEST_ITEMS['ressenti']['titre']}")
    res_rep = {}
    for item in POSTTEST_ITEMS['ressenti']['questions_libres']:
        if len(item) == 3 and item[2] == "text":
            key, label, _ = item
            res_rep[key] = st.text_area(label, key=f"res_{key}")
        else:
            key, label, options = item
            res_rep[key] = st.radio(label, options, key=f"res_{key}")
    reponses["ressenti"] = res_rep

    if st.button("✅ Valider mes réponses", type="primary"):
        ok = enregistrer_questionnaire(code, "posttest", reponses)
        if ok:
            st.success("✅ Merci infiniment pour votre participation à cette étude !")
            st.balloons()
        else:
            st.error("❌ Erreur lors de l'enregistrement.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — HISTORIQUE ÉTUDIANT (lui-même)
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🔍 Mon historique":
    if not st.session_state.code_etudiant:
        st.warning("🔐 Connectez-vous d'abord")
        st.stop()

    code = st.session_state.code_etudiant
    historique = charger_sessions_etudiant(code)

    st.markdown('<p class="main-title">🔍 Mon historique</p>', unsafe_allow_html=True)
    st.markdown("---")

    if not historique:
        st.info("Aucune session pour le moment. Commencez par poser une question !")
        st.stop()

    scores = [round(s.get("evaluation", {}).get("score_global", 0) * 100) for s in historique]
    dates = [s.get("timestamp", "")[:16].replace("T", " ") for s in historique]

    st.markdown(f"### 📈 Votre progression ({len(historique)} sessions)")
    st.line_chart(pd.DataFrame({"Score (%)": scores},
                                index=[f"Q{i+1}" for i in range(len(scores))]))

    if len(historique) >= 2:
        delta = scores[-1] - scores[0]
        if delta > 5:
            st.success(f"📈 Progression de +{delta} points depuis votre première question")
        elif delta < -5:
            st.warning(f"📉 Régression de {abs(delta)} points")
        else:
            st.info(f"➡️ Score stable ({delta:+d} points)")

    st.markdown("### 📋 Détail")
    for i, s in enumerate(historique):
        ev = s.get("evaluation", {})
        score = round(ev.get("score_global", 0) * 100)
        with st.expander(f"Q{i+1} — {dates[i]} — Score : {score}%"):
            st.markdown("**Votre question :**")
            st.info(s.get("requete_originale", ""))
            if s.get("requete_enrichie"):
                st.markdown("**Question enrichie :**")
                st.success(s.get("requete_enrichie", ""))
            st.markdown("**Réponse STI (extrait) :**")
            st.caption(s.get("reponse_sti", "")[:300] + "...")
            if ev.get("conseil_prochain"):
                st.markdown(f"💡 **Conseil :** {ev['conseil_prochain']}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE — ESPACE ENSEIGNANT (protégé par mot de passe)
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "👨‍🏫 Espace enseignant":
    st.markdown('<p class="main-title">👨‍🏫 Espace enseignant</p>', unsafe_allow_html=True)

    if "teacher_auth" not in st.session_state:
        st.session_state.teacher_auth = False

    if not st.session_state.teacher_auth:
        st.markdown("### 🔐 Connexion enseignant")
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if pwd == TEACHER_PASSWORD:
                st.session_state.teacher_auth = True
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect")
        st.stop()

    st.success("✅ Connecté en tant qu'enseignant")

    # ── Statut Supabase ───────────────────────────────────────────────────────
    from database import _get_supabase_client, _get_supabase_creds
    status = get_status_supabase()
    if status == "connecte":
        st.success("🟢 **Supabase connecté** — données persistées dans le cloud")
    elif status == "erreur":
        st.error("🔴 **Erreur Supabase** — vérifiez SUPABASE_URL et SUPABASE_KEY dans Secrets")
    else:
        st.warning("🟡 **Mode local** — données dans sessions.json (perdues au redémarrage !)")
        with st.expander("ℹ️ Comment corriger ?"):
            st.markdown("""
**Sur Streamlit Cloud :**
1. Allez dans votre app → ⋮ (3 points) → **Settings** → **Secrets**
2. Ajoutez ces deux lignes :
```
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "votre-cle-anon"
```
3. Cliquez **Save** — l'app redémarre automatiquement
""")

    if st.button("🔌 Tester la connexion Supabase"):
        url, key = _get_supabase_creds()
        st.code(f"URL : {'✅ ' + url[:35] + '...' if url else '❌ vide'}")
        st.code(f"KEY : {'✅ ' + key[:20] + '...' if key else '❌ vide'}")
        client = _get_supabase_client()
        if client:
            try:
                client.table("sessions").select("id").limit(1).execute()
                st.success("✅ Supabase OK — table sessions accessible")
            except Exception as e:
                st.error(f"❌ Table inaccessible : {e}")
                st.caption("Avez-vous bien exécuté le SQL de création des tables ?")
        else:
            st.error("❌ Connexion impossible — credentials manquants ou invalides")
    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Vue d'ensemble", "👥 Comparaison groupes",
        "🎫 Générer codes", "📥 Export CSV"
    ])

    sessions = charger_sessions()

    # ─── TAB 1 : Vue d'ensemble ───────────────────────────────────────────────
    with tab1:
        if not sessions:
            st.info("Aucune session enregistrée pour le moment.")
        else:
            df = pd.DataFrame([{
                "Étudiant":     s.get("etudiant", "N/A"),
                "Groupe":       s.get("groupe", "N/A"),
                "Mode":         s.get("mode", "N/A"),
                "Niveau":       s.get("niveau_academique", "N/A"),
                "Thème":        s.get("theme", "N/A"),
                "Format":       s.get("format_reponse", "N/A"),
                "Date":         s.get("timestamp", "")[:16].replace("T", " "),
                "Bloom":        s.get("diagnostic", {}).get("bloom_level", 0),
                "Score":        round(s.get("evaluation", {}).get("score_global", 0) * 100),
                "Question":     s.get("requete_originale", "")[:60] + "...",
            } for s in sessions])

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Sessions totales", len(df))
            k2.metric("Étudiants actifs", df["Étudiant"].nunique())
            k3.metric("Score moyen global", f"{df['Score'].mean():.0f}%")
            k4.metric("Score Bloom moyen", f"{df['Bloom'].mean():.1f}/6")

            st.markdown("### 📈 Score global au fil du temps")
            df_sorted = df.sort_values("Date").reset_index(drop=True)
            df_sorted.index = range(1, len(df_sorted) + 1)
            st.line_chart(df_sorted["Score"])

            st.markdown("### 📋 Toutes les sessions")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ─── TAB 2 : Comparaison groupes ──────────────────────────────────────────
    with tab2:
        st.markdown("### 🔬 Comparaison Groupe Contrôle vs Groupe Expérimental")

        if not sessions:
            st.info("Pas encore de données.")
        else:
            df = pd.DataFrame([{
                "Étudiant": s.get("etudiant", ""),
                "Groupe":   s.get("groupe", ""),
                "Score":    round(s.get("evaluation", {}).get("score_global", 0) * 100),
                "Bloom":    s.get("diagnostic", {}).get("bloom_level", 0) or 0,
                "Date":     s.get("timestamp", "")[:10],
            } for s in sessions if s.get("groupe") in ("controle", "experimental")])

            if df.empty:
                st.warning("Pas encore d'étudiants assignés à un groupe.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### 🔵 Groupe contrôle")
                    ctrl = df[df["Groupe"] == "controle"]
                    st.metric("Étudiants", ctrl["Étudiant"].nunique())
                    st.metric("Sessions", len(ctrl))
                    st.metric("Score moyen", f"{ctrl['Score'].mean():.1f}%" if len(ctrl) else "N/A")
                    st.metric("Bloom moyen", f"{ctrl['Bloom'].mean():.2f}" if len(ctrl) else "N/A")
                with col2:
                    st.markdown("#### 🟢 Groupe expérimental")
                    exp = df[df["Groupe"] == "experimental"]
                    st.metric("Étudiants", exp["Étudiant"].nunique())
                    st.metric("Sessions", len(exp))
                    st.metric("Score moyen", f"{exp['Score'].mean():.1f}%" if len(exp) else "N/A")
                    st.metric("Bloom moyen", f"{exp['Bloom'].mean():.2f}" if len(exp) else "N/A")

                st.markdown("### 📊 Évolution des scores moyens par groupe")
                df["Date"] = pd.to_datetime(df["Date"])
                pivot = df.groupby([df["Date"].dt.to_period("W"), "Groupe"])["Score"].mean().unstack()
                if not pivot.empty:
                    pivot.index = pivot.index.astype(str)
                    st.line_chart(pivot)

                st.markdown("### 🎯 Différence de moyenne (test t indépendant)")
                if len(ctrl) > 5 and len(exp) > 5:
                    try:
                        from scipy import stats
                        t, p = stats.ttest_ind(exp["Score"], ctrl["Score"], equal_var=False)
                        st.metric("t-statistique", f"{t:.3f}")
                        st.metric("p-value", f"{p:.4f}")
                        if p < 0.05:
                            st.success(f"✅ Différence statistiquement significative (p < 0.05) — "
                                       f"l'agent a un effet mesurable.")
                        else:
                            st.info(f"ℹ️ Pas de différence significative à ce stade (p = {p:.3f})")
                    except ImportError:
                        st.caption("Installez scipy pour le test t")
                else:
                    st.caption("Trop peu de données pour un test statistique.")

    # ─── TAB 3 : Générer codes ────────────────────────────────────────────────
    with tab3:
        st.markdown("### 🎫 Générer des codes étudiants")
        st.caption("Distribuez ces codes anonymisés à vos étudiants. "
                   "Chaque étudiant entre son code à la première connexion.")

        col1, col2 = st.columns(2)
        with col1:
            n_ctrl = st.number_input("Nombre groupe contrôle", min_value=1, max_value=100, value=30)
        with col2:
            n_exp = st.number_input("Nombre groupe expérimental", min_value=1, max_value=100, value=30)

        if st.button("🎫 Générer les codes"):
            codes = generer_lot_codes(n_ctrl, n_exp)
            df_codes = pd.DataFrame(codes)
            st.success(f"✅ {len(codes)} codes générés")
            st.dataframe(df_codes, use_container_width=True, hide_index=True)

            csv = df_codes.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Télécharger en CSV",
                csv,
                "codes_etudiants.csv",
                "text/csv"
            )

            st.warning("⚠️ **Important** : Ces codes ne sont PAS encore enregistrés dans la base. "
                        "Ils sont simplement générés. L'étudiant les enregistre lui-même "
                        "lors de sa première inscription en validant le consentement.")

    # ─── TAB 4 : Export CSV ───────────────────────────────────────────────────
    with tab4:
        st.markdown("### 📥 Export pour analyse statistique")

        if not sessions:
            st.info("Pas encore de données à exporter.")
        else:
            # Sessions complètes
            df_sessions = pd.DataFrame([{
                "code_etudiant":     s.get("etudiant", ""),
                "groupe":            s.get("groupe", ""),
                "mode":              s.get("mode", ""),
                "niveau_academique": s.get("niveau_academique", ""),
                "theme":             s.get("theme", ""),
                "timestamp":         s.get("timestamp", ""),
                "format_reponse":    s.get("format_reponse", ""),
                "bloom_level":       s.get("diagnostic", {}).get("bloom_level", 0),
                "ambiguity_score":   s.get("diagnostic", {}).get("ambiguity_score", 0),
                "score_global":      s.get("evaluation", {}).get("score_global", 0),
                "score_precision":   s.get("evaluation", {}).get("score_precision", 0),
                "score_profondeur":  s.get("evaluation", {}).get("score_profondeur", 0),
                "score_contexte":    s.get("evaluation", {}).get("score_contexte", 0),
                "gain_etudiant":     s.get("evaluation", {}).get("gain_etudiant"),
                "gain_agent":        s.get("evaluation", {}).get("gain_agent"),
                "phase_fading":      s.get("phase_fading", {}).get("phase", 0),
                "requete_originale": s.get("requete_originale", ""),
                "requete_enrichie":  s.get("requete_enrichie", ""),
            } for s in sessions])

            csv = df_sessions.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Télécharger toutes les sessions (CSV)",
                csv,
                f"sessions_export_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )

            st.markdown(f"**Aperçu** : {len(df_sessions)} lignes")
            st.dataframe(df_sessions.head(20), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### 💡 Pour votre rapport de PFE")
            st.code("""
# Exemple Python pour analyse :
import pandas as pd
from scipy import stats

df = pd.read_csv("sessions_export_YYYYMMDD.csv")

# Test H1 : score moyen plus élevé dans le groupe expérimental ?
ctrl = df[df["groupe"] == "controle"]["score_global"]
exp  = df[df["groupe"] == "experimental"]["score_global"]
t, p = stats.ttest_ind(exp, ctrl, equal_var=False)
print(f"t = {t:.3f}, p = {p:.4f}")

# Test H2 : niveau Bloom moyen ?
t, p = stats.ttest_ind(exp.bloom_level, ctrl.bloom_level)
""", language="python")
