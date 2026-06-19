#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hent_priser.py – Bygger pris-cache i kokt.db fra kassal.app (Kiwi + Coop Extra).

Kjøres fra repo-roten:
    python scripts/hent_priser.py

Mekanikk (se docs/superpowers/specs/2026-06-12-prisestimat-design.md):
  per distinkt ingrediens → søk på hodeord i KIWI og COOP_EXTRA →
  streng token-match → parse vekt fra produktnavn → billigste enhetspris.

API-nøkkel leses fra miljøvariabelen KASSAL_API_KEY (kreves; ingen innebygd
nøkkel — skaff din egen gratis på https://kassal.app). Maks 60 kall/min –
skriptet sover for å holde seg under, og respekterer 429 med backoff.
Gjenopptagbar: hopper over allerede-behandlede. Sett PRISER_LIMIT=N for å
begrense under testing."""

import os, sys, json, sqlite3, time, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kassal

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

API_BASE = "https://kassal.app/api/v1/products"
API_KEY = os.environ.get("KASSAL_API_KEY")
if not API_KEY:
    sys.exit("KASSAL_API_KEY mangler. Skaff en gratis nøkkel på https://kassal.app "
             "og sett miljøvariabelen, f.eks.  export KASSAL_API_KEY=din_nøkkel")
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


def _enhet_for(db, navn):
    """Mest brukte enhet for et ingrediensnavn (samme navn kan ha flere)."""
    r = db.execute("""
        SELECT enhet FROM ingredienser WHERE LOWER(TRIM(navn)) = ?
        GROUP BY enhet ORDER BY COUNT(*) DESC LIMIT 1
    """, (navn,)).fetchone()
    return r[0] if r else ""


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


if __name__ == "__main__":
    main()
