import streamlit as st

st.set_page_config(
    page_title="Registre Cancer du Rein – CHU Rennes",
    page_icon="🫘",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1a3a5c; }
[data-testid="stSidebar"] * { color: #e8f0f7 !important; }
.block-container { padding-top: 1.5rem; }
.metric-card {
    background:#f0f6ff; border-left:4px solid #2c5f8a;
    border-radius:6px; padding:12px 16px; margin-bottom:8px;
}
.metric-card .label { font-size:0.78rem; color:#555; font-weight:600; }
.metric-card .value { font-size:1.6rem; font-weight:700; color:#1a3a5c; }
.section-title {
    background:#2c5f8a; color:white; padding:6px 12px;
    border-radius:4px; font-weight:600; margin:12px 0 8px 0;
}
h1 { color:#1a3a5c; }
h2, h3 { color:#2c5f8a; }
</style>
""", unsafe_allow_html=True)

from utils.database import init_db
init_db()

with st.sidebar:
    st.markdown("### 🫘 Registre Cancer du Rein")
    st.markdown("**CHU Rennes – Service Urologie**")
    st.markdown("---")
    page = st.radio("Navigation", [
        "🏠 Tableau de bord",
        "📥 Importer un PDF",
        "📋 Liste patients",
        "🔍 Fiche patient",
        "📊 Statistiques",
        "📤 Export",
    ], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("<small>v2.0 – IA extraction PDF<br>Dr Z. Khene</small>", unsafe_allow_html=True)

if page == "🏠 Tableau de bord":
    from pages import dashboard; dashboard.show()
elif page == "📥 Importer un PDF":
    from pages import import_pdf; import_pdf.show()
elif page == "📋 Liste patients":
    from pages import patient_list; patient_list.show()
elif page == "🔍 Fiche patient":
    from pages import patient_detail; patient_detail.show()
elif page == "📊 Statistiques":
    from pages import statistics; statistics.show()
elif page == "📤 Export":
    from pages import export; export.show()
