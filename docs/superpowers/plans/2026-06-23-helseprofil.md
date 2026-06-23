# Helseprofil og næringsanalyse — Implementeringsplan (#20)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flerbrukerprofiler med TDEE-beregning, dagsbehov-prosenter i oppskriftsdetaljvisningen, automatisk dagsmål i matplanleggeren, og en About-seksjon i Innstillinger for hjemmebygg.

**Architecture:** All TDEE-logikk i ny `src/lib/helse.ts`. Profildata i Tauri Store (`profiler.json`). About-info fra Rust-kommando bak `#[cfg(feature = "about")]`. UI-endringer samlet i `+page.svelte`.

**Tech Stack:** Svelte 5 runes (`$state`, `$derived`), TypeScript, Tauri Store (`@tauri-apps/plugin-store`), Rust (Tauri 2, serde), rusqlite (read-only).

## Global Constraints

- Svelte 5 runes kun — ingen `$:`, ingen `writable()` stores
- Tauri Store brukes eksakt som `lager.ts`, `favoritter.ts`, `notater.ts`: `await load("filnavn.json")`, `store.get("nøkkel")`, `store.set("nøkkel", verdi)`, `store.save()`
- `invoke` fra `@tauri-apps/api/core` — ikke `@tauri-apps/api`
- Rust: `#[tauri::command]` + registrering i `tauri::generate_handler![]` i `run()`
- Ingen nye npm-pakker — `crypto.randomUUID()` for UUID
- Skrubbe-gate: fengselsbygg kompileres alltid uten `--features about`; ingen personinfo i binær
- Commit-meldinger uten "Co-Authored-By"-trailer

---

## Filstruktur

| Fil | Rolle |
|-----|-------|
| `kokebok-app/src/lib/helse.ts` | Ny — typer, TDEE, dagsbehov, dekningsProsent, Tauri Store CRUD |
| `kokebok-app/src/routes/+page.svelte` | Modifisert — profilvelger, Helseprofil-fane, dagsbehov-kort, matplan-prepopulering |
| `kokebok-app/src-tauri/src/lib.rs` | Modifisert — `about_info` kommando bak `#[cfg(feature = "about")]` |
| `kokebok-app/src-tauri/Cargo.toml` | Modifisert — `[features] about = []` |

---

## Task 1: `helse.ts` — typer, TDEE og Store CRUD

**Files:**
- Create: `kokebok-app/src/lib/helse.ts`

**Interfaces:**
- Produces: `Brukerprofil`, `ProfilStore`, `Dagsbehov`, `tdee(p)`, `dagsbehov(p)`, `dekningsProsent(næring, behov)`, `profilLast()`, `profilLagre(store)`, `profilSettAktiv(id)`, `profilOpprett(felt)`, `profilSlett(id)`

- [ ] **Step 1: Skriv `helse.ts`**

Opprett filen `kokebok-app/src/lib/helse.ts` med følgende innhold:

```typescript
import { load } from "@tauri-apps/plugin-store";

export type Aktivitetsnivå = "stillesittende" | "lett" | "moderat" | "aktiv" | "veldig_aktiv";
export type Mål = "nedgang" | "vedlikehold" | "oppgang";

export interface Brukerprofil {
  id: string;
  navn: string;
  kjønn: "mann" | "kvinne";
  alder: number;
  høyde: number;
  vekt: number;
  aktivitet: Aktivitetsnivå;
  mål: Mål;
}

export interface ProfilStore {
  profiler: Brukerprofil[];
  aktivId: string | null;
}

export interface Dagsbehov {
  kcal: number;
  protein: number;
  fett: number;
  karbo: number;
}

const AKTIVITETSFAKTOR: Record<Aktivitetsnivå, number> = {
  stillesittende: 1.2,
  lett: 1.375,
  moderat: 1.55,
  aktiv: 1.725,
  veldig_aktiv: 1.9,
};

const MÅLSJUSTERING: Record<Mål, number> = {
  nedgang: -500,
  vedlikehold: 0,
  oppgang: 500,
};

function bmr(p: Brukerprofil): number {
  const base = 10 * p.vekt + 6.25 * p.høyde - 5 * p.alder;
  return p.kjønn === "mann" ? base + 5 : base - 161;
}

export function tdee(p: Brukerprofil): number {
  return Math.round(bmr(p) * AKTIVITETSFAKTOR[p.aktivitet] + MÅLSJUSTERING[p.mål]);
}

export function dagsbehov(p: Brukerprofil): Dagsbehov {
  const t = tdee(p);
  return {
    kcal: t,
    protein: Math.round((t * 0.15) / 4),
    fett: Math.round((t * 0.30) / 9),
    karbo: Math.round((t * 0.55) / 4),
  };
}

export function dekningsProsent(næring: number, behov: number): number {
  if (!behov) return 0;
  return Math.round((næring / behov) * 100);
}

const TOM_STORE: ProfilStore = { profiler: [], aktivId: null };

export async function profilLast(): Promise<ProfilStore> {
  const store = await load("profiler.json");
  const data = await store.get<ProfilStore>("profiler");
  return data ?? TOM_STORE;
}

async function _lagre(ps: ProfilStore): Promise<void> {
  const store = await load("profiler.json");
  await store.set("profiler", ps);
  await store.save();
}

export async function profilSettAktiv(id: string | null): Promise<ProfilStore> {
  const ps = await profilLast();
  ps.aktivId = id;
  await _lagre(ps);
  return ps;
}

export async function profilOpprett(felt: Omit<Brukerprofil, "id">): Promise<ProfilStore> {
  const ps = await profilLast();
  const ny: Brukerprofil = { id: crypto.randomUUID(), ...felt };
  ps.profiler.push(ny);
  if (!ps.aktivId) ps.aktivId = ny.id;
  await _lagre(ps);
  return ps;
}

export async function profilOppdater(oppdatert: Brukerprofil): Promise<ProfilStore> {
  const ps = await profilLast();
  ps.profiler = ps.profiler.map((p) => (p.id === oppdatert.id ? oppdatert : p));
  await _lagre(ps);
  return ps;
}

export async function profilSlett(id: string): Promise<ProfilStore> {
  const ps = await profilLast();
  ps.profiler = ps.profiler.filter((p) => p.id !== id);
  if (ps.aktivId === id) ps.aktivId = ps.profiler[0]?.id ?? null;
  await _lagre(ps);
  return ps;
}
```

- [ ] **Step 2: Verifiser TypeScript kompilering**

```powershell
cd kokebok-app && npx tsc --noEmit
```

Forventet: ingen feil. Hvis feil om `@tauri-apps/plugin-store` — sjekk at `package.json` allerede har den (den gjør det fra handleliste/lager).

- [ ] **Step 3: Commit**

```bash
git add kokebok-app/src/lib/helse.ts
git commit -m "feat(helse): TDEE-beregning og profilStore CRUD"
```

---

## Task 2: About-kommando i Rust

**Files:**
- Modify: `kokebok-app/src-tauri/Cargo.toml`
- Modify: `kokebok-app/src-tauri/src/lib.rs`

**Interfaces:**
- Produces: Rust-kommando `about_info()` returnerer JSON `{navn, epost, versjon, beskrivelse}` kun når feature `about` er aktiv

- [ ] **Step 1: Legg til feature i `Cargo.toml`**

Åpne `kokebok-app/src-tauri/Cargo.toml`. Legg til etter `[package]`-seksjonen (men før `[dependencies]`):

```toml
[features]
about = []
```

- [ ] **Step 2: Legg til `AboutInfo` og `about_info` i `lib.rs`**

Åpne `kokebok-app/src-tauri/src/lib.rs`. Legg til rett før `pub fn run()`:

```rust
#[cfg(feature = "about")]
#[derive(serde::Serialize)]
struct AboutInfo {
    navn: &'static str,
    epost: &'static str,
    versjon: &'static str,
    beskrivelse: &'static str,
}

#[cfg(feature = "about")]
#[tauri::command]
fn about_info() -> AboutInfo {
    AboutInfo {
        navn: "Frank Simonsen",
        epost: "elpuddro@gmail.com",
        versjon: env!("CARGO_PKG_VERSION"),
        beskrivelse: "Kokebok er en offline basert oppskriftssamling for Windows og Linux. \
            Appen inneholder over 5 900 norske oppskrifter fra matprat.no og godt.no, \
            med næringsinfo fra Matvaretabellen, smarte funksjoner som ukesmenyplanlegger, \
            handleliste, kjøleskapsstyring og kostholdsfiltre med mere.",
    }
}
```

- [ ] **Step 3: Registrer kommandoen betinget i `run()`**

Finn `pub fn run()` i `lib.rs`. Den inneholder `tauri::Builder::default()` med `.invoke_handler(tauri::generate_handler![...])`. Legg til `about_info` betinget.

Mønsteret er: legg `about_info` i `generate_handler!`-listen, men wrap hele builder-oppsettet slik at kommandoen kun er tilgjengelig med feature. Den enkleste måten i Tauri 2 er å alltid inkludere kommandoen i handleren, men gjøre selve funksjonen betinget — da vil fengselsbygget ikke ha den definert. Alternativt, bruk en cfg-blokk rundt hele invoke_handler.

Den sikreste tilnærmingen (funker med Tauri 2 sin generate_handler! makro): legg til en tom no-op stub:

```rust
// Legg til ETTER den eksisterende #[cfg(feature = "about")]-blokken:
#[cfg(not(feature = "about"))]
#[tauri::command]
fn about_info() -> Option<()> { None }
```

Og legg `about_info` til i `generate_handler![]`-listen som finnes i `run()`. Fengselsbygg returnerer da `null`, hjemmebygg returnerer objektet.

- [ ] **Step 4: Verifiser kompilering (fengselsbygg)**

```powershell
cd kokebok-app && cargo build --manifest-path src-tauri/Cargo.toml
```

Forventet: bygget OK uten `--features about`. Ingen personinfo i binæren.

- [ ] **Step 5: Verifiser kompilering (hjemmebygg)**

```powershell
cargo build --manifest-path kokebok-app/src-tauri/Cargo.toml --features about
```

Forventet: bygget OK med about-info inkludert.

- [ ] **Step 6: Commit**

```bash
git add kokebok-app/src-tauri/Cargo.toml kokebok-app/src-tauri/src/lib.rs
git commit -m "feat(about): Rust-kommando bak cfg(feature = about)"
```

---

## Task 3: Profilvelger i sidebar + Helseprofil-fane i Innstillinger

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `profilLast`, `profilSettAktiv`, `profilOpprett`, `profilOppdater`, `profilSlett`, `tdee`, `Brukerprofil`, `ProfilStore` fra `$lib/helse`
- Consumes: `invoke` fra `@tauri-apps/api/core` (allerede importert)
- Produces: `profilStore` state, `aktivProfil` derived, `aboutInfo` state

- [ ] **Step 1: Legg til imports og state øverst i `<script>`**

Legg til i import-blokken øverst (etter de eksisterende lib-importene):

```typescript
import { profilLast, profilSettAktiv, profilOpprett, profilOppdater, profilSlett, tdee, dagsbehov, dekningsProsent, type Brukerprofil, type ProfilStore } from "$lib/helse";
```

Legg til state-variabler etter `let planLaster = $state(false);`:

```typescript
let profilStore = $state<ProfilStore>({ profiler: [], aktivId: null });
let profilDropdownÅpen = $state(false);
let profilSkjemaÅpent = $state(false);
let profilRedigerer = $state<Brukerprofil | null>(null);
let profilFelt = $state({ navn: "", kjønn: "mann" as "mann"|"kvinne", alder: 30, høyde: 175, vekt: 75, aktivitet: "moderat" as Brukerprofil["aktivitet"], mål: "vedlikehold" as Brukerprofil["mål"] });
let aboutInfo = $state<{ navn: string; epost: string; versjon: string; beskrivelse: string } | null>(null);
```

Legg til derived:

```typescript
let aktivProfil = $derived(
  profilStore.profiler.find((p) => p.id === profilStore.aktivId) ?? null
);
```

- [ ] **Step 2: Last profiler og about-info i `onMount`**

Finn `onMount(async () => {`-blokken. Legg til på slutten av den (før den avsluttende `}`):

```typescript
  profilStore = await profilLast();
  try {
    aboutInfo = await invoke("about_info");
  } catch {
    // fengselsbygg — about ikke tilgjengelig
    aboutInfo = null;
  }
```

- [ ] **Step 3: Legg til hjelpefunksjoner for profil**

Legg til etter `velgMatplan`-funksjonen:

```typescript
  async function velgProfilAktiv(id: string) {
    profilStore = await profilSettAktiv(id);
    profilDropdownÅpen = false;
    if (aktivProfil) planDagsmaal = tdee(aktivProfil);
  }

  function startNyProfil() {
    profilRedigerer = null;
    profilFelt = { navn: "", kjønn: "mann", alder: 30, høyde: 175, vekt: 75, aktivitet: "moderat", mål: "vedlikehold" };
    profilSkjemaÅpent = true;
  }

  function startRedigerProfil(p: Brukerprofil) {
    profilRedigerer = p;
    profilFelt = { navn: p.navn, kjønn: p.kjønn, alder: p.alder, høyde: p.høyde, vekt: p.vekt, aktivitet: p.aktivitet, mål: p.mål };
    profilSkjemaÅpent = true;
  }

  async function lagreProfil() {
    if (!profilFelt.navn.trim()) return;
    if (profilRedigerer) {
      profilStore = await profilOppdater({ ...profilRedigerer, ...profilFelt });
    } else {
      profilStore = await profilOpprett(profilFelt);
    }
    profilSkjemaÅpent = false;
    if (aktivProfil) planDagsmaal = tdee(aktivProfil);
  }

  async function slettProfil(id: string) {
    if (!confirm("Slett denne profilen?")) return;
    profilStore = await profilSlett(id);
    if (aktivProfil) planDagsmaal = tdee(aktivProfil);
  }
```

- [ ] **Step 4: Legg til profilvelger i sidebar**

Finn `<div class="sidebar-logo">` i HTML-delen. Legg til rett ETTER den avsluttende `</div>` for `.sidebar-logo` (og FØR `{#if currentKategori !== ...}`-blokken):

```svelte
  <div class="profil-velger">
    <button
      class="profil-velger-knapp"
      onclick={() => (profilDropdownÅpen = !profilDropdownÅpen)}
    >
      <span class="profil-initialer">
        {aktivProfil ? aktivProfil.navn.slice(0, 2).toUpperCase() : "?"}
      </span>
      <span class="profil-navn-tekst">
        {aktivProfil ? aktivProfil.navn : "Velg profil"}
      </span>
      <span class="profil-chevron">{profilDropdownÅpen ? "▲" : "▼"}</span>
    </button>
    {#if profilDropdownÅpen}
      <div class="profil-dropdown">
        {#each profilStore.profiler as p (p.id)}
          <button
            class="profil-dd-rad"
            class:aktiv={p.id === profilStore.aktivId}
            onclick={() => velgProfilAktiv(p.id)}
          >
            {p.navn} {p.id === profilStore.aktivId ? "✓" : ""}
          </button>
        {/each}
        {#if profilStore.profiler.length === 0}
          <span class="profil-dd-tom">Ingen profiler</span>
        {/if}
        <button class="profil-dd-admin" onclick={() => { profilDropdownÅpen = false; velgInnstillinger(); }}>
          Administrer profiler →
        </button>
      </div>
    {/if}
  </div>
```

- [ ] **Step 5: Legg til Helseprofil-fane i Innstillinger**

Finn `{#if currentKategori === "__innst__"}` i HTML. Det finnes allerede innhold der (temaer, kostholdsfiltre). Legg til en fanevelger øverst i Innstillinger-blokken.

Finn toppen av Innstillinger-innholdet. Den ser slik ut (ca. linje 1020-1030 i filen):
```svelte
{#if currentKategori === "__innst__"}
  <div id="innst-wrap">
```

Legg til fanevelger og ny fane. Finn `let innstFane`-liknende state — det finnes ikke fra før, legg til i script-blokken:

```typescript
let innstFane = $state<"tema" | "diett" | "profil">("tema");
```

Deretter, i HTML, wrap eksisterende innst-innhold med fanevelger. Finn `<div id="innst-wrap">` og legg til etter den:

```svelte
    <div class="innst-faner">
      <button class:aktiv-fane={innstFane === "tema"} onclick={() => (innstFane = "tema")}>🎨 Temaer</button>
      <button class:aktiv-fane={innstFane === "diett"} onclick={() => (innstFane = "diett")}>🍽️ Kosthold</button>
      <button class:aktiv-fane={innstFane === "profil"} onclick={() => (innstFane = "profil")}>👤 Helseprofil</button>
    </div>
```

Wrap eksisterende tema-innhold med `{#if innstFane === "tema"}...{/if}` og eksisterende diett-innhold med `{#if innstFane === "diett"}...{/if}`.

Legg til ny profil-fane:

```svelte
    {#if innstFane === "profil"}
      <div class="profil-liste">
        <h2>Helseprofiler</h2>
        {#each profilStore.profiler as p (p.id)}
          <div class="profil-kort" class:aktiv-profil={p.id === profilStore.aktivId}>
            <div class="profil-kort-info">
              <strong>{p.navn}</strong>
              <span>{tdee(p)} kcal/dag</span>
              {#if p.id === profilStore.aktivId}<span class="aktiv-merke">● Aktiv</span>{/if}
            </div>
            <div class="profil-kort-knapper">
              {#if p.id !== profilStore.aktivId}
                <button onclick={() => velgProfilAktiv(p.id)}>Velg</button>
              {/if}
              <button onclick={() => startRedigerProfil(p)}>Rediger</button>
              <button onclick={() => slettProfil(p.id)}>Slett</button>
            </div>
          </div>
        {/each}
        {#if profilStore.profiler.length === 0}
          <p class="lager-tom">Ingen profiler opprettet ennå.</p>
        {/if}
        {#if !profilSkjemaÅpent}
          <button class="profil-ny-knapp" onclick={startNyProfil}>+ Ny profil</button>
        {:else}
          <div class="profil-skjema">
            <h3>{profilRedigerer ? "Rediger profil" : "Ny profil"}</h3>
            <label>Navn <input type="text" bind:value={profilFelt.navn} /></label>
            <label>Kjønn
              <select bind:value={profilFelt.kjønn}>
                <option value="mann">Mann</option>
                <option value="kvinne">Kvinne</option>
              </select>
            </label>
            <label>Alder (år) <input type="number" min="10" max="120" bind:value={profilFelt.alder} /></label>
            <label>Høyde (cm) <input type="number" min="100" max="250" bind:value={profilFelt.høyde} /></label>
            <label>Vekt (kg) <input type="number" min="30" max="300" step="0.5" bind:value={profilFelt.vekt} /></label>
            <label>Aktivitetsnivå
              <select bind:value={profilFelt.aktivitet}>
                <option value="stillesittende">Stillesittende (lite/ingen trening)</option>
                <option value="lett">Lett aktiv (1–3 dager/uke)</option>
                <option value="moderat">Moderat aktiv (3–5 dager/uke)</option>
                <option value="aktiv">Aktiv (6–7 dager/uke)</option>
                <option value="veldig_aktiv">Veldig aktiv (hard trening + fysisk jobb)</option>
              </select>
            </label>
            <label>Mål
              <select bind:value={profilFelt.mål}>
                <option value="nedgang">Vektnedgang (−500 kcal)</option>
                <option value="vedlikehold">Vedlikehold</option>
                <option value="oppgang">Vektøkning (+500 kcal)</option>
              </select>
            </label>
            <div class="profil-skjema-knapper">
              <button onclick={lagreProfil}>Lagre</button>
              <button onclick={() => (profilSkjemaÅpent = false)}>Avbryt</button>
            </div>
          </div>
        {/if}
      </div>

      {#if aboutInfo}
        <div class="about-seksjon">
          <hr />
          <div class="about-tittel">Om appen · v{aboutInfo.versjon}</div>
          <p class="about-tekst">{aboutInfo.beskrivelse}</p>
          <div class="about-kontakt">{aboutInfo.navn} · {aboutInfo.epost}</div>
        </div>
      {/if}
    {/if}
```

- [ ] **Step 6: Prepopuler matplan-dagsmål fra aktiv profil**

Finn `let planDagsmaal = $state(2000);` i script-blokken. Erstatt med:

```typescript
let planDagsmaal = $state(2000);
```

(uendret — verdien settes dynamisk fra `onMount` og `velgProfilAktiv`). Verifiser at `onMount` allerede setter `planDagsmaal = tdee(aktivProfil)` etter at `profilStore` er lastet. Legg til denne linjen etter `profilStore = await profilLast();` i onMount:

```typescript
  if (profilStore.aktivId) {
    const ap = profilStore.profiler.find(p => p.id === profilStore.aktivId);
    if (ap) planDagsmaal = tdee(ap);
  }
```

- [ ] **Step 7: Legg til CSS for nye elementer**

Legg til i `<style>`-blokken på slutten (før den avsluttende `</style>`):

```css
  /* ── Profilvelger ─────────────────────────────────────────── */
  .profil-velger {
    position: relative;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }
  .profil-velger-knapp {
    display: flex; align-items: center; gap: 8px;
    width: 100%; background: none; border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 10px; cursor: pointer;
    color: var(--text); font-size: 0.85rem;
  }
  .profil-velger-knapp:hover { background: var(--hover-bg); }
  .profil-initialer {
    width: 24px; height: 24px; border-radius: 50%;
    background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; font-weight: 700; flex-shrink: 0;
  }
  .profil-navn-tekst { flex: 1; text-align: left; }
  .profil-chevron { font-size: 0.65rem; color: var(--text-muted); }
  .profil-dropdown {
    position: absolute; top: 100%; left: 12px; right: 12px;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.15);
    z-index: 100; display: flex; flex-direction: column;
  }
  .profil-dd-rad {
    padding: 8px 12px; text-align: left; background: none;
    border: none; cursor: pointer; color: var(--text); font-size: 0.85rem;
  }
  .profil-dd-rad:hover, .profil-dd-rad.aktiv { background: var(--hover-bg); }
  .profil-dd-tom { padding: 8px 12px; color: var(--text-muted); font-size: 0.8rem; }
  .profil-dd-admin {
    padding: 8px 12px; text-align: left; background: none;
    border-top: 1px solid var(--border); border-left: none;
    border-right: none; border-bottom: none;
    cursor: pointer; color: var(--accent); font-size: 0.8rem;
  }
  .profil-dd-admin:hover { text-decoration: underline; }

  /* ── Innstillinger-faner ──────────────────────────────────── */
  .innst-faner {
    display: flex; gap: 4px; margin-bottom: 20px;
    border-bottom: 1px solid var(--border); padding-bottom: 8px;
  }
  .innst-faner button {
    padding: 6px 14px; border: 1px solid var(--border);
    border-radius: 6px 6px 0 0; background: none;
    cursor: pointer; color: var(--text); font-size: 0.85rem;
  }
  .innst-faner button.aktiv-fane {
    background: var(--accent); color: #fff; border-color: var(--accent);
  }

  /* ── Helseprofil-liste og skjema ─────────────────────────── */
  .profil-liste { display: flex; flex-direction: column; gap: 12px; }
  .profil-kort {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 16px; border: 1px solid var(--border);
    border-radius: 8px; background: var(--card-bg);
  }
  .profil-kort.aktiv-profil { border-color: var(--accent); }
  .profil-kort-info { display: flex; flex-direction: column; gap: 2px; font-size: 0.9rem; }
  .aktiv-merke { color: var(--accent); font-size: 0.75rem; }
  .profil-kort-knapper { display: flex; gap: 6px; }
  .profil-kort-knapper button {
    padding: 4px 10px; border: 1px solid var(--border);
    border-radius: 4px; background: none; cursor: pointer;
    color: var(--text); font-size: 0.8rem;
  }
  .profil-kort-knapper button:hover { background: var(--hover-bg); }
  .profil-ny-knapp {
    align-self: flex-start; padding: 8px 16px;
    background: var(--accent); color: #fff; border: none;
    border-radius: 6px; cursor: pointer; font-size: 0.9rem;
  }
  .profil-skjema {
    display: flex; flex-direction: column; gap: 10px;
    padding: 16px; border: 1px solid var(--border); border-radius: 8px;
  }
  .profil-skjema label {
    display: flex; flex-direction: column; gap: 4px; font-size: 0.85rem;
  }
  .profil-skjema input, .profil-skjema select {
    padding: 6px 10px; border: 1px solid var(--border);
    border-radius: 4px; background: var(--bg); color: var(--text);
    font-size: 0.9rem;
  }
  .profil-skjema-knapper { display: flex; gap: 8px; margin-top: 4px; }
  .profil-skjema-knapper button {
    padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
  }
  .profil-skjema-knapper button:first-child {
    background: var(--accent); color: #fff; border: none;
  }
  .profil-skjema-knapper button:last-child {
    background: none; border: 1px solid var(--border); color: var(--text);
  }

  /* ── About-seksjon ───────────────────────────────────────── */
  .about-seksjon {
    margin-top: 24px; padding-top: 16px;
    border-top: 1px solid var(--border); color: var(--text-muted);
  }
  .about-tittel { font-weight: 600; margin-bottom: 8px; color: var(--text); }
  .about-tekst { font-size: 0.85rem; line-height: 1.5; margin-bottom: 8px; }
  .about-kontakt { font-size: 0.8rem; }

  /* ── Dagsbehov-kort ─────────────────────────────────────── */
  .dagsbehov-wrap { margin-top: 16px; }
  .dagsbehov-title {
    font-size: 0.85rem; font-weight: 600; color: var(--text-muted);
    margin-bottom: 8px;
  }
  .dagsbehov-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
  }
  .dagsbehov-kort {
    display: flex; flex-direction: column; align-items: center;
    padding: 10px 6px; border: 1px solid var(--border);
    border-radius: 8px; background: var(--card-bg);
  }
  .dagsbehov-pst { font-size: 1.1rem; font-weight: 700; color: var(--accent); }
  .dagsbehov-lbl { font-size: 0.7rem; color: var(--text-muted); text-align: center; }
  .dagsbehov-profil {
    margin-top: 6px; font-size: 0.75rem; color: var(--text-muted); text-align: center;
  }
```

- [ ] **Step 8: Bygg og test manuelt**

```powershell
cd kokebok-app && npm run dev
```

Sjekk:
1. Profilvelger vises under logoen i sidefeltet
2. Klikk åpner dropdown — viser "Ingen profiler" og "Administrer profiler →"
3. Klikk "Administrer profiler →" åpner Innstillinger med Helseprofil-fane valgt
4. Opprett en profil — den vises i lista med TDEE
5. Velg profil — aktiv-merke vises, matplan-dagsmål oppdateres

- [ ] **Step 9: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(helse): profilvelger i sidebar + Helseprofil-fane i Innstillinger"
```

---

## Task 4: Dagsbehov-prosenter i oppskriftsdetaljvisningen

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `aktivProfil` (derived fra Task 3), `dagsbehov`, `dekningsProsent` fra `$lib/helse`
- Consumes: `naeringPerPorsjon` (eksisterende derived, per 1 porsjon basert på `origP`)

- [ ] **Step 1: Legg til dagsbehov-derived**

Finn de eksisterende `$derived`-uttrykkene i script-blokken (rundt `naeringPerPorsjon`). Legg til rett etter:

```typescript
  let aktivtDagsbehov = $derived(aktivProfil ? dagsbehov(aktivProfil) : null);
```

- [ ] **Step 2: Legg til dagsbehov-blokk i HTML**

Finn `</div>` som avslutter `.naering-wrap`-blokken (etter `naering-disclaimer` og `naering-unavailable`). Den ser slik ut:

```svelte
          {/if}
        </div>
```

(Det er slutten på `.naering-wrap`-div-en, rett FØR `{#if prisVist}`)

Legg til dagsbehov-blokken ETTER `.naering-wrap` og FØR `{#if prisVist}`:

```svelte
        {#if naeringPerPorsjon && aktivtDagsbehov}
          {@const n = naeringPerPorsjon}
          {@const db = aktivtDagsbehov}
          <div class="dagsbehov-wrap">
            <div class="dagsbehov-title">📈 Andel av dagsbehov – per porsjon</div>
            <div class="dagsbehov-grid">
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.e, db.kcal)}%</span>
                <span class="dagsbehov-lbl">🔥 Energi</span>
              </div>
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.p, db.protein)}%</span>
                <span class="dagsbehov-lbl">🥩 Protein</span>
              </div>
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.f, db.fett)}%</span>
                <span class="dagsbehov-lbl">🫙 Fett</span>
              </div>
              <div class="dagsbehov-kort">
                <span class="dagsbehov-pst">{dekningsProsent(n.k, db.karbo)}%</span>
                <span class="dagsbehov-lbl">🌾 Karbo</span>
              </div>
            </div>
            <div class="dagsbehov-profil">
              Basert på profil: {aktivProfil!.navn} · {db.kcal} kcal/dag
            </div>
          </div>
        {/if}
```

- [ ] **Step 3: Test manuelt**

```powershell
cd kokebok-app && npm run dev
```

Sjekk:
1. Opprett en profil (f.eks. Mann, 35 år, 180 cm, 80 kg, moderat, vedlikehold → ca. 2734 kcal/dag)
2. Åpne en oppskrift med næringsdata
3. Dagsbehov-blokken vises under næringskortene med fire prosent-tall
4. Åpne en oppskrift uten næringsdata — dagsbehov-blokken vises ikke
5. Med ingen aktiv profil — dagsbehov-blokken vises ikke

- [ ] **Step 4: Commit**

```bash
git add kokebok-app/src/routes/+page.svelte
git commit -m "feat(helse): dagsbehov-prosenter i oppskriftsdetaljvisning"
```

---

## Spec-dekningssjekk (self-review)

- [x] `helse.ts` — TDEE, dagsbehov, dekningsProsent, Tauri Store CRUD → Task 1
- [x] About-kommando Rust + Cargo feature → Task 2
- [x] Profilvelger i sidebar → Task 3
- [x] Helseprofil-fane i Innstillinger (liste, skjema, rediger, slett, aktiv) → Task 3
- [x] About-seksjon i Innstillinger (kun hjemmebygg) → Task 3
- [x] Matplan prepopuleres med TDEE → Task 3 (Step 6)
- [x] Dagsbehov-prosenter i detalj (energi, protein, fett, karbo) → Task 4
- [x] Alltid per 1 porsjon → Task 4 bruker `naeringPerPorsjon` som allerede er per origP-porsjon
- [x] Vises kun når profil finnes OG oppskrift har næringsdata → Task 4 Step 2 (`{#if naeringPerPorsjon && aktivtDagsbehov}`)
