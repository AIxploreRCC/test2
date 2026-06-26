import streamlit as st
import pandas as pd
import plotly.express as px
from utils.database import get_conn


def show():
    st.title("📊 Statistiques")

    conn = get_conn()
    patients      = pd.read_sql("SELECT * FROM patients", conn)
    tumeurs       = pd.read_sql("SELECT * FROM tumeurs", conn)
    interventions = pd.read_sql("SELECT * FROM interventions", conn)
    conn.close()

    if patients.empty:
        st.info("Aucune donnée. Importez des PDF d'abord.")
        return

    merged = patients.merge(tumeurs, left_on="id", right_on="patient_id", how="left", suffixes=("","_t"))
    merged = merged.merge(interventions, left_on="id", right_on="patient_id", how="left", suffixes=("","_i"))

    tab1, tab2, tab3 = st.tabs(["🧬 Clinique", "🔪 Chirurgie", "🔬 Anapath"])

    with tab1:
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("#### Sexe")
            fig = px.pie(merged, names="sexe", hole=0.4,
                         color_discrete_map={"M":"#2c5f8a","F":"#e8a87c"})
            fig.update_layout(height=270, margin=dict(t=5,b=5))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### Côté tumeur")
            cote = merged["cote"].value_counts().reset_index()
            cote.columns = ["Côté","N"]
            fig = px.bar(cote, x="Côté", y="N", color="Côté",
                         color_discrete_sequence=["#2c5f8a","#4a90c4","#a8d5f5"])
            fig.update_layout(height=270, margin=dict(t=5,b=5), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Distribution taille tumorale")
        fig = px.histogram(merged.dropna(subset=["taille_mm"]), x="taille_mm", nbins=12,
                           color_discrete_sequence=["#2c5f8a"], labels={"taille_mm":"Taille (mm)"})
        fig.add_vline(x=40, line_dash="dash", line_color="red", annotation_text="T1a/T1b")
        fig.update_layout(height=260, margin=dict(t=5,b=5))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### RENAL score vs Taille")
        fig = px.scatter(merged.dropna(subset=["taille_mm","renal_score"]),
                         x="renal_score", y="taille_mm", color="cote",
                         hover_data=["nom","prenom"],
                         labels={"taille_mm":"Taille (mm)","renal_score":"RENAL score"})
        fig.update_layout(height=280, margin=dict(t=5,b=5))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("#### Type d'intervention")
            fig = px.pie(merged.dropna(subset=["type_intervention"]),
                         names="type_intervention", hole=0.4,
                         color_discrete_sequence=px.colors.sequential.Blues_r)
            fig.update_layout(height=270, margin=dict(t=5,b=5))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### Technique")
            tech = merged["technique"].dropna().value_counts().reset_index()
            tech.columns = ["Technique","N"]
            fig = px.bar(tech, x="Technique", y="N", color="Technique",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(height=270, margin=dict(t=5,b=5), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        c3,c4 = st.columns(2)
        with c3:
            st.markdown("#### Ischémie chaude (min)")
            isch = merged.dropna(subset=["ischemie_chaude_min"])
            if not isch.empty:
                fig = px.histogram(isch, x="ischemie_chaude_min", nbins=8,
                                   color_discrete_sequence=["#e74c3c"])
                fig.add_vline(x=25, line_dash="dash", annotation_text="25 min")
                fig.update_layout(height=260, margin=dict(t=5,b=5))
                st.plotly_chart(fig, use_container_width=True)
        with c4:
            st.markdown("#### Complications Clavien")
            if "complication_clavien" in merged.columns:
                clav = merged["complication_clavien"].fillna("0").value_counts().reset_index()
                clav.columns = ["Grade","N"]
                fig = px.bar(clav, x="Grade", y="N",
                             color_discrete_sequence=["#2c5f8a"])
                fig.update_layout(height=260, margin=dict(t=5,b=5))
                st.plotly_chart(fig, use_container_width=True)

    with tab3:
        c1,c2,c3 = st.columns(3)
        with c1:
            st.markdown("#### Histologie")
            fig = px.pie(merged.dropna(subset=["histologie"]), names="histologie",
                         color_discrete_sequence=px.colors.qualitative.Pastel, hole=0.35)
            fig.update_layout(height=270, margin=dict(t=5,b=5))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### Grade ISUP")
            grade = merged["grade_isup"].dropna().astype(int).value_counts().sort_index().reset_index()
            grade.columns = ["ISUP","N"]
            fig = px.bar(grade, x="ISUP", y="N",
                         color_discrete_sequence=["#28a745","#ffc107","#fd7e14","#dc3545"])
            fig.update_layout(height=270, margin=dict(t=5,b=5))
            st.plotly_chart(fig, use_container_width=True)
        with c3:
            st.markdown("#### Stade pT")
            fig = px.pie(merged.dropna(subset=["pt"]), names="pt",
                         color_discrete_sequence=["#2c5f8a","#4a90c4","#f39c12","#e74c3c"], hole=0.35)
            fig.update_layout(height=270, margin=dict(t=5,b=5))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Tableau anapath")
        cols_ap = [c for c in ["nom","prenom","histologie","grade_isup","pt","pn","pm","marges","marge_mm"] if c in merged.columns]
        ap = merged[cols_ap].dropna(subset=["histologie"])
        st.dataframe(ap, use_container_width=True, hide_index=True)
