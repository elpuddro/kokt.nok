# Kosthold- og allergifilter — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La brukeren skjule oppskrifter som ikke passer kostholdet/troen (halal-vennlig, vegetar, vegansk, glutenfri, laktosefri, uten nøtter) via filtre i Innstillinger, drevet av en forhåndsberegnet ingrediens-tagg-tabell.

**Architecture:** Et testet Python-skript klassifiserer ingredienser med kuraterte nøkkelord-regler og fyller en `ingrediens_tagg`-tabell i `kokt.db`. Rust-kommandoen `hent_oppskrifter` får `NOT EXISTS`-betingelser (AND-kombinert) per aktivt filter, så server-side paginering/tellinger forblir korrekte. Frontend lagrer aktive filtre i Tauri Store og viser dem i Innstillinger + en aktiv-indikator.

**Tech Stack:** Python 3 (stdlib + pytest), Rust (rusqlite, Tauri 2), Svelte 5 (runes), TypeScript, Tauri Store.

**Spec:** `docs/superpowers/specs/2026-06-18-kosthold-filter-design.md`

---

## Anker-fakta (verifisert mot kode)

- **Skript-mønster:** `scripts/hent_naering.py` har `_finn_db()` (linje 26-44) som leter etter `kokt.db` (kanonisk: `../kokebok-app/src-tauri/data/kokt.db`). Nytt skript gjenbruker dette mønsteret.
- **Tabell-data:** `ingredienser(navn, raatekst, oppskrift_id, …)`, 8421 distinkte `navn` over 5962 oppskrifter.
- **Rust-spørring:** `hent_oppskrifter` (lib.rs linje 112-180) bygger `conds: Vec<&str>` + `owned: Vec<String>` dynamisk, lager `where_sql`, og bruker samme `filter_refs` for både `COUNT(*)` og `LIMIT/OFFSET`. Diett-betingelser legges inn her.
- **Kommando-registrering:** `tauri::generate_handler![...]` (lib.rs linje 455-460).
- **Store-wrapper-mønster:** `kokebok-app/src/lib/tema.ts` (import `{ load, type Store }`, `FIL`/`NOKKEL`, `hentStore()`, last/sett med try/catch best-effort).
- **Frontend-integrasjon:** `+page.svelte` — `fetchGrid()` (linje 83) kaller `invoke("hent_oppskrifter", { kategori, sok, side, perSide })` (linje 96-97); `onMount` (linje ~351) laster favoritter/handleliste/tema/notater; Innstillinger-visning `{#if currentKategori === "__innst__"}` (linje 509-533) med `<section class="innst-seksjon">`; tema-radioknapp `<label class="tema-valg">` (linje 517-529).
- **Bundle:** `scripts/bygg_bundle_db.py` bruker `shutil.copy2(KILDE, BUNDLE)` (kopierer HELE kokt.db) → `ingrediens_tagg` følger automatisk med; ingen kodeendring trengs, bare re-kjøring.

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `scripts/tagg_ingredienser.py` | Klassifiseringsregler + DB-fylling | Create |
| `scripts/test_tagg_ingredienser.py` | pytest for regel-korrekthet | Create |
| `kokebok-app/src-tauri/src/lib.rs` | `dietter`-param + `NOT EXISTS`-filter i `hent_oppskrifter` | Modify |
| `kokebok-app/src/lib/diett.ts` | Tauri Store-wrapper + `DIETT_FILTRE`-katalog | Create |
| `kokebok-app/src/routes/+page.svelte` | state, Innstillinger-seksjon, aktiv-indikator, fetchGrid-param | Modify |

**Rekkefølge:** klassifiserings-regler+test (T1) → DB-fylling+kjør skript (T2) → Rust-filter (T3) → Store-wrapper (T4) → UI (T5) → bundle+distribusjon-note (T6) → manuell e2e (T7).

---

## Task 1: Klassifiseringsregler + pytest

Ren regel-logikk, ingen DB. TDD: dette er der halal/allergen-korrektheten bor.

**Files:**
- Create: `scripts/tagg_ingredienser.py`
- Create: `scripts/test_tagg_ingredienser.py`

- [ ] **Step 1: Skriv regel-modulen med `tagg_for_tekst`**

Create `scripts/tagg_ingredienser.py` (kun regel-delen i denne tasken; DB-delen kommer i Task 2):
```python
#!/usr/bin/env python3
"""Klassifiser ingredienser til kosthold/allergi-tagger via kuraterte
nøkkelord-regler, og fyll tabellen ingrediens_tagg i kokt.db.

Reglene er bevisst kuraterte og testbare (ikke LLM) fordi halal-korrekthet
krever at de er reviderbare og reproduserbare. Matcher mot ingrediensnavn OG
råtekst (svin gjemmer seg i fritekst som «bacon i terninger»).
"""
import os
import re
import sqlite3
import sys

# Tagg → nøkkelord. ORDGRENSE-tagger (korte/kollisjonsutsatte ord) matches med
# \b…\b; DELSTRENG-tagger (lange entydige ord) matches som ren delstreng.
ORDGRENSE = {
    "alkohol": ["vin", "øl", "rom", "rødvin", "hvitvin", "cognac", "konjakk",
                "likør", "sherry", "marsala", "mirin", "akevitt"],
    "blod":    ["blod"],
    "egg":     ["egg", "eggeplomme", "eggehvite", "majones"],
    "kjott":   ["kjøtt", "kjøttdeig", "kylling", "storfe", "biff", "lam",
                "kalv", "okse", "and", "kalkun", "vilt", "reinsdyr", "pølse",
                "skinke", "bacon", "spekemat"],
    "fisk":    ["fisk", "laks", "ørret", "torsk", "sei", "makrell", "tunfisk",
                "reke", "reker", "skalldyr", "blåskjell", "krabbe", "sild",
                "ansjos", "sardin"],
    "honning": ["honning"],
}
DELSTRENG = {
    "svin":    ["svin", "bacon", "skinke", "spekeskinke", "serrano",
                "prosciutto", "chorizo", "pancetta", "salami", "pepperoni",
                "leverpostei", "ister", "flesk"],
    "gelatin": ["gelatin", "husblas"],
    "melk":    ["melk", "fløte", "kremfløte", "smør", "ost", "parmesan",
                "yoghurt", "rømme", "crème fraîche", "kesam", "cottage"],
    "gluten":  ["hvetemel", "hvete", "bygg", "rug", "semulegryn", "couscous",
                "brød", "pasta", "soyasaus", "ølgjær"],
    "nott":    ["mandel", "hasselnøtt", "valnøtt", "peanøtt", "cashew",
                "pistasj", "pekan", "paranøtt", "nøtt"],
}

# Eksplisitte regler/unntak (false-positive-feller fra spec).
# (frase_som_må_finnes_i_tekst, tagg) — legges til hvis frasen finnes.
EKSTRA = [
    ("vaniljeekstrakt", "alkohol"),   # inneholder alkohol
    ("worcestershire",  "fisk"),      # inneholder ansjos
    ("løpe",            "gelatin"),   # animalsk løpe (tvilsom → tatt med)
    ("rennet",          "gelatin"),
]
# (frase, tagg) som SKAL FJERNES selv om en regel over slo til (unntak).
UNNTAK = [
    ("vineddik",   "alkohol"),   # eddik, ikke alkohol
    ("vindrue",    "alkohol"),
    ("druer",      "alkohol"),
    ("rømme",      "alkohol"),   # «rom» traff ikke pga \b, men sikre uansett
    ("romtemp",    "alkohol"),
    ("aromat",     "alkohol"),
    ("eggplante",  "egg"),       # aubergine
    ("aubergine",  "egg"),
    ("mandel",     "kjott"),     # «and» i mandel
    ("koriander",  "kjott"),
    ("vaniljestang", "kjott"),   # «and» i vaniljestang? nei – men sikre
    ("peanøttsmør", "melk"),     # smør → melk, men dette er nøtt
    ("kakaosmør",  "melk"),      # ikke melk
    ("peanøttsmør", "kjott"),
]


def _norm(s: str) -> str:
    return (s or "").lower().strip()


def tagg_for_tekst(navn: str, raatekst: str = "") -> set:
    """Returner settet av tagger for en ingrediens, basert på navn + råtekst."""
    tekst = _norm(navn) + " " + _norm(raatekst)
    tagger = set()

    for tagg, ord_liste in ORDGRENSE.items():
        for o in ord_liste:
            if re.search(r"\b" + re.escape(o) + r"\b", tekst):
                tagger.add(tagg)
                break

    for tagg, ord_liste in DELSTRENG.items():
        for o in ord_liste:
            if o in tekst:
                tagger.add(tagg)
                break

    for frase, tagg in EKSTRA:
        if frase in tekst:
            tagger.add(tagg)

    for frase, tagg in UNNTAK:
        if frase in tekst:
            tagger.discard(tagg)

    return tagger
```

- [ ] **Step 2: Skriv testene**

Create `scripts/test_tagg_ingredienser.py`:
```python
from tagg_ingredienser import tagg_for_tekst


def test_bacon_er_svin_og_kjott():
    t = tagg_for_tekst("bacon")
    assert "svin" in t and "kjott" in t


def test_rodvin_er_alkohol():
    assert "alkohol" in tagg_for_tekst("rødvin")


def test_vineddik_er_ikke_alkohol():
    assert "alkohol" not in tagg_for_tekst("vineddik")


def test_romme_er_melk_ikke_alkohol():
    t = tagg_for_tekst("rømme")
    assert "melk" in t and "alkohol" not in t


def test_hvetemel_er_gluten():
    assert "gluten" in tagg_for_tekst("hvetemel")


def test_mandel_er_nott_ikke_kjott():
    t = tagg_for_tekst("mandel")
    assert "nott" in t and "kjott" not in t  # «and» i mandel skal ikke telle


def test_kylling_er_kjott():
    assert "kjott" in tagg_for_tekst("kylling")


def test_tofu_har_ingen_tagg():
    assert tagg_for_tekst("tofu") == set()


def test_eggplante_er_ikke_egg():
    assert "egg" not in tagg_for_tekst("eggplante")


def test_raatekst_treffer_svin():
    # navn tomt, men råtekst avslører svin
    assert "svin" in tagg_for_tekst("", "200 g bacon i terninger")


def test_vaniljeekstrakt_er_alkohol():
    assert "alkohol" in tagg_for_tekst("vaniljeekstrakt")


def test_worcestershire_er_fisk():
    assert "fisk" in tagg_for_tekst("worcestershiresaus")


def test_honning_er_honning():
    assert "honning" in tagg_for_tekst("honning")


def test_peanottsmor_er_nott_ikke_melk():
    t = tagg_for_tekst("peanøttsmør")
    assert "nott" in t and "melk" not in t
```

- [ ] **Step 3: Kjør testene, verifiser at de passerer**

Run: `cd "<repo>/scripts" && python -m pytest test_tagg_ingredienser.py -v`
Expected: 14 passed. Hvis en feiler (f.eks. en false-positive-felle), juster ORDGRENSE/UNNTAK i `tagg_ingredienser.py` til alle passerer. IKKE svekk en test for å få grønt — fiks regelen.

- [ ] **Step 4: Commit**

```bash
cd "<repo>" && git add scripts/tagg_ingredienser.py scripts/test_tagg_ingredienser.py
git commit -m "feat(kosthold): klassifiseringsregler + pytest"
```

---

## Task 2: DB-fylling + kjør skriptet

Legg til DB-delen i `tagg_ingredienser.py` og kjør den mot kokt.db.

**Files:**
- Modify: `scripts/tagg_ingredienser.py`

- [ ] **Step 1: Legg til `_finn_db`, skjema og `main`**

Legg til nederst i `scripts/tagg_ingredienser.py` (etter `tagg_for_tekst`):
```python
def _finn_db() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kandidater = [
        os.path.join(script_dir, "..", "kokebok-app", "src-tauri", "data", "kokt.db"),
        os.path.join(script_dir, "kokt.db"),
        os.path.join(os.getcwd(), "kokt.db"),
    ]
    for sti in kandidater:
        sti = os.path.normpath(sti)
        if os.path.exists(sti):
            return sti
    locs = "\n  ".join(os.path.normpath(k) for k in kandidater)
    sys.exit(f"Fant ikke kokt.db. Lette her:\n  {locs}")


SCHEMA = """
CREATE TABLE IF NOT EXISTS ingrediens_tagg (
    navn TEXT NOT NULL,
    tagg TEXT NOT NULL,
    PRIMARY KEY (navn, tagg)
);
CREATE INDEX IF NOT EXISTS idx_tagg_navn ON ingrediens_tagg(navn);
"""


def main() -> None:
    db_sti = _finn_db()
    db = sqlite3.connect(db_sti)
    db.executescript(SCHEMA)
    db.execute("DELETE FROM ingrediens_tagg")  # idempotent: rebygg rent

    # Hent distinkte navn + ALL råtekst per navn (GROUP_CONCAT slår sammen alle
    # forekomster, så «bacon i terninger»-treff i én forekomst teller).
    rader = db.execute(
        "SELECT navn, GROUP_CONCAT(raatekst, ' ') FROM ingredienser "
        "WHERE navn IS NOT NULL AND navn != '' GROUP BY navn"
    ).fetchall()

    antall = 0
    for navn, raatekst in rader:
        # VIKTIG: lagre navnet RÅTT (eksakt som i ingredienser.navn). Joinen i
        # Rust er en eksakt streng-likhet på samme kolonne, så vi unngår at
        # SQLite LOWER() (kun ASCII) og Python .lower() (Æ/Ø/Å) er uenige.
        for tagg in tagg_for_tekst(navn, raatekst or ""):
            db.execute(
                "INSERT OR IGNORE INTO ingrediens_tagg (navn, tagg) VALUES (?, ?)",
                (navn, tagg),
            )
            antall += 1
    db.commit()

    print(f"Klassifiserte {len(rader)} distinkte ingrediensnavn → {antall} tagg-rader.")
    for tagg, c in db.execute(
        "SELECT tagg, COUNT(*) c FROM ingrediens_tagg GROUP BY tagg ORDER BY c DESC"
    ):
        print(f"  {c:5}  {tagg}")
    db.close()


if __name__ == "__main__":
    main()
```

VIKTIG: `INSERT` lagrer det RÅ `navn` (eksakt som i `ingredienser.navn`). Rust-spørringen joiner `t.navn = i.navn` — eksakt streng-likhet på samme kolonne, så ingen normalisering på noen side. (Dette unngår en stillegående bug: SQLite `LOWER()` folder kun ASCII, mens Python `.lower()` folder Æ/Ø/Å — de ville vært uenige, og et svine-/fiske-treff kunne sluppet gjennom ufiltrert.)

- [ ] **Step 2: Verifiser at testene fortsatt passerer (modulen importeres fortsatt rent)**

Run: `cd "<repo>/scripts" && python -m pytest test_tagg_ingredienser.py -v`
Expected: 14 passed (DB-koden kjøres ikke ved import, kun via `main()`).

- [ ] **Step 3: Kjør skriptet mot kokt.db**

Run: `cd "<repo>/scripts" && python tagg_ingredienser.py`
Expected: utskrift «Klassifiserte 8421 distinkte ingrediensnavn → N tagg-rader.» med en fordeling per tagg (kjott/melk/gluten bør være de største). Sanity: `svin`, `alkohol`, `gluten` skal alle ha > 0 rader.

- [ ] **Step 4: Spot-sjekk dataene**

Run:
```bash
cd "<repo>/kokebok-app/src-tauri" && python -c "import sqlite3; c=sqlite3.connect('data/kokt.db'); print('bacon:', sorted(r[0] for r in c.execute(\"SELECT tagg FROM ingrediens_tagg WHERE navn LIKE 'bacon'\"))); print('hvetemel:', sorted(r[0] for r in c.execute(\"SELECT tagg FROM ingrediens_tagg WHERE navn LIKE 'hvetemel'\")))"
```
Expected: `bacon: ['kjott', 'svin']`, `hvetemel: ['gluten']`. (Bruker `LIKE` for å være robust mot store/små bokstaver i lagret navn; selve filter-joinen er eksakt på rått navn.)

- [ ] **Step 5: Commit (kun skriptet — kokt.db er git-sporet binær; sjekk policy)**

```bash
cd "<repo>" && git add scripts/tagg_ingredienser.py
git commit -m "feat(kosthold): DB-fylling av ingrediens_tagg"
```
NB: `kokt.db` endres av skriptet. Sjekk `git status` — hvis kokt.db er sporet og skal committes med den nye tabellen, gjør det i en egen commit: `git add kokebok-app/src-tauri/data/kokt.db && git commit -m "data: ingrediens_tagg i kokt.db"`. Hvis den er gitignorert, hopp over.

---

## Task 3: Rust-filter i `hent_oppskrifter`

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs` (funksjon `hent_oppskrifter`, linje 112-180)

- [ ] **Step 1: Legg til `dietter`-parameter og filter-mapping**

I `hent_oppskrifter`-signaturen (lib.rs ~linje 112-118), legg til en parameter etter `perSide`:
```rust
fn hent_oppskrifter(
    app: AppHandle,
    kategori: Option<String>,
    sok: Option<String>,
    side: Option<i64>,
    #[allow(non_snake_case)] perSide: Option<i64>,
    dietter: Option<Vec<String>>,
) -> Result<ListeSvar, String> {
```

VIKTIG om levetider: `conds` er `Vec<&str>`. De eksisterende betingelsene er
strenglitteraler (`'static`). Våre dynamiske `NOT EXISTS`-strenger må eies av en
variabel som lever lenger enn `conds`. Derfor: deklarer en holder-vektor
`diett_sql: Vec<String>` FØR `conds` brukes til spørringen, bygg strengene inn i
den, og push `&str`-referanser inn i `conds`. (Ingen `Box::leak`, ingen lekkasje.)

Rett etter `let mut owned: Vec<String> = Vec::new();` (linje ~125), legg til
holder-vektoren og helper-mappingen:
```rust
    // Kosthold/allergi-filtre. Eier de dynamiske NOT EXISTS-strengene her så
    // referansene i `conds` lever lenge nok (samme grep som `owned`).
    let mut diett_sql: Vec<String> = Vec::new();

    fn tagger_for(filter_id: &str) -> &'static [&'static str] {
        match filter_id {
            "halal"      => &["svin", "alkohol", "blod", "gelatin"],
            "vegetar"    => &["kjott", "fisk"],
            "vegansk"    => &["kjott", "fisk", "egg", "melk", "gelatin", "honning"],
            "glutenfri"  => &["gluten"],
            "laktosefri" => &["melk"],
            "nott"       => &["nott"],
            _            => &[],
        }
    }
```

Deretter, FØR `let where_sql = …`-blokken (etter sok-blokken som slutter ~linje
144), bygg betingelsene:
```rust
    // Bare aktiver filtrering hvis tagg-tabellen finnes (eldre DB → ingen filtrering).
    let har_tagg_tabell: bool = conn
        .query_row(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ingrediens_tagg'",
            [],
            |_| Ok(true),
        )
        .unwrap_or(false);

    if har_tagg_tabell {
        if let Some(ds) = dietter.as_ref() {
            for id in ds {
                let tagger = tagger_for(id);
                if tagger.is_empty() {
                    continue;
                }
                let placeholders = tagger.iter().map(|_| "?").collect::<Vec<_>>().join(", ");
                // Eksakt streng-join på samme kolonne (ingrediens_tagg.navn lagret
                // RÅTT) — ingen LOWER/TRIM, så ingen ASCII-vs-Æ/Ø/Å-uenighet.
                diett_sql.push(format!(
                    "NOT EXISTS (SELECT 1 FROM ingredienser i \
                     JOIN ingrediens_tagg t ON t.navn = i.navn \
                     WHERE i.oppskrift_id = o.id AND t.tagg IN ({placeholders}))"
                ));
                for tg in tagger {
                    owned.push((*tg).to_string());
                }
            }
        }
    }
    // Push referanser etter at alle strengene er bygd (diett_sql vokser ikke mer).
    for s in &diett_sql {
        conds.push(s.as_str());
    }
```

- [ ] **Step 2: Registrer ingen ny kommando (samme funksjon), bare bygg**

`hent_oppskrifter` er allerede i `generate_handler!`. Ingen registreringsendring trengs.

Run: `cd "<repo>/kokebok-app/src-tauri" && cargo build --features tauri/custom-protocol`
Expected: `Finished` uten feil. (Advarsel om ubrukt `dietter` hvis frontend ikke sender den ennå er OK — den brukes via Tauri sin arg-deserialisering.)

- [ ] **Step 3: Commit**

```bash
cd "<repo>" && git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(kosthold): NOT EXISTS-diettfilter i hent_oppskrifter"
```

---

## Task 4: Store-wrapper `diett.ts`

**Files:**
- Create: `kokebok-app/src/lib/diett.ts`

- [ ] **Step 1: Opprett modulen**

Create `kokebok-app/src/lib/diett.ts`:
```ts
// Aktive kostholdsfiltre persisteres via Tauri Store (som tema.ts). Filter-IDene
// må matche Rust-mappingen `tagger_for` i src-tauri/src/lib.rs.
import { load, type Store } from "@tauri-apps/plugin-store";

export type DiettFilter = { id: string; navn: string; beskrivelse: string };

/** Én kilde til sannhet for UI. Tagg-mappingen ligger i Rust (tagger_for). */
export const DIETT_FILTRE: DiettFilter[] = [
  { id: "halal", navn: "Halal-vennlig (uten åpenbart haram)",
    beskrivelse: "Skjuler svin, alkohol, blod og gelatin. Ikke halal-sertifisering — vanlig kjøtt vises." },
  { id: "vegetar", navn: "Vegetar", beskrivelse: "Skjuler kjøtt og fisk/skalldyr." },
  { id: "vegansk", navn: "Vegansk", beskrivelse: "Skjuler alt animalsk: kjøtt, fisk, egg, melk, gelatin, honning." },
  { id: "glutenfri", navn: "Glutenfri", beskrivelse: "Skjuler hvete, bygg, rug, brød, pasta o.l." },
  { id: "laktosefri", navn: "Laktosefri / melkefri", beskrivelse: "Skjuler melk, fløte, smør, ost o.l." },
  { id: "nott", navn: "Uten nøtter", beskrivelse: "Skjuler mandel, hasselnøtt, peanøtt o.l." },
];

const FIL = "diett.json";
const NOKKEL = "aktive";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

/** Last aktive filter-IDer. Tom liste ved feil. */
export async function diettLast(): Promise<string[]> {
  try {
    const store = await hentStore();
    const v = await store.get<string[]>(NOKKEL);
    return Array.isArray(v) ? v : [];
  } catch (err) {
    console.error("diettLast feilet:", err);
    return [];
  }
}

/** Lagre aktive filter-IDer. Best effort. Returnerer lista (uendret kopi). */
export async function diettSett(aktive: string[]): Promise<string[]> {
  const nytt = [...aktive];
  try {
    const store = await hentStore();
    await store.set(NOKKEL, nytt);
    await store.save();
  } catch (err) {
    console.error("diettSett lagring feilet:", err);
  }
  return nytt;
}
```

- [ ] **Step 2: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil (modulen brukes i Task 5; den kompilerer alene).

- [ ] **Step 3: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/lib/diett.ts
git commit -m "feat(kosthold): Tauri Store-wrapper + filter-katalog"
```

---

## Task 5: UI i `+page.svelte`

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (import ~linje 10; state ~linje 40; onMount ~linje 351; fetchGrid ~linje 96; Innstillinger-seksjon ~linje 531; aktiv-indikator i overskrift; stil)

- [ ] **Step 1: Importer modulen**

Etter `import { notaterLast, notatSett } from "$lib/notater";` (linje ~10), legg til:
```ts
  import { diettLast, diettSett, DIETT_FILTRE } from "$lib/diett";
```

- [ ] **Step 2: Legg til state**

Etter `let notatTimer: any;` (state fra notater-funksjonen, ~linje 40), legg til:
```ts
  let aktiveDietter = $state<string[]>([]);
```

- [ ] **Step 3: Last ved oppstart**

I `onMount`, etter `notater = await notaterLast();` (~linje 354), legg til:
```ts
    aktiveDietter = await diettLast();
```

- [ ] **Step 4: Send dietter med i fetchGrid**

I `fetchGrid()`, i `invoke("hent_oppskrifter", {...})`-kallet (linje ~96-97), legg til `dietter`-feltet:
```ts
        const data: any = await invoke("hent_oppskrifter", {
          kategori: currentKategori, sok, side, perSide, dietter: aktiveDietter,
        });
```

- [ ] **Step 5: Toggle-handler**

Ved de andre funksjonene (f.eks. etter `onNotatInput`), legg til:
```ts
  async function toggleDiett(id: string) {
    const ny = aktiveDietter.includes(id)
      ? aktiveDietter.filter((d) => d !== id)
      : [...aktiveDietter, id];
    aktiveDietter = await diettSett(ny);
    side = 1;
    await fetchGrid();
  }
```

- [ ] **Step 6: Innstillinger-seksjon**

I `__innst__`-visningen, ETTER tema-`<section class="innst-seksjon">...</section>` (slutter ~linje 531), men FØR `</div>` som lukker `#innst-wrap`, legg til:
```svelte
      <section class="innst-seksjon">
        <h2>🍽️ Kosthold og allergier</h2>
        <p class="innst-hint">
          Beste-evne-filtrering basert på ingrediensnavn — ikke en garanti.
          For alvorlige allergier: les alltid den fulle ingredienslista selv.
        </p>
        {#each DIETT_FILTRE as f (f.id)}
          <label class="tema-valg" class:valgt={aktiveDietter.includes(f.id)}>
            <input
              type="checkbox"
              checked={aktiveDietter.includes(f.id)}
              onchange={() => toggleDiett(f.id)}
            />
            <span>{f.navn}</span>
          </label>
        {/each}
      </section>
```

- [ ] **Step 7: Aktiv-indikator i hovedoverskriften**

Finn `<div id="grid-header">` / overskrift-raden (rundt linje 437-449 der `{#if currentKategori === "__innst__"}` velger tittel). Rett etter tittel-blokken, der det er naturlig i header-raden, legg til en pille (plasser den inne i samme rad-container; hvis usikker, legg den rett etter `</h1>`/tittel-elementet):
```svelte
      {#if aktiveDietter.length > 0 && currentKategori !== "__innst__"}
        <button class="diett-pille" onclick={() => (currentKategori = "__innst__")}>
          🍽️ {aktiveDietter.length} {aktiveDietter.length === 1 ? "filter" : "filtre"} aktive
        </button>
      {/if}
```

- [ ] **Step 8: Tom-tilstand-hjelpelinje**

Finn «Ingen oppskrifter funnet»-blokken (`<h3>Ingen oppskrifter funnet</h3>` ~linje 546). Rett etter `<p>Prøv å søke …</p>` (~linje 547), legg til:
```svelte
            {#if aktiveDietter.length > 0}
              <p class="empty-hint">Noen kan være skjult av aktive kostholdsfiltre.</p>
            {/if}
```

- [ ] **Step 9: Stil**

I `<style>`, etter `.tema-valg`-reglene (finn dem; de er nær Innstillinger-stilen), legg til:
```css
  .diett-pille {
    display: inline-flex; align-items: center; gap: 6px;
    margin-left: 12px; padding: 4px 10px;
    background: var(--accent-soft, var(--bg-warm)); color: var(--text);
    border: 1px solid var(--border); border-radius: 20px;
    font-size: 0.82rem; cursor: pointer;
  }
  .diett-pille:hover { border-color: var(--border-focus); }
  .empty-hint { font-size: 0.85rem; opacity: 0.7; margin-top: 6px; }
```

- [ ] **Step 10: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil (pre-eksisterende a11y-advarsel på recipe-card er OK).

- [ ] **Step 11: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(kosthold): Innstillinger-filtre + aktiv-indikator + fetchGrid-param"
```

---

## Task 6: Bundle-DB + distribusjons-note

`bygg_bundle_db.py` kopierer hele kokt.db (`shutil.copy2`), så `ingrediens_tagg` følger automatisk med. Ingen kodeendring — bare re-kjør, og dokumentér løs-tråd-status.

**Files:**
- Modify: `docs/IDEER.md` (oppdater løs-tråd + marker #9/#10)

- [ ] **Step 1: Re-bygg bundle-DB (valgfritt nå; kreves før distribusjon)**

Run: `cd "<repo>/scripts" && python bygg_bundle_db.py`
Expected: «Ferdig: N bilder innebygd». Bundle inneholder nå `ingrediens_tagg`. (Hvis bilder mangler for nye godt.no-oppskrifter, skriptet exit-er nonzero — det er den allerede kjente løse tråden om bundle-data; ikke en del av denne featuren. Noter resultatet.)

- [ ] **Step 2: Oppdater IDEER.md**

I `docs/IDEER.md`, marker idé #9 og #10 som ferdig (erstatt de to blokkene med ferdig-status som peker på spec-en), og oppdater løs-tråd-noten om bundle til å nevne at `ingrediens_tagg` nå må være med. Eksakt tekst for #9/#10-erstatning:
```markdown
9. ~~**Halal/haram-filter**~~ + 10. ~~**Allergi- og diettfilter**~~ — ✅ **FERDIG
   2026-06-18** (samlet). Forhåndsberegnet `ingrediens_tagg`-tabell (kuraterte,
   testede nøkkelord-regler i `scripts/tagg_ingredienser.py`) + `NOT EXISTS`-
   filter i `hent_oppskrifter` + Innstillinger-toggles. Filtre: halal-vennlig,
   vegetar, vegansk, glutenfri, laktosefri, uten nøtter (AND-kombinert).
   Spec: `docs/superpowers/specs/2026-06-18-kosthold-filter-design.md`.
```

- [ ] **Step 3: Commit**

```bash
cd "<repo>" && git add docs/IDEER.md
git commit -m "docs: marker idé #9+#10 (kosthold-filter) som ferdig"
```

---

## Task 7: Manuell ende-til-ende-verifikasjon

Krever kjørende app. MANUELT (menneske).

**Files:** ingen.

- [ ] **Step 1: Kjør appen**

Run: `cd "<repo>/kokebok-app" && npm run tauri dev`

- [ ] **Step 2: Verifiser (sjekkliste)**

- Åpne Innstillinger → ny «🍽️ Kosthold og allergier»-seksjon med 6 avkrysningsbokser + ansvarsfraskrivelse.
- Slå på «Halal-vennlig» → gå til «alle» → oppskrifter med svin/bacon/vin forsvinner; totalteller og sidetall stemmer (ingen tomme sider).
- Legg til «Glutenfri» → enda færre treff (AND).
- En liten «🍽️ N filtre aktive»-pille vises i overskriften; klikk → hopper til Innstillinger.
- Søk samtidig med filter på → begge gjelder.
- Skru av alle filtre → alt tilbake; restart app → valgene består (fra diett.json).
- Sjekk en kjent vegetar-rett vises med vegetar på, og en kjent kjøttrett er borte.

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** tabell+indeks (T2 SCHEMA), klassifiseringsskript+regler (T1-T2),
  tagg-regler m/false-positive-feller (T1 ORDGRENSE/DELSTRENG/EKSTRA/UNNTAK + tester),
  filter-katalog (T4 DIETT_FILTRE + T3 tagger_for — samme innhold), Store-wrapper (T4),
  Rust NOT EXISTS AND-filter m/manglende-tabell-guard (T3), UI Innstillinger-seksjon +
  aktiv-indikator + tom-tilstand + ansvarsfraskrivelse (T5), distribusjon/bundle (T6),
  testing (T1 pytest + T7 e2e). Honning-tagg konsistent (T1 ORDGRENSE, T3 vegansk,
  T4 beskrivelse). Alt dekket.
- **Navn/typer konsistente:** filter-IDer `halal/vegetar/vegansk/glutenfri/laktosefri/nott`
  identiske i `DIETT_FILTRE` (T4) og `tagger_for` (T3). Tagger `svin/alkohol/blod/gelatin/
  kjott/fisk/egg/melk/gluten/nott/honning` identiske i T1-regler og T3-mapping.
  `aktiveDietter`/`toggleDiett`/`diettLast`/`diettSett` konsistent T4→T5.
- **Kritisk join-detalj (bug unngått):** `ingrediens_tagg.navn` lagres RÅTT (eksakt
  som `ingredienser.navn`) i T2; T3-joinen er `t.navn = i.navn` — eksakt streng-likhet
  på samme kolonne. Tidligere utkast brukte `_norm`+`LOWER(TRIM())`, men SQLite `LOWER()`
  folder kun ASCII mens Python `.lower()` folder Æ/Ø/Å → de ville vært uenige og et
  svine-/fiske-treff kunne sluppet ufiltrert gjennom (219 rader har stor bokstav i navn).
  Rått-navn-join fjerner hele bug-klassen. `raatekst` slås sammen med `GROUP_CONCAT` så
  fritekst-treff («bacon i terninger») i en hvilken som helst forekomst teller.
- **Parameter-rekkefølge:** diett-`conds` legges til ETTER kategori/sok-conds, og diett-
  tagg-parametrene pushes til `owned` i samme rekkefølge → posisjonelle `?` stemmer for
  både COUNT og LIST (begge bruker `filter_refs` fra `owned`).
- **Verifisert mot kode:** `hent_oppskrifter` conds/owned-mekanisme, generate_handler,
  tema.ts-wrapper-mønster, Innstillinger-seksjon + tema-valg-label, fetchGrid invoke,
  bygg_bundle_db shutil.copy2 (→ ingen kodeendring for bundle).
- **YAGNI:** binære tagger, 6 filtre, ingen slider/mashbooh. Favoritter urørt.
