# 🫘 Registre Cancer du Rein – CHU Rennes (v2 – Import PDF IA)

Application Streamlit alimentée par **IA** : chargez un PDF (CRC/CRO) et Claude extrait automatiquement toutes les données cliniques pour les insérer dans le registre.

**Aucune saisie manuelle.**

---

## Fonctionnement

```
PDF (CRC/CRO)
     │
     ▼
pypdf – extraction texte brut
     │
     ▼
Claude API (claude-sonnet-4-6) – parsing JSON structuré
     │
     ▼
Normalisation + validation
     │
     ▼
SQLite (registre.db) – 4 tables
     │
     ▼
Tableau de bord / Stats / Export
```

## Données extraites automatiquement

| Catégorie | Champs |
|-----------|--------|
| Patient | IPP, nom, prénom, DDN, sexe, adresse, médecin traitant |
| Tumeur | taille, côté, localisation, exophytique %, RENAL score, cT/N/M, créatinine, DFG, RCP |
| Intervention | date, type, technique, voie, chirurgien, durée, ischémie chaude, pertes sanguines, transfusion, conversion, incidents |
| Anapath | pT/N/M, grade ISUP, histologie, marges, marge min, durée hospit, Clavien-Dindo |

## Installation locale

```bash
git clone https://github.com/VOTRE_USER/registre-rein.git
cd registre-rein
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
streamlit run app.py
```

## Déploiement Streamlit Cloud

1. Push sur GitHub
2. [share.streamlit.io](https://share.streamlit.io) → New app → `app.py`
3. **Settings → Secrets** :
```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."
```
4. Deploy 🚀

## Structure

```
registre_rein/
├── app.py
├── requirements.txt
├── data/                    ← registre.db (auto-créé)
├── utils/
│   ├── database.py          ← SQLite CRUD
│   └── pdf_extractor.py     ← Pipeline extraction IA
└── pages/
    ├── import_pdf.py        ← ⭐ Page principale : upload → IA → registre
    ├── dashboard.py
    ├── patient_list.py
    ├── patient_detail.py
    ├── statistics.py
    └── export.py
```

## Note production

Sur Streamlit Cloud, SQLite est **éphémère** (reset à chaque redéploiement).  
Pour la persistance, migrer vers **Supabase/PostgreSQL** via `st.secrets` — modification mineure dans `database.py`.
