"""Port of the runtime parts of ``src/gkends``: ``endindex.c``, ``getcurrend.c``,
``retrends.c`` and ``euphend.c``.
"""

from __future__ import annotations

from functools import lru_cache

from . import consts as C
from .gkstring import (
    AndDialect,
    GkString,
    GkWord,
    WordForm,
    add_morphflag,
    has_morphflag,
    no_morphflag,
    zap_morphflag,
)
from .greeklib import (
    HARDSHORT,
    at,
    has_quant,
    hasaccent,
    isalpha,
    stripacc,
    stripquant,
    strcmp,
)
from .morphkeys import NameOfStemtype, ScanAsciiKeys
from .morphlib import dictstrcmp, markstem
from . import stemlib

# ==========================================================================
# endindex.c
# ==========================================================================


def chcknend(endstr: str) -> str | None:
    """Noun ending index (``nendind``); quantity marks are ignored."""
    return stemlib.noun_end_index().check(stripquant(endstr))


def chckdictent(possent: str) -> str | None:
    return stemlib.dict_entry_index().check(stripquant(possent))


def chckcmpvb(endstr: str) -> str | None:
    return stemlib.compound_verb_index().check(stripquant(endstr))


def chckvend(endstr: str) -> str | None:
    return stemlib.verb_end_index().check(endstr)


def chckvstem(stemstr: str) -> str | None:
    return stemlib.vb_index().check(stemstr)


def chckdvend(endstr: str) -> str | None:
    return stemlib.deriv_end_index().check(endstr)


def chckend(endstring: str) -> bool:
    return chckvend(endstring) is not None or chcknend(endstring) is not None


# ==========================================================================
# getcurrend.c
# ==========================================================================


def _record_to_gstr(rec, stemtype: int) -> GkString:
    doms = rec.domains.split(b"\0", 1)[0].decode("latin-1")
    return GkString(
        rec.ending,
        WordForm(rec.voice, rec.mood, rec.tense, rec.person, rec.number, rec.case,
                 rec.degree, rec.gender),
        stemtype,
        rec.derivtype,
        rec.dialect,
        rec.geogregion,
        int.from_bytes(rec.morphflags, "little"),
        doms,
    )


@lru_cache(maxsize=None)
def _end_list(stemtype: int) -> tuple[GkString, ...] | None:
    name = NameOfStemtype(stemtype)
    try:
        recs = stemlib.endtable(name)
    except KeyError:
        return None
    return tuple(_record_to_gstr(r, stemtype) for r in recs)


def GetCurrentEndList(gstr: GkString) -> tuple[GkString, ...] | None:
    """The endtable for ``gstr``'s stemtype (shared templates: copy before modifying)."""
    return _end_list(gstr.stemtype)


# ==========================================================================
# euphend.c
# ==========================================================================


def EuphEnd(want: GkString, have: GkString, strict: int) -> int:
    wmf = want.morphflags
    hmf = have.morphflags
    curs = have.gkstring
    if strict and has_morphflag(wmf, C.ITERATIVE) and not has_morphflag(hmf, C.ITERATIVE):
        return 0
    if has_morphflag(wmf, C.UNCONTR_END) and has_morphflag(hmf, C.CONTRACTED):
        return 0
    if has_morphflag(wmf, C.NU_MOVABLE) and not has_morphflag(hmf, C.NU_MOVABLE):
        if not has_morphflag(wmf, C.IS_DERIV):
            return 0
    c0 = at(curs, 0)
    if c0 == "h" and not has_morphflag(wmf, C.ENDS_IN_DIGAMMA) and (
            (have.stemtype & (C.DECL1 | C.DECL2)) or have.form.mood == C.PARTICIPLE
            or has_morphflag(wmf, C.IS_DERIV)):
        if has_morphflag(wmf, C.R_E_I_ALPHA):
            if AndDialect(want.dialect, C.RHO_ETA_DIAL) < 0:
                if not (want.stemtype & C.PPARTMASK) or has_morphflag(wmf, C.IS_DERIV):
                    return 0
                return 1
            have.dialect = C.RHO_ETA_DIAL
            want.morphflags = zap_morphflag(want.morphflags, C.R_E_I_ALPHA)
    elif c0 == "a" and at(curs, 1) == "_":
        if has_morphflag(hmf, C.R_E_I_ALPHA):
            if not has_morphflag(wmf, C.R_E_I_ALPHA):
                return 0
            if has_morphflag(wmf, C.ENDS_IN_DIGAMMA):
                return 0
    if want.form.degree == C.COMPARATIVE and have.form.degree != C.COMPARATIVE:
        if strict:
            return 0
    if want.form.degree == C.SUPERLATIVE and have.form.degree != C.SUPERLATIVE:
        if strict:
            return 0
    wmf = want.morphflags
    hmf = have.morphflags
    hl, hs = has_morphflag(hmf, C.LONG_PEN), has_morphflag(hmf, C.SHORT_PEN)
    if (hl and has_morphflag(wmf, C.LONG_PEN) != hl) or (hs and has_morphflag(wmf, C.SHORT_PEN) != hs):
        return 0
    return 1


# ==========================================================================
# retrends.c
# ==========================================================================


def setwendstr(s: str) -> tuple[str, bool]:
    """Returns ``(wendstr, start_match)``."""
    w = s
    if w.endswith(HARDSHORT):
        w = w[:-1]
    start_match = False
    if w.endswith("-") and s:
        start_match = True
        w = w[:-1]
    return stripacc(w)[0], start_match


def endstrcmp(wendstr: str, haveendstr: str, start_match: bool) -> int:
    if start_match:
        wlen = len(wendstr)
        out = []
        hp = 0
        i = 0
        while i < wlen:
            c = at(haveendstr, hp)
            if hp >= len(haveendstr):
                break  # C reads past the terminator here
            if not isalpha(c) and wendstr[i] != c:
                hp += 1
                continue
            out.append(c)
            hp += 1
            i += 1
        haveendstr = "".join(out)
    return dictstrcmp(wendstr, haveendstr)


def stripquantacc(s: str) -> str:
    return stripacc(stripquant(s))[0]


def noaccstrcmp(w: str, h: str) -> int:
    return strcmp(stripquantacc(w), stripquantacc(h))


def has_quantacc(s: str) -> int:
    r = 0
    if has_quant(s):
        r += 0o10
    if hasaccent(s):
        r += 0o20
    return r


def RightMorphflags(want: GkString, have: GkString) -> int:
    wmf, hmf = want.morphflags, have.morphflags
    if ((has_morphflag(wmf, C.IRREG_COMP) or has_morphflag(wmf, C.IRREG_SUPERL)
         or has_morphflag(wmf, C.NO_COMP))
            and (have.form.degree == C.SUPERLATIVE or have.form.degree == C.COMPARATIVE)):
        return 0
    if has_morphflag(hmf, C.COMP_ONLY) and not has_morphflag(wmf, C.HAS_PREVERB):
        if not has_morphflag(wmf, C.IS_DERIV):
            return 0
    if has_morphflag(hmf, C.NOT_IN_COMPOSITION) and has_morphflag(wmf, C.HAS_PREVERB):
        if not has_morphflag(wmf, C.IS_DERIV):
            return 0
    return 1


def WantGkEnd(wantend: GkString, haveend: GkString, writeflag: bool, strict: int) -> int:
    """0: don't want; 1: want; < 0: past the wanted string in a sorted list."""
    wf = wantend.form
    hf = haveend.form
    wmood, hmood = wf.mood, hf.mood
    wvoice, hvoice = wf.voice, hf.voice
    wtense, htense = wf.tense, hf.tense
    wgender, hgender = wf.gender, hf.gender
    wdegree, hdegree = wf.degree, hf.degree
    wcase, hcase = wf.case, hf.case
    wperson, hperson = wf.person, hf.person
    wnumber, hnumber = wf.number, hf.number
    wform_voice = wvoice

    wendstr, start_match = setwendstr(wantend.gkstring)
    if wmood and hmood != wmood:
        if hmood or strict:
            return 0
    if (wantend.stemtype & C.PPARTMASK) == C.PP_PF:
        wvoice = C.ACTIVE
        wform_voice = C.ACTIVE
    if wvoice:
        if not (wform_voice & hvoice):
            if hvoice or strict:
                return 0
        else:
            if writeflag:
                hf.set_voice(wvoice)
    if wtense and htense != wtense:
        if htense or strict:
            return 0
    if wgender:
        if hgender and not (wgender & hgender):
            return 0
        if writeflag:
            if wgender & hgender:
                hf.set_gender(wgender & hgender)
            else:
                hf.set_gender(wgender)
    if wcase:
        if not (wcase & hcase):
            if hcase or strict:
                return 0
        if writeflag:
            hf.set_case(wcase & hcase)
    if wperson and hperson != wperson:
        if hperson or strict:
            return 0
    if wnumber and hnumber != wnumber:
        if hnumber or strict:
            return 0
    if wendstr and strict:
        hendstr = haveend.gkstring
        compval = endstrcmp(wendstr, hendstr, start_match)
        if compval:
            if compval < 0 and noaccstrcmp(wendstr, hendstr):
                return compval
            if has_quantacc(hendstr) != has_quantacc(wendstr):
                compval = endstrcmp(wendstr, stripquantacc(hendstr), start_match)
                if compval:
                    return 0
            else:
                return 0
        else:
            if hasaccent(wendstr):
                if strcmp(stripquant(wendstr), stripquant(hendstr)):
                    return 0
    if not EuphEnd(wantend, haveend, strict):
        return 0
    if AndDialect(haveend.dialect, wantend.dialect) < 0:
        return 0
    if wdegree:
        if hdegree and wdegree != hdegree and strict:
            return 0
        if writeflag:
            hf.set_degree(wdegree)
    if not RightMorphflags(wantend, haveend):
        return 0
    return 1


def NoWantGkEnd(skipend: GkString, haveend: GkString, strict: int) -> int:
    if skipend.dialect:
        if not haveend.dialect:
            return 0
        if AndDialect(skipend.dialect, haveend.dialect) > 0:
            return 1
    f = skipend.form
    if (not skipend.gkstring and not f.mood and not f.tense and not f.voice and not f.number
            and not f.person and not f.gender and not f.case and not skipend.stemtype
            and no_morphflag(skipend.morphflags)):
        return 0
    return 0 if WantGkEnd(skipend, haveend, False, strict) <= 0 else 1


def AddNewEnd(gstrings: list[GkString], newg: GkString) -> None:
    """Insert ``newg`` (a fresh copy) keeping the C order (descending CompGkString)."""
    from .gkstring import CompGkString

    sofar = len(gstrings)
    if sofar == 0:
        gstrings.append(newg)
        return
    gstrings.append(None)  # type: ignore[arg-type]
    for i in range(sofar, 0, -1):
        if CompGkString(gstrings[i - 1], newg) > 0:
            gstrings[i] = newg
            return
        gstrings[i] = gstrings[i - 1]
    gstrings[0] = newg


def RetrCompEnds(want: GkString, avoid: GkString) -> list[GkString] | None:
    current = GetCurrentEndList(want)
    ends: list[GkString] = []
    if current:
        for tmpl in current:
            cur = tmpl.copy()
            rval = WantGkEnd(want, cur, True, True)
            avoidrval = NoWantGkEnd(avoid, cur, 0)
            if rval < 0 or avoidrval:
                break
            if rval and not avoidrval:
                cur.stemtype = want.stemtype
                AddNewEnd(ends, cur)
    return ends or None


def _is_group_name(g: GkString) -> bool:
    """``Is_group_name``: flag 110 lies past the 12 morphflag bytes, so C reads
    byte 13, which is ``st_domains[1]`` (bit 0x20). Domain codes are
    ``n | PROSEAUTHOR``, so a second domain such as "*xen." (32|64) sets it."""
    return len(g.domains) > 1 and bool(ord(g.domains[1]) & 0x20)


@lru_cache(maxsize=8192)
def chckendings(endstr: str | None, restricts: str, stemstr: str | None, prevbstr: str | None,
                dial: int) -> tuple[GkString, ...] | None:
    """Endings compatible with a stem's ``restricts`` keys (and ``endstr``, if given).

    Pure function of its arguments, so it is memoized; callers must treat the
    returned GkStrings as read-only (copy before modifying)."""
    want, avoid = GkString(), GkString()
    ScanAsciiKeys(restricts, GkWord(), want, avoid)
    if not want.stemtype:
        return None
    if endstr is not None:
        want.gkstring = endstr
    if stemstr is not None:
        markstem(stemstr, want)
    if dial:
        want.dialect |= dial
    else:
        want.dialect = dial
    if prevbstr:
        want.morphflags = add_morphflag(want.morphflags, C.HAS_PREVERB)
    if has_morphflag(want.morphflags, C.PERS_NAME):
        if not want.form.number:
            want.form.number = C.SINGULAR
    if _is_group_name(want):
        if not want.form.number:
            want.form.number = C.PLURAL
    ends = RetrCompEnds(want, avoid)
    return tuple(ends) if ends else None


def EndingOk(keys: str, gstr: GkString, avoidgstr: GkString, wantderiv: int) -> int:
    cur = GkString()
    ScanAsciiKeys(keys, GkWord(), cur, avoidgstr)
    if wantderiv:
        if not gstr.derivtype:
            return 0
        if gstr.derivtype != cur.derivtype:
            return 0
    good = WantGkEnd(gstr, cur, False, 0) > 0 and NoWantGkEnd(avoidgstr, cur, 1) == 0
    if good:
        cf, gf = cur.form, gstr.form
        if cf.voice:
            gf.set_voice(cf.voice)
        case1, case2 = cf.case, gf.case
        if case1 & case2:
            gf.set_case(case1 & case2)
        elif case1 and not case2:
            gf.set_case(case1)
        if cf.number:
            gf.set_number(cf.number)
        if cf.person:
            gf.set_person(cf.person)
        g1, g2 = cf.gender, gf.gender
        if g1 & g2:
            gf.set_gender(g1 & g2)
        elif g1 and not g2:
            gf.set_gender(g1)
        d1, d2 = cur.dialect, gstr.dialect
        if d1 & d2:
            gstr.dialect = d1 & d2
        elif d1 and not d2:
            gstr.dialect = d1
        gstr.morphflags |= cur.morphflags
    return int(good)


def CompatKeys(keys1: str, keys2: str, gstr: GkString) -> int:
    """Are stem keys ``keys1`` compatible with deriv keys ``keys2``? Fills ``gstr``."""
    w = GkWord()
    is_deriv = has_morphflag(gstr.morphflags, C.IS_DERIV)
    g = GkString()
    g2 = GkString()
    gstr.assign(GkString())
    if is_deriv:
        gstr.morphflags = add_morphflag(gstr.morphflags, C.IS_DERIV)
    ScanAsciiKeys(keys1, w, gstr, None)
    ScanAsciiKeys(keys2, w, g2, None)
    rval = EndingOk(keys2, gstr, g, 1)
    if rval:
        if g2.form.tense:
            gstr.form.set_tense(g2.form.tense)
        if g2.form.mood:
            gstr.form.set_mood(g2.form.mood)
        if g2.form.voice:
            gstr.form.set_voice(g2.form.voice)
    return rval
