"""
extract_crc_cro.py
==================
Extraction complète des données cliniques d'un PDF CRC/CRO
de cancer du rein via l'API Anthropic.

Usage :
    python extract_crc_cro.py mon_dossier.pdf
    python extract_crc_cro.py *.pdf           (batch)
    python extract_crc_cro.py mon_dossier.pdf --output resultats.json

Prérequis :
    pip install anthropic pypdf
    export ANTHROPIC_API_KEY="sk-ant-..."
"""

import sys
import os
import io
import json
import re
import argparse
from pathlib import Path

import pypdf
import anthropic

# ─────────────────────────────────────────────────────────────────────────────
# SCHÉMA JSON – toutes les données extraites
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = {
    "patient": {
        "ipp": "string | null",
        "nom": "string | null",
        "prenom": "string | null",
        "date_naissance": "YYYY-MM-DD | null",
        "age": "number | null",
        "sexe": "M | F | null",
        "adresse": "string | null",
        "medecin_traitant": "string | null",
        "poids_kg": "number | null",
        "taille_cm": "number | null",
        "imc": "number | null"
    },
    "antecedents": {
        "medicaux": "string | null",
        "chirurgicaux": "string | null",
        "familiaux": "string | null",
        "tabac": "string | null",
        "tabac_pa": "number | null",
        "autres_traitements": "string | null"
    },
    "consultation": {
        "date": "YYYY-MM-DD | null",
        "motif": "string | null",
        "symptomes": "string | null",
        "examen_clinique": "string | null",
        "pa_systolique": "number | null",
        "pa_diastolique": "number | null"
    },
    "tumeur": {
        "date_imagerie": "YYYY-MM-DD | null",
        "type_imagerie": "TDM | IRM | Échographie | TEP-TDM | null",
        "cote": "Droit | Gauche | Bilatéral | null",
        "taille_mm": "number | null",
        "localisation": "Pôle supérieur | Pôle inférieur | Pôle moyen | Hilaire | null",
        "exophytique_pct": "number | null",
        "endophytique": "true | false | null",
        "contact_sinus": "true | false | null",
        "thrombus_veineux": "true | false | null",
        "renal_score": "number | null",
        "ct": "T1a | T1b | T2a | T2b | T3a | T3b | T4 | null",
        "cn": "N0 | N1 | Nx | null",
        "cm": "M0 | M1 | Mx | null",
        "classification_uicc": "string | null"
    },
    "biologie": {
        "creatinine_umol_l": "number | null",
        "dfg_ml_min": "number | null",
        "formule_dfg": "CKD-EPI | MDRD | Cockcroft | null",
        "hemoglobine": "number | null",
        "psa": "number | null",
        "autres": "string | null"
    },
    "rcp": {
        "date": "YYYY-MM-DD | null",
        "decision": "string | null",
        "examens_complementaires": "string | null"
    },
    "intervention": {
        "date": "YYYY-MM-DD | null",
        "type": "Néphro partielle | Néphro totale | Ablatif | Surveillance | null",
        "technique": "Robot | Cœlioscopie | Chirurgie ouverte | Percutané | null",
        "systeme_robot": "string | null",
        "voie_abord": "string | null",
        "chirurgien": "string | null",
        "aide_operatoire": "string | null",
        "anesthesiste": "string | null",
        "duree_min": "number | null",
        "ischemie_chaude_min": "number | null",
        "ischemie_froide_min": "number | null",
        "pertes_sanguines_ml": "number | null",
        "transfusion": "true | false | null",
        "conversion": "true | false | null",
        "incidents_perop": "string | null",
        "details_operatoires": "string | null",
        "drainage": "true | false | null"
    },
    "anatomopathologie": {
        "histologie": "CCC | Chromophobe | Papillaire type 1 | Papillaire type 2 | Oncocytome | Autre | null",
        "taille_piece_mm": "number | null",
        "grade_isup": "1 | 2 | 3 | 4 | null",
        "pt": "pT1a | pT1b | pT2a | pT2b | pT3a | pT3b | pT4 | null",
        "pn": "N0 | N1 | Nx | null",
        "pm": "M0 | M1 | Mx | null",
        "marges": "R0 | R1 | R2 | null",
        "marge_min_mm": "number | null",
        "invasion_vasculaire": "true | false | null",
        "invasion_lymphatique": "true | false | null",
        "capsule_integre": "true | false | null",
        "surrénale": "string | null",
        "commentaire_anapath": "string | null"
    },
    "suites_operatoires": {
        "duree_hospit_j": "number | null",
        "date_sortie": "YYYY-MM-DD | null",
        "complication_clavien": "0 | I | II | IIIa | IIIb | IVa | IVb | V | null",
        "details_complication": "string | null",
        "j0": "string | null",
        "j1": "string | null",
        "j2": "string | null"
    },
    "meta": {
        "type_document": "CRC | CRO | CRC+CRO | null",
        "surveillance_active": "true | false",
        "etablissement": "string | null",
        "service": "string | null"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# PROMPT SYSTÈME
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""Tu es un assistant médical expert en urologie oncologique.
On te donne le texte complet d'un dossier médical (CRC = compte rendu de consultation
et/ou CRO = compte rendu opératoire) concernant un cancer du rein.

Extrais TOUTES les informations disponibles dans le texte et retourne UNIQUEMENT
un objet JSON valide, sans texte avant ni après, sans balises markdown.

Schéma JSON à respecter :
{json.dumps(SCHEMA, ensure_ascii=False, indent=2)}

Règles strictes :
1. Retourne UNIQUEMENT le JSON, rien d'autre.
2. Si une information est absente du texte : null (ne jamais inventer).
3. Dates : toujours au format YYYY-MM-DD.
4. Tailles : toujours en millimètres (convertis si cm).
5. Booléens : true/false (pas "oui"/"non").
6. transfusion/conversion : true si oui, false si non ou "aucune".
7. Pour ischemie_chaude_min : extrais le nombre de minutes uniquement.
8. Pour pertes_sanguines_ml : si "<50 mL" → 50, si "négligeable" → 0.
9. type_document : "CRC" si consultation seule, "CRO" si opératoire seul, "CRC+CRO" si les deux.
10. surveillance_active : true si aucune intervention n'est prévue/réalisée.
"""

# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION TEXTE PDF
# ─────────────────────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: str) -> str:
    """Extrait le texte de toutes les pages d'un PDF."""
    with open(pdf_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[PAGE {i+1}]\n{text.strip()}")
    return "\n\n".join(pages)


def extract_pdf_text_bytes(pdf_bytes: bytes) -> str:
    """Variante pour bytes (usage Streamlit)."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[PAGE {i+1}]\n{text.strip()}")
    return "\n\n".join(pages)


# ─────────────────────────────────────────────────────────────────────────────
# APPEL API CLAUDE
# ─────────────────────────────────────────────────────────────────────────────

def call_claude(text: str, model: str = "claude-sonnet-4-6") -> dict:
    """Envoie le texte à Claude et retourne le JSON parsé."""
    client = anthropic.Anthropic()

    # Troncature sécurisée si PDF très long (évite dépassement context window)
    MAX_CHARS = 15000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[... texte tronqué pour longueur ...]"

    response = client.messages.create(
        model=model,
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "Voici le texte extrait du dossier médical CRC/CRO.\n"
                "Extrais toutes les données selon le schéma JSON.\n\n"
                f"--- TEXTE ---\n{text}\n--- FIN ---"
            )
        }]
    )

    raw = response.content[0].text.strip()

    # Nettoyage au cas où Claude ajoute des balises markdown
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    raw = raw.strip()

    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# NETTOYAGE & VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def _v(val):
    """Retourne None si valeur vide/null."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("null", "none", "nan", "", "n/a", "-"):
        return None
    return val


def _date(val):
    """Normalise une date en YYYY-MM-DD."""
    v = _v(val)
    if not v:
        return None
    s = str(v).strip()
    patterns = [
        (r"(\d{4})-(\d{2})-(\d{2})", r"\1-\2-\3"),
        (r"(\d{2})/(\d{2})/(\d{4})", r"\3-\2-\1"),
        (r"(\d{2})-(\d{2})-(\d{4})", r"\3-\2-\1"),
        (r"(\d{2})\.(\d{2})\.(\d{4})", r"\3-\2-\1"),
    ]
    for pat, fmt in patterns:
        m = re.match(pat, s)
        if m:
            return re.sub(pat, fmt, s)
    return s


def _num(val):
    """Convertit en float, None si invalide."""
    v = _v(val)
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ".").replace("<", "").strip())
    except Exception:
        return None


def _int(val):
    n = _num(val)
    return int(n) if n is not None else None


def _bool(val):
    v = _v(val)
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).lower()
    if s in ("true", "oui", "yes", "1"):
        return True
    if s in ("false", "non", "no", "0", "aucune", "aucun"):
        return False
    return None


def clean(data: dict) -> dict:
    """Normalise le JSON retourné par Claude."""

    def section(d, schema_keys):
        if not d:
            return {k: None for k in schema_keys}
        return d

    p = data.get("patient") or {}
    a = data.get("antecedents") or {}
    c = data.get("consultation") or {}
    t = data.get("tumeur") or {}
    b = data.get("biologie") or {}
    r = data.get("rcp") or {}
    i = data.get("intervention") or {}
    ap = data.get("anatomopathologie") or {}
    s = data.get("suites_operatoires") or {}
    m = data.get("meta") or {}

    return {
        "patient": {
            "ipp":              _v(p.get("ipp")),
            "nom":              (_v(p.get("nom")) or "").upper() or None,
            "prenom":           _v(p.get("prenom")),
            "date_naissance":   _date(p.get("date_naissance")),
            "age":              _int(p.get("age")),
            "sexe":             _v(p.get("sexe")),
            "adresse":          _v(p.get("adresse")),
            "medecin_traitant": _v(p.get("medecin_traitant")),
            "poids_kg":         _num(p.get("poids_kg")),
            "taille_cm":        _num(p.get("taille_cm")),
            "imc":              _num(p.get("imc")),
        },
        "antecedents": {
            "medicaux":           _v(a.get("medicaux")),
            "chirurgicaux":       _v(a.get("chirurgicaux")),
            "familiaux":          _v(a.get("familiaux")),
            "tabac":              _v(a.get("tabac")),
            "tabac_pa":           _num(a.get("tabac_pa")),
            "autres_traitements": _v(a.get("autres_traitements")),
        },
        "consultation": {
            "date":           _date(c.get("date")),
            "motif":          _v(c.get("motif")),
            "symptomes":      _v(c.get("symptomes")),
            "examen_clinique":_v(c.get("examen_clinique")),
            "pa_systolique":  _int(c.get("pa_systolique")),
            "pa_diastolique": _int(c.get("pa_diastolique")),
        },
        "tumeur": {
            "date_imagerie":   _date(t.get("date_imagerie")),
            "type_imagerie":   _v(t.get("type_imagerie")),
            "cote":            _v(t.get("cote")),
            "taille_mm":       _num(t.get("taille_mm")),
            "localisation":    _v(t.get("localisation")),
            "exophytique_pct": _int(t.get("exophytique_pct")),
            "endophytique":    _bool(t.get("endophytique")),
            "contact_sinus":   _bool(t.get("contact_sinus")),
            "thrombus_veineux":_bool(t.get("thrombus_veineux")),
            "renal_score":     _int(t.get("renal_score")),
            "ct":              _v(t.get("ct")),
            "cn":              _v(t.get("cn")),
            "cm":              _v(t.get("cm")),
            "classification_uicc": _v(t.get("classification_uicc")),
        },
        "biologie": {
            "creatinine_umol_l": _num(b.get("creatinine_umol_l")),
            "dfg_ml_min":        _num(b.get("dfg_ml_min")),
            "formule_dfg":       _v(b.get("formule_dfg")),
            "hemoglobine":       _num(b.get("hemoglobine")),
            "psa":               _num(b.get("psa")),
            "autres":            _v(b.get("autres")),
        },
        "rcp": {
            "date":                   _date(r.get("date")),
            "decision":               _v(r.get("decision")),
            "examens_complementaires":_v(r.get("examens_complementaires")),
        },
        "intervention": {
            "date":               _date(i.get("date")),
            "type":               _v(i.get("type")),
            "technique":          _v(i.get("technique")),
            "systeme_robot":      _v(i.get("systeme_robot")),
            "voie_abord":         _v(i.get("voie_abord")),
            "chirurgien":         _v(i.get("chirurgien")),
            "aide_operatoire":    _v(i.get("aide_operatoire")),
            "anesthesiste":       _v(i.get("anesthesiste")),
            "duree_min":          _int(i.get("duree_min")),
            "ischemie_chaude_min":_int(i.get("ischemie_chaude_min")),
            "ischemie_froide_min":_int(i.get("ischemie_froide_min")),
            "pertes_sanguines_ml":_int(i.get("pertes_sanguines_ml")),
            "transfusion":        _bool(i.get("transfusion")),
            "conversion":         _bool(i.get("conversion")),
            "incidents_perop":    _v(i.get("incidents_perop")),
            "details_operatoires":_v(i.get("details_operatoires")),
            "drainage":           _bool(i.get("drainage")),
        },
        "anatomopathologie": {
            "histologie":          _v(ap.get("histologie")),
            "taille_piece_mm":     _num(ap.get("taille_piece_mm")),
            "grade_isup":          _int(ap.get("grade_isup")),
            "pt":                  _v(ap.get("pt")),
            "pn":                  _v(ap.get("pn")),
            "pm":                  _v(ap.get("pm")),
            "marges":              _v(ap.get("marges")),
            "marge_min_mm":        _num(ap.get("marge_min_mm")),
            "invasion_vasculaire": _bool(ap.get("invasion_vasculaire")),
            "invasion_lymphatique":_bool(ap.get("invasion_lymphatique")),
            "capsule_integre":     _bool(ap.get("capsule_integre")),
            "surrenale":           _v(ap.get("surrénale")),
            "commentaire_anapath": _v(ap.get("commentaire_anapath")),
        },
        "suites_operatoires": {
            "duree_hospit_j":      _int(s.get("duree_hospit_j")),
            "date_sortie":         _date(s.get("date_sortie")),
            "complication_clavien":_v(s.get("complication_clavien")),
            "details_complication":_v(s.get("details_complication")),
            "j0":                  _v(s.get("j0")),
            "j1":                  _v(s.get("j1")),
            "j2":                  _v(s.get("j2")),
        },
        "meta": {
            "type_document":     _v(m.get("type_document")),
            "surveillance_active": _bool(m.get("surveillance_active")) or False,
            "etablissement":     _v(m.get("etablissement")),
            "service":           _v(m.get("service")),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# RAPPORT LISIBLE
# ─────────────────────────────────────────────────────────────────────────────

def print_report(data: dict, filename: str):
    """Affiche un rapport structuré dans le terminal."""
    def f(val):
        if val is None:
            return "—"
        if isinstance(val, bool):
            return "Oui" if val else "Non"
        return str(val)

    p  = data["patient"]
    a  = data["antecedents"]
    c  = data["consultation"]
    t  = data["tumeur"]
    b  = data["biologie"]
    r  = data["rcp"]
    iv = data["intervention"]
    ap = data["anatomopathologie"]
    s  = data["suites_operatoires"]
    m  = data["meta"]

    sep = "─" * 60
    print(f"\n{'═'*60}")
    print(f"  EXTRACTION : {filename}")
    print(f"  Type document : {f(m['type_document'])}")
    print(f"{'═'*60}")

    print(f"\n{sep}")
    print("  PATIENT")
    print(sep)
    print(f"  Nom / Prénom     : {f(p['nom'])} {f(p['prenom'])}")
    print(f"  Date naissance   : {f(p['date_naissance'])}  |  Âge : {f(p['age'])} ans  |  Sexe : {f(p['sexe'])}")
    print(f"  IPP              : {f(p['ipp'])}")
    print(f"  Poids / Taille   : {f(p['poids_kg'])} kg / {f(p['taille_cm'])} cm  |  IMC : {f(p['imc'])}")
    print(f"  Médecin traitant : {f(p['medecin_traitant'])}")

    print(f"\n{sep}")
    print("  ANTÉCÉDENTS")
    print(sep)
    print(f"  Médicaux    : {f(a['medicaux'])}")
    print(f"  Chirurgicaux: {f(a['chirurgicaux'])}")
    print(f"  Familiaux   : {f(a['familiaux'])}")
    print(f"  Tabac       : {f(a['tabac'])}  |  PA : {f(a['tabac_pa'])}")

    print(f"\n{sep}")
    print("  CONSULTATION")
    print(sep)
    print(f"  Date   : {f(c['date'])}")
    print(f"  Motif  : {f(c['motif'])}")
    print(f"  PA     : {f(c['pa_systolique'])}/{f(c['pa_diastolique'])} mmHg")

    print(f"\n{sep}")
    print("  TUMEUR")
    print(sep)
    print(f"  Côté           : {f(t['cote'])}")
    print(f"  Taille         : {f(t['taille_mm'])} mm")
    print(f"  Localisation   : {f(t['localisation'])}")
    print(f"  Exophytique    : {f(t['exophytique_pct'])} %")
    print(f"  Thrombus vein. : {f(t['thrombus_veineux'])}")
    print(f"  RENAL score    : {f(t['renal_score'])}")
    print(f"  Imagerie       : {f(t['type_imagerie'])}  ({f(t['date_imagerie'])})")
    print(f"  Stade clinique : c{f(t['ct'])} {f(t['cn'])} {f(t['cm'])}  —  {f(t['classification_uicc'])}")

    print(f"\n{sep}")
    print("  BIOLOGIE")
    print(sep)
    print(f"  Créatinine : {f(b['creatinine_umol_l'])} µmol/L")
    print(f"  DFG        : {f(b['dfg_ml_min'])} mL/min  ({f(b['formule_dfg'])})")
    print(f"  PSA        : {f(b['psa'])} ng/mL")
    print(f"  Autres     : {f(b['autres'])}")

    print(f"\n{sep}")
    print("  RCP")
    print(sep)
    print(f"  Date     : {f(r['date'])}")
    print(f"  Décision : {f(r['decision'])}")

    if not m["surveillance_active"]:
        print(f"\n{sep}")
        print("  INTERVENTION")
        print(sep)
        print(f"  Date              : {f(iv['date'])}")
        print(f"  Type              : {f(iv['type'])}")
        print(f"  Technique         : {f(iv['technique'])}  —  {f(iv['systeme_robot'])}")
        print(f"  Voie d'abord      : {f(iv['voie_abord'])}")
        print(f"  Chirurgien        : {f(iv['chirurgien'])}")
        print(f"  Aide / Anesthésie : {f(iv['aide_operatoire'])} / {f(iv['anesthesiste'])}")
        print(f"  Durée             : {f(iv['duree_min'])} min")
        print(f"  Ischémie chaude   : {f(iv['ischemie_chaude_min'])} min")
        print(f"  Pertes sanguines  : {f(iv['pertes_sanguines_ml'])} mL")
        print(f"  Transfusion       : {f(iv['transfusion'])}")
        print(f"  Conversion        : {f(iv['conversion'])}")
        print(f"  Incidents         : {f(iv['incidents_perop'])}")

        print(f"\n{sep}")
        print("  ANATOMOPATHOLOGIE")
        print(sep)
        print(f"  Histologie        : {f(ap['histologie'])}")
        print(f"  Taille pièce      : {f(ap['taille_piece_mm'])} mm")
        print(f"  Grade ISUP        : {f(ap['grade_isup'])}")
        print(f"  Stade pTNM        : {f(ap['pt'])} {f(ap['pn'])} {f(ap['pm'])}")
        print(f"  Marges            : {f(ap['marges'])}  (marge min : {f(ap['marge_min_mm'])} mm)")
        print(f"  Invasion vasc.    : {f(ap['invasion_vasculaire'])}")
        print(f"  Invasion lymph.   : {f(ap['invasion_lymphatique'])}")

        print(f"\n{sep}")
        print("  SUITES OPÉRATOIRES")
        print(sep)
        print(f"  Durée hospit.     : {f(s['duree_hospit_j'])} jours")
        print(f"  Date sortie       : {f(s['date_sortie'])}")
        print(f"  Clavien-Dindo     : {f(s['complication_clavien'])}")
        if s.get("details_complication"):
            print(f"  Complication      : {f(s['details_complication'])}")
    else:
        print("\n  ➜ Surveillance active – pas d'intervention")

    print(f"\n{'═'*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# SCORE DE COMPLÉTUDE
# ─────────────────────────────────────────────────────────────────────────────

def completude(data: dict) -> dict:
    """Calcule le % de champs remplis par section."""
    scores = {}
    for section, content in data.items():
        if not isinstance(content, dict):
            continue
        vals = list(content.values())
        filled = sum(1 for v in vals if v is not None and v != "" and v is not False)
        total = len(vals)
        scores[section] = {
            "remplis": filled,
            "total": total,
            "pct": round(filled / total * 100) if total else 0
        }
    all_vals = [v for s in data.values() if isinstance(s, dict) for v in s.values()]
    filled_all = sum(1 for v in all_vals if v is not None and v != "" and v is not False)
    scores["TOTAL"] = {
        "remplis": filled_all,
        "total": len(all_vals),
        "pct": round(filled_all / len(all_vals) * 100) if all_vals else 0
    }
    return scores


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────

def process_file(pdf_path: str, verbose: bool = True) -> dict:
    """Traite un fichier PDF et retourne les données extraites nettoyées."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {pdf_path}")

    if verbose:
        print(f"\n📄 Lecture de : {path.name}")

    text = extract_pdf_text(str(path))

    if verbose:
        print(f"   {len(text)} caractères extraits ({len(text.splitlines())} lignes)")
        print("   Envoi à Claude API...")

    raw = call_claude(text)
    data = clean(raw)

    if verbose:
        print_report(data, path.name)
        scores = completude(data)
        print("  COMPLÉTUDE PAR SECTION")
        print("  " + "─" * 40)
        for sec, sc in scores.items():
            bar = "█" * (sc["pct"] // 5) + "░" * (20 - sc["pct"] // 5)
            print(f"  {sec:<22} {bar}  {sc['pct']:>3}%  ({sc['remplis']}/{sc['total']})")
        print()

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Extraction automatique de données CRC/CRO cancer du rein via Claude API"
    )
    parser.add_argument("pdfs", nargs="+", help="Fichier(s) PDF à traiter")
    parser.add_argument("--output", "-o", help="Fichier JSON de sortie (optionnel)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Pas d'affichage détaillé")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Variable ANTHROPIC_API_KEY non définie.")
        print("   export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    results = []
    errors  = []

    for pdf in args.pdfs:
        try:
            data = process_file(pdf, verbose=not args.quiet)
            results.append({"fichier": Path(pdf).name, "statut": "ok", "donnees": data})
        except Exception as e:
            print(f"❌ Erreur sur {pdf} : {e}")
            errors.append({"fichier": Path(pdf).name, "statut": "erreur", "message": str(e)})

    # Résumé
    print(f"✅ {len(results)} fichier(s) traité(s)  |  ❌ {len(errors)} erreur(s)")

    # Sauvegarde JSON
    output_data = results if len(results) > 1 else (results[0] if results else {})
    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"💾 Résultats sauvegardés dans : {args.output}")
    else:
        # Affichage JSON compact si pas de fichier de sortie
        print("\n--- JSON FINAL ---")
        print(json.dumps(output_data, ensure_ascii=False, indent=2))

    return output_data


if __name__ == "__main__":
    main()
