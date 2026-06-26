"""
Base de données SQLite – 4 tables : patients, tumeurs, interventions, suivis.
Créée automatiquement dans data/registre.db au premier lancement.
"""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "registre.db"


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS patients (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        ipp              TEXT,
        nom              TEXT,
        prenom           TEXT,
        date_naissance   TEXT,
        sexe             TEXT,
        adresse          TEXT,
        medecin_traitant TEXT,
        source_pdf       TEXT,
        created_at       TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS tumeurs (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id       INTEGER REFERENCES patients(id) ON DELETE CASCADE,
        date_imagerie    TEXT,
        type_imagerie    TEXT,
        cote             TEXT,
        taille_mm        REAL,
        localisation     TEXT,
        exophytique_pct  INTEGER,
        renal_score      INTEGER,
        ct               TEXT,
        cn               TEXT,
        cm               TEXT,
        creatinine       REAL,
        dfg              REAL,
        date_rcp         TEXT,
        decision_rcp     TEXT
    );
    CREATE TABLE IF NOT EXISTS interventions (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id           INTEGER REFERENCES patients(id) ON DELETE CASCADE,
        date_intervention    TEXT,
        type_intervention    TEXT,
        technique            TEXT,
        voie_abord           TEXT,
        chirurgien           TEXT,
        duree_min            INTEGER,
        ischemie_chaude_min  INTEGER,
        pertes_sanguines_ml  INTEGER,
        transfusion          INTEGER DEFAULT 0,
        conversion           INTEGER DEFAULT 0,
        incidents            TEXT,
        pt                   TEXT,
        pn                   TEXT,
        pm                   TEXT,
        grade_isup           INTEGER,
        histologie           TEXT,
        marges               TEXT,
        marge_mm             REAL,
        duree_hospit_j       INTEGER,
        complication_clavien TEXT,
        details_complication TEXT
    );
    CREATE TABLE IF NOT EXISTS suivis (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id   INTEGER REFERENCES patients(id) ON DELETE CASCADE,
        date_suivi   TEXT,
        type_suivi   TEXT,
        resultat     TEXT,
        statut       TEXT,
        notes        TEXT
    );
    """)
    conn.commit()
    conn.close()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def upsert_patient(data: dict) -> int:
    """Insère ou met à jour selon IPP. Retourne l'id."""
    conn = get_conn()
    c = conn.cursor()
    existing = None
    if data.get("ipp"):
        existing = c.execute("SELECT id FROM patients WHERE ipp=?", (data["ipp"],)).fetchone()
    if existing:
        pid = existing["id"]
        c.execute("""UPDATE patients SET nom=:nom, prenom=:prenom, date_naissance=:date_naissance,
                     sexe=:sexe, adresse=:adresse, medecin_traitant=:medecin_traitant,
                     source_pdf=:source_pdf WHERE id=:id""", {**data, "id": pid})
    else:
        c.execute("""INSERT INTO patients (ipp,nom,prenom,date_naissance,sexe,adresse,medecin_traitant,source_pdf)
                     VALUES (:ipp,:nom,:prenom,:date_naissance,:sexe,:adresse,:medecin_traitant,:source_pdf)""", data)
        pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid


def insert_tumeur(data: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    cols = ",".join(data.keys())
    ph = ",".join(f":{k}" for k in data.keys())
    c.execute(f"INSERT INTO tumeurs ({cols}) VALUES ({ph})", data)
    tid = c.lastrowid
    conn.commit(); conn.close()
    return tid


def insert_intervention(data: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    cols = ",".join(data.keys())
    ph = ",".join(f":{k}" for k in data.keys())
    c.execute(f"INSERT INTO interventions ({cols}) VALUES ({ph})", data)
    iid = c.lastrowid
    conn.commit(); conn.close()
    return iid


def get_all_patients() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql("""
        SELECT p.id, p.ipp, p.nom, p.prenom, p.date_naissance, p.sexe,
               t.cote, t.taille_mm, t.ct, t.renal_score,
               i.type_intervention, i.technique, i.histologie, i.pt, i.grade_isup, i.marges,
               p.source_pdf, p.created_at
        FROM patients p
        LEFT JOIN tumeurs t ON t.patient_id = p.id
        LEFT JOIN interventions i ON i.patient_id = p.id
        ORDER BY p.id DESC
    """, conn)
    conn.close()
    return df


def get_patient_full(pid: int) -> dict:
    conn = get_conn()
    p = dict(conn.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone() or {})
    t = pd.read_sql("SELECT * FROM tumeurs WHERE patient_id=?", conn, params=(pid,))
    i = pd.read_sql("SELECT * FROM interventions WHERE patient_id=?", conn, params=(pid,))
    s = pd.read_sql("SELECT * FROM suivis WHERE patient_id=? ORDER BY date_suivi DESC", conn, params=(pid,))
    conn.close()
    return {"patient": p, "tumeurs": t, "interventions": i, "suivis": s}


def delete_patient(pid: int):
    conn = get_conn()
    conn.execute("DELETE FROM patients WHERE id=?", (pid,))
    conn.commit(); conn.close()


def get_stats() -> dict:
    conn = get_conn()
    s = {}
    s["n_patients"]    = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    s["n_inter"]       = conn.execute("SELECT COUNT(*) FROM interventions").fetchone()[0]
    s["moy_taille"]    = conn.execute("SELECT ROUND(AVG(taille_mm),1) FROM tumeurs").fetchone()[0] or 0
    s["moy_ischemie"]  = conn.execute("SELECT ROUND(AVG(ischemie_chaude_min),1) FROM interventions WHERE ischemie_chaude_min > 0").fetchone()[0] or 0
    s["r0_pct"]        = conn.execute("SELECT ROUND(100.0*SUM(CASE WHEN marges='R0' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),1) FROM interventions WHERE marges IS NOT NULL").fetchone()[0] or 0
    s["type_inter"]    = pd.read_sql("SELECT type_intervention, COUNT(*) n FROM interventions GROUP BY type_intervention", conn)
    s["histologie"]    = pd.read_sql("SELECT histologie, COUNT(*) n FROM interventions WHERE histologie IS NOT NULL GROUP BY histologie", conn)
    s["stade"]         = pd.read_sql("SELECT pt, COUNT(*) n FROM interventions WHERE pt IS NOT NULL GROUP BY pt", conn)
    s["taille_dist"]   = pd.read_sql("SELECT taille_mm FROM tumeurs WHERE taille_mm IS NOT NULL", conn)
    conn.close()
    return s
