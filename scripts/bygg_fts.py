#!/usr/bin/env python3
"""Bygg FTS5 trigram-søketabell i kokt.db.

Bygger tabellen oppskrift_fts (contentless FTS5, trigram tokenizer).
Hvert oppskrift-row: navn + ingrediensnavn konkatenert til én søketekst.
Må kjøres på nytt etter ny DB-generering (ny scrape, ny tagging).
"""
import sqlite3
import sys
import time
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data" / "kokt.db"


def main() -> None:
    if not DB.is_file():
        sys.exit(f"Fant ikke: {DB}")

    conn = sqlite3.connect(DB)

    # Sjekk FTS5 tilgjengelighet
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts5_probe")
    except sqlite3.OperationalError as e:
        sys.exit(f"FTS5 ikke tilgjengelig i denne SQLite-build: {e}")

    t0 = time.perf_counter()

    conn.execute("DROP TABLE IF EXISTS oppskrift_fts")
    conn.execute(
        "CREATE VIRTUAL TABLE oppskrift_fts "
        "USING fts5(sok_tekst, content='', tokenize='trigram case_sensitive 0')"
    )

    # Bygg kombinert søketekst: oppskriftnavn + alle ingrediensnavn
    conn.execute(
        """
        INSERT INTO oppskrift_fts(rowid, sok_tekst)
        SELECT o.id,
               o.navn || ' ' || COALESCE(GROUP_CONCAT(i.navn, ' '), '')
        FROM   oppskrifter o
        LEFT   JOIN ingredienser i ON i.oppskrift_id = o.id
        GROUP  BY o.id
        """
    )
    conn.commit()

    elapsed = time.perf_counter() - t0
    conn.execute("SELECT COUNT(*) FROM oppskrift_fts")  # trigger FTS segment merge
    count = conn.execute("SELECT COUNT(*) FROM oppskrifter").fetchone()[0]
    conn.close()

    print(f"FTS5 bygget: {count} oppskrifter indeksert på {elapsed*1000:.0f}ms")
    print("Trigram tokenizer med case_sensitive=0 — fanger delstrenger og 1–2 bokstavs-avvik via OR-trigram i Rust.")


if __name__ == "__main__":
    main()
