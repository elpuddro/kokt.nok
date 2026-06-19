// Ren, node-testbar logikk (ingen Tauri-import, som tema-logikk.ts). Finner
// tids-uttrykk i trinn-tekst og regner ut nedtellingslengde i sekunder.

export type TidTreff = {
  tekst: string;    // selve tall+enhet, f.eks. "20-30 minutter"
  start: number;    // indeks i kildeteksten (for klikkbar markering)
  slutt: number;
  sekunder: number;
};

const BRØK: Record<string, number> = { "¼": 0.25, "½": 0.5, "¾": 0.75 };

const MAKS_SEK = 24 * 3600; // forkast urimelige verdier (sannsynlig feilparsing)

// Et tall: heltall, evt. etterfulgt av unicode-brøk («1½»), ELLER bare brøk («½»),
// evt. intervall «a-b»/«a–b» (bindestrek eller em-dash). Tar ØVRE grense.
// Gruppe 1=første tall(heltall), 2=første brøk, 3=andre tall, 4=andre brøk.
const TALL = String.raw`(\d+)?([¼½¾])?(?:\s*[-–]\s*(\d+)?([¼½¾])?)?`;
const RE = new RegExp(TALL + String.raw`\s*(sekunder|sekund|sek|minutter|minutt|min|timer|time|t)\b`, "giu");

function tilTall(heltall?: string, brøk?: string): number | null {
  let v = 0;
  let har = false;
  if (heltall) { v += parseInt(heltall, 10); har = true; }
  if (brøk) { v += BRØK[brøk] ?? 0; har = true; }
  return har ? v : null;
}

function enhetMultiplikator(enhet: string): number {
  const e = enhet.toLowerCase();
  if (e.startsWith("sek")) return 1;
  if (e.startsWith("min")) return 60;
  return 3600; // time/timer/t
}

export function finnTider(tekst: string): TidTreff[] {
  if (!tekst) return [];
  const treff: TidTreff[] = [];
  for (const m of tekst.matchAll(RE)) {
    const [hel, brøk, hel2, brøk2, enhet] = [m[1], m[2], m[3], m[4], m[5]];
    const a = tilTall(hel, brøk);
    if (a === null) continue;            // ingen tallverdi → ikke et treff
    const b = tilTall(hel2, brøk2);
    const verdi = b !== null ? Math.max(a, b) : a;  // intervall → øvre grense
    const sekunder = Math.round(verdi * enhetMultiplikator(enhet));
    if (sekunder <= 0 || sekunder > MAKS_SEK) continue;
    treff.push({
      tekst: m[0].trim(),
      start: m.index,
      slutt: m.index + m[0].length,
      sekunder,
    });
  }
  return treff;
}
