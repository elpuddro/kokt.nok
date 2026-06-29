"""
Oversett norsk DB-innhold til engelsk via DeepL.
Idempotent: hopper over rader der _en-kolonnen allerede er satt.
Bruk: python scripts/oversett_til_engelsk.py <sti-til-db>
"""
import deepl
import sqlite3
import sys
import time

BATCH_SIZE = 200


def legg_til_kolonner(conn: sqlite3.Connection) -> None:
    for sql in [
        "ALTER TABLE oppskrifter ADD COLUMN navn_en TEXT",
        "ALTER TABLE oppskrifter ADD COLUMN beskrivelse_en TEXT",
        "ALTER TABLE trinn ADD COLUMN tekst_en TEXT",
        "ALTER TABLE ingredienser ADD COLUMN navn_en TEXT",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.commit()


def oversett_batch(translator: deepl.Translator, tekster: list[str]) -> list[str]:
    results = translator.translate_text(
        tekster,
        source_lang="NB",
        target_lang="EN-US",
    )
    return [r.text for r in results]


def oversett_oppskrift_navn(conn: sqlite3.Connection, translator: deepl.Translator) -> None:
    rows = conn.execute(
        "SELECT id, navn FROM oppskrifter WHERE navn_en IS NULL AND navn IS NOT NULL"
    ).fetchall()
    print(f"Oversetter {len(rows)} oppskriftnavn...")
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i: i + BATCH_SIZE]
        ids = [r[0] for r in batch]
        tekster = [r[1] for r in batch]
        try:
            oversatte = oversett_batch(translator, tekster)
            for row_id, en in zip(ids, oversatte):
                conn.execute("UPDATE oppskrifter SET navn_en=? WHERE id=?", (en, row_id))
            conn.commit()
            print(f"  {min(i + BATCH_SIZE, len(rows))}/{len(rows)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e}")
    print("  Navn ferdig.")


def oversett_ingredienser(conn: sqlite3.Connection, translator: deepl.Translator) -> None:
    rows = conn.execute(
        """SELECT DISTINCT navn FROM ingredienser
           WHERE navn IS NOT NULL AND TRIM(navn) != '' AND navn_en IS NULL
           AND NOT (TRIM(navn) GLOB '[0-9]*' AND LENGTH(TRIM(navn)) <= 3)"""
    ).fetchall()
    navnliste = [r[0] for r in rows]
    print(f"Oversetter {len(navnliste)} unike ingrediensnavn...")
    for i in range(0, len(navnliste), BATCH_SIZE):
        batch = navnliste[i: i + BATCH_SIZE]
        try:
            oversatte = oversett_batch(translator, batch)
            for nb, en in zip(batch, oversatte):
                conn.execute(
                    "UPDATE ingredienser SET navn_en=? WHERE navn=? AND navn_en IS NULL",
                    (en, nb),
                )
            conn.commit()
            print(f"  {min(i + BATCH_SIZE, len(navnliste))}/{len(navnliste)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e}")
    print("  Ingredienser ferdig.")


def vis_bruk(translator: deepl.Translator) -> None:
    usage = translator.get_usage()
    if usage.character.limit:
        pct = usage.character.count / usage.character.limit * 100
        print(f"DeepL-forbruk: {usage.character.count:,} / {usage.character.limit:,} tegn ({pct:.1f}%)")
    else:
        print(f"DeepL-forbruk: {usage.character.count:,} tegn")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Bruk: python scripts/oversett_til_engelsk.py <sti-til-db>")
        sys.exit(1)
    db_path = sys.argv[1]
    import os
    auth_key = os.environ.get("DEEPL_AUTH_KEY")
    if not auth_key:
        print("Feil: sett DEEPL_AUTH_KEY i miljøet før du kjører scriptet.")
        sys.exit(1)
    print(f"Åpner DB: {db_path}")
    translator = deepl.Translator(auth_key)
    vis_bruk(translator)

    conn = sqlite3.connect(db_path)
    legg_til_kolonner(conn)
    oversett_oppskrift_navn(conn, translator)
    oversett_ingredienser(conn, translator)
    conn.close()

    vis_bruk(translator)
    print("Ferdig!")
