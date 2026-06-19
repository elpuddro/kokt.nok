from tagg_ingredienser import tagg_for_tekst


def test_bacon_er_svin_og_kjott():
    t = tagg_for_tekst("bacon")
    assert "svin" in t and "kjott" in t


def test_rodvin_er_alkohol():
    assert "alkohol" in tagg_for_tekst("rødvin")


def test_vineddik_er_ikke_alkohol():
    assert "alkohol" not in tagg_for_tekst("vineddik")


def test_romme_er_melk_ikke_alkohol():
    t = tagg_for_tekst("rømme")
    assert "melk" in t and "alkohol" not in t


def test_hvetemel_er_gluten():
    assert "gluten" in tagg_for_tekst("hvetemel")


def test_mandel_er_nott_ikke_kjott():
    t = tagg_for_tekst("mandel")
    assert "nott" in t and "kjott" not in t  # «and» i mandel skal ikke telle


def test_kylling_er_kjott():
    assert "kjott" in tagg_for_tekst("kylling")


def test_tofu_har_ingen_tagg():
    assert tagg_for_tekst("tofu") == set()


def test_eggplante_er_ikke_egg():
    assert "egg" not in tagg_for_tekst("eggplante")


def test_raatekst_treffer_svin():
    # navn tomt, men råtekst avslører svin
    assert "svin" in tagg_for_tekst("", "200 g bacon i terninger")


def test_vaniljeekstrakt_er_alkohol():
    assert "alkohol" in tagg_for_tekst("vaniljeekstrakt")


def test_worcestershire_er_fisk():
    assert "fisk" in tagg_for_tekst("worcestershiresaus")


def test_honning_er_honning():
    assert "honning" in tagg_for_tekst("honning")


def test_peanottsmor_er_nott_ikke_melk():
    t = tagg_for_tekst("peanøttsmør")
    assert "nott" in t and "melk" not in t


# ── Sammensatte ord (norsk lukket sammensetning — den kritiske bug-klassen) ──

def test_kyllingfilet_er_kjott():
    assert "kjott" in tagg_for_tekst("kyllingfilet")


def test_oksekjott_er_kjott():
    assert "kjott" in tagg_for_tekst("oksekjøtt")


def test_lammelaar_er_kjott():
    assert "kjott" in tagg_for_tekst("lammelår")


def test_laksefilet_er_fisk():
    assert "fisk" in tagg_for_tekst("laksefilet")


def test_torskefilet_er_fisk():
    assert "fisk" in tagg_for_tekst("torskefilet")


def test_blodpudding_er_blod():
    assert "blod" in tagg_for_tekst("blodpudding")


def test_andebryst_er_kjott():
    assert "kjott" in tagg_for_tekst("andebryst")


# ── Sammensetning-feller: prefiks må ikke skape false positives ──

def test_andre_er_ikke_kjott():
    # «andre» (= other) må ikke tagges som and/kjøtt
    assert "kjott" not in tagg_for_tekst("alfalfaspirer eller andre spirer")


def test_blodappelsin_er_ikke_blod():
    assert "blod" not in tagg_for_tekst("blodappelsin")


def test_seig_er_ikke_fisk():
    assert "fisk" not in tagg_for_tekst("seig karamell")


def test_honningmelon_er_ikke_honning():
    assert "honning" not in tagg_for_tekst("honningmelon")


# ── Plantemelk + ost/most (over-matching av delstreng-tagger) ──

def test_kremost_er_melk():
    assert "melk" in tagg_for_tekst("kremost naturell")


def test_brunost_er_melk():
    assert "melk" in tagg_for_tekst("brunost")


def test_kokosmelk_er_ikke_melk():
    assert "melk" not in tagg_for_tekst("kokosmelk")


def test_mandelmelk_er_nott_ikke_melk():
    t = tagg_for_tekst("mandelmelk")
    assert "nott" in t and "melk" not in t


def test_havrefloete_er_ikke_melk():
    assert "melk" not in tagg_for_tekst("havrefløte")


def test_eplemost_er_ikke_melk():
    assert "melk" not in tagg_for_tekst("eplemost")


def test_hvitloek_most_er_ikke_melk():
    assert "melk" not in tagg_for_tekst("hvitløk most i morter")


# ── Suffiks-sammensetninger (X+kjøtt, X+laks) — bug-klassen fra e2e-runde 3 ──

def test_farikaalkjott_er_kjott():
    assert "kjott" in tagg_for_tekst("fårikålkjøtt")


def test_pinnekjott_er_kjott():
    assert "kjott" in tagg_for_tekst("ferdigdampet pinnekjøtt")


def test_elgkjott_er_kjott():
    assert "kjott" in tagg_for_tekst("elgkjøttdeig")


def test_flatbiff_av_lam_er_kjott():
    assert "kjott" in tagg_for_tekst("flatbiff av lam")


def test_gravlaks_er_fisk():
    assert "fisk" in tagg_for_tekst("gravlaks")


def test_kjempereker_er_fisk():
    assert "fisk" in tagg_for_tekst("kjempereker")


# ── Over-match-feller for de promoterte delstreng-røttene ──

def test_flaksalt_er_ikke_fisk():
    assert "fisk" not in tagg_for_tekst("flaksalt")


def test_fruktkjott_er_ikke_kjott():
    assert "kjott" not in tagg_for_tekst("appelsinjuice uten fruktkjøtt")


def test_lampe_ord_er_ikke_kjott():
    # «lam» som delstreng ville truffet «lammet/flamme»; vi bruker \blam\b
    assert "kjott" not in tagg_for_tekst("flambert dessert")


def test_salami_er_svin_og_kjott():
    t = tagg_for_tekst("salami i skiver")
    assert "svin" in t and "kjott" in t


def test_svinekotelett_er_kjott():
    assert "kjott" in tagg_for_tekst("svinekoteletter")


def test_velg_er_ikke_kjott():
    assert "kjott" not in tagg_for_tekst("velg gjerne fullkornsris")


def test_kjeks_er_ikke_kjott():
    assert "kjott" not in tagg_for_tekst("Oreo-kjeks")


def test_belg_er_ikke_kjott():
    assert "kjott" not in tagg_for_tekst("ert i belg")


def test_hjortetakksalt_er_ikke_kjott():
    assert "kjott" not in tagg_for_tekst("hjortetakksalt")


def test_ribbe_er_kjott():
    assert "kjott" in tagg_for_tekst("ribbe")


def test_hoensesuppe_er_kjott():
    assert "kjott" in tagg_for_tekst("hønsekjøtt", "")


def test_seifilet_er_fisk():
    assert "fisk" in tagg_for_tekst("seifilet")


def test_seig_er_ikke_fisk():
    assert "fisk" not in tagg_for_tekst("seig karamell")


def test_oesters_er_fisk():
    assert "fisk" in tagg_for_tekst("østers")


def test_nyretapp_er_kjott():
    assert "kjott" in tagg_for_tekst("nyretapp")


def test_tynnribbe_er_svin():
    t = tagg_for_tekst("tynnribbe")
    assert "svin" in t and "kjott" in t


def test_nakkekotelett_er_svin():
    assert "svin" in tagg_for_tekst("stykker nakkekoteletter")


def test_lammeribbe_er_ikke_svin():
    # lammeribbe skal være kjøtt, men IKKE svin (lam er halal)
    t = tagg_for_tekst("lammeribbe")
    assert "kjott" in t and "svin" not in t


def test_nduja_er_svin_og_kjott():
    t = tagg_for_tekst("nduja eller annen sterk pølse")
    assert "svin" in t and "kjott" in t


def test_indrefilet_er_kjott():
    assert "kjott" in tagg_for_tekst("indrefilet")


def test_laksefilet_fortsatt_fisk_ikke_kjott():
    # sikre at indrefilet-tillegget ikke gjør laksefilet til kjøtt
    t = tagg_for_tekst("laksefilet")
    assert "fisk" in t and "kjott" not in t


# ── Vanlige matfisk + kutt (full residual-audit) ──

def test_steinbit_er_fisk():
    assert "fisk" in tagg_for_tekst("krydret steinbit i ovn")


def test_kveite_er_fisk():
    assert "fisk" in tagg_for_tekst("ovnsbakt kveite")


def test_flintstek_er_kjott():
    assert "kjott" in tagg_for_tekst("flintstek")


def test_pigwings_er_svin():
    t = tagg_for_tekst("pigwings (pork wings)")
    assert "svin" in t and "kjott" in t


def test_uer_er_fisk():
    assert "fisk" in tagg_for_tekst("uerfilet")


def test_druer_er_ikke_fisk():
    assert "fisk" not in tagg_for_tekst("blå druer, delt i fire")


def test_solsikkeolje_er_ikke_fisk():
    assert "fisk" not in tagg_for_tekst("litt solsikkeolje")


def test_ribbe_er_svin():
    t = tagg_for_tekst("gryterøkt ribbe")
    assert "svin" in t and "kjott" in t


def test_vegetarpoelse_er_ikke_kjott():
    t = tagg_for_tekst("vegetarpølse")
    assert "kjott" not in t and "svin" not in t


def test_soyakjoettdeig_er_ikke_kjott():
    assert "kjott" not in tagg_for_tekst("soyakjøttdeig")


def test_plain_poelse_er_svin():
    # brukervalg: uspesifisert pølse regnes som svin (halal-konservativt)
    t = tagg_for_tekst("grillpølse")
    assert "svin" in t and "kjott" in t


def test_kyllingpoelse_er_kjott_ikke_svin():
    t = tagg_for_tekst("kyllingpølse")
    assert "kjott" in t and "svin" not in t


def test_lammepoelse_er_kjott_ikke_svin():
    t = tagg_for_tekst("lammepølser")
    assert "kjott" in t and "svin" not in t


def test_skrei_er_fisk():
    assert "fisk" in tagg_for_tekst("stekt skrei med kaperssaus")


def test_flyndre_er_fisk():
    assert "fisk" in tagg_for_tekst("helstekt smørflyndre")


def test_smoerflyndre_er_ikke_melk():
    assert "melk" not in tagg_for_tekst("smørflyndre")


def test_kreps_er_fisk():
    assert "fisk" in tagg_for_tekst("kajunsk kreps")


def test_smaagris_er_svin():
    assert "svin" in tagg_for_tekst("helgrilling av smågris")


def test_spareribs_er_svin():
    assert "svin" in tagg_for_tekst("spareribs med bbq-saus")


def test_gaas_er_kjott():
    assert "kjott" in tagg_for_tekst("helstekt gås")


def test_smalahove_er_kjott():
    assert "kjott" in tagg_for_tekst("smalahove")
