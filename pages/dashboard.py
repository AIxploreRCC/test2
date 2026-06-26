import streamlit as st
import plotly.express as px
from utils.database import get_stats, get_all_patients


def metric_card(label, value, suffix=""):
    st.markdown(f"""<div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}{suffix}</div>
    </div>""", unsafe_allow_html=True)


def show():
    st.title("🫘 Registre Cancer du Rein – CHU Rennes")
    st.caption("Service d'Urologie – Dr Z. Khene (PU-PH)")
    st.markdown("---")

    stats = get_stats()

    if stats["n_patients"] == 0:
        st.info("📥 Aucun patient dans le registre. Commencez par **importer un PDF** dans le menu.")
        if st.button("➡️ Aller vers Import PDF", type="primary"):
            st.rerun()
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: metric_card("Patients", stats["n_patients"])
    with c2: metric_card("Interventions", stats["n_inter"])
    with c3: metric_card("Taille moy.", stats["moy_taille"], " mm")
    with c4: metric_card("Ischémie moy.", stats["moy_ischemie"], " min")
    with c5: metric_card("Marges R0", stats["r0_pct"], " %")

    st.markdown("<br>", unsafe_allow_html=True)

    ca, cb, cc = st.columns(3)
    with ca:
        st.markdown("#### Type d'intervention")
        if not stats["type_inter"].empty:
            fig = px.pie(stats["type_inter"], names="type_intervention", values="n",
                         color_discrete_sequence=px.colors.sequential.Blues_r, hole=0.4)
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=240)
            st.plotly_chart(fig, use_container_width=True)

    with cb:
        st.markdown("#### Histologie")
        if not stats["histologie"].empty:
            fig = px.bar(stats["histologie"], x="histologie", y="n",
                         color="histologie", color_discrete_sequence=px.colors.qualitative.Set2,
                         labels={"n":"N","histologie":""})
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=240, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with cc:
        st.markdown("#### Stade pT")
        if not stats["stade"].empty:
            fig = px.bar(stats["stade"], x="pt", y="n",
                         color="pt", color_discrete_sequence=["#2c5f8a","#4a90c4","#f39c12","#e74c3c"],
                         labels={"n":"N","pt":""})
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=240, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Distribution taille tumorale")
    if not stats["taille_dist"].empty:
        fig = px.histogram(stats["taille_dist"], x="taille_mm", nbins=15,
                           color_discrete_sequence=["#2c5f8a"],
                           labels={"taille_mm":"Taille (mm)"})
        fig.add_vline(x=40, line_dash="dash", line_color="#e74c3c", annotation_text="T1a / T1b")
        fig.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=250)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Derniers dossiers importés")
    df = get_all_patients().head(10)
    cols = [c for c in ["ipp","nom","prenom","date_naissance","cote","taille_mm","ct",
                         "type_intervention","histologie","pt","marges","source_pdf"] if c in df.columns]
    st.dataframe(df[cols].rename(columns={
        "ipp":"IPP","nom":"Nom","prenom":"Prénom","date_naissance":"DDN",
        "cote":"Côté","taille_mm":"Taille (mm)","ct":"cT",
        "type_intervention":"Intervention","histologie":"Histologie",
        "pt":"pT","marges":"Marges","source_pdf":"Fichier source"
    }), use_container_width=True, hide_index=True)
