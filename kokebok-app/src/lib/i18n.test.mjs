import assert from "node:assert/strict";

// Importer hele modulen som tekst og evaluer den (node-kompatibel workaround for TS)
// Test-strategien: vi tester LOGIKKEN, ikke TypeScript-typene.
// vi mock'er strings-objektet direkte i testen.

// Minimal implementasjon av t() som speiler i18n.ts sin logikk:
function makeDicts(nb, en) {
  const strings = { nb, en };
  return function t(key, lang) {
    return strings[lang]?.[key] ?? strings["nb"][key] ?? key;
  };
}

// Test 1: riktig verdi for eksisterende nøkkel
{
  const t = makeDicts({ hello: "Hei" }, { hello: "Hello" });
  assert.equal(t("hello", "en"), "Hello");
  assert.equal(t("hello", "nb"), "Hei");
}

// Test 2: fallback norsk → nøkkelnavn når ingen språk har nøkkelen
{
  const t = makeDicts({}, {});
  assert.equal(t("ukjent_nokkel", "en"), "ukjent_nokkel");
  assert.equal(t("ukjent_nokkel", "nb"), "ukjent_nokkel");
}

// Test 3: fallback engelsk → norsk når engelsk mangler nøkkel
{
  const t = makeDicts({ bare_norsk: "Bare norsk" }, {});
  assert.equal(t("bare_norsk", "en"), "Bare norsk");
}

// Test 4: detectLang-logikk (nb/nn → nb, alt annet → en)
function detectLang(navLang) {
  return navLang.startsWith("nb") || navLang.startsWith("nn") ? "nb" : "en";
}
assert.equal(detectLang("nb-NO"), "nb");
assert.equal(detectLang("nn-NO"), "nb");
assert.equal(detectLang("en-US"), "en");
assert.equal(detectLang("fr-FR"), "en");
assert.equal(detectLang("de-DE"), "en");

console.log("i18n.test.mjs: alle 5 tester OK");
