# -*- coding: utf-8 -*-
import kassal


# ── hodeord: strip tilberednings-prefiks, første gjenværende ord ──
def test_hodeord_enkelt():
    assert kassal.hodeord("hvetemel") == "hvetemel"

def test_hodeord_stripper_prefiks():
    assert kassal.hodeord("smeltet smør") == "smør"
    assert kassal.hodeord("finhakket løk") == "løk"

def test_hodeord_komma_og_beskrivelse():
    assert kassal.hodeord("banan , til steking (pynt)") == "banan"

def test_hodeord_for_kort_gir_none():
    assert kassal.hodeord("is") is None  # < 3 tegn

def test_hodeord_dropper_punktuasjon():
    assert kassal.hodeord("(pynt)") is None
    assert kassal.hodeord("1/2 banan") == "banan"

def test_hodeord_kun_prefiks_gir_none():
    assert kassal.hodeord("smeltet") is None


# ── parse_produktnavn: (enhetsklasse, mengde_i_basis) fra produktnavn ──
def test_parse_kg():
    assert kassal.parse_produktnavn("Hvetemel Siktet 1kg Møllerens") == ("g", 1000.0)

def test_parse_gram():
    assert kassal.parse_produktnavn("Gulrot 400g Gartner") == ("g", 400.0)

def test_parse_liter_komma():
    assert kassal.parse_produktnavn("Lettmelk 0,5% 1,75l Q") == ("ml", 1750.0)

def test_parse_stk():
    assert kassal.parse_produktnavn("Egg Frittgående 18stk First Price") == ("stk", 18.0)

def test_parse_ingen_vekt_gir_none():
    assert kassal.parse_produktnavn("Eldorado Krydderblanding") is None


# ── er_treff: hodeord MÅ være første token i produktnavn ──
def test_treff_forste_token():
    assert kassal.er_treff("bakepulver", "Bakepulver 250g Freia") is True
    assert kassal.er_treff("egg", "Egg Frittgående 18stk") is True

def test_treff_avviser_descriptor():
    # presisjon: salt som smaks-descriptor, ikke produktet
    assert kassal.er_treff("salt", "Potetgull Classic Salt 250g Maarud") is False
    assert kassal.er_treff("smør", "Olivero Smør & Olivenolje 400g") is False

def test_treff_avviser_substring():
    assert kassal.er_treff("salt", "Smør Usaltet 250g Tine") is False  # 'salt' ikke token


# ── velg_beste: billigste enhetspris innen samme enhetsklasse ──
def _kand(navn, pris, store=None):
    d = {"name": navn, "current_price": pris}
    if store is not None:
        d["_store"] = store
    return d

def test_velg_beste_billigste_innen_klasse():
    kandidater = [_kand("Egg 12stk Prior", 31.9), _kand("Egg 18stk First Price", 39.9)]
    best = kassal.velg_beste("egg", kandidater, mal_klasse="stk")
    # 39.9/18 = 2.217 < 31.9/12 = 2.658  → 18-pakka er billigst per stk
    assert best["enhetsklasse"] == "stk"
    assert round(best["enhetspris"], 3) == 2.217
    assert best["produkt_navn"] == "Egg 18stk First Price"

def test_velg_beste_baerer_butikk():
    kandidater = [_kand("Egg 18stk First Price", 39.9, store="KIWI")]
    best = kassal.velg_beste("egg", kandidater, mal_klasse="stk")
    assert best["butikk"] == "KIWI"

def test_velg_beste_filtrerer_feil_klasse():
    # ingrediens er stk, men bare g-produkter finnes → ingen match
    kandidater = [_kand("Eggpasta 500g Barilla", 25.0)]
    assert kassal.velg_beste("egg", kandidater, mal_klasse="stk") is None

def test_velg_beste_avviser_descriptor_match():
    kandidater = [_kand("Potetgull Salt 250g", 24.9)]
    assert kassal.velg_beste("salt", kandidater, mal_klasse="g") is None

def test_velg_beste_tom_gir_none():
    assert kassal.velg_beste("xyz", [], mal_klasse="g") is None

def test_velg_beste_null_mengde_krasjer_ikke():
    # Et produkt med "0stk" må ikke gi ZeroDivisionError, bare forkastes.
    kandidater = [_kand("Egg 0stk Test", 10.0)]
    assert kassal.velg_beste("egg", kandidater, mal_klasse="stk") is None


# ── ingrediens_basis: (enhetsklasse, mengde_i_basis) fra ingrediens-enhet ──
def test_ingrediens_basis_gram():
    assert kassal.ingrediens_basis(100.0, "g") == ("g", 100.0)
    assert kassal.ingrediens_basis(2.0, "kg") == ("g", 2000.0)

def test_ingrediens_basis_skje():
    assert kassal.ingrediens_basis(2.0, "ss") == ("g", 30.0)   # 1 ss = 15 g/ml
    assert kassal.ingrediens_basis(1.0, "ts") == ("g", 5.0)

def test_ingrediens_basis_volum():
    assert kassal.ingrediens_basis(4.0, "dl") == ("ml", 400.0)
    assert kassal.ingrediens_basis(0.5, "l") == ("ml", 500.0)

def test_ingrediens_basis_stk():
    assert kassal.ingrediens_basis(4.0, "stk.") == ("stk", 4.0)
    assert kassal.ingrediens_basis(3.0, "") == ("stk", 3.0)

def test_ingrediens_basis_ukjent_gir_none():
    assert kassal.ingrediens_basis(1.0, "bunt") is None
    assert kassal.ingrediens_basis(1.0, "boks") is None
