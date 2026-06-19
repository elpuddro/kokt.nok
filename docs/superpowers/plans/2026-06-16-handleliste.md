# Handleliste — Implementeringsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La brukeren legge oppskrifter i en handleliste, se ingrediensene sammenslått (skalert per valgt porsjonsantall) med estimert totalsum, og kunne tømme/fjerne/justere — persistert via Tauri Store.

**Architecture:** Tynn `$lib/handleliste.ts` over Tauri Store (speiler `favoritter.ts`), en ren `slåSammen`-aggregeringsfunksjon, og UI i `+page.svelte` som gjenbruker favoritt-modus-mønsteret. Ingen skriving til `kokt.db`.

**Tech Stack:** Svelte 5 (runes), Tauri 2 (`@tauri-apps/plugin-store`), TypeScript.

**Spec:** `docs/superpowers/specs/2026-06-16-handleliste-design.md`

**Merk:** Ingen automatisk frontend-testsuite. Verifikasjon: `npm run build` + manuell e2e (Task 6). Den ene rene funksjonen (`slåSammen`) verifiseres med en frittstående node-snutt der den kan testes uten Tauri. Hver task etterlater prosjektet byggbart. **Skraperen kan kjøre samtidig — vi rører ikke `kokt.db`.**

**Anker-fakta (verifisert mot koden):**
- `pris`-objektet fra `hent_oppskrift` har felt `totalt` (ikke `total`), `priset`, `totalt_antall`. Per-oppskrift total skaleres `pris.totalt * curP/origP`.
- Ingredienser har `mengde` (REAL|null), `enhet` (str|null), `navn`, `raatekst`.
- `scaleMengde(m, fromP, toP)` og `fmtMengde(v)` finnes alt i `+page.svelte`.
- Favoritt-modus bruker `currentKategori === "__fav__"`; vi legger til `"__handle__"`.

---

## Filstruktur

| Fil | Ansvar | Endring |
|-----|--------|---------|
| `kokebok-app/src/lib/handleliste.ts` | Tauri Store-wrapper (persistering) | Create |
| `kokebok-app/src/routes/+page.svelte` | State, aggregering, legg-til-knapp, sidebar, visning | Modify |

**Rekkefølge:** Store-wrapper (T1) → state + last (T2) → legg-til-knapp i detalj (T3) → sidebar-knapp + modus (T4) → aggregering + visning (T5) → manuell e2e (T6).

---

## Task 1: Store-wrapper `handleliste.ts`

Speiler `favoritter.ts`, men lagrer `{id, porsjoner}`-objekter.

**Files:**
- Create: `kokebok-app/src/lib/handleliste.ts`

- [ ] **Step 1: Opprett modulen**

Create `kokebok-app/src/lib/handleliste.ts`:
```ts
// Handlelista persisteres i en JSON-fil i appens data-katalog via Tauri Store
// (samme mønster som favoritter.ts). kokt.db er read-only.
import { load, type Store } from "@tauri-apps/plugin-store";

const FIL = "handleliste.json";
const NOKKEL = "poster";

export type HandlelistePost = { id: number; porsjoner: number };

let storePromise: Promise<Store> | null = null;
function hentStore(): Promise<Store> {
  if (!storePromise) storePromise = load(FIL);
  return storePromise;
}

async function lagre(poster: HandlelistePost[]): Promise<void> {
  try {
    const store = await hentStore();
    await store.set(NOKKEL, poster);
    await store.save();
  } catch (err) {
    console.error("handleliste lagring feilet:", err);
  }
}

/** Last handlelista. Tom liste ved feil (ikke kritisk). */
export async function handlelisteLast(): Promise<HandlelistePost[]> {
  try {
    const store = await hentStore();
    return (await store.get<HandlelistePost[]>(NOKKEL)) ?? [];
  } catch (err) {
    console.error("handlelisteLast feilet:", err);
    return [];
  }
}

/** Legg til (eller oppdater porsjoner hvis id finnes). Returnerer ny liste. */
export async function handlelisteLeggTil(
  id: number, porsjoner: number, liste: HandlelistePost[],
): Promise<HandlelistePost[]> {
  const finnes = liste.some((p) => p.id === id);
  const ny = finnes
    ? liste.map((p) => (p.id === id ? { id, porsjoner } : p))
    : [...liste, { id, porsjoner }];
  await lagre(ny);
  return ny;
}

/** Fjern én oppskrift. Returnerer ny liste. */
export async function handlelisteFjern(
  id: number, liste: HandlelistePost[],
): Promise<HandlelistePost[]> {
  const ny = liste.filter((p) => p.id !== id);
  await lagre(ny);
  return ny;
}

/** Endre porsjoner for én post. Returnerer ny liste. */
export async function handlelisteSettPorsjoner(
  id: number, porsjoner: number, liste: HandlelistePost[],
): Promise<HandlelistePost[]> {
  const ny = liste.map((p) => (p.id === id ? { id, porsjoner } : p));
  await lagre(ny);
  return ny;
}

/** Tøm hele lista. Returnerer tom liste. */
export async function handlelisteTøm(): Promise<HandlelistePost[]> {
  await lagre([]);
  return [];
}
```

- [ ] **Step 2: Bygg (typecheck)**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil.

- [ ] **Step 3: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/lib/handleliste.ts
git commit -m "feat(handleliste): Tauri Store-wrapper"
```

---

## Task 2: State + lasting i `+page.svelte`

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (import ~linje 4; state ~linje 31; onMount ~linje 215)

- [ ] **Step 1: Importer modulen**

I `<script>`, etter `import { favorittLast, favorittToggle } from "$lib/favoritter";` (linje 4), legg til:
```ts
  import {
    handlelisteLast, handlelisteLeggTil, handlelisteFjern,
    handlelisteSettPorsjoner, handlelisteTøm, type HandlelistePost,
  } from "$lib/handleliste";
```

- [ ] **Step 2: Legg til state**

Etter `let favoritter = $state<Set<number>>(new Set());` (linje 31), legg til:
```ts
  let handleliste = $state<HandlelistePost[]>([]);
```

- [ ] **Step 3: Last ved oppstart**

I `onMount` (linje ~215), etter `favoritter = await favorittLast();`, legg til:
```ts
    handleliste = await handlelisteLast();
```

- [ ] **Step 4: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` (importen brukes i senere tasks; `handleliste`-state er lest i onMount).

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(handleliste): state + lasting ved oppstart"
```

---

## Task 3: «Legg i handleliste»-knapp i detaljvisningen

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (toggle-funksjon ~linje 132; detail-topbar ~linje 363-370)

- [ ] **Step 1: Legg til legg-til-funksjon**

I `<script>`, etter `toggleFavoritt`-funksjonen (rundt linje 132-136), legg til:
```ts
  async function leggIHandleliste(id: number, porsjoner: number) {
    handleliste = await handlelisteLeggTil(id, porsjoner, handleliste);
  }
```

- [ ] **Step 2: Legg til knappen i detalj-topbar**

I `.detail-topbar` (linje ~363-370), rett ETTER den lukkende `</button>` for `detail-fav` (linje 370), legg til:
```svelte
        <button
          class="detail-handle"
          class:aktiv={handleliste.some((p) => p.id === opp.id)}
          title={handleliste.some((p) => p.id === opp.id) ? "I handlelista" : "Legg i handleliste"}
          onclick={() => leggIHandleliste(opp.id, curP)}
        >{handleliste.some((p) => p.id === opp.id) ? "🛒 I handleliste" : "🛒 Legg i handleliste"}</button>
```
(`curP` er det innstilte porsjonsantallet i detaljen.)

- [ ] **Step 3: Stil for knappen**

I `<style>`, rett etter `.detail-fav.aktiv`-regelen (søk «detail-fav»), legg til:
```css
  .detail-handle {
    border: 1px solid var(--border);
    background: var(--bg-warm);
    color: var(--text);
    padding: 6px 12px;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .detail-handle.aktiv { border-color: var(--accent-dark); }
```

- [ ] **Step 4: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil.

- [ ] **Step 5: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(handleliste): legg-til-knapp i detaljvisning"
```

---

## Task 4: Sidebar-knapp + handleliste-modus

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (velgFavoritter ~linje 124; sidebar ~linje 255-262; header ~linje 282)

- [ ] **Step 1: Legg til modus-velger**

I `<script>`, etter `velgFavoritter`-funksjonen (søk «velgFavoritter»), legg til:
```ts
  function velgHandleliste() {
    currentKategori = "__handle__";
    side = 1;
    sok = "";
    oppskrifter = [];   // gridet brukes ikke i handleliste-modus
  }
```

- [ ] **Step 2: Sidebar-knapp**

I `<nav id="kategori-liste">`, rett ETTER favoritt-knappens lukkende `</button>` (linje ~262, knappen med `kat-teller`/`favoritter.size`), legg til:
```svelte
    <button
      class="kat-btn"
      class:active={currentKategori === "__handle__"}
      onclick={velgHandleliste}
    >
      <span class="kat-emoji">🛒</span>
      <span class="kat-navn">Handleliste</span>
      <span class="kat-teller">{handleliste.length}</span>
    </button>
```

- [ ] **Step 3: Skjul søkefeltet også i handleliste-modus**

Søkefeltet er pakket i `{#if currentKategori !== "__fav__"}` (linje ~230). Endre betingelsen til å skjule i begge modi:
```svelte
  {#if currentKategori !== "__fav__" && currentKategori !== "__handle__"}
```

- [ ] **Step 4: Header-tittel**

I `#header-tittel` (linje ~282), legg til en gren FØRST i `{#if}`-kjeden:
```svelte
      {#if currentKategori === "__handle__"}
        🛒 Handleliste
      {:else if currentKategori === "__fav__"}
```
(behold resten av kjeden uendret etter `{:else if currentKategori === "__fav__"}`).

- [ ] **Step 5: Skjul paginering i handleliste-modus**

Pagineringen er betinget `{#if currentKategori !== "__fav__" && pages > 1}` (linje ~339). Endre til:
```svelte
    {#if currentKategori !== "__fav__" && currentKategori !== "__handle__" && pages > 1}
```

- [ ] **Step 6: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil. (Selve visnings-innholdet kommer i Task 5; knappen bytter modus men gridet er tomt enn så lenge.)

- [ ] **Step 7: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(handleliste): sidebar-knapp + modus"
```

---

## Task 5: Aggregering + handleliste-visning

Henter oppskriftene i lista, slår sammen ingrediensene, viser totalsum + oppskriftsrader m/porsjonsjustering/fjern + tøm.

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte` (aggregering i script; visning i markup; stil)

- [ ] **Step 1: Aggregert state ($derived via async)**

Aggregering krever DB-kall (`hent_oppskrift` per post), så vi bruker en eksplisitt last-funksjon + state (ikke `$derived`, som ikke kan være async). I `<script>`, etter `velgHandleliste`, legg til:
```ts
  // Aggregert handleliste-visning. Lastes når modus åpnes eller lista endres.
  type SamletIngrediens = { navn: string; enhet: string | null; mengde: number | null; raatekst: string };
  let handleAgg = $state<{
    ingredienser: SamletIngrediens[];
    totalsum: number;
    oppskrifter: { id: number; navn: string; porsjoner: number; origP: number }[];
  }>({ ingredienser: [], totalsum: 0, oppskrifter: [] });
  let handleLaster = $state(false);

  function slåSammen(
    poster: { opp: any; porsjoner: number }[],
  ): SamletIngrediens[] {
    const kart = new Map<string, SamletIngrediens>();
    for (const { opp, porsjoner } of poster) {
      const origP = opp.porsjoner || 4;
      for (const i of opp.ingredienser ?? []) {
        const navn = (i.navn ?? i.raatekst ?? "").trim();
        if (!navn) continue;
        const enhet = i.enhet ?? null;
        const nokkel = navn.toLowerCase() + "|" + (enhet ?? "");
        const skalert = i.mengde == null ? null : scaleMengde(i.mengde, origP, porsjoner);
        const eks = kart.get(nokkel);
        if (eks) {
          if (skalert != null) eks.mengde = (eks.mengde ?? 0) + skalert;
        } else {
          kart.set(nokkel, { navn, enhet, mengde: skalert, raatekst: i.raatekst ?? navn });
        }
      }
    }
    return [...kart.values()].sort((a, b) => a.navn.localeCompare(b.navn, "nb"));
  }

  async function lastHandleAgg() {
    handleLaster = true;
    try {
      const poster: { opp: any; porsjoner: number }[] = [];
      for (const p of handleliste) {
        try {
          const opp: any = await invoke("hent_oppskrift", { id: p.id });
          if (opp) poster.push({ opp, porsjoner: p.porsjoner });
        } catch (err) {
          console.error("hent_oppskrift i handleliste feilet:", p.id, err);
        }
      }
      let sum = 0;
      for (const { opp, porsjoner } of poster) {
        const origP = opp.porsjoner || 4;
        const pr = opp.pris;
        if (pr && pr.totalt > 0) sum += pr.totalt * (porsjoner / origP);
      }
      handleAgg = {
        ingredienser: slåSammen(poster),
        totalsum: Math.round(sum),
        oppskrifter: poster.map(({ opp, porsjoner }) => ({
          id: opp.id, navn: opp.navn, porsjoner, origP: opp.porsjoner || 4,
        })),
      };
    } finally {
      handleLaster = false;
    }
  }
```

- [ ] **Step 2: Last aggregering når modus åpnes**

Oppdater `velgHandleliste` (fra Task 4) til å laste aggregeringen. Endre funksjonen til:
```ts
  function velgHandleliste() {
    currentKategori = "__handle__";
    side = 1;
    sok = "";
    oppskrifter = [];
    lastHandleAgg();
  }
```

- [ ] **Step 3: Handlinger som re-aggregerer**

I `<script>`, etter `lastHandleAgg`, legg til:
```ts
  async function handleEndrePorsjoner(id: number, origP: number, delta: number) {
    const post = handleliste.find((p) => p.id === id);
    if (!post) return;
    const ny = Math.max(1, Math.min(post.porsjoner + delta, 100));
    handleliste = await handlelisteSettPorsjoner(id, ny, handleliste);
    await lastHandleAgg();
  }
  async function handleFjern(id: number) {
    handleliste = await handlelisteFjern(id, handleliste);
    await lastHandleAgg();
  }
  async function handleTøm() {
    handleliste = await handlelisteTøm();
    await lastHandleAgg();
  }
```

- [ ] **Step 4: Visnings-markup**

I `<main id="main">`, rett ETTER `</div>` som lukker `#main-header` og FØR `<div id="grid-wrap">` (søk «grid-wrap»), legg til en handleliste-blokk som vises i modus:
```svelte
  {#if currentKategori === "__handle__"}
    <div id="handle-wrap">
      {#if handleliste.length === 0}
        <div class="empty-state">
          <div class="empty-icon">🛒</div>
          <h3>Handlelista er tom</h3>
          <p>Åpne en oppskrift og trykk «🛒 Legg i handleliste».</p>
        </div>
      {:else}
        <div class="handle-oppskrifter">
          <div class="handle-topp">
            <h2>Oppskrifter ({handleAgg.oppskrifter.length})</h2>
            <button class="handle-tom" onclick={handleTøm}>🗑 Tøm handleliste</button>
          </div>
          {#each handleAgg.oppskrifter as o (o.id)}
            <div class="handle-rad">
              <span class="handle-navn">{o.navn}</span>
              <span class="handle-porsjoner">
                <button class="portion-btn" disabled={o.porsjoner <= 1} onclick={() => handleEndrePorsjoner(o.id, o.origP, -1)}>−</button>
                <span>{o.porsjoner} porsjoner</span>
                <button class="portion-btn" onclick={() => handleEndrePorsjoner(o.id, o.origP, 1)}>+</button>
              </span>
              <button class="handle-fjern" title="Fjern" onclick={() => handleFjern(o.id)}>✕</button>
            </div>
          {/each}
        </div>

        <div class="handle-ingredienser">
          <h2>Innkjøpsliste</h2>
          {#if handleLaster}
            <p>Laster…</p>
          {:else}
            <ul>
              {#each handleAgg.ingredienser as i (i.navn + "|" + (i.enhet ?? ""))}
                <li>
                  <span class="handle-mengde">{fmtMengde(i.mengde)} {i.enhet ?? ""}</span>
                  <span class="handle-ingnavn">{i.navn}</span>
                </li>
              {/each}
            </ul>
            {#if handleAgg.totalsum > 0}
              <div class="handle-sum">💰 Estimert totalsum: ca. {handleAgg.totalsum} kr</div>
            {/if}
          {/if}
        </div>
      {/if}
    </div>
  {/if}
```

- [ ] **Step 5: Skjul gridet i handleliste-modus**

`#grid-wrap` skal ikke vises i handleliste-modus. Finn `<div id="grid-wrap">` og pakk det (eller legg til betingelse). Endre `<div id="grid-wrap">` til:
```svelte
  {#if currentKategori !== "__handle__"}
  <div id="grid-wrap">
```
og legg til en lukkende `{/if}` rett etter `</div>` som lukker `#grid-wrap` (den som står før `</main>`). VERIFISER ved bygg at `{#if}/{/if}` balanserer.

- [ ] **Step 6: Stil**

I `<style>`, etter `.detail-handle`-reglene, legg til:
```css
  #handle-wrap { padding: 24px 32px; max-width: 900px; }
  .handle-topp { display: flex; justify-content: space-between; align-items: center; }
  .handle-tom {
    border: 1px solid var(--border); background: var(--bg-warm); color: var(--text);
    padding: 6px 12px; border-radius: var(--radius); cursor: pointer; font-size: 0.85rem;
  }
  .handle-rad {
    display: flex; align-items: center; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid var(--border-light);
  }
  .handle-navn { flex: 1; font-weight: 600; }
  .handle-porsjoner { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: var(--text-muted); }
  .handle-fjern {
    border: none; background: none; cursor: pointer; color: var(--text-muted); font-size: 1rem;
  }
  .handle-ingredienser { margin-top: 28px; }
  .handle-ingredienser ul { list-style: none; padding: 0; }
  .handle-ingredienser li {
    display: flex; gap: 12px; padding: 6px 0; border-bottom: 1px solid var(--border-light);
  }
  .handle-mengde { min-width: 90px; color: var(--accent-dark); font-weight: 600; }
  .handle-sum {
    margin-top: 18px; font-size: 1.05rem; font-weight: 700; color: var(--text);
  }
```

- [ ] **Step 7: Bygg**

Run: `cd "<repo>/kokebok-app" && npm run build`
Expected: `✓ built` uten feil. (Hvis `{#if}/{/if}`-ubalanse fra Step 5: Svelte-kompilatoren gir tydelig feil — rett opp til `✓ built`.)

- [ ] **Step 8: Commit**

```bash
cd "<repo>" && git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(handleliste): aggregering + visning (ingredienser, totalsum, juster/fjern/tøm)"
```

---

## Task 6: Manuell ende-til-ende-verifikasjon

Krever kjørende app. MANUELT (menneske).

**Files:** ingen (verifikasjon).

- [ ] **Step 1: Kjør appen**

Run: `cd "<repo>/kokebok-app" && npm run tauri dev`

- [ ] **Step 2: Verifiser (sjekkliste)**

- Åpne en oppskrift, still porsjoner, trykk «🛒 Legg i handleliste» → knappen viser «🛒 I handleliste».
- Legg til en oppskrift til som deler en ingrediens (f.eks. begge har egg/melk) → i handleliste-visningen er den felles ingrediensen **summert til én linje**.
- Sidebar «🛒 Handleliste» viser teller = antall oppskrifter; visningen viser innkjøpsliste + estimert totalsum + oppskriftsrader.
- Juster porsjoner (±) på en oppskriftsrad → ingrediensmengder OG totalsum endrer seg.
- Fjern én oppskrift (✕) → forsvinner fra lista, aggregering oppdateres.
- «🗑 Tøm handleliste» → tom-tilstand «Handlelista er tom».
- Søkefelt + paginering er skjult i handleliste-modus.
- Lukk appen helt og start på nytt → handlelista består (lest fra handleliste.json).

---

## Self-review-notater (utført ved planskriving)

- **Spec-dekning:** Store-wrapper m/`{id,porsjoner}` (T1), state+last (T2), legg-til
  i detalj m/`curP` (T3), sidebar-knapp+modus+skjul søk/paginering (T4),
  aggregering navn+enhet + totalsum + juster/fjern/tøm + tom-tilstand (T5),
  manuell e2e (T6). Persistering, sammenslåing, totalsum, alle 3 handlinger
  dekket. Ingen DB-skriving.
- **Navn/typer konsistente:** `HandlelistePost{id,porsjoner}` definert T1, brukt
  T2/T3/T5. `handlelisteLeggTil/Fjern/SettPorsjoner/Tøm/Last` likt i T1 og kallere.
  `currentKategori === "__handle__"` brukt likt i T4 (velg, sidebar, søk, header,
  paginering) og T5 (visning, skjul grid). `slåSammen`/`lastHandleAgg`/`handleAgg`
  konsistent i T5.
- **Verifisert mot kode:** pris-felt `pris.totalt` (ikke `total`), `priset`,
  `totalt_antall` — lest fra `prisVist` i +page.svelte. Ingrediensfelt
  `mengde/enhet/navn/raatekst`. `scaleMengde(m,fromP,toP)`/`fmtMengde` finnes.
  `curP`/`origP`/`portion-btn`-klassen gjenbrukt fra detalj. Favoritt-ankrene
  (`__fav__`, sidebar-knapp, detail-fav, søk/paginering-betingelser) bekreftet
  via grep med linjenr.
- **Async-merknad:** aggregering kan ikke være `$derived` (async DB-kall), derfor
  eksplisitt `lastHandleAgg()` kalt fra modus-velger + hver mutasjon (T5 Step 2-3).
- **Skraper-trygt:** kun frontend + Store; ingen `kokt.db`-skriving, så det er
  trygt å implementere mens godt.no-skrapingen kjører.
