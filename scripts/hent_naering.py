#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hent_naering.py – Henter næringsinformasjon fra Matvaretabellen.no
og lagrer resultatet i naering-tabellen i kokt.db.

Kjøres én gang før du bygger appen (fra repo-roten):
    python scripts/hent_naering.py

Ingen API-nøkkel nødvendig.
Filen caches lokalt (scripts/foods_cache.json) – slettes automatisk aldri.
"""

import os, sys, json, sqlite3, difflib, urllib.request, urllib.error

# Windows-konsollen bruker cp1252 ved omdirigering, som ikke takler ✓/✗/–.
# Tving UTF-8 på stdout/stderr så utskrift aldri krasjer kjøringen.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

API_URL = "https://www.matvaretabellen.no/api/nb/foods.json"

def _finn_db() -> str:
    """Leter etter kokt.db. Den kanoniske databasen som faktisk pakkes med
    appen ligger i ../kokebok-app/src-tauri/data/kokt.db (relativt til denne
    scripts/-mappa på repo-roten), så den prøves først. Faller tilbake til
    eldre plasseringer / cwd for robusthet."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kandidater = [
        os.path.join(script_dir, '..', 'kokebok-app', 'src-tauri', 'data', 'kokt.db'),  # kanonisk, bundles med appen
        os.path.join(script_dir, '..', 'kokebok-app', 'src-tauri', 'kokt.db'),  # før data/-flytting
        os.path.join(script_dir, '..', 'src-tauri', 'kokt.db'),  # gammel scripts-i-app-layout
        os.path.join(script_dir, 'kokt.db'),
        os.path.join(os.getcwd(), 'kokt.db'),
    ]
    for sti in kandidater:
        sti = os.path.normpath(sti)
        if os.path.exists(sti):
            return sti
    locs = '\n  '.join(os.path.normpath(k) for k in kandidater)
    sys.exit(f"Fant ikke kokt.db. Lette her:\n  {locs}")

DB_STI = _finn_db()
CACHE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'foods_cache.json')

SCHEMA = """
CREATE TABLE IF NOT EXISTS naering (
    id               INTEGER PRIMARY KEY,
    ingredient_navn  TEXT UNIQUE NOT NULL,
    mat_navn         TEXT,
    energi_kcal      REAL,
    protein_g        REAL,
    fett_g           REAL,
    karbohydrat_g    REAL,
    fiber_g          REAL
);
"""

# Nutrient IDs i Matvaretabellen.no
NUTR = {
    'protein_g':      'Protein',
    'fett_g':         'Fett',
    'karbohydrat_g':  'Karbo',
    'fiber_g':        'Fiber',
}

# ── Last ned / les fra cache ──────────────────────────────────────────────────
def hent_matvarer() -> list:
    if os.path.exists(CACHE):
        print(f"Bruker cache: {CACHE}")
        with open(CACHE, encoding='utf-8') as f:
            return json.load(f)['foods']

    print("Laster ned foods.json fra matvaretabellen.no …")
    req = urllib.request.Request(
        API_URL,
        headers={
            'User-Agent': 'KokebokApp/1.0 (privat, ikke-kommersiell bruk)',
            'Accept':     'application/json',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} – klarte ikke laste matvaretabellen: {e}")
    except Exception as e:
        sys.exit(f"Nettverksfeil: {e}")

    data = json.loads(raw)
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    foods = data['foods']
    print(f"Lastet ned {len(foods)} matvarer og cachet til {CACHE}\n")
    return foods


# ── Bygg søkeindeks ───────────────────────────────────────────────────────────
def bygg_indeks(matvarer: list) -> dict:
    """
    Returnerer: {normalisert_navn: food_dict, ...}
    Indekserer både fullt navn og første del (før komma).
    """
    idx = {}
    for mat in matvarer:
        raw = mat.get('foodName', '')
        if not raw:
            continue
        full  = raw.lower().strip()
        kort  = full.split(',')[0].strip()
        # Fjern vanlige suffikser for bedre treff
        for suffix in [', rå', ', kokt', ', stekt', ', fersk', ', tørr',
                       ', frossen', ', hermetisk', ', pasteurisert', ' rå']:
            full_clean = full.replace(suffix, '')
        idx.setdefault(full, mat)
        idx.setdefault(kort, mat)
        idx.setdefault(full_clean, mat)
    return idx


# ── Navnematching ─────────────────────────────────────────────────────────────
def finn_treff(ingredient: str, idx: dict, matvarer: list):
    norm = ingredient.lower().strip()

    # 1. Eksakt
    if norm in idx:
        return idx[norm]

    # 2. Ingrediens er prefiks i matvarenavn (f.eks. "gulrot" → "Gulrot, rå")
    for key, mat in idx.items():
        if key.startswith(norm) or norm.startswith(key):
            return mat

    # 3. Ingrediens er inneholdt i matvarenavn
    for mat in matvarer:
        navn = mat.get('foodName', '').lower()
        if norm in navn:
            return mat

    # 4. Fuzzy (difflib) – krever minst 65% likhet
    alle_navn = [m.get('foodName', '').lower() for m in matvarer]
    hits = difflib.get_close_matches(norm, alle_navn, n=1, cutoff=0.65)
    if hits:
        for mat in matvarer:
            if mat.get('foodName', '').lower() == hits[0]:
                return mat

    return None


# ── Trekk ut næringsverdier ───────────────────────────────────────────────────
def ekstraher(mat: dict) -> dict:
    c_map = {}
    for c in mat.get('constituents', []):
        nid = c.get('nutrientId')
        qty = c.get('quantity')
        if nid and qty is not None:
            c_map[nid] = qty

    return {
        'energi_kcal':    mat.get('calories', {}).get('quantity'),
        'protein_g':      c_map.get('Protein'),
        'fett_g':         c_map.get('Fett'),
        'karbohydrat_g':  c_map.get('Karbo'),
        'fiber_g':        c_map.get('Fiber'),
    }


# ── Hoved ─────────────────────────────────────────────────────────────────────
def main():
    print("=== Næringsinformasjon fra Matvaretabellen.no ===\n")

    db_sti = os.path.abspath(DB_STI)
    if not os.path.exists(db_sti):
        sys.exit(f"Finner ikke databasen: {db_sti}\n"
                 f"Kjør scriptet fra kokebok/-mappa.")

    db = sqlite3.connect(db_sti)
    db.executescript(SCHEMA)
    db.commit()

    matvarer = hent_matvarer()
    idx      = bygg_indeks(matvarer)
    print(f"{len(matvarer)} matvarer i tabellen, {len(idx)} indeksnøkler\n")

    # Alle distinkte ingredienser etter frekvens (ingen øvre grense lenger –
    # vi vil dekke så mye av databasen som mulig). Sett miljøvariabelen
    # NAERING_LIMIT for å begrense under testing, f.eks. NAERING_LIMIT=50.
    limit = os.environ.get('NAERING_LIMIT')
    limit_sql = f"LIMIT {int(limit)}" if limit and limit.isdigit() else ""
    rader = db.execute(f"""
        SELECT LOWER(TRIM(navn)) AS n, COUNT(*) AS c
        FROM   ingredienser
        GROUP  BY n
        ORDER  BY c DESC
        {limit_sql}
    """).fetchall()

    allerede = {r[0] for r in
                db.execute("SELECT ingredient_navn FROM naering").fetchall()}
    todo = [(n, c) for n, c in rader if n not in allerede]

    print(f"Ingredienser i DB:    {len(rader)}")
    print(f"Allerede matchet:     {len(allerede)}")
    print(f"Skal behandles nå:    {len(todo)}\n")

    ok = ingen = 0

    for i, (navn, _) in enumerate(todo, 1):
        mat = finn_treff(navn, idx, matvarer)

        if mat:
            n = ekstraher(mat)
            try:
                db.execute("""
                    INSERT OR REPLACE INTO naering
                        (ingredient_navn, mat_navn,
                         energi_kcal, protein_g, fett_g, karbohydrat_g, fiber_g)
                    VALUES (?,?,?,?,?,?,?)
                """, (navn, mat['foodName'],
                      n['energi_kcal'], n['protein_g'], n['fett_g'],
                      n['karbohydrat_g'], n['fiber_g']))
                ok += 1
                kal = f"{int(n['energi_kcal'])} kcal" if n['energi_kcal'] else "? kcal"
                print(f"[{i:3}/{len(todo)}] ✓  {navn:35s} → {mat['foodName'][:38]} ({kal})")
            except sqlite3.Error as e:
                print(f"[{i:3}/{len(todo)}] ✗  DB-feil: {e}")
        else:
            ingen += 1
            try:
                db.execute(
                    "INSERT OR IGNORE INTO naering (ingredient_navn) VALUES (?)", (navn,))
            except sqlite3.Error:
                pass
            print(f"[{i:3}/{len(todo)}] –  {navn:35s} → ingen treff")

        if i % 50 == 0:
            db.commit()

    db.commit()
    db.close()

    print(f"\n{'='*60}")
    print(f"Ferdig!  ✓ {ok} matchet  –  {ingen} ingen treff")
    print(f"Næringstabellen er klar. Kopier kokt.db til app-roten og bygg.")

if __name__ == '__main__':
    main()
