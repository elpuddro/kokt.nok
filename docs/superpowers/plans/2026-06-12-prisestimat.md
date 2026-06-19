# Prisestimat for oppskrifter — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estimere omtrentlig kostnad per oppskrift ved å matche ingredienser mot Kiwi/Coop Extra-priser fra kassal.app, cachet i `kokt.db`, vist som total + per porsjon med ærlig dekningsindikator.

**Architecture:** Offline Python-skript bygger en `priser`-tabell i `kokt.db` (streng token-match mot produktnavn, vekt parses fra navnet, enhetspris forhåndsberegnes). `lib.rs` summerer kostnad i `hent_oppskrift` (samme stil som nærings-SQL). `+page.svelte` viser tallet (samme mønster som nærings-boksen).

**Tech Stack:** Python 3.13 (stdlib `urllib` + ny `pytest` for parse-logikk), Rust/rusqlite (Tauri-backend), Svelte 5 (`$derived`).

**Spec:** `docs/superpowers/specs/2026-06-12-prisestimat-design.md`

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `scripts/kassal.py` | Ren, testbar logikk: `hodeord()`, `parse_produktnavn()`, `er_treff()`, `velg_beste()`. Ingen nettverk/DB. | Opprett |
| `scripts/hent_priser.py` | Orkestrering: les ingredienser fra DB, kall API (rate-limit, 429-backoff), bruk `kassal.py`, skriv `priser`-tabell. | Opprett |
| `scripts/test_kassal.py` | pytest for `kassal.py` (parse + match-gate, der prototypen viste skjørhet). | Opprett |
| `scripts/requirements-dev.txt` | `pytest` (eneste dev-avhengighet). | Opprett |
| `kokebok-app/src-tauri/src/lib.rs` | Ny `priser`-beregning i `hent_oppskrift`; konstanter for enhet-konvertering. | Modify (~linje 168–272) |
| `kokebok-app/src/routes/+page.svelte` | `prisVist`-`$derived` + pris-boks i detaljvisning. | Modify (script ~159–170, markup ~355) |
| `README.md` | Dokumentér `hent_priser.py` under «Data». | Modify |

**Designvalg:** Ren logikk (`kassal.py`) skilles fra I/O (`hent_priser.py`) slik at parse/match — den skjøre delen — kan enhetstestes uten nett eller DB. Dette speiler hvordan prototypen bekreftet mekanikken isolert.

---

## Task 1: Ren logikk-modul `kassal.py` med parse + match-gate (TDD)

Dette er kjernen prototypen beviste. Testes grundig fordi den er skjør (jf. salt→potetgull, egg→truseinnlegg).

**Files:**
- Create: `scripts/kassal.py`
- Create: `scripts/test_kassal.py`
- Create: `scripts/requirements-dev.txt`

- [ ] **Step 1: Opprett dev-avhengighet**

Create `scripts/requirements-dev.txt`:

```
pytest>=8.0
```

Run: `python -m pip install -r scripts/requirements-dev.txt`
Expected: pytest installeres uten feil.

- [ ] **Step 2: Skriv de feilende testene**

Create `scripts/test_kassal.py`:

```python
# -*- coding: utf-8 -*-
import kassal


# ── hodeord: strip tilberednings-prefiks, første gjenværende ord ──
def test_hodeord_enkelt():
    assert kassal.hodeord("hvetemel") == "hvetemel"

def test_hodeord_stripper_prefiks():
    assert kassal.hodeord("smeltet smør") == "smør"
    assert kassal.hodeord("finhakket løk") == "løk"

def test_hodeord_komma_og_beskrivelse():
    assert kassal.hodeord("banan , til steking (pynt)") == "banan"

def test_hodeord_for_kort_gir_none():
    assert kassal.hodeord("is") is None  # < 3 tegn


# ── parse_produktnavn: (enhetsklasse, mengde_i_basis) fra produktnavn ──
def test_parse_kg():
    assert kassal.parse_produktnavn("Hvetemel Siktet 1kg Møllerens") == ("g", 1000.0)

def test_parse_gram():
    assert kassal.parse_produktnavn("Gulrot 400g Gartner") == ("g", 400.0)

def test_parse_liter_komma():
    assert kassal.parse_produktnavn("Lettmelk 0,5% 1,75l Q") == ("ml", 1750.0)

def test_parse_stk():
    assert kassal.parse_produktnavn("Egg Frittgående 18stk First Price") == ("stk", 18.0)

def test_parse_ingen_vekt_gir_none():
    assert kassal.parse_produktnavn("Eldorado Krydderblanding") is None

def test_parse_tar_siste_forekomst():
    # "0,5%" skal ikke forstyrre; vekten 1,75l vinner
    assert kassal.parse_produktnavn("Lettmelk 0,5% 1,75l Q")[1] == 1750.0


# ── er_treff: hodeord MÅ være første token i produktnavn ──
def test_treff_forste_token():
    assert kassal.er_treff("bakepulver", "Bakepulver 250g Freia") is True
    assert kassal.er_treff("egg", "Egg Frittgående 18stk") is True

def test_treff_avviser_descriptor():
    # presisjon: salt som smaks-descriptor, ikke produktet
    assert kassal.er_treff("salt", "Potetgull Classic Salt 250g Maarud") is False
    assert kassal.er_treff("smør", "Olivero Smør & Olivenolje 400g") is False

def test_treff_avviser_substring():
    assert kassal.er_treff("salt", "Smør Usaltet 250g Tine") is False  # 'salt' ikke token


# ── velg_beste: billigste enhetspris innen samme enhetsklasse ──
def _kand(navn, pris, store=None):
    d = {"name": navn, "current_price": pris}
    if store is not None:
        d["_store"] = store
    return d

def test_velg_beste_billigste_innen_klasse():
    kandidater = [_kand("Egg 12stk Prior", 31.9), _kand("Egg 18stk First Price", 39.9)]
    best = kassal.velg_beste("egg", kandidater, mal_klasse="stk")
    # 39.9/18 = 2.217 < 31.9/12 = 2.658  → 18-pakka er billigst per stk
    assert best["enhetsklasse"] == "stk"
    assert round(best["enhetspris"], 3) == 2.217
    assert best["produkt_navn"] == "Egg 18stk First Price"

def test_velg_beste_baerer_butikk():
    kandidater = [_kand("Egg 18stk First Price", 39.9, store="KIWI")]
    best = kassal.velg_beste("egg", kandidater, mal_klasse="stk")
    assert best["butikk"] == "KIWI"

def test_velg_beste_filtrerer_feil_klasse():
    # ingrediens er stk, men bare g-produkter finnes → ingen match
    kandidater = [_kand("Eggpasta 500g Barilla", 25.0)]
    assert kassal.velg_beste("egg", kandidater, mal_klasse="stk") is None

def test_velg_beste_avviser_descriptor_match():
    kandidater = [_kand("Potetgull Salt 250g", 24.9)]
    assert kassal.velg_beste("salt", kandidater, mal_klasse="g") is None

def test_velg_beste_tom_gir_none():
    assert kassal.velg_beste("xyz", [], mal_klasse="g") is None
```

- [ ] **Step 3: Kjør testene og bekreft at de feiler**

Run: `cd scripts && python -m pytest test_kassal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kassal'` (eller AttributeError).

- [ ] **Step 4: Implementer `kassal.py`**

Create `scripts/kassal.py`:

```python
# -*- coding: utf-8 -*-
"""Ren, testbar logikk for prismatching mot kassal.app.
Ingen nettverk eller DB her — kun parsing og match-gate, slik at logikken
kan enhetstestes isolert. Brukes av hent_priser.py."""

import re

# Tilberednings-prefiks som strippes før hodeord velges.
STRIP = {
    "smeltet", "finhakket", "hakket", "revet", "grovhakket", "oppmalt",
    "knust", "kvernet", "kokt", "stekt", "frisk", "fersk",
}

_WEIGHT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|hg|g|l|dl|cl|ml|stk)\b", re.I)
_TOKEN_RE = re.compile(r"[a-zæøå]+")

# Normalisering av parset enhet → (enhetsklasse, multiplikator til basis)
_TO_BASIS = {
    "kg": ("g", 1000.0), "hg": ("g", 100.0), "g": ("g", 1.0),
    "l": ("ml", 1000.0), "dl": ("ml", 100.0), "cl": ("ml", 10.0), "ml": ("ml", 1.0),
    "stk": ("stk", 1.0),
}


def hodeord(ingrediens_navn):
    """Første meningsbærende ord i ingrediensnavnet, etter prefiks-strip.
    Returnerer None hvis < 3 tegn (kassal.app krever min. 3 tegn i søk)."""
    ord = [w for w in re.split(r"[\s,]+", ingrediens_navn.lower()) if w and w not in STRIP]
    if not ord:
        return None
    h = ord[0]
    return h if len(h) >= 3 else None


def parse_produktnavn(produkt_navn):
    """Trekk ut (enhetsklasse, mengde_i_basis) fra et produktnavn.
    'Hvetemel 1kg' → ('g', 1000.0); 'Egg 18stk' → ('stk', 18.0).
    Tar SISTE vekt-forekomst (vekten står typisk sist). None hvis ingen."""
    treff = list(_WEIGHT_RE.finditer(produkt_navn))
    if not treff:
        return None
    m = treff[-1]
    val = float(m.group(1).replace(",", "."))
    klasse, mult = _TO_BASIS[m.group(2).lower()]
    return (klasse, val * mult)


def er_treff(hode, produkt_navn):
    """Presisjons-gate: hodeordet MÅ være FØRSTE token i produktnavnet.
    Avviser 'salt' i 'Potetgull Salt' og 'smør' i 'Olivero Smør & Olivenolje'."""
    toks = _TOKEN_RE.findall(produkt_navn.lower())
    return bool(toks) and toks[0] == hode


def velg_beste(hode, kandidater, mal_klasse):
    """Velg produktet med lavest enhetspris innen mal_klasse ('g'|'ml'|'stk').
    kandidater: liste av dict med minst 'name' og 'current_price'. Hvis et
    kandidat-dict har '_store', bæres butikken med i resultatet (robust mot at
    Kiwi/Xtra har produkter med likt navn — vi trenger ikke slå opp på navn).
    Returnerer dict {produkt_navn, butikk, pakkepris, pakke_mengde,
    enhetsklasse, enhetspris} eller None hvis ingen passerer gaten."""
    beste = None
    for p in kandidater:
        navn = p.get("name") or ""
        pris = p.get("current_price")
        if pris is None or not er_treff(hode, navn):
            continue
        parsed = parse_produktnavn(navn)
        if not parsed:
            continue
        klasse, mengde = parsed
        if klasse != mal_klasse or mengde <= 0:
            continue
        enhetspris = pris / mengde
        if beste is None or enhetspris < beste["enhetspris"]:
            beste = {
                "produkt_navn": navn,
                "butikk": p.get("_store"),
                "pakkepris": pris,
                "pakke_mengde": mengde,
                "enhetsklasse": klasse,
                "enhetspris": enhetspris,
            }
    return beste
```

- [ ] **Step 5: Kjør testene og bekreft at de passerer**

Run: `cd scripts && python -m pytest test_kassal.py -v`
Expected: PASS — alle tester grønne (~19 stk).

- [ ] **Step 6: Commit**

```bash
git add scripts/kassal.py scripts/test_kassal.py scripts/requirements-dev.txt
git commit -m "feat(priser): ren parse/match-logikk for kassal.app med tester"
```

---

## Task 2: Bestem ingrediensens enhetsklasse + basismengde (TDD)

`lib.rs` trenger å vite hvilken enhetsklasse en *ingrediens* (ikke produkt) hører til, og dens basismengde. Samme tabell brukes i skriptet for å velge `mal_klasse`. Vi legger den i `kassal.py` så den deles og testes.

**Files:**
- Modify: `scripts/kassal.py` (legg til `ingrediens_basis`)
- Modify: `scripts/test_kassal.py` (legg til tester)

- [ ] **Step 1: Skriv feilende tester**

Legg til i `scripts/test_kassal.py`:

```python
# ── ingrediens_basis: (enhetsklasse, mengde_i_basis) fra ingrediens-enhet ──
def test_ingrediens_basis_gram():
    assert kassal.ingrediens_basis(100.0, "g") == ("g", 100.0)
    assert kassal.ingrediens_basis(2.0, "kg") == ("g", 2000.0)

def test_ingrediens_basis_skje():
    assert kassal.ingrediens_basis(2.0, "ss") == ("g", 30.0)   # 1 ss = 15 g/ml
    assert kassal.ingrediens_basis(1.0, "ts") == ("g", 5.0)

def test_ingrediens_basis_volum():
    assert kassal.ingrediens_basis(4.0, "dl") == ("ml", 400.0)
    assert kassal.ingrediens_basis(0.5, "l") == ("ml", 500.0)

def test_ingrediens_basis_stk():
    assert kassal.ingrediens_basis(4.0, "stk.") == ("stk", 4.0)
    assert kassal.ingrediens_basis(3.0, "") == ("stk", 3.0)

def test_ingrediens_basis_ukjent_gir_none():
    assert kassal.ingrediens_basis(1.0, "bunt") is None
    assert kassal.ingrediens_basis(1.0, "boks") is None
```

Merk: `ss`/`ts` defaulter til `g`-klassen (15 g / 5 g). For volum-ingredienser i ss/ts (f.eks. olje) blir det en liten unøyaktighet, men holder presisjonen enkel; dokumentert i spec som akseptert.

- [ ] **Step 2: Kjør og bekreft fail**

Run: `cd scripts && python -m pytest test_kassal.py::test_ingrediens_basis_gram -v`
Expected: FAIL — `AttributeError: module 'kassal' has no attribute 'ingrediens_basis'`.

- [ ] **Step 3: Implementer `ingrediens_basis`**

Legg til i `scripts/kassal.py` (etter `_TO_BASIS`):

```python
# Ingrediens-enhet → (enhetsklasse, multiplikator til basis g/ml/stk).
# ss/ts defaulter til g-klassen (15 g / 5 g). klype/never er små g-anslag.
_ING_BASIS = {
    "g": ("g", 1.0), "kg": ("g", 1000.0), "hg": ("g", 100.0),
    "ss": ("g", 15.0), "ts": ("g", 5.0), "klype": ("g", 1.0), "never": ("g", 5.0),
    "dl": ("ml", 100.0), "l": ("ml", 1000.0), "cl": ("ml", 10.0), "ml": ("ml", 1.0),
    "stk.": ("stk", 1.0), "stk": ("stk", 1.0), "": ("stk", 1.0),
}
```

og funksjonen:

```python
def ingrediens_basis(mengde, enhet):
    """(enhetsklasse, mengde_i_basis) for en ingrediens-enhet, eller None
    hvis enheten ikke kan konverteres (boks, bunt, glass, pose, ...)."""
    e = (enhet or "").strip().lower()
    if e not in _ING_BASIS:
        return None
    klasse, mult = _ING_BASIS[e]
    return (klasse, mengde * mult)
```

- [ ] **Step 4: Kjør og bekreft pass**

Run: `cd scripts && python -m pytest test_kassal.py -v`
Expected: PASS — alle tester grønne.

- [ ] **Step 5: Commit**

```bash
git add scripts/kassal.py scripts/test_kassal.py
git commit -m "feat(priser): ingrediens_basis enhetskonvertering med tester"
```

---

## Task 3: Orkestrerings-skript `hent_priser.py`

Henter ingredienser fra DB, kaller API med rate-limit/backoff, bruker `kassal.py`, skriver `priser`-tabell. Gjenopptagbar. Ikke enhetstestet (I/O + nett) — verifiseres med en liten ekte kjøring (`PRISER_LIMIT`).

**Files:**
- Create: `scripts/hent_priser.py`

- [ ] **Step 1: Skriv skriptet**

Create `scripts/hent_priser.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hent_priser.py – Bygger pris-cache i kokt.db fra kassal.app (Kiwi + Coop Extra).

Kjøres fra repo-roten:
    python scripts/hent_priser.py

Mekanikk (se docs/superpowers/specs/2026-06-12-prisestimat-design.md):
  per distinkt ingrediens → søk på hodeord i KIWI og COOP_EXTRA →
  streng token-match → parse vekt fra produktnavn → billigste enhetspris.

API-nøkkel leses fra KASSAL_API_KEY (med innebygd fallback; nøkkelen er ikke
sensitiv). Maks 60 kall/min – skriptet sover for å holde seg under, og
respekterer 429 med backoff. Gjenopptagbar: hopper over allerede-behandlede.
Sett PRISER_LIMIT=N for å begrense under testing."""

import os, sys, json, sqlite3, time, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kassal

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

API_BASE = "https://kassal.app/api/v1/products"
API_KEY = os.environ.get("KASSAL_API_KEY")  # kreves; ingen innebygd nøkkel
BUTIKKER = ("KIWI", "COOP_EXTRA")
MIN_INTERVALL = 1.05  # sekunder mellom kall → < 60/min

SCHEMA = """
CREATE TABLE IF NOT EXISTS priser (
    ingredient_navn  TEXT PRIMARY KEY,
    produkt_navn     TEXT,
    butikk           TEXT,
    pakkepris        REAL,
    pakke_mengde     REAL,
    enhetsklasse     TEXT,
    enhetspris       REAL,
    oppdatert        TEXT
);
"""


def _finn_db():
    sd = os.path.dirname(os.path.abspath(__file__))
    for sti in [
        os.path.join(sd, "..", "kokebok-app", "src-tauri", "data", "kokt.db"),
        os.path.join(sd, "..", "kokebok-app", "src-tauri", "kokt.db"),
    ]:
        sti = os.path.normpath(sti)
        if os.path.exists(sti):
            return sti
    sys.exit("Fant ikke kokt.db under kokebok-app/src-tauri/data/")


def _hent(query, store):
    """Ett API-kall. Returnerer produkt-liste (data) eller [] ved feil.
    Håndterer 429 med backoff via Retry-After."""
    url = API_BASE + "?" + urllib.parse.urlencode({"search": query, "store": store, "size": 5})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {API_KEY}"})
    for forsok in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("data", [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                vent = int(e.headers.get("Retry-After", "5"))
                print(f"   429 – venter {vent}s …")
                time.sleep(vent)
                continue
            print(f"   HTTP {e.code} for '{query}' [{store}]")
            return []
        except Exception as ex:
            print(f"   Nettverksfeil for '{query}' [{store}]: {ex}")
            time.sleep(2)
    return []


def main():
    print("=== Prisdata fra kassal.app (Kiwi + Coop Extra) ===\n")
    db = sqlite3.connect(_finn_db())
    db.executescript(SCHEMA)
    db.commit()

    limit = os.environ.get("PRISER_LIMIT")
    limit_sql = f"LIMIT {int(limit)}" if limit and limit.isdigit() else ""
    rader = db.execute(f"""
        SELECT LOWER(TRIM(navn)) AS n, COUNT(*) AS c
        FROM ingredienser
        GROUP BY n ORDER BY c DESC {limit_sql}
    """).fetchall()

    ferdige = {r[0] for r in db.execute("SELECT ingredient_navn FROM priser").fetchall()}
    todo = [(n, c) for n, c in rader if n not in ferdige]
    print(f"Distinkte ingredienser: {len(rader)}  |  gjenstår: {len(todo)}\n")

    forrige = 0.0
    ok = bom = 0
    for i, (navn, _) in enumerate(todo, 1):
        hode = kassal.hodeord(navn)
        # mal_klasse: hva ingrediensen MÅ matche. Bruk mengde=1 (vi trenger kun klassen).
        basis = kassal.ingrediens_basis(1.0, _enhet_for(db, navn))
        if not hode or not basis:
            db.execute("INSERT OR IGNORE INTO priser (ingredient_navn) VALUES (?)", (navn,))
            bom += 1
            print(f"[{i}/{len(todo)}] –  {navn:30s} (ingen hodeord/enhet)")
            continue
        mal_klasse = basis[0]

        kandidater = []
        for store in BUTIKKER:
            ventetid = MIN_INTERVALL - (time.time() - forrige)
            if ventetid > 0:
                time.sleep(ventetid)
            for p in _hent(hode, store):
                p["_store"] = store
                kandidater.append(p)
            forrige = time.time()

        beste = kassal.velg_beste(hode, kandidater, mal_klasse)
        if beste:
            # butikk bæres med fra velg_beste (_store), robust mot like navn.
            db.execute("""
                INSERT OR REPLACE INTO priser
                  (ingredient_navn, produkt_navn, butikk, pakkepris,
                   pakke_mengde, enhetsklasse, enhetspris, oppdatert)
                VALUES (?,?,?,?,?,?,?, datetime('now'))
            """, (navn, beste["produkt_navn"], beste["butikk"], beste["pakkepris"],
                  beste["pakke_mengde"], beste["enhetsklasse"], beste["enhetspris"]))
            ok += 1
            print(f"[{i}/{len(todo)}] ✓  {navn:30s} → {beste['produkt_navn'][:34]} "
                  f"({beste['enhetspris']:.3f} kr/{beste['enhetsklasse']})")
        else:
            db.execute("INSERT OR IGNORE INTO priser (ingredient_navn) VALUES (?)", (navn,))
            bom += 1
            print(f"[{i}/{len(todo)}] –  {navn:30s} → ingen gyldig match")

        if i % 25 == 0:
            db.commit()

    db.commit()
    db.close()
    print(f"\n{'='*60}\nFerdig!  ✓ {ok} priset  –  {bom} uten match")


def _enhet_for(db, navn):
    """Mest brukte enhet for et ingrediensnavn (samme navn kan ha flere)."""
    r = db.execute("""
        SELECT enhet FROM ingredienser WHERE LOWER(TRIM(navn)) = ?
        GROUP BY enhet ORDER BY COUNT(*) DESC LIMIT 1
    """, (navn,)).fetchone()
    return r[0] if r else ""


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Liten ekte testkjøring (verifiser ende-til-ende mot API)**

Run (PowerShell — brukerens shell): `cd "<repo>"; $env:PRISER_LIMIT=8; python scripts/hent_priser.py`
Expected: 8 vanligste ingredienser behandles; minst noen får `✓` med fornuftig kr/enhet (f.eks. egg → ~2 kr/stk). Ingen krasj. Tar ~20–30 sek (rate-limit).
(Rydd opp etter: `Remove-Item Env:\PRISER_LIMIT`.)

- [ ] **Step 3: Verifiser tabellen**

Run:
```bash
cd "<repo>/kokebok-app/src-tauri/data" && python -c "import sqlite3; db=sqlite3.connect('kokt.db'); [print(r) for r in db.execute('SELECT ingredient_navn, produkt_navn, butikk, enhetsklasse, ROUND(enhetspris,3) FROM priser WHERE enhetspris IS NOT NULL LIMIT 10')]"
```
Expected: Rader med fornuftige produkt-matcher og enhetspriser. Manuell sjekk: ingen åpenbare feiltreff (descriptor-matcher).

- [ ] **Step 4: Commit**

```bash
git add scripts/hent_priser.py
git commit -m "feat(priser): orkestrerings-skript med rate-limit og 429-backoff"
```

---

## Task 4: Kostnadsberegning i `lib.rs`

Ny blokk i `hent_oppskrift` som summerer kostnad fra `priser`-tabellen, parallelt med nærings-blokken. Returnerer pris-objekt eller `Null`.

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (i `hent_oppskrift`, etter nærings-blokken ~linje 269, før `Ok(Some(opp))`)

- [ ] **Step 1: Legg til pris-beregning**

Kontekst: i `hent_oppskrift` finnes allerede en levende mutbar lån `let obj = opp.as_object_mut().unwrap();` (linje 180) som brukes hele veien (setter inn `ingredienser`, `trinn`, `kategorier`, `naering`). Pris-koden MÅ derfor bruke `obj` direkte — ikke re-låne `opp` — ellers oppstår en borrow-konflikt. Les `porsjoner` fra `obj`, ikke fra `opp`.

I `kokebok-app/src-tauri/src/lib.rs`, rett ETTER linjen `obj.insert("naering".into(), naering);` (linje 272), legg til:

```rust
    // ─── Pris-estimat ──────────────────────────────────────────────────────────
    // Beregn kostnad PER ingrediens i en subquery (`kostnad`), så aggregerer vi.
    // `kostnad` blir NULL når (a) ingen pris-rad matcher, ELLER (b) ingrediensens
    // enhet ikke passer pris-radens enhetsklasse (indre CASE → NULL). VIKTIG:
    // `priset` må telle bare rader der `kostnad` faktisk ble beregnet (IS NOT
    // NULL) — ikke bare join-treff — ellers blåses dekningstallet opp med
    // ingredienser som matchet men ikke kunne prises pga. enhets-mismatch.
    // Enhetsklasse + enhetspris er forhåndsberegnet av scripts/hent_priser.py;
    // konverteringen speiler ingrediens_basis i kassal.py.
    let pris_sql = "
        SELECT
          ROUND(SUM(kostnad), 2)                       AS totalt,
          COUNT(kostnad)                               AS priset,        -- COUNT hopper over NULL
          COUNT(*)                                     AS totalt_antall,
          MAX(oppdatert)                               AS oppdatert
        FROM (
          SELECT
            i.id,
            p.oppdatert AS oppdatert,
            (CASE p.enhetsklasse
               WHEN 'g' THEN (CASE i.enhet
                 WHEN 'g' THEN i.mengde      WHEN 'kg' THEN i.mengde*1000
                 WHEN 'hg' THEN i.mengde*100 WHEN 'ss' THEN i.mengde*15
                 WHEN 'ts' THEN i.mengde*5   WHEN 'klype' THEN i.mengde
                 WHEN 'never' THEN i.mengde*5 ELSE NULL END)
               WHEN 'ml' THEN (CASE i.enhet
                 WHEN 'ml' THEN i.mengde     WHEN 'dl' THEN i.mengde*100
                 WHEN 'l' THEN i.mengde*1000 WHEN 'cl' THEN i.mengde*10
                 ELSE NULL END)
               WHEN 'stk' THEN (CASE i.enhet
                 WHEN 'stk.' THEN i.mengde WHEN 'stk' THEN i.mengde
                 WHEN '' THEN i.mengde ELSE NULL END)
               ELSE NULL END
             * p.enhetspris) AS kostnad
          FROM ingredienser i
          LEFT JOIN priser p
                 ON LOWER(TRIM(i.navn)) = p.ingredient_navn
                AND p.enhetspris IS NOT NULL
          WHERE i.oppskrift_id = ?
        )";

    // Les porsjoner fra det allerede eksisterende `obj`-lånet (ikke fra `opp`).
    let porsjoner = obj
        .get("porsjoner")
        .and_then(|v| v.as_f64())
        .filter(|p| *p > 0.0)
        .unwrap_or(4.0);

    let mut prows = query_json(&conn, pris_sql, &[&id])?;
    let pris = match prows.pop() {
        Some(pr) => {
            let totalt = pr.get("totalt").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let priset = pr.get("priset").and_then(|v| v.as_i64()).unwrap_or(0);
            if totalt > 0.0 && priset > 0 {
                let mut m = pr.as_object().unwrap().clone();
                m.insert(
                    "per_porsjon".into(),
                    Value::from((totalt / porsjoner * 100.0).round() / 100.0),
                );
                Value::Object(m)
            } else {
                Value::Null
            }
        }
        None => Value::Null,
    };
    obj.insert("pris".into(), pris);
```

Merk: `priset` = `COUNT(kostnad)` teller bare ingredienser der en kostnad faktisk ble beregnet (SQL `COUNT` hopper over NULL). `totalt_antall` = `COUNT(*)` = alle ingredienser i oppskriften. Dermed er «N av M priset» ærlig: en ingrediens som matchet et produkt men ikke kunne konverteres (enhets-mismatch) gir NULL kostnad og telles IKKE som priset.

- [ ] **Step 2: Kompiler**

Run: `cd "<repo>/kokebok-app/src-tauri" && cargo check`
Expected: `Finished` uten feil. (Advarsler om ubrukt kode er ok.)

- [ ] **Step 3: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(priser): kostnadsberegning i hent_oppskrift"
```

---

## Task 5: Pris-boks i frontend `+page.svelte`

Vis pris-estimatet ved siden av nærings-boksen, samme mønster.

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (derived ~etter linje 170; markup ~etter nærings-boksen ~linje 393)

- [ ] **Step 1: Legg til derived pris-data**

I `<script>`, rett etter `naeringPerPorsjon`-blokken (~linje 170), legg til:

```ts
  // Pris: backend gir total for GRUNN-porsjoner. Total skalerer med curP/origP;
  // per-porsjon er stabil (total / origP), som nærings-per-porsjon.
  let prisVist = $derived.by(() => {
    const pr = currentOppskrift?.pris;
    if (!pr || !(pr.totalt > 0)) return null;
    const skala = curP / origP;
    return {
      total: Math.round(pr.totalt * skala),
      perPorsjon: Math.round(pr.totalt / origP),
      priset: pr.priset,
      antall: pr.totalt_antall,
    };
  });
```

- [ ] **Step 2: Legg til markup**

`naering-wrap`-div-en åpner ~linje 355 og lukkes av `</div>` på linje 402 (rett etter `{/if}` på linje 401). Legg pris-boksen rett ETTER den lukkende `</div>` på linje 402, FØR den neste `</div>` (linje 403):

```svelte
        {#if prisVist}
          {@const pr = prisVist}
          <div class="pris-wrap">
            <div class="pris-title">💰 Estimert kostnad</div>
            <div class="pris-tall">
              ~{pr.total} kr · ~{pr.perPorsjon} kr/porsjon
            </div>
            <div class="pris-dekning">
              {pr.priset} av {pr.antall} ingredienser priset
            </div>
          </div>
        {/if}
```

- [ ] **Step 3: Legg til stil**

Først, finn de faktiske fargene nærings-boksen bruker, så pris-boksen matcher:

Run: `cd "<repo>/kokebok-app" && grep -n "naering-wrap\|naering-title\|naering-disclaimer" src/app.css src/routes/+page.svelte`

Stilene ligger inline i `+page.svelte` sin `<style>`-blokk (fra ~linje 412), ikke i `app.css`. Legg pris-stilen der, ved siden av `.naering-*`-reglene. Appen bruker CSS-variabler (`var(--border)` osv.) — bruk gjerne disse. Bruk verdiene under som utgangspunkt, men erstatt fargene med de eksisterende `naering`-fargene/variablene hvis de avviker:

```css
  .pris-wrap {
    margin-top: 1rem;
    padding: 1rem 1.25rem;
    background: #f6efe3;
    border-radius: 12px;
    border: 1px solid #e6d9c2;
  }
  .pris-title { font-weight: 600; margin-bottom: 0.35rem; }
  .pris-tall { font-size: 1.15rem; color: #7a4a1e; }
  .pris-dekning {
    font-size: 0.85rem;
    color: #9a8a72;
    opacity: 0.8;
    margin-top: 0.25rem;
  }
```

- [ ] **Step 4: Bygg frontend**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil.

- [ ] **Step 5: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(priser): pris-boks i oppskrift-detalj"
```

---

## Task 6: Manuell ende-til-ende-verifikasjon + README

Pris-boksen vises bare for oppskrifter der noen ingredienser er priset. Trenger en reell (om enn liten) pris-cache for å se den. Kjør en delvis cache og verifiser i appen.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Bygg en delvis pris-cache (topp ~200 ingredienser)**

Run (PowerShell): `cd "<repo>"; $env:PRISER_LIMIT=200; python scripts/hent_priser.py; Remove-Item Env:\PRISER_LIMIT`
Expected: ~200 vanligste ingredienser behandles (~7 min med rate-limit). Dekker de fleste enkle oppskrifter delvis.

- [ ] **Step 2: Kjør appen i dev og verifiser visuelt**

Run: `cd "<repo>/kokebok-app" && npm run tauri dev`
Expected (MANUELL sjekk — krever menneske ved skjermen):
- Åpne en oppskrift med vanlige ingredienser (f.eks. søk «pannekak»).
- Pris-boksen vises under næring: «~X kr · ~Y kr/porsjon · N av M priset».
- Endre porsjoner opp/ned: **total** endrer seg, **per-porsjon** står stille.
- Åpne en oppskrift uten prisede ingredienser: pris-boksen vises ikke (ingen krasj).

- [ ] **Step 3: Dokumentér i README**

I `README.md`, under «### Oppdatere næringsdata», legg til en parallell seksjon:

```markdown
### Oppdatere prisdata (valgfritt)

`priser`-tabellen hentes fra [kassal.app](https://kassal.app) (Kiwi + Coop Extra).
Skriptet matcher ingredienser mot butikkprodukter, parser pakkevekt fra
produktnavnet og regner billigste enhetspris.

```bash
python scripts/hent_priser.py        # fra repo-roten; oppdaterer data/kokt.db
```

Maks 60 API-kall/min, så full kjøring (~7195 ingredienser × 2 kall) tar noen
timer. Skriptet er gjenopptagbart. `PRISER_LIMIT=N` begrenser under testing.
Etter oppdatering må appen bygges på nytt for at ny `kokt.db` skal pakkes med.
```

Også i arkitektur-/data-tabellen: nevn `priser`-tabellen ved siden av `naering`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(priser): dokumentér hent_priser.py i README"
```

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** Tabell (T3), skript-mekanikk (T1–T3), lib.rs-beregning (T4),
  UI (T5), dekningsgrenser (håndtert som NULL/ikke-priset i T4-SQL), nøkkel fra
  env (T3). Alt dekket.
- **Typer konsistente:** `enhetsklasse` ∈ {g,ml,stk}, `enhetspris`, `pakke_mengde`,
  `pakkepris` brukt likt i kassal.py (T1), DB-schema (T3), lib.rs-SQL (T4). Retur-
  feltene `totalt`/`per_porsjon`/`priset`/`totalt_antall` matcher mellom lib.rs (T4)
  og frontend `prisVist` (T5).
- **Kjent skjørhet flagget:** ss/ts→g-default (akseptert unøyaktighet for olje);
  volum/stk-dekningshull telles ærlig. Stil-fargekoder må matches mot faktisk
  app.css ved implementering (notert i T5 Step 3).
