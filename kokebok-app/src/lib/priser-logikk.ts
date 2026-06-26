import type { Prispost } from "./priser.ts";

export function prisForIngrediens(navn: string, poster: Prispost[]): Prispost | null {
  const søk = navn.toLowerCase();
  // Eksakt match (case-insensitiv), nyeste dato vinner
  const eksakte = poster.filter(p => p.ingrediens.toLowerCase() === søk);
  if (eksakte.length > 0) return eksakte.sort((a, b) => b.dato.localeCompare(a.dato))[0];
  // Substring match
  const sub = poster.filter(p => p.ingrediens.toLowerCase().includes(søk));
  if (sub.length > 0) return sub.sort((a, b) => b.dato.localeCompare(a.dato))[0];
  return null;
}

export function prisHistorikk(navn: string, poster: Prispost[]): Prispost[] {
  const søk = navn.toLowerCase();
  return poster
    .filter(p => p.ingrediens.toLowerCase() === søk)
    .sort((a, b) => a.dato.localeCompare(b.dato));
}

export function unike_ingredienser(poster: Prispost[]): string[] {
  const sett = new Set(poster.map(p => p.ingrediens.toLowerCase()));
  return [...sett].sort();
}
