# godt.no-skraper — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Et bruker-kjørt Python-skript `scripts/hent_godt.py` som skraper oppskrifter (med 600px-bilder) fra godt.no inn i `data/kokt.db` som en andre datakilde ved siden av matprat, til privat bruk.

**Architecture:** Sitemap-drevet oppdagelse → JSON-LD-først uttrekk (HTML-fallback) → norsk ingrediensparser → dedup på URL+uklar navn → skriv til de eksisterende fire tabellene. Rene parsere TDD-es med pytest; nettverk/IO-deler valideres manuelt av brukeren mot ekte sider.

**Tech Stack:** Python 3 (stdlib `urllib`/`xml.etree`/`json`/`re`/`difflib`/`html.parser`), Pillow (bilder). Ingen requests/bs4 — matcher husstilen i `hent_naering.py`/`hent_priser.py`.

**Spec:** `docs/superpowers/specs/2026-06-15-godt-scraper-design.md`

**VIKTIG — agent/etisk grense:** godt.no robots.txt blokkerer AI-crawlere eksplisitt. Implementereren skal **IKKE hente/crawle godt.no live** (ingen WebFetch/urlopen mot godt.no under utvikling). Alle nettverksdeler testes mot **lokale fixtures / hardkodede strenger**, aldri mot live-siden. Brukeren kjører skriptet mot ekte sider selv.

**Testoppsett:** pytest finnes (`scripts/requirements-dev.txt`). Tester legges i `scripts/test_hent_godt.py` og kjøres fra `scripts/`-mappa (samme som `test_kassal.py`, som gjør `import kassal`). Kjør: `cd scripts && python -m pytest test_hent_godt.py -v`.

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `scripts/hent_godt.py` | Hele skraperen (alle funksjoner under) | Create (bygges opp task for task) |
| `scripts/test_hent_godt.py` | pytest for rene parsere | Create |
| `.gitignore` | Ignorer `scripts/godt_cache/` | Modify |
| `README.md` | godt.no-attribusjon + re-kjør næring/pris-note | Modify |

**Rekkefølge:** rene TDD-funksjoner først (T1 ingrediensparser, T2 tid/yield-hjelpere, T3 JSON-LD-parser, T4 kategori-map, T5 dedup), så IO-lag (T6 hent/cache/robots, T7 sitemap, T8 bilde, T9 lagre+main), så docs (T10). Hver task etterlater skriptet importerbart og testene grønne.

**Skjelett:** T1 oppretter fila med modul-docstring + UTF-8-reconfigure + imports, så hver senere task legger til sin funksjon.

---

## Task 1: Ingrediensparser `parse_ingrediens` (TDD)

Norsk rålinje → `(mengde: float|None, enhet: str|None, navn: str)`. Beholder aldri tap: kalleren lagrer alltid rålinja i `raatekst` separat.

**Files:**
- Create: `scripts/hent_godt.py`
- Create: `scripts/test_hent_godt.py`

- [ ] **Step 1: Opprett skjelett-fila**

Create `scripts/hent_godt.py`:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hent_godt.py – Skraper oppskrifter fra godt.no inn i kokt.db (privat bruk).

Kjøres én gang fra repo-roten:
    python scripts/hent_godt.py --limit 10      # trygg første kjøring
    python scripts/hent_godt.py                 # hele katalogen

Andre datakilde ved siden av matprat. Respekterer robots.txt for egen UA,
rate-limiter, og cacher sider i scripts/godt_cache/. Oppskriftsdata © godt.no.
"""
import sys

# Windows-konsollen bruker cp1252 ved omdirigering; tving UTF-8 så ✓/– ikke krasjer.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import re

# Brøk-symboler → desimal (samme verdier som appens FRACS i +page.svelte).
_BROK = {
    "¼": 0.25, "½": 0.5, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3,
    "⅛": 0.125,
}

# Kjente norske enheter (fra ingredienser.enhet i kokt.db).
_ENHETER = {
    "g", "kg", "dl", "l", "ml", "ts", "ss", "stk", "stk.", "pk", "pakke",
    "boks", "bokser", "pose", "poser", "glass", "plate", "plater", "klype",
    "bunt", "skive", "skiver", "båt", "båter", "fedd", "kopp", "krm",
}
```

- [ ] **Step 2: Skriv de feilende testene**

Create `scripts/test_hent_godt.py`:
```python
# -*- coding: utf-8 -*-
import hent_godt


def test_parse_tall_enhet_navn():
    assert hent_godt.parse_ingrediens("2 dl melk") == (2.0, "dl", "melk")

def test_parse_heltall_gram():
    assert hent_godt.parse_ingrediens("100 g smør") == (100.0, "g", "smør")

def test_parse_brok_symbol():
    assert hent_godt.parse_ingrediens("½ ts salt") == (0.5, "ts", "salt")

def test_parse_brok_skrastrek():
    assert hent_godt.parse_ingrediens("1/2 dl fløte") == (0.5, "dl", "fløte")

def test_parse_stk_uten_enhetsord():
    # "3 egg" – tall + navn, ingen enhet
    assert hent_godt.parse_ingrediens("3 egg") == (3.0, None, "egg")

def test_parse_uten_mengde():
    assert hent_godt.parse_ingrediens("salt etter smak") == (None, None, "salt etter smak")

def test_parse_desimal_komma():
    assert hent_godt.parse_ingrediens("1,5 dl vann") == (1.5, "dl", "vann")

def test_parse_tom_streng():
    assert hent_godt.parse_ingrediens("") == (None, None, "")

def test_parse_stripper_whitespace():
    assert hent_godt.parse_ingrediens("  2 ss olje  ") == (2.0, "ss", "olje")
```

- [ ] **Step 3: Kjør testene – forvent FAIL**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle 9 feiler med `AttributeError: module 'hent_godt' has no attribute 'parse_ingrediens'`.

- [ ] **Step 4: Implementer `parse_ingrediens`**

Legg til i `scripts/hent_godt.py`:
```python
def parse_ingrediens(linje):
    """Rålinje → (mengde, enhet, navn). Best-effort; rålinja lagres separat.

    Tall kan være heltall, desimal (komma eller punktum), brøk-symbol (½) eller
    skråstrek-brøk (1/2). Enhet gjenkjennes bare hvis ordet rett etter tallet er
    en kjent norsk enhet; ellers regnes resten som navn (f.eks. "3 egg").
    """
    s = linje.strip()
    if not s:
        return (None, None, "")

    # Finn ledende mengde: brøksymbol, eller (heltall/desimal/skråstrek-brøk).
    mengde = None
    rest = s
    m = re.match(r"^([¼½¾⅓⅔⅛])\s*(.*)$", s)
    if m:
        mengde = _BROK[m.group(1)]
        rest = m.group(2)
    else:
        m = re.match(r"^(\d+)\s*/\s*(\d+)\s+(.*)$", s)
        if m:
            mengde = int(m.group(1)) / int(m.group(2))
            rest = m.group(3)
        else:
            m = re.match(r"^(\d+(?:[.,]\d+)?)\s+(.*)$", s)
            if m:
                mengde = float(m.group(1).replace(",", "."))
                rest = m.group(2)

    if mengde is None:
        return (None, None, s)

    # Enhet: første ord i rest, hvis det er en kjent enhet.
    enhet = None
    deler = rest.split(maxsplit=1)
    if deler and deler[0].lower().rstrip(".") in {e.rstrip(".") for e in _ENHETER}:
        enhet = deler[0]
        rest = deler[1] if len(deler) > 1 else ""

    return (mengde, enhet, rest.strip())
```

- [ ] **Step 5: Kjør testene – forvent PASS**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle 9 grønne.

- [ ] **Step 6: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py scripts/test_hent_godt.py
git commit -m "feat(godt): ingrediensparser parse_ingrediens (TDD)"
```

---

## Task 2: Tid- og porsjon-hjelpere (TDD)

`iso8601_til_min` (ISO-8601-varighet → "N min" som matprat-`tid`) og `parse_yield` (recipeYield → ledende heltall).

**Files:**
- Modify: `scripts/hent_godt.py`
- Modify: `scripts/test_hent_godt.py`

- [ ] **Step 1: Skriv feilende tester**

Legg til i `scripts/test_hent_godt.py`:
```python
def test_iso_varighet_minutter():
    assert hent_godt.iso8601_til_min("PT30M") == "30 min"

def test_iso_varighet_timer_og_min():
    assert hent_godt.iso8601_til_min("PT1H30M") == "90 min"

def test_iso_varighet_bare_timer():
    assert hent_godt.iso8601_til_min("PT2H") == "120 min"

def test_iso_varighet_ugyldig_gir_none():
    assert hent_godt.iso8601_til_min("") is None
    assert hent_godt.iso8601_til_min(None) is None
    assert hent_godt.iso8601_til_min("tull") is None

def test_yield_heltall():
    assert hent_godt.parse_yield("4 porsjoner") == 4

def test_yield_bare_tall():
    assert hent_godt.parse_yield("6") == 6

def test_yield_liste_tar_forste_tall():
    # recipeYield kan være liste, kalleren sender str; her: ledende tall
    assert hent_godt.parse_yield("ca 4-6 porsjoner") == 4

def test_yield_uten_tall_gir_none():
    assert hent_godt.parse_yield("noen") is None
    assert hent_godt.parse_yield(None) is None
```

- [ ] **Step 2: Kjør – forvent FAIL**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -k "iso_varighet or yield" -v`
Expected: de 8 nye feiler (`has no attribute 'iso8601_til_min'` / `'parse_yield'`).

- [ ] **Step 3: Implementer**

Legg til i `scripts/hent_godt.py`:
```python
def iso8601_til_min(varighet):
    """ISO-8601-varighet (PT1H30M) → "N min". None ved ugyldig/ tom."""
    if not varighet:
        return None
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$", varighet)
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    timer = int(m.group(1)) if m.group(1) else 0
    minutter = int(m.group(2)) if m.group(2) else 0
    return f"{timer * 60 + minutter} min"


def parse_yield(verdi):
    """recipeYield → ledende heltall (porsjoner). None hvis ingen tall."""
    if not verdi:
        return None
    m = re.search(r"\d+", str(verdi))
    return int(m.group(0)) if m else None
```

- [ ] **Step 4: Kjør – forvent PASS**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle grønne (17 totalt).

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py scripts/test_hent_godt.py
git commit -m "feat(godt): tid- og porsjon-hjelpere (TDD)"
```

---

## Task 3: JSON-LD-parser `parse_jsonld` (TDD)

Trekk ut schema.org/Recipe-dict fra HTML. Håndterer `@graph`-wrapping og at JSON-LD-blokka kan være en liste.

**Files:**
- Modify: `scripts/hent_godt.py`
- Modify: `scripts/test_hent_godt.py`

- [ ] **Step 1: Skriv feilende tester**

Legg til i `scripts/test_hent_godt.py` (øverst, legg til `import json` om ikke finnes — testen bygger HTML-fixture):
```python
def _html_med_jsonld(obj):
    import json
    return (
        '<html><head>'
        '<script type="application/ld+json">' + json.dumps(obj) + '</script>'
        '</head><body>x</body></html>'
    )

def test_jsonld_enkel_recipe():
    obj = {"@context": "https://schema.org", "@type": "Recipe", "name": "Kjøttkaker"}
    res = hent_godt.parse_jsonld(_html_med_jsonld(obj))
    assert res["name"] == "Kjøttkaker"

def test_jsonld_i_graph():
    obj = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage"},
        {"@type": "Recipe", "name": "Vafler"},
    ]}
    res = hent_godt.parse_jsonld(_html_med_jsonld(obj))
    assert res["name"] == "Vafler"

def test_jsonld_liste_paa_toppniva():
    obj = [{"@type": "Organization"}, {"@type": "Recipe", "name": "Suppe"}]
    res = hent_godt.parse_jsonld(_html_med_jsonld(obj))
    assert res["name"] == "Suppe"

def test_jsonld_ingen_recipe_gir_none():
    obj = {"@type": "WebPage", "name": "ikke en oppskrift"}
    assert hent_godt.parse_jsonld(_html_med_jsonld(obj)) is None

def test_jsonld_ingen_blokk_gir_none():
    assert hent_godt.parse_jsonld("<html><body>ingenting</body></html>") is None

def test_jsonld_ugyldig_json_gir_none():
    html = '<script type="application/ld+json">{ ugyldig }</script>'
    assert hent_godt.parse_jsonld(html) is None
```

- [ ] **Step 2: Kjør – forvent FAIL**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -k jsonld -v`
Expected: de 6 nye feiler (`has no attribute 'parse_jsonld'`).

- [ ] **Step 3: Implementer**

Legg til i `scripts/hent_godt.py` (og legg `import json` til imports øverst hvis ikke der):
```python
import json


def _er_recipe(node):
    t = node.get("@type") if isinstance(node, dict) else None
    if isinstance(t, list):
        return "Recipe" in t
    return t == "Recipe"


def parse_jsonld(html):
    """Finn schema.org/Recipe-dict i HTML-ens JSON-LD. None hvis ingen finnes.

    Håndterer: flere ld+json-blokker, toppnivå-liste, og @graph-wrapping.
    """
    blokker = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    for blokk in blokker:
        try:
            data = json.loads(blokk.strip())
        except (ValueError, TypeError):
            continue
        kandidater = data if isinstance(data, list) else [data]
        for node in kandidater:
            if not isinstance(node, dict):
                continue
            if _er_recipe(node):
                return node
            for g in node.get("@graph", []) or []:
                if _er_recipe(g):
                    return g
    return None
```

- [ ] **Step 4: Kjør – forvent PASS**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle grønne (23 totalt).

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py scripts/test_hent_godt.py
git commit -m "feat(godt): JSON-LD Recipe-parser (TDD)"
```

---

## Task 4: Kategori-mapping `map_type` (TDD)

godt.no-kategori → eksisterende `type`-vokabular der mulig, ellers rå (kapitalisert). Vokabularet er matprat-settet i kokt.db.

**Files:**
- Modify: `scripts/hent_godt.py`
- Modify: `scripts/test_hent_godt.py`

- [ ] **Step 1: Skriv feilende tester**

Legg til i `scripts/test_hent_godt.py`:
```python
def test_map_type_direkte_treff():
    assert hent_godt.map_type("Dessert") == "Dessert"

def test_map_type_ulik_kasus():
    assert hent_godt.map_type("dessert") == "Dessert"

def test_map_type_synonym_middag():
    # godt.no "Middag" finnes ikke i vokabularet → behold rå, kapitalisert
    assert hent_godt.map_type("middag") == "Middag"

def test_map_type_kjent_kake():
    assert hent_godt.map_type("kaker") == "Kaker"

def test_map_type_tom_gir_annet():
    assert hent_godt.map_type("") == "Annet"
    assert hent_godt.map_type(None) == "Annet"
```

- [ ] **Step 2: Kjør – forvent FAIL**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -k map_type -v`
Expected: de 5 nye feiler.

- [ ] **Step 3: Implementer**

Legg til i `scripts/hent_godt.py`:
```python
# Eksisterende type-vokabular i kokt.db (matprat-settet). Brukes til å mappe
# godt.no-kategorier inn så filtrering i appen forblir konsistent.
_TYPE_VOKAB = {
    "tilbehør", "kaker", "annet", "dessert", "tapas/småretter", "gryter",
    "forretter", "brød/bakverk", "sandwich/smørbrød", "biffer", "ovnsretter",
    "kjøttdeig- og farseretter", "hele fileter", "steker", "supper", "salater",
    "drikke", "kyllingfilet", "panneretter", "koteletter", "pasta", "frokost",
    "pizza", "grillspyd", "pålegg", "wok", "turmat", "vegetar", "grillet kylling",
    "koldtbord", "vafler/pannekaker",
}
# Original-kasus for vokabularet (for å returnere riktig skrivemåte).
_TYPE_KANONISK = {
    "tilbehør": "Tilbehør", "kaker": "Kaker", "annet": "Annet", "dessert": "Dessert",
    "tapas/småretter": "Tapas/småretter", "gryter": "Gryter", "forretter": "Forretter",
    "brød/bakverk": "Brød/bakverk", "sandwich/smørbrød": "Sandwich/smørbrød",
    "biffer": "Biffer", "ovnsretter": "Ovnsretter",
    "kjøttdeig- og farseretter": "Kjøttdeig- og farseretter",
    "hele fileter": "Hele fileter", "steker": "Steker", "supper": "Supper",
    "salater": "Salater", "drikke": "Drikke", "kyllingfilet": "Kyllingfilet",
    "panneretter": "Panneretter", "koteletter": "Koteletter", "pasta": "Pasta",
    "frokost": "Frokost", "pizza": "Pizza", "grillspyd": "Grillspyd",
    "pålegg": "Pålegg", "wok": "Wok", "turmat": "Turmat", "vegetar": "Vegetar",
    "grillet kylling": "Grillet kylling", "koldtbord": "Koldtbord",
    "vafler/pannekaker": "Vafler/pannekaker",
}


def map_type(kategori):
    """godt.no-kategori → eksisterende type-vokabular, ellers rå kapitalisert.
    Tom/None → "Annet"."""
    if not kategori:
        return "Annet"
    n = kategori.strip().lower()
    if n in _TYPE_VOKAB:
        return _TYPE_KANONISK[n]
    return kategori.strip()[:1].upper() + kategori.strip()[1:]
```

- [ ] **Step 4: Kjør – forvent PASS**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle grønne (28 totalt).

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py scripts/test_hent_godt.py
git commit -m "feat(godt): kategori-mapping map_type (TDD)"
```

---

## Task 5: Dedup `er_duplikat` + slug-hjelper (TDD)

`lag_slug` (URL → slug) og `er_duplikat(conn, url, navn)` (URL-eksakt + `difflib` uklar navnematch ≥ 0.9) mot in-memory DB.

**Files:**
- Modify: `scripts/hent_godt.py`
- Modify: `scripts/test_hent_godt.py`

- [ ] **Step 1: Skriv feilende tester**

Legg til i `scripts/test_hent_godt.py`:
```python
import sqlite3

def _db_med(navn_url_par):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE oppskrifter (id INTEGER PRIMARY KEY, navn TEXT, url TEXT)")
    for navn, url in navn_url_par:
        conn.execute("INSERT INTO oppskrifter (navn, url) VALUES (?, ?)", (navn, url))
    return conn

def test_slug_fra_url():
    assert hent_godt.lag_slug("https://www.godt.no/oppskrifter/kjottkaker/") == "kjottkaker"

def test_slug_uten_etterskrastrek():
    assert hent_godt.lag_slug("https://www.godt.no/oppskrifter/vafler") == "vafler"

def test_dup_url_eksakt():
    conn = _db_med([("Vafler", "https://www.godt.no/oppskrifter/vafler/")])
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/vafler/", "Vafler") is True

def test_dup_uklar_navn():
    conn = _db_med([("Kjøttkaker", "https://matprat.no/x")])
    # samme navn, annen url → uklar match slår til
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/kjottkaker/", "Kjøttkaker") is True

def test_dup_ny_oppskrift():
    conn = _db_med([("Vafler", "https://matprat.no/x")])
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/lapskaus/", "Lapskaus") is False
```

- [ ] **Step 2: Kjør – forvent FAIL**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -k "slug or dup" -v`
Expected: de 5 nye feiler.

- [ ] **Step 3: Implementer**

Legg til i `scripts/hent_godt.py` (legg `import difflib` til imports):
```python
import difflib


def lag_slug(url):
    """URL → siste sti-segment som slug."""
    return url.rstrip("/").rsplit("/", 1)[-1]


def er_duplikat(conn, url, navn):
    """True hvis url finnes fra før, eller navn uklart matcher (≥ 0.9) et
    eksisterende navn (fanger samme rett fra to kilder)."""
    rad = conn.execute("SELECT 1 FROM oppskrifter WHERE url = ?", (url,)).fetchone()
    if rad:
        return True
    if not navn:
        return False
    n = navn.strip().lower()
    for (eks,) in conn.execute("SELECT navn FROM oppskrifter WHERE navn IS NOT NULL"):
        if difflib.SequenceMatcher(None, n, eks.strip().lower()).ratio() >= 0.9:
            return True
    return False
```

- [ ] **Step 4: Kjør – forvent PASS**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle grønne (33 totalt).

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py scripts/test_hent_godt.py
git commit -m "feat(godt): dedup er_duplikat + lag_slug (TDD)"
```

---

## Task 6: HTTP-lag `hent` + robots (manuell verifikasjon)

Høflig GET med cache + UA + rate-limit, og `robots_ok`. IKKE testet mot live godt.no — verifiseres mot en lokal HTTP-fixture / robots-streng.

**Files:**
- Modify: `scripts/hent_godt.py`
- Modify: `.gitignore`

- [ ] **Step 1: Ignorer cache-katalogen**

I `.gitignore`, legg til:
```
scripts/godt_cache/
```

- [ ] **Step 2: Implementer hent + robots**

Legg til i `scripts/hent_godt.py` (legg til imports: `import os, time, hashlib, urllib.request, urllib.robotparser`):
```python
import os
import time
import hashlib
import urllib.request
import urllib.robotparser

BASIS = "https://www.godt.no"
UA = "kokt-nok-personlig-skraper/1.0 (privat bruk; kontakt: lokal)"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "godt_cache")
_FORRIGE = {"t": 0.0}
_ROBOTS = {"rp": None}


def _rate_limit(delay):
    """Sørg for minst `delay` sekunder siden forrige request (enkelt-trådet)."""
    naa = time.monotonic()
    vent = delay - (naa - _FORRIGE["t"])
    if vent > 0:
        time.sleep(vent)
    _FORRIGE["t"] = time.monotonic()


def hent(url, delay=0.25, bruk_cache=True):
    """Høflig GET → bytes. Cacher per URL i godt_cache/. Setter UA + rate-limit.

    delay=0.25 ⇒ ~4 req/s. Returnerer None ved HTTP-feil (logges av kaller).
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    nokkel = hashlib.sha1(url.encode("utf-8")).hexdigest() + ".bin"
    sti = os.path.join(CACHE_DIR, nokkel)
    if bruk_cache and os.path.exists(sti):
        with open(sti, "rb") as f:
            return f.read()
    _rate_limit(delay)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001 – nettverksfeil skal ikke abortere kjøring
        print(f"  FEIL ved henting av {url}: {e}")
        return None
    with open(sti, "wb") as f:
        f.write(data)
    return data


def robots_ok(url):
    """True hvis vår UA har lov til å hente url per godt.no/robots.txt.
    Feiler robots-henting → returner True (vi har allerede satt en ærlig UA og
    rate-limit; manglende robots blokkerer ikke privat bruk)."""
    rp = _ROBOTS["rp"]
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(BASIS + "/robots.txt")
        try:
            rp.read()
        except Exception:  # noqa: BLE001
            _ROBOTS["rp"] = rp  # cache likevel; can_fetch blir permissiv
            return True
        _ROBOTS["rp"] = rp
    return rp.can_fetch(UA, url)
```

- [ ] **Step 3: Kompiler/importer-sjekk (ingen live-fetch)**

Run: `cd "<repo>/scripts" && python -c "import hent_godt; print('import ok'); print(hent_godt.lag_slug('https://www.godt.no/oppskrifter/x/'))"`
Expected: `import ok` og `x`. (Bekrefter at nye imports/funksjoner laster; ingen nettverk.)

- [ ] **Step 4: Kjør hele testsuiten (skal fortsatt være grønn)**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle 33 grønne.

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py .gitignore
git commit -m "feat(godt): hoflig HTTP-lag hent + robots_ok + cache"
```

---

## Task 7: Sitemap-oppdagelse `finn_oppskrift_urls`

Parser sitemap-index → under-sitemaps → filtrer `/oppskrifter/`-URLer. Bruker `hent`. Verifiseres mot en lokal XML-streng (ikke live).

**Files:**
- Modify: `scripts/hent_godt.py`
- Modify: `scripts/test_hent_godt.py`

- [ ] **Step 1: Skriv test for URL-filtrering (ren del)**

Legg til i `scripts/test_hent_godt.py`:
```python
def test_urls_fra_sitemap_xml():
    xml = b'''<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://www.godt.no/oppskrifter/vafler/</loc></url>
      <url><loc>https://www.godt.no/artikler/noe/</loc></url>
      <url><loc>https://www.godt.no/oppskrifter/lapskaus/</loc></url>
    </urlset>'''
    urls = hent_godt.urls_fra_sitemap(xml)
    assert "https://www.godt.no/oppskrifter/vafler/" in urls
    assert "https://www.godt.no/oppskrifter/lapskaus/" in urls
    assert all("/oppskrifter/" in u for u in urls)
    assert len(urls) == 2

def test_locs_fra_sitemap_index():
    xml = b'''<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://www.godt.no/sitemap-1.xml</loc></sitemap>
      <sitemap><loc>https://www.godt.no/sitemap-2.xml</loc></sitemap>
    </sitemapindex>'''
    locs = hent_godt.locs_fra_xml(xml)
    assert locs == ["https://www.godt.no/sitemap-1.xml", "https://www.godt.no/sitemap-2.xml"]
```

- [ ] **Step 2: Kjør – forvent FAIL**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -k "sitemap" -v`
Expected: de 2 nye feiler.

- [ ] **Step 3: Implementer**

Legg til i `scripts/hent_godt.py` (legg `import xml.etree.ElementTree as ET` til imports):
```python
import xml.etree.ElementTree as ET

_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def locs_fra_xml(xml_bytes):
    """Alle <loc>-tekster i en sitemap eller sitemap-index."""
    rot = ET.fromstring(xml_bytes)
    return [e.text.strip() for e in rot.iter(f"{_SM_NS}loc") if e.text]


def urls_fra_sitemap(xml_bytes):
    """<loc>-URLer som peker på /oppskrifter/-sider."""
    return [u for u in locs_fra_xml(xml_bytes) if "/oppskrifter/" in u]


def finn_oppskrift_urls(delay=0.25, grense=None):
    """Sitemap-index → under-sitemaps → samlet liste av oppskrift-URLer.

    Henter /sitemap-index.xml, så hver under-sitemap, og filtrerer på
    /oppskrifter/. `grense` kutter listen tidlig (for --limit-kjøringer).
    """
    indeks = hent(BASIS + "/sitemap-index.xml", delay=delay)
    if not indeks:
        return []
    under = locs_fra_xml(indeks)
    funnet = []
    for sm_url in under:
        data = hent(sm_url, delay=delay)
        if not data:
            continue
        funnet.extend(urls_fra_sitemap(data))
        if grense and len(funnet) >= grense:
            break
    # Dedup behold rekkefølge.
    sett = list(dict.fromkeys(funnet))
    return sett[:grense] if grense else sett
```

- [ ] **Step 4: Kjør – forvent PASS**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle grønne (35 totalt).

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py scripts/test_hent_godt.py
git commit -m "feat(godt): sitemap-oppdagelse finn_oppskrift_urls"
```

---

## Task 8: Bildenedlasting `lagre_bilde`

Last ned bilde-URL via `hent` → Pillow → 600px lengste side, WebP q78 → `bilder/{slug}.webp`. Returnerer relativ sti eller None.

**Files:**
- Modify: `scripts/hent_godt.py`

- [ ] **Step 1: Implementer**

Legg til i `scripts/hent_godt.py` (legg til imports: `import io`; `from PIL import Image`; gjenbruk konstantene fra recompress: 600/q78):
```python
import io
from PIL import Image

BILDER_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "kokebok-app", "src-tauri", "data", "bilder",
    )
)
_BILDE_SIDE = 600
_BILDE_Q = 78


def lagre_bilde(bilde_url, slug, delay=0.25):
    """Last ned bilde → 600px WebP → bilder/{slug}.webp. Returner relativ sti
    ("bilder/{slug}.webp") eller None ved feil. Hopper over hvis fila finnes."""
    if not bilde_url:
        return None
    rel = f"bilder/{slug}.webp"
    mal = os.path.join(BILDER_DIR, f"{slug}.webp")
    if os.path.exists(mal):
        return rel
    data = hent(bilde_url, delay=delay)
    if not data:
        return None
    try:
        with Image.open(io.BytesIO(data)) as src:
            im = src.convert("RGB")
        w, h = im.size
        storst = max(w, h)
        if storst > _BILDE_SIDE:
            im = im.resize(
                (round(w * _BILDE_SIDE / storst), round(h * _BILDE_SIDE / storst)),
                Image.LANCZOS,
            )
        os.makedirs(BILDER_DIR, exist_ok=True)
        im.save(mal, "WEBP", quality=_BILDE_Q, method=6)
    except Exception as e:  # noqa: BLE001
        print(f"  FEIL ved bilde {bilde_url}: {e}")
        return None
    return rel
```

- [ ] **Step 2: Importer-sjekk**

Run: `cd "<repo>/scripts" && python -c "import hent_godt; print('ok'); print(hent_godt.BILDER_DIR)"`
Expected: `ok` og en sti som ender på `...\kokebok-app\src-tauri\data\bilder`.

- [ ] **Step 3: Testsuiten fortsatt grønn**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle 35 grønne.

- [ ] **Step 4: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py
git commit -m "feat(godt): bildenedlasting lagre_bilde (600px WebP)"
```

---

## Task 9: Sammenstilling `bygg_oppskrift` + `lagre_oppskrift` + `main`

Bygg en oppskrift-dict fra JSON-LD (ren, testbar), skriv til de fire tabellene, og orkestrer hele kjøringen med `--limit`/`--delay`.

**Files:**
- Modify: `scripts/hent_godt.py`
- Modify: `scripts/test_hent_godt.py`

- [ ] **Step 1: Test `bygg_oppskrift` (ren transformasjon)**

Legg til i `scripts/test_hent_godt.py`:
```python
def test_bygg_oppskrift_fra_jsonld():
    ld = {
        "@type": "Recipe",
        "name": "Vafler",
        "description": "Gode vafler",
        "recipeYield": "4 porsjoner",
        "totalTime": "PT30M",
        "recipeCategory": "Dessert",
        "recipeIngredient": ["2 dl melk", "3 egg"],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Bland."},
            {"@type": "HowToStep", "text": "Stek."},
        ],
    }
    o = hent_godt.bygg_oppskrift(ld, "https://www.godt.no/oppskrifter/vafler/")
    assert o["navn"] == "Vafler"
    assert o["slug"] == "vafler"
    assert o["type"] == "Dessert"
    assert o["porsjoner"] == 4
    assert o["tid"] == "30 min"
    assert o["url"] == "https://www.godt.no/oppskrifter/vafler/"
    assert o["ingredienser"][0] == {"mengde": 2.0, "enhet": "dl", "navn": "melk", "raatekst": "2 dl melk", "sortering": 0}
    assert o["trinn"] == [{"nummer": 1, "tekst": "Bland."}, {"nummer": 2, "tekst": "Stek."}]

def test_bygg_oppskrift_instruksjoner_som_strenger():
    ld = {"@type": "Recipe", "name": "X", "recipeInstructions": ["Ett steg."]}
    o = hent_godt.bygg_oppskrift(ld, "https://www.godt.no/oppskrifter/x/")
    assert o["trinn"] == [{"nummer": 1, "tekst": "Ett steg."}]
```

- [ ] **Step 2: Kjør – forvent FAIL**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -k bygg_oppskrift -v`
Expected: de 2 nye feiler.

- [ ] **Step 3: Implementer `bygg_oppskrift`**

Legg til i `scripts/hent_godt.py` (legg `from datetime import datetime, timezone` til imports):
```python
from datetime import datetime, timezone


def _instruksjon_tekst(trinn):
    """recipeInstructions-element → tekst (HowToStep-dict eller ren streng)."""
    if isinstance(trinn, dict):
        return (trinn.get("text") or "").strip()
    return str(trinn).strip()


def _bilde_url_fra_ld(ld):
    """JSON-LD image kan være str, dict med url, eller liste. Returner første."""
    bilde = ld.get("image")
    if isinstance(bilde, list):
        bilde = bilde[0] if bilde else None
    if isinstance(bilde, dict):
        return bilde.get("url")
    return bilde


def bygg_oppskrift(ld, url):
    """schema.org/Recipe-dict → normalisert oppskrift-dict (uten å skrive DB).

    Ingredienser parses; rålinja beholdes i raatekst. Bilde-URL hentes ut men
    lastes ikke her (det gjør main via lagre_bilde)."""
    kat = ld.get("recipeCategory")
    if isinstance(kat, list):
        kat = kat[0] if kat else None

    ingredienser = []
    for i, linje in enumerate(ld.get("recipeIngredient", []) or []):
        mengde, enhet, navn = parse_ingrediens(str(linje))
        ingredienser.append({
            "mengde": mengde, "enhet": enhet, "navn": navn,
            "raatekst": str(linje), "sortering": i,
        })

    trinn = []
    raa_trinn = ld.get("recipeInstructions", []) or []
    if isinstance(raa_trinn, (str, dict)):
        raa_trinn = [raa_trinn]
    nr = 1
    for t in raa_trinn:
        tekst = _instruksjon_tekst(t)
        if tekst:
            trinn.append({"nummer": nr, "tekst": tekst})
            nr += 1

    return {
        "slug": lag_slug(url),
        "navn": (ld.get("name") or "").strip(),
        "type": map_type(kat),
        "beskrivelse": (ld.get("description") or "").strip() or None,
        "porsjoner": parse_yield(ld.get("recipeYield")),
        "tid": iso8601_til_min(ld.get("totalTime")) or iso8601_til_min(ld.get("cookTime")),
        "url": url,
        "hentet": datetime.now(timezone.utc).isoformat(),
        "bilde_url": _bilde_url_fra_ld(ld),
        "ingredienser": ingredienser,
        "trinn": trinn,
        "kategorier": [map_type(kat)] if kat else [],
    }
```

- [ ] **Step 4: Kjør – forvent PASS**

Run: `cd "<repo>/scripts" && python -m pytest test_hent_godt.py -v`
Expected: alle grønne (37 totalt).

- [ ] **Step 5: Implementer `_finn_db`, `lagre_oppskrift`, `main` (IO – ingen ny test)**

Legg til i `scripts/hent_godt.py` (legg `import sqlite3, argparse` til imports):
```python
import sqlite3
import argparse


def _finn_db():
    """Finn kanonisk kokt.db (samme mønster som hent_naering.py)."""
    d = os.path.dirname(os.path.abspath(__file__))
    for sti in [
        os.path.join(d, "..", "kokebok-app", "src-tauri", "data", "kokt.db"),
        os.path.join(d, "..", "kokebok-app", "src-tauri", "kokt.db"),
        os.path.join(d, "kokt.db"),
        os.path.join(os.getcwd(), "kokt.db"),
    ]:
        sti = os.path.normpath(sti)
        if os.path.exists(sti):
            return sti
    sys.exit("Fant ikke kokt.db")


def lagre_oppskrift(conn, o, bilde_rel):
    """Sett inn oppskrift + ingredienser + trinn + kategorier i én transaksjon."""
    cur = conn.execute(
        """INSERT INTO oppskrifter (slug, navn, type, beskrivelse, porsjoner, tid, bilde, url, hentet)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (o["slug"], o["navn"], o["type"], o["beskrivelse"], o["porsjoner"],
         o["tid"], bilde_rel, o["url"], o["hentet"]),
    )
    opp_id = cur.lastrowid
    for ing in o["ingredienser"]:
        conn.execute(
            """INSERT INTO ingredienser (oppskrift_id, gruppe, mengde, enhet, navn, raatekst, sortering)
               VALUES (?, NULL, ?, ?, ?, ?, ?)""",
            (opp_id, ing["mengde"], ing["enhet"], ing["navn"], ing["raatekst"], ing["sortering"]),
        )
    for tr in o["trinn"]:
        conn.execute(
            "INSERT INTO trinn (oppskrift_id, nummer, tekst) VALUES (?, ?, ?)",
            (opp_id, tr["nummer"], tr["tekst"]),
        )
    for kat in o["kategorier"]:
        conn.execute(
            "INSERT INTO kategorier (oppskrift_id, kategori) VALUES (?, ?)",
            (opp_id, kat),
        )


def main():
    ap = argparse.ArgumentParser(description="Skrap oppskrifter fra godt.no inn i kokt.db.")
    ap.add_argument("--limit", type=int, default=None, help="maks antall oppskrifter")
    ap.add_argument("--delay", type=float, default=0.25, help="sekunder mellom requests (0.25 ≈ 4 req/s)")
    args = ap.parse_args()

    db = _finn_db()
    conn = sqlite3.connect(db)
    print(f"DB: {db}")

    urls = finn_oppskrift_urls(delay=args.delay, grense=args.limit)
    print(f"Fant {len(urls)} oppskrift-URLer i sitemap.")

    nye = dupl = feil = 0
    for i, url in enumerate(urls, 1):
        if args.limit and nye >= args.limit:
            break
        if not robots_ok(url):
            print(f"  robots.txt blokkerer {url} – hopper over")
            continue
        html = hent(url, delay=args.delay)
        if not html:
            feil += 1
            continue
        ld = parse_jsonld(html.decode("utf-8", "replace"))
        if not ld or not (ld.get("name") or "").strip():
            print(f"  ingen JSON-LD Recipe på {url} – hopper over")
            feil += 1
            continue
        o = bygg_oppskrift(ld, url)
        if er_duplikat(conn, o["url"], o["navn"]):
            dupl += 1
            continue
        bilde_rel = lagre_bilde(o["bilde_url"], o["slug"], delay=args.delay)
        lagre_oppskrift(conn, o, bilde_rel)
        conn.commit()
        nye += 1
        if nye % 25 == 0:
            print(f"  …{nye} nye så langt")

    conn.close()
    print(f"Ferdig: {nye} nye, {dupl} duplikater, {feil} hoppet over (feil/ufullstendig).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Importer-sjekk + full testsuite**

Run:
```bash
cd "<repo>/scripts" && python -c "import hent_godt; print('import ok')" && python -m pytest test_hent_godt.py -v
```
Expected: `import ok`; alle 37 grønne.

- [ ] **Step 7: `--help` røyktest (ingen nettverk)**

Run: `cd "<repo>" && python scripts/hent_godt.py --help`
Expected: argparse-hjelp vises med `--limit` og `--delay`. (Ingen fetch, fordi --help avslutter før main-logikk.)

- [ ] **Step 8: Commit**

```bash
cd "<repo>" && git add scripts/hent_godt.py scripts/test_hent_godt.py
git commit -m "feat(godt): bygg_oppskrift + lagre_oppskrift + main (orkestrering)"
```

---

## Task 10: Dokumentasjon

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Utvid lisens-linja**

I `README.md`, i `## Lisens`-seksjonen, endre linja:
```
Privat bruk. Oppskriftsdata © matprat.no. Næringsdata © matvaretabellen.no.
```
til:
```
Privat bruk. Oppskriftsdata © matprat.no og © godt.no. Næringsdata © matvaretabellen.no.
```

- [ ] **Step 2: Legg til skraper-seksjon**

Finn ankerpunkt: `grep -n "## Data\|hent_naering\|hent_priser\|scrape\|## Bygg" README.md`. Legg til (tilpass overskriftsnivå til `##`):
```markdown
## Skrape godt.no (valgfritt, privat bruk)

`scripts/hent_godt.py` henter oppskrifter (med 600px-bilder) fra godt.no inn i
`kokt.db` som en andre datakilde. Sitemap-drevet, respekterer robots.txt for egen
user-agent, rate-limiter og cacher i `scripts/godt_cache/`.

```bash
# trygg første kjøring – 10 oppskrifter, sjekk resultatet i appen/DB:
python scripts/hent_godt.py --limit 10
# hele katalogen:
python scripts/hent_godt.py
```

Kjør på en egen git-branch og inspiser radtellingene før du committer (skriptet
endrer den sporede `kokt.db`). Etter skraping: kjør `hent_naering.py` og
`hent_priser.py` på nytt for å dekke de nye oppskriftene med næring/pris.
```

- [ ] **Step 3: Commit**

```bash
cd "<repo>" && git add README.md
git commit -m "docs(godt): dokumenter godt.no-skraper + attribusjon"
```

---

## Task 11: Manuell skraper-kjøring (krever bruker; live mot godt.no)

Dette steget kjøres av MENNESKET — det er den eneste delen som henter fra godt.no live.

**Files:** ingen (kjøring/verifikasjon).

- [ ] **Step 1: Trygg første kjøring på egen branch**

Run:
```bash
cd "<repo>" && python scripts/hent_godt.py --limit 10
```
Sjekk oppsummeringa: `Ferdig: N nye, M duplikater, K hoppet over`.

- [ ] **Step 2: Inspiser resultatet**

Run:
```bash
cd "<repo>" && .venv/Scripts/python.exe -c "
import sqlite3
db=sqlite3.connect('kokebok-app/src-tauri/data/kokt.db')
for r in db.execute(\"SELECT navn, type, porsjoner, tid, bilde FROM oppskrifter WHERE url LIKE '%godt.no%' LIMIT 10\"): print(r)
print('ingredienser-eksempel:')
for r in db.execute(\"SELECT i.raatekst, i.mengde, i.enhet, i.navn FROM ingredienser i JOIN oppskrifter o ON o.id=i.oppskrift_id WHERE o.url LIKE '%godt.no%' LIMIT 8\"): print(' ', r)
"
```
Sjekk at navn/type/porsjoner/tid ser riktige ut, at ingredienser er fornuftig parset, og at `bilder/{slug}.webp`-filene finnes.

- [ ] **Step 3: Kjør i appen**

Run: `cd "<repo>/kokebok-app" && npm run tauri dev`
Verifiser at godt.no-oppskriftene vises med bilde og korrekte felt.

- [ ] **Step 4: (når fornøyd) full kjøring + næring/pris**

```bash
cd "<repo>" && python scripts/hent_godt.py
python scripts/hent_naering.py
python scripts/hent_priser.py
```

- [ ] **Step 5: Commit datasettet (egen vurdering)**

Inspiser diff/størrelse på `kokt.db` og commit når du er fornøyd.

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** sitemap-oppdagelse (T7), JSON-LD-først+fallback (T3; HTML-
  fallback håndteres via `bygg_oppskrift` som tåler manglende felt + `or None`),
  ingrediensparser (T1), 600px WebP-bilder (T8), dedup URL+navn (T5), skriv til
  kokt.db (T9), robots/rate-limit/cache (T6), tester (T1–T5,T7,T9), README+
  attribusjon (T10), manuell kjøring (T11). Næring/pris eksplisitt utenfor scope
  (kjøres etterpå, T11 Step 4).
- **Agent-grense holdt:** ingen task ber implementereren hente fra godt.no live;
  alle nett-funksjoner testes mot lokale strenger/fixtures. Kun T11 (menneske)
  treffer live-siden.
- **Navn/typer konsistente:** `parse_ingrediens`→`(mengde,enhet,navn)` brukt likt
  i T1 og T9. `bygg_oppskrift`-dict-nøkler (`slug,navn,type,beskrivelse,porsjoner,
  tid,url,hentet,bilde_url,ingredienser,trinn,kategorier`) matcher `lagre_oppskrift`
  sin INSERT. `lag_slug`,`map_type`,`iso8601_til_min`,`parse_yield`,`er_duplikat`
  definert i T1–T5, brukt i T9. `hent(url,delay,bruk_cache)`-signatur lik i T6/T7/T8/T9.
- **Skjema verifisert mot ekte DB:** kolonner i alle fire INSERT-er (T9) stemmer
  med `PRAGMA table_info` (oppskrifter: slug,navn,type,beskrivelse,porsjoner,tid,
  bilde,url,hentet; ingredienser: oppskrift_id,gruppe,mengde,enhet,navn,raatekst,
  sortering; trinn: oppskrift_id,nummer,tekst; kategorier: oppskrift_id,kategori).
  `type`-vokabular (T4) hentet fra faktiske distinct-verdier. `tid`-format "N min"
  matcher matprat-rader.
- **TDD ekte her:** rene funksjoner (T1–T5,T7,T9 bygg_oppskrift) har failing-first
  pytest; IO-deler (T6,T8,T9 main) har importer-/røyk-sjekk + manuell T11.
