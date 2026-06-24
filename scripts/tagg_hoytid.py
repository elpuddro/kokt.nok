#!/usr/bin/env python3
"""Tagg oppskrifter med høytid-nøkler via nøkkelordregler.

Kjør fra repo-roten: python scripts/tagg_hoytid.py
Skriver data/hoytid_forslag.json (merger med eksisterende manuell kurasjon).
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
DB = ROT / "kokebok-app" / "src-tauri" / "data" / "kokt.db"
FORSLAG = ROT / "data" / "hoytid_forslag.json"

REGLER: dict[str, list[str]] = {
    "jul": [
        "pinnekjøtt", "pinnekjott", "ribbe", "juleskinke", "lutefisk", "rakfisk",
        "pepperkake", "julekake", "multekrem", "riskrem", "risgrøt",
        "gløgg", "julemat", "julen", "advent",
    ],
    "paske": [
        "påskelam", "påske", "lammestek", "påskeegg", "appelsinkake",
    ],
    "mai17": [
        "bløtkake", "nasjonaldag", "bunad",
    ],
    "sankthans": [
        "sankthans", "midsommer",
    ],
    "farikaal": [
        "fårikål", "får i kål", "lam og kål",
    ],
    "halloween": [
        "gresskar", "pumpkin", "halloween",
    ],
    "valentins": [
        "valentins", "tiramisu", "fondant",
    ],
}

# Nøkkelord som krever ordgrense (korte ord som gir falske positive som delstreng)
ORDGRENSE: dict[str, list[str]] = {
    "paske":     ["lam"],
    "mai17":     ["pølse"],
    "sankthans": ["jordbær", "rømme", "rømmegrøt", "grillmat", "spekemat", "bål"],
    "valentins": ["sjokolade", "champagne", "hjerte", "romantisk", "bær"],
}


def tagg_hoytid(navn: str, ingredienser: str) -> set[str]:
    """Returner sett av høytidsnøkler som matcher navn+ingredienser."""
    tekst = (navn + " " + ingredienser).lower()
    treff: set[str] = set()
    for hoytid, ord_liste in REGLER.items():
        for ord in ord_liste:
            if ord in tekst:
                treff.add(hoytid)
                break
    for hoytid, ord_liste in ORDGRENSE.items():
        for ord in ord_liste:
            if re.search(rf"\b{re.escape(ord)}\b", tekst):
                # lam i fårikål-kontekst er høstmat, ikke påskemat
                if hoytid == "paske" and ord == "lam" and "farikaal" in treff:
                    continue
                treff.add(hoytid)
                break
    return treff


def main() -> None:
    if not DB.is_file():
        sys.exit(f"Fant ikke DB: {DB}")

    conn = sqlite3.connect(DB)
    rader = conn.execute(
        "SELECT o.id, o.navn, GROUP_CONCAT(i.navn, ', ') "
        "FROM oppskrifter o "
        "LEFT JOIN ingredienser i ON i.oppskrift_id = o.id "
        "GROUP BY o.id"
    ).fetchall()
    conn.close()

    # Last eksisterende manuell kurasjon (merge)
    eksisterende: dict[str, list[str]] = {}
    if FORSLAG.is_file():
        eksisterende = json.loads(FORSLAG.read_text(encoding="utf-8"))

    resultat: dict[str, list[str]] = dict(eksisterende)
    for opp_id, navn, ing_tekst in rader:
        hoytider = tagg_hoytid(navn or "", ing_tekst or "")
        if hoytider:
            nokkel = str(opp_id)
            gamle = set(eksisterende.get(nokkel, []))
            resultat[nokkel] = sorted(gamle | hoytider)

    FORSLAG.parent.mkdir(exist_ok=True)
    FORSLAG.write_text(
        json.dumps(resultat, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    teller: dict[str, int] = {}
    for hoytider in resultat.values():
        for h in hoytider:
            teller[h] = teller.get(h, 0) + 1
    print(f"Ferdig: {len(resultat)} oppskrifter tagget.")
    for h, n in sorted(teller.items()):
        print(f"  {h}: {n}")
    print(f"Lagret: {FORSLAG}")


if __name__ == "__main__":
    main()
