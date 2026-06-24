# Høytid og sesongoppskrifter Implementasjonsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forsiden viser sesong-kurerte retter i høytidsperioder, og matplanleggeren får en sesong-toggle som vekter høytidsretter (+50 score) i ukemenyen.

**Architecture:** En ny `høytid TEXT`-kolonne i `kokt.db` tagges via Python-scripts (nøkkelordregler + manuell kurasjon). Dato-logikken porteres fra `tema-logikk.ts` til Rust som rene funksjoner (`paaskedag`, `hoytid_aktiv_dato`, `hoytid_aktiv`). Frontend leser `hoytid_aktiv` i `onMount` og grener forsiden og matplanleggeren på resultatet.

**Tech Stack:** Python 3 (tagging-scripts, pytest), Rust (`lib.rs`, `rusqlite`, `chrono`-fri dato-logikk), Svelte 5 runes (`$state`), Tauri Store (`plan.json`), SQLite (`kokt.db`)

## Global Constraints

- `kokt.db` er **read-only** i appen — tagging skjer kun via offline Python-scripts
- Svelte 5 runes kun: `$state`, `$derived` — ingen `$:`, ingen `writable()`
- Tauri Store: `load("plan.json")`, singleton-mønster som resten av appen
- Ingen nye Tauri-kommandoer utover `hoytid_aktiv` + utvidelse av eksisterende `forside_oppskrifter` og `generer_matplan`
- CSS-variabler fra `app.css`: `--card`, `--text-muted`, `--border`, `--surface`, `--bg`, `--text`, `--radius-sm`, `--font-ui`
- `kokt.db` er delt mellom dev og portable — scripts kjøres manuelt, ikke automatisk ved build
- Ingen `chrono`-crate — all datoberegning skjer med `std::time::SystemTime` og egne Gauss/Computus-funksjoner
- Ingen `#[allow(non_snake_case)]` utover eksisterende (bruk snake_case for nye parametere)
- Commit-meldinger uten "Co-Authored-By"-trailer

## Høytider og nøkler

| Nøkkel | Navn | Datovindu |
|---|---|---|
| `valentins` | Valentinsdag | feb 7–14 |
| `paske` | Påske | palmesøndag (påske−7) → 2. påskedag (påske+1) |
| `mai17` | 17. mai | mai 10–18 |
| `sankthans` | Sankthans | jun 20–24 |
| `farikaal` | Fårikålens dag | siste torsdag i sept ± 3 dager |
| `halloween` | Halloween | okt 24–31 |
| `jul` | Jul | des 1 – jan 6 |

## Filstruktur

| Fil | Status | Ansvar |
|---|---|---|
| `scripts/tagg_hoytid.py` | Ny | Nøkkelordregler → `data/hoytid_forslag.json` |
| `scripts/importer_hoytid.py` | Ny | `hoytid_forslag.json` → `kokt.db` `høytid`-kolonne |
| `scripts/test_tagg_hoytid.py` | Ny | Unit-tester for tagg_hoytid-logikken |
| `kokebok-app/src-tauri/src/lib.rs` | Modifiser | `paaskedag`, `hoytid_aktiv_dato`, `hoytid_aktiv` kommando, utvidet `forside_oppskrifter` og `generer_matplan` |
| `kokebok-app/src/routes/+page.svelte` | Modifiser | `aktivHoytid` state, `lastForside` gren, høytidsbanner, sesong-toggle |

---

### Task 1: Tagging-scripts og DB-kolonne

**Files:**
- Create: `scripts/tagg_hoytid.py`
- Create: `scripts/importer_hoytid.py`
- Create: `scripts/test_tagg_hoytid.py`
- Modify: `kokebok-app/src-tauri/data/kokt.db` (via script — legg til `høytid`-kolonne)

**Interfaces:**
- Produces:
  - `tagg_hoytid(navn: str, ingredienser: str) -> set[str]` — testbar ren funksjon
  - `data/hoytid_forslag.json` — `{str(id): [nøkkel, ...]}` for alle matchede oppskrifter
  - `kokt.db` med `høytid TEXT`-kolonne på `oppskrifter`-tabellen

- [ ] **Step 1: Skriv testene først**

Opprett `scripts/test_tagg_hoytid.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from tagg_hoytid import tagg_hoytid

def test_pinnekjott_er_jul():
    assert "jul" in tagg_hoytid("Pinnekjøtt med kålrabistappe", "pinnekjøtt, kålrabi")

def test_ribbe_er_jul():
    assert "jul" in tagg_hoytid("Julegribberibbe", "ribbe, svor")

def test_lam_er_paske():
    assert "paske" in tagg_hoytid("Lammestek", "lammestek, rosmarin")

def test_blotkake_er_mai17():
    assert "mai17" in tagg_hoytid("Bløtkake til 17. mai", "jordbær, fløte")

def test_jordbær_er_sankthans():
    assert "sankthans" in tagg_hoytid("Jordbær med rømme", "jordbær, rømme")

def test_farikaal_er_farikaal():
    assert "farikaal" in tagg_hoytid("Fårikål", "lam, kål, pepper")

def test_gresskar_er_halloween():
    assert "halloween" in tagg_hoytid("Gresskarpai", "gresskar, kanel")

def test_sjokolade_er_valentins():
    assert "valentins" in tagg_hoytid("Sjokoladefondue", "sjokolade, fløte")

def test_kylling_er_ingen_hoytid():
    assert tagg_hoytid("Kyllingfilet", "kylling, hvitløk") == set()

def test_farikaal_er_ikke_paske():
    assert "paske" not in tagg_hoytid("Fårikål", "lam, kål")
```

- [ ] **Step 2: Kjør testene — verifiser at de feiler**

```
cd C:\Users\elpud\CODE\kokt.nok\scripts
pytest test_tagg_hoytid.py -v
```

Forventet: ImportError (tagg_hoytid ikke laget ennå)

- [ ] **Step 3: Implementer `scripts/tagg_hoytid.py`**

```python
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
        "pepperkake", "julekake", "multekrem", "riskrem", "risgrøt", "risgrøt",
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
    "paske":     ["lam"],           # «lam» i «flamme» → falsk positiv
    "mai17":     ["pølse"],         # «pølse» er dagligdags — bare match alene
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
            nøkkel = str(opp_id)
            # Merger: union av eksisterende og nye regler
            gamle = set(eksisterende.get(nøkkel, []))
            resultat[nøkkel] = sorted(gamle | hoytider)

    FORSLAG.parent.mkdir(exist_ok=True)
    FORSLAG.write_text(json.dumps(resultat, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

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
```

- [ ] **Step 4: Kjør testene — verifiser at de passerer**

```
cd C:\Users\elpud\CODE\kokt.nok\scripts
pytest test_tagg_hoytid.py -v
```

Forventet: 10 PASSED

- [ ] **Step 5: Implementer `scripts/importer_hoytid.py`**

```python
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

    # Legg til kolonne hvis den ikke finnes
    eksist = [r[1] for r in conn.execute("PRAGMA table_info(oppskrifter)")]
    if "hoytid" not in eksist:
        conn.execute("ALTER TABLE oppskrifter ADD COLUMN hoytid TEXT")

    # Nullstill alle eksisterende høytid-tagger, sett nye
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
```

- [ ] **Step 6: Legg til `høytid`-kolonne og kjør tagging**

```
cd C:\Users\elpud\CODE\kokt.nok
python scripts/tagg_hoytid.py
```

Forventet output: `Ferdig: N oppskrifter tagget.` med liste per høytid.

Gjennomgå `data/hoytid_forslag.json` manuelt — fjern åpenbare feil, legg til manglende.

```
python scripts/importer_hoytid.py
```

Forventet: `Ferdig: N oppskrifter tagget i kokt.db.`

- [ ] **Step 7: Commit**

```
git add scripts/tagg_hoytid.py scripts/importer_hoytid.py scripts/test_tagg_hoytid.py data/hoytid_forslag.json
git commit -m "feat(hoytid): tagging-scripts og hoytid-kolonne i kokt.db"
```

---

### Task 2: Rust — `hoytid_aktiv` og utvidet `forside_oppskrifter`

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs`

**Interfaces:**
- Consumes: `høytid TEXT`-kolonne i `kokt.db` (fra Task 1)
- Produces:
  - `fn paaskedag(aar: i32) -> (u32, u32)` — (måned, dag) for 1. påskedag
  - `fn hoytid_aktiv_dato(maaned: u32, dag: u32, ukedag: u32, aar: i32) -> Option<String>` — testbar ren funksjon
  - `#[tauri::command] fn hoytid_aktiv() -> Option<String>` — kalles fra frontend
  - Utvidet `forside_oppskrifter` med `hoytid: Option<String>`-parameter

- [ ] **Step 1: Skriv Rust-tester for dato-logikken**

Legg til under `#[cfg(test)] mod tests {` (linje ~1330 i `lib.rs`), etter eksisterende tester:

```rust
    #[test]
    fn test_paaskedag_2024() {
        // Påske 2024: 31. mars
        assert_eq!(paaskedag(2024), (3, 31));
    }

    #[test]
    fn test_paaskedag_2025() {
        // Påske 2025: 20. april
        assert_eq!(paaskedag(2025), (4, 20));
    }

    #[test]
    fn test_hoytid_jul_desember() {
        // 15. des, tirsdag (ukedag 2), 2024
        assert_eq!(hoytid_aktiv_dato(12, 15, 2, 2024).as_deref(), Some("jul"));
    }

    #[test]
    fn test_hoytid_jul_januar() {
        // 3. jan, torsdag (ukedag 4), 2025
        assert_eq!(hoytid_aktiv_dato(1, 3, 4, 2025).as_deref(), Some("jul"));
    }

    #[test]
    fn test_hoytid_halloween() {
        // 28. okt, mandag (ukedag 1), 2024
        assert_eq!(hoytid_aktiv_dato(10, 28, 1, 2024).as_deref(), Some("halloween"));
    }

    #[test]
    fn test_hoytid_mai17() {
        // 17. mai, fredag (ukedag 5), 2024
        assert_eq!(hoytid_aktiv_dato(5, 17, 5, 2024).as_deref(), Some("mai17"));
    }

    #[test]
    fn test_hoytid_valentins() {
        // 10. feb, lørdag (ukedag 6), 2024
        assert_eq!(hoytid_aktiv_dato(2, 10, 6, 2024).as_deref(), Some("valentins"));
    }

    #[test]
    fn test_hoytid_ingen_august() {
        // 15. aug — ingen høytid
        assert_eq!(hoytid_aktiv_dato(8, 15, 4, 2024), None);
    }
```

- [ ] **Step 2: Kjør tester — verifiser at de feiler**

```
cd kokebok-app/src-tauri
cargo test 2>&1 | tail -20
```

Forventet: feil på `paaskedag` og `hoytid_aktiv_dato` (ikke definert ennå)

- [ ] **Step 3: Implementer dato-logikken i `lib.rs`**

Legg til disse funksjonene rett over `fn forside_oppskrifter` (linje 1238):

```rust
// Beregn 1. påskedag for ett år via Gauss/Computus-algoritmen.
// Returnerer (måned, dag): (3, X) for mars, (4, X) for april.
fn paaskedag(aar: i32) -> (u32, u32) {
    let a = (aar % 19) as u32;
    let b = (aar / 100) as u32;
    let c = (aar % 100) as u32;
    let d = b / 4;
    let e = b % 4;
    let f = (b + 8) / 25;
    let g = (b - f + 1) / 3;
    let h = (19 * a + b - d - g + 15) % 30;
    let i = c / 4;
    let k = c % 4;
    let l = (32 + 2 * e + 2 * i - h - k) % 7;
    let m = (a + 11 * h + 22 * l) / 451;
    let maaned = (h + l - 7 * m + 114) / 31;
    let dag = ((h + l - 7 * m + 114) % 31) + 1;
    (maaned, dag)
}

// Gitt dato (1-indeksert måned, dag, ISO ukedag 1=man..7=søn, år),
// returner gjeldende høytidsnøkkel eller None.
fn hoytid_aktiv_dato(maaned: u32, dag: u32, ukedag: u32, aar: i32) -> Option<String> {
    // Valentinsdag: feb 7–14
    if maaned == 2 && dag >= 7 && dag <= 14 {
        return Some("valentins".into());
    }

    // Påske: palmesøndag (påske−7 dager) → 2. påskedag (påske+1 dag)
    let (p_mnd, p_dag) = paaskedag(aar);
    // Konverter til dagnummer i år for enkel ± beregning
    let dager_i_mnd = |m: u32, y: i32| -> u32 {
        match m {
            1|3|5|7|8|10|12 => 31,
            4|6|9|11 => 30,
            2 => if y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) { 29 } else { 28 },
            _ => 30,
        }
    };
    let til_dagsnr = |m: u32, d: u32| -> i32 {
        let mut n: i32 = d as i32;
        for mm in 1..m { n += dager_i_mnd(mm, aar) as i32; }
        n
    };
    let paske_nr = til_dagsnr(p_mnd, p_dag);
    let dato_nr  = til_dagsnr(maaned, dag);
    if dato_nr >= paske_nr - 7 && dato_nr <= paske_nr + 1 {
        return Some("paske".into());
    }

    // 17. mai: mai 10–18
    if maaned == 5 && dag >= 10 && dag <= 18 {
        return Some("mai17".into());
    }

    // Sankthans: jun 20–24
    if maaned == 6 && dag >= 20 && dag <= 24 {
        return Some("sankthans".into());
    }

    // Fårikålens dag: siste torsdag i september ± 3 dager
    // Siste torsdag i sept: finn dag 30, gå bakover til torsdag (ukedag 4)
    // Vi beregner siste torsdag ved å se hvilken dag 30. sept er.
    // Bruk Zeller-variant: ukedag for 30. sept i `aar`.
    let sept_30_ukedag = {
        // Tomohiko Sakamoto-algoritme (returnerer 0=søn..6=lør → konverter til 1=man..7=søn)
        let y = if 9 <= 9 { aar - 1 } else { aar }; // september er etter feb → ingen justering
        let y = aar; let m = 9u32; let d = 30u32;
        let t: [i32; 12] = [0,3,2,5,0,3,5,1,4,6,2,4];
        let yr = if m < 3 { y - 1 } else { y };
        let wd = (yr + yr/4 - yr/100 + yr/400 + t[(m-1) as usize] + d as i32) % 7;
        // 0=søn,1=man,...,6=lør → ISO: man=1..søn=7
        let iso = if wd == 0 { 7u32 } else { wd as u32 };
        iso
    };
    // Torsdag=4. Siste torsdag i sept: 30 - (sept_30_ukedag - 4 + 7) % 7
    let diff = (sept_30_ukedag + 7 - 4) % 7;
    let siste_tors = 30u32 - diff;
    let farikaal_nr = til_dagsnr(9, siste_tors);
    if maaned == 9 && (dato_nr - farikaal_nr).abs() <= 3 {
        return Some("farikaal".into());
    }

    // Halloween: okt 24–31
    if maaned == 10 && dag >= 24 {
        return Some("halloween".into());
    }

    // Jul: des 1 – jan 6
    if maaned == 12 && dag >= 1 {
        return Some("jul".into());
    }
    if maaned == 1 && dag <= 6 {
        return Some("jul".into());
    }

    None
}

#[tauri::command]
fn hoytid_aktiv() -> Option<String> {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // Unix-sekunder → dato (ingen chrono-crate)
    // Naiv gregorisk: sekunder siden 1970-01-01
    let dager_siden_epoke = (secs / 86400) as i64;
    // Tomohiko Sakamoto for ukedag (1970-01-01 var torsdag = ISO 4)
    let mut z = dager_siden_epoke + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe/1460 + doe/36524 - doe/146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365*yoe + yoe/4 - yoe/100);
    let mp = (5*doy + 2)/153;
    let d = doy - (153*mp+2)/5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    // ISO ukedag: 1970-01-01=torsdag=4
    let ukedag = ((dager_siden_epoke + 3) % 7 + 1) as u32; // 1=man..7=søn
    hoytid_aktiv_dato(m as u32, d as u32, ukedag, y as i32)
}
```

- [ ] **Step 4: Kjør tester — verifiser at de passerer**

```
cd kokebok-app/src-tauri
cargo test 2>&1 | tail -20
```

Forventet: alle tester PASS (inkl. de nye høytid-testene)

- [ ] **Step 5: Utvid `forside_oppskrifter` med `hoytid`-parameter**

Endre signaturen (linje ~1238):

```rust
#[tauri::command]
fn forside_oppskrifter(
    app: AppHandle,
    typer: Vec<String>,
    #[allow(non_snake_case)] nattFilter: bool,
    hoytid: Option<String>,
) -> Vec<ForsideOppskrift> {
    let conn = match open(&app) {
        Ok(c) => c,
        Err(_) => return vec![],
    };

    // Høytidsmodus: ignorer typer/nattFilter, filtrer på høytid-kolonne
    if let Some(ref h) = hoytid {
        let sql = "SELECT id, navn, tid, bilde FROM oppskrifter \
                   WHERE INSTR(',' || COALESCE(hoytid,'') || ',', ',' || ? || ',') > 0 \
                   ORDER BY RANDOM() LIMIT 20";
        return conn.prepare(sql)
            .and_then(|mut stmt| {
                stmt.query_map([h.as_str()], |row| {
                    Ok(ForsideOppskrift {
                        id: row.get(0)?,
                        navn: row.get(1)?,
                        tid: row.get(2)?,
                        bilde: row.get(3)?,
                    })
                })
                .and_then(|rows| rows.collect())
            })
            .unwrap_or_default();
    }

    if typer.is_empty() {
        return vec![];
    }

    let placeholders = typer.iter().map(|_| "?").collect::<Vec<_>>().join(", ");

    let sql = if nattFilter {
        format!(
            "SELECT id, navn, tid, bilde FROM oppskrifter \
             WHERE type IN ({placeholders}) \
             AND id NOT IN ( \
                 SELECT DISTINCT oppskrift_id FROM trinn \
                 WHERE LOWER(tekst) LIKE '%ovn%' \
                    OR LOWER(tekst) LIKE '%stekepanne%' \
             ) \
             ORDER BY RANDOM() LIMIT 20"
        )
    } else {
        format!(
            "SELECT id, navn, tid, bilde FROM oppskrifter \
             WHERE type IN ({placeholders}) \
             ORDER BY RANDOM() LIMIT 20"
        )
    };

    let params: Vec<&dyn rusqlite::ToSql> = typer.iter().map(|s| s as &dyn rusqlite::ToSql).collect();

    conn.prepare(&sql)
        .and_then(|mut stmt| {
            stmt.query_map(params.as_slice(), |row| {
                Ok(ForsideOppskrift {
                    id: row.get(0)?,
                    navn: row.get(1)?,
                    tid: row.get(2)?,
                    bilde: row.get(3)?,
                })
            })
            .and_then(|rows| rows.collect())
        })
        .unwrap_or_default()
}
```

- [ ] **Step 6: Legg til `hoytid_aktiv` i `invoke_handler` (linje ~1314)**

```rust
        .invoke_handler(tauri::generate_handler![
            get_kategorier,
            hent_oppskrifter,
            hent_oppskrift,
            hent_oppskrifter_by_ids,
            cook_mode,
            ingrediens_forslag,
            hva_kan_jeg_lage,
            generer_matplan,
            about_info,
            forside_oppskrifter,
            hoytid_aktiv,
        ])
```

- [ ] **Step 7: Kompiler og verifiser**

```
cd kokebok-app/src-tauri
cargo test 2>&1 | tail -10
```

Forventet: alle tester PASS, ingen kompileringsfeil

- [ ] **Step 8: Commit**

```
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(hoytid): paaskedag, hoytid_aktiv, utvidet forside_oppskrifter"
```

---

### Task 3: Rust — utvidet `generer_matplan` med sesong-scoring

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs`

**Interfaces:**
- Consumes: `Kandidat`-struct (linje ~870), `score()`-funksjon (linje ~1016), `generer_matplan`-kommando (linje ~1053)
- Produces: `generer_matplan` med ny `hoytid: Option<String>`-parameter og sesong-scoring

- [ ] **Step 1: Legg til `hoytid`-felt på `Kandidat`-struct (linje ~870)**

```rust
struct Kandidat {
    id: i64,
    navn: String,
    type_: String,
    kcal: Option<f64>,
    fett: Option<f64>,
    ingredienser: Vec<String>,
    hoytid: Option<String>,
}
```

- [ ] **Step 2: Hent `hoytid`-kolonne i `kandidater_for_slot` (linje ~904)**

Endre SELECT-setningen fra:
```rust
    let sql = format!(
        "SELECT o.id, o.navn, o.type FROM oppskrifter o \
         WHERE o.type IN ({kat_ph}){diett_where} LIMIT 400"
    );
```

til:

```rust
    let sql = format!(
        "SELECT o.id, o.navn, o.type, o.hoytid FROM oppskrifter o \
         WHERE o.type IN ({kat_ph}){diett_where} LIMIT 400"
    );
```

Endre `query_map`-kallene (linje ~915) fra:
```rust
    let rader = stmt.query_map(refs.as_slice(), |r| {
        Ok((r.get::<_, i64>(0)?, r.get::<_, String>(1)?, r.get::<_, String>(2)?))
    });
```

til:

```rust
    let rader = stmt.query_map(refs.as_slice(), |r| {
        Ok((r.get::<_, i64>(0)?, r.get::<_, String>(1)?, r.get::<_, String>(2)?, r.get::<_, Option<String>>(3)?))
    });
```

Oppdater `basis`-vektoren og den endelige `Kandidat`-konstruksjonen (linje ~925 og ~1011):

```rust
    let mut basis: Vec<(i64, String, String, Option<String>)> = Vec::new();
    for row in rader.filter_map(|r| r.ok()) {
        basis.push(row);
    }
```

og i slutten av funksjonen:

```rust
        let hoytid = ing_map_hoytid.remove(&id).flatten();
        Kandidat { id, navn, type_, kcal, fett, ingredienser, hoytid }
```

Legg til `ing_map_hoytid: HashMap<i64, Option<String>>` som henter `hoytid` fra `basis` (siden vi nå har det fra SELECT):

```rust
    let mut ing_map_hoytid: std::collections::HashMap<i64, Option<String>> =
        basis.iter().map(|(id, _, _, h)| (*id, h.clone())).collect();
```

- [ ] **Step 3: Legg til `hoytid`-parameter i `generer_matplan` (linje ~1053)**

```rust
#[tauri::command]
fn generer_matplan(
    app: AppHandle,
    dagsmaal: i64,
    personer: i64,
    dietter: Option<Vec<String>>,
    laaste: Vec<LaastSlot>,
    #[allow(non_snake_case)] sunnPlan: bool,
    hoytid: Option<String>,
) -> Result<UkeSvar, String> {
```

- [ ] **Step 4: Legg til sesong-scoring i `velg`-closure (linje ~1117)**

Inne i `velg`-closuren, etter `sunnPlan`-justeringen:

```rust
            if sunnPlan && s > 0.0 {
                if k.kcal.map_or(false, |kc| kc > 600.0) {
                    s *= 0.5;
                }
                if let (Some(kc), Some(ft)) = (k.kcal, k.fett) {
                    if kc > 0.0 && (ft * 9.0 / kc) > 0.35 {
                        s *= 0.7;
                    }
                }
            }
            // Sesong-bonus: +50 for høytidsmerket rett
            if let Some(ref h) = hoytid {
                if let Some(ref opp_hoytid) = k.hoytid {
                    if opp_hoytid.split(',').any(|t| t.trim() == h.as_str()) {
                        s += 50.0;
                    }
                }
            }
```

- [ ] **Step 5: Kompiler og verifiser**

```
cd kokebok-app/src-tauri
cargo test 2>&1 | tail -10
```

Forventet: alle tester PASS, ingen kompileringsfeil

- [ ] **Step 6: Commit**

```
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(hoytid): sesong-scoring i generer_matplan"
```

---

### Task 4: Frontend — `aktivHoytid`, høytidsbanner og sesong-toggle

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes:
  - `hoytid_aktiv() -> Option<String>` (Rust, Task 2)
  - `forside_oppskrifter({ typer, nattFilter, hoytid })` — ny `hoytid`-parameter (Task 2)
  - `generer_matplan({ dagsmaal, personer, dietter, laaste, sunnPlan, hoytid })` — ny `hoytid`-parameter (Task 3)
  - Tauri Store `plan.json` nøkkel `"sesong"` (boolean)
- Produces: fungerende UI — høytidsbanner på forsiden, sesong-toggle i matplanleggeren

- [ ] **Step 1: Legg til `aktivHoytid` state og `HOYTID_BANNER`-konstant**

Etter linje ~94 (`let forsideTittel = $state("")`), legg til:

```typescript
  let aktivHoytid = $state<string | null>(null);

  const HOYTID_BANNER: Record<string, string> = {
    jul:       "🎄 Juleoppskrifter",
    paske:     "🐣 Påskeoppskrifter",
    mai17:     "🇳🇴 17. mai-mat",
    sankthans: "🔥 Sankthansmat",
    farikaal:  "🍲 Fårikålens dag",
    halloween: "🎃 Halloweenmat",
    valentins: "❤️ Valentinsmiddag",
  };
```

- [ ] **Step 2: Legg til `planSesong` state**

Etter `let planLaster = $state(false)` (linje ~64):

```typescript
  let planSesong = $state(false);
```

- [ ] **Step 3: Hent `aktivHoytid` og `planSesong` i `onMount`**

Finn `onMount`-blokken (søk på `await lastForside()`). Legg til øverst i `onMount`, før `lastForside()`:

```typescript
    aktivHoytid = await invoke<string | null>("hoytid_aktiv");
```

Last `planSesong` fra Store. Finn der `planDagsmaal` og `planPersoner` lastes fra Store i `onMount` (søk på `plan.json`). Legg til på samme sted:

```typescript
    planSesong = (await planStore.get<boolean>("sesong")) ?? false;
```

- [ ] **Step 4: Oppdater `lastForside()` til å bruke `aktivHoytid`**

Endre `lastForside()` (linje ~334):

```typescript
  async function lastForside() {
    if (aktivHoytid) {
      forsideTittel = HOYTID_BANNER[aktivHoytid] ?? "Sesongmat";
      forsideOppskrifter = await invoke<ForsideOppskrift[]>("forside_oppskrifter", {
        typer: [],
        nattFilter: false,
        hoytid: aktivHoytid,
      });
    } else {
      const sone = nåværendeTidssone();
      forsideTittel = sone.tittel;
      const t = new Date().getHours();
      const nattFilter = (t >= 22 || t < 6) && aboutInfo === null;
      forsideOppskrifter = await invoke<ForsideOppskrift[]>("forside_oppskrifter", {
        typer: sone.typer,
        nattFilter,
        hoytid: null,
      });
    }
  }
```

- [ ] **Step 5: Oppdater `genererPlan()` til å sende `hoytid`**

Endre `genererPlan()` (linje ~358):

```typescript
  async function genererPlan() {
    planLaster = true;
    try {
      const uke = await invoke<Uke>("generer_matplan", {
        dagsmaal: planDagsmaal,
        personer: planPersoner,
        dietter: aktiveDietter,
        laaste: samleLaaste(),
        sunnPlan: aktivtMidjeFilter,
        hoytid: planSesong && aktivHoytid ? aktivHoytid : null,
      });
      plan = uke;
    } catch (e) {
      console.error("generer_matplan feilet:", e);
    } finally {
      planLaster = false;
    }
  }
```

- [ ] **Step 6: Legg til `onPlanSesongChange`-funksjon**

Etter `genererPlan()`:

```typescript
  async function onPlanSesongChange() {
    const store = await load("plan.json");
    await store.set("sesong", planSesong);
    await store.save();
  }
```

- [ ] **Step 7: Legg til sesong-toggle i `plan-kontroll` (linje ~1276)**

Etter `{#if aktiveDietter.length > 0}...{/if}`-blokken og før `<button class="plan-generer"`:

```html
        <label class="plan-toggle {!aktivHoytid ? 'deaktivert' : ''}">
          <input type="checkbox" bind:checked={planSesong}
                 disabled={!aktivHoytid}
                 onchange={onPlanSesongChange} />
          Sesongmeny
        </label>
```

- [ ] **Step 8: Legg til høytidsbanner over forsidegriddet (linje ~1339)**

Endre `forside-header`-blokken:

```html
      <div class="forside-wrap">
        <div class="forside-header">
          <h2 class="forside-tittel">{forsideTittel}</h2>
          {#if !aktivHoytid}
            <p class="forside-undertekst">Forslag til deg akkurat nå</p>
          {/if}
        </div>
```

- [ ] **Step 9: Legg til CSS**

Legg til nederst i `<style>`-blokken:

```css
  .plan-toggle { display: flex; flex-direction: row; align-items: center; gap: 6px; font-size: 0.82rem; color: var(--text-muted); cursor: pointer; }
  .plan-toggle input { width: auto; }
  .plan-toggle.deaktivert { opacity: 0.4; cursor: not-allowed; }
```

- [ ] **Step 10: Verifiser i dev-modus**

```
cd kokebok-app
npm run tauri dev
```

Sjekk:
- Forsiden viser enten høytidsretter (hvis dato er i høytidsvindu) eller tidsbaserte forslag (ellers)
- Matplanleggeren har sesong-toggle — grået ut utenfor høytid, aktiv i høytid
- For manuell test: endre `hoytid_aktiv()` midlertidig til å returnere `Some("jul".into())` og verifiser at forsiden viser juleretter og togglen aktiveres

- [ ] **Step 11: Commit**

```
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(hoytid): aktivHoytid state, høytidsbanner og sesong-toggle"
```

---

### Task 5: Rebygg bundle og push

**Files:**
- `kokebok-app/src-tauri/data/kokt-bundle.db` (regenerert)

**Interfaces:**
- Consumes: oppdatert `kokt.db` med `høytid`-kolonne (Task 1), ny Rust-kode (Task 2+3), ny frontend (Task 4)

- [ ] **Step 1: Rebygg bundle-DB**

```
cd C:\Users\elpud\CODE\kokt.nok
python scripts/bygg_bundle_db.py
```

Forventet: `Ferdig: 5962 bilder innebygd, 0 manglet.`

- [ ] **Step 2: Commit bundle (hvis den er git-tracket) og push**

```
git add kokebok-app/src-tauri/data/kokt-bundle.db data/hoytid_forslag.json
git commit -m "data: rebygg bundle med hoytid-tagging"
git push
```

- [ ] **Step 3: Oppdater IDEER.md**

Merk #6 og #23 som ✅ FERDIG 2026-06-24 i `docs/IDEER.md`:

```
git add docs/IDEER.md
git commit -m "docs(ideer): merk #6 og #23 som ferdig"
git push
```
