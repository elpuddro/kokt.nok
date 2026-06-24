import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from tagg_hoytid import tagg_hoytid


def test_pinnekjott_er_jul():
    assert "jul" in tagg_hoytid("Pinnekjøtt med kålrabistappe", "pinnekjøtt, kålrabi")


def test_ribbe_er_jul():
    assert "jul" in tagg_hoytid("Julegribberibbe", "ribbe, svor")


def test_lam_er_paske():
    assert "paske" in tagg_hoytid("Lammestek", "lammestek, rosmarin")


def test_blotkake_er_mai17():
    assert "mai17" in tagg_hoytid("Bløtkake til 17. mai", "jordbær, fløte")


def test_jordbær_er_sankthans():
    assert "sankthans" in tagg_hoytid("Jordbær med rømme", "jordbær, rømme")


def test_farikaal_er_farikaal():
    assert "farikaal" in tagg_hoytid("Fårikål", "lam, kål, pepper")


def test_gresskar_er_halloween():
    assert "halloween" in tagg_hoytid("Gresskarpai", "gresskar, kanel")


def test_sjokolade_er_valentins():
    assert "valentins" in tagg_hoytid("Sjokoladefondue", "sjokolade, fløte")


def test_kylling_er_ingen_hoytid():
    assert tagg_hoytid("Kyllingfilet", "kylling, hvitløk") == set()


def test_farikaal_er_ikke_paske():
    assert "paske" not in tagg_hoytid("Fårikål", "lam, kål")
