"""
Page principale : import de PDF → extraction IA → registre
Supporte l'upload de 1 ou plusieurs PDF simultanément.
"""
import streamlit as st
import json
import pandas as pd
from utils.pdf_extractor import process_pdf, extract_text_from_pdf


def _field(label, val, editable=False, key=None):
    """Affiche un champ avec sa valeur extraite."""
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"<span style='color:#555;font-size:0.85rem;font-weight:600'>{label}</span>",
                    unsafe_allow_html=True)
    with col2:
        display = str(val) if val not in (None, "None", "nan", "") else "—"
        color = "#155724" if val not in (None, "None", "nan", "") else "#999"
        st.markdown(f"<span style='color:{color};font-size:0.9rem'>{display}</span>",
                    unsafe_allow_html=True)


def _confidence_badge(data: dict) -> str:
    """Calcule un score de confiance basé sur les champs non-null."""
    fields_patient = ["nom", "prenom", "date_naissance", "sexe", "ipp"]
    fields_tumeur  = ["taille_mm", "cote", "ct", "renal_score", "dfg"]
    fields_inter   = ["type_intervention", "technique", "pt", "histologie", "marges"]

    total, filled = 0, 0
    for f in fields_patient:
        total += 1
        if data["patient"].get(f): filled += 1
    for f in fields_tumeur:
        total += 1
        if data["tumeur"].get(f): filled += 1
    if data["intervention"]:
        for f in fields_inter:
            total += 1
            if data["intervention"].get(f): filled += 1

    pct = int(filled / total * 100) if total else 0
    color = "#28a745" if pct >= 75 else "#ffc107" if pct >= 50 else "#dc3545"
    return f'<span style="background:{color};color:white;padding:3px 10px;border-radius:12px;font-weight:700;font-size:0.85rem">{pct}% données extraites</span>'


def show():
    st.title("📥 Import de PDF – Extraction automatique IA")
    st.caption("Chargez un ou plusieurs CRC/CRO : Claude analyse le document et alimente le registre automatiquement.")

    # ── Instructions ──────────────────────────────────────────────────────────
    with st.expander("ℹ️ Comment ça fonctionne ?", expanded=False):
        st.markdown("""
        **Pipeline complet :**
        1. **Upload** : déposez 1 ou plusieurs PDF (CRC, CRO, ou les deux en un seul fichier)
        2. **Extraction texte** : lecture du contenu textuel du PDF (pypdf)
        3. **Analyse IA** : Claude lit le document et extrait les données structurées
        4. **Prévisualisation** : vous vérifiez les données avant enregistrement
        5. **Enregistrement** : insertion en base SQLite, dossier créé automatiquement

        **Données extraites automatiquement :**
        - Identité patient (nom, prénom, DDN, sexe, IPP)
        - Données tumorales (taille, côté, localisation, RENAL score, stade cTNM, DFG)
        - Décision RCP
        - Intervention (technique, durée, ischémie chaude, pertes sanguines)
        - Anatomopathologie (pTNM, grade ISUP, histologie, marges)
        - Complications (Clavien-Dindo)
        """)

    # ── Clé API ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🔑 Clé API Anthropic")
    st.info("Sur Streamlit Cloud, ajoutez `ANTHROPIC_API_KEY` dans **Settings → Secrets** "
            "(`ANTHROPIC_API_KEY = \"sk-ant-...\"`). En local, définissez la variable d'environnement.")

    import os
    import anthropic
    api_key_input = st.text_input("Clé API (optionnel si déjà en variable d'env.)",
                                   type="password", placeholder="sk-ant-api03-...",
                                   help="Laissez vide si ANTHROPIC_API_KEY est déjà défini dans l'environnement.")
    if api_key_input:
        os.environ["ANTHROPIC_API_KEY"] = api_key_input

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        st.warning("⚠️ Clé API manquante. Renseignez-la ci-dessus ou dans les secrets Streamlit.")

    # ── Upload ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📄 Sélection des fichiers PDF")
    uploaded_files = st.file_uploader(
        "Déposez un ou plusieurs PDF (CRC, CRO, ou dossier complet)",
        type=["pdf"],
        accept_multiple_files=True,
        disabled=not has_key,
    )

    if not uploaded_files:
        st.markdown("""
        <div style='border:2px dashed #b0c8e0;border-radius:8px;padding:40px;text-align:center;color:#666;margin-top:16px'>
            <div style='font-size:2rem'>📂</div>
            <div style='margin-top:8px'>Glissez vos fichiers PDF ici ou cliquez pour sélectionner</div>
            <div style='font-size:0.8rem;margin-top:4px;color:#999'>Formats supportés : CRC, CRO, dossier combiné</div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(f"**{len(uploaded_files)} fichier(s) chargé(s)**")

    # ── Traitement fichier par fichier ────────────────────────────────────────
    if "extractions" not in st.session_state:
        st.session_state.extractions = {}

    # Bouton lancement extraction
    if st.button(f"🤖 Analyser {len(uploaded_files)} PDF avec Claude", type="primary",
                 use_container_width=True, disabled=not has_key):
        st.session_state.extractions = {}
        progress = st.progress(0, text="Initialisation...")

        for idx, f in enumerate(uploaded_files):
            progress.progress((idx) / len(uploaded_files),
                              text=f"Analyse de {f.name} ({idx+1}/{len(uploaded_files)})...")
            try:
                pdf_bytes = f.read()
                # Aperçu texte extrait
                with st.spinner(f"Lecture de {f.name}..."):
                    txt = extract_text_from_pdf(pdf_bytes)

                with st.spinner(f"Claude analyse {f.name}..."):
                    result = process_pdf(pdf_bytes, f.name)

                st.session_state.extractions[f.name] = {
                    "result": result,
                    "status": "success",
                    "text_preview": txt[:500],
                }
            except Exception as e:
                st.session_state.extractions[f.name] = {
                    "status": "error",
                    "error": str(e),
                }

        progress.progress(1.0, text="✅ Analyse terminée !")

    # ── Résultats ─────────────────────────────────────────────────────────────
    if st.session_state.get("extractions"):
        st.markdown("---")
        st.markdown("### 📋 Résultats de l'extraction")

        for fname, extr in st.session_state.extractions.items():
            with st.expander(f"📄 {fname}", expanded=True):
                if extr["status"] == "error":
                    st.error(f"❌ Erreur : {extr['error']}")
                    continue

                result = extr["result"]
                data = result

                # Badge confiance
                st.markdown(_confidence_badge(data), unsafe_allow_html=True)
                st.markdown(f"<small style='color:#28a745'>✅ Enregistré – Patient ID : **{data['patient_id']}**</small>",
                            unsafe_allow_html=True)
                st.markdown("")

                tab1, tab2, tab3, tab4 = st.tabs(["👤 Patient", "🔬 Tumeur", "🔪 Intervention", "🗂️ JSON brut"])

                with tab1:
                    p = data["patient"]
                    col1, col2 = st.columns(2)
                    with col1:
                        _field("Nom", p.get("nom"))
                        _field("Prénom", p.get("prenom"))
                        _field("Date de naissance", p.get("date_naissance"))
                        _field("Sexe", p.get("sexe"))
                    with col2:
                        _field("IPP", p.get("ipp"))
                        _field("Adresse", p.get("adresse"))
                        _field("Médecin traitant", p.get("medecin_traitant"))

                with tab2:
                    t = data["tumeur"]
                    col1, col2 = st.columns(2)
                    with col1:
                        _field("Côté", t.get("cote"))
                        _field("Taille (mm)", t.get("taille_mm"))
                        _field("Localisation", t.get("localisation"))
                        _field("Exophytique (%)", t.get("exophytique_pct"))
                        _field("RENAL score", t.get("renal_score"))
                        _field("Imagerie", f"{t.get('type_imagerie')} – {t.get('date_imagerie')}")
                    with col2:
                        _field("cT", t.get("ct"))
                        _field("cN", t.get("cn"))
                        _field("cM", t.get("cm"))
                        _field("Créatinine (µmol/L)", t.get("creatinine"))
                        _field("DFG (mL/min)", t.get("dfg"))
                        _field("Date RCP", t.get("date_rcp"))
                    if t.get("decision_rcp"):
                        st.markdown(f"**Décision RCP :** {t['decision_rcp']}")

                with tab3:
                    if data.get("surveillance"):
                        st.info("🔭 Surveillance active – pas d'intervention chirurgicale")
                    elif data.get("intervention"):
                        i = data["intervention"]
                        col1, col2 = st.columns(2)
                        with col1:
                            _field("Date", i.get("date_intervention"))
                            _field("Type", i.get("type_intervention"))
                            _field("Technique", i.get("technique"))
                            _field("Voie d'abord", i.get("voie_abord"))
                            _field("Chirurgien", i.get("chirurgien"))
                            _field("Durée (min)", i.get("duree_min"))
                            _field("Ischémie chaude (min)", i.get("ischemie_chaude_min"))
                            _field("Pertes sanguines (mL)", i.get("pertes_sanguines_ml"))
                        with col2:
                            _field("pT", i.get("pt"))
                            _field("pN", i.get("pn"))
                            _field("pM", i.get("pm"))
                            _field("Grade ISUP", i.get("grade_isup"))
                            _field("Histologie", i.get("histologie"))
                            _field("Marges", i.get("marges"))
                            _field("Marge min. (mm)", i.get("marge_mm"))
                            _field("Hospit. (j)", i.get("duree_hospit_j"))
                            _field("Clavien-Dindo", i.get("complication_clavien"))
                    else:
                        st.warning("Données interventionnelles non trouvées dans le PDF")

                with tab4:
                    st.code(json.dumps(data.get("raw_json", {}), ensure_ascii=False, indent=2),
                            language="json")
                    if extr.get("text_preview"):
                        with st.expander("Texte brut extrait du PDF (aperçu)"):
                            st.text(extr["text_preview"])

        st.markdown("---")
        n_ok = sum(1 for e in st.session_state.extractions.values() if e["status"] == "success")
        n_err = len(st.session_state.extractions) - n_ok
        if n_ok:
            st.success(f"✅ {n_ok} dossier(s) ajouté(s) au registre.")
        if n_err:
            st.error(f"❌ {n_err} fichier(s) en erreur.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Voir la liste des patients", use_container_width=True):
                st.session_state.extractions = {}
                st.rerun()
        with col2:
            if st.button("🔄 Importer d'autres PDF", use_container_width=True):
                st.session_state.extractions = {}
                st.rerun()
