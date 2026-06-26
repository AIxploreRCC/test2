import streamlit as st
import pandas as pd
import io
from utils.database import get_conn


def show():
    st.title("📤 Export des données")

    conn = get_conn()
    patients      = pd.read_sql("SELECT * FROM patients", conn)
    tumeurs       = pd.read_sql("SELECT * FROM tumeurs", conn)
    interventions = pd.read_sql("SELECT * FROM interventions", conn)
    suivis        = pd.read_sql("SELECT * FROM suivis", conn)
    conn.close()

    if patients.empty:
        st.info("Aucune donnée à exporter.")
        return

    full = patients.merge(tumeurs, left_on="id", right_on="patient_id", how="left", suffixes=("","_t"))
    full = full.merge(interventions, left_on="id", right_on="patient_id", how="left", suffixes=("","_i"))

    st.markdown(f"**{len(patients)} patient(s)** dans le registre")
    st.dataframe(full.head(), use_container_width=True)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("#### 📄 CSV fusionné")
        csv = full.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Télécharger CSV", csv,
                           file_name="registre_rein.csv", mime="text/csv",
                           use_container_width=True)

    with c2:
        st.markdown("#### 📊 Excel multi-onglets")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            patients.to_excel(w, sheet_name="Patients", index=False)
            tumeurs.to_excel(w, sheet_name="Tumeurs", index=False)
            interventions.to_excel(w, sheet_name="Interventions", index=False)
            suivis.to_excel(w, sheet_name="Suivis", index=False)
            full.to_excel(w, sheet_name="Données_fusionnées", index=False)
        buf.seek(0)
        st.download_button("⬇️ Télécharger Excel", buf,
                           file_name="registre_rein.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)

    with c3:
        st.markdown("#### 📋 Résumé stats")
        num_cols = [c for c in ["taille_mm","renal_score","dfg","duree_min",
                                 "ischemie_chaude_min","pertes_sanguines_ml","duree_hospit_j"]
                    if c in full.columns]
        summary = full[num_cols].describe().round(1)
        csv_s = summary.to_csv(sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Télécharger résumé", csv_s,
                           file_name="resume_stats.csv", mime="text/csv",
                           use_container_width=True)

    st.markdown("---")
    st.markdown("### Statistiques descriptives")
    num_cols2 = [c for c in ["taille_mm","renal_score","dfg","duree_min",
                              "ischemie_chaude_min","pertes_sanguines_ml","duree_hospit_j"]
                 if c in full.columns]
    st.dataframe(full[num_cols2].describe().round(1), use_container_width=True)
