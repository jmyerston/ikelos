"""Differential tests: morphkeys / morphlib ports vs the C morphlib (via ctypes)."""

from __future__ import annotations

import ctypes
import random

import pytest

import clib
from clib import CGkString, CGkWord, CWordForm, gs_from_c, gs_to_c, gs_tuple, gw_from_c, gw_to_c, gw_tuple
from pymorpheus import consts as C
from pymorpheus import morphlib as M
from pymorpheus.gkstring import GkString, GkWord, WordForm, add_morphflag
from pymorpheus.morphkeys import ScanAsciiKeys
from pymorpheus.stemlib import read_text

pytestmark = pytest.mark.skipif(clib.lib() is None, reason="C library not built (tools/build_clib.sh)")

RND = random.Random(42)


def _keysets() -> list[str]:
    out = set()
    for name in ("steminds/nomind", "steminds/vbind"):
        lines = read_text(name).splitlines()
        for line in RND.sample(lines, 2500):
            for ent in line.split(" :")[1:]:
                fields = ent.strip().split(":")
                out.add(" ".join(fields[1:]))
                out.add(" ".join(fields))
    out.update([
        "not masc", "aor not ind", "crasis kai/", "crasis", "pb a)po/ verb", "rpb a)na/ aor",
        "end:ou os_ou", "pb:kata/ pp_pr", "rpb:a)po/ pp_ao", "le:lu/w ew_denom", "foo bar masc",
        "dissimilation apocope raw_preverb", "masc fem neut nom voc acc", "mid pass act dep",
        "*aeschin. *aesop. prose", "illw", "doric attic epic homeric",
    ])
    return sorted(out)


KEYSETS = _keysets()


def _words(n=3000) -> list[str]:
    out = set()
    for name in ("steminds/nomind", "steminds/vbind"):
        lines = read_text(name).splitlines()
        for line in RND.sample(lines, n):
            stem = line.split(" ")[0].lstrip("0123456789")
            if stem and len(stem) < 40 and "\0" not in stem:
                out.add(stem)
            for ent in line.split(" :")[1:2]:
                lem = ent.split(":")[0]
                if 0 < len(lem) < 40:
                    out.add(lem)
    return sorted(out)


WORDS = _words()


def test_scanasciikeys():
    L = clib.lib()
    for keys in KEYSETS:
        for with_avoid in (False, True):
            cw, cwant, cavoid = CGkWord(), CGkString(), CGkString()
            r = L.ScanAsciiKeys(clib.cbuf(keys), ctypes.byref(cw), ctypes.byref(cwant),
                                ctypes.byref(cavoid) if with_avoid else None)
            pw, pwant, pavoid = GkWord(), GkString(), GkString()
            pr = ScanAsciiKeys(keys, pw, pwant, pavoid if with_avoid else None)
            assert r == pr, keys
            assert gs_tuple(gs_from_c(cwant)) == gs_tuple(pwant), keys
            if with_avoid:
                assert gs_tuple(gs_from_c(cavoid)) == gs_tuple(pavoid), keys
            assert gw_tuple(gw_from_c(cw)) == gw_tuple(pw), keys


def test_load_euph_tab():
    L = clib.lib()
    L.load_euph_tab.restype = ctypes.POINTER(CGkString)
    for rel, is_contr in (("rule_files/raw_preverbs.table", 0), ("rule_files/conseuph.table", 1),
                          ("rule_files/vowcontr.table", 1)):
        n = ctypes.c_int()
        tab = L.load_euph_tab(rel.encode(), ctypes.byref(n), is_contr)
        py = M.load_euph_tab(rel, bool(is_contr))
        assert n.value == len(py)
        for i, e in enumerate(py):
            c = tab[i]
            raw = ctypes.string_at(ctypes.addressof(c) + CGkString.gkstring.offset, 60)
            assert raw[: raw.index(0)].decode() == e.gkstring, (rel, i)
            cooked = raw[10:]
            assert cooked[: cooked.index(0)].decode() == e.cooked, (rel, i)
            g = gs_from_c(c)
            assert (g.form.astuple(), g.stemtype, g.derivtype, g.dialect, g.morphflags, g.domains) == \
                (e.form.astuple(), e.stemtype, e.derivtype, e.dialect, e.morphflags, e.domains), (rel, i)


def test_simple_augment_and_redup():
    for w in WORDS:
        for syll in (0, 1):
            _, out = clib.call_str("simpleaugment", w, syll)
            assert out == M.simpleaugment(w, bool(syll)), (w, syll)
            for redupc in "ei":
                _, out = clib.call_str("simpleredupit", w, syll, ord(redupc))
                assert out == M.simpleredupit(w, bool(syll), redupc), (w, syll, redupc)


def test_unredupl_unaugfromlemma():
    L = clib.lib()
    for w in WORDS:
        for redupc in "ei":
            res = clib.cbuf("")
            r = L.un_redupl(clib.cbuf(w), res, ord(redupc))
            assert (r, clib.sval(res)) == M.un_redupl(w, redupc), w
        lemma = RND.choice(WORDS)
        for lem in (lemma, w, "e)" + w, w[1:]):
            b = clib.cbuf(w)
            r = L.unaugfromlemma(b, clib.cbuf(lem))
            assert (r, clib.sval(b)) == M.unaugfromlemma(w, lem), (w, lem)


def test_putsimpleacc_cmpend_dictstrcmp():
    L = clib.lib()
    for w in WORDS:
        from pymorpheus.greeklib import stripacc

        bare = stripacc(w)[0]
        _, out = clib.call_str("putsimpleacc", bare)
        assert out == M.putsimpleacc(bare), bare
        for k in (1, 2, 3, len(w)):
            ending = w[-k:] if k <= len(w) else w
            stem = clib.cbuf("")
            r = L.cmpend(clib.cbuf(w), clib.cbuf(ending), stem)
            assert (r, clib.sval(stem) if r else "") == M.cmpend(w, ending), (w, ending)
        o = RND.choice(WORDS)
        c = L.dictstrcmp(clib.cbuf(w), clib.cbuf(o))
        p = M.dictstrcmp(w, o)
        assert (c > 0) - (c < 0) == (p > 0) - (p < 0), (w, o)


PREVERBS = ["a)po/", "kata/", "su/n", "e)n", "pro/s", "a)mfi/", "dia/", "e)pi/", "u(po/", "pro/",
            "peri/", "a)nti/", "meta/", "para/", "e)k", "a)na/", "u(pe/r", "ei)s", "a)po/,kata/",
            "para/,su/n", "e)pi/,a)na/", "e)k,pro/", "a)nti/,kata/", "su/n,e)k"]
PB_FLAGS = [0, C.RAW_PREVERB, C.APOCOPE, C.DISSIMILATION, C.ELIDE_PREVERB, C.UNASP_PREVERB,
            C.PREVB_AUGMENT, C.DOUBLED_CONS, C.IOTA_INTENS, C.SIG_TO_CI, C.SHORT_EIS, C.EN_TO_ENI,
            C.PROS_TO_POTI, C.META_TO_PEDA, C.UPO_TO_UPAI]
STEMS = ["ba/llw", "e)/xw", "ai(re/w", "i(/sthmi", "lu/w", "r(e/w", "o)/llumi", "fe/rw", "sth/sw",
         "zhte/w", "gra/fw", "mi/gnumi", "pe/mpw", "dido/nai", "e(/lkw", "a)/gw", "ou)ra/nios",
         "strateu/w", "kei/mai", "qe/w", "ti/qhmi", "eu)/xomai", "u(/w", "h(/kw", "i)/dw"]


def test_rstprevb():
    L = clib.lib()
    for pb in PREVERBS:
        for st in STEMS:
            for f in PB_FLAGS:
                g = GkString()
                g.morphflags = add_morphflag(0, f) if f else 0
                cg = gs_to_c(g)
                b = clib.cbuf(st)
                L.rstprevb(b, clib.cbuf(pb), ctypes.byref(cg))
                out = M.rstprevb(st, pb, g)
                assert (clib.sval(b), gs_from_c(cg).morphflags) == (out, g.morphflags), (pb, st, f)


RAWPBS = ["a)po", "kata", "sun", "sum", "en", "pros", "parasummeta", "a)f", "kaq", "a)mfi", "dia",
          "e)pi", "u(po", "pro", "peri", "a)nti", "meta", "para", "e)k", "e)c", "a)na", "u(per",
          "ei)s", "a)poka", "a)pokata", "katapro", "sullu", "e)gka", "a)nqu", "proti", "xyz", ""]


def test_is_preverb_combpbstem():
    L = clib.lib()
    for raw in RAWPBS:
        g = GkString()
        cg = gs_to_c(g)
        full = clib.cbuf("")
        r = L.is_preverb(clib.cbuf(raw), full, ctypes.byref(cg))
        pr, pfull = M.is_preverb(raw, "", g)
        assert (r, clib.sval(full)) == (pr, pfull), raw
        assert gs_tuple(gs_from_c(cg)) == gs_tuple(g), raw
        for st in STEMS + ["ai)r", "air", "strat", "roibd", "rre", "skep", "xa", ""]:
            for dial in (0, C.ATTIC, C.IONIC):
                for f in (0, C.DISSIMILATION, C.UNASP_PREVERB):
                    mf = add_morphflag(0, f) if f else 0
                    arr = (ctypes.c_ubyte * 12)()
                    clib.mf_to_c(mf, arr)
                    b = clib.cbuf(st)
                    r = L.CombPbStem(clib.cbuf(raw), b, dial, arr)
                    ok, pst, pmf = M.CombPbStem(raw, st, dial, mf)
                    assert (bool(r), clib.sval(b), clib.mf_from_c(arr)) == (ok, pst, pmf), (raw, st, dial, f)


FORMS = [WordForm(case=c, number=n, gender=g) for c in (1, 2, 4, 8, 16) for n in (1, 2, 4) for g in (1, 2, 4)]
FORMS += [WordForm(voice=1, mood=6, gender=4, number=1, case=1), WordForm(voice=2, mood=5, tense=5)]
END_FLAGS = [0, C.CONTRACTED, C.ENCLITIC, C.ACCENT_OPTIONAL, C.STEM_ACC, C.SUFF_ACC, C.ANT_ACC,
             C.PROCLITIC, C.NO_CIRCUMFLEX, C.PERS_NAME]
ENDINGS = ["os", "ou", "w|", "on", "e", "oi", "wn", "ois", "ous", "a", "h", "hs", "h|", "hn", "ai",
           "wn", "ais", "as", "s", "os", "i", "a", "es", "wn", "si", "esi", "", "*", "eos", "ews", "ei"]


def test_fixpersacc():
    L = clib.lib()
    from pymorpheus.greeklib import stripacc

    for w in RND.sample(WORDS, 400):
        stem = stripacc(w)[0][:-2] or stripacc(w)[0]
        for ending in RND.sample(ENDINGS, 6):
            form = RND.choice(FORMS)
            stype = RND.choice([C.NOUNSTEM | C.DECL3, C.NOUNSTEM | C.DECL2, C.ADJSTEM | C.DECL1, 0])
            sflag = RND.choice(END_FLAGS)
            eflag = RND.choice(END_FLAGS)
            mflag = RND.choice(END_FLAGS)
            stemg = GkString(stem, stemtype=stype, morphflags=add_morphflag(0, sflag) if sflag else 0)
            endg = GkString(ending, form=form.copy(), morphflags=add_morphflag(0, eflag) if eflag else 0)
            mf = add_morphflag(0, mflag) if mflag else 0
            for is_ending in (0, 1):
                arr = (ctypes.c_ubyte * 12)()
                clib.mf_to_c(mf, arr)
                cform = CWordForm()
                clib.form_to_c(form, cform)
                cend = clib.cbuf(ending)
                word = clib.cbuf("")
                L.FixPersAcc(ctypes.byref(gs_to_c(endg)), arr, ctypes.byref(gs_to_c(stemg)), cend, word,
                             cform, is_ending)
                pw, pend = M.FixPersAcc(endg, mf, stemg, ending, form, is_ending)
                assert (clib.sval(word), clib.sval(cend)) == (pw, pend), (stem, ending, form, sflag, eflag, mflag)


def test_markstem():
    L = clib.lib()
    for w in WORDS:
        for stype, mood in ((C.NOUNSTEM, 0), (C.ADJSTEM, 0), (C.VERBSTEM, 6), (C.VERBSTEM, 1)):
            g = GkString(w, stemtype=stype, form=WordForm(mood=mood))
            cg = gs_to_c(g)
            L.markstem(clib.cbuf(w), ctypes.byref(cg))
            M.markstem(w, g)
            assert gs_from_c(cg).morphflags == g.morphflags, (w, stype, mood)


def test_add_augment_unaugment():
    L = clib.lib()
    for w in WORDS:
        from pymorpheus.greeklib import stripacc

        s = stripacc(w)[0]
        for tense, mood in ((C.AORIST, C.INDICATIVE), (C.IMPERF, C.INDICATIVE), (C.PLUPERF, C.INDICATIVE),
                            (C.AORIST, C.SUBJUNCTIVE)):
            for sflag in (0, C.SYLL_AUGMENT, C.RAW_SONANT, C.ATTIC_REDUPL):
                for dial in (0, C.ATTIC, C.DORIC):
                    forms = [GkWord() for _ in range(8)]
                    g = forms[0]
                    g.workword = s
                    g.form = WordForm(tense=tense, mood=mood)
                    g.dialect = dial
                    if sflag:
                        g.stem.morphflags = add_morphflag(0, sflag)
                    arr = (CGkWord * 8)()
                    for i in range(8):
                        gw_to_c(forms[i], arr[i])
                    mf = (ctypes.c_ubyte * 12)()
                    r = L.add_augment(arr, mf, 6)
                    pr = M.add_augment(forms, 0, 0, 6)
                    assert r == pr, (s, tense, sflag, dial)
                    for i in range(max(r, 1)):
                        assert gw_tuple(gw_from_c(arr[i])) == gw_tuple(forms[i]), (s, tense, sflag, dial, i)
        for wantsyll in (0, 1):
            for wantredupl in (0, 1):
                cp = [CGkString() for _ in range(12)]
                cq = [CGkString() for _ in range(12)]
                pp_ = (ctypes.POINTER(CGkString) * 12)(*[ctypes.pointer(x) for x in cp])
                qq_ = (ctypes.POINTER(CGkString) * 12)(*[ctypes.pointer(x) for x in cq])
                r = L.unaugment(clib.cbuf(s), pp_, qq_, 10, 0, wantsyll, wantredupl)
                pp = [GkString() for _ in range(12)]
                qq = [GkString() for _ in range(12)]
                pr = M.unaugment(s, pp, qq, 10, 0, bool(wantsyll), bool(wantredupl))
                assert r == pr, s
                for i in range(12):
                    assert gs_tuple(gs_from_c(cp[i])) == gs_tuple(pp[i]), (s, i)
                    assert gs_tuple(gs_from_c(cq[i])) == gs_tuple(qq[i]), (s, i)
