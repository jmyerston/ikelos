import pytest

from ikelos.betacode import beta_to_unicode, unicode_to_beta

PAIRS = [
    ("a)/nqrwpos", "ἄνθρωπος"),
    ("*(abask", "Ἁβασκ"),
    ("*)aqh/nh", "Ἀθήνη"),
    ("w)=|", "ᾦ"),
    ("h|", "ῃ"),
    ("bi/ou", "βίου"),
    ("lo/gos", "λόγος"),
    ("ui(o/s", "υἱός"),
    ("a)i+/dhs", "ἀΐδης"),
    ("m'", "μʼ"),
]


@pytest.mark.parametrize("beta,uni", PAIRS)
def test_beta_to_unicode(beta, uni):
    assert beta_to_unicode(beta) == uni


@pytest.mark.parametrize("beta,uni", PAIRS)
def test_unicode_to_beta(beta, uni):
    assert unicode_to_beta(uni) == beta


def test_quantity_marks():
    assert beta_to_unicode("a_s", keep_quantity=True) == "ᾱς"
    assert beta_to_unicode("a_s") == "ας"
    assert unicode_to_beta("ᾱς", keep_quantity=True) == "a_s"


def test_passthrough_lemma_markup():
    assert beta_to_unicode("biou=,bio/s") == "βιοῦ,βιός"
    assert beta_to_unicode("gallus#1") == "γαλλυς#1"


def test_medial_sigma():
    assert beta_to_unicode("sw=ma") == "σῶμα"
