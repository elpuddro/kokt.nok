import { prisForIngrediens, prisHistorikk, unike_ingredienser } from "./priser-logikk.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

const poster = [
  { id: "1", ingrediens: "Kyllingfilet", pris: 89.9, enhet: "kg", dato: "2026-06-01", butikk: "Rema" },
  { id: "2", ingrediens: "kyllingfilet", pris: 94.9, enhet: "kg", dato: "2026-06-20", butikk: "Kiwi" },
  { id: "3", ingrediens: "Mel", pris: 15.0, enhet: "kg", dato: "2026-06-10" },
];

sjekk("eksakt match case-insensitiv → siste post", () => {
  const res = prisForIngrediens("kyllingfilet", poster);
  assert.equal(res?.id, "2");
  assert.equal(res?.pris, 94.9);
});
sjekk("eksakt match med annen case → siste post", () => {
  const res = prisForIngrediens("KYLLINGFILET", poster);
  assert.equal(res?.id, "2");
});
sjekk("substring match → siste", () => {
  const res = prisForIngrediens("kylling", poster);
  assert.ok(res !== null);
});
sjekk("ingen match → null", () => {
  assert.equal(prisForIngrediens("banan", poster), null);
});
sjekk("prisHistorikk returnerer sortert dato asc", () => {
  const res = prisHistorikk("kyllingfilet", poster);
  assert.equal(res.length, 2);
  assert.equal(res[0].dato, "2026-06-01");
  assert.equal(res[1].dato, "2026-06-20");
});
sjekk("unike_ingredienser returnerer unike navn (lowercase)", () => {
  const res = unike_ingredienser(poster);
  assert.equal(res.length, 2);
  assert.ok(res.includes("kyllingfilet"));
  assert.ok(res.includes("mel"));
});

console.log(`\n${ok} tester ok`);
