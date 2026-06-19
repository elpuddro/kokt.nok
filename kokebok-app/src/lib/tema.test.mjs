// Frittstående test av tema-logikk. Kjør: node --experimental-strip-types tema.test.mjs
// (fra kokebok-app/src/lib/). Bruker kun Node-innebygd assert.
import assert from "node:assert";
import { paaskedag, gjeldendeTema, aktivtTema } from "./tema-logikk.ts";

function iso(d) { return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; }

// Computus — kjente påskedatoer
assert.equal(iso(paaskedag(2024)), "2024-03-31", "paaske 2024");
assert.equal(iso(paaskedag(2026)), "2026-04-05", "paaske 2026");
assert.equal(iso(paaskedag(2027)), "2027-03-28", "paaske 2027");

// gjeldendeTema — høytider og sesonger (måned er 0-indeksert i Date)
assert.equal(gjeldendeTema(new Date(2026, 9, 28)), "halloween", "28. okt");
assert.equal(gjeldendeTema(new Date(2026, 4, 17)), "17mai", "17. mai");
assert.equal(gjeldendeTema(new Date(2026, 10, 11)), "singles", "11. nov");
assert.equal(gjeldendeTema(new Date(2026, 1, 10)), "valentines", "10. feb");
assert.equal(gjeldendeTema(new Date(2026, 11, 24)), "vinter", "24. des");
assert.equal(gjeldendeTema(new Date(2026, 6, 15)), "sommer", "15. juli");
assert.equal(gjeldendeTema(new Date(2026, 3, 6)), "paske", "6. april 2026 (paaskeuke)");
assert.equal(gjeldendeTema(new Date(2026, 8, 15)), "host", "15. sept");

// aktivtTema — manuell overstyrer
assert.equal(aktivtTema({ modus: "manuell", tema: "dark" }, new Date(2026, 9, 28)), "dark", "manuell dark");
assert.equal(aktivtTema({ modus: "auto", tema: null }, new Date(2026, 9, 28)), "halloween", "auto -> halloween");
assert.equal(aktivtTema(null, new Date(2026, 6, 15)), "sommer", "null -> auto sommer");
assert.equal(aktivtTema({ modus: "manuell", tema: "tulle-id" }, new Date(2026, 6, 15)), "sommer", "ugyldig manuell -> auto");

console.log("ALLE TEMA-LOGIKK-TESTER OK");
