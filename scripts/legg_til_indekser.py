#!/usr/bin/env python3
"""Legg til manglende indekser i kokt.db.

Kjøres én gang (eller etter ny DB-generering). Idempotent: bruker
CREATE INDEX IF NOT EXISTS, så det er trygt å kjøre på nytt.
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data" / "kokt.db"


def main() -> None:
    if not DB.is_file():
        sys.exit(f"Fant ikke: {DB}")

    conn = sqlite3.connect(DB)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_kat_kategori "
        "ON kategorier(kategori)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_opp_hoytid "
        "ON oppskrifter(hoytid) WHERE hoytid IS NOT NULL"
    )
    conn.commit()
    conn.close()
    print("Indekser lagt til (eller fantes allerede).")


if __name__ == "__main__":
    main()
