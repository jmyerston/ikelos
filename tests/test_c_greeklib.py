"""Differential tests: ikelos.greeklib vs the C greeklib (via ctypes)."""

from __future__ import annotations

import ctypes
import gzip
import json
import random

import pytest

import clib
from ikelos import greeklib as G
from ikelos.stemlib import read_text

pytestmark = pytest.mark.skipif(clib.lib() is None, reason="C library not built (tools/build_clib.sh)")

P_ERR = ctypes.c_void_p(-1).value


def _corpus() -> list[str]:
    words = set()
    with gzip.open(clib.HERE / "golden" / "default.jsonl.gz", "rt") as fh:
        for i, line in enumerate(fh):
            if i % 7 == 0:
                words.add(json.loads(line)["input"])
    rnd = random.Random(0)
    for line in rnd.sample(read_text("steminds/nomind").splitlines(), 3000):
        words.add(line.split(" ")[0])
        words.update(line.split()[1:3])
    for line in rnd.sample(read_text("steminds/vbind").splitlines(), 2000):
        words.add(line.split(" ")[0])
    # odd shapes
    words.update(["", "a", "*)/andra", "*(/aidhn", "e)nh(/bwsa", "a)nanti/r)r(hton", "graoi=n",
                  "ui+=a", "a)mfi/", "pro+i/", "-pai=s*", "r(ei=a", "ei(=", "q", "w)|", "a_)",
                  "lu/w", "le/gw", "pe/mpomen", "kai\\", "ou)k", "nu+", "a^^", "a__", "e)/eipe/ te"])
    return sorted(w for w in words if w.isascii() and "\0" not in w)


CORPUS = _corpus()


def ptr_index(p, buf) -> int:
    if p is None or p == P_ERR:
        return -1
    return p - ctypes.addressof(buf)


def test_corpus_size():
    assert len(CORPUS) > 5000


@pytest.mark.parametrize("syll", [0, 1, 2])
def test_getsyll_getaccent(syll):
    L = clib.lib()
    L.getsyll.restype = ctypes.c_void_p
    L.getsyll2.restype = ctypes.c_void_p
    L.getaccp.restype = ctypes.c_void_p
    L.getaccent.restype = ctypes.c_int
    for w in CORPUS:
        b = clib.cbuf(w)
        assert ptr_index(L.getsyll(b, syll), b) == G.getsyll(w, syll), w
        if w:
            assert ptr_index(L.getsyll2(b, syll), b) == G.getsyll2(w, syll), w
        assert ptr_index(L.getaccp(b, syll), b) == G.getaccp(w, syll), w
        c = L.getaccent(b, syll)
        assert chr(c & 0xFF) == G.getaccent(w, syll), w


def test_counts_and_predicates():
    L = clib.lib()
    for w in CORPUS:
        b = clib.cbuf(w)
        assert L.nsylls(b) == G.nsylls(w), w
        assert L.naccents(b) == G.naccents(w), w
        assert bool(L.hasaccent(b)) == G.hasaccent(w), w
        assert bool(L.has_quant(b)) == G.has_quant(w), w
        assert bool(L.has_diaeresis(b)) == G.has_diaeresis(w), w
        assert bool(L.has_extra_breath(b)) == G.has_extra_breath(w), w
        assert chr(L.getbreath(b) & 0xFF) == G.getbreath(w), w
        if w:
            assert L.longbyposition(b) == G.longbyposition(w), w
        for p in range(len(w)):
            assert bool(L.is_diphth(ctypes.byref(b, p), b)) == G.is_diphth(w, p), (w, p)


@pytest.mark.parametrize("syll", [0, 1, 2])
def test_quantity(syll):
    L = clib.lib()
    for w in CORPUS:
        b = clib.cbuf(w)
        for e in (0, 1):
            for o in (0, 1):
                assert L.quantprim(b, syll, e, o) == G.quantprim(w, syll, e, o), (w, e, o)
                assert L.getquantity(b, syll, None, e, o) == G.getquantity(w, syll, None, e, o), w


@pytest.mark.parametrize(
    "name,py",
    [
        ("stripbreath", G.stripbreath),
        ("stripdiaer", G.stripdiaer),
        ("stripquant", G.stripquant),
        ("stripshortmark", G.stripshortmark),
        ("striplongmark", G.striplongmark),
        ("stripstemsep", G.stripstemsep),
        ("stripmetachars", G.stripmetachars),
        ("stripacute", G.stripacute),
        ("striphyph", G.striphyph),
        ("zap2acc", G.zap2acc),
        ("zap_extra_breath", G.zap_extra_breath),
        ("zap_rr_breath", G.zap_rr_breath),
        ("standword", G.standword),
        ("beta_tolower", G.beta_tolower),
    ],
)
def test_string_transforms(name, py):
    for w in CORPUS:
        if not w and name in ("zap_rr_breath", "stripmetachars", "standword", "stripzeroend"):
            continue  # C reads past the terminator
        if name == "standword" and len(w) >= G.MAXWORDSIZE:
            continue  # C overflows its MAXWORDSIZE stack buffer
        _, out = clib.call_str(name, w)
        assert out == py(w), (name, w)


def test_stripacc():
    for w in CORPUS:
        r, out = clib.call_str("stripacc", w)
        assert (out, r) == G.stripacc(w), w


def test_addaccent_addbreath():
    L = clib.lib()
    for w in CORPUS:
        for acc in "/=\\":
            for syll in (0, 1, 2):
                p = G.getsyll(w, syll)
                if p < 0:
                    continue
                b = clib.cbuf(w)
                L.addaccent(b, ord(acc), ctypes.byref(b, p))
                assert clib.sval(b) == G.addaccent(w, acc, p), (w, acc, syll)
        for br in "()":
            b = clib.cbuf(w)
            L.addbreath(b, ord(br))
            assert clib.sval(b) == G.addbreath(w, br), (w, br)


def test_ends_in_next_cons():
    L = clib.lib()
    rnd = random.Random(1)
    for w in CORPUS:
        for k in (0, 1, 2, 4):
            suffix = w[len(w) - k:] if k <= len(w) else w
            other = rnd.choice(CORPUS)
            for s2 in (suffix, other[-3:]):
                assert bool(L.ends_in(clib.cbuf(w), clib.cbuf(s2))) == G.ends_in(w, s2), (w, s2)
        b = clib.cbuf(w)
        for p in range(len(w)):
            assert bool(L.next_cons_rough(ctypes.byref(b, p))) == G.next_cons_rough(w, p), (w, p)
