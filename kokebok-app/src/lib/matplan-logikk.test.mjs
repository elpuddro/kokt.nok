import { FORDELING, slotMaal, scoreKandidat, kcalForDag } from "./matplan-logikk.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

// FORDELING summerer til 1
sjekk("fordeling summerer 1.0", () => {
  const s = FORDELING.frokost + FORDELING.lunsj + FORDELING.middag + FORDELING.kveldsmat;
  assert.ok(Math.abs(s - 1) < 1e-9);
});

// slotMaal fordeler dagsmålet
sjekk("slotMaal 2000 → middag 800", () => {
  const m = slotMaal(2000);
  assert.equal(m.middag, 800);
  assert.equal(m.frokost, 400);
  assert.equal(m.lunsj, 500);
  assert.equal(m.kveldsmat, 300);
});

// scoreKandidat: nærmere kcal-mål gir høyere score (jitter=0)
sjekk("nær kcal-mål scorer høyere", () => {
  const tom = new Set();
  const a = scoreKandidat({ kcal: 800, type: "Middag", ingredienser: ["x"] }, 800, tom, tom, 0);
  const b = scoreKandidat({ kcal: 400, type: "Middag", ingredienser: ["x"] }, 800, tom, tom, 0);
  assert.ok(a > b);
});

// scoreKandidat: gjentatt type straffes (variasjon)
sjekk("gjentatt type straffes", () => {
  const tom = new Set();
  const brukt = new Set(["Middag"]);
  const fersk = scoreKandidat({ kcal: 800, type: "Middag", ingredienser: ["a"] }, 800, tom, tom, 0);
  const gjentatt = scoreKandidat({ kcal: 800, type: "Middag", ingredienser: ["a"] }, 800, brukt, tom, 0);
  assert.ok(fersk > gjentatt);
});

// scoreKandidat: delte råvarer premieres (gjenbruk)
sjekk("delte råvarer premieres", () => {
  const tom = new Set();
  const brukteIng = new Set(["løk", "hvitløk"]);
  const deler = scoreKandidat({ kcal: 800, type: "Middag", ingredienser: ["løk", "kjøtt"] }, 800, tom, brukteIng, 0);
  const deler_ikke = scoreKandidat({ kcal: 800, type: "Middag", ingredienser: ["fisk", "ris"] }, 800, tom, brukteIng, 0);
  assert.ok(deler > deler_ikke);
});

// kcalForDag summerer rett-slots, ignorerer rester/enkel/tom
sjekk("kcalForDag ignorerer ikke-rett", () => {
  const slots = [
    { kind: "rett", id: 1, navn: "A", kcal: 400, laast: false },
    { kind: "rester", visTekst: "Rester: A", laast: false },
    { kind: "rett", id: 2, navn: "B", kcal: 800, laast: false },
    { kind: "enkel", visTekst: "Brødskive", laast: false },
  ];
  assert.equal(kcalForDag(slots), 1200);
});

// kcalForDag: null hvis ingen rett har kcal
sjekk("kcalForDag null uten kcal-retter", () => {
  const slots = [{ kind: "enkel", visTekst: "Brødskive", laast: false }];
  assert.equal(kcalForDag(slots), null);
});

console.log(`\n${ok} tester ok`);
