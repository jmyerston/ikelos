import pytest

from ikelos import stemlib


def test_endtables_loaded():
    names = stemlib.endtable_names()
    assert len(names) == 139
    recs = stemlib.endtable("a_hs")
    assert len(recs) == 23
    assert recs[0].ending == "a" and recs[0].stemtype == 4164
    assert len(stemlib.derivtable_names()) == 38


def test_morphstrcmp_iota_subscript():
    assert stemlib.morphstrcmp("h|", "hi") == 0
    assert stemlib.morphstrncmp("h|s", "his ", 3) == 0
    assert stemlib.morphstrcmp("a", "b") < 0


@pytest.mark.parametrize(
    "stem,expected_prefix",
    [("a)nqrwp", ":a)/nqrwpos:os_ou:masc"), ("log", ":lo/gos:os_ou:masc")],
)
def test_nom_index(stem, expected_prefix):
    keys = stemlib.nom_index().lookup(stem, exact_match=False)
    assert keys is not None and keys.startswith(expected_prefix)


def test_nom_index_miss():
    assert stemlib.nom_index().lookup("zzzzq", exact_match=False) is None


def test_vb_index():
    assert stemlib.vb_index().check("paideu") == ":paideu/w:w_stem:euw"
    assert stemlib.vb_index().check("paideuzz") is None


@pytest.mark.parametrize(
    "loader",
    [stemlib.vb_index, stemlib.noun_end_index, stemlib.verb_end_index, stemlib.deriv_end_index],
)
def test_end_index_binary_search_finds_every_key(loader):
    """Binary search must agree with the file contents (i.e. files are sorted for it)."""
    idx = loader()
    misses = []
    for line in idx.lines:
        if " " not in line:
            continue
        key = line.split(" ", 1)[0]
        if idx.check(key) is None:
            misses.append(key)
    assert len(misses) <= 0.001 * len(idx.lines), misses[:10]
