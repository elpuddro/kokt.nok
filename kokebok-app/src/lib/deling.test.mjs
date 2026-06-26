import { formaterOppskrift } from "./deling.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

const full = {
  navn: "Pasta Carbonara",
  tid: 30,
  porsjoner: 4,
  ingredienser: [
    { mengde: 400, enhet: "g", navn: "pasta" },
    { mengde: 150, enhet: "g", navn: "bacon" },
  ],
  trinn: [
    { nummer: 1, tekst: "Kok pasta." },
    { nummer: 2, tekst: "Stek bacon." },
    { nummer: 3, tekst: "Bland sammen." },
  ],
};

const ingenIngr = { navn: "Testoppskrift", tid: 10, porsjoner: 2, ingredienser: [], trinn: [{ nummer: 1, tekst: "Gjør noe." }] };
const ingenSteg = { navn: "Testoppskrift 2", tid: 5, porsjoner: 1, ingredienser: [{ mengde: 1, enhet: "stk", navn: "egg" }], trinn: [] };
const minimal = { navn: "Bare navn" };

sjekk("inneholder oppskriftnavn", () => {
  assert.ok(formaterOppskrift(full).includes("Pasta Carbonara"));
});
sjekk("inneholder tid og porsjoner", () => {
  const t = formaterOppskrift(full);
  assert.ok(t.includes("30 min"));
  assert.ok(t.includes("4"));
});
sjekk("inneholder ingredienser", () => {
  const t = formaterOppskrift(full);
  assert.ok(t.includes("pasta"));
  assert.ok(t.includes("400 g"));
});
sjekk("inneholder fremgangsmåte nummerert", () => {
  const t = formaterOppskrift(full);
  assert.ok(t.includes("1. Kok pasta."));
  assert.ok(t.includes("3. Bland sammen."));
});
sjekk("inneholder footer", () => {
  assert.ok(formaterOppskrift(full).includes("Delt fra Steike bra"));
});
sjekk("ingen ingredienser → seksjonen utelates", () => {
  const t = formaterOppskrift(ingenIngr);
  assert.ok(!t.includes("INGREDIENSER"));
});
sjekk("ingen steg → seksjonen utelates", () => {
  const t = formaterOppskrift(ingenSteg);
  assert.ok(!t.includes("FREMGANGSMÅTE"));
});
sjekk("minimal oppskrift (bare navn) → krasjer ikke", () => {
  const t = formaterOppskrift(minimal);
  assert.ok(t.includes("Bare navn"));
  assert.ok(t.includes("Delt fra Steike bra"));
});

console.log(`\n${ok} tester ok`);
