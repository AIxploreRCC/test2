import streamlit as st
from utils.database import get_all_patients, delete_patient


def show():
    st.title("📋 Liste des patients")

    df = get_all_patients()
    if df.empty:
        st.info("Aucun patient. Importez des PDF via **📥 Importer un PDF**.")
        return

    with st.expander("🔎 Filtres"):
        fc1, fc2, fc3 = st.columns(3)
        f_sexe  = fc1.multiselect("Sexe", ["M","F"], default=["M","F"])
        f_cote  = fc2.multiselect("Côté", ["Droit","Gauche","Bilatéral"], default=["Droit","Gauche","Bilatéral"])
        f_inter = fc3.multiselect("Intervention",
                                   ["Néphro partielle","Néphro totale","Ablatif","Surveillance"],
                                   default=["Néphro partielle","Néphro totale","Ablatif","Surveillance"])
        tmin, tmax = st.slider("Taille (mm)", 0, 200, (0, 200))

    if "sexe" in df.columns and f_sexe:
        df = df[df["sexe"].isin(f_sexe) | df["sexe"].isna()]
    if "cote" in df.columns:
        df = df[df["cote"].isin(f_cote) | df["cote"].isna()]
    if "type_intervention" in df.columns:
        df = df[df["type_intervention"].isin(f_inter) | df["type_intervention"].isna()]
    if "taille_mm" in df.columns:
        df = df[df["taille_mm"].isna() | ((df["taille_mm"] >= tmin) & (df["taille_mm"] <= tmax))]

    st.markdown(f"**{len(df)} patient(s)**")

    display = df[[c for c in ["id","ipp","nom","prenom","date_naissance","sexe",
                               "cote","taille_mm","ct","renal_score","type_intervention",
                               "histologie","pt","grade_isup","marges","source_pdf"] if c in df.columns]]
    st.dataframe(display.rename(columns={
        "id":"ID","ipp":"IPP","nom":"Nom","prenom":"Prénom","date_naissance":"DDN","sexe":"Sexe",
        "cote":"Côté","taille_mm":"Taille (mm)","ct":"cT","renal_score":"RENAL",
        "type_intervention":"Intervention","histologie":"Histologie","pt":"pT",
        "grade_isup":"ISUP","marges":"Marges","source_pdf":"PDF source"
    }), use_container_width=True, hide_index=True)

    st.markdown("---")
    ids    = df["id"].tolist()
    labels = [f"ID {r['id']} – {r['nom']} {r['prenom']}" for _, r in df.iterrows()]

    c1, c2 = st.columns([3,1])
    with c1:
        sel = st.selectbox("Ouvrir un dossier :", labels)
        if st.button("📂 Ouvrir la fiche", type="primary"):
            st.session_state["patient_id"] = ids[labels.index(sel)]
            st.info("Rendez-vous sur '🔍 Fiche patient'.")
    with c2:
        del_sel = st.selectbox("Supprimer :", labels, key="del")
        if st.button("🗑️ Supprimer"):
            delete_patient(ids[labels.index(del_sel)])
            st.warning("Patient supprimé.")
            st.rerun()
