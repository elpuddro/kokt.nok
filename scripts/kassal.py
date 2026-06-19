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

# Ingrediens-enhet → (enhetsklasse, multiplikator til basis g/ml/stk).
# ss/ts defaulter til g-klassen (15 g / 5 g). klype/never er små g-anslag.
_ING_BASIS = {
    "g": ("g", 1.0), "kg": ("g", 1000.0), "hg": ("g", 100.0),
    "ss": ("g", 15.0), "ts": ("g", 5.0), "klype": ("g", 1.0), "never": ("g", 5.0),
    "dl": ("ml", 100.0), "l": ("ml", 1000.0), "cl": ("ml", 10.0), "ml": ("ml", 1.0),
    "stk.": ("stk", 1.0), "stk": ("stk", 1.0), "": ("stk", 1.0),
}


def hodeord(ingrediens_navn):
    """Første meningsbærende ord i ingrediensnavnet, etter prefiks-strip.
    Bare rene bokstav-tokens ([a-zæøå]+) tas med; ord med sifre eller
    tegnsetting (f.eks. '(pynt)', '1/2') droppes. Returnerer None hvis
    ingen kandidat gjenstår eller første ord er < 3 tegn."""
    ord_liste = [w for w in re.split(r"[\s,]+", ingrediens_navn.lower())
                 if w and w not in STRIP and _TOKEN_RE.fullmatch(w)]
    if not ord_liste:
        return None
    h = ord_liste[0]
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
        if klasse != mal_klasse or mengde <= 0:  # mengde<=0 verner mot 0-divisjon
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


def ingrediens_basis(mengde, enhet):
    """(enhetsklasse, mengde_i_basis) for en ingrediens-enhet, eller None
    hvis enheten ikke kan konverteres (boks, bunt, glass, pose, ...)."""
    e = (enhet or "").strip().lower()
    if e not in _ING_BASIS:
        return None
    klasse, mult = _ING_BASIS[e]
    return (klasse, mengde * mult)
