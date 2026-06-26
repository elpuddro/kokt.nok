import { loggForDato, tidspunktFraKlokkeslett, loggSumNæring, loggKcalPerDag } from "./matvarelogg-logikk.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

const næring = { 1: { kcal: 400, protein: 30, fett: 10, karbo: 50 } };

const poster = [
  { id: "a", dato: "2026-06-26", tidspunkt: "middag", type: "oppskrift", oppskriftId: 1, porsjoner: 2 },
  { id: "b", dato: "2026-06-26", tidspunkt: "frokost", type: "fri", beskrivelse: "egg", kcal: 140, protein: 12, fett: 10, karbo: 0 },
  { id: "c", dato: "2026-06-25", tidspunkt: "lunsj", type: "fri", beskrivelse: "salat", kcal: 200, protein: 5, fett: 8, karbo: 20 },
];

sjekk("loggForDato filtrerer riktig dato", () => {
  const res = loggForDato(poster, "2026-06-26");
  assert.equal(res.length, 2);
});
sjekk("loggForDato tom ved ingen match", () => {
  assert.equal(loggForDato(poster, "2026-01-01").length, 0);
});
sjekk("tidspunktFraKlokkeslett 8 → frokost", () => assert.equal(tidspunktFraKlokkeslett(8), "frokost"));
sjekk("tidspunktFraKlokkeslett 12 → lunsj", () => assert.equal(tidspunktFraKlokkeslett(12), "lunsj"));
sjekk("tidspunktFraKlokkeslett 16 → middag", () => assert.equal(tidspunktFraKlokkeslett(16), "middag"));
sjekk("tidspunktFraKlokkeslett 20 → kveldsmat", () => assert.equal(tidspunktFraKlokkeslett(20), "kveldsmat"));
sjekk("tidspunktFraKlokkeslett 3 → annet", () => assert.equal(tidspunktFraKlokkeslett(3), "annet"));
sjekk("loggSumNæring oppskrift × 2 porsjoner + fri", () => {
  const res = loggSumNæring(loggForDato(poster, "2026-06-26"), næring);
  assert.equal(res.kcal, 940); // 400*2 + 140
  assert.equal(res.protein, 72); // 30*2 + 12
});
sjekk("loggSumNæring ukjent oppskrift → kcal 0", () => {
  const p = [{ id: "x", dato: "2026-06-26", tidspunkt: "middag", type: "oppskrift", oppskriftId: 99, porsjoner: 1 }];
  const res = loggSumNæring(p, næring);
  assert.equal(res.kcal, 0);
});
sjekk("loggKcalPerDag returnerer siste N dager", () => {
  const res = loggKcalPerDag(poster, næring, 7);
  assert.equal(res.length, 7);
  const dag26 = res.find(d => d.dato === "2026-06-26");
  assert.ok(dag26);
  assert.equal(dag26.kcal, 940);
});

console.log(`\n${ok} tester ok`);
