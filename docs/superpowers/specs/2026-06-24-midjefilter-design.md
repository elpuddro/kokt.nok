# Midjefilter og sunnere matplan — Design (#22)

**Dato:** 2026-06-24

---

## Mål

Brukere kan registrere midjemål (cm) på helseprofilen og aktivere et manuelt filter som justerer matplanleggeren mot sunnere oppskrifter (lavere kcal/porsjon og lavere fettprosent). Filteret er aktivt kun når brukeren eksplisitt slår det på, og kun når midjemålet er registrert.

---

## Arkitektur

Tre lag endres:

1. **`helse.ts`** — `Brukerprofil` får to nye felt (`midje?`, `midjeFilter`), ny hjelpefunksjon `midjeOverGrenje(p)` returnerer `true` når midje er over WHO-grensen for kjønnet.
2. **`lib.rs`** — `generer_matplan` får ett nytt parameter `sunn_plan: bool`. Når `true` multipliseres score for høy-kcal og høy-fett kandidater ned.
3. **`+page.svelte`** — Nye skjemafelt i Helseprofil-fanen, `aktivtMidjeFilter`-derived, `sunnPlan`-argument til `generer_matplan`-kallet.

---

## Datamodell

### Endringer i `Brukerprofil` (`helse.ts`)

```typescript
export interface Brukerprofil {
  id: string
  navn: string
  kjønn: "mann" | "kvinne"
  alder: number
  høyde: number
  vekt: number
  aktivitet: Aktivitetsnivå
  mål: Mål
  midje?: number        // cm, heltall, valgfritt
  midjeFilter: boolean  // standard: false
}
```

Bakoverkompatibilitet: eksisterende lagrede profiler mangler `midje` og `midjeFilter`. Ved lasting håndteres dette med `?? false` for `midjeFilter` og `undefined` for `midje` — ingen migrasjonskode nødvendig.

### Hjelpefunksjon

```typescript
export function midjeOverGrenje(p: Brukerprofil): boolean {
  if (!p.midjeFilter || p.midje == null) return false
  return p.kjønn === "mann" ? p.midje > 94 : p.midje > 80
}
```

WHO-grenser: mann >94 cm, kvinne >80 cm.

---

## Rust: `generer_matplan`

### Nytt parameter

`generer_matplan` får `sunn_plan: bool` (camelCase i Tauri: `sunnPlan`).

### Scoringsjustering

Etter eksisterende score-beregning per kandidat, når `sunn_plan = true`:

```rust
if sunn_plan {
    // Straf høy kcal (over 600 kcal/porsjon)
    if kandidat.kcal > 600.0 {
        score *= 0.5;
    }
    // Straf høy fettprosent (fett > 35% av total kcal)
    // fett_kcal = fett_g * 9; total_kcal = kcal
    if kandidat.kcal > 0.0 && (kandidat.fett * 9.0 / kandidat.kcal) > 0.35 {
        score *= 0.7;
    }
}
```

Kombinert effekt for en oppskrift med både høy kcal og høy fett: `score *= 0.35`.

Oppskrifter uten næringsdata (`kcal = 0.0`) straffes ikke — de beholder eksisterende score.

`kandidat.kcal` og `kandidat.fett` er allerede tilgjengelig i strukturen som brukes i scoring (fra `naering`-tabellen, per porsjon). Ingen ny DB-query nødvendig.

---

## UI: Helseprofil-skjema

### Nye felt i opprett/rediger-skjema

Legg til etter `vekt`-feltet:

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

`midjeOverGrenjeFelt` er en lokal beregning basert på `profilFelt` (ikke aktiv profil):
```typescript
let midjeOverGrenjeFelt = $derived(
  profilFelt.midje != null &&
  (profilFelt.kjønn === "mann" ? profilFelt.midje > 94 : profilFelt.midje > 80)
)
```

### Profilliste — aktiv-indikator

I profillisten legges 🎯 til ved siden av TDEE-tallet når `midjeOverGrenje(p)` er `true`:

```svelte
<span>{tdee(p)} kcal/dag {midjeOverGrenje(p) ? "🎯" : ""}</span>
```

### `profilFelt`-utvidelse

`profilFelt` får to nye felt:
```typescript
let profilFelt = $state({
  navn: "", kjønn: "mann" as "mann"|"kvinne",
  alder: 30, høyde: 175, vekt: 75,
  aktivitet: "moderat" as Brukerprofil["aktivitet"],
  mål: "vedlikehold" as Brukerprofil["mål"],
  midje: undefined as number | undefined,
  midjeFilter: false,
})
```

`startRedigerProfil` og `startNyProfil` oppdateres tilsvarende.

### `aktivtMidjeFilter` derived

```typescript
let aktivtMidjeFilter = $derived(aktivProfil ? midjeOverGrenje(aktivProfil) : false)
```

### Kall til `generer_matplan`

Finn eksisterende `invoke("generer_matplan", { ... })` og legg til `sunnPlan: aktivtMidjeFilter`.

---

## Ikke inkludert (YAGNI)

- Automatisk aktivering av filter (brukeren må aktivere manuelt)
- Historikk over midjeutvikling
- Visualisering av WHO-risikosoner
- Justert TDEE basert på kroppsfett-estimat

---

## Filer som endres

| Fil | Endring |
|-----|---------|
| `kokebok-app/src/lib/helse.ts` | `midje?` og `midjeFilter` i `Brukerprofil`, `midjeOverGrenje(p)` |
| `kokebok-app/src-tauri/src/lib.rs` | `sunnPlan: bool` i `generer_matplan`, scoringsjustering |
| `kokebok-app/src/routes/+page.svelte` | Skjemafelt, `midjeOverGrenjeFelt`-derived, `aktivtMidjeFilter`-derived, `sunnPlan`-argument |
