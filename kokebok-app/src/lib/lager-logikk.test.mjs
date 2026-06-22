import { utlopsStatus } from "./lager-logikk.ts";
import assert from "node:assert";

let ok = 0;
function sjekk(n, f) { try { f(); ok++; console.log("  ok  " + n); }
  catch (e) { console.error("FAIL " + n + ": " + e.message); process.exitCode = 1; } }

const I = "2026-06-19"; // "idag" i testene
sjekk("null dato → null", () => assert.equal(utlopsStatus(null, I), null));
sjekk("i går → utgått", () => assert.equal(utlopsStatus("2026-06-18", I), "utgått"));
sjekk("i dag → snart", () => assert.equal(utlopsStatus("2026-06-19", I), "snart"));
sjekk("om 3 dager → snart (grense)", () => assert.equal(utlopsStatus("2026-06-22", I), "snart"));
sjekk("om 4 dager → ok", () => assert.equal(utlopsStatus("2026-06-23", I), "ok"));
sjekk("langt fram → ok", () => assert.equal(utlopsStatus("2026-12-01", I), "ok"));
sjekk("tom streng → null", () => assert.equal(utlopsStatus("", I), null));

console.log(`\n${ok} tester ok`);
