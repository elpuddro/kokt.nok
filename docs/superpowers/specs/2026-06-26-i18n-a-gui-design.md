# Tospråklig app — Sub-prosjekt A: GUI-lag (#38a) — Design

## Mål

Appen bytter automatisk mellom norsk og engelsk basert på systemspråk, med manuell override i Innstillinger. Alle hardkodede UI-strenger, kategorinavn og enheter oversettes via en `t(key, lang)`-funksjon. Ingen DB-endring i dette sub-prosjektet.

## Avhengigheter

Ingen — dette sub-prosjektet er selvstendig og kan implementeres uten endringer i DB eller Rust.

## Arkitektur

- Ny lib-fil: `src/lib/i18n.ts` — eksporterer `t(key, lang)`, `detectLang()`, type `Lang`
- `innstillinger.json` Store får nytt felt `"spraak": "nb" | "en" | "auto"` (default `"auto"`)
- `+page.svelte` får én reaktiv `lang: Lang`-variabel, alle hardkodede strenger erstattes med `t("key", lang)`
- Språkbytte er øyeblikkelig — ingen reload nødvendig

## `src/lib/i18n.ts`

```ts
export type Lang = "nb" | "en";

export function detectLang(): Lang {
  return navigator.language.startsWith("nb") || navigator.language.startsWith("nn")
    ? "nb"
    : "en";
}

export function t(key: string, lang: Lang): string {
  const val = strings[lang]?.[key] ?? strings["nb"][key] ?? key;
  return val;
}

const strings: Record<Lang, Record<string, string>> = {
  nb: { /* alle norske strenger */ },
  en: { /* alle engelske strenger */ },
};
```

Fallback-kjede: engelsk nøkkel → norsk nøkkel → nøkkelnavnet selv. Appen viser aldri tom streng.

## Streng-kategorier (~250 nøkler)

### UI-strenger
Alle knapper, labels, placeholder-tekster, feilmeldinger, modal-titler, sidebar-lenker i `+page.svelte`.

Eksempler:
| Nøkkel | Norsk | Engelsk |
|--------|-------|---------|
| `search_placeholder` | Søk etter oppskrift... | Search for recipe... |
| `btn_favorites` | Favoritter | Favourites |
| `btn_shopping_list` | Handleliste | Shopping list |
| `btn_meal_plan` | Matplan | Meal plan |
| `btn_inventory` | Lager | Pantry |
| `btn_diary` | Dagbok | Food diary |
| `btn_prices` | Priser | Prices |
| `btn_settings` | Innstillinger | Settings |
| `btn_share` | Del | Share |
| `btn_copied` | ✓ Kopiert! | ✓ Copied! |
| `btn_add_to_list` | Legg i handleliste | Add to shopping list |
| `btn_log_meal` | Logg måltid | Log meal |
| `no_results` | Ingen oppskrifter funnet | No recipes found |
| `unknown_recipe` | Ukjent oppskrift | Unknown recipe |
| `servings` | porsjoner | servings |
| `minutes` | min | min |

### Måltidstidspunkt
| Nøkkel | Norsk | Engelsk |
|--------|-------|---------|
| `meal_breakfast` | Frokost | Breakfast |
| `meal_lunch` | Lunsj | Lunch |
| `meal_dinner` | Middag | Dinner |
| `meal_supper` | Kveldsmat | Supper |
| `meal_other` | Annet | Other |

### Kategorier (~20 stykker)
Nøkkelformat: `cat_<slug>` der slug er `type`-verdien fra DB lowercased og mellomrom erstattet med `_`.

Eksempler:
| Nøkkel | Norsk | Engelsk |
|--------|-------|---------|
| `cat_kjøtt_og_fugl` | Kjøtt og fugl | Meat & poultry |
| `cat_fisk_og_skalldyr` | Fisk og skalldyr | Fish & seafood |
| `cat_vegetar` | Vegetar | Vegetarian |
| `cat_baking` | Baking | Baking |
| `cat_desserter` | Desserter | Desserts |
| `cat_supper_og_gryteretter` | Supper og gryteretter | Soups & stews |
| `cat_salater` | Salater | Salads |
| `cat_snacks` | Snacks | Snacks |
| `cat_frokost` | Frokost | Breakfast |
| `cat_alle` | Alle | All |

**Merk:** `get_kategorier`-kommandoen returnerer `type`-verdien fra DB. Frontend oversetter med `t("cat_" + type.toLowerCase().replace(/ /g, "_"), lang)`. Hvis nøkkel mangler, vises `type`-verdien som fallback.

### Enheter
| Nøkkel | Norsk | Engelsk |
|--------|-------|---------|
| `unit_ss` | ss | tbsp |
| `unit_ts` | ts | tsp |
| `unit_dl` | dl | dl |
| `unit_l` | l | l |
| `unit_g` | g | g |
| `unit_kg` | kg | kg |
| `unit_stk` | stk | pcs |
| `unit_pakke` | pakke | pack |
| `unit_ml` | ml | ml |
| `unit_neve` | neve | handful |

### Innstillinger — språkvalg
| Nøkkel | Norsk | Engelsk |
|--------|-------|---------|
| `settings_language` | Språk | Language |
| `lang_auto` | Automatisk (systemspråk) | Automatic (system language) |
| `lang_nb` | Norsk | Norwegian |
| `lang_en` | Engelsk | English |

## Innstillinger-Store

Eksisterende `innstillinger.json` Store får nytt felt:

```ts
interface Innstillinger {
  // ... eksisterende felt ...
  spraak: "nb" | "en" | "auto";  // default "auto"
}
```

`innstillingerLast()` returnerer `"auto"` hvis feltet mangler (bakoverkompatibelt).

## `+page.svelte` — reaktiv `lang`

```ts
import { t, detectLang, type Lang } from "$lib/i18n.ts";

let lang: Lang = $state(detectLang());

// I onMount, etter innstillingerLast():
const spraakValg = innstillinger.spraak ?? "auto";
lang = spraakValg === "auto" ? detectLang() : spraakValg as Lang;
```

Språkbytte i Innstillinger:
```svelte
<select bind:value={spraakValg} onchange={async () => {
  await innstillingerLagre({ ...innstillinger, spraak: spraakValg });
  lang = spraakValg === "auto" ? detectLang() : spraakValg as Lang;
}}>
  <option value="auto">{t("lang_auto", lang)}</option>
  <option value="nb">{t("lang_nb", lang)}</option>
  <option value="en">{t("lang_en", lang)}</option>
</select>
```

Alle hardkodede norske strenger i template erstattes med `t("nøkkel", lang)`.

## Testing

- Unit-test for `t()`: fallback til nøkkelnavn, fallback norsk→engelsk, korrekte verdier for alle kategorier og enheter
- Unit-test for `detectLang()`: `"nb-NO"` → `"nb"`, `"en-US"` → `"en"`, `"fr-FR"` → `"en"`
- Manuell e2e: bytt til engelsk i Innstillinger → alle UI-strenger bytter øyeblikkelig
- Manuell e2e: sett til «Auto», endre `navigator.language` mock → riktig språk velges

## Kanttilfeller

- Ukjent kategori-nøkkel: viser `type`-verdien fra DB (alltid norsk — OK som fallback)
- Ukjent enhets-nøkkel: viser råverdien fra DB (`ss`, `ts` osv. — akseptabelt)
- Manglende `spraak`-felt i gammel Store: `"auto"` brukes som default
- Appen starter uten Store-data: `detectLang()` brukes direkte
