// Ren, node-testbar logikk for oppskriftsversjonering (ingen Tauri-import).

export type KopiIngrediens = {
  gruppe: string | null;
  mengde: number | null;
  enhet: string | null;
  navn: string | null;
  sortering: number;
};

export type KopiTrinn = {
  nummer: number;
  tekst: string;
};

export type OppskriftKopi = {
  navn: string;
  beskrivelse: string | null;
  porsjoner: number | null;
  tid: string | null;
  ingredienser: KopiIngrediens[];
  trinn: KopiTrinn[];
};

export type OppskriftEntry = {
  kladd: OppskriftKopi | null;
  historikk: VersjonSnapshot[];
};

export type VersjonSnapshot = {
  id: string;
  lagretTidspunkt: string;
  label: string;
  kopi: OppskriftKopi;
};

export type IngrediensDiff = {
  orig: KopiIngrediens | null;
  versjon: KopiIngrediens | null;
  endret: boolean;
};

export type TrinnDiff = {
  orig: KopiTrinn | null;
  versjon: KopiTrinn | null;
  endret: boolean;
};

export type OppskriftDiff = {
  navn: { orig: string; versjon: string; endret: boolean };
  beskrivelse: { orig: string | null; versjon: string | null; endret: boolean };
  porsjoner: { orig: number | null; versjon: number | null; endret: boolean };
  tid: { orig: string | null; versjon: string | null; endret: boolean };
  ingredienser: IngrediensDiff[];
  trinn: TrinnDiff[];
};

// Raw-type: hva hent_oppskrift returnerer (subset vi bruker).
export type OppskriftRaw = {
  navn: string;
  beskrivelse?: string | null;
  porsjoner?: number | null;
  tid?: string | null;
  ingredienser?: Array<{
    gruppe?: string | null;
    mengde?: number | null;
    enhet?: string | null;
    navn?: string | null;
    sortering?: number;
  }>;
  trinn?: Array<{ nummer: number; tekst: string }>;
};

/** Bygg OppskriftKopi fra et oppskrift-objekt returnert av hent_oppskrift. */
export function kopiFraOppskrift(opp: OppskriftRaw): OppskriftKopi {
  return {
    navn: opp.navn,
    beskrivelse: opp.beskrivelse ?? null,
    porsjoner: opp.porsjoner ?? null,
    tid: opp.tid ?? null,
    ingredienser: (opp.ingredienser ?? []).map((i, idx) => ({
      gruppe: i.gruppe ?? null,
      mengde: i.mengde ?? null,
      enhet: i.enhet ?? null,
      navn: i.navn ?? null,
      sortering: i.sortering ?? idx,
    })),
    trinn: (opp.trinn ?? []).map((t) => ({ nummer: t.nummer, tekst: t.tekst })),
  };
}

/** Beregn strukturell diff mellom to OppskriftKopi. */
export function beregnDiff(orig: OppskriftKopi, versjon: OppskriftKopi): OppskriftDiff {
  // Ingrediensdiff: match på indeks (posisjonell sammenligning)
  const maxIng = Math.max(orig.ingredienser.length, versjon.ingredienser.length);
  const ingredienser: IngrediensDiff[] = [];
  for (let i = 0; i < maxIng; i++) {
    const o = orig.ingredienser[i] ?? null;
    const v = versjon.ingredienser[i] ?? null;
    const endret =
      o === null || v === null ||
      o.navn !== v.navn || o.mengde !== v.mengde ||
      o.enhet !== v.enhet || o.gruppe !== v.gruppe;
    ingredienser.push({ orig: o, versjon: v, endret });
  }

  // Trinndiff: match på indeks
  const maxTrinn = Math.max(orig.trinn.length, versjon.trinn.length);
  const trinn: TrinnDiff[] = [];
  for (let i = 0; i < maxTrinn; i++) {
    const o = orig.trinn[i] ?? null;
    const v = versjon.trinn[i] ?? null;
    const endret = o === null || v === null || o.tekst !== v.tekst;
    trinn.push({ orig: o, versjon: v, endret });
  }

  return {
    navn: { orig: orig.navn, versjon: versjon.navn, endret: orig.navn !== versjon.navn },
    beskrivelse: { orig: orig.beskrivelse, versjon: versjon.beskrivelse, endret: orig.beskrivelse !== versjon.beskrivelse },
    porsjoner: { orig: orig.porsjoner, versjon: versjon.porsjoner, endret: orig.porsjoner !== versjon.porsjoner },
    tid: { orig: orig.tid, versjon: versjon.tid, endret: orig.tid !== versjon.tid },
    ingredienser,
    trinn,
  };
}
