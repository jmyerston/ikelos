"""Differential tests: gkends / gkdict ports vs C (via ctypes)."""

from __future__ import annotations

import ctypes
import random

import pytest

import clib
from clib import CGkString, gs_from_c, gs_to_c, gs_tuple
from pymorpheus import gkdict as D
from pymorpheus import gkends as E
from pymorpheus.gkstring import GkString
from pymorpheus.greeklib import stripacc
from pymorpheus.stemlib import read_text

pytestmark = pytest.mark.skipif(clib.lib() is None, reason="C library not built (tools/build_clib.sh)")

RND = random.Random(7)


def _entries():
    """(stem, restricts) pairs from the stem indices."""
    out = []
    for name in ("steminds/nomind", "steminds/vbind"):
        for line in RND.sample(read_text(name).splitlines(), 600):
            stem = line.split(" ")[0]
            for ent in line.split(" :")[1:]:
                fields = ent.strip().split(":")
                out.append((stem.lstrip("123"), " ".join(fields[1:])))
    return out


ENTRIES = _entries() + [
    # two domains: C reads Is_group_name (flag 110) from st_domains[1]
    ("*(ellhsponti", "os_h_on *hdt. *xen."),
    ("*(ellhsponti", "os_h_on *xen. *hdt."),
]


def _stems():
    s = set()
    for name in ("steminds/nomind", "steminds/vbind"):
        for line in RND.sample(read_text(name).splitlines(), 1500):
            st = line.split(" ")[0].lstrip("123")
            if st and len(st) < 40:
                s.add(st)
                s.add(st[:-1])
                s.add("e)" + st)
                s.add("le" + st)
    s.update(["tim", "lu", "e)lu", "lelu", "poie", "gegra", "ei)", "kai/", "a)po/", "h)gor", "e)fil", "ti_m"])
    return sorted(x for x in s if x)


STEMS = _stems()


def test_chckstem_and_indices():
    L = clib.lib()
    for st in STEMS:
        for is_nom in (0, 1):
            b = clib.cbuf(st)
            keys = clib.cbuf("", 8192)
            r = L.chckstem(b, keys, is_nom)
            assert (r, clib.sval(keys), clib.sval(b)) == D.chckstem(st, bool(is_nom)), (st, is_nom)
        for name, py in (("chckindecl", D.chckindecl), ("chckirrverb", D.chckirrverb),
                         ("chckderiv", D.chckderiv)):
            keys = clib.cbuf("", 8192)
            r = getattr(L, name)(clib.cbuf(st), keys)
            assert (r, clib.sval(keys)) == py(st), (name, st)
        keys = clib.cbuf("", 8192)
        r = L.checkforderiv(clib.cbuf(st), keys)
        assert (r, clib.sval(keys)) == D.checkforderiv(st), st


def _c_endings(endstr, restricts, stemstr, prevb, dial):
    L = clib.lib()
    L.chckendings.restype = ctypes.POINTER(CGkString)
    n = ctypes.c_int()
    p = L.chckendings(clib.cbuf(endstr) if endstr is not None else None, clib.cbuf(restricts),
                      clib.cbuf(stemstr) if stemstr is not None else None,
                      clib.cbuf(prevb) if prevb is not None else None, dial, ctypes.byref(n))
    if not p:
        return None
    return [gs_tuple(gs_from_c(p[i])) for i in range(n.value)]


def test_chckendings():
    for stem, restricts in ENTRIES:
        for endstr in (None, "os", "ou", "w", "e", "-", "a_", "h|", "ai", "ein"):
            for prevb in (None, "", "a)po"):
                c = _c_endings(endstr, restricts, stem, prevb, 0)
                p = E.chckendings(endstr, restricts, stem, prevb, 0)
                p = None if p is None else [gs_tuple(g) for g in p]
                assert c == p, (stem, restricts, endstr, prevb)


def test_compatkeys():
    L = clib.lib()
    lines = read_text("derivs/indices/derivind").splitlines()
    dkeys = []
    for line in RND.sample(lines, min(200, len(lines))):
        dkeys += line.split(" ")[1:]
    for (stem, restricts) in RND.sample(ENTRIES, 300):
        for dk in RND.sample(dkeys, min(20, len(dkeys))):
            k1 = dk.replace(":", " ")
            for is_deriv in (0, 1):
                g = GkString()
                if is_deriv:
                    from pymorpheus.gkstring import add_morphflag
                    from pymorpheus import consts as C
                    g.morphflags = add_morphflag(0, C.IS_DERIV)
                cg = gs_to_c(g)
                r = L.CompatKeys(clib.cbuf(k1), clib.cbuf(restricts), ctypes.byref(cg))
                pr = E.CompatKeys(k1, restricts, g)
                assert (r, gs_tuple(gs_from_c(cg))) == (pr, gs_tuple(g)), (k1, restricts)
