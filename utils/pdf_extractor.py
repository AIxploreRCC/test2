"""
Extraction automatique des données cliniques depuis un PDF (CRC/CRO)
via l'API Anthropic (claude-sonnet-4-6).

Pipeline :
  1. pypdf  → texte brut du PDF
  2. Claude → JSON structuré
  3. Validation + nettoyage
  4. Insertion SQLite
"""
import json
import re
import base64
import io
import anthropic
import pypdf
import streamlit as st
from utils.database import upsert_patient, insert_tumeur, insert_intervention

# ── Prompt système ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un assistant médical expert en urologie oncologique.
On te donne le texte d'un dossier médical (CRC = compte rendu de consultation
et/ou CRO = compte rendu opératoire) pour un cancer du rein.

Extrais TOUTES les informations disponibles et retourne UNIQUEMENT un objet JSON
valide, sans texte avant ni après, sans balises markdown, en respectant
exactement ce schéma :

{
  "patient": {
    "ipp": "string ou null",
    "nom": "string ou null",
    "prenom": "string ou null",
    "date_naissance": "YYYY-MM-DD ou null",
    "sexe": "M ou F ou null",
    "adresse": "string ou null",
    "medecin_traitant": "string ou null"
  },
  "tumeur": {
    "date_imagerie": "YYYY-MM-DD ou null",
    "type_imagerie": "TDM | IRM | Échographie | TEP-TDM ou null",
    "cote": "Droit | Gauche | Bilatéral ou null",
    "taille_mm": number ou null,
    "localisation": "string ou null",
    "exophytique_pct": number ou null,
    "renal_score": number ou null,
    "ct": "T1a | T1b | T2a | T2b | T3a | T3b | T4 ou null",
    "cn": "N0 | N1 | Nx ou null",
    "cm": "M0 | M1 | Mx ou null",
    "creatinine": number ou null,
    "dfg": number ou null,
    "date_rcp": "YYYY-MM-DD ou null",
    "decision_rcp": "string ou null"
  },
  "intervention": {
    "date_intervention": "YYYY-MM-DD ou null",
    "type_intervention": "Néphro partielle | Néphro totale | Ablatif | Surveillance ou null",
    "technique": "Robot | Cœlioscopie | Chirurgie ouverte | Percutané (ablation) ou null",
    "voie_abord": "string ou null",
    "chirurgien": "string ou null",
    "duree_min": number ou null,
    "ischemie_chaude_min": number ou null,
    "pertes_sanguines_ml": number ou null,
    "transfusion": 0 ou 1,
    "conversion": 0 ou 1,
    "incidents": "string ou null",
    "pt": "pT1a | pT1b | pT2a | pT2b | pT3a | pT3b | pT4 ou null",
    "pn": "N0 | N1 | Nx ou null",
    "pm": "M0 | M1 | Mx ou null",
    "grade_isup": 1 ou 2 ou 3 ou 4 ou null,
    "histologie": "CCC | Chromophobe | Papillaire type 1 | Papillaire type 2 | Autre ou null",
    "marges": "R0 | R1 | R2 ou null",
    "marge_mm": number ou null,
    "duree_hospit_j": number ou null,
    "complication_clavien": "0 | I | II | IIIa | IIIb | IVa | IVb | V ou null",
    "details_complication": "string ou null"
  },
  "surveillance_active": false
}

Règles :
- Si une intervention chirurgicale n'a pas été réalisée (surveillance active), 
  met surveillance_active à true et laisse intervention à null.
- Convertis toutes les dates en format YYYY-MM-DD.
- Pour taille_mm : extrait le nombre en millimètres (si cm, convertis).
- Pour transfusion et conversion : 0 = non, 1 = oui.
- Si une information n'est pas mentionnée : null.
- NE JAMAIS inventer des données non présentes dans le texte.
"""

# ── Extraction texte PDF ───────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extrait le texte brut d'un PDF en mémoire."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
        text += "\n\n"
    return text.strip()


# ── Appel Claude API ──────────────────────────────────────────────────────────

def call_claude_extraction(pdf_text: str, pdf_bytes: bytes = None) -> dict:
    """
    Envoie le texte PDF à Claude et retourne le JSON parsé.
    Essaie d'abord le texte, puis fallback vision si texte vide.
    """
    client = anthropic.Anthropic()

    if len(pdf_text.strip()) > 100:
        # Cas standard : PDF textuel
        user_content = f"""Voici le texte extrait d'un dossier médical CRC/CRO de cancer du rein.
Extrais toutes les informations selon le schéma JSON demandé.

--- TEXTE DU DOSSIER ---
{pdf_text[:12000]}
--- FIN DU TEXTE ---
"""
        messages = [{"role": "user", "content": user_content}]
    else:
        # Fallback : envoyer le PDF en base64 (vision)
        if pdf_bytes is None:
            raise ValueError("PDF vide ou non lisible")
        b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": b64}
                },
                {
                    "type": "text",
                    "text": "Extrais toutes les informations médicales selon le schéma JSON demandé."
                }
            ]
        }]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    raw = response.content[0].text.strip()
    # Nettoyer si markdown
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ── Nettoyage et normalisation ────────────────────────────────────────────────

def _clean_str(v):
    if v is None or str(v).lower() in ("null","none","nan",""):
        return None
    return str(v).strip()

def _clean_num(v):
    if v is None or str(v).lower() in ("null","none","nan",""):
        return None
    try:
        return float(v)
    except Exception:
        return None

def _clean_int(v):
    n = _clean_num(v)
    return int(n) if n is not None else None

def _clean_date(v):
    if not v:
        return None
    v = str(v).strip()
    # Accepte YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
    patterns = [
        (r"(\d{4})-(\d{2})-(\d{2})", lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        (r"(\d{2})/(\d{2})/(\d{4})", lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),
        (r"(\d{2})-(\d{2})-(\d{4})", lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),
    ]
    for pat, fmt in patterns:
        m = re.match(pat, v)
        if m:
            return fmt(m)
    return v if v.lower() != "null" else None


def normalize_extracted(data: dict) -> dict:
    """Normalise et nettoie le JSON retourné par Claude."""
    p = data.get("patient") or {}
    t = data.get("tumeur") or {}
    i = data.get("intervention") or {}

    patient = {
        "ipp":              _clean_str(p.get("ipp")),
        "nom":              (_clean_str(p.get("nom")) or "").upper() or None,
        "prenom":           _clean_str(p.get("prenom")),
        "date_naissance":   _clean_date(p.get("date_naissance")),
        "sexe":             _clean_str(p.get("sexe")),
        "adresse":          _clean_str(p.get("adresse")),
        "medecin_traitant": _clean_str(p.get("medecin_traitant")),
        "source_pdf":       None,  # rempli par l'appelant
    }

    tumeur = {
        "date_imagerie":  _clean_date(t.get("date_imagerie")),
        "type_imagerie":  _clean_str(t.get("type_imagerie")),
        "cote":           _clean_str(t.get("cote")),
        "taille_mm":      _clean_num(t.get("taille_mm")),
        "localisation":   _clean_str(t.get("localisation")),
        "exophytique_pct":_clean_int(t.get("exophytique_pct")),
        "renal_score":    _clean_int(t.get("renal_score")),
        "ct":             _clean_str(t.get("ct")),
        "cn":             _clean_str(t.get("cn")),
        "cm":             _clean_str(t.get("cm")),
        "creatinine":     _clean_num(t.get("creatinine")),
        "dfg":            _clean_num(t.get("dfg")),
        "date_rcp":       _clean_date(t.get("date_rcp")),
        "decision_rcp":   _clean_str(t.get("decision_rcp")),
    }

    surveillance = bool(data.get("surveillance_active", False))
    intervention = None
    if not surveillance and i:
        intervention = {
            "date_intervention":    _clean_date(i.get("date_intervention")),
            "type_intervention":    _clean_str(i.get("type_intervention")),
            "technique":            _clean_str(i.get("technique")),
            "voie_abord":           _clean_str(i.get("voie_abord")),
            "chirurgien":           _clean_str(i.get("chirurgien")),
            "duree_min":            _clean_int(i.get("duree_min")),
            "ischemie_chaude_min":  _clean_int(i.get("ischemie_chaude_min")),
            "pertes_sanguines_ml":  _clean_int(i.get("pertes_sanguines_ml")),
            "transfusion":          int(i.get("transfusion") or 0),
            "conversion":           int(i.get("conversion") or 0),
            "incidents":            _clean_str(i.get("incidents")),
            "pt":                   _clean_str(i.get("pt")),
            "pn":                   _clean_str(i.get("pn")),
            "pm":                   _clean_str(i.get("pm")),
            "grade_isup":           _clean_int(i.get("grade_isup")),
            "histologie":           _clean_str(i.get("histologie")),
            "marges":               _clean_str(i.get("marges")),
            "marge_mm":             _clean_num(i.get("marge_mm")),
            "duree_hospit_j":       _clean_int(i.get("duree_hospit_j")),
            "complication_clavien": _clean_str(i.get("complication_clavien")),
            "details_complication": _clean_str(i.get("details_complication")),
        }

    return {"patient": patient, "tumeur": tumeur, "intervention": intervention,
            "surveillance": surveillance}


# ── Fonction principale ───────────────────────────────────────────────────────

def process_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """
    Traitement complet d'un PDF :
      1. Extraction texte
      2. Appel Claude
      3. Normalisation
      4. Insertion DB
    Retourne un dict avec les données extraites et l'id patient.
    """
    # 1. Texte
    text = extract_text_from_pdf(pdf_bytes)

    # 2. Claude
    raw = call_claude_extraction(text, pdf_bytes)

    # 3. Normalisation
    data = normalize_extracted(raw)
    data["patient"]["source_pdf"] = filename

    # 4. DB
    pid = upsert_patient(data["patient"])
    data["tumeur"]["patient_id"] = pid
    insert_tumeur(data["tumeur"])

    if data["intervention"]:
        data["intervention"]["patient_id"] = pid
        insert_intervention(data["intervention"])

    return {**data, "patient_id": pid, "raw_json": raw}
