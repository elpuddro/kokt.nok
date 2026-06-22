# Lager + «Hva har jeg i kjøleskapet?» — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La brukeren registrere hva de har hjemme (navn + valgfri utløpsdato), få utløpsvarsel, og se oppskrifter rangert etter dekningsgrad («kan lages nå» / «mangler N») i en egen 🧊 Kjøleskap-visning.

**Architecture:** Lager lagres i Tauri Store (`lager.json`, som handleliste.ts). Dekningsgrad-match kjører server-side i Rust (indeksert SQL, gjenbruker `idx_ing_opp_navn`) via to kommandoer. Utløps-klassifisering er ren node-testbar logikk. UI i `__lager__`-sidebar-modus + «Jeg lagde denne»-knapp i detalj.

**Tech Stack:** Svelte 5 (runes), Tauri 2, TypeScript (node-testbar via `--experimental-strip-types`), Rust/rusqlite.

**Spec:** `docs/superpowers/specs/2026-06-19-lager-kjoeleskap-design.md`

> **`<repo>`** = repo-roten (din lokale klone av kokt.nok). Linjenumre kan drifte ±5 — bekreft anker ved å lese før redigering.

---

## Anker-fakta (verifisert mot kode)

- **Staples-kollisjon (KRITISK, verifisert mot DB):** delstreng `mel` fanger
  «melk»/«karamell»/«marmelade» → MÅ IKKE brukes som naken delstreng. `salt`
  kolliderer IKKE med «salat» (salt er ikke delstreng av salat). Løsning:
  staple-match bruker ordgrense (`\bord`) ELLER spesifikke fulle navn. Trygg
  retning: heller en sjelden staple-feilklassifisering enn at melk/karamell blir
  «har alltid».
- **Store-mønster:** `kokebok-app/src/lib/handleliste.ts` (load/get/set/save,
  best-effort, returnerer ny liste). `lager.ts` speiler dette.
- **Ren-logikk-mønster:** `src/lib/tid-parsing.ts` + `.test.mjs` (node, ingen
  Tauri-import, `node --experimental-strip-types`).
- **Sidebar-modus:** `velgFavoritter/velgHandleliste/velgInnstillinger` (linje
  163-180) setter `currentKategori = "__fav__"/"__handle__"/"__innst__"`. Sidebar-
  knapper ~linje 510-536 (Handleliste-knapp 520-528, Innstillinger 529-536).
- **Visnings-blokker:** `{#if currentKategori === "__handle__"}` (584-631) er mal
  for lager-visningen. Flere steder ekskluderer modus-visninger fra grid/header:
  linje 487, 568, 679 (`!== "__handle__" && !== "__innst__"`) — `"__lager__"` må
  legges til i ALLE tre.
- **Header-tittel-blokk:** linje 556-560 (`{#if currentKategori === "__innst__"} ⚙️
  Innstillinger {:else if ... "__handle__"} 🛒 Handleliste ...`).
- **onMount:** linje 462-471 (laster favoritter/handleliste/tema/notater/dietter).
- **Detalj-topbar:** linje 753; `.detail-handle` (762), `.detail-cook` (768) — «Jeg
  lagde denne» legges her. `{@const opp = currentOppskrift}` linje 746.
- **Rust generate_handler:** lib.rs 633-639 (`...hent_oppskrifter_by_ids, cook_mode`).
  `query_json`-helper + `idx_ing_opp_navn` finnes. `åpneOppskrift(id)` finnes i frontend.

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src/lib/lager-logikk.ts` | `utlopsStatus(utloper, idag)` ren logikk | Create |
| `kokebok-app/src/lib/lager-logikk.test.mjs` | node-tester | Create |
| `kokebok-app/src/lib/lager.ts` | Tauri Store-wrapper (`lager.json`) | Create |
| `kokebok-app/src-tauri/src/lib.rs` | `ingrediens_forslag` + `hva_kan_jeg_lage` + staples | Modify |
| `kokebok-app/src/routes/+page.svelte` | `__lager__`-visning, autocomplete, forslag, «Jeg lagde denne» | Modify |

**Rekkefølge:** ren logikk (T1) → Store-wrapper (T2) → Rust-kommandoer (T3) → sidebar+visning (T4) → autocomplete+forslag+fratrekk (T5) → manuell e2e (T6).

---

## Task 1: Utløps-logikk `lager-logikk.ts` (ren, TDD)

**Files:**
- Create: `kokebok-app/src/lib/lager-logikk.ts`
- Create: `kokebok-app/src/lib/lager-logikk.test.mjs`

- [ ] **Step 1: Skriv testene**

Create `kokebok-app/src/lib/lager-logikk.test.mjs`:
```js
import { utlopsStatus } from "./lager-logikk.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

const I = "2026-06-19"; // "idag" i testene
sjekk("null dato → null", () => assert.equal(utlopsStatus(null, I), null));
sjekk("i går → utgått", () => assert.equal(utlopsStatus("2026-06-18", I), "utgått"));
sjekk("i dag → snart", () => assert.equal(utlopsStatus("2026-06-19", I), "snart"));
sjekk("om 3 dager → snart (grense)", () => assert.equal(utlopsStatus("2026-06-22", I), "snart"));
sjekk("om 4 dager → ok", () => assert.equal(utlopsStatus("2026-06-23", I), "ok"));
sjekk("langt fram → ok", () => assert.equal(utlopsStatus("2026-12-01", I), "ok"));
sjekk("tom streng → null", () => assert.equal(utlopsStatus("", I), null));

console.log(`\n${ok} tester ok`);
```

- [ ] **Step 2: Kjør, bekreft FAIL**

Run: `cd "<repo>/kokebok-app/src/lib" && node --experimental-strip-types lager-logikk.test.mjs`
Expected: FAIL (`utlopsStatus` finnes ikke).

- [ ] **Step 3: Implementer**

Create `kokebok-app/src/lib/lager-logikk.ts`:
```ts
// Ren, node-testbar logikk (ingen Tauri-import). Klassifiserer utløpsdato.
export type UtlopsStatus = "utgått" | "snart" | "ok" | null;

/** Status for en vares utløpsdato relativt til idag (begge ISO "YYYY-MM-DD").
 *  null hvis ingen dato. «snart» = utgår innen 3 dager (inkl. i dag/forbi-grense). */
export function utlopsStatus(utloper: string | null, idag: string): UtlopsStatus {
  if (!utloper) return null;
  const u = Date.parse(utloper + "T00:00:00");
  const d = Date.parse(idag + "T00:00:00");
  if (Number.isNaN(u) || Number.isNaN(d)) return null;
  const dager = Math.round((u - d) / 86_400_000);
  if (dager < 0) return "utgått";
  if (dager <= 3) return "snart";
  return "ok";
}
```

- [ ] **Step 4: Kjør, bekreft PASS**

Run: `cd "<repo>/kokebok-app/src/lib" && node --experimental-strip-types lager-logikk.test.mjs`
Expected: `7 tester ok`, exit 0.

- [ ] **Step 5: Commit**
```bash
cd "<repo>" && git add kokebok-app/src/lib/lager-logikk.ts kokebok-app/src/lib/lager-logikk.test.mjs
git commit -m "feat(lager): utløps-status (ren logikk) + node-tester"
```

---

## Task 2: Store-wrapper `lager.ts`

**Files:**
- Create: `kokebok-app/src/lib/lager.ts`

- [ ] **Step 1: Opprett modulen**

Create `kokebok-app/src/lib/lager.ts`:
```ts
// Lageret persisteres i lager.json via Tauri Store (samme mønster som
// handleliste.ts). kokt.db er read-only.
import { load, type Store } from "@tauri-apps/plugin-store";

export type LagerVare = { navn: string; utloper: string | null };

const FIL = "lager.json";
const NOKKEL = "varer";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

async function lagre(varer: LagerVare[]): Promise<void> {
  try {
    const store = await hentStore();
    await store.set(NOKKEL, varer);
    await store.save();
  } catch (err) {
    console.error("lager lagring feilet:", err);
  }
}

/** Last lageret. Tom liste ved feil. */
export async function lagerLast(): Promise<LagerVare[]> {
  try {
    const store = await hentStore();
    return (await store.get<LagerVare[]>(NOKKEL)) ?? [];
  } catch (err) {
    console.error("lagerLast feilet:", err);
    return [];
  }
}

/** Legg til en vare (dedup på navn, case-insensitivt). Returnerer ny liste. */
export async function lagerLeggTil(
  navn: string, utloper: string | null, liste: LagerVare[],
): Promise<LagerVare[]> {
  const rent = navn.trim();
  if (!rent) return liste;
  const finnes = liste.some((v) => v.navn.toLowerCase() === rent.toLowerCase());
  const ny = finnes
    ? liste.map((v) => (v.navn.toLowerCase() === rent.toLowerCase() ? { navn: rent, utloper } : v))
    : [...liste, { navn: rent, utloper }];
  await lagre(ny);
  return ny;
}

/** Fjern én vare (på navn, case-insensitivt). Returnerer ny liste. */
export async function lagerFjern(navn: string, liste: LagerVare[]): Promise<LagerVare[]> {
  const ny = liste.filter((v) => v.navn.toLowerCase() !== navn.toLowerCase());
  await lagre(ny);
  return ny;
}

/** Tøm lageret. Returnerer tom liste. */
export async function lagerTøm(): Promise<LagerVare[]> {
  await lagre([]);
  return [];
}
```

- [ ] **Step 2: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` (brukes i T4/T5; kompilerer alene).

- [ ] **Step 3: Commit**
```bash
cd "<repo>" && git add kokebok-app/src/lib/lager.ts
git commit -m "feat(lager): Tauri Store-wrapper"
```

---

## Task 3: Rust-kommandoer `ingrediens_forslag` + `hva_kan_jeg_lage`

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs`

- [ ] **Step 1: Legg til kommandoene + staples**

I `lib.rs`, rett FØR `// ─── Kommando: kategorier`-blokken (eller ved de andre
`#[tauri::command]`-funksjonene), legg til:
```rust
// ─── Lager / «hva kan jeg lage» ─────────────────────────────────────────────────
// Staples = «har alltid», teller verken som dekket eller mangel.
// VIKTIG (verifisert mot DB): naken delstreng «mel» fanger «melk»/«karamell»/
// «marmelade» → forbudt. Vi bruker EKSAKT ord-match mot en utvidet staple-liste,
// pluss en trygg suffiks-sjekk KUN for «olje»/«salt»/«pepper» (disse tre har
// ingen melk-lignende kollisjon). «melk»/«melkesjokolade»/«eplemost» = IKKE staple.
fn er_staple(navn_lower: &str) -> bool {
    const STAPLE_ORD: &[&str] = &[
        "salt", "pepper", "vann", "sukker", "smør",
        "hvetemel", "rugmel", "sammalt", "semulegryn", "melis",
        "olje", "olivenolje", "rapsolje", "solsikkeolje", "maisolje", "frityrolje",
        "nøytral", "kvernet", "flaksalt", "havsalt", "grovsalt",
    ];
    let ord: Vec<&str> = navn_lower
        .split(|c: char| !c.is_alphabetic())
        .filter(|w| !w.is_empty())
        .collect();
    if ord.iter().any(|w| STAPLE_ORD.contains(w)) {
        return true;
    }
    // Trygge suffikser (sammensatt som ETT ord): «xolje»/«xsalt»/«xpepper».
    ord.iter().any(|w| {
        (w.ends_with("olje") || w.ends_with("salt") || w.ends_with("pepper")) && w.len() > 4
    })
}

#[tauri::command]
fn ingrediens_forslag(app: AppHandle, prefiks: String) -> Result<Vec<String>, String> {
    let p = prefiks.trim().to_lowercase();
    if p.len() < 2 {
        return Ok(vec![]);
    }
    let conn = open(&app)?;
    // Prioriter de som STARTER med prefikset, så de som inneholder det.
    let mut stmt = conn
        .prepare(
            "SELECT DISTINCT navn FROM ingredienser \
             WHERE navn IS NOT NULL AND LOWER(navn) LIKE ?1 \
             ORDER BY CASE WHEN LOWER(navn) LIKE ?2 THEN 0 ELSE 1 END, navn COLLATE NOCASE \
             LIMIT 10",
        )
        .map_err(|e| e.to_string())?;
    let inneholder = format!("%{p}%");
    let starter = format!("{p}%");
    let rader = stmt
        .query_map([&inneholder, &starter], |r| r.get::<_, String>(0))
        .map_err(|e| e.to_string())?;
    Ok(rader.filter_map(|r| r.ok()).collect())
}

#[derive(Serialize)]
struct Forslag {
    id: i64,
    navn: String,
    #[serde(rename = "type")]
    type_: Option<String>,
    bilde: Option<String>,
    totalt: i64,
    dekket: i64,
    mangler: Vec<String>,
}

#[tauri::command]
fn hva_kan_jeg_lage(app: AppHandle, varer: Vec<String>) -> Result<Vec<Forslag>, String> {
    let varer: Vec<String> = varer.iter().map(|v| v.trim().to_lowercase()).filter(|v| !v.is_empty()).collect();
    if varer.is_empty() {
        return Ok(vec![]);
    }
    let conn = open(&app)?;
    // Hent alle (oppskrift, ingrediens) og avgjør match i Rust (toveis delstreng).
    // Indeksert via idx_ing_opp_navn. Grupper per oppskrift.
    let mut stmt = conn
        .prepare(
            "SELECT o.id, o.navn, o.type, o.bilde, i.navn \
             FROM oppskrifter o JOIN ingredienser i ON i.oppskrift_id = o.id \
             WHERE i.navn IS NOT NULL AND i.navn != '' \
             ORDER BY o.id",
        )
        .map_err(|e| e.to_string())?;
    let rader = stmt
        .query_map([], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, Option<String>>(2)?,
                r.get::<_, Option<String>>(3)?,
                r.get::<_, String>(4)?,
            ))
        })
        .map_err(|e| e.to_string())?;

    let mut ut: Vec<Forslag> = Vec::new();
    let mut cur: Option<(i64, String, Option<String>, Option<String>)> = None;
    let mut totalt = 0i64;
    let mut dekket = 0i64;
    let mut mangler: Vec<String> = Vec::new();

    let dekkes = |ing_lower: &str| -> bool {
        varer.iter().any(|v| ing_lower.contains(v.as_str()) || v.contains(ing_lower))
    };
    // Hjelpe-closure for å pushe ferdig oppskrift hvis den har minst én match.
    macro_rules! flush {
        () => {
            if let Some((id, navn, typ, bilde)) = cur.take() {
                if dekket > 0 {
                    ut.push(Forslag { id, navn, type_: typ, bilde, totalt, dekket, mangler: std::mem::take(&mut mangler) });
                } else {
                    mangler.clear();
                }
                totalt = 0; dekket = 0;
            }
        };
    }

    for row in rader.filter_map(|r| r.ok()) {
        let (id, onavn, otype, obilde, inavn) = row;
        if cur.as_ref().map(|c| c.0) != Some(id) {
            flush!();
            cur = Some((id, onavn, otype, obilde));
        }
        let il = inavn.to_lowercase();
        if er_staple(&il) {
            continue; // staples teller verken som total eller mangel
        }
        totalt += 1;
        if dekkes(&il) {
            dekket += 1;
        } else {
            mangler.push(inavn);
        }
    }
    flush!();

    // Sorter: færrest mangler først, så høyest dekning, så navn. Begrens til 60.
    ut.sort_by(|a, b| {
        (a.totalt - a.dekket).cmp(&(b.totalt - b.dekket))
            .then(b.dekket.cmp(&a.dekket))
            .then(a.navn.to_lowercase().cmp(&b.navn.to_lowercase()))
    });
    ut.truncate(60);
    Ok(ut)
}
```

NB: `er_staple` bruker EKSAKT ord-match (ingen `endswith` på `mel`) for å unngå
«melk»→staple. Step 3 har en datasjekk som MÅ gi `FEIL: 0` før man går videre.
`serde::Serialize` er alt importert (brukt av `ListeSvar`).

NB om `flush!`-makroen: den fanger lokale `mut`-variabler (`cur`/`totalt`/`dekket`/
`mangler`/`ut`) fra omsluttende scope. Det er gyldig Rust, men hvis lånekontrolløren
klager, erstatt makroen med en vanlig closure `let mut flush = || {...}` som tar
`&mut`-referansene, ELLER inline-koden to steder (i løkka ved id-bytte + etter
løkka). Logikken (push oppskrift hvis `dekket > 0`, nullstill akkumulatorer) er det
samme. Strategien er riktig; juster kun formen ved kompileringsfeil.

- [ ] **Step 2: Registrer kommandoene**

Utvid `generate_handler!`-lista (lib.rs ~linje 633-639) til:
```rust
        .invoke_handler(tauri::generate_handler![
            get_kategorier,
            hent_oppskrifter,
            hent_oppskrift,
            hent_oppskrifter_by_ids,
            cook_mode,
            ingrediens_forslag,
            hva_kan_jeg_lage
        ])
```

- [ ] **Step 3: Bygg + datasjekk på staples**

Run: `cd "<repo>/kokebok-app/src-tauri" && cargo build --features tauri/custom-protocol`
Expected: `Finished` uten feil.

Verifiser at staple-logikken (samme som Rust-versjonen over) ikke feilklassifiserer
melk/karamell. Kjør:
```bash
cd "<repo>/kokebok-app/src-tauri" && python -c "
import re
STAPLE_ORD={'salt','pepper','vann','sukker','smør','hvetemel','rugmel','sammalt',
            'semulegryn','melis','olje','olivenolje','rapsolje','solsikkeolje',
            'maisolje','frityrolje','nøytral','kvernet','flaksalt','havsalt','grovsalt'}
def er_staple(n):
    ord=[w for w in re.split(r'[^a-zæøå]+', n.lower()) if w]
    if any(w in STAPLE_ORD for w in ord): return True
    return any((w.endswith('olje') or w.endswith('salt') or w.endswith('pepper')) and len(w)>4 for w in ord)
forventet={'melk':False,'karamell':False,'marmelade':False,'melkesjokolade':False,
           'salat':False,'eplemost':False,'kyllingfilet':False,
           'salt':True,'hvetemel':True,'rapsolje':True,'olivenolje':True,'smør':True,
           'sukker':True,'kvernet pepper':True,'vann':True,'flaksalt':True}
feil=0
for t,exp in forventet.items():
    r=er_staple(t); m='ok' if r==exp else 'FEIL'; feil+=(m=='FEIL')
    print(f'  {m} {t}: {r}')
print('FEIL:',feil)
"
```
Expected: alle «ok», `FEIL: 0`. **Hvis melk/karamell/marmelade gir True:** logikken
er feil — IKKE gå videre. Bruk eksakt ord-match (ingen `endswith` på `mel`), juster
SAMME logikk i Rust + her til `FEIL: 0`.

- [ ] **Step 4: Funksjonell sjekk mot DB**

Run:
```bash
cd "<repo>/kokebok-app/src-tauri/data" && python -c "
import sqlite3
c=sqlite3.connect('kokt.db')
# simuler hva_kan_jeg_lage(['kyllingfilet','pasta','tomat']) grovt: tell dekning
varer=['kyllingfilet','pasta','tomat']
def dekkes(il): return any(il in v or v in il for v in varer)
import re
STAPLE_ORD={'salt','pepper','vann','sukker','smør','hvetemel','rugmel','sammalt',
            'semulegryn','melis','olje','olivenolje','rapsolje','solsikkeolje',
            'maisolje','frityrolje','nøytral','kvernet','flaksalt','havsalt','grovsalt'}
def staple(n):
    ord=[w for w in re.split(r'[^a-zæøå]+', n.lower()) if w]
    if any(w in STAPLE_ORD for w in ord): return True
    return any((w.endswith('olje') or w.endswith('salt') or w.endswith('pepper')) and len(w)>4 for w in ord)
best=[]
for oid,onavn in c.execute('SELECT id,navn FROM oppskrifter'):
    ings=[r[0].lower() for r in c.execute('SELECT navn FROM ingredienser WHERE oppskrift_id=?',(oid,)) if r[0]]
    nonst=[i for i in ings if not staple(i)]
    d=sum(1 for i in nonst if dekkes(i))
    if d>0: best.append((len(nonst)-d, -d, onavn))
best.sort()
print('topp 5 forslag for kylling+pasta+tomat:')
for mangel,negd,navn in best[:5]: print(f'  mangler {mangel}: {navn}')
"
```
Expected: relevante kylling/pasta-retter øverst med lav mangel-telling.

- [ ] **Step 5: Commit**
```bash
cd "<repo>" && git add kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(lager): ingrediens_forslag + hva_kan_jeg_lage (indeksert dekningsmatch)"
```

---

## Task 4: Sidebar-oppføring + `__lager__`-visning

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

- [ ] **Step 1: Import + state**

Etter `import { diettLast, ... } from "$lib/diett";` (linje ~11), legg til:
```ts
  import { lagerLast, lagerLeggTil, lagerFjern, lagerTøm, type LagerVare } from "$lib/lager";
  import { utlopsStatus } from "$lib/lager-logikk";
```
Etter `let aktiveDietter = $state<string[]>([]);` (linje ~45), legg til:
```ts
  let lager = $state<LagerVare[]>([]);
  let lagerForslag = $state<any[]>([]);
  let lagerForslagTimer: any = null;
  let nyVareNavn = $state("");
  let nyVareUtloper = $state("");
  let autoForslag = $state<string[]>([]);
  let autoTimer: any = null;
```

- [ ] **Step 2: Last i onMount**

I `onMount` (linje 462-471), etter `aktiveDietter = await diettLast();`, legg til:
```ts
    lager = await lagerLast();
```

- [ ] **Step 3: Sidebar-handler + knapp**

Ved de andre `velg*`-funksjonene (etter `velgInnstillinger`, ~linje 180), legg til:
```ts
  function velgKjøleskap() {
    currentKategori = "__lager__";
    oppdaterLagerForslag();
  }
```
I sidebar-nav, MELLOM Handleliste-knappen (slutter ~linje 528) og Innstillinger-
knappen (~linje 529), legg til:
```svelte
    <button
      class="kat-btn"
      class:active={currentKategori === "__lager__"}
      onclick={velgKjøleskap}
    >
      <span class="kat-emoji">🧊</span>
      <span class="kat-navn">Kjøleskap</span>
      <span class="kat-teller">{lager.length}</span>
    </button>
```

- [ ] **Step 4: Inkluder __lager__ i modus-ekskluderingene**

Tre steder skjuler modus-visninger grid/header. Legg til `&& currentKategori !== "__lager__"`:
- Linje ~487: `{#if currentKategori !== "__fav__" && currentKategori !== "__handle__" && currentKategori !== "__innst__"}` → legg til `&& currentKategori !== "__lager__"`
- Linje ~568: samme tillegg (`{#if currentKategori !== "__innst__"}`-blokken for header-antall — legg til `&& currentKategori !== "__lager__"`)
- Linje ~679: `{#if currentKategori !== "__handle__" && currentKategori !== "__innst__"}` (grid-wrap) → legg til `&& currentKategori !== "__lager__"`

(Bekreft de eksakte betingelsene ved lesing; mønsteret er å legge `__lager__` i
samme ekskluderingsliste som `__handle__`/`__innst__`.)

- [ ] **Step 5: Header-tittel**

I header-tittel-blokken (linje ~556-560), legg til en gren:
```svelte
      {:else if currentKategori === "__lager__"}
        🧊 Kjøleskap
```
(plasser den blant de andre `{:else if}`-grenene for modusene).

- [ ] **Step 6: Visnings-blokk (skall, fylles i T5)**

ETTER `{#if currentKategori === "__handle__"}…{/if}`-blokken (slutter ~linje 631),
legg til (forslagsdelen kobles i T5; her settes strukturen):
```svelte
  {#if currentKategori === "__lager__"}
    <div id="lager-wrap">
      <section class="lager-rediger">
        <h2>Mitt kjøleskap</h2>
        <p class="innst-hint">Legg til varer du har, så foreslår vi oppskrifter under.</p>
        <!-- autocomplete-input fylles i T5 -->
        {#if lager.length === 0}
          <p class="lager-tom">Ingen varer registrert ennå.</p>
        {:else}
          <ul class="lager-liste">
            {#each lager as v (v.navn)}
              {@const st = utlopsStatus(v.utloper, new Date().toISOString().slice(0, 10))}
              <li class="lager-vare" class:utgaatt={st === "utgått"} class:snart={st === "snart"}>
                <span class="lager-navn">{v.navn}</span>
                {#if v.utloper}<span class="lager-utlop">
                  {st === "utgått" ? "⚠ utgått" : st === "snart" ? "⚠ går ut snart" : ""} {v.utloper}
                </span>{/if}
                <button class="lager-fjern" title="Fjern" onclick={() => fjernVare(v.navn)}>✕</button>
              </li>
            {/each}
          </ul>
          <button class="lager-tom-btn" onclick={tømLager}>🗑 Tøm kjøleskap</button>
        {/if}
      </section>
      <section class="lager-forslag">
        <h2>Hva kan jeg lage?</h2>
        <!-- forslagsliste fylles i T5 -->
      </section>
    </div>
  {/if}
```

- [ ] **Step 7: Midlertidige stubs så det bygger**

Ved funksjonene, legg til stubs (fullføres i T5) slik at T4 bygger:
```ts
  async function fjernVare(navn: string) {
    lager = await lagerFjern(navn, lager);
    oppdaterLagerForslag();
  }
  async function tømLager() {
    lager = await lagerTøm();
    lagerForslag = [];
  }
  function oppdaterLagerForslag() {
    clearTimeout(lagerForslagTimer);
    lagerForslagTimer = setTimeout(async () => {
      if (lager.length === 0) { lagerForslag = []; return; }
      try {
        lagerForslag = await invoke("hva_kan_jeg_lage", { varer: lager.map((v) => v.navn) });
      } catch (e) { console.error("hva_kan_jeg_lage feilet:", e); lagerForslag = []; }
    }, 300);
  }
```

- [ ] **Step 8: Stil**

I `<style>`, etter `.diett-pille`-reglene (eller nær handleliste-stilene), legg til:
```css
  #lager-wrap { flex: 1; overflow-y: auto; padding: 24px 32px; max-width: 760px; }
  .lager-rediger, .lager-forslag { margin-bottom: 28px; }
  .lager-liste { list-style: none; padding: 0; }
  .lager-vare {
    display: flex; align-items: center; gap: 10px; padding: 8px 10px;
    border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 6px;
    background: var(--surface);
  }
  .lager-navn { flex: 1; font-weight: 600; }
  .lager-utlop { font-size: 0.82rem; color: var(--text-muted); }
  .lager-vare.snart { border-color: #d8821a; }
  .lager-vare.snart .lager-utlop { color: #d8821a; }
  .lager-vare.utgaatt { border-color: #c0392b; }
  .lager-vare.utgaatt .lager-utlop { color: #c0392b; font-weight: 700; }
  .lager-fjern { border: none; background: none; cursor: pointer; color: var(--text-muted); font-size: 1rem; }
  .lager-fjern:hover { color: var(--text); }
  .lager-tom, .lager-tom-btn { color: var(--text-muted); }
  .lager-tom-btn { border: 1px solid var(--border); background: var(--surface); border-radius: var(--radius); padding: 6px 12px; cursor: pointer; margin-top: 4px; }
```

- [ ] **Step 9: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` (pre-eksisterende a11y-advarsel OK).

- [ ] **Step 10: Commit**
```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(lager): 🧊 Kjøleskap sidebar-visning + lager-redigering"
```

---

## Task 5: Autocomplete + forslagsliste + «Jeg lagde denne»

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

- [ ] **Step 1: Autocomplete-handlere**

Ved funksjonene, legg til:
```ts
  function onNyVareInput(e: Event) {
    nyVareNavn = (e.target as HTMLInputElement).value;
    clearTimeout(autoTimer);
    const p = nyVareNavn.trim();
    if (p.length < 2) { autoForslag = []; return; }
    autoTimer = setTimeout(async () => {
      try { autoForslag = await invoke("ingrediens_forslag", { prefiks: p }); }
      catch (e) { console.error(e); autoForslag = []; }
    }, 200);
  }
  async function leggTilVare(navn?: string) {
    const n = (navn ?? nyVareNavn).trim();
    if (!n) return;
    lager = await lagerLeggTil(n, nyVareUtloper || null, lager);
    nyVareNavn = ""; nyVareUtloper = ""; autoForslag = [];
    oppdaterLagerForslag();
  }
```

- [ ] **Step 2: Autocomplete-input i markup**

I `.lager-rediger`-seksjonen, erstatt `<!-- autocomplete-input fylles i T5 -->` med:
```svelte
        <div class="lager-input-rad">
          <div class="lager-auto">
            <input
              class="lager-input"
              placeholder="Legg til vare (f.eks. kyllingfilet)…"
              value={nyVareNavn}
              oninput={onNyVareInput}
              onkeydown={(e) => { if (e.key === "Enter") leggTilVare(); }}
            />
            {#if autoForslag.length > 0}
              <ul class="lager-auto-liste">
                {#each autoForslag as f}
                  <li><button type="button" onclick={() => leggTilVare(f)}>{f}</button></li>
                {/each}
              </ul>
            {/if}
          </div>
          <input class="lager-dato" type="date" bind:value={nyVareUtloper} title="Utløpsdato (valgfritt)" />
          <button class="lager-legg" onclick={() => leggTilVare()}>Legg til</button>
        </div>
```

- [ ] **Step 3: Forslagsliste (gruppert «mangler N»)**

I `.lager-forslag`-seksjonen, erstatt `<!-- forslagsliste fylles i T5 -->` med:
```svelte
        {#if lager.length === 0}
          <p class="lager-tom">Legg til varer over for å se forslag.</p>
        {:else if lagerForslag.length === 0}
          <p class="lager-tom">Ingen treff på det du har registrert.</p>
        {:else}
          {#each [...new Set(lagerForslag.map((f) => f.totalt - f.dekket))].sort((a, b) => a - b) as mangelN}
            <div class="forslag-gruppe-tittel">
              {mangelN === 0 ? "✅ Kan lages nå" : `Mangler ${mangelN}`}
            </div>
            {#each lagerForslag.filter((f) => f.totalt - f.dekket === mangelN) as f (f.id)}
              <button class="forslag-rad" onclick={() => åpneOppskrift(f.id)}>
                {#if imgSrc(f.id)}<img src={imgSrc(f.id)} alt={f.navn} loading="lazy" />{/if}
                <span class="forslag-navn">{f.navn}</span>
                {#if f.mangler.length > 0}
                  <span class="forslag-mangler">mangler: {f.mangler.slice(0, 4).join(", ")}{f.mangler.length > 4 ? "…" : ""}</span>
                {/if}
              </button>
            {/each}
          {/each}
        {/if}
```
(`imgSrc` og `åpneOppskrift` finnes alt i fila.)

- [ ] **Step 4: «Jeg lagde denne» i detalj-topbar**

I `.detail-topbar`, etter `.detail-cook`-knappen (~linje 768), legg til:
```svelte
        {#if lager.length > 0}
          <button class="detail-handle" title="Fjern matchede varer fra kjøleskapet" onclick={() => lagdeDenne(opp)}>
            ✓ Lagde denne
          </button>
        {/if}
```
Og handleren ved funksjonene:
```ts
  async function lagdeDenne(opp: any) {
    const ings: string[] = (opp.ingredienser ?? []).map((i: any) => (i.navn ?? "").toLowerCase());
    const fjernet: string[] = [];
    let ny = lager;
    for (const v of [...lager]) {
      const vl = v.navn.toLowerCase();
      if (ings.some((il) => il.includes(vl) || vl.includes(il))) {
        ny = await lagerFjern(v.navn, ny);
        fjernet.push(v.navn);
      }
    }
    lager = ny;
    oppdaterLagerForslag();
    if (fjernet.length > 0) alert(`Fjernet fra kjøleskapet: ${fjernet.join(", ")}`);
  }
```
(Enkel `alert`-bekreftelse — YAGNI; kan byttes til toast senere.)

- [ ] **Step 5: Stil for autocomplete + forslag**

I `<style>`, etter lager-stilene fra T4, legg til:
```css
  .lager-input-rad { display: flex; gap: 8px; margin-bottom: 14px; align-items: flex-start; }
  .lager-auto { position: relative; flex: 1; }
  .lager-input { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); color: var(--text); font-family: var(--font-ui); }
  .lager-auto-liste {
    position: absolute; top: 100%; left: 0; right: 0; z-index: 20; list-style: none;
    margin: 2px 0 0; padding: 4px; background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); box-shadow: var(--shadow); max-height: 240px; overflow-y: auto;
  }
  .lager-auto-liste button { display: block; width: 100%; text-align: left; border: none; background: none; padding: 6px 8px; cursor: pointer; color: var(--text); border-radius: 4px; }
  .lager-auto-liste button:hover { background: var(--card-hover); }
  .lager-dato { padding: 8px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); color: var(--text); }
  .lager-legg { border: 1px solid var(--accent); background: var(--accent); color: #fff; border-radius: var(--radius); padding: 8px 14px; cursor: pointer; }
  .forslag-gruppe-tittel { font-weight: 700; margin: 16px 0 8px; color: var(--text); }
  .forslag-rad {
    display: flex; align-items: center; gap: 12px; width: 100%; text-align: left;
    border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface);
    padding: 8px 12px; margin-bottom: 6px; cursor: pointer;
  }
  .forslag-rad:hover { border-color: var(--border-focus); }
  .forslag-rad img { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; }
  .forslag-navn { flex: 1; font-weight: 600; color: var(--text); }
  .forslag-mangler { font-size: 0.8rem; color: var(--text-muted); }
```

- [ ] **Step 6: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten nye feil.

- [ ] **Step 7: Commit**
```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(lager): autocomplete, gruppert forslagsliste, «Jeg lagde denne»"
```

---

## Task 6: Manuell ende-til-ende-verifikasjon

Krever kjørende app. MANUELT (menneske).

**Files:** ingen.

- [ ] **Step 1: Kjør appen**

Run: `cd "<repo>/kokebok-app" && npm run tauri dev`

- [ ] **Step 2: Sjekkliste**

- Sidebar har «🧊 Kjøleskap» (mellom Handleliste og Innstillinger) med teller.
- Skriv «kyll» i vare-inputen → autocomplete viser ekte ingrediensnavn
  (kyllingfilet, kyllinglår…). Velg ett → legges i lageret.
- Legg til vare med utløpsdato i dag/i går → markeres oransje/rød. Om 1 uke → nøytral.
- Legg til et par varer (kyllingfilet, pasta, tomat) → «Hva kan jeg lage» viser
  oppskrifter gruppert «Kan lages nå» / «Mangler 1» / «Mangler 2», med «mangler: …».
- Staple-sjekk: legg til kun «salt» → skal IKKE gi «kan lages nå» på alt (salt er staple).
- Klikk et forslag → oppskriften åpnes. I detalj: «✓ Lagde denne» fjerner matchede
  varer fra kjøleskapet (bekreftelse vises), og forslag oppdateres.
- Fjern vare (✕) og «Tøm kjøleskap» virker.
- Restart app → lageret består (lager.json).

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** ren utløps-logikk+test (T1), Store-wrapper CRUD (T2),
  ingrediens_forslag + hva_kan_jeg_lage + staples m/ordgrense (T3), sidebar-modus
  + lager-visning + utløpsfarge (T4), autocomplete + gruppert «mangler N» +
  «Jeg lagde denne» (T5), manuell e2e (T6). Alle spec-beslutninger dekket.
- **Staple-kollisjon (spec-flagget — bug funnet & rettet ved planskriving):** et
  første utkast med `endswith('mel')` gjorde «melk» til staple (verifisert mot data).
  Rettet til EKSAKT ord-match mot utvidet staple-liste + trygg suffiks KUN for
  olje/salt/pepper. T3 Step 3 har en datasjekk som krever `FEIL: 0`
  (melk/karamell/marmelade/melkesjokolade/eplemost = False) før man går videre.
- **Navn/typer konsistente:** `LagerVare{navn,utloper}` (T2) brukt i T4/T5.
  `utlopsStatus` (T1) brukt i T4. `Forslag{id,navn,type,bilde,totalt,dekket,mangler}`
  (T3) ↔ `lagerForslag`-bruk i T5 (`f.totalt - f.dekket`, `f.mangler`, `f.id`).
  `lagerLast/LeggTil/Fjern/Tøm` (T2) konsistent T4/T5. Kommandonavn
  `ingrediens_forslag`/`hva_kan_jeg_lage` (T3) ↔ `invoke(...)` (T4/T5).
- **Verifisert mot kode:** sidebar-knapp-mønster (510-536), modus-ekskluderinger
  (487/568/679), header-tittel (556-560), handleliste-visning som mal (584-631),
  onMount (462-471), detail-topbar (753-768), generate_handler (633-639). `imgSrc`/
  `åpneOppskrift`/`query_json`/`idx_ing_opp_navn`/`serde::Serialize` finnes.
- **Bygg-rekkefølge:** T4 bygger pga stubs (Step 7); T5 fyller dem. Hver task
  etterlater prosjektet byggbart.
