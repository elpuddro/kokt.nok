"""
Oversett norsk DB-innhold til engelsk via Claude Haiku.
Idempotent: hopper over rader der navn_en allerede er satt.
Bruk: python scripts/oversett_til_engelsk.py <sti-til-db>
"""
import anthropic
import sqlite3
import json
import sys
import time

MODEL = "claude-haiku-4-5-20251001"
client = anthropic.Anthropic()  # leser ANTHROPIC_API_KEY fra env


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
            pass  # kolonnen finnes allerede
    conn.commit()


def oversett_batch_liste(items: list[dict], felt: list[str]) -> list[dict]:
    felt_str = ", ".join(felt)
    prompt = f"""Translate the following Norwegian recipe texts to English.
Return a JSON array with exactly {len(items)} elements. Each element is an object with keys: {felt_str}.
Rules:
- Preserve cooking terminology and measurements exactly
- Keep brand names, proper nouns, and Norwegian dish names unchanged
- Keep the same order as the input
- Return ONLY valid JSON, no explanation, no markdown

Input:
{json.dumps(items, ensure_ascii=False)}"""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    # Fjern eventuell markdown-innpakning
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def oversett_oppskrifter(conn: sqlite3.Connection, batch_size: int = 50) -> None:
    rows = conn.execute(
        "SELECT id, navn, beskrivelse FROM oppskrifter WHERE navn_en IS NULL"
    ).fetchall()
    print(f"Oversetter {len(rows)} oppskrifter (batch={batch_size})...")
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        items = [
            {"id": r[0], "navn": r[1] or "", "beskrivelse": r[2] or ""}
            for r in batch
        ]
        try:
            results = oversett_batch_liste(items, ["navn_en", "beskrivelse_en"])
            for j, res in enumerate(results):
                conn.execute(
                    "UPDATE oppskrifter SET navn_en=?, beskrivelse_en=? WHERE id=?",
                    (res.get("navn_en"), res.get("beskrivelse_en"), items[j]["id"]),
                )
            conn.commit()
            print(f"  {min(i + batch_size, len(rows))}/{len(rows)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e} — hopper over")
        time.sleep(0.5)


def oversett_trinn(conn: sqlite3.Connection, batch_size: int = 150) -> None:
    rows = conn.execute(
        "SELECT id, tekst FROM trinn WHERE tekst_en IS NULL AND tekst IS NOT NULL"
    ).fetchall()
    print(f"Oversetter {len(rows)} trinn (batch={batch_size})...")
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        items = [{"id": r[0], "tekst": r[1]} for r in batch]
        try:
            results = oversett_batch_liste(items, ["tekst_en"])
            for j, res in enumerate(results):
                conn.execute(
                    "UPDATE trinn SET tekst_en=? WHERE id=?",
                    (res.get("tekst_en"), items[j]["id"]),
                )
            conn.commit()
            print(f"  {min(i + batch_size, len(rows))}/{len(rows)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e} — hopper over")
        time.sleep(0.5)


def oversett_ingredienser(conn: sqlite3.Connection, batch_size: int = 300) -> None:
    rows = conn.execute(
        "SELECT DISTINCT navn FROM ingredienser WHERE navn IS NOT NULL AND navn_en IS NULL"
    ).fetchall()
    navnliste = [r[0] for r in rows]
    print(f"Oversetter {len(navnliste)} unike ingrediensnavn (batch={batch_size})...")
    for i in range(0, len(navnliste), batch_size):
        batch = navnliste[i : i + batch_size]
        prompt = f"""Translate these Norwegian ingredient names to English.
Return a JSON object mapping each Norwegian name (key) to its English translation (value).
Rules:
- Keep scientific names, brand names, and international terms unchanged
- For compound ingredients, translate the description (e.g. "rød paprika" → "red bell pepper")
- Return ONLY valid JSON object, no explanation

Input: {json.dumps(batch, ensure_ascii=False)}"""
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            mapping: dict[str, str] = json.loads(text)
            for nb_navn, en_navn in mapping.items():
                conn.execute(
                    "UPDATE ingredienser SET navn_en=? WHERE navn=? AND navn_en IS NULL",
                    (en_navn, nb_navn),
                )
            conn.commit()
            print(f"  {min(i + batch_size, len(navnliste))}/{len(navnliste)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e} — hopper over")
        time.sleep(0.5)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Bruk: python scripts/oversett_til_engelsk.py <sti-til-db>")
        sys.exit(1)
    db_path = sys.argv[1]
    print(f"Åpner DB: {db_path}")
    conn = sqlite3.connect(db_path)
    legg_til_kolonner(conn)
    oversett_oppskrifter(conn)
    oversett_trinn(conn)
    oversett_ingredienser(conn)
    conn.close()
    print("Ferdig!")
