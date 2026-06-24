# Oppskriftsversjonering — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brukeren kan redigere sin personlige kopi av en scraped oppskrift (ingredienser, trinn, navn, beskrivelse, porsjoner, tid), manuelt lagre versjoner, og sammenligne/gjenopprette tidligere versjoner. Alt lagres i Tauri Store; `kokt.db` røres aldri.

**Architecture:** Ren testbar logikk i `versjoner-logikk.ts` (diff, kopier-fra-oppskrift). Tauri Store I/O i `versjoner.ts` (singleton `load("versjoner.json")`). UI inline i `+page.svelte` sitt eksisterende `detail-panel`: Rediger-knapp i topbar, inline redigerbare felt, lagremodal, historikkpanel og sammenligningsoverlay.

**Tech Stack:** Svelte 5 runes (`$state`, `$derived`), `@tauri-apps/plugin-store`, TypeScript, Node `.test.mjs` (samme mønster som `matplan-logikk.test.mjs`).

**Spec:** `docs/superpowers/specs/2026-06-24-oppskriftsversjonering-design.md`

> **`<repo>`** = din lokale klone av kokt.nok. Les hver fil FØR du redigerer — linjenumre kan drifte.

---

## Global Constraints

- `kokt.db` er **read-only** — aldri skriv til den
- Svelte 5 runes kun: `$state`, `$derived` — ingen `$:`, ingen `writable()`
- Tauri Store: `load("versjoner.json")`, `store.get/set/save()`
- `invoke` fra `@tauri-apps/api/core`
- Ingen nye Rust-kommandoer
- CSS-variabler fra `app.css`: `--card`, `--card-hover`, `--text-muted`, `--border`, `--surface`, `--bg`, `--text`, `--radius-sm`, `--font-ui`
- Versjonering er **profil-spesifikk**: profil-ID som ytterste nøkkel
- Ingen drag-resortering av trinn — pil opp/ned-knapper
- Rediger-knapp vises kun når `aktivProfil !== null`
- Tester kjøres med: `node --experimental-strip-types kokebok-app/src/lib/versjoner-logikk.test.mjs`

---

## Anker-fakta (verifisert mot kode 2026-06-24)

- **`currentOppskrift`** settes i `åpneOppskrift(id)` (ca. linje 543–554 i `+page.svelte`). Inne i `{#if currentOppskrift}` brukes `{@const opp = currentOppskrift}` (ca. linje 1324).
- **`aktivProfil`** er `$derived` (ca. linje 92): `profilStore.profiler.find(p => p.id === profilStore.aktivId) ?? null`
- **`detail-topbar`** (ca. linje 1331–1358): knapper for Tilbake, Favoritt, Handleliste, CookMode, "Lagde denne".
- **`detail-body`** (ca. linje 1369–1515): navn, beskrivelse, porsjoner, ingredienser, trinn, næring, dagsbehov, pris, notat-seksjon.
- **`notatTimer`** er allerede i bruk for debounce av notater. Samme mønster brukes for kladd-debounce.
- **Singleton store-mønster** (fra `notater.ts`): `let storePromise: Promise<Store> | null = null; function hentStore() { if (!storePromise) storePromise = load(FIL); return storePromise; }`
- **Test-runner** (fra `matplan-logikk.test.mjs`): `import assert from "node:assert"; function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); } catch(e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }`

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src/lib/versjoner-logikk.ts` | Ren logikk: typer, `kopiFraOppskrift`, `beregnDiff` | Create |
| `kokebok-app/src/lib/versjoner-logikk.test.mjs` | Node-tester for logikk-modulen | Create |
| `kokebok-app/src/lib/versjoner.ts` | Tauri Store I/O for versjoner | Create |
| `kokebok-app/src/routes/+page.svelte` | Redigerings-UI, historikkpanel, sammenligningsoverlay | Modify |

**Rekkefølge:** ren logikk (T1) → Store-wrapper (T2) → rediger-UI i detaljpanel (T3) → lagremodal + historikkpanel (T4) → sammenligningsoverlay (T5) → manuell e2e (T6).

---

## Task 1: Ren logikk `versjoner-logikk.ts` (TDD)

**Files:**
- Create: `kokebok-app/src/lib/versjoner-logikk.ts`
- Create: `kokebok-app/src/lib/versjoner-logikk.test.mjs`

**Interfaces:**
- Produces:
  - `OppskriftKopi`, `KopiIngrediens`, `KopiTrinn`, `VersjonSnapshot`, `OppskriftEntry` — eksporterte typer
  - `kopiFraOppskrift(opp: OppskriftRaw): OppskriftKopi`
  - `beregnDiff(orig: OppskriftKopi, versjon: OppskriftKopi): OppskriftDiff`
  - `IngrediensDiff`, `TrinnDiff`, `OppskriftDiff` — eksporterte typer

- [ ] **Step 1: Skriv testfilen**

Opprett `kokebok-app/src/lib/versjoner-logikk.test.mjs`:

```js
import { kopiFraOppskrift, beregnDiff } from "./versjoner-logikk.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

const rawOpp = {
  id: 1, navn: "Pasta", beskrivelse: "God pasta", porsjoner: 4, tid: "30 min",
  ingredienser: [
    { gruppe: null, mengde: 200, enhet: "g", navn: "pasta", sortering: 0 },
    { gruppe: null, mengde: 1, enhet: "ss", navn: "olje", sortering: 1 },
  ],
  trinn: [
    { nummer: 1, tekst: "Kok opp vann." },
    { nummer: 2, tekst: "Ha i pasta." },
  ],
};

// kopiFraOppskrift lager OppskriftKopi fra råoppskrift
sjekk("kopiFraOppskrift: navn og tid", () => {
  const k = kopiFraOppskrift(rawOpp);
  assert.equal(k.navn, "Pasta");
  assert.equal(k.tid, "30 min");
  assert.equal(k.porsjoner, 4);
});

sjekk("kopiFraOppskrift: ingredienser", () => {
  const k = kopiFraOppskrift(rawOpp);
  assert.equal(k.ingredienser.length, 2);
  assert.equal(k.ingredienser[0].navn, "pasta");
  assert.equal(k.ingredienser[1].enhet, "ss");
});

sjekk("kopiFraOppskrift: trinn", () => {
  const k = kopiFraOppskrift(rawOpp);
  assert.equal(k.trinn.length, 2);
  assert.equal(k.trinn[0].tekst, "Kok opp vann.");
});

// beregnDiff: ingen endringer
sjekk("beregnDiff: ingen endringer", () => {
  const k = kopiFraOppskrift(rawOpp);
  const diff = beregnDiff(k, k);
  assert.equal(diff.navn.endret, false);
  assert.equal(diff.ingredienser.every(d => !d.endret), true);
  assert.equal(diff.trinn.every(d => !d.endret), true);
});

// beregnDiff: endret navn
sjekk("beregnDiff: endret navn", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = { ...orig, navn: "Annen pasta" };
  const diff = beregnDiff(orig, versjon);
  assert.equal(diff.navn.endret, true);
  assert.equal(diff.navn.orig, "Pasta");
  assert.equal(diff.navn.versjon, "Annen pasta");
});

// beregnDiff: endret ingrediensmengde
sjekk("beregnDiff: endret mengde gir endret=true", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    ingredienser: [
      { ...orig.ingredienser[0], mengde: 300 },
      orig.ingredienser[1],
    ],
  };
  const diff = beregnDiff(orig, versjon);
  assert.equal(diff.ingredienser[0].endret, true);
  assert.equal(diff.ingredienser[1].endret, false);
});

// beregnDiff: ny ingrediens i versjon
sjekk("beregnDiff: ny ingrediens i versjon", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    ingredienser: [
      ...orig.ingredienser,
      { gruppe: null, mengde: 2, enhet: "fedd", navn: "hvitløk", sortering: 2 },
    ],
  };
  const diff = beregnDiff(orig, versjon);
  // ekstra rad med orig=null
  const ny = diff.ingredienser.find(d => d.orig === null);
  assert.ok(ny !== undefined);
  assert.equal(ny.versjon?.navn, "hvitløk");
});

// beregnDiff: slettet ingrediens
sjekk("beregnDiff: slettet ingrediens", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    ingredienser: [orig.ingredienser[0]],
  };
  const diff = beregnDiff(orig, versjon);
  const slettet = diff.ingredienser.find(d => d.versjon === null);
  assert.ok(slettet !== undefined);
  assert.equal(slettet.orig?.navn, "olje");
});

// beregnDiff: omskrevet trinn
sjekk("beregnDiff: omskrevet trinn", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    trinn: [
      { nummer: 1, tekst: "Kok opp masse vann." },
      orig.trinn[1],
    ],
  };
  const diff = beregnDiff(orig, versjon);
  assert.equal(diff.trinn[0].endret, true);
  assert.equal(diff.trinn[1].endret, false);
});

console.log(`\n${ok} tester OK`);
```

- [ ] **Step 2: Kjør testen — forvent feil**

```
node --experimental-strip-types kokebok-app/src/lib/versjoner-logikk.test.mjs
```

Forventet: feil med "Cannot find module" eller lignende (filen finnes ikke ennå).

- [ ] **Step 3: Opprett `versjoner-logikk.ts`**

Opprett `kokebok-app/src/lib/versjoner-logikk.ts`:

```typescript
// Ren, node-testbar logikk for oppskriftsversjonering (ingen Tauri-import).

export type KopiIngrediens = {
  gruppe: string | null;
  mengde: number | null;
  enhet: string | null;
  navn: string | null;
  sortering: number;
};

export type KopiTrinn = {
  nummer: number;
  tekst: string;
};

export type OppskriftKopi = {
  navn: string;
  beskrivelse: string | null;
  porsjoner: number | null;
  tid: string | null;
  ingredienser: KopiIngrediens[];
  trinn: KopiTrinn[];
};

export type OppskriftEntry = {
  kladd: OppskriftKopi | null;
  historikk: VersjonSnapshot[];
};

export type VersjonSnapshot = {
  id: string;
  lagretTidspunkt: string;
  label: string;
  kopi: OppskriftKopi;
};

export type IngrediensDiff = {
  orig: KopiIngrediens | null;
  versjon: KopiIngrediens | null;
  endret: boolean;
};

export type TrinnDiff = {
  orig: KopiTrinn | null;
  versjon: KopiTrinn | null;
  endret: boolean;
};

export type OppskriftDiff = {
  navn: { orig: string; versjon: string; endret: boolean };
  beskrivelse: { orig: string | null; versjon: string | null; endret: boolean };
  porsjoner: { orig: number | null; versjon: number | null; endret: boolean };
  tid: { orig: string | null; versjon: string | null; endret: boolean };
  ingredienser: IngrediensDiff[];
  trinn: TrinnDiff[];
};

// Raw-type: hva hent_oppskrift returnerer (subset vi bruker).
export type OppskriftRaw = {
  navn: string;
  beskrivelse?: string | null;
  porsjoner?: number | null;
  tid?: string | null;
  ingredienser?: Array<{
    gruppe?: string | null;
    mengde?: number | null;
    enhet?: string | null;
    navn?: string | null;
    sortering?: number;
  }>;
  trinn?: Array<{ nummer: number; tekst: string }>;
};

/** Bygg OppskriftKopi fra et oppskrift-objekt returnert av hent_oppskrift. */
export function kopiFraOppskrift(opp: OppskriftRaw): OppskriftKopi {
  return {
    navn: opp.navn,
    beskrivelse: opp.beskrivelse ?? null,
    porsjoner: opp.porsjoner ?? null,
    tid: opp.tid ?? null,
    ingredienser: (opp.ingredienser ?? []).map((i, idx) => ({
      gruppe: i.gruppe ?? null,
      mengde: i.mengde ?? null,
      enhet: i.enhet ?? null,
      navn: i.navn ?? null,
      sortering: i.sortering ?? idx,
    })),
    trinn: (opp.trinn ?? []).map((t) => ({ nummer: t.nummer, tekst: t.tekst })),
  };
}

/** Beregn strukturell diff mellom to OppskriftKopi. */
export function beregnDiff(orig: OppskriftKopi, versjon: OppskriftKopi): OppskriftDiff {
  // Ingrediensdiff: match på indeks (posisjonell sammenligning)
  const maxIng = Math.max(orig.ingredienser.length, versjon.ingredienser.length);
  const ingredienser: IngrediensDiff[] = [];
  for (let i = 0; i < maxIng; i++) {
    const o = orig.ingredienser[i] ?? null;
    const v = versjon.ingredienser[i] ?? null;
    const endret =
      o === null || v === null ||
      o.navn !== v.navn || o.mengde !== v.mengde ||
      o.enhet !== v.enhet || o.gruppe !== v.gruppe;
    ingredienser.push({ orig: o, versjon: v, endret });
  }

  // Trinndiff: match på indeks
  const maxTrinn = Math.max(orig.trinn.length, versjon.trinn.length);
  const trinn: TrinnDiff[] = [];
  for (let i = 0; i < maxTrinn; i++) {
    const o = orig.trinn[i] ?? null;
    const v = versjon.trinn[i] ?? null;
    const endret = o === null || v === null || o.tekst !== v.tekst;
    trinn.push({ orig: o, versjon: v, endret });
  }

  return {
    navn: { orig: orig.navn, versjon: versjon.navn, endret: orig.navn !== versjon.navn },
    beskrivelse: { orig: orig.beskrivelse, versjon: versjon.beskrivelse, endret: orig.beskrivelse !== versjon.beskrivelse },
    porsjoner: { orig: orig.porsjoner, versjon: versjon.porsjoner, endret: orig.porsjoner !== versjon.porsjoner },
    tid: { orig: orig.tid, versjon: versjon.tid, endret: orig.tid !== versjon.tid },
    ingredienser,
    trinn,
  };
}
```

- [ ] **Step 4: Kjør tester — forvent alle OK**

```
node --experimental-strip-types kokebok-app/src/lib/versjoner-logikk.test.mjs
```

Forventet output:
```
  ok  kopiFraOppskrift: navn og tid
  ok  kopiFraOppskrift: ingredienser
  ok  kopiFraOppskrift: trinn
  ok  beregnDiff: ingen endringer
  ok  beregnDiff: endret navn
  ok  beregnDiff: endret mengde gir endret=true
  ok  beregnDiff: ny ingrediens i versjon
  ok  beregnDiff: slettet ingrediens
  ok  beregnDiff: omskrevet trinn

9 tester OK
```

- [ ] **Step 5: Commit**

```bash
git add kokebok-app/src/lib/versjoner-logikk.ts kokebok-app/src/lib/versjoner-logikk.test.mjs
git commit -m "feat(versjonering): typer og logikk (kopiFraOppskrift, beregnDiff)"
```

---

## Task 2: Tauri Store-wrapper `versjoner.ts`

**Files:**
- Create: `kokebok-app/src/lib/versjoner.ts`

**Interfaces:**
- Consumes: `OppskriftEntry`, `OppskriftKopi`, `VersjonSnapshot` fra `./versjoner-logikk.ts`
- Produces:
  - `versjonerLast(profilId: string, oppskriftId: number): Promise<OppskriftEntry | null>`
  - `kladd_sett(profilId: string, oppskriftId: number, kopi: OppskriftKopi): Promise<void>`
  - `kladd_fjern(profilId: string, oppskriftId: number): Promise<void>`
  - `versjon_lagre(profilId: string, oppskriftId: number, label: string, kopi: OppskriftKopi): Promise<VersjonSnapshot[]>`
  - `versjon_slett(profilId: string, oppskriftId: number, versjonId: string): Promise<VersjonSnapshot[]>`

- [ ] **Step 1: Opprett `versjoner.ts`**

Opprett `kokebok-app/src/lib/versjoner.ts`:

```typescript
// Versjonering av oppskrifter — Tauri Store I/O.
// kokt.db er read-only; all brukerdata lagres i versjoner.json.
import { load, type Store } from "@tauri-apps/plugin-store";
import type { OppskriftEntry, OppskriftKopi, VersjonSnapshot } from "./versjoner-logikk.ts";

const FIL = "versjoner.json";

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

// Intern type for hele store-strukturen
type VersjonerStore = Record<string, Record<string, OppskriftEntry>>;

async function hentAlle(): Promise<VersjonerStore> {
  try {
    const store = await hentStore();
    return (await store.get<VersjonerStore>("v")) ?? {};
  } catch {
    return {};
  }
}

async function lagreAlle(data: VersjonerStore): Promise<void> {
  const store = await hentStore();
  await store.set("v", data);
  await store.save();
}

/** Last kladd og historikk for én oppskrift under én profil. */
export async function versjonerLast(
  profilId: string,
  oppskriftId: number,
): Promise<OppskriftEntry | null> {
  try {
    const alle = await hentAlle();
    return alle[profilId]?.[oppskriftId] ?? null;
  } catch (err) {
    console.error("versjonerLast feilet:", err);
    return null;
  }
}

/** Oppdater kladd (autolaging — debounce i kallende kode). */
export async function kladd_sett(
  profilId: string,
  oppskriftId: number,
  kopi: OppskriftKopi,
): Promise<void> {
  try {
    const alle = await hentAlle();
    if (!alle[profilId]) alle[profilId] = {};
    const entry = alle[profilId][oppskriftId] ?? { kladd: null, historikk: [] };
    alle[profilId][oppskriftId] = { ...entry, kladd: kopi };
    await lagreAlle(alle);
  } catch (err) {
    console.error("kladd_sett feilet:", err);
  }
}

/** Fjern kladd (ved avbryt uten eksisterende versjon). */
export async function kladd_fjern(
  profilId: string,
  oppskriftId: number,
): Promise<void> {
  try {
    const alle = await hentAlle();
    const entry = alle[profilId]?.[oppskriftId];
    if (!entry) return;
    alle[profilId][oppskriftId] = { ...entry, kladd: null };
    await lagreAlle(alle);
  } catch (err) {
    console.error("kladd_fjern feilet:", err);
  }
}

/** Lagre en navngitt versjon. Returnerer oppdatert historikk (nyeste først). */
export async function versjon_lagre(
  profilId: string,
  oppskriftId: number,
  label: string,
  kopi: OppskriftKopi,
): Promise<VersjonSnapshot[]> {
  try {
    const alle = await hentAlle();
    if (!alle[profilId]) alle[profilId] = {};
    const entry = alle[profilId][oppskriftId] ?? { kladd: null, historikk: [] };
    const snapshot: VersjonSnapshot = {
      id: crypto.randomUUID(),
      lagretTidspunkt: new Date().toISOString(),
      label: label.trim(),
      kopi,
    };
    const historikk = [snapshot, ...entry.historikk];
    alle[profilId][oppskriftId] = { kladd: kopi, historikk };
    await lagreAlle(alle);
    return historikk;
  } catch (err) {
    console.error("versjon_lagre feilet:", err);
    return [];
  }
}

/** Slett én versjon. Returnerer oppdatert historikk. */
export async function versjon_slett(
  profilId: string,
  oppskriftId: number,
  versjonId: string,
): Promise<VersjonSnapshot[]> {
  try {
    const alle = await hentAlle();
    const entry = alle[profilId]?.[oppskriftId];
    if (!entry) return [];
    const historikk = entry.historikk.filter((v) => v.id !== versjonId);
    alle[profilId][oppskriftId] = { ...entry, historikk };
    await lagreAlle(alle);
    return historikk;
  } catch (err) {
    console.error("versjon_slett feilet:", err);
    return [];
  }
}
```

- [ ] **Step 2: Bygg for å verifisere TypeScript**

```
cd kokebok-app && npm run build
```

Forventet: bygger uten feil. (Siden `versjoner.ts` ikke importeres i `+page.svelte` ennå, vil ikke Svelte-kompilator klage.)

- [ ] **Step 3: Commit**

```bash
git add kokebok-app/src/lib/versjoner.ts
git commit -m "feat(versjonering): Tauri Store-wrapper (versjonerLast, kladd_sett, versjon_lagre, versjon_slett)"
```

---

## Task 3: Redigerings-UI i detaljpanelet

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes:
  - `versjonerLast`, `kladd_sett`, `kladd_fjern` fra `$lib/versjoner`
  - `kopiFraOppskrift`, `OppskriftKopi`, `KopiIngrediens`, `KopiTrinn`, `OppskriftEntry`, `VersjonSnapshot` fra `$lib/versjoner-logikk`
- Produces: redigeringsstate og -funksjoner som Task 4 og 5 bygger videre på

Forutsetning: Les `+page.svelte` for gjeldende linjenumre rundt:
- Import-blokken (topp av `<script>`)
- State-deklarasjonene (linje ~33–90)
- `åpneOppskrift`-funksjonen (linje ~543–555)
- `lukkDetalj`-funksjonen (linje ~556–560)
- `detail-topbar`-blokken
- Starten av `detail-body`

- [ ] **Step 1: Legg til import i `<script>`-blokken**

Finn import-blokken øverst i `<script lang="ts">` (der `favorittLast`, `notaterLast` osv. importeres). Legg til på slutten av import-blokken:

```typescript
  import { versjonerLast, kladd_sett, kladd_fjern, versjon_lagre, versjon_slett } from "$lib/versjoner";
  import { kopiFraOppskrift, beregnDiff, type OppskriftKopi, type KopiIngrediens, type KopiTrinn, type VersjonSnapshot } from "$lib/versjoner-logikk";
```

- [ ] **Step 2: Legg til redigerings-state**

Finn state-blokken (etter `let innstFane = $state...`, rundt linje 69). Legg til:

```typescript
  // ── Versjonering / redigering ────────────────────────────────────────────────
  let redigerModus = $state(false);
  let kladd = $state<OppskriftKopi | null>(null);
  let historikk = $state<VersjonSnapshot[]>([]);
  let sammenlignVersjon = $state<VersjonSnapshot | null>(null);
  let lagreModalApen = $state(false);
  let lagreLabel = $state("");
  let kladdTimer: any = null;
```

- [ ] **Step 3: Last kladd og historikk når oppskrift åpnes**

Finn `åpneOppskrift`-funksjonen. Etter `portioner = opp.porsjoner ?? 4;` legger du til:

```typescript
      // Last kladd og historikk for aktiv profil
      if (aktivProfil) {
        const entry = await versjonerLast(aktivProfil.id, id);
        kladd = entry?.kladd ?? null;
        historikk = entry?.historikk ?? [];
      } else {
        kladd = null;
        historikk = [];
      }
      redigerModus = false;
      sammenlignVersjon = null;
      lagreModalApen = false;
      lagreLabel = "";
```

- [ ] **Step 4: Nullstill redigerings-state ved lukking**

Finn `lukkDetalj`-funksjonen. Legg til etter `portioner = null;`:

```typescript
    redigerModus = false;
    kladd = null;
    historikk = [];
    sammenlignVersjon = null;
    lagreModalApen = false;
    lagreLabel = "";
    if (kladdTimer) { clearTimeout(kladdTimer); kladdTimer = null; }
```

- [ ] **Step 5: Legg til `åpneRediger`- og `avbrytRediger`-funksjoner**

Legg til etter `lukkDetalj`-funksjonen:

```typescript
  function åpneRediger() {
    if (!currentOppskrift || !aktivProfil) return;
    if (!kladd) kladd = kopiFraOppskrift(currentOppskrift);
    redigerModus = true;
  }

  function avbrytRediger() {
    redigerModus = false;
    // Gjenopprett kladd fra store (ikke kast brukers lagrede kladd)
    if (currentOppskrift && aktivProfil) {
      versjonerLast(aktivProfil.id, currentOppskrift.id).then((entry) => {
        kladd = entry?.kladd ?? null;
      });
    }
  }

  function oppdaterKladd(nyKopi: OppskriftKopi) {
    kladd = nyKopi;
    if (!currentOppskrift || !aktivProfil) return;
    const profilId = aktivProfil.id;
    const oppskriftId = currentOppskrift.id;
    if (kladdTimer) clearTimeout(kladdTimer);
    kladdTimer = setTimeout(() => {
      kladd_sett(profilId, oppskriftId, nyKopi).catch(console.error);
    }, 800);
  }
```

- [ ] **Step 6: Legg til "Rediger"-knapp i `detail-topbar`**

Finn `detail-topbar`-blokken. Rett etter `<button class="btn-back" onclick={lukkDetalj}>← Tilbake</button>` — legg til:

```svelte
        {#if aktivProfil}
          {#if redigerModus}
            <button class="detail-rediger" onclick={avbrytRediger}>← Avbryt</button>
            <button class="detail-rediger aktiv" onclick={() => lagreModalApen = true}>💾 Lagre versjon</button>
          {:else}
            <button
              class="detail-rediger"
              class:har-kladd={kladd !== null}
              onclick={åpneRediger}
              title={kladd !== null ? "Du har en redigert versjon" : "Rediger din kopi"}
            >✏️ Rediger{kladd !== null ? " ●" : ""}</button>
          {/if}
        {/if}
```

- [ ] **Step 7: Bytt ut ingrediensliste og fremgangsmåte i `detail-body` med redigerbar versjon**

Finn `detail-columns`-blokken (der ingredienser og trinn vises). Den er ca. slik:

```svelte
        <div class="detail-columns">
          <div>
            <div class="detail-section-title">Ingredienser</div>
            {#each grupper as [g, ings]}
              ...
```

Pakk hele `detail-columns`-blokken inn i en betingelse. Erstatt `<div class="detail-columns">` og alt innholdet med:

```svelte
        {#if redigerModus && kladd}
          {@const k = kladd}
          <div class="rediger-meta">
            <label class="rediger-label">Navn
              <input class="rediger-input" type="text" value={k.navn}
                oninput={(e) => oppdaterKladd({ ...k, navn: (e.target as HTMLInputElement).value })} />
            </label>
            <label class="rediger-label">Beskrivelse
              <textarea class="rediger-textarea" value={k.beskrivelse ?? ""}
                oninput={(e) => oppdaterKladd({ ...k, beskrivelse: (e.target as HTMLTextAreaElement).value || null })}></textarea>
            </label>
            <div class="rediger-rad">
              <label class="rediger-label">Porsjoner
                <input class="rediger-input rediger-input-sm" type="number" min="1" value={k.porsjoner ?? ""}
                  oninput={(e) => oppdaterKladd({ ...k, porsjoner: parseInt((e.target as HTMLInputElement).value) || null })} />
              </label>
              <label class="rediger-label">Tid
                <input class="rediger-input rediger-input-sm" type="text" value={k.tid ?? ""}
                  oninput={(e) => oppdaterKladd({ ...k, tid: (e.target as HTMLInputElement).value || null })} />
              </label>
            </div>
          </div>

          <div class="detail-columns">
            <div>
              <div class="detail-section-title">Ingredienser</div>
              {#each k.ingredienser as ing, idx}
                <div class="rediger-ing-rad">
                  <input class="rediger-input rediger-input-mengde" type="number" placeholder="mengde"
                    value={ing.mengde ?? ""}
                    oninput={(e) => {
                      const nyIng = [...k.ingredienser];
                      nyIng[idx] = { ...ing, mengde: parseFloat((e.target as HTMLInputElement).value) || null };
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }} />
                  <input class="rediger-input rediger-input-enhet" type="text" placeholder="enhet"
                    value={ing.enhet ?? ""}
                    oninput={(e) => {
                      const nyIng = [...k.ingredienser];
                      nyIng[idx] = { ...ing, enhet: (e.target as HTMLInputElement).value || null };
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }} />
                  <input class="rediger-input rediger-input-navn" type="text" placeholder="ingrediens"
                    value={ing.navn ?? ""}
                    oninput={(e) => {
                      const nyIng = [...k.ingredienser];
                      nyIng[idx] = { ...ing, navn: (e.target as HTMLInputElement).value || null };
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }} />
                  <button class="rediger-slett" title="Slett ingrediens"
                    onclick={() => {
                      const nyIng = k.ingredienser.filter((_, i) => i !== idx);
                      oppdaterKladd({ ...k, ingredienser: nyIng });
                    }}>🗑</button>
                </div>
              {/each}
              <button class="rediger-legg-til" onclick={() => {
                const nyIng: KopiIngrediens = { gruppe: null, mengde: null, enhet: null, navn: null, sortering: k.ingredienser.length };
                oppdaterKladd({ ...k, ingredienser: [...k.ingredienser, nyIng] });
              }}>＋ Legg til ingrediens</button>
            </div>

            <div>
              <div class="detail-section-title">Fremgangsmåte</div>
              {#each k.trinn as trinn, idx}
                <div class="rediger-trinn-rad">
                  <div class="rediger-trinn-nr">{idx + 1}</div>
                  <textarea class="rediger-textarea rediger-trinn-tekst" value={trinn.tekst}
                    oninput={(e) => {
                      const nyTrinn = [...k.trinn];
                      nyTrinn[idx] = { ...trinn, tekst: (e.target as HTMLTextAreaElement).value };
                      oppdaterKladd({ ...k, trinn: nyTrinn });
                    }}></textarea>
                  <div class="rediger-trinn-knapper">
                    <button class="rediger-pil" disabled={idx === 0} title="Flytt opp"
                      onclick={() => {
                        const t = [...k.trinn];
                        [t[idx - 1], t[idx]] = [t[idx], t[idx - 1]];
                        oppdaterKladd({ ...k, trinn: t.map((x, i) => ({ ...x, nummer: i + 1 })) });
                      }}>↑</button>
                    <button class="rediger-pil" disabled={idx === k.trinn.length - 1} title="Flytt ned"
                      onclick={() => {
                        const t = [...k.trinn];
                        [t[idx], t[idx + 1]] = [t[idx + 1], t[idx]];
                        oppdaterKladd({ ...k, trinn: t.map((x, i) => ({ ...x, nummer: i + 1 })) });
                      }}>↓</button>
                    <button class="rediger-slett" title="Slett trinn"
                      onclick={() => {
                        const nyTrinn = k.trinn.filter((_, i) => i !== idx).map((x, i) => ({ ...x, nummer: i + 1 }));
                        oppdaterKladd({ ...k, trinn: nyTrinn });
                      }}>🗑</button>
                  </div>
                </div>
              {/each}
              <button class="rediger-legg-til" onclick={() => {
                const nyTrinn: KopiTrinn = { nummer: k.trinn.length + 1, tekst: "" };
                oppdaterKladd({ ...k, trinn: [...k.trinn, nyTrinn] });
              }}>＋ Legg til trinn</button>
            </div>
          </div>
        {:else}
          <div class="detail-columns">
            <div>
              <div class="detail-section-title">Ingredienser</div>
              {#each grupper as [g, ings]}
                {#if multiGroup}<div class="ing-group-title">{g}</div>{/if}
                {#each ings as i}
                  {@const m = fmtMengde(scaleMengde(i.mengde, origP, curP))}
                  <div class="ing-item">
                    <span class="ing-mengde">{m}</span>
                    <span class="ing-enhet">{i.enhet ?? ""}</span>
                    <span class="ing-navn">{i.navn ?? ""}</span>
                  </div>
                {/each}
              {/each}
            </div>
            <div>
              <div class="detail-section-title">Fremgangsmåte</div>
              {#each opp.trinn as t, idx}
                <div class="step-item">
                  <div class="step-num">{t.nummer ?? idx + 1}</div>
                  <div class="step-tekst">
                    {#each trinnSegmenter(t.tekst) as s}
                      {#if s.klikk}
                        <button
                          class="tid-knapp"
                          title="Start timer ({fmtTid(s.sekunder)})"
                          onclick={() => startTimer(s.sekunder, `${opp.navn} – trinn ${t.nummer ?? idx + 1}`)}
                        >⏱ {s.tekst}</button>
                      {:else}{s.tekst}{/if}
                    {/each}
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}
```

- [ ] **Step 8: Legg til CSS for redigerings-UI**

Finn `<style>`-blokken (bunnen av filen). Legg til:

```css
  /* ── Versjonering / redigering ── */
  .detail-rediger {
    font-size: 0.82rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 5px 10px; cursor: pointer;
  }
  .detail-rediger.aktiv { background: var(--card-hover); }
  .detail-rediger.har-kladd { border-color: var(--text-muted); }
  .rediger-meta { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
  .rediger-rad { display: flex; gap: 16px; }
  .rediger-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.82rem; color: var(--text-muted); font-family: var(--font-ui); }
  .rediger-input {
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 5px 8px; font-size: 0.9rem; font-family: var(--font-ui);
    width: 100%;
  }
  .rediger-input-sm { width: 90px; }
  .rediger-input-mengde { width: 64px; }
  .rediger-input-enhet { width: 60px; }
  .rediger-input-navn { flex: 1; }
  .rediger-textarea {
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 6px 8px; font-size: 0.9rem; font-family: var(--font-ui);
    width: 100%; min-height: 56px; resize: vertical;
  }
  .rediger-ing-rad { display: flex; gap: 4px; align-items: center; margin-bottom: 4px; }
  .rediger-slett { background: none; border: none; cursor: pointer; font-size: 1rem; padding: 2px 4px; color: var(--text-muted); }
  .rediger-legg-til {
    margin-top: 8px; font-size: 0.82rem; font-family: var(--font-ui);
    background: none; border: 1px dashed var(--border); border-radius: var(--radius-sm);
    color: var(--text-muted); padding: 4px 10px; cursor: pointer; width: 100%;
  }
  .rediger-trinn-rad { display: flex; gap: 6px; align-items: flex-start; margin-bottom: 8px; }
  .rediger-trinn-nr { min-width: 24px; font-weight: 600; color: var(--text-muted); padding-top: 6px; }
  .rediger-trinn-tekst { flex: 1; min-height: 72px; }
  .rediger-trinn-knapper { display: flex; flex-direction: column; gap: 2px; }
  .rediger-pil {
    background: none; border: 1px solid var(--border); border-radius: var(--radius-sm);
    cursor: pointer; font-size: 0.8rem; padding: 2px 6px; color: var(--text-muted);
  }
  .rediger-pil:disabled { opacity: 0.3; cursor: default; }
```

- [ ] **Step 9: Bygg og sjekk**

```
cd kokebok-app && npm run build
```

Forventet: bygger uten TypeScript-feil.

- [ ] **Step 10: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(versjonering): redigerings-UI i detaljpanel (ingredienser, trinn, metadata)"
```

---

## Task 4: Lagremodal og historikkpanel

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `versjon_lagre`, `versjon_slett` fra `$lib/versjoner`; state fra Task 3

- [ ] **Step 1: Legg til `lagreVersjon`-funksjon**

Finn `avbrytRediger`-funksjonen (lagt til i Task 3). Legg til etter den:

```typescript
  async function lagreVersjon() {
    if (!currentOppskrift || !aktivProfil || !kladd) return;
    historikk = await versjon_lagre(aktivProfil.id, currentOppskrift.id, lagreLabel, kladd);
    lagreModalApen = false;
    lagreLabel = "";
    redigerModus = false;
  }

  async function slettVersjon(versjonId: string) {
    if (!currentOppskrift || !aktivProfil) return;
    historikk = await versjon_slett(aktivProfil.id, currentOppskrift.id, versjonId);
  }

  function gjenopprettVersjon(versjon: VersjonSnapshot) {
    if (!currentOppskrift || !aktivProfil) return;
    kladd = { ...versjon.kopi };
    sammenlignVersjon = null;
    redigerModus = true;
    // Kladd autolages via debounce ved neste oppdaterKladd-kall
    kladd_sett(aktivProfil.id, currentOppskrift.id, versjon.kopi).catch(console.error);
  }

  function fmtVersjonTid(iso: string): string {
    try {
      return new Intl.DateTimeFormat("nb-NO", {
        day: "numeric", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      }).format(new Date(iso));
    } catch {
      return iso;
    }
  }
```

- [ ] **Step 2: Legg til lagremodal i `detail-panel`**

Finn slutten av `<div id="detail-panel">` — rett etter `</div>` som lukker `detail-body`, men før `</div>` som lukker `detail-panel`. Legg til:

```svelte
      {#if lagreModalApen}
        <div class="lagre-modal-bakgrunn" role="presentation" onclick={() => lagreModalApen = false}>
          <div class="lagre-modal" role="dialog" onclick={(e) => e.stopPropagation()}>
            <div class="lagre-modal-tittel">💾 Lagre versjon</div>
            <input
              class="rediger-input"
              type="text"
              placeholder="Beskrivelse (valgfri), f.eks. «Med gresskar»"
              bind:value={lagreLabel}
              onkeydown={(e) => { if (e.key === "Enter") lagreVersjon(); }}
            />
            <div class="lagre-modal-knapper">
              <button class="lagre-modal-btn" onclick={lagreVersjon}>Lagre</button>
              <button class="lagre-modal-btn lagre-modal-avbryt" onclick={() => lagreModalApen = false}>Avbryt</button>
            </div>
          </div>
        </div>
      {/if}
```

- [ ] **Step 3: Legg til historikkpanel i `detail-body`**

Finn `<section class="detail-notat">` (etter næring/pris). Legg til etter denne seksjonen (dvs. etter `</section>` som lukker `detail-notat`):

```svelte
        {#if historikk.length > 0}
          <section class="versjon-historikk">
            <div class="versjon-historikk-tittel">📋 Versjonshistorikk ({historikk.length})</div>
            {#each historikk as v (v.id)}
              <div class="versjon-rad">
                <div class="versjon-rad-info">
                  <span class="versjon-tidspunkt">{fmtVersjonTid(v.lagretTidspunkt)}</span>
                  {#if v.label}
                    <span class="versjon-label">{v.label}</span>
                  {:else}
                    <span class="versjon-label ingen">Ingen beskrivelse</span>
                  {/if}
                </div>
                <div class="versjon-rad-knapper">
                  <button class="versjon-btn" onclick={() => sammenlignVersjon = v}>Sammenlign</button>
                  <button class="versjon-btn" onclick={() => gjenopprettVersjon(v)}>Gjenopprett</button>
                  <button class="versjon-btn versjon-btn-slett" onclick={() => slettVersjon(v.id)}>Slett</button>
                </div>
              </div>
            {/each}
          </section>
        {/if}
```

- [ ] **Step 4: Legg til CSS for lagremodal og historikk**

I `<style>`-blokken, legg til:

```css
  /* ── Lagremodal ── */
  .lagre-modal-bakgrunn {
    position: absolute; inset: 0; background: rgba(0,0,0,0.45);
    display: flex; align-items: center; justify-content: center; z-index: 10;
  }
  .lagre-modal {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; width: min(340px, 90%); display: flex; flex-direction: column; gap: 12px;
  }
  .lagre-modal-tittel { font-weight: 600; font-size: 1rem; }
  .lagre-modal-knapper { display: flex; gap: 8px; justify-content: flex-end; }
  .lagre-modal-btn {
    font-size: 0.85rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 6px 14px; cursor: pointer;
  }
  .lagre-modal-avbryt { color: var(--text-muted); }

  /* ── Historikkpanel ── */
  .versjon-historikk { margin-top: 20px; }
  .versjon-historikk-tittel { font-weight: 600; font-size: 0.9rem; margin-bottom: 8px; color: var(--text); }
  .versjon-rad {
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;
    padding: 8px 0; border-bottom: 1px solid var(--border);
  }
  .versjon-rad:last-child { border-bottom: none; }
  .versjon-rad-info { display: flex; flex-direction: column; gap: 2px; }
  .versjon-tidspunkt { font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-ui); }
  .versjon-label { font-size: 0.88rem; }
  .versjon-label.ingen { color: var(--text-muted); font-style: italic; }
  .versjon-rad-knapper { display: flex; gap: 6px; }
  .versjon-btn {
    font-size: 0.78rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 4px 10px; cursor: pointer;
  }
  .versjon-btn-slett { color: var(--text-muted); }
```

- [ ] **Step 5: Bygg og sjekk**

```
cd kokebok-app && npm run build
```

Forventet: bygger uten feil.

- [ ] **Step 6: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(versjonering): lagremodal og historikkpanel"
```

---

## Task 5: Sammenligningsoverlay

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `beregnDiff` fra `$lib/versjoner-logikk`; `sammenlignVersjon` state fra Task 3; `gjenopprettVersjon` fra Task 4

- [ ] **Step 1: Legg til sammenligningsoverlay**

Finn `{#if currentOppskrift}` (der `detail-overlay` er). Etter `{/if}` som lukker `detail-overlay`-blokken, men fortsatt inni `{#if currentOppskrift}`, legg til:

```svelte
  {#if sammenlignVersjon && currentOppskrift}
    {@const origKopi = kopiFraOppskrift(currentOppskrift)}
    {@const diff = beregnDiff(origKopi, sammenlignVersjon.kopi)}
    <div
      id="sammenlign-overlay"
      role="presentation"
      onclick={(e) => { if (e.target === e.currentTarget) sammenlignVersjon = null; }}
    >
      <div id="sammenlign-panel">
        <div class="sammenlign-topbar">
          <span class="sammenlign-tittel">📊 Sammenlign: {sammenlignVersjon.label || fmtVersjonTid(sammenlignVersjon.lagretTidspunkt)}</span>
          <button class="sammenlign-lukk" onclick={() => sammenlignVersjon = null}>✕ Lukk</button>
          <button class="sammenlign-bruk" onclick={() => gjenopprettVersjon(sammenlignVersjon!)}>Bruk denne versjonen</button>
        </div>

        <div class="sammenlign-body">
          <!-- Metadata -->
          {#if diff.navn.endret || diff.beskrivelse.endret || diff.porsjoner.endret || diff.tid.endret}
            <div class="sammenlign-seksjon-tittel">Metadata</div>
            <div class="sammenlign-meta-grid">
              {#if diff.navn.endret}
                <div class="sammenlign-meta-felt">Navn</div>
                <div class="sammenlign-orig">{diff.navn.orig}</div>
                <div class="sammenlign-versjon">{diff.navn.versjon}</div>
              {/if}
              {#if diff.beskrivelse.endret}
                <div class="sammenlign-meta-felt">Beskrivelse</div>
                <div class="sammenlign-orig">{diff.beskrivelse.orig ?? "–"}</div>
                <div class="sammenlign-versjon">{diff.beskrivelse.versjon ?? "–"}</div>
              {/if}
              {#if diff.porsjoner.endret}
                <div class="sammenlign-meta-felt">Porsjoner</div>
                <div class="sammenlign-orig">{diff.porsjoner.orig ?? "–"}</div>
                <div class="sammenlign-versjon">{diff.porsjoner.versjon ?? "–"}</div>
              {/if}
              {#if diff.tid.endret}
                <div class="sammenlign-meta-felt">Tid</div>
                <div class="sammenlign-orig">{diff.tid.orig ?? "–"}</div>
                <div class="sammenlign-versjon">{diff.tid.versjon ?? "–"}</div>
              {/if}
            </div>
          {/if}

          <!-- Ingredienser -->
          <div class="sammenlign-seksjon-tittel">Ingredienser</div>
          <div class="sammenlign-tabell-hdr">
            <div>Original</div><div>Din versjon</div>
          </div>
          {#each diff.ingredienser as d}
            <div
              class="sammenlign-rad"
              class:endret={d.endret && d.orig !== null && d.versjon !== null}
              class:ny={d.orig === null}
              class:slettet={d.versjon === null}
            >
              <div class="sammenlign-celle">
                {#if d.orig}
                  {d.orig.mengde ?? ""} {d.orig.enhet ?? ""} {d.orig.navn ?? ""}
                {:else}
                  <span class="sammenlign-tom">–</span>
                {/if}
              </div>
              <div class="sammenlign-celle">
                {#if d.versjon}
                  {d.versjon.mengde ?? ""} {d.versjon.enhet ?? ""} {d.versjon.navn ?? ""}
                {:else}
                  <span class="sammenlign-tom">–</span>
                {/if}
              </div>
            </div>
          {/each}

          <!-- Trinn -->
          <div class="sammenlign-seksjon-tittel">Fremgangsmåte</div>
          <div class="sammenlign-tabell-hdr">
            <div>Original</div><div>Din versjon</div>
          </div>
          {#each diff.trinn as d, i}
            <div
              class="sammenlign-rad"
              class:endret={d.endret && d.orig !== null && d.versjon !== null}
              class:ny={d.orig === null}
              class:slettet={d.versjon === null}
            >
              <div class="sammenlign-celle sammenlign-celle-trinn">
                {#if d.orig}<span class="sammenlign-trinn-nr">{i + 1}.</span> {d.orig.tekst}{:else}<span class="sammenlign-tom">–</span>{/if}
              </div>
              <div class="sammenlign-celle sammenlign-celle-trinn">
                {#if d.versjon}<span class="sammenlign-trinn-nr">{i + 1}.</span> {d.versjon.tekst}{:else}<span class="sammenlign-tom">–</span>{/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}
```

- [ ] **Step 2: Legg til CSS for sammenligningsoverlay**

I `<style>`-blokken, legg til:

```css
  /* ── Sammenligningsoverlay ── */
  #sammenlign-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    display: flex; align-items: stretch; justify-content: flex-end; z-index: 200;
  }
  #sammenlign-panel {
    background: var(--bg); width: min(720px, 100vw);
    display: flex; flex-direction: column; overflow: hidden;
  }
  .sammenlign-topbar {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    padding: 12px 16px; border-bottom: 1px solid var(--border);
  }
  .sammenlign-tittel { font-weight: 600; flex: 1; font-size: 0.92rem; }
  .sammenlign-lukk, .sammenlign-bruk {
    font-size: 0.82rem; font-family: var(--font-ui);
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 5px 12px; cursor: pointer;
  }
  .sammenlign-body { flex: 1; overflow-y: auto; padding: 16px; }
  .sammenlign-seksjon-tittel { font-weight: 600; font-size: 0.88rem; margin: 16px 0 6px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
  .sammenlign-meta-grid {
    display: grid; grid-template-columns: auto 1fr 1fr; gap: 4px 12px; margin-bottom: 8px;
    font-size: 0.88rem;
  }
  .sammenlign-meta-felt { color: var(--text-muted); font-family: var(--font-ui); }
  .sammenlign-tabell-hdr {
    display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
    font-size: 0.78rem; color: var(--text-muted); font-family: var(--font-ui);
    border-bottom: 1px solid var(--border); padding-bottom: 4px; margin-bottom: 4px;
  }
  .sammenlign-rad {
    display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
    padding: 4px 6px; border-radius: var(--radius-sm); font-size: 0.88rem;
  }
  .sammenlign-rad.endret { background: rgba(255, 200, 0, 0.12); }
  .sammenlign-rad.ny { background: rgba(0, 180, 80, 0.12); }
  .sammenlign-rad.slettet { background: rgba(220, 50, 50, 0.12); }
  .sammenlign-celle { padding: 2px 0; }
  .sammenlign-celle-trinn { white-space: pre-wrap; }
  .sammenlign-trinn-nr { font-weight: 600; color: var(--text-muted); margin-right: 4px; }
  .sammenlign-orig { color: var(--text-muted); }
  .sammenlign-versjon { color: var(--text); }
  .sammenlign-tom { color: var(--text-muted); font-style: italic; }
```

- [ ] **Step 3: Bygg og sjekk**

```
cd kokebok-app && npm run build
```

Forventet: bygger uten feil.

- [ ] **Step 4: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(versjonering): sammenligningsoverlay med strukturell diff"
```

---

## Task 6: Manuell e2e-sjekk

Ingen kode skrives. Kjør `npm run tauri dev` fra `kokebok-app` og verifiser følgende:

- [ ] **Åpne en oppskrift uten aktiv profil** — "Rediger"-knappen er IKKE synlig.

- [ ] **Aktiver en profil, åpne en oppskrift** — "Rediger"-knappen er synlig.

- [ ] **Klikk Rediger** — metadata-felt (navn, beskrivelse, porsjoner, tid), ingrediensliste med redigerbare felter og trinnliste med textarea vises.

- [ ] **Rediger ingrediensmengde** — etter 800 ms dukker `versjoner.json` opp i appdata (Windows: `%APPDATA%\com.kokt.nok\`) med kladd lagret.

- [ ] **Klikk "Lagre versjon"** — lagremodal åpnes. Skriv en label, klikk "Lagre" — redigeringsmodus lukkes, historikkpanel vises nederst i detaljpanelet.

- [ ] **Klikk "Sammenlign"** — sammenligningsoverlay åpnes. Endrede ingredienser har gul bakgrunn. "✕ Lukk" lukker overlyet.

- [ ] **Klikk "Gjenopprett"** — kladden oppdateres med versjonsdata, redigeringsmodus åpnes.

- [ ] **Klikk "Avbryt" i redigeringsmodus** — redigeringsmodus lukkes, ingen data tapes fra historikken.

- [ ] **Slett en versjon** — versjonen fjernes fra historikklisten.

- [ ] **Lukk og gjenåpne oppskriften** — kladd og historikk er fortsatt til stede.

- [ ] **Commit**

```bash
git commit --allow-empty -m "test(versjonering): manuell e2e godkjent"
```

---

## Etter alle tasks

Kjør tester én siste gang:

```
node --experimental-strip-types kokebok-app/src/lib/versjoner-logikk.test.mjs
```

Forventet: 9 tester OK.

Bruk `superpowers:finishing-a-development-branch` for merge/push.
