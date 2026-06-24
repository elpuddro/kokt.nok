#!/usr/bin/env python3
"""Importer høytid-tagging fra data/hoytid_forslag.json til kokt.db.

Kjør fra repo-roten etter å ha kurert hoytid_forslag.json:
  python scripts/importer_hoytid.py

Idempotent: trygt å kjøre flere ganger.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
DB = ROT / "kokebok-app" / "src-tauri" / "data" / "kokt.db"
FORSLAG = ROT / "data" / "hoytid_forslag.json"


def main() -> None:
    if not DB.is_file():
        sys.exit(f"Fant ikke DB: {DB}")
    if not FORSLAG.is_file():
        sys.exit(f"Fant ikke forslag-fil: {FORSLAG}\n  → Kjør scripts/tagg_hoytid.py først")

    forslag: dict[str, list[str]] = json.loads(FORSLAG.read_text(encoding="utf-8"))

    conn = sqlite3.connect(DB)

    eksist = [r[1] for r in conn.execute("PRAGMA table_info(oppskrifter)")]
    if "hoytid" not in eksist:
        conn.execute("ALTER TABLE oppskrifter ADD COLUMN hoytid TEXT")

    conn.execute("UPDATE oppskrifter SET hoytid = NULL")
    oppdatert = 0
    for id_str, hoytider in forslag.items():
        if hoytider:
            verdi = ",".join(sorted(hoytider))
            conn.execute(
                "UPDATE oppskrifter SET hoytid = ? WHERE id = ?",
                (verdi, int(id_str)),
            )
            oppdatert += 1

    conn.commit()
    conn.close()
    print(f"Ferdig: {oppdatert} oppskrifter tagget i kokt.db.")


if __name__ == "__main__":
    main()
