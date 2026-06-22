// Kokebok – Tauri backend (rusqlite). Porter IPC-handlerne fra den gamle
// Electron-appens main.js til Rust-kommandoer.

use rusqlite::{Connection, OpenFlags};
use serde::Serialize;
use serde_json::{Map, Value};
use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

// ─── DB-tilkobling ────────────────────────────────────────────────────────────
fn db_path(app: &AppHandle) -> Result<PathBuf, String> {
    // Portabel modus: kokt.db ligger ved siden av selve exe-en. Prøves først så
    // en portabel mappe (exe + kokt.db) vinner over en evt. resource-pakket DB.
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let p = dir.join("kokt.db");
            if p.exists() {
                return Ok(p);
            }
        }
    }
    // NSIS-installert: kokt.db pakkes til resource-dir.
    if let Ok(p) = app
        .path()
        .resolve("kokt.db", tauri::path::BaseDirectory::Resource)
    {
        if p.exists() {
            return Ok(p);
        }
    }
    // Dev: kokt.db i prosjektets data-katalog.
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    for cand in [
        cwd.join("data").join("kokt.db"),
        cwd.join("src-tauri").join("data").join("kokt.db"),
    ] {
        if cand.exists() {
            return Ok(cand);
        }
    }
    Err("Fant ikke kokt.db".into())
}

fn open(app: &AppHandle) -> Result<Connection, String> {
    let p = db_path(app)?;
    Connection::open_with_flags(&p, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| format!("Klarte ikke åpne database: {e}"))
}

// Kjør en SELECT og returner rader som JSON-objekter (kolonnenavn → verdi).
fn query_json(
    conn: &Connection,
    sql: &str,
    params: &[&dyn rusqlite::ToSql],
) -> Result<Vec<Value>, String> {
    let mut stmt = conn.prepare(sql).map_err(|e| e.to_string())?;
    let col_names: Vec<String> = stmt.column_names().iter().map(|s| s.to_string()).collect();
    let n = col_names.len();

    let rows = stmt
        .query_map(params, |row| {
            let mut obj = Map::new();
            for i in 0..n {
                let v = match row.get_ref(i)? {
                    rusqlite::types::ValueRef::Null => Value::Null,
                    rusqlite::types::ValueRef::Integer(x) => Value::from(x),
                    rusqlite::types::ValueRef::Real(x) => Value::from(x),
                    rusqlite::types::ValueRef::Text(t) => {
                        Value::from(String::from_utf8_lossy(t).into_owned())
                    }
                    rusqlite::types::ValueRef::Blob(_) => Value::Null,
                };
                obj.insert(col_names[i].clone(), v);
            }
            Ok(Value::Object(obj))
        })
        .map_err(|e| e.to_string())?;

    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(|e| e.to_string())?);
    }
    Ok(out)
}

// ─── Kosthold/allergi-filtre ────────────────────────────────────────────────────
// Filter-ID → tagger det ekskluderer. Delt av hent_oppskrifter OG get_kategorier
// (én kilde, må matche frontend DIETT_FILTRE + scripts/tagg_ingredienser.py).
fn tagger_for(filter_id: &str) -> &'static [&'static str] {
    match filter_id {
        "halal"      => &["svin", "alkohol", "blod", "gelatin"],
        // Vegetar/vegansk ekskluderer også blod (blodpudding) og gelatin
        // (animalsk kollagen) — ingen av delene er vegetarisk.
        "vegetar"    => &["kjott", "fisk", "blod", "gelatin"],
        "vegansk"    => &["kjott", "fisk", "egg", "melk", "blod", "gelatin", "honning"],
        "glutenfri"  => &["gluten"],
        "laktosefri" => &["melk"],
        "nott"       => &["nott"],
        _            => &[],
    }
}

// Kjøtt/fisk-kategorier: oppskrifter med disse `type`-verdiene er iboende
// kjøtt/fisk uansett hvordan ingrediensene er navngitt (fanger «côte de boeuf»,
// «tomahawk» o.l. som nøkkelord aldri dekker). Brukes som ekstra ekskludering
// for vegetar/vegansk. For vegetar spiller kjøtt-vs-fisk ingen rolle (begge
// ekskluderes), så «Hele fileter» (fisk eller kjøtt) er trygg å ta med.
fn kjott_fisk_kategorier() -> &'static [&'static str] {
    &[
        "Biffer",
        "Steker",
        "Koteletter",
        "Kyllingfilet",
        "Kjøttdeig- og farseretter",
        "Grillet kylling",
        "Hele fileter",
    ]
}

// Bygg NOT EXISTS-betingelser + parametre for aktive diettfiltre. Skriver
// betingelses-SQL til `sql_ut` (eies av kaller) og tagg-parametre til `owned`.
// `alias` er oppskrift-tabellens alias i ytre spørring (f.eks. "o" eller "").
fn bygg_diett_filter(
    conn: &Connection,
    dietter: &Option<Vec<String>>,
    opp_ref: &str,
    sql_ut: &mut Vec<String>,
    owned: &mut Vec<String>,
) {
    let har_tabell: bool = conn
        .query_row(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ingrediens_tagg'",
            [],
            |_| Ok(true),
        )
        .unwrap_or(false);
    if !har_tabell {
        return;
    }
    if let Some(ds) = dietter.as_ref() {
        for id in ds {
            let tagger = tagger_for(id);
            if tagger.is_empty() {
                continue;
            }
            let placeholders = tagger.iter().map(|_| "?").collect::<Vec<_>>().join(", ");
            // Eksakt streng-join på samme kolonne (ingrediens_tagg.navn lagret RÅTT).
            let mut klausul = format!(
                "NOT EXISTS (SELECT 1 FROM ingredienser i \
                 JOIN ingrediens_tagg t ON t.navn = i.navn \
                 WHERE i.oppskrift_id = {opp_ref}.id AND t.tagg IN ({placeholders}))"
            );
            for tg in tagger {
                owned.push((*tg).to_string());
            }
            // Kategori-signal: vegetar/vegansk (filtre som ekskluderer kjøtt/fisk)
            // skjuler også oppskrifter i kjøtt/fisk-kategorier, uansett ingrediens-
            // navn. Fanger eksotiske kutt («côte de boeuf») nøkkelord ikke dekker.
            if tagger.contains(&"kjott") {
                let kats = kjott_fisk_kategorier();
                let kat_ph = kats.iter().map(|_| "?").collect::<Vec<_>>().join(", ");
                klausul = format!("({klausul} AND {opp_ref}.type NOT IN ({kat_ph}))");
                for k in kats {
                    owned.push((*k).to_string());
                }
            }
            sql_ut.push(klausul);
        }
    }
}

// ─── Cook Mode: hold skjermen/maskinen våken (kryssplattform, best-effort) ──────
#[derive(Default)]
struct CookModeState {
    #[allow(dead_code)]
    cookie: std::sync::Mutex<Option<u32>>,
}

#[cfg(windows)]
fn sett_keep_awake(on: bool) {
    use windows_sys::Win32::System::Power::{
        SetThreadExecutionState, ES_CONTINUOUS, ES_DISPLAY_REQUIRED, ES_SYSTEM_REQUIRED,
    };
    unsafe {
        if on {
            SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED);
        } else {
            SetThreadExecutionState(ES_CONTINUOUS);
        }
    }
}

#[cfg(target_os = "linux")]
fn sett_keep_awake_linux(on: bool, state: &CookModeState) {
    let mut cookie = state.cookie.lock().unwrap();
    let conn = match zbus::blocking::Connection::session() {
        Ok(c) => c,
        Err(e) => { eprintln!("cook_mode: ingen sesjonsbuss: {e}"); return; }
    };
    let proxy = zbus::blocking::Proxy::new(
        &conn,
        "org.freedesktop.ScreenSaver",
        "/org/freedesktop/ScreenSaver",
        "org.freedesktop.ScreenSaver",
    );
    let proxy = match proxy { Ok(p) => p, Err(e) => { eprintln!("cook_mode: proxy-feil: {e}"); return; } };
    if on {
        if let Some(c) = cookie.take() {
            let _ = proxy.call_method("UnInhibit", &(c));
        }
        match proxy.call_method("Inhibit", &("kokt.nok", "Matlaging")) {
            Ok(reply) => { if let Ok(c) = reply.body().deserialize::<u32>() { *cookie = Some(c); } }
            Err(e) => eprintln!("cook_mode: Inhibit feilet: {e}"),
        }
    } else if let Some(c) = cookie.take() {
        let _ = proxy.call_method("UnInhibit", &(c));
    }
}

#[tauri::command]
fn cook_mode(
    #[allow(unused_variables)] app: AppHandle,
    on: bool,
) -> Result<(), String> {
    #[cfg(windows)]
    {
        sett_keep_awake(on);
    }
    #[cfg(target_os = "linux")]
    {
        let state = app.state::<CookModeState>();
        sett_keep_awake_linux(on, &state);
    }
    Ok(())
}

// ─── Kommando: kategorier ──────────────────────────────────────────────────────
#[tauri::command]
fn get_kategorier(app: AppHandle, dietter: Option<Vec<String>>) -> Result<Vec<Value>, String> {
    let conn = open(&app)?;

    // Diettfiltre påvirker tellingen: korrelert subquery mot ytre «oppskrifter o».
    let mut diett_sql: Vec<String> = Vec::new();
    let mut owned: Vec<String> = Vec::new();
    bygg_diett_filter(&conn, &dietter, "o", &mut diett_sql, &mut owned);

    let where_sql = if diett_sql.is_empty() {
        String::new()
    } else {
        format!("WHERE {}", diett_sql.join(" AND "))
    };
    let refs: Vec<&dyn rusqlite::ToSql> =
        owned.iter().map(|s| s as &dyn rusqlite::ToSql).collect();

    query_json(
        &conn,
        &format!(
            "SELECT o.type AS kategori, COUNT(*) AS antall
             FROM   oppskrifter o {where_sql}
             GROUP  BY o.type
             ORDER  BY o.type COLLATE NOCASE"
        ),
        refs.as_slice(),
    )
}

// ─── Kommando: paginert + filtrert liste ───────────────────────────────────────
#[derive(Serialize)]
struct ListeSvar {
    total: i64,
    oppskrifter: Vec<Value>,
    side: i64,
    #[serde(rename = "perSide")]
    per_side: i64,
}

#[tauri::command]
fn hent_oppskrifter(
    app: AppHandle,
    kategori: Option<String>,
    sok: Option<String>,
    side: Option<i64>,
    #[allow(non_snake_case)] perSide: Option<i64>,
    dietter: Option<Vec<String>>,
) -> Result<ListeSvar, String> {
    let conn = open(&app)?;
    let side = side.unwrap_or(1).max(1);
    let per_side = perSide.unwrap_or(24).clamp(1, 200);

    let mut conds: Vec<&str> = Vec::new();
    // Eier strengene for LIKE/kategori her, så referansene lever lenge nok.
    let mut owned: Vec<String> = Vec::new();
    // Eier de dynamiske diett-NOT EXISTS-strengene (samme grep som `owned`).
    let mut diett_sql: Vec<String> = Vec::new();

    if let Some(k) = kategori.as_ref() {
        if !k.is_empty() && k != "alle" {
            conds.push("o.type = ?");
            owned.push(k.clone());
        }
    }
    if let Some(s) = sok.as_ref() {
        let s = s.trim();
        if !s.is_empty() {
            conds.push(
                "(o.navn LIKE ? OR EXISTS (SELECT 1 FROM ingredienser i \
                 WHERE i.oppskrift_id = o.id AND i.navn LIKE ?))",
            );
            let like = format!("%{s}%");
            owned.push(like.clone());
            owned.push(like);
        }
    }

    // Kosthold/allergi-filtre (delt helper). Diett-tagg-parametre legges til
    // `owned` ETTER kategori/sok → posisjonelle `?` stemmer for COUNT og LIST.
    bygg_diett_filter(&conn, &dietter, "o", &mut diett_sql, &mut owned);
    for s in &diett_sql {
        conds.push(s.as_str());
    }

    let where_sql = if conds.is_empty() {
        String::new()
    } else {
        format!("WHERE {}", conds.join(" AND "))
    };
    let offset = (side - 1) * per_side;

    // Parametre for filter (kategori + evt. to LIKE).
    let filter_refs: Vec<&dyn rusqlite::ToSql> =
        owned.iter().map(|s| s as &dyn rusqlite::ToSql).collect();

    let count_sql = format!("SELECT COUNT(*) AS c FROM oppskrifter o {where_sql}");
    let total: i64 = conn
        .query_row(&count_sql, filter_refs.as_slice(), |r| r.get(0))
        .map_err(|e| e.to_string())?;

    let list_sql = format!(
        "SELECT o.id, o.slug, o.navn, o.type, o.porsjoner, o.tid, o.bilde
         FROM   oppskrifter o {where_sql}
         ORDER  BY o.navn COLLATE NOCASE
         LIMIT  ? OFFSET ?"
    );
    let mut list_refs: Vec<&dyn rusqlite::ToSql> = filter_refs.clone();
    list_refs.push(&per_side);
    list_refs.push(&offset);

    let oppskrifter = query_json(&conn, &list_sql, list_refs.as_slice())?;

    Ok(ListeSvar {
        total,
        oppskrifter,
        side,
        per_side,
    })
}

// ─── Kommando: full oppskrift ──────────────────────────────────────────────────
#[tauri::command]
fn hent_oppskrift(app: AppHandle, id: i64) -> Result<Option<Value>, String> {
    let conn = open(&app)?;

    // Eksplisitt kolonneliste (ikke SELECT *) for å unngå å materialisere
    // bilde_data-BLOB-en på hver detalj-åpning i release. Bilder hentes via
    // kbilde-protokollen, ikke herfra.
    let mut rows = query_json(
        &conn,
        "SELECT id, slug, navn, type, beskrivelse, porsjoner, tid, bilde, url, hentet
         FROM oppskrifter WHERE id = ?",
        &[&id],
    )?;
    if rows.is_empty() {
        return Ok(None);
    }
    let mut opp = rows.remove(0);
    let obj = opp.as_object_mut().unwrap();

    let ings = query_json(
        &conn,
        "SELECT gruppe, mengde, enhet, navn, raatekst, sortering
         FROM ingredienser WHERE oppskrift_id = ? ORDER BY gruppe, sortering",
        &[&id],
    )?;
    obj.insert("ingredienser".into(), Value::Array(ings));

    let trinn = query_json(
        &conn,
        "SELECT nummer, tekst FROM trinn WHERE oppskrift_id = ? ORDER BY nummer",
        &[&id],
    )?;
    obj.insert("trinn".into(), Value::Array(trinn));

    let kats = query_json(
        &conn,
        "SELECT kategori FROM kategorier WHERE oppskrift_id = ?",
        &[&id],
    )?;
    let kat_strs: Vec<Value> = kats
        .into_iter()
        .filter_map(|k| k.get("kategori").cloned())
        .collect();
    obj.insert("kategorier".into(), Value::Array(kat_strs));

    // Næring – samme enhet-konvertering som gamle main.js.
    let naering_sql = "
        SELECT
          ROUND(SUM(CASE i.enhet
            WHEN 'g'  THEN i.mengde        * COALESCE(n.energi_kcal,0)/100
            WHEN 'kg' THEN i.mengde*1000   * COALESCE(n.energi_kcal,0)/100
            WHEN 'dl' THEN i.mengde*100    * COALESCE(n.energi_kcal,0)/100
            WHEN 'l'  THEN i.mengde*1000   * COALESCE(n.energi_kcal,0)/100
            WHEN 'ml' THEN i.mengde        * COALESCE(n.energi_kcal,0)/100
            WHEN 'ss' THEN i.mengde*15     * COALESCE(n.energi_kcal,0)/100
            WHEN 'ts' THEN i.mengde*5      * COALESCE(n.energi_kcal,0)/100
            ELSE 0 END)) AS energi,
          ROUND(SUM(CASE i.enhet
            WHEN 'g'  THEN i.mengde        * COALESCE(n.protein_g,0)/100
            WHEN 'kg' THEN i.mengde*1000   * COALESCE(n.protein_g,0)/100
            WHEN 'dl' THEN i.mengde*100    * COALESCE(n.protein_g,0)/100
            WHEN 'l'  THEN i.mengde*1000   * COALESCE(n.protein_g,0)/100
            WHEN 'ml' THEN i.mengde        * COALESCE(n.protein_g,0)/100
            WHEN 'ss' THEN i.mengde*15     * COALESCE(n.protein_g,0)/100
            WHEN 'ts' THEN i.mengde*5      * COALESCE(n.protein_g,0)/100
            ELSE 0 END),1) AS protein,
          ROUND(SUM(CASE i.enhet
            WHEN 'g'  THEN i.mengde        * COALESCE(n.fett_g,0)/100
            WHEN 'kg' THEN i.mengde*1000   * COALESCE(n.fett_g,0)/100
            WHEN 'dl' THEN i.mengde*100    * COALESCE(n.fett_g,0)/100
            WHEN 'l'  THEN i.mengde*1000   * COALESCE(n.fett_g,0)/100
            WHEN 'ml' THEN i.mengde        * COALESCE(n.fett_g,0)/100
            WHEN 'ss' THEN i.mengde*15     * COALESCE(n.fett_g,0)/100
            WHEN 'ts' THEN i.mengde*5      * COALESCE(n.fett_g,0)/100
            ELSE 0 END),1) AS fett,
          ROUND(SUM(CASE i.enhet
            WHEN 'g'  THEN i.mengde        * COALESCE(n.karbohydrat_g,0)/100
            WHEN 'kg' THEN i.mengde*1000   * COALESCE(n.karbohydrat_g,0)/100
            WHEN 'dl' THEN i.mengde*100    * COALESCE(n.karbohydrat_g,0)/100
            WHEN 'l'  THEN i.mengde*1000   * COALESCE(n.karbohydrat_g,0)/100
            WHEN 'ml' THEN i.mengde        * COALESCE(n.karbohydrat_g,0)/100
            WHEN 'ss' THEN i.mengde*15     * COALESCE(n.karbohydrat_g,0)/100
            WHEN 'ts' THEN i.mengde*5      * COALESCE(n.karbohydrat_g,0)/100
            ELSE 0 END),1) AS karbohydrat,
          ROUND(SUM(CASE i.enhet
            WHEN 'g'  THEN i.mengde        * COALESCE(n.fiber_g,0)/100
            WHEN 'kg' THEN i.mengde*1000   * COALESCE(n.fiber_g,0)/100
            WHEN 'dl' THEN i.mengde*100    * COALESCE(n.fiber_g,0)/100
            WHEN 'ss' THEN i.mengde*15     * COALESCE(n.fiber_g,0)/100
            ELSE 0 END),1) AS fiber,
          COUNT(n.ingredient_navn) AS treff,
          COUNT(i.id)              AS totalt
        FROM      ingredienser i
        LEFT JOIN naering n
               ON LOWER(TRIM(i.navn)) = LOWER(TRIM(n.ingredient_navn))
        WHERE i.oppskrift_id = ?";

    let mut nrows = query_json(&conn, naering_sql, &[&id])?;
    let naering = match nrows.pop() {
        Some(nr) => {
            let energi = nr.get("energi").and_then(|v| v.as_f64()).unwrap_or(0.0);
            if energi > 0.0 {
                nr
            } else {
                Value::Null
            }
        }
        None => Value::Null,
    };
    obj.insert("naering".into(), naering);

    // ─── Pris-estimat ──────────────────────────────────────────────────────────
    // Beregn kostnad PER ingrediens i en subquery (`kostnad`), så aggregerer vi.
    // `kostnad` blir NULL når (a) ingen pris-rad matcher, ELLER (b) ingrediensens
    // enhet ikke passer pris-radens enhetsklasse (indre CASE → NULL). VIKTIG:
    // `priset` må telle bare rader der `kostnad` faktisk ble beregnet (IS NOT
    // NULL) — ikke bare join-treff — ellers blåses dekningstallet opp med
    // ingredienser som matchet men ikke kunne prises pga. enhets-mismatch.
    // Enhetsklasse + enhetspris er forhåndsberegnet av scripts/hent_priser.py;
    // konverteringen speiler ingrediens_basis i kassal.py.
    let pris_sql = "
        SELECT
          ROUND(SUM(kostnad), 2)                       AS totalt,
          COUNT(kostnad)                               AS priset,
          COUNT(*)                                     AS totalt_antall,
          MAX(oppdatert)                               AS oppdatert
        FROM (
          SELECT
            i.id,
            p.oppdatert AS oppdatert,
            (CASE p.enhetsklasse
               WHEN 'g' THEN (CASE i.enhet
                 WHEN 'g' THEN i.mengde      WHEN 'kg' THEN i.mengde*1000
                 WHEN 'hg' THEN i.mengde*100 WHEN 'ss' THEN i.mengde*15
                 WHEN 'ts' THEN i.mengde*5   WHEN 'klype' THEN i.mengde
                 WHEN 'never' THEN i.mengde*5 ELSE NULL END)
               WHEN 'ml' THEN (CASE i.enhet
                 WHEN 'ml' THEN i.mengde     WHEN 'dl' THEN i.mengde*100
                 WHEN 'l' THEN i.mengde*1000 WHEN 'cl' THEN i.mengde*10
                 ELSE NULL END)
               WHEN 'stk' THEN (CASE i.enhet
                 WHEN 'stk.' THEN i.mengde WHEN 'stk' THEN i.mengde
                 WHEN '' THEN i.mengde ELSE NULL END)
               ELSE NULL END
             * p.enhetspris) AS kostnad
          FROM ingredienser i
          LEFT JOIN priser p
                 ON LOWER(TRIM(i.navn)) = p.ingredient_navn
                AND p.enhetspris IS NOT NULL
          WHERE i.oppskrift_id = ?
        )";

    // Les porsjoner fra det allerede eksisterende `obj`-lånet (ikke fra `opp`).
    let porsjoner = obj
        .get("porsjoner")
        .and_then(|v| v.as_f64())
        .filter(|p| *p > 0.0)
        .unwrap_or(4.0);

    let mut prows = query_json(&conn, pris_sql, &[&id])?;
    let pris = match prows.pop() {
        Some(pr) => {
            let totalt = pr.get("totalt").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let priset = pr.get("priset").and_then(|v| v.as_i64()).unwrap_or(0);
            if totalt > 0.0 && priset > 0 {
                let mut m = pr.as_object().unwrap().clone();
                m.insert(
                    "per_porsjon".into(),
                    Value::from((totalt / porsjoner * 100.0).round() / 100.0),
                );
                Value::Object(m)
            } else {
                Value::Null
            }
        }
        None => Value::Null,
    };
    obj.insert("pris".into(), pris);

    Ok(Some(opp))
}

// ─── Kommando: oppskrifter etter id-liste (favoritter) ─────────────────────────
#[tauri::command]
fn hent_oppskrifter_by_ids(app: AppHandle, ids: Vec<i64>) -> Result<Vec<Value>, String> {
    if ids.is_empty() {
        return Ok(Vec::new());
    }
    let conn = open(&app)?;

    // Bygg "?,?,?,..." og eier id-ene som ToSql-referanser (samme mønster som
    // hent_oppskrifter sin owned/filter_refs).
    let placeholders = vec!["?"; ids.len()].join(",");
    let sql = format!(
        "SELECT id, slug, navn, type, porsjoner, tid, bilde
         FROM   oppskrifter
         WHERE  id IN ({placeholders})
         ORDER  BY navn COLLATE NOCASE"
    );
    let refs: Vec<&dyn rusqlite::ToSql> =
        ids.iter().map(|i| i as &dyn rusqlite::ToSql).collect();

    query_json(&conn, &sql, refs.as_slice())
}

// ─── Bildebytes: DB-BLOB (release) med fil-fallback (dev) ──────────────────────
fn bilde_bytes(app: &AppHandle, id: i64) -> Option<Vec<u8>> {
    let conn = open(app).ok()?;

    // Prøv BLOB fra DB. Kolonnen bilde_data finnes bare i den genererte
    // bundle-DB-en; i dev (sti-DB) finnes den ikke, da gir prepare() feil og vi
    // faller gjennom til fil-fallback.
    if let Ok(mut stmt) = conn.prepare("SELECT bilde_data FROM oppskrifter WHERE id = ?") {
        if let Ok(Some(bytes)) = stmt.query_row([id], |r| r.get::<_, Option<Vec<u8>>>(0)) {
            if !bytes.is_empty() {
                return Some(bytes);
            }
        }
    }

    // Fil-fallback: slå opp slug → les bilder/{slug}.webp fra disk.
    let slug: String = conn
        .query_row("SELECT slug FROM oppskrifter WHERE id = ?", [id], |r| r.get(0))
        .ok()?;
    for base in bilde_kataloger(app) {
        let sti = base.join(format!("{slug}.webp"));
        if let Ok(bytes) = fs::read(&sti) {
            return Some(bytes);
        }
    }
    None
}

// Mulige bilder/-kataloger (release-ressurs + dev-stier), samme mønster som db_path.
fn bilde_kataloger(app: &AppHandle) -> Vec<PathBuf> {
    let mut ut = Vec::new();
    if let Ok(p) = app
        .path()
        .resolve("bilder", tauri::path::BaseDirectory::Resource)
    {
        ut.push(p);
    }
    if let Ok(cwd) = std::env::current_dir() {
        ut.push(cwd.join("data").join("bilder"));
        ut.push(cwd.join("src-tauri").join("data").join("bilder"));
    }
    ut
}

// ─── Lager / «hva kan jeg lage» ─────────────────────────────────────────────────
// Staples = «har alltid», teller verken som dekket eller mangel.
// VIKTIG (verifisert mot DB): naken delstreng «mel» fanger «melk»/«karamell»/
// «marmelade» → forbudt. Vi bruker EKSAKT ord-match mot en utvidet staple-liste,
// pluss en trygg suffiks-sjekk KUN for «olje»/«salt»/«pepper» (disse tre har
// ingen melk-lignende kollisjon). «melk»/«melkesjokolade»/«eplemost» = IKKE staple.
fn er_staple(navn_lower: &str) -> bool {
    const STAPLE_ORD: &[&str] = &[
        "salt", "pepper", "vann", "sukker", "smør",
        "hvetemel", "rugmel", "sammalt", "semulegryn", "melis",
        "olje", "olivenolje", "rapsolje", "solsikkeolje", "maisolje", "frityrolje",
        "nøytral", "kvernet", "flaksalt", "havsalt", "grovsalt",
    ];
    let ord: Vec<&str> = navn_lower
        .split(|c: char| !c.is_alphabetic())
        .filter(|w| !w.is_empty())
        .collect();
    if ord.iter().any(|w| STAPLE_ORD.contains(w)) {
        return true;
    }
    // Trygge suffikser (sammensatt som ETT ord): «xolje»/«xsalt»/«xpepper».
    ord.iter().any(|w| {
        (w.ends_with("olje") || w.ends_with("salt") || w.ends_with("pepper")) && w.len() > 4
    })
}

#[tauri::command]
fn ingrediens_forslag(app: AppHandle, prefiks: String) -> Result<Vec<String>, String> {
    let p = prefiks.trim().to_lowercase();
    if p.len() < 2 {
        return Ok(vec![]);
    }
    let conn = open(&app)?;
    // Prioriter de som STARTER med prefikset, så de som inneholder det.
    let mut stmt = conn
        .prepare(
            "SELECT DISTINCT navn FROM ingredienser \
             WHERE navn IS NOT NULL AND LOWER(navn) LIKE ?1 \
             ORDER BY CASE WHEN LOWER(navn) LIKE ?2 THEN 0 ELSE 1 END, navn COLLATE NOCASE \
             LIMIT 10",
        )
        .map_err(|e| e.to_string())?;
    let inneholder = format!("%{p}%");
    let starter = format!("{p}%");
    let rader = stmt
        .query_map([&inneholder, &starter], |r| r.get::<_, String>(0))
        .map_err(|e| e.to_string())?;
    Ok(rader.filter_map(|r| r.ok()).collect())
}

#[derive(Serialize)]
struct Forslag {
    id: i64,
    navn: String,
    #[serde(rename = "type")]
    type_: Option<String>,
    bilde: Option<String>,
    totalt: i64,
    dekket: i64,
    mangler: Vec<String>,
}

#[tauri::command]
fn hva_kan_jeg_lage(app: AppHandle, varer: Vec<String>) -> Result<Vec<Forslag>, String> {
    let varer: Vec<String> = varer.iter().map(|v| v.trim().to_lowercase()).filter(|v| !v.is_empty()).collect();
    if varer.is_empty() {
        return Ok(vec![]);
    }
    let conn = open(&app)?;
    let mut stmt = conn
        .prepare(
            "SELECT o.id, o.navn, o.type, o.bilde, i.navn \
             FROM oppskrifter o JOIN ingredienser i ON i.oppskrift_id = o.id \
             WHERE i.navn IS NOT NULL AND i.navn != '' \
             ORDER BY o.id",
        )
        .map_err(|e| e.to_string())?;
    let rader = stmt
        .query_map([], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, Option<String>>(2)?,
                r.get::<_, Option<String>>(3)?,
                r.get::<_, String>(4)?,
            ))
        })
        .map_err(|e| e.to_string())?;

    let mut ut: Vec<Forslag> = Vec::new();
    let mut cur: Option<(i64, String, Option<String>, Option<String>)> = None;
    let mut totalt = 0i64;
    let mut dekket = 0i64;
    let mut mangler: Vec<String> = Vec::new();

    let dekkes = |ing_lower: &str| -> bool {
        varer.iter().any(|v| ing_lower.contains(v.as_str()) || v.contains(ing_lower))
    };
    macro_rules! flush {
        () => {
            if let Some((id, navn, typ, bilde)) = cur.take() {
                if dekket > 0 {
                    ut.push(Forslag { id, navn, type_: typ, bilde, totalt, dekket, mangler: std::mem::take(&mut mangler) });
                } else {
                    mangler.clear();
                }
                totalt = 0; dekket = 0;
            }
        };
    }

    for row in rader.filter_map(|r| r.ok()) {
        let (id, onavn, otype, obilde, inavn) = row;
        if cur.as_ref().map(|c| c.0) != Some(id) {
            flush!();
            cur = Some((id, onavn, otype, obilde));
        }
        let il = inavn.to_lowercase();
        if er_staple(&il) {
            continue;
        }
        totalt += 1;
        if dekkes(&il) {
            dekket += 1;
        } else {
            mangler.push(inavn);
        }
    }
    flush!();

    ut.sort_by(|a, b| {
        (a.totalt - a.dekket).cmp(&(b.totalt - b.dekket))
            .then(b.dekket.cmp(&a.dekket))
            .then(a.navn.to_lowercase().cmp(&b.navn.to_lowercase()))
    });
    ut.truncate(60);
    Ok(ut)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(CookModeState::default())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .register_uri_scheme_protocol("kbilde", |ctx, request| {
            // URL: kbilde://localhost/{id} (convertFileSrc lager plattform-riktig form).
            // Siste sti-segment er id-en.
            let path = request.uri().path();
            let id: Option<i64> = path.trim_matches('/').parse().ok();
            let app = ctx.app_handle();
            match id.and_then(|i| bilde_bytes(app, i)) {
                Some(bytes) => tauri::http::Response::builder()
                    .status(200)
                    .header(tauri::http::header::CONTENT_TYPE, "image/webp")
                    .body(bytes)
                    .unwrap(),
                None => tauri::http::Response::builder()
                    .status(404)
                    .body(Vec::new())
                    .unwrap(),
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_kategorier,
            hent_oppskrifter,
            hent_oppskrift,
            hent_oppskrifter_by_ids,
            cook_mode,
            ingrediens_forslag,
            hva_kan_jeg_lage
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
