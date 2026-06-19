# godt.no-skraper — designspesifikasjon

> Status: godkjent design, klar for implementeringsplan.
> Dato: 2026-06-15.

## Mål

Legge til oppskrifter (med bilder) fra godt.no som en **andre datakilde** ved
siden av de eksisterende 4444 matprat-oppskriftene, til **privat/offline bruk**.
Mater samme skjema og bildepipeline som allerede finnes.

## Juridisk / etisk ramme (les først)

- **Privat bruk.** Appen distribueres ikke offentlig; dette speiler den
  eksisterende matprat-presedensen (README: «Privat bruk. Oppskriftsdata ©
  matprat.no»). README utvides med tilsvarende godt.no-attribusjon.
- **godt.no robots.txt blokkerer eksplisitt AI-crawlere** (navngir ClaudeBot,
  anthropic-ai m.fl. med `Disallow: /`). Det finnes ingen generell
  `User-agent: *`-blokk i fila. Skriptet er en **bruker-kjørt** prosess med egen
  user-agent, ikke en AI-crawler, men signalet er at siden ikke ønsker
  bulk-automatisk innsamling. Brukeren tar ansvar for privat bruk.
- **Agent-grense:** Claude designer/skriver skriptet, men **crawler ikke godt.no
  selv** under arbeidet (ingen live-fetch av oppskriftssider). Derfor er designet
  bygget mot godt.no sin *sannsynlige* struktur (schema.org/Recipe JSON-LD, vanlig
  for norske oppskriftssider); **brukeren validerer mot ekte sider** ved kjøring.
- Skriptet skal være en god borger: respektere robots.txt for egen UA, sette en
  tydelig ikke-villedende UA, rate-limite, og cache sider lokalt.

## Beslutninger (låst i brainstorming)

| Tema | Valg |
|------|------|
| Oppdagelse | Sitemap-drevet (`/sitemap-index.xml` → under-sitemaps → `/oppskrifter/`-URLer) |
| Uttrekk | JSON-LD (schema.org/Recipe) først, defensiv HTML-fallback |
| Ingredienser | Ny norsk best-effort-parser + behold alltid `raatekst` |
| Rate-limit | Moderat ~3–5 req/s, enkelt-trådet |
| Bilder | Last ned → 600px WebP → `bilder/{slug}.webp` (matcher images-in-DB-pipeline) |
| Skrivemål | Direkte inn i `data/kokt.db` (re-kjørbar via dedup) |
| Dedup | URL-eksakt + uklar navnematch (`difflib`) mot eksisterende rader |
| Tester | pytest for rene parsere; `--limit N` for manuell første kjøring |

## Arkitektur

Ett Python-skript `scripts/hent_godt.py`, kjørt én gang fra repo-roten — samme
husstil som `hent_naering.py`/`hent_priser.py`: stdlib `urllib`, UTF-8
stdout-reconfigure, `_finn_db()`-locator, lokal cache. Andre datakilde til samme
skjema: `oppskrifter`, `ingredienser`, `trinn`, `kategorier`.

### Pipeline (per kjøring)
1. **Oppdag** — hent `/sitemap-index.xml`, bor i under-sitemaps, samle
   `/oppskrifter/`-URLer.
2. **Høflighetsport** — hent `/robots.txt`, respekter for egen UA; tydelig UA;
   ~3–5 req/s enkelt-trådet; cache sider i `scripts/godt_cache/`.
3. **Uttrekk** — JSON-LD (name, ingredients, instructions, image, servings, time,
   category); HTML-fallback for manglende felt.
4. **Dedup** — hopp over hvis `url` finnes; hopp over hvis `navn` uklart matcher
   eksisterende (`difflib`).
5. **Parse ingredienser** — norsk best-effort: `mengde`/`enhet`/`navn`, behold
   `raatekst`.
6. **Bilde** — last ned hovedbilde → WebP, 600px lengste side → `bilder/{slug}.webp`.
7. **Skriv** — sett inn i `data/kokt.db` med `url`, `hentet` (ISO-tidsstempel).

### Komponenter (funksjoner i `scripts/hent_godt.py`)

| Funksjon | Ansvar |
|----------|--------|
| `_finn_db()` | Finn kanonisk kokt.db (kopi av helper i hent_naering.py) |
| `hent(url)` | Én høflig GET: cache-sjekk → UA-header → rate-limit-sleep → bytes; cache til `godt_cache/` |
| `robots_ok(url)` | Sjekk sti mot robots.txt for egen UA før fetch (`urllib.robotparser`) |
| `finn_oppskrift_urls()` | Sitemap-index → under-sitemaps → filtrert URL-liste (`xml.etree`) |
| `parse_jsonld(html)` | Trekk ut schema.org/Recipe-dict fra `<script type="application/ld+json">` |
| `parse_html_fallback(html, felt)` | Best-effort HTML-uttrekk for felt JSON-LD manglet |
| `parse_ingrediens(linje)` | Norsk rålinje → `(mengde, enhet, navn)`; `2 dl`, `½ ts`, `100 g`, brøk, «etter smak» |
| `lagre_bilde(url, slug)` | Last ned foto → 600px WebP → `bilder/{slug}.webp` (Pillow) |
| `er_duplikat(conn, url, navn)` | URL-eksakt + `difflib` uklar navnematch |
| `lagre_oppskrift(conn, data)` | Sett inn i alle 4 tabeller i én transaksjon |
| `main()` | Orkestrer: oppdag → loop (dedup → uttrekk → parse → bilde → lagre) → fremdrift/oppsummering; støtter `--limit N` og `--delay` |

**Avhengigheter:** stdlib + **Pillow** (allerede brukt i recompress/bygg_bundle).
Ingen nye tunge deps (ingen requests/bs4) — HTML-fallback bruker `re`/`html.parser`.

**Risiko flagget:** JSON-LD-parsing er stdlib-enkel og robust; **HTML-fallback** er
den skjøre delen. Skrives defensivt (try/except per felt, logg-og-hopp-over), og
er den delen brukeren mest sannsynlig må justere mot ekte sider. Skriptet
rapporterer hvilke oppskrifter som falt tilbake til HTML eller ble hoppet over.

## Skjemamapping

**`oppskrifter`:**
| Kolonne | Kilde |
|---------|-------|
| `slug` | URL-slug; dedup-suffiks ved kollisjon |
| `navn` | JSON-LD `name` |
| `type` | JSON-LD `recipeCategory` (første) → mappet til eksisterende `type`-vokabular der mulig, ellers rå |
| `beskrivelse` | JSON-LD `description` |
| `porsjoner` | JSON-LD `recipeYield` (ledende heltall) |
| `tid` | JSON-LD `totalTime`/`cookTime` (ISO-8601 → lesbar streng som matprat-`tid`) |
| `bilde` | `bilder/{slug}.webp` (etter `lagre_bilde`) |
| `url` | oppskrifts-URL (proveniens + dedup-nøkkel) |
| `hentet` | ISO-tidsstempel ved skraping |

**`ingredienser`:** én rad per `recipeIngredient` → `parse_ingrediens` →
`mengde`/`enhet`/`navn` + `raatekst`, `gruppe` (hvis sidegruppert, ellers null),
`sortering` (rekkefølge).

**`trinn`:** `recipeInstructions` (`HowToStep`-liste) → én rad hver, `nummer` =
rekkefølge, `tekst` = trinntekst.

**`kategorier`:** `recipeCategory` + `keywords` → kategorirader.

**Ikke fylt:** `naering` og priser — fylles etterpå av eksisterende
`hent_naering.py` / `hent_priser.py` (kjøres på nytt etter skraping, som for
matprat). README noterer dette.

## Feilhåndtering

Per-oppskrift try/except — én dårlig side logger advarsel og hoppes over, aborterer
aldri kjøringen. Cache gjør re-kjøring billig (kun nye/feilede sider hentes på
nytt). Oppsummering til slutt: `N nye, M duplikater, K hoppet over (feil)`.

## Testing & validering

Ingen automatisk testsuite i prosjektet, men de rene delene er testbare — legg til
pytest-tester etter `scripts/test_kassal.py`-presedens (pytest er i
`requirements-dev.txt`):
- **`parse_ingrediens`** — norske eksempellinjer (`"2 dl melk"` →
  `(2.0, "dl", "melk")`, `"½ ts salt"`, `"100 g smør"`, `"salt etter smak"` →
  `(None, None, "salt etter smak")`, `"3 egg"`).
- **`parse_jsonld`** — mot en lagret/håndskrevet schema.org/Recipe-fixture.
- **`er_duplikat`** — URL-eksakt og uklar-navn mot in-memory DB.

**Manuell validering (bruker, mot ekte sider):** kjør først med `--limit 10`,
sjekk at navn/ingredienser/trinn/bilder kom riktig gjennom, så hele katalogen.

**Operasjonell sikkerhet:** skriver til git-sporet `kokt.db` — kjør første ekte
kjøring på en branch og inspiser diff/radtellinger før commit.

## Dokumentasjon

README: utvid lisens-linja med godt.no-attribusjon, og noter at `hent_naering.py`
+ `hent_priser.py` bør kjøres på nytt etter skraping for å dekke nye oppskrifter.

## Avgrensninger (ikke i denne saken)

- Næring/pris for nye oppskrifter — eksisterende skript, kjøres etterpå.
- images-in-DB-bundling — egen parkert branch (`feat/bilder-i-db`); de nye
  `bilder/{slug}.webp` plukkes naturlig opp av den pipelinen når den fullføres.
