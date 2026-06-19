# Bilder i databasen — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distribuere appen som to artefakter (binær + én `kokt.db` med bilder innebygd som BLOB), uten løs `bilder/`-mappe.

**Architecture:** Bilder lagres som BLOB i en fat *bundle*-DB generert ved byggtid (Python). Frontend ber om bilder via et Rust custom-protokoll (`kbilde`) som leser BLOB fra DB, med fil-fallback i dev. Kilde-DB (`kokt.db`, kun stier) blir i git; fat-DB er et gitignorert byggartefakt.

**Tech Stack:** Tauri 2.11 (`register_uri_scheme_protocol`, `tauri::http`), Rust/rusqlite, Svelte 5, Python 3 + Pillow (byggskript).

**Spec:** `docs/superpowers/specs/2026-06-15-bilder-i-db-design.md`

**Merk om testing:** Prosjektet har ingen automatisk testsuite. Verifikasjons-portene er `cargo check`, `npm run build`, datasjekk via Python, og manuell e2e (Task 7). Hver task etterlater prosjektet kompilerbart.

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `scripts/recompress_bilder.py` | Rekomprimer `bilder/*.webp` 800→600px q78, in-place | Create |
| `scripts/bygg_bundle_db.py` | Kopier kokt.db → kokt-bundle.db, legg til `bilde_data` BLOB, fyll fra filer | Create |
| `.gitignore` | Ignorer `kokt-bundle.db` | Modify |
| `kokebok-app/src-tauri/src/lib.rs` | Registrer `kbilde`-protokoll + bildehandler (DB-BLOB → fil-fallback) | Modify |
| `kokebok-app/src-tauri/tauri.conf.json` | CSP `img-src` + bundle-ressurser (drop `bilder/`, bruk bundle-DB) | Modify |
| `kokebok-app/src/routes/+page.svelte` | `imgSrc(id)` via `convertFileSrc(.., "kbilde")` | Modify |
| `README.md` | Dokumenter 2-stegs pakkeflyt | Modify |

**Rekkefølge:** dataprep-skript (T1–T2) → Rust-protokoll med fil-fallback (T3, virker i dev uten fat-DB) → frontend (T4, bilder vises i dev via fallback) → bundle/CSP-config (T5) → docs (T6) → manuell e2e (T7).

---

## Task 1: Rekomprimeringsskript (`recompress_bilder.py`)

Skalerer alle bilder 800→600px q78, in-place. Idempotent (hopper over ≤600px).

**Files:**
- Create: `scripts/recompress_bilder.py`

- [ ] **Step 1: Skriv skriptet**

Create `scripts/recompress_bilder.py`:

```python
#!/usr/bin/env python3
"""Rekomprimer kokebok-bildene: skaler lengste side til 600px, WebP q78.

In-place over kokebok-app/src-tauri/data/bilder/*.webp. Idempotent: hopper over
filer som allerede er <= 600px slik at gjentatte kjoringer ikke forringer videre.
Krever Pillow (pip install Pillow).
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow mangler. Kjor: pip install Pillow")

SIDE = 600
KVALITET = 78
BILDER = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data" / "bilder"


def main() -> None:
    if not BILDER.is_dir():
        sys.exit(f"Fant ikke bildekatalog: {BILDER}")
    filer = sorted(BILDER.glob("*.webp"))
    if not filer:
        sys.exit(f"Ingen .webp i {BILDER}")

    endret = hoppet = 0
    for f in filer:
        im = Image.open(f).convert("RGB")
        w, h = im.size
        storst = max(w, h)
        if storst <= SIDE:
            hoppet += 1
            continue
        ny = im.resize(
            (round(w * SIDE / storst), round(h * SIDE / storst)),
            Image.LANCZOS,
        )
        ny.save(f, "WEBP", quality=KVALITET, method=6)
        endret += 1

    print(f"Ferdig: {endret} rekomprimert, {hoppet} hoppet over ({len(filer)} totalt).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Mål størrelse før**

Run (Git Bash):
```bash
du -sh "<repo>/kokebok-app/src-tauri/data/bilder"
```
Expected: ~294 MB. Noter tallet.

- [ ] **Step 3: Kjør skriptet**

Run:
```bash
cd "<repo>" && .venv/Scripts/python.exe scripts/recompress_bilder.py
```
Expected: `Ferdig: 4444 rekomprimert, 0 hoppet over (4444 totalt).`

- [ ] **Step 4: Mål størrelse etter + verifiser dimensjon**

Run:
```bash
du -sh "<repo>/kokebok-app/src-tauri/data/bilder"
cd "<repo>" && .venv/Scripts/python.exe -c "from PIL import Image; import glob; f=sorted(glob.glob('kokebok-app/src-tauri/data/bilder/*.webp'))[0]; print(Image.open(f).size)"
```
Expected: ~197 MB; dimensjon `(600, 600)`.

- [ ] **Step 5: Verifiser idempotens**

Run:
```bash
cd "<repo>" && .venv/Scripts/python.exe scripts/recompress_bilder.py
```
Expected: `Ferdig: 0 rekomprimert, 4444 hoppet over (4444 totalt).`

- [ ] **Step 6: Commit**

(Kun skriptet — `bilder/` er gitignorert, så de rekomprimerte filene committes ikke.)
```bash
cd "<repo>" && git add scripts/recompress_bilder.py
git commit -m "feat(bilder): rekomprimeringsskript 800->600px q78"
```

---

## Task 2: Bundle-DB-skript (`bygg_bundle_db.py`)

Kopierer kilde-DB, legger til `bilde_data BLOB`, fyller fra `bilder/{slug}.webp`. Verifiserer at alle rader fikk bytes.

**Files:**
- Create: `scripts/bygg_bundle_db.py`
- Modify: `.gitignore`

- [ ] **Step 1: Ignorer fat-DB i git**

I `.gitignore`, legg til en linje etter `kokebok-app/src-tauri/data/bilder/` (linje ~13):
```
kokebok-app/src-tauri/data/kokt-bundle.db
```

- [ ] **Step 2: Skriv skriptet**

Create `scripts/bygg_bundle_db.py`:

```python
#!/usr/bin/env python3
"""Bygg en distribuerbar kokt-bundle.db med bildene innebygd som BLOB.

Kopierer data/kokt.db -> data/kokt-bundle.db (rorer aldri git-kilden), legger
til kolonnen bilde_data BLOB pa oppskrifter, og fyller den fra bilder/{slug}.webp.
Kjor scripts/recompress_bilder.py forst hvis du vil ha 600px-bilder.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "kokebok-app" / "src-tauri" / "data"
KILDE = DATA / "kokt.db"
BUNDLE = DATA / "kokt-bundle.db"
BILDER = DATA / "bilder"


def main() -> None:
    if not KILDE.is_file():
        sys.exit(f"Fant ikke kilde-DB: {KILDE}")
    if BUNDLE.exists():
        BUNDLE.unlink()
    shutil.copy2(KILDE, BUNDLE)

    db = sqlite3.connect(BUNDLE)
    cols = [r[1] for r in db.execute("PRAGMA table_info(oppskrifter)")]
    if "bilde_data" not in cols:
        db.execute("ALTER TABLE oppskrifter ADD COLUMN bilde_data BLOB")

    rader = db.execute("SELECT id, slug FROM oppskrifter").fetchall()
    fylt = mangler = 0
    for opp_id, slug in rader:
        sti = BILDER / f"{slug}.webp"
        if not sti.is_file():
            mangler += 1
            print(f"  ADVARSEL: mangler bildefil for slug={slug!r}")
            continue
        db.execute(
            "UPDATE oppskrifter SET bilde_data = ? WHERE id = ?",
            (sqlite3.Binary(sti.read_bytes()), opp_id),
        )
        fylt += 1
    db.commit()

    # Verifikasjon: ingen rader uten BLOB (gitt at filene fantes).
    uten = db.execute(
        "SELECT COUNT(*) FROM oppskrifter WHERE bilde_data IS NULL"
    ).fetchone()[0]
    db.close()

    storrelse_mb = BUNDLE.stat().st_size / 1024 / 1024
    print(f"Ferdig: {fylt} bilder innebygd, {mangler} manglet.")
    print(f"kokt-bundle.db: {storrelse_mb:.0f} MB, {uten} rader uten bilde_data.")
    if mangler or uten:
        sys.exit("FEIL: noen rader mangler bilde_data — sjekk advarsler over.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Kjør skriptet**

Run:
```bash
cd "<repo>" && .venv/Scripts/python.exe scripts/bygg_bundle_db.py
```
Expected: `Ferdig: 4444 bilder innebygd, 0 manglet.` og `kokt-bundle.db: ~197 MB, 0 rader uten bilde_data.`

- [ ] **Step 4: Verifiser at BLOB-er er gyldige WebP**

Run:
```bash
cd "<repo>" && .venv/Scripts/python.exe -c "
import sqlite3, io
from PIL import Image
db = sqlite3.connect('kokebok-app/src-tauri/data/kokt-bundle.db')
for r in db.execute('SELECT slug, bilde_data FROM oppskrifter LIMIT 3'):
    im = Image.open(io.BytesIO(r[1]))
    print(r[0], im.format, im.size)
"
```
Expected: 3 linjer, `WEBP (600, 600)` (eller proporsjonalt).

- [ ] **Step 5: Bekreft at fat-DB er gitignorert**

Run:
```bash
cd "<repo>" && git check-ignore kokebok-app/src-tauri/data/kokt-bundle.db
```
Expected: stien skrives ut (= ignorert).

- [ ] **Step 6: Commit**

```bash
cd "<repo>" && git add scripts/bygg_bundle_db.py .gitignore
git commit -m "feat(bilder): bygg_bundle_db-skript + gitignore fat-DB"
```

---

## Task 3: Rust `kbilde`-protokoll (DB-BLOB → fil-fallback)

Registrer custom-protokoll. Handler leser id fra request-sti, prøver `bilde_data` fra DB (release), faller tilbake til `bilder/{slug}.webp` (dev). Bom → 404.

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (imports øverst; ny helper før `run()`; `register_uri_scheme_protocol` i `run()` ~linje 348-349)

- [ ] **Step 1: Legg til imports**

I `kokebok-app/src-tauri/src/lib.rs`, etter `use std::path::PathBuf;` (linje 7), legg til:
```rust
use std::fs;
```

- [ ] **Step 2: Legg til bildehandler-helper**

I samme fil, rett FØR `#[cfg_attr(mobile, tauri::mobile_entry_point)]`, legg til. Denne returnerer `Vec<u8>` (bytene) eller `None` (404):

```rust
// ─── Bildebytes: DB-BLOB (release) med fil-fallback (dev) ──────────────────────
fn bilde_bytes(app: &AppHandle, id: i64) -> Option<Vec<u8>> {
    let conn = open(app).ok()?;

    // Prøv BLOB fra DB. Kolonnen bilde_data finnes bare i den genererte
    // bundle-DB-en; i dev (sti-DB) finnes den ikke, da gir prepare() feil og vi
    // faller gjennom til fil-fallback.
    if let Ok(mut stmt) = conn.prepare("SELECT bilde_data FROM oppskrifter WHERE id = ?") {
        if let Ok(Some(bytes)) = stmt.query_row([id], |r| r.get::<_, Option<Vec<u8>>>(0)) {
            if !bytes.is_empty() {
                return Some(bytes);
            }
        }
    }

    // Fil-fallback: slå opp slug → les bilder/{slug}.webp fra disk.
    let slug: String = conn
        .query_row("SELECT slug FROM oppskrifter WHERE id = ?", [id], |r| r.get(0))
        .ok()?;
    for base in bilde_kataloger(app) {
        let sti = base.join(format!("{slug}.webp"));
        if let Ok(bytes) = fs::read(&sti) {
            return Some(bytes);
        }
    }
    None
}

// Mulige bilder/-kataloger (release-ressurs + dev-stier), samme mønster som db_path.
fn bilde_kataloger(app: &AppHandle) -> Vec<PathBuf> {
    let mut ut = Vec::new();
    if let Ok(p) = app
        .path()
        .resolve("bilder", tauri::path::BaseDirectory::Resource)
    {
        ut.push(p);
    }
    if let Ok(cwd) = std::env::current_dir() {
        ut.push(cwd.join("data").join("bilder"));
        ut.push(cwd.join("src-tauri").join("data").join("bilder"));
    }
    ut
}
```

- [ ] **Step 3: Registrer protokollen i `run()`**

I `run()`, mellom `.plugin(tauri_plugin_store::Builder::default().build())` og `.invoke_handler(...)`, legg til:

```rust
        .register_uri_scheme_protocol("kbilde", |ctx, request| {
            // URL: kbilde://localhost/{id} (convertFileSrc lager plattform-riktig form).
            // Siste sti-segment er id-en.
            let path = request.uri().path();
            let id: Option<i64> = path.trim_matches('/').parse().ok();
            let app = ctx.app_handle();
            match id.and_then(|i| bilde_bytes(app, i)) {
                Some(bytes) => tauri::http::Response::builder()
                    .status(200)
                    .header(tauri::http::header::CONTENT_TYPE, "image/webp")
                    .body(bytes)
                    .unwrap(),
                None => tauri::http::Response::builder()
                    .status(404)
                    .body(Vec::new())
                    .unwrap(),
            }
        })
```

- [ ] **Step 4: Kompiler**

Run:
```bash
cd "<repo>/kokebok-app/src-tauri" && cargo check
```
Expected: `Finished` uten feil. (Hvis `ctx.app_handle()` gir type-/lånefeil, bruk `let app = ctx.app_handle().clone();` og `bilde_bytes(&app, i)`.)

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(bilder): kbilde custom-protokoll med DB-BLOB og fil-fallback"
```

---

## Task 4: Frontend `imgSrc(id)`

Bytt fra asset-sti til `kbilde`-protokoll via `convertFileSrc`. Bruker id, ikke `bilde`-sti.

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (`imgSrc` ~linje 40-46; kallesteder kort ~318 og detalj-hero ~381)

- [ ] **Step 1: Skriv om `imgSrc`**

I `kokebok-app/src/routes/+page.svelte`, erstatt hele funksjonen (linje 40-46):
```ts
  function imgSrc(bilde: string | null | undefined): string | null {
    if (!bilde) return null;
    if (bilde.startsWith("http")) return bilde;
    if (!resourceDir) return null;
    const rel = bilde.replace(/\\/g, "/");
    return convertFileSrc(`${resourceDir}/${rel}`);
  }
```
med:
```ts
  // Bilder serveres fra databasen via kbilde-protokollen (se lib.rs).
  // convertFileSrc lager den plattform-riktige URL-en (http://kbilde.localhost/… på Windows).
  function imgSrc(id: number | null | undefined): string | null {
    if (id == null) return null;
    return convertFileSrc(String(id), "kbilde");
  }
```

- [ ] **Step 2: Oppdater kall på kortet**

I recipe-card finnes `imgSrc(r.bilde)` to ganger (linje ~318-320):
```svelte
              {#if imgSrc(r.bilde)}
                <img src={imgSrc(r.bilde)} alt={r.navn} loading="lazy" />
```
Endre begge til `imgSrc(r.id)`:
```svelte
              {#if imgSrc(r.id)}
                <img src={imgSrc(r.id)} alt={r.navn} loading="lazy" />
```

- [ ] **Step 3: Oppdater kall i detalj-hero**

I `.detail-hero` finnes `imgSrc(opp.bilde)` to ganger (linje ~381-383):
```svelte
        {#if imgSrc(opp.bilde)}
          <img src={imgSrc(opp.bilde)} alt={opp.navn} />
```
Endre begge til `imgSrc(opp.id)`:
```svelte
        {#if imgSrc(opp.id)}
          <img src={imgSrc(opp.id)} alt={opp.navn} />
```

- [ ] **Step 4: Bygg**

Run:
```bash
cd "<repo>/kokebok-app" && npm run build
```
Expected: `✓ built` uten feil.

- [ ] **Step 5: Sjekk om `resourceDir`/`resolveResource` er blitt dødt**

Run:
```bash
cd "<repo>" && grep -n "resourceDir\|resolveResource" kokebok-app/src/routes/+page.svelte
```
Forventet: kun tilordningene (`let resourceDir`, `import { resolveResource }`, `resourceDir = await resolveResource("")`) gjenstår, ingen *lesere*. Hvis ingen leser `resourceDir` lenger: fjern importlinjen `import { resolveResource } from "@tauri-apps/api/path";`, `let resourceDir = $state("");`, og linjen `resourceDir = await resolveResource("");` i `onMount`. Bygg på nytt (`npm run build`) og bekreft `✓ built`. Hvis `resourceDir` fortsatt leses et annet sted, la alt stå.

- [ ] **Step 6: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(bilder): imgSrc via kbilde-protokoll (id i stedet for sti)"
```

---

## Task 5: Bundle-config + CSP

Tillat `kbilde` i CSP `img-src`; bytt bundle til fat-DB og dropp `bilder/`-ressursen + asset-scope.

**Files:**
- Modify: `kokebok-app/src-tauri/tauri.conf.json`

- [ ] **Step 1: Oppdater CSP `img-src`**

I `kokebok-app/src-tauri/tauri.conf.json`, i `app.security.csp` (linje 24), endre `img-src`-delen fra:
```
img-src 'self' asset: http://asset.localhost https://asset.localhost data:;
```
til (legg til kbilde-vertene; behold `data:` for placeholdere):
```
img-src 'self' kbilde: http://kbilde.localhost https://kbilde.localhost data:;
```
Slik at hele `csp`-strengen blir:
```json
      "csp": "default-src 'self'; img-src 'self' kbilde: http://kbilde.localhost https://kbilde.localhost data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:",
```

- [ ] **Step 2: Fjern asset-protokoll-blokken**

I samme fil, fjern hele `assetProtocol`-blokken (linje 25-28) siden bilder ikke lenger serveres via asset-protokollen. `security`-objektet skal da kun inneholde `csp`:
```json
    "security": {
      "csp": "default-src 'self'; img-src 'self' kbilde: http://kbilde.localhost https://kbilde.localhost data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:"
    }
```

- [ ] **Step 3: Bytt bundle-ressurser til fat-DB**

I `bundle.resources` (linje 34-37), endre fra:
```json
    "resources": {
      "data/kokt.db": "kokt.db",
      "data/bilder/": "bilder/"
    },
```
til (bundle fat-DB-en som `kokt.db`; ingen `bilder/`-mappe):
```json
    "resources": {
      "data/kokt-bundle.db": "kokt.db"
    },
```

- [ ] **Step 4: Verifiser at JSON er gyldig**

Run:
```bash
cd "<repo>" && .venv/Scripts/python.exe -c "import json; json.load(open('kokebok-app/src-tauri/tauri.conf.json')); print('gyldig JSON')"
```
Expected: `gyldig JSON`.

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add kokebok-app/src-tauri/tauri.conf.json
git commit -m "feat(bilder): CSP for kbilde + bundle fat-DB, dropp bilder-ressurs"
```

---

## Task 6: Dokumenter pakkeflyt i README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Finn et passende sted**

Run:
```bash
cd "<repo>" && grep -n "tauri build\|## Bygg\|## Build\|pakking\|distribu" README.md
```
Bruk treffet for byggseksjonen som ankerpunkt (eller slutten av fila hvis ingen byggseksjon finnes).

- [ ] **Step 2: Legg til pakkeseksjon**

Legg til (tilpass overskriftsnivå til README-stilen):
```markdown
## Pakking til distribusjon (2 steg)

Bildene ligger som løse WebP under `kokebok-app/src-tauri/data/bilder/` i
utvikling, men pakkes inn i databasen for distribusjon, slik at sluttbygget kun
er to filer: app-binæren + én `kokt.db`.

1. **Bygg bundle-databasen** (engangs per bildeendring):
   ```bash
   # valgfritt: rekomprimer bildene 800→600px først (sparer ~33 % plass)
   .venv/Scripts/python.exe scripts/recompress_bilder.py
   # generer kokt-bundle.db med bildene innebygd som BLOB
   .venv/Scripts/python.exe scripts/bygg_bundle_db.py
   ```
2. **Bygg appen:**
   ```bash
   cd kokebok-app && npm run tauri build
   ```
   `tauri.conf.json` bundler `kokt-bundle.db` som `kokt.db`. Ingen `bilder/`-mappe
   følger med — bildene serveres fra DB-en via `kbilde`-protokollen.

I `npm run tauri dev` finnes ikke `bilde_data`-kolonnen i sti-DB-en, så
bildehandleren faller tilbake til å lese de løse filene fra `data/bilder/`.
```

- [ ] **Step 3: Commit**

```bash
cd "<repo>" && git add README.md
git commit -m "docs(bilder): dokumenter 2-stegs pakkeflyt"
```

---

## Task 7: Manuell ende-til-ende-verifikasjon

Krever kjørende app + et pakket bygg. MANUELT (menneske ved skjermen).

**Files:** ingen (verifikasjon).

- [ ] **Step 1: Dev — fil-fallback**

Run:
```bash
cd "<repo>/kokebok-app" && npm run tauri dev
```
Sjekk:
- Kort-thumbnails vises i rutenettet.
- Åpne en oppskrift → detalj-hero-bildet vises.
- (Dette beviser at `kbilde`-protokollen + fil-fallback virker uten fat-DB.)

- [ ] **Step 2: Pakk et bygg med innebygde bilder**

Run:
```bash
cd "<repo>" && .venv/Scripts/python.exe scripts/recompress_bilder.py && .venv/Scripts/python.exe scripts/bygg_bundle_db.py
cd kokebok-app && npm run tauri build
```
Expected: NSIS-installer bygges uten feil.

- [ ] **Step 3: Installer og verifiser to-artefakt-distribusjon**

- Installer fra `kokebok-app/src-tauri/target/release/bundle/nsis/…`.
- I install-katalogen: bekreft at det kun finnes app-binæren + `kokt.db` (ingen `bilder/`-mappe).
- Start appen: kort-thumbnails + detalj-hero vises (nå fra DB-BLOB, ikke fil).
- Oppskrift uten bilde (om noen): emoji-placeholder vises, ingen krasj.

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** rekomprimering 600px q78 (T1), fat bundle-DB + `bilde_data`
  BLOB + gitignore (T2), `kbilde`-protokoll med DB→fil-fallback (T3), `imgSrc(id)`
  via convertFileSrc (T4), CSP + bundle-config + dropp `bilder/` (T5), README
  2-stegs flyt (T6), manuell e2e inkl. «kun to filer» (T7). Favoritter urørt
  (ingen task — bevisst). Alt i spec-en dekket.
- **Navn/typer konsistente:** kolonne `bilde_data` likt i T2 (Python),  T3 (Rust
  SELECT). Protokollnavn `kbilde` likt i T3 (register), T4 (convertFileSrc), T5
  (CSP). `imgSrc(id)` signatur i T4 brukt med `r.id`/`opp.id`. Fat-DB-navn
  `kokt-bundle.db` likt i T2, T5, README.
- **Verifisert mot kode:** `tauri.conf.json` CSP/resources-linjer (T5) lest fra
  fil. `register_uri_scheme_protocol` synkron-signatur + `tauri::http::Response`
  bekreftet mot Tauri 2.11 (context7). `db_path`-mønster gjenbrukt i
  `bilde_kataloger` (T3). `imgSrc`-kallesteder (kort + hero, hver 2 ganger)
  bekreftet via grep.
- **Kjent risiko (flagget i steg):** `ctx.app_handle()` låne-/clone-detalj (T3
  Step 4 har fallback). WebView2 host-format håndteres av convertFileSrc, ikke
  hardkodet URL.
```
