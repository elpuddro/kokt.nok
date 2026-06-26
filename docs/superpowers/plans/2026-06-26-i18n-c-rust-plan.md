# Tospråklig app — Sub-prosjekt C: Rust + DB-kobling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alle Tauri-kommandoer som returnerer tekstinnhold fra DB får `lang: String`-parameter og bruker `COALESCE(kolonne_en, kolonne)` i SQL slik at appen returnerer engelske tekster når de er tilgjengelige.

**Architecture:** SQL-spørringer endres til `COALESCE(o.navn_en, o.navn) AS navn` o.l. for alle berørte kommandoer. `lang`-parameter sendes med i signaturen for klarhet og fremtidig utvidelse, men COALESCE håndterer fallback automatisk — ingen betinget SQL nødvendig. Struct-er (`Oppskrift` osv.) endres IKKE — COALESCE aliaser alltid til det norske kolonnenavnet. Frontend sender `lang` ved alle berørte `invoke`-kall.

**Tech Stack:** Rust (rusqlite), Tauri v2, SvelteKit 5.

## Global Constraints

- **Sub-prosjekt B MÅ VÆRE KJØRT FØRST** — kolonnene `navn_en`, `beskrivelse_en`, `tekst_en` (trinn), `navn_en` (ingredienser) må eksistere i DB. Verifiser med: `sqlite3 kokebok-app/src-tauri/data/kokt-bundle.db ".schema oppskrifter" | grep navn_en`
- Rust struct-er endres IKKE — COALESCE aliaser til norsk kolonnenavn
- Søk er bidireksjonelt: `WHERE LOWER(COALESCE(navn_en, navn)) LIKE ?1 OR LOWER(navn) LIKE ?1`
- `get_kategorier` berøres IKKE — frontend oversetter via `t()` (sub-prosjekt A)
- `#[tauri::command]` dekoratøren skal forbli på alle kommandoer
- INGEN Claude co-author trailer i commits
- Test-kommando for Rust: `cd kokebok-app && cargo test` (eksisterende tester må fortsatt passere)
- Alkohol-filteret i `hva_kan_jeg_lage` og `kandidater_for_slot` røres IKKE

---

## Fil-oversikt

| Fil | Handling |
|-----|----------|
| `kokebok-app/src-tauri/src/lib.rs` | Modifiser — `lang`-parameter + COALESCE i 5 kommandoer |
| `kokebok-app/src/routes/+page.svelte` | Modifiser — send `lang` med i alle berørte `invoke`-kall |

---

### Task 1: `hent_oppskrifter` — legg til `lang` og COALESCE

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (fn `hent_oppskrifter`, ca. linje 358–491)

**Interfaces:**
- Produces: `fn hent_oppskrifter(..., lang: Option<String>) -> Result<ListeSvar, String>`
  SQL returnerer `COALESCE(o.navn_en, o.navn) AS navn`

- [ ] **Steg 1: Verifiser at DB har `navn_en`-kolonnen**

```bash
sqlite3 kokebok-app/src-tauri/data/kokt-bundle.db ".schema oppskrifter" | grep -c "navn_en"
```

Forventet output: `1` (kolonnen finnes). Hvis `0`: sub-prosjekt B er ikke kjørt — stopp og kjør det først.

- [ ] **Steg 2: Legg til `lang`-parameter i `hent_oppskrifter`-signaturen**

Finn i `lib.rs`:
```rust
fn hent_oppskrifter(
    app: AppHandle,
    kategori: Option<String>,
    sok: Option<String>,
    side: Option<i64>,
    #[allow(non_snake_case)] perSide: Option<i64>,
    dietter: Option<Vec<String>>,
    sorter: Option<String>,
) -> Result<ListeSvar, String> {
```

Endre til:
```rust
fn hent_oppskrifter(
    app: AppHandle,
    kategori: Option<String>,
    sok: Option<String>,
    side: Option<i64>,
    #[allow(non_snake_case)] perSide: Option<i64>,
    dietter: Option<Vec<String>>,
    sorter: Option<String>,
    lang: Option<String>,
) -> Result<ListeSvar, String> {
```

- [ ] **Steg 3: Endre `list_sql` til å bruke COALESCE for `navn`**

Finn i funksjonen:
```rust
    let list_sql = format!(
        "SELECT o.id, o.slug, o.navn, o.type, o.porsjoner, o.tid, o.bilde
         FROM   oppskrifter o {where_sql}
         ORDER  BY {order}
         LIMIT  ? OFFSET ?"
    );
```

Endre til:
```rust
    let list_sql = format!(
        "SELECT o.id, o.slug, COALESCE(o.navn_en, o.navn) AS navn, o.type, o.porsjoner, o.tid, o.bilde
         FROM   oppskrifter o {where_sql}
         ORDER  BY {order}
         LIMIT  ? OFFSET ?"
    );
```

- [ ] **Steg 4: Oppdater FTS-fallback LIKE-søk til å søke bidireksjonelt**

Finn den eksisterende LIKE-fallback-linjen:
```rust
                conds.push(
                    "(o.navn LIKE ? OR EXISTS (SELECT 1 FROM ingredienser i \
                     WHERE i.oppskrift_id = o.id AND i.navn LIKE ?))",
                );
```

Endre til:
```rust
                conds.push(
                    "(COALESCE(o.navn_en, o.navn) LIKE ? OR o.navn LIKE ? OR EXISTS (SELECT 1 FROM ingredienser i \
                     WHERE i.oppskrift_id = o.id AND (COALESCE(i.navn_en, i.navn) LIKE ? OR i.navn LIKE ?)))",
                );
```

Merk: FTS-søket (ord-matching via `fts_ids_for_ord`) er ikke berørt — det matcher på ID-er.

**VIKTIG**: Fordi LIKE-fallback nå bruker 4 `?` per ord (mot 2 tidligere), må `owned`-vektoren pushe alle 4 verdier. Finn der `owned.push(like.clone())` forekommer for LIKE-fallback og endre:

Finn:
```rust
            let like = format!("%{ord}%");
            owned.push(like.clone());
            owned.push(like);
            conds.push(
                "(o.navn LIKE ? OR EXISTS (SELECT 1 FROM ingredienser i \
                 WHERE i.oppskrift_id = o.id AND i.navn LIKE ?))",
            );
```

Endre til:
```rust
            let like = format!("%{ord}%");
            owned.push(like.clone());
            owned.push(like.clone());
            owned.push(like.clone());
            owned.push(like);
            conds.push(
                "(COALESCE(o.navn_en, o.navn) LIKE ? OR o.navn LIKE ? OR EXISTS (SELECT 1 FROM ingredienser i \
                 WHERE i.oppskrift_id = o.id AND (COALESCE(i.navn_en, i.navn) LIKE ? OR i.navn LIKE ?)))",
            );
```

- [ ] **Steg 5: Bygg og kjør Rust-tester**

```bash
cd kokebok-app && cargo test 2>&1 | tail -20
```

Forventet: alle eksisterende tester passerer, 0 errors.

- [ ] **Steg 6: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(i18n): hent_oppskrifter — lang-param + COALESCE for navn"
```

---

### Task 2: `hent_oppskrift` — COALESCE for navn, beskrivelse, trinn og ingredienser

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (fn `hent_oppskrift`, ca. linje 491–674)

**Interfaces:**
- Produces: `fn hent_oppskrift(app: AppHandle, id: i64, lang: Option<String>) -> Result<Option<Value>, String>`
  SQL for oppskrift, trinn og ingredienser bruker COALESCE

- [ ] **Steg 1: Legg til `lang`-parameter**

Finn:
```rust
fn hent_oppskrift(app: AppHandle, id: i64) -> Result<Option<Value>, String> {
```

Endre til:
```rust
fn hent_oppskrift(app: AppHandle, id: i64, lang: Option<String>) -> Result<Option<Value>, String> {
```

- [ ] **Steg 2: Endre oppskrift-SQL til COALESCE for navn og beskrivelse**

Finn:
```rust
    let mut rows = query_json(
        &conn,
        "SELECT id, slug, navn, type, beskrivelse, porsjoner, tid, bilde, url, hentet
         FROM oppskrifter WHERE id = ?",
        &[&id],
    )?;
```

Endre til:
```rust
    let mut rows = query_json(
        &conn,
        "SELECT id, slug, COALESCE(navn_en, navn) AS navn, type,
                COALESCE(beskrivelse_en, beskrivelse) AS beskrivelse,
                porsjoner, tid, bilde, url, hentet
         FROM oppskrifter WHERE id = ?",
        &[&id],
    )?;
```

- [ ] **Steg 3: Endre ingrediens-SQL til COALESCE for navn**

Finn:
```rust
    let ings = query_json(
        &conn,
        "SELECT gruppe, mengde, enhet, navn, raatekst, sortering
         FROM ingredienser WHERE oppskrift_id = ? ORDER BY gruppe, sortering",
        &[&id],
    )?;
```

Endre til:
```rust
    let ings = query_json(
        &conn,
        "SELECT gruppe, mengde, enhet, COALESCE(navn_en, navn) AS navn, raatekst, sortering
         FROM ingredienser WHERE oppskrift_id = ? ORDER BY gruppe, sortering",
        &[&id],
    )?;
```

- [ ] **Steg 4: Endre trinn-SQL til COALESCE for tekst**

Finn:
```rust
    let trinn = query_json(
        &conn,
        "SELECT nummer, tekst FROM trinn WHERE oppskrift_id = ? ORDER BY nummer",
        &[&id],
    )?;
```

Endre til:
```rust
    let trinn = query_json(
        &conn,
        "SELECT nummer, COALESCE(tekst_en, tekst) AS tekst FROM trinn WHERE oppskrift_id = ? ORDER BY nummer",
        &[&id],
    )?;
```

- [ ] **Steg 5: Bygg og kjør Rust-tester**

```bash
cd kokebok-app && cargo test 2>&1 | tail -20
```

Forventet: 0 errors, alle tester passerer.

- [ ] **Steg 6: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(i18n): hent_oppskrift — COALESCE for navn/beskrivelse/trinn/ingredienser"
```

---

### Task 3: `hent_oppskrifter_by_ids` og `sok_ingredienser` — lang + COALESCE

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (fn `hent_oppskrifter_by_ids` ca. linje 674, fn `sok_ingredienser` ca. linje 791)

**Interfaces:**
- Produces:
  - `fn hent_oppskrifter_by_ids(app: AppHandle, ids: Vec<i64>, lang: Option<String>) -> Result<Vec<Value>, String>`
  - `fn sok_ingredienser(app: AppHandle, q: String, lang: Option<String>) -> Result<Vec<String>, String>`

- [ ] **Steg 1: Oppdater `hent_oppskrifter_by_ids`**

Finn:
```rust
fn hent_oppskrifter_by_ids(app: AppHandle, ids: Vec<i64>) -> Result<Vec<Value>, String> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    let conn = open(&app)?;

    let placeholders = vec!["?"; ids.len()].join(",");
    let sql = format!(
        "SELECT id, slug, navn, type, porsjoner, tid, bilde
         FROM   oppskrifter
         WHERE  id IN ({placeholders})
         ORDER  BY navn COLLATE NOCASE"
    );
```

Endre til:
```rust
fn hent_oppskrifter_by_ids(app: AppHandle, ids: Vec<i64>, lang: Option<String>) -> Result<Vec<Value>, String> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    let conn = open(&app)?;

    let placeholders = vec!["?"; ids.len()].join(",");
    let sql = format!(
        "SELECT id, slug, COALESCE(navn_en, navn) AS navn, type, porsjoner, tid, bilde
         FROM   oppskrifter
         WHERE  id IN ({placeholders})
         ORDER  BY COALESCE(navn_en, navn) COLLATE NOCASE"
    );
```

- [ ] **Steg 2: Oppdater `sok_ingredienser`**

Finn:
```rust
fn sok_ingredienser(app: AppHandle, q: String) -> Result<Vec<String>, String> {
    if q.trim().is_empty() {
        return Ok(vec![]);
    }
    let conn = open(&app)?;
    let mønster = format!("%{}%", q.to_lowercase());
    let mut stmt = conn.prepare(
        "SELECT DISTINCT navn FROM ingredienser WHERE LOWER(navn) LIKE ?1 ORDER BY navn LIMIT 20"
    ).map_err(|e| e.to_string())?;
    let navn: Vec<String> = stmt.query_map([&mønster], |row| row.get(0))
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(navn)
}
```

Endre til:
```rust
fn sok_ingredienser(app: AppHandle, q: String, lang: Option<String>) -> Result<Vec<String>, String> {
    if q.trim().is_empty() {
        return Ok(vec![]);
    }
    let conn = open(&app)?;
    let mønster = format!("%{}%", q.to_lowercase());
    let mut stmt = conn.prepare(
        "SELECT DISTINCT COALESCE(navn_en, navn) AS navn FROM ingredienser \
         WHERE LOWER(COALESCE(navn_en, navn)) LIKE ?1 OR LOWER(navn) LIKE ?1 \
         ORDER BY 1 LIMIT 20"
    ).map_err(|e| e.to_string())?;
    let navn: Vec<String> = stmt.query_map([&mønster], |row| row.get(0))
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(navn)
}
```

- [ ] **Steg 3: Bygg og kjør Rust-tester**

```bash
cd kokebok-app && cargo test 2>&1 | tail -20
```

Forventet: 0 errors.

- [ ] **Steg 4: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(i18n): hent_oppskrifter_by_ids og sok_ingredienser — lang + COALESCE"
```

---

### Task 4: `generer_matplan` / `kandidater_for_slot` — COALESCE for oppskriftnavn

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (fn `kandidater_for_slot` ca. linje 975, fn `generer_matplan` ca. linje 1151)

**Interfaces:**
- Produces: `kandidater_for_slot` henter `COALESCE(navn_en, navn)` for `Kandidat.navn`
  `generer_matplan` trenger ikke signaturendring (kaller bare `kandidater_for_slot`)

- [ ] **Steg 1: Les `kandidater_for_slot` SQL**

Finn `fn kandidater_for_slot` (ca. linje 975) og se på SQL-spørringen som henter oppskrifter. Den ser typisk ut som:

```rust
    let sql = format!(
        "SELECT o.id, o.navn, o.type, ...
         FROM oppskrifter o
         JOIN kategorier k ON k.oppskrift_id = o.id
         WHERE k.kategori IN ({kat_placeholders})
         ..."
    );
```

- [ ] **Steg 2: Endre `navn` til COALESCE i `kandidater_for_slot`**

Finn `o.navn` i SELECT-listen i SQL-en og endre til:
```sql
COALESCE(o.navn_en, o.navn) AS navn
```

Les hele `kandidater_for_slot`-funksjonen og finn alle steder der `o.navn` hentes i SQL — endre alle til `COALESCE(o.navn_en, o.navn) AS navn`.

- [ ] **Steg 3: Endre `forside_oppskrifter` SQL om den finnes**

```bash
grep -n "forside_oppskrifter\|fn forside" kokebok-app/src-tauri/src/lib.rs
```

Finn `fn forside_oppskrifter` (ca. linje 1470). Endre `o.navn` → `COALESCE(o.navn_en, o.navn) AS navn` i SQL-en.

- [ ] **Steg 4: Bygg og kjør Rust-tester**

```bash
cd kokebok-app && cargo test 2>&1 | tail -20
```

Forventet: 0 errors, alle tester passerer.

- [ ] **Steg 5: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(i18n): kandidater_for_slot og forside_oppskrifter — COALESCE for navn"
```

---

### Task 5: `hva_kan_jeg_lage` og `ingrediens_forslag` — COALESCE for ingrediensnavn

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (fn `hva_kan_jeg_lage` ca. linje 819, fn `ingrediens_forslag` ca. linje 767)

**Interfaces:**
- Produces:
  - `fn hva_kan_jeg_lage(app: AppHandle, varer: Vec<String>, lang: Option<String>)` — `Forslag.navn` på riktig språk
  - `fn ingrediens_forslag(app: AppHandle, prefiks: String, lang: Option<String>)` — engelske ingrediensnavn

- [ ] **Steg 1: Oppdater `hva_kan_jeg_lage`**

Finn:
```rust
fn hva_kan_jeg_lage(app: AppHandle, varer: Vec<String>) -> Result<Vec<Forslag>, String> {
```

Endre til:
```rust
fn hva_kan_jeg_lage(app: AppHandle, varer: Vec<String>, lang: Option<String>) -> Result<Vec<Forslag>, String> {
```

Finn SQL-en i `hva_kan_jeg_lage` som inneholder `SELECT o.id, o.navn, o.type, i.navn`:
```rust
    let mut stmt = conn
        .prepare(
            "SELECT o.id, o.navn, o.type, i.navn \
             FROM oppskrifter o JOIN ingredienser i ON i.oppskrift_id = o.id \
             WHERE i.navn IS NOT NULL AND i.navn != '' \
             AND NOT EXISTS (SELECT 1 FROM ingredienser ai JOIN ingrediens_tagg t ON t.navn = ai.navn \
                             WHERE ai.oppskrift_id = o.id AND t.tagg = 'alkohol') \
             ORDER BY o.id",
        )
```

Endre til:
```rust
    let mut stmt = conn
        .prepare(
            "SELECT o.id, COALESCE(o.navn_en, o.navn) AS navn, o.type, \
                    COALESCE(i.navn_en, i.navn) AS inavn \
             FROM oppskrifter o JOIN ingredienser i ON i.oppskrift_id = o.id \
             WHERE i.navn IS NOT NULL AND i.navn != '' \
             AND NOT EXISTS (SELECT 1 FROM ingredienser ai JOIN ingrediens_tagg t ON t.navn = ai.navn \
                             WHERE ai.oppskrift_id = o.id AND t.tagg = 'alkohol') \
             ORDER BY o.id",
        )
```

Kolonneindeksene i `query_map`-closuren er de samme (0=id, 1=navn, 2=type, 3=inavn) — navnene er bare aliaser.

- [ ] **Steg 2: Oppdater `ingrediens_forslag`**

Finn:
```rust
fn ingrediens_forslag(app: AppHandle, prefiks: String) -> Result<Vec<String>, String> {
```

Endre til:
```rust
fn ingrediens_forslag(app: AppHandle, prefiks: String, lang: Option<String>) -> Result<Vec<String>, String> {
```

Finn SQL-en:
```rust
    let mut stmt = conn
        .prepare(
            "SELECT DISTINCT navn FROM ingredienser \
             WHERE navn IS NOT NULL AND LOWER(navn) LIKE ?1 \
             ORDER BY CASE WHEN LOWER(navn) LIKE ?2 THEN 0 ELSE 1 END, navn COLLATE NOCASE \
             LIMIT 10",
        )
```

Endre til:
```rust
    let mut stmt = conn
        .prepare(
            "SELECT DISTINCT COALESCE(navn_en, navn) AS navn FROM ingredienser \
             WHERE navn IS NOT NULL \
               AND (LOWER(COALESCE(navn_en, navn)) LIKE ?1 OR LOWER(navn) LIKE ?1) \
             ORDER BY CASE WHEN LOWER(COALESCE(navn_en, navn)) LIKE ?2 THEN 0 ELSE 1 END, \
                      COALESCE(navn_en, navn) COLLATE NOCASE \
             LIMIT 10",
        )
```

- [ ] **Steg 3: Bygg og kjør Rust-tester**

```bash
cd kokebok-app && cargo test 2>&1 | tail -20
```

Forventet: 0 errors.

- [ ] **Steg 4: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(i18n): hva_kan_jeg_lage og ingrediens_forslag — COALESCE for ingrediensnavn"
```

---

### Task 6: Frontend — send `lang` med i alle berørte `invoke`-kall

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (alle berørte invoke-kall)

**Interfaces:**
- Consumes: `lang: Lang` (fra sub-prosjekt A, Task 2) — MÅ finnes i `+page.svelte`
- Note: Hvis sub-prosjekt A ikke er implementert ennå, legg til en midlertidig `let lang = "nb";` øverst i script-blokken og fjern den når A er på plass.

- [ ] **Steg 1: Finn alle berørte invoke-kall**

```bash
cd kokebok-app && grep -n "invoke.*hent_oppskrift\b\|invoke.*hent_oppskrifter\b\|invoke.*hent_oppskrifter_by_ids\|invoke.*sok_ingredienser\|invoke.*hva_kan_jeg_lage\|invoke.*ingrediens_forslag\|invoke.*generer_matplan\|invoke.*forside_oppskrifter" src/routes/+page.svelte
```

Typiske treff (eksakt linjekall endres basert på faktiske linjer i filen):

- `invoke("hent_oppskrifter", { kategori, sok, side, perSide, dietter, sorter })` — legg til `lang`
- `invoke("hent_oppskrift", { id })` — legg til `lang` (finnes på ~3 steder)
- `invoke("hent_oppskrifter_by_ids", { ids: [...favoritter] })` — legg til `lang`
- `invoke<string[]>("sok_ingredienser", { q: rad.ingrediens })` — legg til `lang`
- `invoke("hva_kan_jeg_lage", { varer })` — legg til `lang`
- `invoke("ingrediens_forslag", { prefiks })` — legg til `lang`
- `invoke("generer_matplan", { dagsmaal, ... })` — legg til `lang` (selv om Rust ikke bruker det ennå)
- `invoke("forside_oppskrifter", { ... })` — legg til `lang`

- [ ] **Steg 2: Oppdater hvert invoke-kall**

For hvert treff fra Steg 1, legg til `, lang` som parameter. Eksempel:

```ts
// Før:
const data: any = await invoke("hent_oppskrifter", {
  kategori: currentKategori, sok, side, perSide, dietter: aktiveDietter, sorter,
});

// Etter:
const data: any = await invoke("hent_oppskrifter", {
  kategori: currentKategori, sok, side, perSide, dietter: aktiveDietter, sorter, lang,
});
```

```ts
// Før:
const opp: any = await invoke("hent_oppskrift", { id });

// Etter:
const opp: any = await invoke("hent_oppskrift", { id, lang });
```

```ts
// Før:
const liste: any[] = await invoke("hent_oppskrifter_by_ids", { ids: [...favoritter] });

// Etter:
const liste: any[] = await invoke("hent_oppskrifter_by_ids", { ids: [...favoritter], lang });
```

```ts
// Før:
rad.forslag = await invoke<string[]>("sok_ingredienser", { q: rad.ingrediens })

// Etter:
rad.forslag = await invoke<string[]>("sok_ingredienser", { q: rad.ingrediens, lang })
```

- [ ] **Steg 3: Verifiser kompilering**

```bash
cd kokebok-app && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | head -40
```

Forventet: 0 errors.

- [ ] **Steg 4: Bygg Tauri i dev-modus for å verifisere Rust-grensesnitt**

```bash
cd kokebok-app && cargo build --manifest-path src-tauri/Cargo.toml 2>&1 | tail -20
```

Forventet: `Compiling kokt_nok` → `Finished`. Ingen errors.

- [ ] **Steg 5: Merk #38c ferdig i `docs/IDEER.md`**

Legg til i `docs/IDEER.md`:
```
- [x] #38 Tospråklig app — Sub-prosjekt C (Rust + DB-kobling) FERDIG 2026-06-26
```

- [ ] **Steg 6: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte docs/IDEER.md
git commit -m "feat(i18n): send lang med i alle invoke-kall + merk #38c ferdig"
```
