"""Port of the runtime parts of ``src/gkdict``: ``dictio.c`` and ``derivio.c``.

``compnoun.c`` is only reachable behind ``if (... && 0)`` in checknom.c and is
not ported.
"""

from __future__ import annotations

from . import consts as C
from .gkends import CompatKeys, chckdvend, chckvstem
from .gkstring import GkString, GkWord, add_morphflag, has_morphflag, zap_morphflag
from .greeklib import (
    Is_cons,
    Is_rei_char,
    Is_vowel,
    Xstrncat,
    at,
    has_diaeresis,
    isalpha,
    stripacc,
    stripdiaer,
    stripmetachars,
    stripquant,
)
from .morphkeys import ScanAsciiKeys, SprintGkFlags, nextkey
from .morphlib import redupit2, simpleredupit, un_redupl, unaugment
from . import stemlib

LONGSTRING = C.LONGSTRING

# ==========================================================================
# dictio.c
# ==========================================================================


def _keys(found: str | None) -> tuple[int, str]:
    return (1, found) if found is not None else (0, "")


def chckirrverb(irregstr: str) -> tuple[int, str]:
    workstem = stripacc(stripmetachars("1" + irregstr))[0]
    return _keys(chckvstem(workstem))


def chckindecl(indeclstr: str) -> tuple[int, str]:
    tmp = stripacc(stripdiaer(stripquant("2" + indeclstr)))[0]
    return _keys(stemlib.nom_index().lookup(tmp, exact_match=False))


def chckderiv(derivstr: str) -> tuple[int, str]:
    tmp = stripdiaer(stripquant("3" + derivstr))
    return _keys(chckvstem(tmp))


def chckstem(stemstr: str, is_nom: bool) -> tuple[int, str, str]:
    """Returns ``(nhits, stemkeys, stemstr)``; C strips quantity and diaeresis
    from the caller's ``stemstr`` in place."""
    stemstr = stripdiaer(stripquant(stemstr))
    if is_nom:
        if not stemstr:
            return 0, "", stemstr
        rval, keys = _keys(stemlib.nom_index().lookup(stemstr, exact_match=False))
        return rval, keys, stemstr
    rval, stemkeys = _keys(chckvstem(stemstr))
    rval2, tmpkeys = checkforderiv(stemstr)
    if rval2:
        if rval:
            stemkeys = Xstrncat(stemkeys, " ", LONGSTRING)
        stemkeys = Xstrncat(stemkeys, tmpkeys, LONGSTRING)
    return rval + rval2, stemkeys, stemstr


# ==========================================================================
# derivio.c
# ==========================================================================


def checkforderiv(stemstr: str) -> tuple[int, str]:
    rval, stemkeys = checkforderiv2(stemstr, "", "")
    rval2, stemkeys2 = checkforredupderiv(stemstr)
    if rval2:
        if stemkeys:
            stemkeys += " "
        stemkeys += stemkeys2
    return rval + rval2, stemkeys


def checkforredupderiv(stemstr: str) -> tuple[int, str]:
    if Is_cons(at(stemstr, 0)):
        ok, noredup = un_redupl(stemstr, "e")
        if not ok:
            return 0, ""
        return checkforderiv2(noredup, "redupl", "")
    return checkaugredup(stemstr)


MAXREDUPLS = 4


def checkaugredup(stemstr: str) -> tuple[int, str]:
    stemkeys = ""
    hits = 0
    if stemstr.startswith("e)") and not Is_cons(at(stemstr, 3)):
        if at(stemstr, 2) not in ("z", "c", "y"):
            return 0, stemkeys
    tstem = [GkString() for _ in range(MAXREDUPLS)]
    tqstem = [GkString() for _ in range(MAXREDUPLS)]
    n = unaugment(stemstr, tstem, tqstem, MAXREDUPLS, C.ALL_DIAL, True, True)
    for i in range(n):
        tmpkeys = SprintGkFlags(tstem[i], "\t", True)
        tempstem = tstem[i].gkstring
        had_redupl = "syll_aug" if has_morphflag(tstem[i].morphflags, C.SYLL_AUGMENT) else "temp_aug"
        if tmpkeys:
            had_redupl += " " + tmpkeys
        found, tmpkeys = checkforderiv2(tempstem, had_redupl, tqstem[i].gkstring)
        if found:
            if stemkeys:
                stemkeys = Xstrncat(stemkeys, " ", LONGSTRING)
            stemkeys = Xstrncat(stemkeys, tmpkeys, LONGSTRING)
            hits += 1
    return hits, stemkeys


def checkforderiv2(stemstr: str, had_redupl: str, redupstem: str) -> tuple[int, str]:
    """Returns ``(sofar, stemkeys)``. If nothing is found, ``stemkeys`` keeps
    whatever the last deriv-ending lookup left there, as in C."""
    sofar = 0
    resbuf = ""
    _r, stemkeys = _keys(chckdvend("*"))
    found, derivkeys2 = chckderiv(stemstr)
    if found:
        n, resbuf = checkcomderivs(stemkeys, stemstr, "", derivkeys2, resbuf, had_redupl, redupstem)
        if n:
            sofar += 1
    ep = len(stemstr) - 1
    while ep > 0:
        found_end, stemkeys = _keys(chckdvend(stemstr[ep:]))
        if found_end:
            derivstr = stemstr[:ep]
            found, derivkeys2 = chckderiv(derivstr)
            if found:
                n, resbuf = checkcomderivs(stemkeys, derivstr, stemstr[ep:], derivkeys2, resbuf,
                                           had_redupl, redupstem)
                if n:
                    sofar += 1
        ep -= 1
    if sofar:
        stemkeys = resbuf
    return sofar, stemkeys


def checkcomderivs(derivs: str, defstem: str, suffix: str, lemmkeys: str, nkeys: str,
                   had_redupl: str, redupstem: str) -> tuple[int, str]:
    rval = 0
    cur = lemmkeys
    while True:
        nk = nextkey(cur)
        if nk is None:
            break
        lkey, cur = nk
        n, nkeys = checkcomderiv(derivs, defstem, suffix, lkey, nkeys, had_redupl, redupstem)
        rval += n
    return rval, nkeys


def checkcomderiv(derivstr: str, defstem: str, suffix: str, lkeys: str, rkeys: str,
                  had_redupl: str, redupstem: str) -> tuple[int, str]:
    asuffkeys = derivstr
    tmpsuff = suffix
    markedstem = 0
    tmpdstem, _, rest = lkeys.partition(":")
    lemma, _, dstemkeys = rest.partition(":")
    dstemkeys = dstemkeys.replace(":", " ")
    if tmpdstem:
        markedstem += 1
    else:
        tmpdstem = defstem
    if had_redupl and Is_vowel(at(tmpdstem, 0)) and not redupstem:
        return checkmultredups(asuffkeys, tmpdstem, dstemkeys, tmpsuff, lemma, lkeys, rkeys,
                               had_redupl, markedstem)
    if had_redupl:
        if redupstem:
            markedstem += 1
            tmpdstem = redupstem
            tmpsuff = ""
        else:
            tmpdstem = simpleredupit(tmpdstem, False, "e")
    return checkcomderiv2(asuffkeys, tmpdstem, dstemkeys, tmpsuff, lemma, lkeys, rkeys,
                          had_redupl, markedstem)


def checkmultredups(asuffkeys: str, dstem: str, dstemkeys: str, suffix: str, lemma: str,
                    lkeys: str, rkeys: str, had_redupl: str, markedstem: int) -> tuple[int, str]:
    rval = 0
    forms = [GkWord() for _ in range(6)]
    gstr = GkString()
    forms[0].workword = dstem
    gstr.dialect = 0
    ScanAsciiKeys(dstemkeys, forms[0], gstr, None)
    forms[0].dialect = gstr.dialect
    got = redupit2(forms, 0, False, "e", 5)
    for i in range(got):
        gstr.dialect = forms[i].dialect
        cur = SprintGkFlags(gstr, " ", True)
        n, rkeys = checkcomderiv2(asuffkeys, forms[i].workword, cur, suffix, lemma, lkeys, rkeys,
                                  had_redupl, markedstem)
        rval += n
    return rval, rkeys


def _is_perfect(st: int) -> bool:
    p = st & C.PPARTMASK
    return p in (C.PP_PP, C.PP_PF, C.PP_FP)


def checkcomderiv2(asuffkeys: str, dstem: str, dstemkeys: str, suffix: str, lemma: str,
                   lkeys: str, rkeys: str, had_redupl: str, markedstem: int) -> tuple[int, str]:
    rval = 0
    gstr = GkString()
    dbuf = asuffkeys
    while True:
        nk = nextkey(dbuf)
        if nk is None:
            break
        derivsuff, dbuf = nk
        if derivsuff and derivsuff[0] != ":":
            head, _, rest = derivsuff[1:].partition(":")
            tmpdsuff = derivsuff[0] + head
            derivsuff = rest.replace(":", " ")
            markedstem += 1
        else:
            tmpdsuff = suffix
            derivsuff = derivsuff.replace(":", " ")
        stembuf = dstem + tmpdsuff if markedstem else ""
        if DstemTakesDsuff(derivsuff, dstemkeys, gstr, dstem, tmpdsuff):
            if not had_redupl and _is_perfect(gstr.stemtype):
                continue
            if had_redupl and not _is_perfect(gstr.stemtype):
                continue
            if had_redupl.startswith("syll_aug") and not has_morphflag(gstr.morphflags, C.SYLL_AUGMENT):
                continue
            if rkeys:
                rkeys = Xstrncat(rkeys, " ", LONGSTRING)
            if had_redupl:
                gstr.morphflags = add_morphflag(gstr.morphflags, C.REDUPL)
                ScanAsciiKeys(had_redupl, GkWord(), gstr, None)
            tmp1 = SprintGkFlags(gstr, ":", True)
            rkeys = Xstrncat(rkeys, f"{stembuf}:{lemma}{tmp1}", LONGSTRING)
            rval += 1
    return rval, rkeys


def DstemTakesDsuff(dsuffkeys: str, dstemkeys: str, gstr: GkString, defstem: str,
                    derivstr: str) -> int:
    gstr.morphflags = add_morphflag(gstr.morphflags, C.IS_DERIV)
    if has_diaeresis(derivstr) and not ends_in_vowel(defstem):
        return 0
    rval = CompatKeys(dsuffkeys, dstemkeys, gstr)
    gstr.morphflags = zap_morphflag(gstr.morphflags, C.IS_DERIV)
    if not rval:
        return 0
    if derivstr.startswith("a_") and not Is_rei_char(defstem[-1:] or "\0") and need_rei_alpha(dsuffkeys):
        rval = 0
    return rval


def need_rei_alpha(dsuffkeys: str) -> int:
    g = GkString()
    ScanAsciiKeys(dsuffkeys, GkWord(), g, None)
    return 1 if has_morphflag(g.morphflags, C.R_E_I_ALPHA) else 0


def ends_in_vowel(s: str) -> bool:
    p = len(s) - 1
    while p >= 0 and not isalpha(s[p]):
        p -= 1
    return Is_vowel(at(s, p)) if p >= 0 else False
