import { kopiFraOppskrift, beregnDiff } from "./versjoner-logikk.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

const rawOpp = {
  id: 1, navn: "Pasta", beskrivelse: "God pasta", porsjoner: 4, tid: "30 min",
  ingredienser: [
    { gruppe: null, mengde: 200, enhet: "g", navn: "pasta", sortering: 0 },
    { gruppe: null, mengde: 1, enhet: "ss", navn: "olje", sortering: 1 },
  ],
  trinn: [
    { nummer: 1, tekst: "Kok opp vann." },
    { nummer: 2, tekst: "Ha i pasta." },
  ],
};

// kopiFraOppskrift lager OppskriftKopi fra råoppskrift
sjekk("kopiFraOppskrift: navn og tid", () => {
  const k = kopiFraOppskrift(rawOpp);
  assert.equal(k.navn, "Pasta");
  assert.equal(k.tid, "30 min");
  assert.equal(k.porsjoner, 4);
});

sjekk("kopiFraOppskrift: ingredienser", () => {
  const k = kopiFraOppskrift(rawOpp);
  assert.equal(k.ingredienser.length, 2);
  assert.equal(k.ingredienser[0].navn, "pasta");
  assert.equal(k.ingredienser[1].enhet, "ss");
});

sjekk("kopiFraOppskrift: trinn", () => {
  const k = kopiFraOppskrift(rawOpp);
  assert.equal(k.trinn.length, 2);
  assert.equal(k.trinn[0].tekst, "Kok opp vann.");
});

// beregnDiff: ingen endringer
sjekk("beregnDiff: ingen endringer", () => {
  const k = kopiFraOppskrift(rawOpp);
  const diff = beregnDiff(k, k);
  assert.equal(diff.navn.endret, false);
  assert.equal(diff.ingredienser.every(d => !d.endret), true);
  assert.equal(diff.trinn.every(d => !d.endret), true);
});

// beregnDiff: endret navn
sjekk("beregnDiff: endret navn", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = { ...orig, navn: "Annen pasta" };
  const diff = beregnDiff(orig, versjon);
  assert.equal(diff.navn.endret, true);
  assert.equal(diff.navn.orig, "Pasta");
  assert.equal(diff.navn.versjon, "Annen pasta");
});

// beregnDiff: endret ingrediensmengde
sjekk("beregnDiff: endret mengde gir endret=true", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    ingredienser: [
      { ...orig.ingredienser[0], mengde: 300 },
      orig.ingredienser[1],
    ],
  };
  const diff = beregnDiff(orig, versjon);
  assert.equal(diff.ingredienser[0].endret, true);
  assert.equal(diff.ingredienser[1].endret, false);
});

// beregnDiff: ny ingrediens i versjon
sjekk("beregnDiff: ny ingrediens i versjon", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    ingredienser: [
      ...orig.ingredienser,
      { gruppe: null, mengde: 2, enhet: "fedd", navn: "hvitløk", sortering: 2 },
    ],
  };
  const diff = beregnDiff(orig, versjon);
  // ekstra rad med orig=null
  const ny = diff.ingredienser.find(d => d.orig === null);
  assert.ok(ny !== undefined);
  assert.equal(ny.versjon?.navn, "hvitløk");
});

// beregnDiff: slettet ingrediens
sjekk("beregnDiff: slettet ingrediens", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    ingredienser: [orig.ingredienser[0]],
  };
  const diff = beregnDiff(orig, versjon);
  const slettet = diff.ingredienser.find(d => d.versjon === null);
  assert.ok(slettet !== undefined);
  assert.equal(slettet.orig?.navn, "olje");
});

// beregnDiff: omskrevet trinn
sjekk("beregnDiff: omskrevet trinn", () => {
  const orig = kopiFraOppskrift(rawOpp);
  const versjon = {
    ...orig,
    trinn: [
      { nummer: 1, tekst: "Kok opp masse vann." },
      orig.trinn[1],
    ],
  };
  const diff = beregnDiff(orig, versjon);
  assert.equal(diff.trinn[0].endret, true);
  assert.equal(diff.trinn[1].endret, false);
});

console.log(`\n${ok} tester OK`);
