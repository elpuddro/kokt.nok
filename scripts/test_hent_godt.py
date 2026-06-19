# -*- coding: utf-8 -*-
import pytest
import hent_godt


@pytest.fixture(autouse=True)
def _reset_navn_cache():
    hent_godt.nullstill_navn_cache()
    yield
    hent_godt.nullstill_navn_cache()


def test_parse_tall_enhet_navn():
    assert hent_godt.parse_ingrediens("2 dl melk") == (2.0, "dl", "melk")

def test_parse_heltall_gram():
    assert hent_godt.parse_ingrediens("100 g smør") == (100.0, "g", "smør")

def test_parse_brok_symbol():
    assert hent_godt.parse_ingrediens("½ ts salt") == (0.5, "ts", "salt")

def test_parse_brok_skrastrek():
    assert hent_godt.parse_ingrediens("1/2 dl fløte") == (0.5, "dl", "fløte")

def test_parse_stk_uten_enhetsord():
    assert hent_godt.parse_ingrediens("3 egg") == (3.0, None, "egg")

def test_parse_uten_mengde():
    assert hent_godt.parse_ingrediens("salt etter smak") == (None, None, "salt etter smak")

def test_parse_desimal_komma():
    assert hent_godt.parse_ingrediens("1,5 dl vann") == (1.5, "dl", "vann")

def test_parse_tom_streng():
    assert hent_godt.parse_ingrediens("") == (None, None, "")

def test_parse_stripper_whitespace():
    assert hent_godt.parse_ingrediens("  2 ss olje  ") == (2.0, "ss", "olje")

def test_parse_range_tar_forste_tall():
    # godt.no: «1 - 2 stk mango» / «1-2 ss honning» -> bruk foerste tall, behold enhet.
    assert hent_godt.parse_ingrediens("1 - 2 stk mango") == (1.0, "stk", "mango")
    assert hent_godt.parse_ingrediens("1-2 ss honning") == (1.0, "ss", "honning")

def test_parse_heltall_pluss_brok():
    assert hent_godt.parse_ingrediens("1½ dl melk") == (1.5, "dl", "melk")

def test_parse_heltall_pluss_brok_uten_mellomrom():
    assert hent_godt.parse_ingrediens("2¼ ts kanel") == (2.25, "ts", "kanel")


def test_iso_varighet_minutter():
    assert hent_godt.iso8601_til_min("PT30M") == "30 min"

def test_iso_varighet_timer_og_min():
    assert hent_godt.iso8601_til_min("PT1H30M") == "90 min"

def test_iso_varighet_bare_timer():
    assert hent_godt.iso8601_til_min("PT2H") == "120 min"

def test_iso_varighet_ugyldig_gir_none():
    assert hent_godt.iso8601_til_min("") is None
    assert hent_godt.iso8601_til_min(None) is None
    assert hent_godt.iso8601_til_min("tull") is None

def test_yield_heltall():
    assert hent_godt.parse_yield("4 porsjoner") == 4

def test_yield_bare_tall():
    assert hent_godt.parse_yield("6") == 6

def test_yield_liste_tar_forste_tall():
    assert hent_godt.parse_yield("ca 4-6 porsjoner") == 4

def test_yield_uten_tall_gir_none():
    assert hent_godt.parse_yield("noen") is None
    assert hent_godt.parse_yield(None) is None


def _html_med_jsonld(obj):
    import json
    return (
        '<html><head>'
        '<script type="application/ld+json">' + json.dumps(obj) + '</script>'
        '</head><body>x</body></html>'
    )

def test_jsonld_enkel_recipe():
    obj = {"@context": "https://schema.org", "@type": "Recipe", "name": "Kjøttkaker"}
    res = hent_godt.parse_jsonld(_html_med_jsonld(obj))
    assert res["name"] == "Kjøttkaker"

def test_jsonld_i_graph():
    obj = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage"},
        {"@type": "Recipe", "name": "Vafler"},
    ]}
    res = hent_godt.parse_jsonld(_html_med_jsonld(obj))
    assert res["name"] == "Vafler"

def test_jsonld_liste_paa_toppniva():
    obj = [{"@type": "Organization"}, {"@type": "Recipe", "name": "Suppe"}]
    res = hent_godt.parse_jsonld(_html_med_jsonld(obj))
    assert res["name"] == "Suppe"

def test_jsonld_ingen_recipe_gir_none():
    obj = {"@type": "WebPage", "name": "ikke en oppskrift"}
    assert hent_godt.parse_jsonld(_html_med_jsonld(obj)) is None

def test_jsonld_ingen_blokk_gir_none():
    assert hent_godt.parse_jsonld("<html><body>ingenting</body></html>") is None

def test_jsonld_ugyldig_json_gir_none():
    html = '<script type="application/ld+json">{ ugyldig }</script>'
    assert hent_godt.parse_jsonld(html) is None


def test_map_type_direkte_treff():
    assert hent_godt.map_type("Dessert") == "Dessert"

def test_map_type_ulik_kasus():
    assert hent_godt.map_type("dessert") == "Dessert"

def test_map_type_synonym_middag():
    assert hent_godt.map_type("middag") == "Middag"

def test_map_type_kjent_kake():
    assert hent_godt.map_type("kaker") == "Kaker"

def test_map_type_tom_gir_annet():
    assert hent_godt.map_type("") == "Annet"
    assert hent_godt.map_type(None) == "Annet"

import sqlite3

def _db_med(navn_url_par):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE oppskrifter (id INTEGER PRIMARY KEY, navn TEXT, url TEXT)")
    for navn, url in navn_url_par:
        conn.execute("INSERT INTO oppskrifter (navn, url) VALUES (?, ?)", (navn, url))
    return conn

def test_slug_fra_url():
    assert hent_godt.lag_slug("https://www.godt.no/oppskrifter/kjottkaker/") == "kjottkaker"

def test_slug_uten_etterskrastrek():
    assert hent_godt.lag_slug("https://www.godt.no/oppskrifter/vafler") == "vafler"

def test_dup_url_eksakt():
    conn = _db_med([("Vafler", "https://www.godt.no/oppskrifter/vafler/")])
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/vafler/", "Vafler") is True

def test_dup_uklar_navn():
    conn = _db_med([("Kjøttkaker", "https://matprat.no/x")])
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/kjottkaker/", "Kjøttkaker") is True

def test_dup_ny_oppskrift():
    conn = _db_med([("Vafler", "https://matprat.no/x")])
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/lapskaus/", "Lapskaus") is False

def test_dup_paa_slug():
    # oppskrifter.slug er UNIQUE: en slug som finnes fra foer (annen url/navn)
    # er en duplikat, ikke en feil.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE oppskrifter (id INTEGER PRIMARY KEY, navn TEXT, url TEXT, slug TEXT)")
    conn.execute("INSERT INTO oppskrifter (navn, url, slug) VALUES (?,?,?)",
                 ("Rabarbrasirup", "https://matprat.no/r", "rabarbrasirup"))
    # samme slug, ny url, ulikt navn -> fanges via slug-sjekken
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/tilbehoer/16957/rabarbrasirup",
                                 "Rabarbrasirup-variant", "rabarbrasirup") is True
    # ny slug -> ikke duplikat
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/x/1/y", "Helt ny", "helt-ny") is False

def test_trygg_url_enkoder_mellomrom_og_spesialtegn():
    # godt.no bilde-URLer har mellomrom/spesialtegn som urllib ellers nekter.
    ut = hent_godt._trygg_url("https://img.godt.no/w2000/plain/recipes/Mango smoothie")
    assert " " not in ut
    assert ut.startswith("https://img.godt.no/")
    assert "%20" in ut  # mellomrom enkodet

def test_dup_cache_isoleres_mellom_dber():
    # Egen DB med ett navn; cache skal reflektere denne, ikke en tidligere.
    conn = _db_med([("Lapskaus", "https://matprat.no/y")])
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/lapskaus/", "Lapskaus") is True
    assert hent_godt.er_duplikat(conn, "https://www.godt.no/oppskrifter/pizza/", "Pizza") is False


def test_er_oppskrift_url_skiller_oppskrift_fra_kategori():
    # Ekte oppskrift har /<kategori>/<tall>/<slug>; kategoriside har ikke tallet.
    assert hent_godt.er_oppskrift_url(
        "https://www.godt.no/oppskrifter/frokost/9780/frisk-og-tropisk-mango-smoothie")
    assert not hent_godt.er_oppskrift_url("https://www.godt.no/oppskrifter/frokost")
    assert not hent_godt.er_oppskrift_url("https://www.godt.no/oppskrifter/dessert")
    assert not hent_godt.er_oppskrift_url("https://www.godt.no/oppskrifter/saus")

def test_urls_fra_sitemap_xml():
    # Reell godt.no-struktur: oppskrifter har tall-id; kategorisider droppes.
    xml = b'''<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://www.godt.no/oppskrifter/frokost/9780/mango-smoothie</loc></url>
      <url><loc>https://www.godt.no/oppskrifter/dessert</loc></url>
      <url><loc>https://www.godt.no/artikler/noe/</loc></url>
      <url><loc>https://www.godt.no/oppskrifter/middag/12345/lapskaus</loc></url>
    </urlset>'''
    urls = hent_godt.urls_fra_sitemap(xml)
    assert "https://www.godt.no/oppskrifter/frokost/9780/mango-smoothie" in urls
    assert "https://www.godt.no/oppskrifter/middag/12345/lapskaus" in urls
    assert "https://www.godt.no/oppskrifter/dessert" not in urls  # kategoriside
    assert len(urls) == 2

def test_locs_fra_sitemap_index():
    xml = b'''<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://www.godt.no/sitemap-1.xml</loc></sitemap>
      <sitemap><loc>https://www.godt.no/sitemap-2.xml</loc></sitemap>
    </sitemapindex>'''
    locs = hent_godt.locs_fra_xml(xml)
    assert locs == ["https://www.godt.no/sitemap-1.xml", "https://www.godt.no/sitemap-2.xml"]


def test_locs_fra_xml_ugyldig_gir_tom_liste():
    # Malformert XML skal ikke krasje – returner tom liste så kjøringen fortsetter.
    assert hent_godt.locs_fra_xml(b"<urlset><loc>uavsluttet") == []


def test_bygg_oppskrift_fra_jsonld():
    ld = {
        "@type": "Recipe",
        "name": "Vafler",
        "description": "Gode vafler",
        "recipeYield": "4 porsjoner",
        "totalTime": "PT30M",
        "recipeCategory": "Dessert",
        "recipeIngredient": ["2 dl melk", "3 egg"],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Bland."},
            {"@type": "HowToStep", "text": "Stek."},
        ],
    }
    o = hent_godt.bygg_oppskrift(ld, "https://www.godt.no/oppskrifter/vafler/")
    assert o["navn"] == "Vafler"
    assert o["slug"] == "vafler"
    assert o["type"] == "Dessert"
    assert o["porsjoner"] == 4
    assert o["tid"] == "30 min"
    assert o["url"] == "https://www.godt.no/oppskrifter/vafler/"
    assert o["ingredienser"][0] == {"mengde": 2.0, "enhet": "dl", "navn": "melk", "raatekst": "2 dl melk", "sortering": 0}
    assert o["trinn"] == [{"nummer": 1, "tekst": "Bland."}, {"nummer": 2, "tekst": "Stek."}]

def test_bygg_oppskrift_instruksjoner_som_strenger():
    ld = {"@type": "Recipe", "name": "X", "recipeInstructions": ["Ett steg."]}
    o = hent_godt.bygg_oppskrift(ld, "https://www.godt.no/oppskrifter/x/")
    assert o["trinn"] == [{"nummer": 1, "tekst": "Ett steg."}]

def test_bygg_oppskrift_ingrediens_som_streng():
    # recipeIngredient som EN streng skal bli ÉN ingrediens, ikke én per tegn.
    ld = {"@type": "Recipe", "name": "X", "recipeIngredient": "2 dl melk"}
    o = hent_godt.bygg_oppskrift(ld, "https://www.godt.no/oppskrifter/x/")
    assert len(o["ingredienser"]) == 1
    assert o["ingredienser"][0]["raatekst"] == "2 dl melk"
    assert o["ingredienser"][0]["mengde"] == 2.0
    assert o["ingredienser"][0]["enhet"] == "dl"

def test_bygg_oppskrift_ekte_godt_no_form():
    # Bygd fra faktisk godt.no Recipe JSON-LD (mango-smoothie): recipeCategory
    # som komma-streng, recipeYield som tall, HowToStep-instruksjoner, totalTime.
    ld = {
        "@type": "Recipe",
        "name": "Frisk og tropisk mango smoothie",
        "description": "Toppet med pasjonsfrukt, kokos, chiafrø og pistasj.",
        "recipeCategory": "frokost, lunsj",
        "recipeYield": 2,
        "totalTime": "PT10M",
        "performTime": "PT10M",
        "recipeIngredient": ["1 - 2 stk mango", "300 g yoghurt naturell", "1 dl kokosmelk"],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Kjør mango, banan og yoghurt i en hurtigmikser.  "},
            {"@type": "HowToStep", "text": "Tips! Bruk frossen frukt."},
        ],
        "image": ["https://img.godt.no/w2000/plain/recipes/00/abc"],
    }
    o = hent_godt.bygg_oppskrift(
        ld, "https://www.godt.no/oppskrifter/frokost/9780/frisk-og-tropisk-mango-smoothie")
    assert o["navn"] == "Frisk og tropisk mango smoothie"
    assert o["slug"] == "frisk-og-tropisk-mango-smoothie"
    assert o["porsjoner"] == 2
    assert o["tid"] == "10 min"
    assert o["type"] == "Frokost"          # komma-streng → første kategori, mappet
    assert o["kategorier"] == ["Frokost"]
    assert len(o["ingredienser"]) == 3
    assert o["ingredienser"][0]["mengde"] == 1.0 and o["ingredienser"][0]["enhet"] == "stk"
    assert o["trinn"][0]["nummer"] == 1
    assert o["trinn"][0]["tekst"] == "Kjør mango, banan og yoghurt i en hurtigmikser."  # trimmet
    assert o["bilde_url"] == "https://img.godt.no/w2000/plain/recipes/00/abc"
