#!/usr/bin/env python3
"""Klassifiser ingredienser til kosthold/allergi-tagger via kuraterte
nøkkelord-regler, og fyll tabellen ingrediens_tagg i kokt.db.

Reglene er bevisst kuraterte og testbare (ikke LLM) fordi halal-korrekthet
krever at de er reviderbare og reproduserbare. Matcher mot ingrediensnavn OG
råtekst (svin gjemmer seg i fritekst som «bacon i terninger»).
"""
import os
import re
import sqlite3
import sys

# To matchestrategier mot normalisert (lowercase) tekst, valgt etter TVETYDIGHET
# (ikke etter posisjon — norske røtter står som prefiks «kyllingfilet», suffiks
# «fårikålkjøtt»/«gravlaks» OG alene «lam»):
#
#   DELSTRENG  – ren delstreng (ord-i-ord). STANDARD for lange, ENTYDIGE røtter
#                (kjøtt, kylling, laks, gelatin …). Fanger alle tre posisjonene.
#                Kjente kollisjoner håndteres i UNNTAK (flaksalt, fruktkjøtt).
#   ORDGRENSE  – full \bord\b. KUN korte, kollisjonsutsatte røtter der delstreng
#                ville gi mange false positives: «and» (andre), «vin» (vineddik),
#                «lam» (flamme/lampe/reklame), «sei» (seig), «egg» (eggplante),
#                «rom»/«øl». Disse får ekstra unntak under.
ORDGRENSE = {
    "alkohol": ["vin", "øl", "rom", "rødvin", "hvitvin", "cognac", "konjakk",
                "likør", "sherry", "marsala", "mirin", "akevitt"],
    "egg":     ["egg", "eggeplomme", "eggehvite", "majones"],
    "honning": ["honning"],    # full grense: ikke «honningmelon» (frukt)
    "kjott_streng": ["and"],   # «and» (fugl) vs «andre»; pseudo-tagg → kjott
}
# PREFIKS – ledende grense \bord (ingen avsluttende). For røtter som er
# sammensetnings-prefiks men IKKE delstreng-trygge: «lam» treffer «lammelår»/
# «lammekjøtt»/«lam», men IKKE «flamme/reklame/islam» (de starter ikke med lam).
PREFIKS = {
    # «lam» → lammelår (ikke flamme/islam); «elg/hjort/rein» → elgstek/hjortestek
    # (ikke «velg»/«hjortetakk»/«reint» — se UNNTAK).
    "kjott": ["lam", "elg", "hjort", "rein", "nyretapp"],
    # «sei» → seifilet (ikke «seig»); «uer» → uerfilet (ikke «druer»);
    # «sik» → sik/sikfilet (ikke «solsikke»/«apsikat»).
    "fisk":  ["sei", "uer", "sik"],
}
DELSTRENG = {
    "blod":    ["blod"],   # blodpudding/blodklubb (unntak: blodappelsin = frukt)
    "kjott":   ["kjøtt", "kylling", "storfe", "biff", "kalv", "okse", "ande",
                "kalkun", "vilt", "reinsdyr", "spekemat",
                "kjøttdeig", "pinnekjøtt", "fårikål", "fåre", "fenalår",
                "kjekjøtt", "culotte", "karbonade", "høns", "gås",
                "smalahove", "reinhjerne",
                # Kjøttkutt som aldri er fisk i datasettet (fisk = laksefilet
                # osv.). Trygge som delstreng → fanger «biff av indrefilet».
                "indrefilet", "ytrefilet", "mørbrad", "entrecote", "entrecôte",
                # Kutt/retter funnet i full residual-audit (kjøtt, ikke fisk).
                "flintstek", "brisket", "bibringe", "høyrygg", "rypebryst",
                "tafelspiss", "roastbeef"],
    "fisk":    ["fisk", "laks", "ørret", "torsk", "makrell", "tunfisk", "reke",
                "skalldyr", "blåskjell", "krabbe", "sild", "ansjos", "sardin",
                "scampi", "scampin", "kaviar", "østers", "blekksprut",
                "kamskjell", "hummer", "sjøkreps",
                # Vanlige norske matfisk (funnet i full residual-audit).
                "steinbit", "kveite", "hyse", "kolje", "brosme", "breiflabb",
                "rødspette", "sjøtunge", "abbor", "gjedde",
                # Runde 2 av audit (e2e i «Annet»-kategorien).
                "skrei", "flyndre", "kreps", "hummer", "sjøtunge", "lutefisk"],
    # Kun UTVETYDIG svin. «ribbe/kotelett» er IKKE her: de finnes også som
    # lammeribbe/lammekotelett — å tagge dem svin ville feilaktig skjult lam fra
    # halal (lam er tillatt). Svine-varianter fanges av «svin»-delstrengen.
    # «ribbe» er svin i norsk data (ingen lamme-/storferibbe funnet). svin⊆kjøtt.
    "svin":    ["svin", "bacon", "skinke", "spekeskinke", "serrano",
                "prosciutto", "chorizo", "pancetta", "salami", "pepperoni",
                "leverpostei", "ister", "flesk", "sideflesk", "tynnribbe",
                "ribbe", "nakkekotelett", "nakkekam", "pulled pork", "nduja",
                "pigwings", "smågris", "spareribs",
                # pigwings/smågris/spareribs — også halal-relevant
                # Brukervalg: uspesifisert «pølse»/«korv» regnes som svin
                # (konservativt for halal). Kylling-/lamme-/vegetarpølse får
                # unntak (UNNTAK + plantebasert-strip) så de ikke blir svin.
                "pølse", "korv"],
    "gelatin": ["gelatin", "husblas"],
    "melk":    ["melk", "fløte", "kremfløte", "smør", "ost", "parmesan",
                "yoghurt", "rømme", "crème fraîche", "kesam", "cottage"],
    "gluten":  ["hvetemel", "hvete", "bygg", "rug", "semulegryn", "couscous",
                "brød", "pasta", "soyasaus", "ølgjær"],
    "nott":    ["mandel", "hasselnøtt", "valnøtt", "peanøtt", "cashew",
                "pistasj", "pekan", "paranøtt", "nøtt"],
}

# Eksplisitte regler/unntak (false-positive-feller fra spec + funnet i data).
# (frase_som_må_finnes_i_tekst, tagg) — legges til hvis frasen finnes.
EKSTRA = [
    ("vaniljeekstrakt", "alkohol"),   # inneholder alkohol
    ("worcestershire",  "fisk"),      # inneholder ansjos
    ("løpe",            "gelatin"),   # animalsk løpe (tvilsom → tatt med)
    ("rennet",          "gelatin"),
]
# (frase, tagg) som SKAL FJERNES selv om en regel over slo til (unntak).
UNNTAK = [
    ("vineddik",     "alkohol"),   # eddik, ikke alkohol
    ("vindrue",      "alkohol"),
    ("druer",        "alkohol"),
    ("rømme",        "alkohol"),   # «rom» traff ikke pga \b, men sikre uansett
    ("romtemp",      "alkohol"),
    ("aromat",       "alkohol"),
    ("eggplante",    "egg"),       # aubergine
    ("aubergine",    "egg"),
    ("blodappelsin", "blod"),      # frukt, ikke blod
    ("blodgrapefrukt", "blod"),
    ("flaksalt",     "fisk"),      # «laks»-delstreng treffer flaksalt (flak-salt)
    ("seig",         "fisk"),      # «sei»-prefiks treffer «seig/seige» (= seig)
    ("seide",        "fisk"),
    ("smørflyndre",  "melk"),      # «smør»-delstreng: smørflyndre = fisk, ikke smør
    ("fruktkjøtt",   "kjott"),     # fruktkjøtt = fruktmasse, ikke kjøtt
    ("lammeribbe",   "svin"),      # lammeribbe = lam (halal-ok), ikke svin
    ("fårelår",      "svin"),      # sikring: fåre-kutt er ikke svin
    # Ikke-svin pølser: «pølse»→svin (brukervalg), men disse er ikke svin.
    # Forblir kjøtt (kylling/lam/kalkun fanges av egne kjøtt-regler).
    ("lammepølse",   "svin"),
    ("kyllingpølse", "svin"),
    ("kalkunpølse",  "svin"),
    ("hjortetakk",   "kjott"),     # hjortetakksalt = bakepulver, ikke hjort
    ("reint",        "kjott"),     # «rein»-prefiks: «reint/reine» (= ren)
    ("reine",        "kjott"),
    # Plantemelk/-fløte: «melk»/«fløte» som delstreng treffer disse, men de er
    # nettopp det laktosefri/vegansk-brukere VIL ha. Strip melk-taggen.
    # (mandelmelk beholder nott — UNNTAK fjerner kun melk.)
    ("kokosmelk",    "melk"),
    ("kokosfløte",   "melk"),
    ("mandelmelk",   "melk"),
    ("havremelk",    "melk"),
    ("havrefløte",   "melk"),
    ("soyamelk",     "melk"),
    ("sojamelk",     "melk"),
    ("rismelk",      "melk"),
    ("cashewmelk",   "melk"),
    # «ost»-delstreng treffer most-familien (eplemost, hvitløk most, finmoste) —
    # juice/mosing, ikke ost. kremost/brunost rammes ikke (ingen av disse fraser).
    # NB: ikke bruk «most » med etterfølgende mellomrom — det treffer «kremost »!
    # Bruk ledende mellomrom (« most») så bare standalone-ordet rammes.
    ("eplemost",     "melk"),
    (" most",        "melk"),      # « most» (hvitløk most, banan most, most avokado→nei)
    ("finmoste",     "melk"),
    ("pastafarge",   "gluten"),    # konditorfarge, ikke pasta
    ("mandel",       "kjott"),     # «and» i mandel (ekstra sikring)
    ("koriander",    "kjott"),
    ("peanøttsmør",  "melk"),      # smør → melk, men dette er nøtt
    ("kakaosmør",    "melk"),      # ikke melk
    ("peanøttsmør",  "kjott"),
]


def _norm(s: str) -> str:
    return (s or "").lower().strip()


def tagg_for_tekst(navn: str, raatekst: str = "") -> set:
    """Returner settet av tagger for en ingrediens, basert på navn + råtekst."""
    tekst = _norm(navn) + " " + _norm(raatekst)
    tagger = set()

    # ORDGRENSE: full \bord\b. Pseudo-tagger «*_streng» mappes til ekte tagg
    # (egne fordi de kollisjonsutsatte ordene må ha full grense).
    PSEUDO = {"kjott_streng": "kjott", "fisk_streng": "fisk"}
    for tagg, ord_liste in ORDGRENSE.items():
        ekte = PSEUDO.get(tagg, tagg)
        for o in ord_liste:
            if re.search(r"\b" + re.escape(o) + r"\b", tekst):
                tagger.add(ekte)
                break

    # PREFIKS: ledende \bord (fanger «lammelår», ikke «flamme»).
    for tagg, ord_liste in PREFIKS.items():
        for o in ord_liste:
            if re.search(r"\b" + re.escape(o), tekst):
                tagger.add(tagg)
                break

    for tagg, ord_liste in DELSTRENG.items():
        for o in ord_liste:
            if o in tekst:
                tagger.add(tagg)
                break

    for frase, tagg in EKSTRA:
        if frase in tekst:
            tagger.add(tagg)

    for frase, tagg in UNNTAK:
        if frase in tekst:
            tagger.discard(tagg)

    # Plantebasert erstatning: «vegetarpølse», «soyakjøttdeig», «kjøttfri X»,
    # «quorn» osv. skal IKKE telle som kjøtt/fisk/svin (det er hele poenget).
    # Strukturell strip → fanger hele klassen, ikke ord-for-ord.
    if any(m in tekst for m in ("vegetar", "vegan", "soya", "soja", "plantebasert",
                                "kjøttfri", "kjøtterstatning", "quorn", "tofu")):
        for animalsk in ("kjott", "fisk", "svin"):
            tagger.discard(animalsk)

    # Implikasjon: alt svin er også kjøtt (salami/skinke/bacon skal skjules av
    # vegetar/vegansk, ikke bare halal). Settes etter UNNTAK/veggie-strip.
    if "svin" in tagger:
        tagger.add("kjott")

    return tagger


def _finn_db() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kandidater = [
        os.path.join(script_dir, "..", "kokebok-app", "src-tauri", "data", "kokt.db"),
        os.path.join(script_dir, "kokt.db"),
        os.path.join(os.getcwd(), "kokt.db"),
    ]
    for sti in kandidater:
        sti = os.path.normpath(sti)
        if os.path.exists(sti):
            return sti
    locs = "\n  ".join(os.path.normpath(k) for k in kandidater)
    sys.exit(f"Fant ikke kokt.db. Lette her:\n  {locs}")


SCHEMA = """
CREATE TABLE IF NOT EXISTS ingrediens_tagg (
    navn TEXT NOT NULL,
    tagg TEXT NOT NULL,
    PRIMARY KEY (navn, tagg)
);
CREATE INDEX IF NOT EXISTS idx_tagg_navn ON ingrediens_tagg(navn);
-- Avgjørende for ytelse: NOT EXISTS-diettfilteret korrelerer på
-- ingredienser.oppskrift_id og joiner på navn. Uten denne indeksen gjør hver
-- av 5962 oppskrifter et fullt scan av 67050 ingrediens-rader (~35 s henger).
-- Sammensatt (oppskrift_id, navn) = dekkende: seek på id + les navn fra indeks.
CREATE INDEX IF NOT EXISTS idx_ing_opp_navn ON ingredienser(oppskrift_id, navn);
"""


def main() -> None:
    # Windows-konsollen er ofte cp1252; tving UTF-8 så utskrift med → / Æ/Ø/Å
    # ikke krasjer. (reconfigure finnes på Python 3.7+.)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    db_sti = _finn_db()
    db = sqlite3.connect(db_sti)
    db.executescript(SCHEMA)
    db.execute("DELETE FROM ingrediens_tagg")  # idempotent: rebygg rent

    # Hent distinkte navn + ALL råtekst per navn (GROUP_CONCAT slår sammen alle
    # forekomster, så «bacon i terninger»-treff i én forekomst teller).
    rader = db.execute(
        "SELECT navn, GROUP_CONCAT(raatekst, ' ') FROM ingredienser "
        "WHERE navn IS NOT NULL AND navn != '' GROUP BY navn"
    ).fetchall()

    antall = 0
    for navn, raatekst in rader:
        # VIKTIG: lagre navnet RÅTT (eksakt som i ingredienser.navn). Joinen i
        # Rust er en eksakt streng-likhet på samme kolonne, så vi unngår at
        # SQLite LOWER() (kun ASCII) og Python .lower() (Æ/Ø/Å) er uenige.
        for tagg in tagg_for_tekst(navn, raatekst or ""):
            db.execute(
                "INSERT OR IGNORE INTO ingrediens_tagg (navn, tagg) VALUES (?, ?)",
                (navn, tagg),
            )
            antall += 1
    db.commit()

    print(f"Klassifiserte {len(rader)} distinkte ingrediensnavn → {antall} tagg-rader.")
    for tagg, c in db.execute(
        "SELECT tagg, COUNT(*) c FROM ingrediens_tagg GROUP BY tagg ORDER BY c DESC"
    ):
        print(f"  {c:5}  {tagg}")
    db.close()


if __name__ == "__main__":
    main()
