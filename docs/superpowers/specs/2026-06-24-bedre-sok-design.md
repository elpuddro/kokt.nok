# Bedre søk og sortering — Design (#5)

**Dato:** 2026-06-24

---

## Mål

Søkefeltet tolker mellomrom-separerte ord som AND-kombinasjon (hvert ord må matche navn eller ingrediens). Brukeren kan sortere oppskriftslisten på navn (A–Å/Å–A) og tilberedningstid (kortest/lengst).

---

## Arkitektur

To uavhengige forbedringer, begge i samme to filer:

1. **AND-søk** — `hent_oppskrifter` i `lib.rs` splitter `sok` på whitespace og genererer ett vilkår per ord (maks 5). Frontend endres ikke utover at `sorter` sendes med.
2. **Sortering** — ny `sorter`-parameter i `hent_oppskrifter`. Frontend får en `<select>`-dropdown i header, persistert i Tauri Store.

---

## Søkelogikk

### Nåværende (ett ord)

```sql
(o.navn LIKE '%X%' OR EXISTS (SELECT 1 FROM ingredienser i WHERE i.oppskrift_id = o.id AND i.navn LIKE '%X%'))
```

### Nytt (N ord, AND-kombinert)

Hvert whitespace-separert ord genererer ett eget vilkår, AND-koblet:

```sql
(o.navn LIKE '%kjøttdeig%' OR EXISTS (SELECT 1 FROM ingredienser i WHERE i.oppskrift_id = o.id AND i.navn LIKE '%kjøttdeig%'))
AND
(o.navn LIKE '%sitron%' OR EXISTS (SELECT 1 FROM ingredienser i WHERE i.oppskrift_id = o.id AND i.navn LIKE '%sitron%'))
```

**Regler:**
- Ett ord = eksisterende oppførsel (ingen endring i brukeropplevelse)
- Maks 5 ord tolkes; ord utover 5 ignoreres stille
- Hvert ord trimmest og tomme ord hoppes over
- Splitting skjer i Rust: `sok.split_whitespace().take(5)`

---

## Sortering

### Parameter

`hent_oppskrifter` får nytt parameter `sorter: Option<String>` med fire gyldige verdier:

| Verdi | Sortering |
|-------|-----------|
| `"navn_asc"` | `ORDER BY o.navn COLLATE NOCASE ASC` (default) |
| `"navn_desc"` | `ORDER BY o.navn COLLATE NOCASE DESC` |
| `"tid_asc"` | Korteste tid først; NULL sist |
| `"tid_desc"` | Lengste tid først; NULL sist |

Ugyldig eller manglende verdi faller tilbake til `"navn_asc"`.

### Tidsparsingi Rust

`tid`-kolonnen er fritekst (`"30 min"`, `"1 time 20 min"`, `"1 time"`, `NULL`). En hjelpefunksjon `tid_til_min(s: &str) -> Option<i64>` konverterer til minutter:

```rust
fn tid_til_min(s: &str) -> Option<i64> {
    let s = s.trim().to_lowercase();
    if s.contains("time") && s.contains("min") {
        // "X time Y min"
        let t: i64 = s.split("time").next()?.trim().parse().ok()?;
        let m: i64 = s.split("time").nth(1)?.replace("min", "").trim().parse().ok()?;
        return Some(t * 60 + m);
    }
    if s.ends_with("time") {
        // "X time"
        return s.replace("time", "").trim().parse::<i64>().ok().map(|t| t * 60);
    }
    if s.ends_with("min") {
        // "X min"
        return s.replace("min", "").trim().parse::<i64>().ok();
    }
    None
}
```

Siden SQLite ikke kan kalle Rust-funksjoner direkte, hentes alle rader med ekstra `tid`-kolonne og sorteres i Rust-minnet etter `tid_til_min`. Kun for tidssortering — navn-sortering gjøres fortsatt i SQL.

**Implementasjonsdetalj for tidssortering:** `hent_oppskrifter` henter rader usortert fra DB (kun WHERE-filter), sorterer `Vec<OppskriftRad>` i Rust, paginerer manuelt (`skip(offset).take(per_side)`). COUNT-queryen er uendret.

### UI

En `<select>`-dropdown plassert i `#main-header` til høyre for søkefeltet:

```svelte
<select bind:value={sorter} onchange={onSorterChange}>
  <option value="navn_asc">Navn A–Å</option>
  <option value="navn_desc">Navn Å–A</option>
  <option value="tid_asc">Tid: kortest først</option>
  <option value="tid_desc">Tid: lengst først</option>
</select>
```

`onSorterChange` persisterer til Tauri Store og kaller `fetchGrid()`.

### Persistering

Tauri Store-nøkkel: `"sorter"` i `sorter.json`. Lastes i `onMount` etter eksisterende Store-lastinger. Standardverdi `"navn_asc"` hvis ingenting er lagret.

```typescript
// Last
const sorterStore = await load("sorter.json");
sorter = (await sorterStore.get<string>("sorter")) ?? "navn_asc";

// Lagre
async function onSorterChange() {
  const s = await load("sorter.json");
  await s.set("sorter", sorter);
  await s.save();
  side = 1;
  await fetchGrid();
}
```

---

## Filer som endres

| Fil | Endring |
|-----|---------|
| `kokebok-app/src-tauri/src/lib.rs` | AND-splitting av `sok`, `tid_til_min()`, `sorter`-parameter, in-memory sort + manuell paginering for tidssortering |
| `kokebok-app/src/routes/+page.svelte` | `sorter`-state, Tauri Store last/lagre, `<select>`-dropdown i header, `sorter` sendt med i `fetchGrid` |

---

## Ikke inkludert (YAGNI)

- Sortering på porsjoner
- Fritekstsøk i beskrivelse/trinn
- Avansert søkesyntaks (sitater, minus-operator)
- Sortering persistert per kategori
- Søkehistorikk
