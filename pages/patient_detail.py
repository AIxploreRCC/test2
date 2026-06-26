import streamlit as st
from utils.database import get_all_patients, get_patient_full, insert_suivi
from datetime import date


def show():
    st.title("🔍 Fiche patient")

    df = get_all_patients()
    if df.empty:
        st.info("Aucun patient.")
        return

    ids    = df["id"].tolist()
    labels = [f"ID {r['id']} – {r['nom']} {r['prenom']}" for _, r in df.iterrows()]

    default = 0
    if "patient_id" in st.session_state and st.session_state["patient_id"] in ids:
        default = ids.index(st.session_state["patient_id"])

    sel = st.selectbox("Patient", labels, index=default)
    pid = ids[labels.index(sel)]
    st.session_state["patient_id"] = pid

    data = get_patient_full(pid)
    p      = data["patient"]
    tumeurs = data["tumeurs"]
    inter   = data["interventions"]
    suivis  = data["suivis"]

    if not p:
        st.error("Patient introuvable.")
        return

    st.markdown("---")
    hc1, hc2 = st.columns([2,1])
    with hc1:
        st.markdown(f"## {p.get('nom','')} {p.get('prenom','')}")
        st.markdown(f"**IPP :** {p.get('ipp','–')}  |  **DDN :** {p.get('date_naissance','–')}  |  **Sexe :** {p.get('sexe','–')}")
        st.markdown(f"**Médecin traitant :** {p.get('medecin_traitant','–')}")
        if p.get("adresse"):
            st.markdown(f"**Adresse :** {p['adresse']}")
    with hc2:
        st.info(f"Créé le **{str(p.get('created_at','?'))[:10]}**\n\n📄 Source : `{p.get('source_pdf','–')}`")

    st.markdown('<div class="section-title">🔬 Tumeur</div>', unsafe_allow_html=True)
    if tumeurs.empty:
        st.warning("Aucune donnée tumorale.")
    else:
        for _, t in tumeurs.iterrows():
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Taille", f"{t.get('taille_mm','?')} mm")
            c2.metric("RENAL", t.get("renal_score","?"))
            c3.metric("cT", t.get("ct","?"))
            c4.metric("Côté", t.get("cote","?"))
            c5,c6,c7 = st.columns(3)
            c5.markdown(f"**Imagerie :** {t.get('type_imagerie','?')} — {t.get('date_imagerie','?')}")
            c6.markdown(f"**Localisation :** {t.get('localisation','?')}, exo {t.get('exophytique_pct','?')}%")
            c7.markdown(f"**DFG :** {t.get('dfg','?')} mL/min | Créat. {t.get('creatinine','?')} µmol/L")
            if t.get("decision_rcp"):
                st.markdown(f"**RCP {t.get('date_rcp','')} :** {t['decision_rcp']}")

    st.markdown('<div class="section-title">🔪 Intervention</div>', unsafe_allow_html=True)
    if inter.empty:
        st.info("Surveillance active ou intervention non renseignée.")
    else:
        for _, i in inter.iterrows():
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Technique", i.get("technique","?"))
            c2.metric("Type", i.get("type_intervention","?"))
            c3.metric("Durée", f"{i.get('duree_min','?')} min")
            c4.metric("Ischémie", f"{i.get('ischemie_chaude_min') or '–'} min")
            c5,c6,c7,c8 = st.columns(4)
            c5.metric("pT", i.get("pt","?"))
            c6.metric("Histologie", i.get("histologie","?"))
            c7.metric("Grade ISUP", i.get("grade_isup","?"))
            c8.metric("Marges", i.get("marges","?"))
            st.markdown(
                f"**Chirurgien :** {i.get('chirurgien','?')} | "
                f"**Voie :** {i.get('voie_abord','?')} | "
                f"**Pertes :** {i.get('pertes_sanguines_ml','?')} mL | "
                f"**Clavien :** {i.get('complication_clavien','0')}"
            )
            if i.get("incidents"): st.markdown(f"**Incidents :** {i['incidents']}")
            st.markdown("---")

    st.markdown('<div class="section-title">📅 Suivi</div>', unsafe_allow_html=True)
    if suivis.empty:
        st.info("Aucun suivi enregistré.")
    else:
        for _, s in suivis.iterrows():
            sc1,sc2,sc3 = st.columns(3)
            sc1.markdown(f"**{s.get('date_suivi','?')}** – {s.get('type_suivi','?')}")
            sc2.markdown(f"**{s.get('statut','?')}**")
            sc3.markdown(str(s.get("resultat","") or ""))

    with st.expander("➕ Ajouter un suivi"):
        with st.form(f"suivi_form_{pid}"):
            fs1,fs2,fs3 = st.columns(3)
            ds     = fs1.date_input("Date", value=date.today())
            ts     = fs2.selectbox("Type", ["Consultation","Imagerie","Biologie","Mixte"])
            statut = fs3.selectbox("Statut", ["Sans récidive","Récidive locale","Métastase","Décès","Perdu de vue"])
            res    = st.text_area("Résultat / Notes", height=70)
            if st.form_submit_button("Enregistrer le suivi", type="primary"):
                insert_suivi({
                    "patient_id": pid,
                    "date_suivi": str(ds),
                    "type_suivi": ts,
                    "resultat": res,
                    "statut": statut,
                    "notes": None,
                })
                st.success("✅ Suivi ajouté.")
                st.rerun()
