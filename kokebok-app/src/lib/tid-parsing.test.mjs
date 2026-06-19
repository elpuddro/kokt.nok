import { finnTider } from "./tid-parsing.ts";
import assert from "node:assert";

let bestått = 0;
function sjekk(navn, fn) {
  try { fn(); bestått++; console.log("  ok  " + navn); }
  catch (e) { console.error("FAIL " + navn + ": " + e.message); process.exitCode = 1; }
}

// Enkelt tall + enhet → sekunder
sjekk("40 minutter = 2400s", () => {
  const t = finnTider("stek i ca. 40 minutter");
  assert.equal(t.length, 1);
  assert.equal(t[0].sekunder, 2400);
});
sjekk("5 min = 300s", () => assert.equal(finnTider("kok 5 min")[0].sekunder, 300));
sjekk("1 minutt = 60s", () => assert.equal(finnTider("vent 1 minutt")[0].sekunder, 60));
sjekk("30 sekunder = 30s", () => assert.equal(finnTider("rør i 30 sekunder")[0].sekunder, 30));
sjekk("2 timer = 7200s", () => assert.equal(finnTider("la heve i 2 timer")[0].sekunder, 7200));
sjekk("1 t = 3600s", () => assert.equal(finnTider("stek 1 t")[0].sekunder, 3600));

// Intervall → øvre grense av DET intervallet
sjekk("20-30 minutter = 1800s (øvre)", () =>
  assert.equal(finnTider("stek i 20-30 minutter")[0].sekunder, 1800));
sjekk("1-2 timer = 7200s (øvre)", () =>
  assert.equal(finnTider("hev i 1-2 timer")[0].sekunder, 7200));
sjekk("5-6 timer = 21600s (øvre, ikke tak)", () =>
  assert.equal(finnTider("la stå i 5-6 timer")[0].sekunder, 21600));
sjekk("em-dash 45–50 minutter = 3000s", () =>
  assert.equal(finnTider("stek 45–50 minutter")[0].sekunder, 3000));

// Brøk
sjekk("1½ t = 5400s", () => assert.equal(finnTider("stek 1½ t")[0].sekunder, 5400));
sjekk("½ time = 1800s", () => assert.equal(finnTider("vent ½ time")[0].sekunder, 1800));
sjekk("1¼ time = 4500s", () => assert.equal(finnTider("kok 1¼ time")[0].sekunder, 4500));

// Flere i ett trinn → alle
sjekk("flere tider", () => {
  const t = finnTider("stek 20 min, deretter hvil 5 min");
  assert.equal(t.length, 2);
  assert.equal(t[0].sekunder, 1200);
  assert.equal(t[1].sekunder, 300);
});

// Posisjon (for klikkbar markering)
sjekk("start/slutt-posisjon", () => {
  const t = finnTider("kok i 5 min nå");
  assert.equal("kok i 5 min nå".slice(t[0].start, t[0].slutt), t[0].tekst);
});

// Robusthet
sjekk("ingen tid → tom", () => assert.equal(finnTider("rør godt sammen").length, 0));
sjekk("løst tall uten enhet ignoreres", () =>
  assert.equal(finnTider("del i 4 biter").length, 0));
sjekk("urimelig stor verdi forkastes (100 timer)", () =>
  assert.equal(finnTider("la stå i 100 timer").length, 0));
sjekk("tom streng → tom", () => assert.equal(finnTider("").length, 0));

console.log(`\n${bestått} tester ok`);
