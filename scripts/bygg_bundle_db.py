#!/usr/bin/env python3
"""Bygg en distribuerbar kokt-bundle.db med bildene innebygd som BLOB.

Kopierer data/kokt.db -> data/kokt-bundle.db (rorer aldri git-kilden), legger
til kolonnen bilde_data BLOB pa oppskrifter, og fyller den fra bilder/{slug}.webp.
Kjor scripts/recompress_bilder.py forst hvis du vil ha 600px-bilder.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data"
KILDE = DATA / "kokt.db"
BUNDLE = DATA / "kokt-bundle.db"
BILDER = DATA / "bilder"


def main() -> None:
    if not KILDE.is_file():
        sys.exit(f"Fant ikke kilde-DB: {KILDE}")
    if BUNDLE.exists():
        BUNDLE.unlink()
    shutil.copy2(KILDE, BUNDLE)

    db = sqlite3.connect(BUNDLE)
    cols = [r[1] for r in db.execute("PRAGMA table_info(oppskrifter)")]
    if "bilde_data" not in cols:
        db.execute("ALTER TABLE oppskrifter ADD COLUMN bilde_data BLOB")

    rader = db.execute("SELECT id, slug FROM oppskrifter").fetchall()
    fylt = mangler = 0
    for opp_id, slug in rader:
        sti = BILDER / f"{slug}.webp"
        if not sti.is_file():
            mangler += 1
            print(f"  ADVARSEL: mangler bildefil for slug={slug!r}")
            continue
        db.execute(
            "UPDATE oppskrifter SET bilde_data = ? WHERE id = ?",
            (sqlite3.Binary(sti.read_bytes()), opp_id),
        )
        fylt += 1
    db.commit()

    uten = db.execute(
        "SELECT COUNT(*) FROM oppskrifter WHERE bilde_data IS NULL"
    ).fetchone()[0]
    db.close()

    storrelse_mb = BUNDLE.stat().st_size / 1024 / 1024
    print(f"Ferdig: {fylt} bilder innebygd, {mangler} manglet.")
    print(f"kokt-bundle.db: {storrelse_mb:.0f} MB, {uten} rader uten bilde_data.")
    if mangler or uten:
        sys.exit("FEIL: noen rader mangler bilde_data — sjekk advarsler over.")


if __name__ == "__main__":
    main()
