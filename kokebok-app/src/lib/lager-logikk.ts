// Ren, node-testbar logikk (ingen Tauri-import). Klassifiserer utløpsdato.
export type UtlopsStatus = "utgått" | "snart" | "ok" | null;

/** Status for en vares utløpsdato relativt til idag (begge ISO "YYYY-MM-DD").
 *  null hvis ingen dato. «snart» = utgår innen 3 dager (inkl. i dag/forbi-grense). */
export function utlopsStatus(utloper: string | null, idag: string): UtlopsStatus {
  if (!utloper) return null;
  const u = Date.parse(utloper + "T00:00:00");
  const d = Date.parse(idag + "T00:00:00");
  if (Number.isNaN(u) || Number.isNaN(d)) return null;
  const dager = Math.round((u - d) / 86_400_000);
  if (dager < 0) return "utgått";
  if (dager <= 3) return "snart";
  return "ok";
}
