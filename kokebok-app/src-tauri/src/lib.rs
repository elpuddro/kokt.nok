// Kokebok – Tauri backend (rusqlite). Porter IPC-handlerne fra den gamle
// Electron-appens main.js til Rust-kommandoer.

use rusqlite::{Connection, OpenFlags};
use serde::{Serialize, Deserialize};
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

fn tid_til_min(s: &str) -> Option<i64> {
    let s = s.trim().to_lowercase();
    // "X time(r) Y min"
    if (s.contains("timer") || s.contains("time")) && s.contains("min") {
        let del = if s.contains("timer") { "timer" } else { "time" };
        let t: i64 = s.split(del).next()?.trim().parse().ok()?;
        let m: i64 = s.split(del).nth(1)?.replace("min", "").trim().parse().ok()?;
        return Some(t * 60 + m);
    }
    if s.ends_with("timer") {
        return s.replace("timer", "").trim().parse::<i64>().ok().map(|t| t * 60);
    }
    if s.ends_with("time") {
        return s.replace("time", "").trim().parse::<i64>().ok().map(|t| t * 60);
    }
    if s.ends_with("min") {
        return s.replace("min", "").trim().parse::<i64>().ok();
    }
    None
}

#[tauri::command]
fn hent_oppskrifter(
    app: AppHandle,
    kategori: Option<String>,
    sok: Option<String>,
    side: Option<i64>,
    #[allow(non_snake_case)] perSide: Option<i64>,
    dietter: Option<Vec<String>>,
    sorter: Option<String>,
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
        for ord in s.split_whitespace().take(5) {
            let like = format!("%{ord}%");
            owned.push(like.clone());
            owned.push(like);
            conds.push(
                "(o.navn LIKE ? OR EXISTS (SELECT 1 FROM ingredienser i \
                 WHERE i.oppskrift_id = o.id AND i.navn LIKE ?))",
            );
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

    let sorter_str = sorter.as_deref().unwrap_or("navn_asc");

    let oppskrifter = if sorter_str == "tid_asc" || sorter_str == "tid_desc" {
        // Tidssortering: hent alle filtrerte rader, sorter i Rust, paginer manuelt.
        let alle_sql = format!(
            "SELECT o.id, o.slug, o.navn, o.type, o.porsjoner, o.tid, o.bilde
             FROM   oppskrifter o {where_sql}"
        );
        let mut rader: Vec<serde_json::Value> =
            query_json(&conn, &alle_sql, filter_refs.as_slice())?;

        rader.sort_by(|a, b| {
            let ta = a["tid"].as_str().and_then(tid_til_min);
            let tb = b["tid"].as_str().and_then(tid_til_min);
            let by_tid = match (ta, tb) {
                (Some(x), Some(y)) => if sorter_str == "tid_asc" { x.cmp(&y) } else { y.cmp(&x) },
                (Some(_), None) => std::cmp::Ordering::Less,
                (None, Some(_)) => std::cmp::Ordering::Greater,
                (None, None) => std::cmp::Ordering::Equal,
            };
            by_tid.then_with(|| {
                let na = a["navn"].as_str().unwrap_or("").to_lowercase();
                let nb = b["navn"].as_str().unwrap_or("").to_lowercase();
                na.cmp(&nb)
            })
        });

        rader.into_iter()
            .skip(offset as usize)
            .take(per_side as usize)
            .collect()
    } else {
        let order = match sorter_str {
            "navn_desc" => "o.navn COLLATE NOCASE DESC",
            _           => "o.navn COLLATE NOCASE ASC",
        };
        let list_sql = format!(
            "SELECT o.id, o.slug, o.navn, o.type, o.porsjoner, o.tid, o.bilde
             FROM   oppskrifter o {where_sql}
             ORDER  BY {order}
             LIMIT  ? OFFSET ?"
        );
        let mut list_refs: Vec<&dyn rusqlite::ToSql> = filter_refs.clone();
        list_refs.push(&per_side);
        list_refs.push(&offset);
        query_json(&conn, &list_sql, list_refs.as_slice())?
    };

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
            "SELECT o.id, o.navn, o.type, i.navn \
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
                r.get::<_, String>(3)?,
            ))
        })
        .map_err(|e| e.to_string())?;

    let mut ut: Vec<Forslag> = Vec::new();
    let mut cur: Option<(i64, String, Option<String>)> = None;
    let mut totalt = 0i64;
    let mut dekket = 0i64;
    let mut mangler: Vec<String> = Vec::new();

    let dekkes = |ing_lower: &str| -> bool {
        varer.iter().any(|v| ing_lower.contains(v.as_str()) || v.contains(ing_lower))
    };
    macro_rules! flush {
        () => {
            if let Some((id, navn, typ)) = cur.take() {
                if dekket > 0 {
                    ut.push(Forslag { id, navn, type_: typ, totalt, dekket, mangler: std::mem::take(&mut mangler) });
                } else {
                    mangler.clear();
                }
                totalt = 0; dekket = 0;
            }
        };
    }

    for row in rader.filter_map(|r| r.ok()) {
        let (id, onavn, otype, inavn) = row;
        if cur.as_ref().map(|c| c.0) != Some(id) {
            flush!();
            cur = Some((id, onavn, otype));
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

// ─── Matplanlegger ──────────────────────────────────────────────────────────────
// Kuratert kategori→slot-mapping. En kategori kan høre til flere slots.
// Dessert/Kaker/Snacks/Koldtbord er bevisst utelatt fra alle måltids-slots.
fn slot_kategorier(slot: &str) -> &'static [&'static str] {
    match slot {
        "frokost" => &["Frokost", "Vafler/pannekaker", "Drikke", "Brød/bakverk"],
        "lunsj" => &[
            "Lunsj", "Sandwich/smørbrød", "Salater", "Supper",
            "Tapas/småretter", "Smårett", "Forrett", "Forretter",
        ],
        "middag" => &[
            "Middag", "Gryter", "Ovnsretter", "Pasta", "Pizza", "Biffer",
            "Koteletter", "Wok", "Kyllingfilet", "Hele fileter", "Steker",
            "Panneretter", "Kjøttdeig- og farseretter", "Grillspyd",
            "Grillet kylling", "Vegetar", "Turmat",
        ],
        // kveldsmat: bare ekte smørbrød/pålegg trekkes; faste enkle tekster i tillegg
        "kveldsmat" => &["Sandwich/smørbrød", "Pålegg"],
        _ => &[],
    }
}

// Faste enkle kveldsmat-forslag (ikke oppskrifter).
const KVELDSMAT_ENKEL: &[&str] = &[
    "Brødskive med pålegg", "Ostesmørbrød", "Knekkebrød med pålegg",
    "Yoghurt med müsli", "Frukt og nøtter",
];

#[derive(Serialize, Clone)]
#[serde(tag = "kind")]
enum SlotSvar {
    #[serde(rename = "rett")]
    Rett { id: i64, navn: String, kcal: Option<f64>, laast: bool },
    #[serde(rename = "rester")]
    Rester { #[serde(rename = "visTekst")] vis_tekst: String, laast: bool },
    #[serde(rename = "enkel")]
    Enkel { #[serde(rename = "visTekst")] vis_tekst: String, laast: bool },
    #[serde(rename = "tom")]
    Tom { grunn: String },
}

#[derive(Serialize)]
struct DagSvar {
    frokost: SlotSvar,
    lunsj: SlotSvar,
    middag: SlotSvar,
    kveldsmat: SlotSvar,
    #[serde(rename = "kcalDag")]
    kcal_dag: Option<f64>,
}

#[derive(Serialize)]
struct UkeSvar {
    dager: Vec<DagSvar>,
    dagsmaal: i64,
    personer: i64,
    generert: String,
}

#[derive(Deserialize)]
struct LaastSlot {
    dag: usize,
    slot: String,
    id: i64,
}

// En kandidat-rett for en slot, med on-demand kcal/porsjon og ingrediensnavn.
struct Kandidat {
    id: i64,
    navn: String,
    type_: String,
    kcal: Option<f64>,
    fett: Option<f64>,
    ingredienser: Vec<String>,
    hoytid: Option<String>,
}

// Hent kvalifiserte kandidater for én slot: mapper til slot + passer diett-filtre.
fn kandidater_for_slot(
    conn: &Connection,
    slot: &str,
    dietter: &Option<Vec<String>>,
) -> Vec<Kandidat> {
    let kats = slot_kategorier(slot);
    if kats.is_empty() {
        return vec![];
    }
    let kat_ph = kats.iter().map(|_| "?").collect::<Vec<_>>().join(", ");

    // Diett-klausuler (gjenbruk eksisterende helper, opp_ref = "o").
    let mut diett_sql: Vec<String> = Vec::new();
    let mut owned: Vec<String> = Vec::new();
    for k in kats {
        owned.push((*k).to_string());
    }
    bygg_diett_filter(conn, dietter, "o", &mut diett_sql, &mut owned);
    let diett_where = if diett_sql.is_empty() {
        String::new()
    } else {
        format!(" AND {}", diett_sql.join(" AND "))
    };

    let sql = format!(
        "SELECT o.id, o.navn, o.type, o.hoytid FROM oppskrifter o \
         WHERE o.type IN ({kat_ph}){diett_where} LIMIT 400"
    );
    let refs: Vec<&dyn rusqlite::ToSql> =
        owned.iter().map(|s| s as &dyn rusqlite::ToSql).collect();

    let mut stmt = match conn.prepare(&sql) {
        Ok(s) => s,
        Err(_) => return vec![],
    };
    let rader = stmt.query_map(refs.as_slice(), |r| {
        Ok((r.get::<_, i64>(0)?, r.get::<_, String>(1)?, r.get::<_, String>(2)?, r.get::<_, Option<String>>(3)?))
    });
    let rader = match rader {
        Ok(r) => r,
        Err(_) => return vec![],
    };

    // Samle alle kandidater først (ID, navn, type, hoytid).
    let mut basis: Vec<(i64, String, String, Option<String>)> = Vec::new();
    for row in rader.filter_map(|r| r.ok()) {
        basis.push(row);
    }
    if basis.is_empty() {
        return vec![];
    }

    // Bulk-hent kcal, fett og porsjoner for alle kandidater i én query.
    let id_ph = basis.iter().map(|_| "?").collect::<Vec<_>>().join(", ");
    let ids: Vec<i64> = basis.iter().map(|(id, _, _, _)| *id).collect();
    let id_refs: Vec<&dyn rusqlite::ToSql> = ids.iter().map(|id| id as &dyn rusqlite::ToSql).collect();

    let naering_sql = format!(
        "SELECT i.oppskrift_id,
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
             WHEN 'g'  THEN i.mengde        * COALESCE(n.fett_g,0)/100
             WHEN 'kg' THEN i.mengde*1000   * COALESCE(n.fett_g,0)/100
             WHEN 'dl' THEN i.mengde*100    * COALESCE(n.fett_g,0)/100
             WHEN 'l'  THEN i.mengde*1000   * COALESCE(n.fett_g,0)/100
             WHEN 'ml' THEN i.mengde        * COALESCE(n.fett_g,0)/100
             WHEN 'ss' THEN i.mengde*15     * COALESCE(n.fett_g,0)/100
             WHEN 'ts' THEN i.mengde*5      * COALESCE(n.fett_g,0)/100
             ELSE 0 END), 1) AS fett_total,
           COUNT(n.ingredient_navn) AS treff,
           o.porsjoner
         FROM ingredienser i
         LEFT JOIN naering n ON LOWER(TRIM(i.navn)) = LOWER(TRIM(n.ingredient_navn))
         JOIN oppskrifter o ON o.id = i.oppskrift_id
         WHERE i.oppskrift_id IN ({id_ph})
         GROUP BY i.oppskrift_id"
    );
    let mut kcal_map: std::collections::HashMap<i64, Option<f64>> = std::collections::HashMap::new();
    let mut fett_map: std::collections::HashMap<i64, Option<f64>> = std::collections::HashMap::new();
    if let Ok(mut stmt) = conn.prepare(&naering_sql) {
        if let Ok(rows) = stmt.query_map(id_refs.as_slice(), |r| {
            Ok((r.get::<_, i64>(0)?, r.get::<_, Option<f64>>(1)?, r.get::<_, Option<f64>>(2)?, r.get::<_, i64>(3)?, r.get::<_, Option<f64>>(4)?))
        }) {
            for row in rows.filter_map(|r| r.ok()) {
                let (opp_id, energi, fett_total, treff, porsjoner) = row;
                let p = porsjoner.filter(|&p| p > 0.0).unwrap_or(4.0);
                let kcal = if treff > 0 {
                    energi.filter(|&e| e > 0.0).map(|e| (e / p * 10.0).round() / 10.0)
                } else {
                    None
                };
                let fett = if treff > 0 {
                    fett_total.filter(|&f| f > 0.0).map(|f| (f / p * 10.0).round() / 10.0)
                } else {
                    None
                };
                kcal_map.insert(opp_id, kcal);
                fett_map.insert(opp_id, fett);
            }
        }
    }

    // Bulk-hent ingrediensnavn for alle kandidater i én query.
    let ing_sql = format!(
        "SELECT oppskrift_id, LOWER(navn) FROM ingredienser \
         WHERE oppskrift_id IN ({id_ph}) AND navn IS NOT NULL"
    );
    let mut ing_map: std::collections::HashMap<i64, Vec<String>> = std::collections::HashMap::new();
    if let Ok(mut stmt) = conn.prepare(&ing_sql) {
        if let Ok(rows) = stmt.query_map(id_refs.as_slice(), |r| {
            Ok((r.get::<_, i64>(0)?, r.get::<_, String>(1)?))
        }) {
            for row in rows.filter_map(|r| r.ok()) {
                let (opp_id, navn) = row;
                ing_map.entry(opp_id).or_default().push(navn);
            }
        }
    }

    basis.into_iter().map(|(id, navn, type_, hoytid)| {
        let kcal = kcal_map.get(&id).copied().flatten();
        let fett = fett_map.get(&id).copied().flatten();
        let ingredienser = ing_map.remove(&id).unwrap_or_default();
        Kandidat { id, navn, type_, kcal, fett, ingredienser, hoytid }
    }).collect()
}

// Score (samme formel som matplan-logikk.ts scoreKandidat, jitter via indeks).
fn score(
    k: &Kandidat,
    maal: f64,
    brukt_type: &std::collections::HashSet<String>,
    brukte_ing: &std::collections::HashSet<String>,
    jitter: f64,
) -> f64 {
    let mut s = 100.0;
    match k.kcal {
        Some(kc) if maal > 0.0 => s -= (kc - maal).abs() / maal * 60.0,
        _ => s -= 25.0,
    }
    if brukt_type.contains(&k.type_) {
        s -= 30.0;
    }
    let delte = k.ingredienser.iter().filter(|i| brukte_ing.contains(*i)).count();
    s += (delte.min(4) as f64) * 5.0;
    s + jitter
}

// Minimal xorshift64 PRNG — ingen ekstern crate nødvendig.
fn xorshift64(state: &mut u64) -> u64 {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    *state
}

fn shuffle<T>(v: &mut Vec<T>, rng: &mut u64) {
    let n = v.len();
    for i in (1..n).rev() {
        let j = (xorshift64(rng) as usize) % (i + 1);
        v.swap(i, j);
    }
}

#[tauri::command]
fn generer_matplan(
    app: AppHandle,
    dagsmaal: i64,
    personer: i64,
    dietter: Option<Vec<String>>,
    laaste: Vec<LaastSlot>,
    #[allow(non_snake_case)] sunnPlan: bool,
    hoytid: Option<String>,
) -> Result<UkeSvar, String> {
    use std::collections::HashSet;
    let conn = open(&app)?;
    let dagsmaal = dagsmaal.max(0);
    let maal = |slot: &str| -> f64 {
        let andel = match slot {
            "frokost" => 0.20, "lunsj" => 0.25, "middag" => 0.40, "kveldsmat" => 0.15,
            _ => 0.0,
        };
        dagsmaal as f64 * andel
    };

    // Seed fra nåtid — ny for hvert kall, garanterer ulike resultater.
    let seed_ns = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(12345);
    let mut rng: u64 = seed_ns | 1; // xorshift64 krever non-zero seed

    // Forhåndshent og shuffle kandidater per slot — ett DB-kall per slot-type.
    let mut kand_frokost = kandidater_for_slot(&conn, "frokost", &dietter);
    let mut kand_lunsj = kandidater_for_slot(&conn, "lunsj", &dietter);
    let mut kand_middag = kandidater_for_slot(&conn, "middag", &dietter);
    let mut kand_kveld = kandidater_for_slot(&conn, "kveldsmat", &dietter);
    shuffle(&mut kand_frokost, &mut rng);
    shuffle(&mut kand_lunsj, &mut rng);
    shuffle(&mut kand_middag, &mut rng);
    shuffle(&mut kand_kveld, &mut rng);

    let mut brukt_type: HashSet<String> = HashSet::new();
    let mut brukte_ing: HashSet<String> = HashSet::new();
    let mut brukt_id: HashSet<i64> = HashSet::new();

    // Velg beste ledige kandidat for en slot; respekter lås.
    let velg = |kandidater: &[Kandidat],
                    slot: &str,
                    dag: usize,
                    teller: f64,
                    bt: &mut HashSet<String>,
                    bi: &mut HashSet<String>,
                    bid: &mut HashSet<i64>| -> SlotSvar {
        // Lås? Finn den låste retten blant kandidatene (eller behold som rett uansett).
        if let Some(l) = laaste.iter().find(|l| l.dag == dag && l.slot == slot) {
            if let Some(k) = kandidater.iter().find(|k| k.id == l.id) {
                bt.insert(k.type_.clone());
                for i in &k.ingredienser { bi.insert(i.clone()); }
                bid.insert(k.id);
                return SlotSvar::Rett { id: k.id, navn: k.navn.clone(), kcal: k.kcal, laast: true };
            }
        }
        let m = maal(slot);
        let mut best: Option<&Kandidat> = None;
        let mut best_s = f64::NEG_INFINITY;
        for (i, k) in kandidater.iter().enumerate() {
            if bid.contains(&k.id) { continue; }
            // Jitter er nå posisjon i den shufflede lista (unik per kall) + id-hash.
            let jitter = ((i as f64 * 0.137 + k.id as f64 * 2.399_963 + teller) % 1.0) * 10.0;
            let mut s = score(k, m, bt, bi, jitter);
            if sunnPlan && s > 0.0 {
                if k.kcal.map_or(false, |kc| kc > 600.0) {
                    s *= 0.5;
                }
                if let (Some(kc), Some(ft)) = (k.kcal, k.fett) {
                    if kc > 0.0 && (ft * 9.0 / kc) > 0.35 {
                        s *= 0.7;
                    }
                }
            }
            // Sesong-bonus: +50 for høytidsmerket rett
            if let Some(ref h) = hoytid {
                if let Some(ref opp_hoytid) = k.hoytid {
                    if opp_hoytid.split(',').any(|t| t.trim() == h.as_str()) {
                        s += 50.0;
                    }
                }
            }
            if s > best_s { best_s = s; best = Some(k); }
        }
        match best {
            Some(k) => {
                bt.insert(k.type_.clone());
                for i in &k.ingredienser { bi.insert(i.clone()); }
                bid.insert(k.id);
                SlotSvar::Rett { id: k.id, navn: k.navn.clone(), kcal: k.kcal, laast: false }
            }
            None => SlotSvar::Tom { grunn: "Ingen passende rett — juster filtre".into() },
        }
    };

    let mut dager: Vec<DagSvar> = Vec::with_capacity(7);
    let mut forrige_middag_navn: Option<String> = None;

    for dag in 0..7usize {
        let frokost = velg(&kand_frokost, "frokost", dag, dag as f64, &mut brukt_type, &mut brukte_ing, &mut brukt_id);

        // Lunsj: annenhver dag (1,3,5) = rester av forrige middag hvis den finnes.
        let lunsj = if dag % 2 == 1 {
            if let Some(navn) = &forrige_middag_navn {
                SlotSvar::Rester { vis_tekst: format!("Rester: {navn}"), laast: false }
            } else {
                velg(&kand_lunsj, "lunsj", dag, dag as f64 + 0.5, &mut brukt_type, &mut brukte_ing, &mut brukt_id)
            }
        } else {
            velg(&kand_lunsj, "lunsj", dag, dag as f64 + 0.5, &mut brukt_type, &mut brukte_ing, &mut brukt_id)
        };

        let middag = velg(&kand_middag, "middag", dag, dag as f64 + 0.25, &mut brukt_type, &mut brukte_ing, &mut brukt_id);
        if let SlotSvar::Rett { navn, .. } = &middag {
            forrige_middag_navn = Some(navn.clone());
        }

        // Kveldsmat: prøv ekte smørbrød/pålegg-rett, ellers fast enkel tekst.
        let kveldsmat = {
            // 60 % av dagene: enkel fast tekst (matcher «1-2 skiver»-vanen); ellers rett.
            if dag % 5 == 2 && !kand_kveld.is_empty() {
                velg(&kand_kveld, "kveldsmat", dag, dag as f64 + 0.75, &mut brukt_type, &mut brukte_ing, &mut brukt_id)
            } else {
                let idx = dag % KVELDSMAT_ENKEL.len();
                SlotSvar::Enkel { vis_tekst: KVELDSMAT_ENKEL[idx].to_string(), laast: false }
            }
        };

        // kcal/dag: sum av rett-slots med kjent kcal.
        let mut kcal_sum = 0.0;
        let mut har = false;
        for s in [&frokost, &lunsj, &middag, &kveldsmat] {
            if let SlotSvar::Rett { kcal: Some(k), .. } = s { kcal_sum += k; har = true; }
        }
        let kcal_dag = if har { Some((kcal_sum * 10.0).round() / 10.0) } else { None };

        dager.push(DagSvar { frokost, lunsj, middag, kveldsmat, kcal_dag });
    }

    Ok(UkeSvar {
        dager,
        dagsmaal,
        personer: personer.max(1),
        generert: chrono_now(),
    })
}

// Enkel ISO-tidsstempel uten ekstra avhengighet.
fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
    format!("{secs}")
}

// ─── About-info (kun hjemmebygg) ──────────────────────────────────────────────
#[cfg(feature = "about")]
#[derive(serde::Serialize)]
struct AboutInfo {
    navn: &'static str,
    epost: &'static str,
    versjon: &'static str,
    beskrivelse: &'static str,
}

#[cfg(feature = "about")]
#[tauri::command]
fn about_info() -> AboutInfo {
    AboutInfo {
        navn: "Frank Simonsen",
        epost: "elpuddro@gmail.com",
        versjon: env!("CARGO_PKG_VERSION"),
        beskrivelse: "Kokebok er en offline basert oppskriftssamling for Windows og Linux. \
            Appen inneholder over 5 900 norske oppskrifter fra matprat.no og godt.no, \
            med næringsinfo fra Matvaretabellen, smarte funksjoner som ukesmenyplanlegger, \
            handleliste, kjøleskapsstyring og kostholdsfiltre med mere.",
    }
}

#[cfg(not(feature = "about"))]
#[tauri::command]
fn about_info() -> Option<()> { None }

// ─── Høytidsdeteksjon ────────────────────────────────────────────────────────

// Beregn 1. påskedag for ett år via Gauss/Computus-algoritmen.
// Returnerer (måned, dag): (3, X) for mars, (4, X) for april.
fn paaskedag(aar: i32) -> (u32, u32) {
    let a = (aar % 19) as u32;
    let b = (aar / 100) as u32;
    let c = (aar % 100) as u32;
    let d = b / 4;
    let e = b % 4;
    let f = (b + 8) / 25;
    let g = (b - f + 1) / 3;
    let h = (19 * a + b - d - g + 15) % 30;
    let i = c / 4;
    let k = c % 4;
    let l = (32 + 2 * e + 2 * i - h - k) % 7;
    let m = (a + 11 * h + 22 * l) / 451;
    let maaned = (h + l - 7 * m + 114) / 31;
    let dag = ((h + l - 7 * m + 114) % 31) + 1;
    (maaned, dag)
}

// Gitt dato (1-indeksert måned, dag, ISO ukedag 1=man..7=søn, år),
// returner gjeldende høytidsnøkkel eller None.
fn hoytid_aktiv_dato(maaned: u32, dag: u32, _ukedag: u32, aar: i32) -> Option<String> {
    // Valentinsdag: feb 7–14
    if maaned == 2 && dag >= 7 && dag <= 14 {
        return Some("valentins".into());
    }

    // Påske: palmesøndag (påske−7 dager) → 2. påskedag (påske+1 dag)
    let (p_mnd, p_dag) = paaskedag(aar);
    // Konverter til dagnummer i år for enkel ± beregning
    let dager_i_mnd = |m: u32, y: i32| -> u32 {
        match m {
            1|3|5|7|8|10|12 => 31,
            4|6|9|11 => 30,
            2 => if y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) { 29 } else { 28 },
            _ => 30,
        }
    };
    let til_dagsnr = |m: u32, d: u32| -> i32 {
        let mut n: i32 = d as i32;
        for mm in 1..m { n += dager_i_mnd(mm, aar) as i32; }
        n
    };
    let paske_nr = til_dagsnr(p_mnd, p_dag);
    let dato_nr  = til_dagsnr(maaned, dag);
    if dato_nr >= paske_nr - 7 && dato_nr <= paske_nr + 1 {
        return Some("paske".into());
    }

    // 17. mai: mai 10–18
    if maaned == 5 && dag >= 10 && dag <= 18 {
        return Some("mai17".into());
    }

    // Sankthans: jun 20–24
    if maaned == 6 && dag >= 20 && dag <= 24 {
        return Some("sankthans".into());
    }

    // Fårikålens dag: siste torsdag i september ± 3 dager
    // Siste torsdag i sept: finn dag 30, gå bakover til torsdag (ukedag 4)
    // Vi beregner siste torsdag ved å se hvilken dag 30. sept er.
    // Bruk Tomohiko Sakamoto-algoritme for ukedag.
    let sept_30_ukedag = {
        let y = aar; let m = 9u32; let d = 30u32;
        let t: [i32; 12] = [0,3,2,5,0,3,5,1,4,6,2,4];
        let yr = if m < 3 { y - 1 } else { y };
        let wd = (yr + yr/4 - yr/100 + yr/400 + t[(m-1) as usize] + d as i32) % 7;
        // 0=søn,1=man,...,6=lør → ISO: man=1..søn=7
        let iso = if wd == 0 { 7u32 } else { wd as u32 };
        iso
    };
    // Torsdag=4. Siste torsdag i sept: 30 - (sept_30_ukedag - 4 + 7) % 7
    let diff = (sept_30_ukedag + 7 - 4) % 7;
    let siste_tors = 30u32 - diff;
    let farikaal_nr = til_dagsnr(9, siste_tors);
    if maaned == 9 && (dato_nr - farikaal_nr).abs() <= 3 {
        return Some("farikaal".into());
    }

    // Halloween: okt 24–31
    if maaned == 10 && dag >= 24 {
        return Some("halloween".into());
    }

    // Jul: des 1 – jan 6
    if maaned == 12 && dag >= 1 {
        return Some("jul".into());
    }
    if maaned == 1 && dag <= 6 {
        return Some("jul".into());
    }

    None
}

#[tauri::command]
fn hoytid_aktiv() -> Option<String> {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // Unix-sekunder → dato (ingen chrono-crate)
    // Naiv gregorisk: sekunder siden 1970-01-01
    let dager_siden_epoke = (secs / 86400) as i64;
    // Civil-from-days algoritme (Howard Hinnant)
    let z = dager_siden_epoke + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe/1460 + doe/36524 - doe/146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365*yoe + yoe/4 - yoe/100);
    let mp = (5*doy + 2)/153;
    let d = doy - (153*mp+2)/5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    // ISO ukedag: 1970-01-01=torsdag=4
    let ukedag = ((dager_siden_epoke + 3) % 7 + 1) as u32; // 1=man..7=søn
    hoytid_aktiv_dato(m as u32, d as u32, ukedag, y as i32)
}

// ─── Forside: tilfeldige oppskrifter etter type-kategori ─────────────────────
#[derive(serde::Serialize)]
struct ForsideOppskrift {
    id: i64,
    navn: String,
    tid: Option<String>,
    bilde: Option<String>,
}

#[tauri::command]
fn forside_oppskrifter(
    app: AppHandle,
    typer: Vec<String>,
    #[allow(non_snake_case)] nattFilter: bool,
    hoytid: Option<String>,
) -> Vec<ForsideOppskrift> {
    let conn = match open(&app) {
        Ok(c) => c,
        Err(_) => return vec![],
    };

    // Høytidsmodus: ignorer typer/nattFilter, filtrer på høytid-kolonne
    if let Some(ref h) = hoytid {
        let sql = "SELECT id, navn, tid, bilde FROM oppskrifter \
                   WHERE INSTR(',' || COALESCE(hoytid,'') || ',', ',' || ? || ',') > 0 \
                   ORDER BY RANDOM() LIMIT 20";
        return conn.prepare(sql)
            .and_then(|mut stmt| {
                stmt.query_map([h.as_str()], |row| {
                    Ok(ForsideOppskrift {
                        id: row.get(0)?,
                        navn: row.get(1)?,
                        tid: row.get(2)?,
                        bilde: row.get(3)?,
                    })
                })
                .and_then(|rows| rows.collect())
            })
            .unwrap_or_default();
    }

    if typer.is_empty() {
        return vec![];
    }

    let placeholders = typer.iter().map(|_| "?").collect::<Vec<_>>().join(", ");

    let sql = if nattFilter {
        format!(
            "SELECT id, navn, tid, bilde FROM oppskrifter \
             WHERE type IN ({placeholders}) \
             AND id NOT IN ( \
                 SELECT DISTINCT oppskrift_id FROM trinn \
                 WHERE LOWER(tekst) LIKE '%ovn%' \
                    OR LOWER(tekst) LIKE '%stekepanne%' \
             ) \
             ORDER BY RANDOM() LIMIT 20"
        )
    } else {
        format!(
            "SELECT id, navn, tid, bilde FROM oppskrifter \
             WHERE type IN ({placeholders}) \
             ORDER BY RANDOM() LIMIT 20"
        )
    };

    let params: Vec<&dyn rusqlite::ToSql> = typer.iter().map(|s| s as &dyn rusqlite::ToSql).collect();

    conn.prepare(&sql)
        .and_then(|mut stmt| {
            stmt.query_map(params.as_slice(), |row| {
                Ok(ForsideOppskrift {
                    id: row.get(0)?,
                    navn: row.get(1)?,
                    tid: row.get(2)?,
                    bilde: row.get(3)?,
                })
            })
            .and_then(|rows| rows.collect())
        })
        .unwrap_or_default()
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
            hva_kan_jeg_lage,
            generer_matplan,
            about_info,
            forside_oppskrifter,
            hoytid_aktiv,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::{tid_til_min, paaskedag, hoytid_aktiv_dato};

    #[test]
    fn test_tid_til_min_min() {
        assert_eq!(tid_til_min("30 min"), Some(30));
    }
    #[test]
    fn test_tid_til_min_time() {
        assert_eq!(tid_til_min("1 time"), Some(60));
    }
    #[test]
    fn test_tid_til_min_time_og_min() {
        assert_eq!(tid_til_min("1 time 20 min"), Some(80));
    }
    #[test]
    fn test_tid_til_min_ugyldig() {
        assert_eq!(tid_til_min(""), None);
        assert_eq!(tid_til_min("ukjent"), None);
    }
    #[test]
    fn test_tid_til_min_2_timer() {
        assert_eq!(tid_til_min("2 timer 30 min"), Some(150));
    }

    #[test]
    fn test_paaskedag_2024() {
        // Påske 2024: 31. mars
        assert_eq!(paaskedag(2024), (3, 31));
    }

    #[test]
    fn test_paaskedag_2025() {
        // Påske 2025: 20. april
        assert_eq!(paaskedag(2025), (4, 20));
    }

    #[test]
    fn test_hoytid_jul_desember() {
        // 15. des, tirsdag (ukedag 2), 2024
        assert_eq!(hoytid_aktiv_dato(12, 15, 2, 2024).as_deref(), Some("jul"));
    }

    #[test]
    fn test_hoytid_jul_januar() {
        // 3. jan, torsdag (ukedag 4), 2025
        assert_eq!(hoytid_aktiv_dato(1, 3, 4, 2025).as_deref(), Some("jul"));
    }

    #[test]
    fn test_hoytid_halloween() {
        // 28. okt, mandag (ukedag 1), 2024
        assert_eq!(hoytid_aktiv_dato(10, 28, 1, 2024).as_deref(), Some("halloween"));
    }

    #[test]
    fn test_hoytid_mai17() {
        // 17. mai, fredag (ukedag 5), 2024
        assert_eq!(hoytid_aktiv_dato(5, 17, 5, 2024).as_deref(), Some("mai17"));
    }

    #[test]
    fn test_hoytid_valentins() {
        // 10. feb, lørdag (ukedag 6), 2024
        assert_eq!(hoytid_aktiv_dato(2, 10, 6, 2024).as_deref(), Some("valentins"));
    }

    #[test]
    fn test_hoytid_ingen_august() {
        // 15. aug — ingen høytid
        assert_eq!(hoytid_aktiv_dato(8, 15, 4, 2024), None);
    }
}
