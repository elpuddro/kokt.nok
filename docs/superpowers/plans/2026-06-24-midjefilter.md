# Midjefilter — Implementeringsplan (#22)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brukere kan registrere midjemål (cm) i helseprofilen og aktivere et filter som skjevstiller matplanleggeren mot sunnere oppskrifter (lavere kcal/porsjon og lavere fettprosent).

**Architecture:** Tre lag endres i rekkefølge: (1) `helse.ts` — ny `midje?`/`midjeFilter`-felt i `Brukerprofil` + `midjeOverGrenje(p)`, (2) `lib.rs` — `generer_matplan` får `sunn_plan: bool`, scoring-straf for høy-kcal og høy-fett kandidater; `Kandidat`-struct utvides med `fett: Option<f64>` hentet i eksisterende bulk-query, (3) `+page.svelte` — nye skjemafelt, derived `aktivtMidjeFilter`, `sunnPlan`-arg til `invoke`.

**Tech Stack:** Tauri 2 (Rust, rusqlite, serde), Svelte 5 runes (`$state`, `$derived`), TypeScript, `@tauri-apps/plugin-store`, `invoke` fra `@tauri-apps/api/core`.

## Global Constraints

- Svelte 5 runes kun — ingen `$:`, ingen `writable()`
- `invoke` fra `@tauri-apps/api/core` — ikke `@tauri-apps/api`
- Tauri Store: `load("profiler.json")`, `store.get/set/save()`
- Rust: `#[tauri::command]` + registrering i `tauri::generate_handler![]`
- Ingen nye npm-pakker, ingen DB-endringer, ingen migrasjonskode
- CSS: bruk `--card`, `--card-hover`, `--text-muted`, `--border` (ikke --card-bg, --hover-bg)
- Commit-meldinger uten "Co-Authored-By"-trailer
- Fengselsbygg: `cargo build --manifest-path kokebok-app/src-tauri/Cargo.toml` (uten --features about)
- WHO-grenser: mann >94 cm, kvinne >80 cm
- Kombinert scoring-straf for både høy kcal OG høy fett: `score *= 0.5 * 0.7 = 0.35`
- Oppskrifter uten næringsdata (`kcal = None`) straffes ikke

---

## Filstruktur

| Fil | Endring |
|-----|---------|
| `kokebok-app/src/lib/helse.ts` | `midje?` og `midjeFilter` i `Brukerprofil`; ny export `midjeOverGrenje(p)` |
| `kokebok-app/src-tauri/src/lib.rs` | `Kandidat` får `fett: Option<f64>`; bulk-query henter fett; `generer_matplan` får `sunn_plan: bool`; scoring-multiplikatorer |
| `kokebok-app/src/routes/+page.svelte` | `profilFelt` + `startNyProfil`/`startRedigerProfil` oppdatert; `midjeOverGrenjeFelt` derived; `aktivtMidjeFilter` derived; `genererPlan` sender `sunnPlan`; nye skjemafelt + 🎯-indikator |

---

## Task 1: `helse.ts` — Brukerprofil-utvidelse og `midjeOverGrenje`

**Files:**
- Modify: `kokebok-app/src/lib/helse.ts`

**Interfaces:**
- Produces: `Brukerprofil` med `midje?: number` og `midjeFilter: boolean`
- Produces: `export function midjeOverGrenje(p: Brukerprofil): boolean`
- Konsumeres av Task 3 (`+page.svelte`)

- [ ] **Step 1: Les `helse.ts`**

  Åpne `kokebok-app/src/lib/helse.ts`. Finn:
  - `interface Brukerprofil` (linje 6–15) — der du legger til de to nye feltene
  - Eksisterende eksporter (`tdee`, `dagsbehov`, `dekningsProsent`) — som mønster for ny export

- [ ] **Step 2: Legg til `midje?` og `midjeFilter` i `Brukerprofil`**

  Finn blokken:
  ```typescript
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
  ```

  Erstatt med:
  ```typescript
  export interface Brukerprofil {
    id: string;
    navn: string;
    kjønn: "mann" | "kvinne";
    alder: number;
    høyde: number;
    vekt: number;
    aktivitet: Aktivitetsnivå;
    mål: Mål;
    midje?: number;
    midjeFilter: boolean;
  }
  ```

  Bakoverkompatibilitet: eksisterende lagrede profiler mangler `midjeFilter`. Ved lasting gir TypeScript `undefined`; i Step 4 i Task 3 brukes `?? false` i all ny kode.

- [ ] **Step 3: Legg til `midjeOverGrenje`-funksjonen**

  Finn linjen rett etter `export function dekningsProsent(...)` (ca. linje 62–65). Legg til ny export-funksjon rett etter:

  ```typescript
  export function midjeOverGrenje(p: Brukerprofil): boolean {
    if (!p.midjeFilter || p.midje == null) return false;
    return p.kjønn === "mann" ? p.midje > 94 : p.midje > 80;
  }
  ```

- [ ] **Step 4: Verifiser TypeScript**

  Kjør fra `C:\Users\elpud\CODE\kokt.nok\.claude\worktrees\feat+matplanlegger`:
  ```powershell
  cd kokebok-app && npx tsc --noEmit
  ```
  Forventet: 0 nye feil (ett pre-eksisterende feil i `vite.config.js` er OK). Gå tilbake til worktree-root etter verifisering.

- [ ] **Step 5: Commit**

  ```bash
  git add kokebok-app/src/lib/helse.ts
  git commit -m "feat(midjefilter): midje + midjeFilter i Brukerprofil, midjeOverGrenje"
  ```

---

## Task 2: `lib.rs` — fett i Kandidat og `sunn_plan`-scoring

**Files:**
- Modify: `kokebok-app/src-tauri/src/lib.rs`

**Interfaces:**
- `Kandidat`-struct (ca. linje 813) utvides: `fett: Option<f64>` legges til
- Bulk-query for kcal (ca. linje 879) utvides til å hente fett per porsjon
- `generer_matplan`-signatur (ca. linje 980) får nytt param `#[allow(non_snake_case)] sunnPlan: bool`
- `score()`-funksjon kalles uendret; scoring-justeringen skjer i `velg`-closuren etter `score()` er beregnet

**Interfaces (produces):**
- `generer_matplan(..., sunnPlan: bool) -> Result<UkeSvar, String>` — registrert i `generate_handler![]`

- [ ] **Step 1: Les relevant kode i `lib.rs`**

  Les disse seksjonene:
  - `struct Kandidat` (ca. linje 813–819): ser nåværende felter
  - `kandidater_for_slot` / bulk-kcal-query (ca. linje 879–916): forstå SQL-struktur
  - `fn score(...)` (ca. linje 943–961): eksisterende scoring-formel
  - `fn generer_matplan(...)` (ca. linje 979–1055): signatur og `velg`-closure

- [ ] **Step 2: Legg til `fett: Option<f64>` i `Kandidat`**

  Finn:
  ```rust
  struct Kandidat {
      id: i64,
      navn: String,
      type_: String,
      kcal: Option<f64>,
      ingredienser: Vec<String>,
  }
  ```
  Erstatt med:
  ```rust
  struct Kandidat {
      id: i64,
      navn: String,
      type_: String,
      kcal: Option<f64>,
      fett: Option<f64>,
      ingredienser: Vec<String>,
  }
  ```

- [ ] **Step 3: Utvid bulk-kcal-query til å hente fett per porsjon**

  Bulk-fett-queryen er en separat `HashMap`-bygging etter `kcal_map`. Finn linjen `// Bulk-hent ingrediensnavn for alle kandidater` (ca. linje 918) og legg inn fett-bulk-henting MELLOM `kcal_map`-blokken og ingrediens-blokken:

  ```rust
  // Bulk-hent fett per porsjon for alle kandidater.
  let fett_sql = format!(
      "SELECT i.oppskrift_id,
         ROUND(SUM(CASE i.enhet
           WHEN 'g'  THEN i.mengde        * COALESCE(n.fett_g,0)/100
           WHEN 'kg' THEN i.mengde*1000   * COALESCE(n.fett_g,0)/100
           WHEN 'dl' THEN i.mengde*100    * COALESCE(n.fett_g,0)/100
           WHEN 'l'  THEN i.mengde*1000   * COALESCE(n.fett_g,0)/100
           WHEN 'ml' THEN i.mengde        * COALESCE(n.fett_g,0)/100
           WHEN 'ss' THEN i.mengde*15     * COALESCE(n.fett_g,0)/100
           WHEN 'ts' THEN i.mengde*5      * COALESCE(n.fett_g,0)/100
           ELSE 0 END), 1) AS fett_total,
         COUNT(n.ingredient_navn) AS treff,
         o.porsjoner
       FROM ingredienser i
       LEFT JOIN naering n ON LOWER(TRIM(i.navn)) = LOWER(TRIM(n.ingredient_navn))
       JOIN oppskrifter o ON o.id = i.oppskrift_id
       WHERE i.oppskrift_id IN ({id_ph})
       GROUP BY i.oppskrift_id"
  );
  let mut fett_map: std::collections::HashMap<i64, Option<f64>> = std::collections::HashMap::new();
  if let Ok(mut stmt) = conn.prepare(&fett_sql) {
      if let Ok(rows) = stmt.query_map(id_refs.as_slice(), |r| {
          Ok((r.get::<_, i64>(0)?, r.get::<_, Option<f64>>(1)?, r.get::<_, i64>(2)?, r.get::<_, Option<f64>>(3)?))
      }) {
          for row in rows.filter_map(|r| r.ok()) {
              let (opp_id, fett_total, treff, porsjoner) = row;
              let fett = if treff > 0 {
                  fett_total.filter(|&f| f > 0.0).map(|f| {
                      let p = porsjoner.filter(|&p| p > 0.0).unwrap_or(4.0);
                      (f / p * 10.0).round() / 10.0
                  })
              } else {
                  None
              };
              fett_map.insert(opp_id, fett);
          }
      }
  }
  ```

  Merk: `id_ph` og `id_refs` er allerede deklarert i scope fra kcal-bulk-blokken.

- [ ] **Step 4: Legg `fett` i `Kandidat`-konstruktøren**

  Finn (ca. linje 935–939):
  ```rust
  basis.into_iter().map(|(id, navn, type_)| {
      let kcal = kcal_map.get(&id).copied().flatten();
      let ingredienser = ing_map.remove(&id).unwrap_or_default();
      Kandidat { id, navn, type_, kcal, ingredienser }
  ```
  Erstatt med:
  ```rust
  basis.into_iter().map(|(id, navn, type_)| {
      let kcal = kcal_map.get(&id).copied().flatten();
      let fett = fett_map.get(&id).copied().flatten();
      let ingredienser = ing_map.remove(&id).unwrap_or_default();
      Kandidat { id, navn, type_, kcal, fett, ingredienser }
  ```

- [ ] **Step 5: Legg til `sunnPlan: bool` i `generer_matplan`-signaturen**

  Finn:
  ```rust
  fn generer_matplan(
      app: AppHandle,
      dagsmaal: i64,
      personer: i64,
      dietter: Option<Vec<String>>,
      laaste: Vec<LaastSlot>,
  ) -> Result<UkeSvar, String> {
  ```
  Erstatt med:
  ```rust
  fn generer_matplan(
      app: AppHandle,
      dagsmaal: i64,
      personer: i64,
      dietter: Option<Vec<String>>,
      laaste: Vec<LaastSlot>,
      #[allow(non_snake_case)] sunnPlan: bool,
  ) -> Result<UkeSvar, String> {
  ```

- [ ] **Step 6: Legg til scoring-justert `velg`-wrapper**

  Finn `velg`-closurens `let mut best_s = f64::NEG_INFINITY;`-linjen (ca. linje 1038). Score-beregningen skjer i `let s = score(k, m, bt, bi, jitter);`. Legg til sunn-plan-multiplikator ETTER `score()` og FØR `if s > best_s`:

  Finn:
  ```rust
          let jitter = ((i as f64 * 0.137 + k.id as f64 * 2.399_963 + teller) % 1.0) * 10.0;
              let s = score(k, m, bt, bi, jitter);
              if s > best_s { best_s = s; best = Some(k); }
  ```
  Erstatt med:
  ```rust
          let jitter = ((i as f64 * 0.137 + k.id as f64 * 2.399_963 + teller) % 1.0) * 10.0;
              let mut s = score(k, m, bt, bi, jitter);
              if sunnPlan {
                  if k.kcal.map_or(false, |kc| kc > 600.0) {
                      s *= 0.5;
                  }
                  if let (Some(kc), Some(ft)) = (k.kcal, k.fett) {
                      if kc > 0.0 && (ft * 9.0 / kc) > 0.35 {
                          s *= 0.7;
                      }
                  }
              }
              if s > best_s { best_s = s; best = Some(k); }
  ```

- [ ] **Step 7: Verifiser kompilering**

  ```powershell
  cargo build --manifest-path kokebok-app/src-tauri/Cargo.toml
  ```
  Forventet: kompilerer uten feil.

- [ ] **Step 8: Commit**

  ```bash
  git add kokebok-app/src-tauri/src/lib.rs
  git commit -m "feat(midjefilter): fett i Kandidat + sunn_plan-scoring i generer_matplan"
  ```

---

## Task 3: `+page.svelte` — UI og invoke-kall

**Files:**
- Modify: `kokebok-app/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `midjeOverGrenje` fra Task 1 — importer fra `$lib/helse`
- Consumes: `generer_matplan(..., sunnPlan: bool)` fra Task 2
- `profilFelt` (ca. linje 65): legg til `midje: undefined as number | undefined` og `midjeFilter: false`
- `aktivtMidjeFilter`: `$derived` fra `aktivProfil` via `midjeOverGrenje`

- [ ] **Step 1: Les relevante seksjoner i `+page.svelte`**

  Finn og noter linjenummer for:
  1. Import-linjen for `$lib/helse` (ca. linje 16) — der du legger til `midjeOverGrenje`
  2. `profilFelt`-deklarasjonen (ca. linje 65)
  3. `aktivProfil`-derived (ca. linje 90–92) — der du legger til `aktivtMidjeFilter`
  4. `startNyProfil`-funksjonen og `startRedigerProfil`-funksjonen
  5. `genererPlan`-funksjonen (ca. linje 308–323) — der du legger til `sunnPlan`
  6. Helseprofil-skjemaet i settings-HTML (søk etter `vekt`-input-feltet og label "Vekt (kg)")
  7. Profilliste-HTML (søk etter `tdee(p)` der du legger til 🎯)

- [ ] **Step 2: Legg til `midjeOverGrenje` i import**

  Finn (ca. linje 16):
  ```typescript
  import { profilLast, profilSettAktiv, profilOpprett, profilOppdater, profilSlett, tdee, dagsbehov, dekningsProsent, type Brukerprofil, type ProfilStore } from "$lib/helse";
  ```
  Erstatt med:
  ```typescript
  import { profilLast, profilSettAktiv, profilOpprett, profilOppdater, profilSlett, tdee, dagsbehov, dekningsProsent, midjeOverGrenje, type Brukerprofil, type ProfilStore } from "$lib/helse";
  ```

- [ ] **Step 3: Utvid `profilFelt`**

  Finn (ca. linje 65):
  ```typescript
  let profilFelt = $state({ navn: "", kjønn: "mann" as "mann"|"kvinne", alder: 30, høyde: 175, vekt: 75, aktivitet: "moderat" as Brukerprofil["aktivitet"], mål: "vedlikehold" as Brukerprofil["mål"] });
  ```
  Erstatt med:
  ```typescript
  let profilFelt = $state({ navn: "", kjønn: "mann" as "mann"|"kvinne", alder: 30, høyde: 175, vekt: 75, aktivitet: "moderat" as Brukerprofil["aktivitet"], mål: "vedlikehold" as Brukerprofil["mål"], midje: undefined as number | undefined, midjeFilter: false });
  ```

- [ ] **Step 4: Legg til `aktivtMidjeFilter` og `midjeOverGrenjeFelt` derived**

  Finn `aktivProfil`-derived (ca. linje 90–92):
  ```typescript
  let aktivProfil = $derived(
    profilStore.profiler.find((p) => p.id === profilStore.aktivId) ?? null
  );
  ```
  Legg til disse to derived rett ETTER `aktivProfil`:
  ```typescript
  let aktivtMidjeFilter = $derived(aktivProfil ? midjeOverGrenje(aktivProfil) : false);
  let midjeOverGrenjeFelt = $derived(
    profilFelt.midje != null &&
    (profilFelt.kjønn === "mann" ? profilFelt.midje > 94 : profilFelt.midje > 80)
  );
  ```

- [ ] **Step 5: Oppdater `startNyProfil` og `startRedigerProfil`**

  Finn `startNyProfil`-funksjonen. Den tilbakestiller `profilFelt`. Finn linjen der `profilFelt = { ... }` settes og legg til `midje: undefined, midjeFilter: false` i objektet.

  Eksempel (finn den eksakte formen i koden):
  ```typescript
  profilFelt = { navn: "", kjønn: "mann", alder: 30, høyde: 175, vekt: 75, aktivitet: "moderat", mål: "vedlikehold", midje: undefined, midjeFilter: false };
  ```

  Finn `startRedigerProfil`-funksjonen. Den kopierer verdier fra en eksisterende profil inn i `profilFelt`. Legg til:
  ```typescript
  profilFelt = {
    navn: p.navn,
    kjønn: p.kjønn,
    alder: p.alder,
    høyde: p.høyde,
    vekt: p.vekt,
    aktivitet: p.aktivitet,
    mål: p.mål,
    midje: p.midje,
    midjeFilter: p.midjeFilter ?? false,
  };
  ```

- [ ] **Step 6: Legg til `sunnPlan` i `genererPlan`**

  Finn (ca. linje 311–316):
  ```typescript
      const uke = await invoke<Uke>("generer_matplan", {
        dagsmaal: planDagsmaal,
        personer: planPersoner,
        dietter: aktiveDietter,
        laaste: samleLaaste(),
      });
  ```
  Erstatt med:
  ```typescript
      const uke = await invoke<Uke>("generer_matplan", {
        dagsmaal: planDagsmaal,
        personer: planPersoner,
        dietter: aktiveDietter,
        laaste: samleLaaste(),
        sunnPlan: aktivtMidjeFilter,
      });
  ```

- [ ] **Step 7: Legg til midjefilter-skjemafelt i Helseprofil-fanen**

  I Helseprofil-fanen i innstillinger finnes skjemaet med vekt-feltet. Søk etter `Vekt (kg)` i HTML-en. Legg til disse feltene rett ETTER vekt-feltet (etter dets avsluttende `</label>`-tag):

  ```svelte
  <label>Midjemål (cm) — valgfritt
    <input type="number" min="50" max="200"
      bind:value={profilFelt.midje}
      placeholder="f.eks. 88" />
  </label>
  {#if profilFelt.midje}
    <label class="midjefilter-label">
      <input type="checkbox" bind:checked={profilFelt.midjeFilter} />
      Filtrer matplan mot sunnere oppskrifter
    </label>
    {#if !midjeOverGrenjeFelt}
      <p class="midjefilter-info">
        Midjemålet er innenfor normalområdet — filteret har liten effekt.
      </p>
    {/if}
  {/if}
  ```

- [ ] **Step 8: Legg til 🎯-indikator i profillisten**

  Finn der `tdee(p)` vises i profillisten (søk etter `tdee(p)` i HTML-seksjonen for profil-dropdown eller profilliste). Det ser trolig slik ut:
  ```svelte
  <span>{tdee(p)} kcal/dag</span>
  ```
  Erstatt med:
  ```svelte
  <span>{tdee(p)} kcal/dag {midjeOverGrenje(p) ? "🎯" : ""}</span>
  ```

- [ ] **Step 9: Legg til CSS**

  Finn `<style>`-blokken, gå til slutten (før `</style>`). Legg til:
  ```css
  /* ── Midjefilter ──────────────────────────────────────────── */
  .midjefilter-label { display: flex; align-items: center; gap: 8px; font-weight: normal; cursor: pointer; }
  .midjefilter-info { font-size: 0.8rem; color: var(--text-muted); margin: 2px 0 8px; }
  ```

- [ ] **Step 10: Verifiser TypeScript**

  ```powershell
  cd kokebok-app && npx tsc --noEmit
  ```
  Forventet: 0 nye feil.

- [ ] **Step 11: Commit**

  ```bash
  git add kokebok-app/src/routes/+page.svelte
  git commit -m "feat(midjefilter): midjefilter-skjemafelt, aktivtMidjeFilter-derived, sunnPlan til generer_matplan"
  ```

---

## Spec-dekningssjekk (self-review)

- [x] `midje?: number` og `midjeFilter: boolean` i `Brukerprofil` → Task 1 Step 2
- [x] `midjeOverGrenje(p)` exportert fra `helse.ts` → Task 1 Step 3
- [x] WHO-grenser: mann >94, kvinne >80 → Task 1 Step 3
- [x] `midjeFilter=false` ved lasting av gammel profil (via `?? false` i `startRedigerProfil`) → Task 3 Step 5
- [x] `Kandidat` har `fett: Option<f64>` → Task 2 Step 2
- [x] Fett hentes per porsjon med bulk-query → Task 2 Step 3
- [x] `sunnPlan: bool` i `generer_matplan` signatur → Task 2 Step 5
- [x] Kcal-straf: `>600 kcal/porsjon → score *= 0.5` → Task 2 Step 6
- [x] Fett-straf: `>35% av kcal → score *= 0.7` → Task 2 Step 6
- [x] Kombinert straf `0.35` → Task 2 Step 6
- [x] Ingen straf ved `kcal = None` → Task 2 Step 6 (`k.kcal.map_or(false, ...)`)
- [x] `aktivtMidjeFilter = $derived(...)` → Task 3 Step 4
- [x] `midjeOverGrenjeFelt` for lokal skjema-indikasjon → Task 3 Step 4
- [x] `profilFelt` utvidet med `midje`/`midjeFilter` → Task 3 Step 3
- [x] `startNyProfil` og `startRedigerProfil` oppdatert → Task 3 Step 5
- [x] `sunnPlan: aktivtMidjeFilter` i `genererPlan` → Task 3 Step 6
- [x] Midjemål-input i skjema → Task 3 Step 7
- [x] Checkbox vises kun når `profilFelt.midje` er satt → Task 3 Step 7
- [x] Info-melding ved midje innenfor normalområde → Task 3 Step 7
- [x] 🎯-indikator i profilliste → Task 3 Step 8
- [x] Filter manuelt (ikke auto-aktivert) → aktivtMidjeFilter bruker `midjeFilter`-feltet via `midjeOverGrenje` som krever `p.midjeFilter === true`
