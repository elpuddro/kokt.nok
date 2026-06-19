# Temaer (fargepaletter + sesong/høytids-automatikk) — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-17.

## Mål

La brukeren bytte fargepalett mellom 11 temaer (standard, dark mode, 4 sesonger,
5 høytider), med **automatisk** bytte til sesong/høytidstema etter dato og
mulighet for manuell overstyring (huskes). Backlog-idé #8.

## Arkitektur

Hele appen drives av ~25 CSS-variabler i `:root` (`app.css`), referert 114
ganger i `+page.svelte`. Et tema = et annet sett verdier for disse variablene.
**Ingen komponentendringer** — vi setter `data-tema` på `<html>`, og en
`[data-tema="..."]`-blokk i `app.css` overstyrer `:root`. Standardtemaet («varm»)
= `:root` (intet attributt).

### Tre lag

1. **`kokebok-app/src/app.css`** — én `[data-tema="X"]`-blokk per ikke-standard
   tema (10 blokker). Hver overstyrer fargevariablene som skiller seg fra
   standard (`--bg`, `--bg-warm`, `--surface`, `--card`, `--card-hover`,
   `--sidebar-bg`, `--border*`, `--accent*`, `--text*`, `--shadow*`). Inkl. ekte
   dark mode (mørke flater, lysere tekst).

2. **`kokebok-app/src/lib/tema.ts`** — ren logikk + tynn Store-wrapper:
   | Funksjon | Ansvar | Testbar |
   |----------|--------|---------|
   | `paaskedag(år)` | Computus → `Date` for påskedag | ✅ ren |
   | `gjeldendeTema(dato)` | dato → tema-id (høytid → sesong → "varm") | ✅ ren |
   | `aktivtTema(lagret, dato)` | løs faktisk tema (auto→gjeldendeTema, ellers manuelt) | ✅ ren |
   | `temaLast()` | les `{modus, tema}` fra Store; default `{modus:"auto"}` | Store |
   | `temaSett(modus, tema)` | lagre valg | Store |

   Store-delen best-effort (favoritt-mønster). Persistering: `tema.json` —
   `{ modus: "auto" | "manuell", tema: string | null }`.

3. **`kokebok-app/src/routes/+page.svelte`** — state + `applyTema(id)` (setter
   `document.documentElement.dataset.tema`, fjerner for "varm"); `onMount` løser
   og anvender tema; sidebar-knapp «⚙️ Innstillinger» → modus
   `currentKategori === "__innst__"`; innstillings-visning med tema-velger
   (Automatisk + 11 temaer) som kaller `temaSett` + `applyTema`.

### Tema-id-er (11)
`varm` (standard), `dark`, `vinter`, `vaar`, `sommer`, `host`, `17mai`,
`halloween`, `valentines`, `paske`, `singles`.

### Auto-logikk (`gjeldendeTema(dato)`)

Sjekk høytidsvinduer først (mest spesifikke), så sesong etter måned, ellers
"varm".

| Tema | Vindu |
|------|-------|
| Valentines | 7.–14. feb |
| Påske | palmesøndag (påskedag−7) → 2. påskedag (påskedag+1), via `paaskedag(år)` (Computus) |
| 17. mai | 10.–18. mai |
| Halloween | 24.–31. okt |
| Singles Day | 11. nov |
| Jul/vinter | 1. des–6. jan |
| Sesong ellers | vår (mar–mai), sommer (jun–aug), høst (sep–nov), vinter (des–feb) |

Manuelt valg overstyrer auto til brukeren velger «Automatisk» igjen.

## Dataflyt

```
OPPSTART: lagret = temaLast() → id = aktivtTema(lagret, new Date())
  → applyTema(id) → document.documentElement.dataset.tema = id
  → CSS [data-tema=id] overstyrer :root → hele appen re-skinnes
VELG TEMA: "Automatisk" → temaSett("auto", null) + applyTema(aktivtTema(...))
           "<tema>"     → temaSett("manuell", id) + applyTema(id); persistert
```

## Feilhåndtering

- Store-feil → default `{modus:"auto"}`, app starter i auto/standard. Aldri krasj.
- Ukjent lagret tema-id → fall tilbake til "varm".
- `applyTema("varm")` fjerner `data-tema` (bruker `:root`).

## Testing

Ingen frontend-testsuite i prosjektet, men `tema.ts` sin rene logikk er
node-testbar (skrives som frittstående test, mønster fra Python-skriptene):
- `paaskedag(2024)` = 31. mars; `paaskedag(2026)` = 5. april; `paaskedag(2027)` = 28. mars.
- `gjeldendeTema(2026-10-28)` = "halloween"; `(2026-05-17)` = "17mai";
  `(2026-11-11)` = "singles"; `(2026-07-15)` = "sommer"; `(2026-12-24)` = "vinter".
- `aktivtTema({modus:"manuell",tema:"dark"}, <enhver dato>)` = "dark".

Resten (CSS-paletter, sidebar-knapp, innstillingsvisning) via `npm run build` +
manuell e2e: bytt tema → hele appen skifter farge umiddelbart; «Automatisk» →
ser dagens auto-tema; lukk/åpne → valget består.

## Filer

| Fil | Endring |
|-----|---------|
| `kokebok-app/src/lib/tema.ts` | Create — logikk + Store |
| `kokebok-app/src/app.css` | Modify — 10 tema-palett-blokker |
| `kokebok-app/src/routes/+page.svelte` | Modify — state, applyTema, sidebar-knapp, innstillingsvisning |

## Avgrensninger (ikke i denne saken)

- Egne notater (backlog #7) — egen sak, tas rett etter dette.
- Innstillinger-visningen er bevisst laget som egen sidebar-seksjon så den kan
  romme fremtidige innstillinger (notater, halal-filter), men kun tema-velgeren
  bygges nå.
