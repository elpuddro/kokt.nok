// Ren, node-testbar logikk for matplanleggeren (ingen Tauri-import).
export type SlotType = "frokost" | "lunsj" | "middag" | "kveldsmat";

export type Slot =
  | { kind: "rett"; id: number; navn: string; kcal: number | null; laast: boolean }
  | { kind: "rester"; visTekst: string; laast: boolean }
  | { kind: "enkel"; visTekst: string; laast: boolean }
  | { kind: "tom"; grunn: string };

/** Andel av dagsmålet per slot. Summerer til 1.0. Middag tyngst. */
export const FORDELING: Record<SlotType, number> = {
  frokost: 0.20,
  lunsj: 0.25,
  middag: 0.40,
  kveldsmat: 0.15,
};

/** kcal-mål per slot ut fra dagsmål. */
export function slotMaal(dagsmaal: number): Record<SlotType, number> {
  return {
    frokost: Math.round(dagsmaal * FORDELING.frokost),
    lunsj: Math.round(dagsmaal * FORDELING.lunsj),
    middag: Math.round(dagsmaal * FORDELING.middag),
    kveldsmat: Math.round(dagsmaal * FORDELING.kveldsmat),
  };
}

/** Score en kandidat for en slot. Høyere = bedre.
 *  - nærhet til kcal-mål (mindre avvik = bedre)
 *  - variasjon: straff hvis rettens type alt er brukt denne uka
 *  - gjenbruk: bonus per råvare delt med alt valgte retter
 *  - jitter: liten tilfeldig spredning så to genereringer skiller seg. */
export function scoreKandidat(
  kand: { kcal: number | null; type: string; ingredienser: string[] },
  slotMaalKcal: number,
  bruktType: Set<string>,
  brukteIngredienser: Set<string>,
  jitter: number,
): number {
  let score = 100;
  // kcal-nærhet: trekk fra normalisert avvik (0 avvik → full pott).
  if (kand.kcal != null && slotMaalKcal > 0) {
    const avvik = Math.abs(kand.kcal - slotMaalKcal) / slotMaalKcal;
    score -= avvik * 60; // opptil -60 ved 100 % avvik
  } else {
    score -= 25; // ukjent kcal: moderat straff, men fortsatt valgbar
  }
  // variasjon: straff gjentatt type
  if (bruktType.has(kand.type)) score -= 30;
  // gjenbruk: bonus per delt råvare (tak 4 → +20)
  let delte = 0;
  for (const ing of kand.ingredienser) {
    if (brukteIngredienser.has(ing.toLowerCase())) delte++;
  }
  score += Math.min(delte, 4) * 5;
  // jitter
  score += jitter;
  return score;
}

/** Sum kcal for en dags slots. Bare kind:"rett" med tallverdi teller.
 *  null hvis ingen rett-slot har kcal. */
export function kcalForDag(slots: Slot[]): number | null {
  let sum = 0;
  let har = false;
  for (const s of slots) {
    if (s.kind === "rett" && typeof s.kcal === "number") {
      sum += s.kcal;
      har = true;
    }
  }
  return har ? sum : null;
}
