# Tospråklig app — Sub-prosjekt B: DB-skjema + oversettelsesscript (#38b) — Design

## Mål

Legge til engelske tekstkolonner i `kokt-bundle.db` og fylle dem med Claude API-oversettelse av alle 5962 oppskrifter (navn, beskrivelse, trinn) og ~2500 unike ingrediensnavn. Output er en oppdatert `kokt-bundle.db` som pakkes inn i neste portable build.

## Avhengigheter

Ingen avhengighet til sub-prosjekt A eller C — kan kjøres uavhengig. Sub-prosjekt C trenger de nye kolonnene.

## DB-skjemaendringer

Fire `ALTER TABLE`-setninger (idempotente, sjekker om kolonne finnes):

```sql
ALTER TABLE oppskrifter ADD COLUMN navn_en TEXT;
ALTER TABLE oppskrifter ADD COLUMN beskrivelse_en TEXT;
ALTER TABLE trinn ADD COLUMN tekst_en TEXT;
ALTER TABLE ingredienser ADD COLUMN navn_en TEXT;
```

Alle nullable. Norsk er alltid primær — engelske kolonner kan være NULL uten at appen krasjer (Rust bruker `COALESCE(navn_en, navn)` som fallback, implementert i sub-prosjekt C).

## Oversettelsesscript

**Fil:** `scripts/oversett_til_engelsk.py`

**Krav:** `pip install anthropic` (bruker `claude-haiku-4-5-20251001`)

**Kjøring:**
```bash
python scripts/oversett_til_engelsk.py kokebok-app/src-tauri/data/kokt-bundle.db
```

**Struktur:**

```python
import anthropic, sqlite3, json, sys, time

MODEL = "claude-haiku-4-5-20251001"
client = anthropic.Anthropic()  # leser ANTHROPIC_API_KEY fra env

def oversett_batch(items: list[dict], felt: list[str]) -> list[dict]:
    """Send en batch til Claude, returner oversatte verdier."""
    prompt = f"""Translate the following Norwegian recipe texts to English.
Return a JSON array with the same length. Each element has keys: {', '.join(felt)}.
Preserve cooking terminology, ingredient names, and measurements.
Keep brand names and proper nouns unchanged.
Input:
{json.dumps(items, ensure_ascii=False)}
Return ONLY valid JSON, no explanation."""
    
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return json.loads(msg.content[0].text)

def oversett_oppskrifter(conn, batch_size=50):
    rows = conn.execute(
        "SELECT id, navn, beskrivelse FROM oppskrifter WHERE navn_en IS NULL"
    ).fetchall()
    print(f"Oversetter {len(rows)} oppskrifter...")
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        items = [{"id": r[0], "navn": r[1] or "", "beskrivelse": r[2] or ""} for r in batch]
        try:
            results = oversett_batch(items, ["navn_en", "beskrivelse_en"])
            for j, res in enumerate(results):
                conn.execute(
                    "UPDATE oppskrifter SET navn_en=?, beskrivelse_en=? WHERE id=?",
                    (res.get("navn_en"), res.get("beskrivelse_en"), items[j]["id"])
                )
            conn.commit()
            print(f"  {min(i+batch_size, len(rows))}/{len(rows)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e} — hopper over")
        time.sleep(0.5)  # unngå rate limiting

def oversett_trinn(conn, batch_size=200):
    rows = conn.execute(
        "SELECT id, tekst FROM trinn WHERE tekst_en IS NULL AND tekst IS NOT NULL"
    ).fetchall()
    print(f"Oversetter {len(rows)} trinn...")
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        items = [{"id": r[0], "tekst": r[1]} for r in batch]
        try:
            results = oversett_batch(items, ["tekst_en"])
            for j, res in enumerate(results):
                conn.execute(
                    "UPDATE trinn SET tekst_en=? WHERE id=?",
                    (res.get("tekst_en"), items[j]["id"])
                )
            conn.commit()
            print(f"  {min(i+batch_size, len(rows))}/{len(rows)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e} — hopper over")
        time.sleep(0.5)

def oversett_ingredienser(conn, batch_size=500):
    rows = conn.execute(
        "SELECT DISTINCT navn FROM ingredienser WHERE navn IS NOT NULL AND navn_en IS NULL"
    ).fetchall()
    navnliste = [r[0] for r in rows]
    print(f"Oversetter {len(navnliste)} unike ingrediensnavn...")
    for i in range(0, len(navnliste), batch_size):
        batch = navnliste[i:i+batch_size]
        prompt = f"""Translate these Norwegian ingredient names to English.
Return a JSON object mapping each Norwegian name to its English translation.
Keep scientific names, brand names, and international terms unchanged.
Input: {json.dumps(batch, ensure_ascii=False)}
Return ONLY valid JSON object."""
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            mapping = json.loads(msg.content[0].text)
            for nb_navn, en_navn in mapping.items():
                conn.execute(
                    "UPDATE ingredienser SET navn_en=? WHERE navn=? AND navn_en IS NULL",
                    (en_navn, nb_navn)
                )
            conn.commit()
            print(f"  {min(i+batch_size, len(navnliste))}/{len(navnliste)}")
        except Exception as e:
            print(f"  FEIL batch {i}: {e} — hopper over")
        time.sleep(0.5)

if __name__ == "__main__":
    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)
    # Legg til kolonner hvis de ikke finnes
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
    
    oversett_oppskrifter(conn)
    oversett_trinn(conn)
    oversett_ingredienser(conn)
    conn.close()
    print("Ferdig!")
```

## Idempotens

Scriptet er trygt å kjøre på nytt:
- `WHERE navn_en IS NULL` hopper over allerede-oversatte rader
- `ALTER TABLE ... ADD COLUMN` feiler stille hvis kolonnen finnes
- Batching med `commit()` etter hver batch — ved avbrudd fortsetter neste kjøring der den slapp

## Estimat

- Oppskrifter (5962 × navn + beskrivelse): ~120 batches à 50, ca. 25 min, ~$0.30
- Trinn (~35 000 trinn): ~175 batches à 200, ca. 20 min, ~$0.25
- Ingrediensnavn (~2500 unike): ~5 batches à 500, ca. 5 min, ~$0.05
- **Totalt: ~50 min, ~$0.60**

## QA etter oversettelse

Manuell stikkprøve på 20–30 oppskrifter (norske originalretter, internasjonale retter, bakverk). Sjekk at:
- Norske spesialiteter («fårikål», «lutefisk», «lefse») beholder norsk navn i parentes eller beholdes uoversatt
- Ingrediensmengder og enheter er uberørt
- Fremgangsmåte-tekst er flytende engelsk

## Kobling til portable build

Etter vellykket kjøring av scriptet og QA: kjør `scripts/bygg_bundle_db.py` (eller tilsvarende) for å pakke den oppdaterte `kokt-bundle.db` inn i neste distribusjon. Ingen andre build-endringer nødvendig for dette sub-prosjektet.

## Testing

- Kjør script mot en kopi av DB: `cp kokt-bundle.db kokt-bundle-test.db && python scripts/oversett_til_engelsk.py kokt-bundle-test.db`
- Verifiser at `SELECT COUNT(*) FROM oppskrifter WHERE navn_en IS NULL` returnerer 0 etter kjøring
- Verifiser at `SELECT COUNT(*) FROM trinn WHERE tekst_en IS NULL AND tekst IS NOT NULL` returnerer 0
- Stikkprøve 5 oppskrifter manuelt
