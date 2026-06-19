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

import difflib
import hashlib
import io
import json
import os
import re
import time
import urllib.request
import urllib.robotparser
import urllib.parse
import xml.etree.ElementTree as ET

from PIL import Image

import argparse
import sqlite3
from datetime import datetime, timezone

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


def parse_ingrediens(linje):
    """Rålinje → (mengde, enhet, navn). Best-effort; rålinja lagres separat.

    Tall kan være heltall, desimal (komma eller punktum), brøk-symbol (½) eller
    skråstrek-brøk (1/2). Enhet gjenkjennes bare hvis ordet rett etter tallet er
    en kjent norsk enhet; ellers regnes resten som navn (f.eks. "3 egg").
    """
    s = linje.strip()
    if not s:
        return (None, None, "")

    # Finn ledende mengde: range, brøksymbol, eller (heltall/desimal/skråstrek-brøk).
    mengde = None
    rest = s
    # Range «1 - 2 stk ...» / «1-2 stk ...»: bruk første tall (godt.no-mønster).
    m = re.match(r"^(\d+(?:[.,]\d+)?)\s*-\s*\d+(?:[.,]\d+)?\s+(.*)$", s)
    if m:
        mengde = float(m.group(1).replace(",", "."))
        rest = m.group(2)
    elif re.match(r"^(\d+)\s*([¼½¾⅓⅔⅛])\s*(.*)$", s):
        m = re.match(r"^(\d+)\s*([¼½¾⅓⅔⅛])\s*(.*)$", s)
        mengde = int(m.group(1)) + _BROK[m.group(2)]
        rest = m.group(3)
    elif re.match(r"^([¼½¾⅓⅔⅛])\s*(.*)$", s):
        m = re.match(r"^([¼½¾⅓⅔⅛])\s*(.*)$", s)
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


# Eksisterende type-vokabular i kokt.db (matprat-settet), lowercase → kanonisk
# skrivemåte. Brukes til å mappe godt.no-kategorier inn så filtrering i appen
# forblir konsistent.
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
    if n in _TYPE_KANONISK:
        return _TYPE_KANONISK[n]
    return kategori.strip()[:1].upper() + kategori.strip()[1:]


def lag_slug(url):
    """URL → siste sti-segment som slug."""
    return url.rstrip("/").rsplit("/", 1)[-1]


# Cache av eksisterende (lowercased) navn for uklar dedup. Lastes én gang per
# kjøring; nye innsettinger i samme kjøring fanges uansett av URL-dedup.
_NAVN_CACHE = {"liste": None}


def _last_navn_cache(conn):
    if _NAVN_CACHE["liste"] is None:
        _NAVN_CACHE["liste"] = [
            navn.strip().lower()
            for (navn,) in conn.execute(
                "SELECT navn FROM oppskrifter WHERE navn IS NOT NULL"
            )
        ]
    return _NAVN_CACHE["liste"]


def nullstill_navn_cache():
    """Tøm navn-cachen (brukes i tester / mellom kjøringer)."""
    _NAVN_CACHE["liste"] = None


def er_duplikat(conn, url, navn, slug=None):
    """True hvis url ELLER slug finnes fra før, eller navn uklart matcher (≥ 0.9)
    et eksisterende navn (fanger samme rett fra to kilder).

    Slug-sjekken er viktig: oppskrifter.slug har UNIQUE-constraint, så en
    slug-kollisjon (f.eks. «rabarbrasirup» fra både matprat og godt.no) er en
    ekte duplikat — ikke en feil. Uten denne sjekken krasjer INSERT-en og blir
    feilaktig talt som «hoppet over (feil)».

    Navnelista caches på modulnivå og lastes én gang per kjøring; nye rader i
    samme kjøring dedupes via URL/slug, ikke navn.
    """
    rad = conn.execute("SELECT 1 FROM oppskrifter WHERE url = ?", (url,)).fetchone()
    if rad:
        return True
    if slug:
        rad = conn.execute("SELECT 1 FROM oppskrifter WHERE slug = ?", (slug,)).fetchone()
        if rad:
            return True
    if not navn:
        return False
    n = navn.strip().lower()
    eksisterende = _last_navn_cache(conn)
    return bool(difflib.get_close_matches(n, eksisterende, n=1, cutoff=0.9))


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


_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def locs_fra_xml(xml_bytes):
    """Alle <loc>-tekster i en sitemap eller sitemap-index. Tom liste ved
    malformert XML (én dårlig sitemap skal ikke abortere hele kjøringen)."""
    try:
        rot = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  ADVARSEL: kunne ikke parse sitemap-XML: {e}")
        return []
    return [e.text.strip() for e in rot.iter(f"{_SM_NS}loc") if e.text]


# Ekte oppskrift-URL har et numerisk id-segment, f.eks.
# /oppskrifter/frokost/9780/frisk-og-tropisk-mango-smoothie. Kategori-/
# landingssider (/oppskrifter/frokost, /oppskrifter/dessert) mangler tallet.
_OPPSKRIFT_RE = re.compile(r"/oppskrifter/[^/]+/\d+/")


def er_oppskrift_url(u):
    """True hvis URL-en er en enkelt-oppskrift (har /<kategori>/<tall>/-segment),
    ikke en kategori-/landingsside."""
    return bool(_OPPSKRIFT_RE.search(u))


def urls_fra_sitemap(xml_bytes):
    """<loc>-URLer som peker på faktiske oppskrifter (ikke kategorisider)."""
    return [u for u in locs_fra_xml(xml_bytes) if er_oppskrift_url(u)]


def finn_oppskrift_urls(delay=0.25, grense=None):
    """Sitemap-index → recipe-sitemap(s) → liste av oppskrift-URLer.

    godt.no sin sitemap-index har egne under-sitemaps; oppskriftene ligger i
    sitemap-recipes.xml (de andre er static/kategorier, artikler, tags). Vi
    velger derfor sitemaps hvis navn inneholder «recipe» og henter bare dem.
    Faller tilbake til ALLE under-sitemaps hvis ingen «recipe»-sitemap finnes.
    URL-ene filtreres uansett på oppskrift-mønsteret (belte+bukseseler).
    """
    indeks = hent(BASIS + "/sitemap-index.xml", delay=delay)
    if not indeks:
        return []
    under = locs_fra_xml(indeks)
    recipe_sm = [s for s in under if "recipe" in s.lower()]
    valgte = recipe_sm or under
    funnet = []
    for sm_url in valgte:
        data = hent(sm_url, delay=delay)
        if not data:
            continue
        funnet.extend(urls_fra_sitemap(data))
        if grense and len(funnet) >= grense:
            break
    # Dedup behold rekkefølge.
    sett = list(dict.fromkeys(funnet))
    return sett[:grense] if grense else sett


BILDER_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "kokebok-app", "src-tauri", "data", "bilder",
    )
)
_BILDE_SIDE = 600
_BILDE_Q = 78


def _trygg_url(u):
    """URL-enkod sti/spørring slik at mellomrom og spesialtegn (æøå, –) ikke
    feiler i urllib. godt.no har bilde-URLer som «.../recipes/Mango smoothie»."""
    deler = urllib.parse.urlsplit(u)
    sti = urllib.parse.quote(deler.path, safe="/%")
    spm = urllib.parse.quote(deler.query, safe="=&%")
    return urllib.parse.urlunsplit((deler.scheme, deler.netloc, sti, spm, deler.fragment))


def lagre_bilde(bilde_url, slug, delay=0.25):
    """Last ned bilde → 600px WebP → bilder/{slug}.webp. Returner relativ sti
    ("bilder/{slug}.webp") eller None ved feil. Hopper over hvis fila finnes."""
    if not bilde_url:
        return None
    rel = f"bilder/{slug}.webp"
    mal = os.path.join(BILDER_DIR, f"{slug}.webp")
    if os.path.exists(mal):
        return rel
    data = hent(_trygg_url(bilde_url), delay=delay)
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
    # recipeCategory kan være liste (["frokost"]), komma-streng ("frokost, lunsj")
    # eller enkelt ("frokost"). Ta første kategori uansett form.
    kat = ld.get("recipeCategory")
    if isinstance(kat, list):
        kat = kat[0] if kat else None
    if isinstance(kat, str) and "," in kat:
        kat = kat.split(",")[0].strip()

    ingredienser = []
    raa_ingr = ld.get("recipeIngredient", []) or []
    if isinstance(raa_ingr, str):
        raa_ingr = [raa_ingr]
    for i, linje in enumerate(raa_ingr):
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
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (opp_id, "Ingredienser", ing["mengde"], ing["enhet"], ing["navn"],
             ing["raatekst"], ing["sortering"]),
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


def skrap_alle(conn, delay, grense):
    """Skrap oppskrifter fra sitemap inn i conn. Returnerer (nye, dupl, feil)."""
    urls = finn_oppskrift_urls(delay=delay, grense=grense)
    print(f"Fant {len(urls)} oppskrift-URLer i sitemap.")
    nye = dupl = feil = 0
    for url in urls:
        if grense and nye >= grense:
            break
        if not robots_ok(url):
            print(f"  robots.txt blokkerer {url} – hopper over")
            continue
        try:
            html = hent(url, delay=delay)
            if not html:
                feil += 1
                continue
            ld = parse_jsonld(html.decode("utf-8", "replace"))
            if not ld or not (ld.get("name") or "").strip():
                print(f"  ingen JSON-LD Recipe på {url} – hopper over")
                feil += 1
                continue
            o = bygg_oppskrift(ld, url)
            if er_duplikat(conn, o["url"], o["navn"], o["slug"]):
                dupl += 1
                continue
            bilde_rel = lagre_bilde(o["bilde_url"], o["slug"], delay=delay)
            lagre_oppskrift(conn, o, bilde_rel)
            conn.commit()
            nye += 1
            if nye % 25 == 0:
                print(f"  …{nye} nye så langt")
        except Exception as e:  # noqa: BLE001 – én dårlig oppskrift skal ikke abortere kjøringen
            conn.rollback()
            print(f"  FEIL ved {url}: {e}")
            feil += 1
    return nye, dupl, feil


def backfill_bilder(conn, delay):
    """Hent bilder for godt.no-rader som mangler bilde-fil (f.eks. fra en tidligere
    kjøring der bilde-URL-en feilet). Henter oppskriftssiden på nytt for å finne
    image-URL-en, laster bildet (med fikset URL-enkoding), og oppdaterer raden.
    Returnerer (fikset, fortsatt_uten)."""
    rader = conn.execute(
        "SELECT id, slug, url FROM oppskrifter "
        "WHERE url LIKE '%godt.no%' AND (bilde IS NULL OR bilde = '')"
    ).fetchall()
    print(f"Rader uten bilde: {len(rader)}")
    fikset = uten = 0
    for opp_id, slug, url in rader:
        try:
            html = hent(url, delay=delay)
            if not html:
                uten += 1
                continue
            ld = parse_jsonld(html.decode("utf-8", "replace"))
            bilde_url = _bilde_url_fra_ld(ld) if ld else None
            bilde_rel = lagre_bilde(bilde_url, slug, delay=delay)
            if bilde_rel:
                conn.execute("UPDATE oppskrifter SET bilde = ? WHERE id = ?", (bilde_rel, opp_id))
                conn.commit()
                fikset += 1
                print(f"  OK: {slug}")
            else:
                uten += 1
                print(f"  fortsatt uten bilde: {slug}")
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            print(f"  FEIL ved backfill {slug}: {e}")
            uten += 1
    return fikset, uten


def main():
    ap = argparse.ArgumentParser(description="Skrap oppskrifter fra godt.no inn i kokt.db.")
    ap.add_argument("--limit", type=int, default=None, help="maks antall oppskrifter")
    ap.add_argument("--delay", type=float, default=0.25, help="sekunder mellom requests (0.25 ≈ 4 req/s)")
    ap.add_argument("--backfill-bilder", action="store_true",
                    help="hent kun manglende bilder for eksisterende godt.no-rader")
    args = ap.parse_args()

    db = _finn_db()
    conn = sqlite3.connect(db)
    nullstill_navn_cache()  # frisk navn-cache for denne kjøringen
    print(f"DB: {db}")

    if args.backfill_bilder:
        fikset, uten = backfill_bilder(conn, args.delay)
        conn.close()
        print(f"Ferdig: {fikset} bilder fikset, {uten} fortsatt uten.")
        return

    nye, dupl, feil = skrap_alle(conn, args.delay, args.limit)
    conn.close()
    print(f"Ferdig: {nye} nye, {dupl} duplikater, {feil} hoppet over (feil/ufullstendig).")


if __name__ == "__main__":
    main()
