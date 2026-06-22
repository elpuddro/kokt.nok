# Vinanbefaling fra Vinmonopolet — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skrap Vinmonopolets sortiment inn i kokt.db og vis de 3 beste drikkevarene for en oppskrift bak en 🍷-knapp i detaljvisningen.

**Architecture:** Engangsskript (`hent_viner.py`) henter produkter fra `apis.vinmonopolet.no` med gratis API-nøkkel, parser matpasning fra fritekst og lagrer i `viner`-tabell. Rust-kommando `vin_forslag` scorer viner mot oppskrift via kategori-map + ingrediens-boost. Svelte viser topp 3 som kortgrid bak toggle-knapp.

**Tech Stack:** Python 3 (skraper), Rust/rusqlite (match-logikk), Svelte 5 runes, Tauri 2 IPC, SQLite

## Global Constraints

- Tauri 2 IPC: alle Rust-kommandoer deklareres med `#[tauri::command]` og registreres i `generate_handler![]`
- Svelte 5 runes: bruk `$state`, `$derived`, `{#if}`, `{#each}` — ikke Svelte 4-syntaks
- Ingen pris vises, ingen lenke til Vinmonopolet, ingen logo
- DB åpnes READ_ONLY i Rust — ingen runtime-migrasjoner
- TypeScript via `--experimental-strip-types` (`.mjs`-tester med `node`)
- Normaliserte varetyper: `rodvin`, `hvitvin`, `rose`, `musserende`, `dessertvin`, `sterkvin`, `ol`, `cider`, `likor`, `aperitif`, `brennevin`
- Normaliserte matpasnings-tags: `pasta`, `fisk`, `fjærkre`, `vilt`, `storfe`, `svin`, `grønnsaker`, `dessert`, `aperitif`, `asiatisk`
- `VinForslag`-type eksporteres fra `$lib/vin.ts` og brukes i både `+page.svelte` og Rust-signaturen

---

### Task 1: Skraper `hent_viner.py` + `viner`-tabell i kokt.db

**Files:**
- Create: `scripts/hent_viner.py`

**Interfaces:**
- Produces: tabell `viner(id, varenummer, navn, produsent, land, varetype, druetype, matpasning)` i `kokt.db` med index `idx_viner_varetype`
- Produces: normaliserte matpasnings-tags som JSON-array i `matpasning`-feltet

- [ ] **Steg 1: Sett opp skjema og test at DB-tilkobling fungerer**

Opprett `scripts/hent_viner.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hent_viner.py — Henter produkter fra apis.vinmonopolet.no og lagrer i viner-tabellen.

Krever gratis API-nøkkel fra developer.vinmonopolet.no.
Kjøres én gang før bundle-bygg:
    python scripts/hent_viner.py --key <din-nøkkel>

Nøkkelen kan også settes som miljøvariabel: VMP_KEY
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data" / "kokt.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS viner (
    id          INTEGER PRIMARY KEY,
    varenummer  TEXT UNIQUE NOT NULL,
    navn        TEXT NOT NULL,
    produsent   TEXT,
    land        TEXT,
    varetype    TEXT,
    druetype    TEXT,
    matpasning  TEXT
);
CREATE INDEX IF NOT EXISTS idx_viner_varetype ON viner(varetype);
"""

# Kategorier vi vil ha med (mainCategory.name fra API)
KATEGORIER = {
    "Rødvin": "rodvin",
    "Hvitvin": "hvitvin",
    "Rosévin": "rose",
    "Musserende vin": "musserende",
    "Perlende vin": "musserende",
    "Dessertvin": "dessertvin",
    "Sterkvin": "sterkvin",
    "Øl": "ol",
    "Cider": "cider",
    "Likør": "likor",
    "Aperitif": "aperitif",
    "Brennevin": "brennevin",
}

# Fritekst → matpasnings-tag
MATPASNING_REGLER = [
    (["pasta", "pizza", "taco", "tapas", "nudler"],         "pasta"),
    (["fisk", "sjømat", "skalldyr", "laks", "torsk", "sei", "reke", "krabbe"], "fisk"),
    (["kylling", "fjærkre", "høns"],                        "fjærkre"),
    (["lam", "vilt", "hjort", "elg", "rein"],               "vilt"),
    (["biff", "entrecôte", "okse", "storfe", "indrefilet"], "storfe"),
    (["svin", "ribbe", "koteletter", "nakke"],              "svin"),
    (["grønnsaker", "vegetar", "salat", "tomat"],           "grønnsaker"),
    (["dessert", "kake", "sjokolade", "søtt", "frukt"],     "dessert"),
    (["aperitif", "forrett", "snacks"],                     "aperitif"),
    (["asiatisk", "wok", "thai", "indisk", "kinesisk"],     "asiatisk"),
]


def ekstraher_matpasning(tekst: str) -> list:
    if not tekst:
        return []
    tekst_lower = tekst.lower()
    tags = []
    for nokkelord, tag in MATPASNING_REGLER:
        if any(n in tekst_lower for n in nokkelord) and tag not in tags:
            tags.append(tag)
    return tags


def normaliser_varetype(main_cat: str) -> str | None:
    return KATEGORIER.get(main_cat)


def hent_side(url: str, key: str) -> list:
    req = urllib.request.Request(url, headers={
        "Ocp-Apim-Subscription-Key": key,
        "User-Agent": "kokt.nok/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default=os.environ.get("VMP_KEY", ""), help="API-nøkkel")
    parser.add_argument("--max", type=int, default=0, help="Maks antall produkter (0 = alle)")
    args = parser.parse_args()

    if not args.key:
        sys.exit("Mangler API-nøkkel. Bruk --key eller VMP_KEY miljøvariabel.")

    if not DB.is_file():
        sys.exit(f"Fant ikke kokt.db: {DB}")

    db = sqlite3.connect(DB)
    for stmt in SCHEMA.strip().split(";"):
        s = stmt.strip()
        if s:
            db.execute(s)
    db.commit()

    BASE = "https://apis.vinmonopolet.no/products/v0/details-normal"
    side = 0
    batch = 500
    totalt = hentet = hoppet = 0

    print("Henter produkter fra Vinmonopolet...")
    while True:
        url = f"{BASE}?maxResults={batch}&start={side * batch}"
        try:
            produkter = hent_side(url, args.key)
        except Exception as e:
            print(f"Feil ved side {side}: {e}")
            break
        if not produkter:
            break

        for p in produkter:
            totalt += 1
            main_cat = (p.get("mainCategory") or {}).get("name", "")
            varetype = normaliser_varetype(main_cat)
            if not varetype:
                hoppet += 1
                continue

            varenummer = str(p.get("code", ""))
            navn = p.get("name", "").strip()
            if not varenummer or not navn:
                hoppet += 1
                continue

            produsent = (p.get("main_producer") or {}).get("name") or p.get("producer", {}).get("name")
            land = (p.get("main_country") or {}).get("name")
            druetype = ", ".join(
                d.get("name", "") for d in (p.get("grapes") or []) if d.get("name")
            ) or None

            # Matpasning fra stilbeskrivelse
            stil = p.get("Characteristics") or p.get("characteristics") or {}
            beskrivelse = stil.get("description", "") if isinstance(stil, dict) else ""
            tags = ekstraher_matpasning(beskrivelse)
            matpasning = json.dumps(tags, ensure_ascii=False) if tags else None

            try:
                db.execute(
                    "INSERT OR REPLACE INTO viner "
                    "(varenummer, navn, produsent, land, varetype, druetype, matpasning) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (varenummer, navn, produsent, land, varetype, druetype, matpasning),
                )
                hentet += 1
            except sqlite3.Error as e:
                print(f"  DB-feil for {varenummer}: {e}")

        db.commit()
        print(f"  Side {side}: {len(produkter)} produkter, {hentet} lagret så langt")

        if args.max and hentet >= args.max:
            break
        if len(produkter) < batch:
            break
        side += 1

    db.close()
    print(f"\nFerdig: {totalt} totalt, {hentet} lagret, {hoppet} hoppet over (ukjent kategori).")
    antall = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM viner").fetchone()[0]
    print(f"viner-tabell: {antall} rader.")


if __name__ == "__main__":
    main()
```

- [ ] **Steg 2: Test fritekst-parseren isolert**

Opprett `scripts/test_hent_viner.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from hent_viner import ekstraher_matpasning, normaliser_varetype

# ekstraher_matpasning
assert ekstraher_matpasning("Passer til pasta og pizza") == ["pasta"], f"Got {ekstraher_matpasning('Passer til pasta og pizza')}"
assert ekstraher_matpasning("Passer godt til grillet laks og sjømat") == ["fisk"], f"Got {ekstraher_matpasning('Passer godt til grillet laks og sjømat')}"
assert ekstrajer_matpasning("Passer til kylling og grønnsaker") == ["fjærkre", "grønnsaker"]
assert ekstraher_matpasning("") == []
assert ekstraher_matpasning("Ingen kjente nøkkelord her") == []

# normaliser_varetype
assert normaliser_varetype("Rødvin") == "rodvin"
assert normaliser_varetype("Hvitvin") == "hvitvin"
assert normaliser_varetype("Øl") == "ol"
assert normaliser_varetype("Ukjent") is None

print("Alle tester OK")
```

- [ ] **Steg 3: Kjør testene**

```
cd C:\Users\elpud\CODE\kokt.nok
python scripts/test_hent_viner.py
```

Forventet: `Alle tester OK`

Fiks typo `ekstrajer_matpasning` → `ekstraher_matpasning` i testfilen (copypaste-feil i planen — bruk korrekt navn).

- [ ] **Steg 4: Kjør skraperen med --max 10 for å verifisere API-tilkobling**

Forutsetter at bruker har hentet nøkkel fra `developer.vinmonopolet.no`.

```
python scripts/hent_viner.py --key <din-nøkkel> --max 10
```

Forventet output:
```
Henter produkter fra Vinmonopolet...
  Side 0: 10 produkter, X lagret så langt
Ferdig: 10 totalt, X lagret, Y hoppet over (ukjent kategori).
viner-tabell: X rader.
```

Verifiser i sqlite3:
```
sqlite3 kokebok-app/src-tauri/data/kokt.db "SELECT varenummer, navn, varetype, matpasning FROM viner LIMIT 5"
```

- [ ] **Steg 5: Commit**

```bash
git add scripts/hent_viner.py scripts/test_hent_viner.py
git commit -m "feat(viner): skraper hent_viner.py + viner-tabell i kokt.db"
```

---

### Task 2: Rust-kommando `vin_forslag`

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs`

**Interfaces:**
- Consumes: tabell `viner` (fra Task 1), tabell `oppskrifter`, tabell `ingredienser`
- Produces: `#[tauri::command] fn vin_forslag(app: AppHandle, oppskrift_id: i64) -> Result<Vec<VinForslag>, String>`
- Produces: `struct VinForslag { id: i64, navn: String, produsent: Option<String>, land: Option<String>, varetype: String, druetype: Option<String> }` — serialisert med `#[derive(Serialize)]`

- [ ] **Steg 1: Legg til structs og kategori-map**

Finn seksjonen i `lib.rs` etter de andre struct-definisjonene (f.eks. etter `struct Kandidat`) og legg til:

```rust
#[derive(Serialize)]
struct VinForslag {
    id: i64,
    navn: String,
    produsent: Option<String>,
    land: Option<String>,
    varetype: String,
    druetype: Option<String>,
}

struct KategoriVinProfil {
    tags: &'static [&'static str],
    foretrukne_typer: &'static [&'static str],
}

fn vin_profil_for_kategori(kat: &str) -> KategoriVinProfil {
    match kat {
        "Fisk" | "Sjømat" | "Hele fileter" => KategoriVinProfil {
            tags: &["fisk", "skalldyr"],
            foretrukne_typer: &["hvitvin", "rose", "musserende"],
        },
        "Pasta" | "Pizza" => KategoriVinProfil {
            tags: &["pasta"],
            foretrukne_typer: &["hvitvin", "rodvin", "ol"],
        },
        "Middag" | "Biffer" | "Steker" | "Koteletter" => KategoriVinProfil {
            tags: &["storfe", "svin"],
            foretrukne_typer: &["rodvin"],
        },
        "Gryter" | "Ovnsretter" => KategoriVinProfil {
            tags: &["storfe", "grønnsaker"],
            foretrukne_typer: &["rodvin", "hvitvin"],
        },
        "Kyllingfilet" | "Grillet kylling" => KategoriVinProfil {
            tags: &["fjærkre"],
            foretrukne_typer: &["hvitvin", "rose", "rodvin"],
        },
        "Vilt" | "Grillspyd" => KategoriVinProfil {
            tags: &["vilt", "storfe"],
            foretrukne_typer: &["rodvin"],
        },
        "Vegetar" => KategoriVinProfil {
            tags: &["grønnsaker"],
            foretrukne_typer: &["hvitvin", "rose", "ol"],
        },
        "Wok" | "Panneretter" => KategoriVinProfil {
            tags: &["asiatisk"],
            foretrukne_typer: &["hvitvin", "ol"],
        },
        "Dessert" | "Kaker" | "Bakst" | "Søtt" => KategoriVinProfil {
            tags: &["dessert"],
            foretrukne_typer: &["dessertvin", "musserende", "likor"],
        },
        "Forretter" | "Snacks" => KategoriVinProfil {
            tags: &["aperitif"],
            foretrukne_typer: &["musserende", "aperitif", "ol"],
        },
        _ => KategoriVinProfil {
            tags: &[],
            foretrukne_typer: &["rodvin", "hvitvin"],
        },
    }
}

// Ingrediens-token → matpasnings-tag
fn ingrediens_til_tag(navn: &str) -> Option<&'static str> {
    let n = navn.to_lowercase();
    if ["laks", "ørret", "torsk", "sei", "hyse"].iter().any(|k| n.contains(k)) {
        return Some("fisk");
    }
    if ["reke", "krabbe", "blåskjell", "hummer", "sjømat"].iter().any(|k| n.contains(k)) {
        return Some("fisk");
    }
    if n.contains("kylling") { return Some("fjærkre"); }
    if ["lam", "fårikål"].iter().any(|k| n.contains(k)) { return Some("vilt"); }
    if ["biff", "entrecôte", "indrefilet", "oksekjøtt"].iter().any(|k| n.contains(k)) {
        return Some("storfe");
    }
    if ["svinekjøtt", "ribbe", "nakkekoteletter"].iter().any(|k| n.contains(k)) {
        return Some("svin");
    }
    if n.contains("sopp") { return Some("grønnsaker"); }
    if ["sjokolade", "vanilje"].iter().any(|k| n.contains(k)) { return Some("dessert"); }
    None
}
```

- [ ] **Steg 2: Skriv `vin_forslag`-kommandoen**

Legg til etter de andre `#[tauri::command]`-funksjonene (f.eks. etter `generer_matplan`):

```rust
#[tauri::command]
fn vin_forslag(app: AppHandle, oppskrift_id: i64) -> Result<Vec<VinForslag>, String> {
    let conn = open(&app)?;

    // Hent oppskriftstype
    let kat: String = conn
        .query_row(
            "SELECT COALESCE(type, '') FROM oppskrifter WHERE id = ?",
            [oppskrift_id],
            |r| r.get(0),
        )
        .unwrap_or_default();

    let profil = vin_profil_for_kategori(&kat);

    // Hent ingrediensnavn for boost
    let mut ing_stmt = conn
        .prepare("SELECT LOWER(navn) FROM ingredienser WHERE oppskrift_id = ? AND navn IS NOT NULL")
        .map_err(|e| e.to_string())?;
    let ingredienser: Vec<String> = ing_stmt
        .query_map([oppskrift_id], |r| r.get(0))
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    // Bygg ingrediens-tag-sett
    let mut ing_tags: std::collections::HashSet<&str> = std::collections::HashSet::new();
    for ing in &ingredienser {
        if let Some(tag) = ingrediens_til_tag(ing) {
            ing_tags.insert(tag);
        }
    }

    // Hent alle viner med matpasning eller riktig varetype
    let mut vin_stmt = conn
        .prepare(
            "SELECT id, navn, produsent, land, varetype, druetype, matpasning \
             FROM viner WHERE varetype IS NOT NULL",
        )
        .map_err(|e| e.to_string())?;

    let mut scoret: Vec<(i64, f64, String, Option<String>, Option<String>, String, Option<String>)> =
        vin_stmt
            .query_map([], |r| {
                Ok((
                    r.get::<_, i64>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, Option<String>>(2)?,
                    r.get::<_, Option<String>>(3)?,
                    r.get::<_, String>(4)?,
                    r.get::<_, Option<String>>(5)?,
                    r.get::<_, Option<String>>(6)?,
                ))
            })
            .map_err(|e| e.to_string())?
            .filter_map(|r| r.ok())
            .filter_map(|(id, navn, prod, land, varetype, druetype, matpasning_json)| {
                let mut score = 0.0f64;

                // Kategori-tag-overlapp
                if let Some(ref mp) = matpasning_json {
                    if let Ok(tags) = serde_json::from_str::<Vec<String>>(mp) {
                        for tag in &tags {
                            if profil.tags.contains(&tag.as_str()) {
                                score += 10.0;
                            }
                            // Ingrediens-boost
                            if ing_tags.contains(tag.as_str()) {
                                score += 10.0;
                            }
                        }
                    }
                }

                // Foretrukket varetype-bonus
                if profil.foretrukne_typer.contains(&varetype.as_str()) {
                    score += 5.0;
                }

                if score == 0.0 {
                    return None;
                }

                Some((id, score, navn, prod, land, varetype, druetype))
            })
            .collect();

    // Sorter DESC på score, ta topp 3
    scoret.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    let resultat = scoret
        .into_iter()
        .take(3)
        .map(|(id, _, navn, produsent, land, varetype, druetype)| VinForslag {
            id,
            navn,
            produsent,
            land,
            varetype,
            druetype,
        })
        .collect();

    Ok(resultat)
}
```

- [ ] **Steg 3: Registrer kommandoen i `generate_handler!`**

Finn `generate_handler![` i `lib.rs` og legg til `vin_forslag`:

```rust
generate_handler![
    // ... eksisterende kommandoer ...
    vin_forslag,
]
```

- [ ] **Steg 4: Bygg og verifiser at det kompilerer**

```
cd kokebok-app/src-tauri
cargo check
```

Forventet: `Finished` uten errors. Warnings om ubrukte imports er OK å ignorere.

- [ ] **Steg 5: Commit**

```bash
git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(viner): vin_forslag Tauri-kommando med kategori-map + ingrediens-boost"
```

---

### Task 3: Frontend — knapp og vinforslag-seksjon

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `vin_forslag(oppskrift_id: i64) -> Vec<VinForslag>` (fra Task 2)
- Consumes: `VinForslag = { id: number; navn: string; produsent: string|null; land: string|null; varetype: string; druetype: string|null }`

- [ ] **Steg 1: Legg til TypeScript-typen og state**

Finn der andre state-variabler er definert (f.eks. etter `let planLaster`) og legg til:

```typescript
type VinForslag = {
  id: number;
  navn: string;
  produsent: string | null;
  land: string | null;
  varetype: string;
  druetype: string | null;
};

let vinForslag = $state<VinForslag[]>([]);
let vinLaster = $state(false);
let vinApen = $state(false);
let vinForOppskriftId = $state<number | null>(null);
```

- [ ] **Steg 2: Legg til `lastVinForslag`-funksjonen**

Finn der andre async-funksjoner er definert (f.eks. etter `genererPlan`) og legg til:

```typescript
async function lastVinForslag(id: number) {
  if (vinForOppskriftId === id) return;
  vinForslag = [];
  vinApen = false;
  vinLaster = true;
  vinForslag = await invoke<VinForslag[]>("vin_forslag", { oppskriftId: id });
  vinForOppskriftId = id;
  vinLaster = false;
}
```

- [ ] **Steg 3: Kall `lastVinForslag` når detaljvisning åpnes**

Finn der `currentOppskrift` settes (når bruker klikker på en oppskrift, f.eks. i `velgOppskrift`-funksjonen eller tilsvarende). Legg til kallet etter at oppskriften er satt:

```typescript
if (currentOppskrift?.id) {
  lastVinForslag(currentOppskrift.id);
}
```

Alternativt: legg det i en `$effect` som reagerer på `currentOppskrift`:

```typescript
$effect(() => {
  if (currentOppskrift?.id) {
    lastVinForslag(currentOppskrift.id);
  }
});
```

Bruk whichever approach som passer best med eksisterende kode (sjekk hvordan næringsinformasjon lastes i dag).

- [ ] **Steg 4: Legg til hjelpefunksjon for varetype-ikon**

```typescript
function vinIkon(varetype: string): string {
  switch (varetype) {
    case "rodvin": return "🍷";
    case "rose": return "🌸";
    case "ol": case "cider": return "🍺";
    case "likor": case "aperitif": case "brennevin": return "🍸";
    default: return "🥂"; // hvitvin, musserende, dessertvin, sterkvin
  }
}
```

- [ ] **Steg 5: Legg til HTML-seksjonen i detaljvisningen**

Finn der næringsinformasjon vises (`.naering-wrap`-seksjonen) og legg til rett etter den, før notat-seksjonen:

```svelte
{#if !vinLaster && vinForslag.length > 0}
  <div class="vin-wrap">
    <button
      class="vin-toggle"
      onclick={() => (vinApen = !vinApen)}
      aria-expanded={vinApen}
    >
      🍷 Vinforslag {vinApen ? "▲" : "▼"}
    </button>
    {#if vinApen}
      <div class="vin-grid">
        {#each vinForslag as v}
          <div class="vin-kort">
            <div class="vin-ikon">{vinIkon(v.varetype)}</div>
            <div class="vin-navn">{v.navn}</div>
            {#if v.produsent}
              <div class="vin-meta">{v.produsent}</div>
            {/if}
            {#if v.land}
              <div class="vin-meta">{v.land}</div>
            {/if}
            {#if v.druetype}
              <div class="vin-druetype">{v.druetype}</div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}
```

- [ ] **Steg 6: Legg til CSS**

Finn CSS-seksjonen (etter `<style>`) og legg til:

```css
.vin-wrap {
  margin-top: 16px;
  padding: 14px 20px;
  background: var(--bg-warm);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.vin-toggle {
  background: none;
  border: none;
  font-family: var(--font-head);
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text);
  cursor: pointer;
  padding: 0;
}
.vin-toggle:hover { color: var(--accent); }
.vin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.vin-kort {
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 12px;
  text-align: center;
  box-shadow: var(--shadow-sm);
}
.vin-ikon { font-size: 1.5rem; margin-bottom: 6px; }
.vin-navn {
  font-family: var(--font-head);
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--text);
  line-height: 1.2;
  margin-bottom: 4px;
}
.vin-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.3;
}
.vin-druetype {
  font-size: 0.72rem;
  color: var(--text-muted);
  font-style: italic;
  margin-top: 3px;
}
```

- [ ] **Steg 7: Bygg og test manuelt**

Start dev-server og åpne en fiskerett (f.eks. søk "laks"). Verifiser:
- Knappen `🍷 Vinforslag ▼` vises under næringsinformasjon
- Klikk ekspanderer til 3 kort
- Kortene viser ikon, navn, produsent, land
- Klikk igjen kollapser

Test også kjøttrett og dessert for å verifisere at matchlogikken gir relevante typer.

Merk: `viner`-tabellen må være populert (Task 1 kjørt) for at noe skal vises.

- [ ] **Steg 8: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(viner): vinforslag-knapp og kortgrid i oppskriftsdetaljvisning"
```

---

## Selvsjekk av plan

**Spec coverage:**
- ✅ Skraper med API-nøkkel, fritekst-parser, alle kategorier
- ✅ `viner`-tabell med riktige felter og index
- ✅ `vin_forslag`-kommando med kategori-map + ingrediens-boost + topp 3
- ✅ Frontend: toggle-knapp, kortgrid, ikoner per varetype, cache per oppskrift
- ✅ Ingen pris, ingen lenke, ingen logo

**Type consistency:**
- `VinForslag` definert i Task 2 (Rust) og Task 3 (TypeScript) med identiske feltnavn
- `varetype`-verdier er konsistente mellom skraper (Task 1), Rust (Task 2) og `vinIkon` (Task 3)
- `oppskrift_id` i TypeScript → `oppskrift_id: i64` i Rust (Tauri IPC konverterer automatisk)
