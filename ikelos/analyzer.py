"""Port of the Greek analyzer: ``src/anal/{checkstring,checkword,checkindecl,
checknom,checkverb,prvb,checkhalf1,checkstem,checkdict,checkirreg,checkcrasis,
checkgenwds}.c`` and the generator ``src/gener/genwd.c``.

Morpheus analyzes by generation: it segments the word into (preverb) + stem +
ending, looks the stem up, regenerates every form that stem + compatible
endings can produce, and keeps the generated forms that match the input.

C passes ``gk_word`` structs by value (struct copies that share the analysis
array pointer) and by pointer; here ``GkWord.copy()`` / ``assign()`` reproduce
those semantics, and ``GkWord.analyses`` (a fixed list of slots) plus
``GkWord.totanal`` reproduce the shared ``gk_analysis`` buffer.
"""

from __future__ import annotations

from . import consts as C
from .gkdict import chckindecl, chckirrverb, chckstem
from .gkends import chckcmpvb, chckendings, chcknend, chckvend
from .gkstring import (
    AndDialect,
    GkString,
    GkWord,
    add_morphflag,
    eq_forminfo,
    has_morphflag,
    zap_morphflag,
    _short,
)
from .greeklib import (
    C_ERR,
    MAXWORDSIZE,
    NOBREATH,
    ROUGHBR,
    SMOOTHBR,
    ULTIMA,
    Is_accent,
    Is_asp,
    Is_cons,
    Is_vowel,
    Xstrncat,
    Xstrncmp,
    addbreath,
    at,
    beta_tolower,
    checkaccent,
    getbreath,
    hasaccent,
    is_blank,
    is_substring,
    isalpha,
    isspace,
    isupper,
    naccents,
    nsylls,
    starts_w_diphth,
    stripacc,
    stripacute,
    stripbreath,
    stripdiaer,
    stripmetachars,
    stripquant,
    stripstemsep,
    standword,
    zap2acc,
    zap_extra_breath,
)
from .morphkeys import ScanAsciiKeys, nextkey
from .morphlib import (
    CombPbStem,
    FixPersAcc,
    FixRecAcc,
    add_augment,
    cmpend,
    is_preverb,
    needs_augment,
    poss_thirdmono,
    rstprevb,
    stand_phonetics,
)
from .stemlib import morphstrcmp

LONGSTRING = C.LONGSTRING
MAXANALYSES = C.MAXANALYSES
ANALYSIS = 0o4  # modes.h
INDECL = C.INDECL
MAX_FORM_VARIANTS = 12

WantDialects = C.ALL_DIAL


def _sacc(s: str) -> str:
    return stripacc(s)[0]


def _cpanal(dst: GkWord, src: GkWord) -> None:
    """``CpGkAnal``."""
    dst.totanal = src.totanal
    dst.analyses = src.analyses


def parsefield(s: str, c: str, maxlen: int = LONGSTRING) -> tuple[str, str]:
    """``parsefield``: field up to ``c`` or whitespace. Returns (field, rest);
    rest is "" when the field ended at whitespace."""
    i, n = 0, len(s)
    out = []
    while i < n and s[i] != c and not isspace(s[i]):
        out.append(s[i])
        i += 1
        if len(out) > maxlen:
            while i < n and not isspace(s[i]):
                i += 1
            break
    buf = "".join(out[: maxlen + 1])
    if i < n and isspace(s[i]):
        return buf, ""
    if i < n:
        i += 1
    return buf, s[i:]


# ==========================================================================
# checkstring.c
# ==========================================================================


def checkstring(string: str, prntflags: int) -> GkWord | None:
    """Analyze one word. Returns the GkWord (``totanal`` > 0 on success) or None."""
    if is_blank(string):
        return None
    if len(string) >= MAXWORDSIZE:
        return None
    g = GkWord()
    g.dialect = WantDialects
    g.workword = string
    g.prntflags = prntflags
    g.rawword = g.workword
    g.workword = standword(g.workword)
    stand_phonetics(g)
    checkstring1(g)
    return g


def checkstring1(g: GkWord) -> None:
    if g.workword[:1] == "'":
        savework = g.workword
        g.workword = Xstrncat("e)", savework[1:], MAXWORDSIZE)
        n = checkstring2(g)
        if not n:
            tmp = savework
            if hasaccent(tmp):
                tmp = _sacc(tmp)
            g.workword = Xstrncat("e)/", tmp[1:], MAXWORDSIZE)
            n = checkstring2(g)
        g.workword = Xstrncat("a)", savework[1:], MAXWORDSIZE)
        n = checkstring2(g)
        if not n and not hasaccent(savework):
            g.workword = Xstrncat("a)/", savework[1:], MAXWORDSIZE)
            n = checkstring2(g)
    else:
        checkstring2(g)


def checkstring2(g: GkWord) -> int:
    rval = checkstring3(g)
    if not rval and not g.totanal:
        rval = checkcrasis(g)
    d = AndDialect(g.dialect, C.HOMERIC | C.IONIC)
    if d >= 0 or not (g.dialect & C.PROSE):
        olddial = g.dialect
        m = g.morphflags
        m2 = g.morphflags
        g.morphflags = add_morphflag(g.morphflags, C.UNAUGMENTED)
        g.stem.morphflags = add_morphflag(g.stem.morphflags, C.UNAUGMENTED)
        if not (g.dialect & (C.IONIC | C.PROSE)):
            g.dialect = _short(g.dialect | C.IONIC | C.EPIC)
        g.dialect = _short(g.dialect | C.IONIC | C.EPIC)
        rval = checkstring3(g)
        if not rval and not g.totanal:
            rval = checkcrasis(g)
        g.dialect = olddial
        g.morphflags = m
        g.stem.morphflags = m2
        if not rval and not (g.dialect & (C.IONIC | C.PROSE)):
            g.morphflags = add_morphflag(g.morphflags, C.POETIC)
            g.morphflags = add_morphflag(g.morphflags, C.UNAUGMENTED)
            g.stem.morphflags = add_morphflag(g.stem.morphflags, C.UNAUGMENTED)
            rval = checkstring3(g)
            if not rval and not g.totanal:
                rval = checkcrasis(g)
            g.dialect = olddial
            g.morphflags = m
            g.stem.morphflags = m2
    return g.totanal


GreekSuff = (("per", C.NOUNSTEM | C.ADJSTEM),)


def checkstring3(g: GkWord) -> int:
    saveword = g.workword
    rval = checkstring4(g)
    s0 = at(g.workword, 0)
    if (isupper(s0) or s0 == "*") and not (g.prntflags & C.STRICT_CASE):
        g.workword = beta_tolower(g.workword)
        rval = checkstring4(g)
        if rval > 0:
            g.workword = saveword
            return rval
        g.workword = saveword
    if g.workword.endswith("'"):
        rval += checkapostr(g)
        if rval:
            g.workword = saveword
            return rval
    for enclitic, stype in GreekSuff:
        if g.totanal:
            break
        ok, workword = cmpend(g.workword, enclitic)
        if ok:
            g.workword = workword
            rval += checkstring3(g)
            if stype:
                slots = g.analyses
                newi = 0
                for i in range(g.totanal):
                    if slots[i].stemtype & stype:
                        if newi != i:
                            slots[newi].assign(slots[i])
                        newi += 1
                g.totanal = newi
            if rval:
                g.workword = saveword
                return rval
            g.workword = saveword
    g.workword = saveword
    return rval


def checkstring4(g: GkWord) -> int:
    rval = checkword(g)
    if rval > 0:
        return rval
    saveword = g.workword
    i = saveword.find("cu")
    if i >= 0:  # has_cun
        g.workword = saveword[:i] + "s" + saveword[i + 1:]
        rval += checkindecl(g)
        rval += checknom(g)
        g.workword = saveword
        if rval > 0:
            return rval
    i = saveword.find("tt")
    if i >= 0:  # has_tt
        g.workword = saveword[:i] + "ss" + saveword[i + 2:]
        rval = checkstring4(g)
        g.workword = saveword
        if rval > 0:
            return rval
    return 0


def _add_apostrvowel(word: str, end: int, vow: str) -> str:
    word = word[:end] + vow
    if naccents(word) == 0:
        word = Xstrncat(word, "/", MAXWORDSIZE)
    if vow[0] in ("u", "i", "a"):
        word = Xstrncat(word, "^", MAXWORDSIZE)
    return word


def checkapostr(g: GkWord) -> int:
    saveword = g.workword
    w = g.workword
    p = len(w) - 1
    if at(w, p) != "'":
        return 0
    rval = 0
    if p > 0 and w[p - 1] in ("q", "x", "f"):
        lw = list(w)
        if w[p - 1] == "q":
            lw[p - 1] = "t"
            if p - 2 >= 0 and w[p - 2] == "x":
                lw[p - 2] = "k"
        elif w[p - 1] == "x":
            lw[p - 1] = "k"
        else:
            lw[p - 1] = "p"
        g.workword = "".join(lw)
        rval += checkapostr(g)
        g.workword = saveword
    num_sylls = nsylls(g.workword)
    for vow in ("a", "i", "o"):
        if num_sylls >= 1:
            g.workword = _add_apostrvowel(g.workword, p, vow)
            curval = checkstring3(g)
            g.workword = saveword
            rval += curval
    g.workword = _add_apostrvowel(g.workword, p, "e")
    curval = checkstring3(g)
    g.workword = saveword
    rval += curval
    if num_sylls >= 1:
        g.workword = _add_apostrvowel(g.workword, p, "ai")
        tmpmf = g.morphflags
        g.morphflags = add_morphflag(g.morphflags, C.POETIC)
        curval = checkstring3(g)
        g.workword = saveword
        rval += curval
        g.morphflags = tmpmf
    if not rval:
        g.workword = saveword
        _r, syllno, accnum = checkaccent(g.workword)
        if syllno == ULTIMA and accnum != C_ERR:
            g.workword = _sacc(g.workword)
            rval = checkapostr(g)
        g.workword = saveword
    return rval


# ==========================================================================
# checkword.c, checkindecl.c, checknom.c
# ==========================================================================


def checkword(g: GkWord) -> int:
    rval = 0
    if not has_morphflag(g.stem.morphflags, C.UNAUGMENTED):
        rval += checkindecl(g)
    if not has_morphflag(g.stem.morphflags, C.UNAUGMENTED):
        rval += checknom(g)
    rval += checkverb(g)
    return rval


def checkindecl(g: GkWord) -> int:
    if g.prntflags & C.VERBS_ONLY:
        return 0
    tmpword = g.workword
    rval, keys = chckindecl(tmpword)
    if not rval:
        return 0
    hits = 0
    k = 0
    while k < len(keys):
        sp = keys[k:]
        workword, sp = parsefield(sp, ":", MAXWORDSIZE)
        if not workword:
            workword = tmpword
        g.lemma, sp = parsefield(sp, ":", MAXWORDSIZE)
        stemkeys, sp = parsefield(sp, " ", LONGSTRING)
        stemkeys = stemkeys.replace(":", " ")
        g.stem.gkstring = workword
        forms = GenIrregForm(g, stemkeys, INDECL)
        if forms:
            hits += CheckGenWords(g, forms)
        while k < len(keys) and not isspace(keys[k]):
            k += 1
        while k < len(keys) and isspace(keys[k]):
            k += 1
    return hits


def checknom(g: GkWord) -> int:
    if g.prntflags & C.VERBS_ONLY:
        return 0
    return checkregnom(g)


def checkregnom(g: GkWord) -> int:
    workword = g.workword
    rval = 0
    g.endstring.gkstring = "*"
    g.stem.gkstring = workword
    rval += gotnom(g)
    for wp in range(len(workword)):
        g.endstring.gkstring = workword[wp:]
        g.stem.gkstring = workword[:wp]
        rval += gotnom(g)
    return rval


def gotnom(g: GkWord) -> int:
    rval = 0
    g.endstring.gkstring = _sacc(g.endstring.gkstring)
    endkeys = chcknend(g.endstring.gkstring)
    if endkeys is not None:
        curstem = GkString(_sacc(g.stem.gkstring))
        ok, stemkeys, curstem.gkstring = stemexists(curstem.gkstring, endkeys, True)
        if ok:
            rval += StemWorks(g, stemkeys, curstem)
    return rval


# ==========================================================================
# checkverb.c, prvb.c
# ==========================================================================


def checkverb(g: GkWord) -> int:
    workword = g.workword
    rval = 0
    wp = 0
    half1 = ""
    n = len(workword)
    while wp < n:
        g.stem.gkstring = workword[wp:]
        g.rawprvb = half1
        rval += try_irregvb(g)
        g.preverb.gkstring = ""
        g.rawprvb = ""
        g.stem.gkstring = half1
        g.endstring.gkstring = workword[wp:]
        rval += analyzed_verb(g)
        half1 += workword[wp]
        wp += 1
        while wp < n and not isalpha(workword[wp]) and workword[wp] not in "|()":
            wp += 1
    if not rval:
        g.preverb.gkstring = ""
        g.endstring.gkstring = "*"
        g.stem.gkstring = workword
        rval += analyzed_verb(g)
    return rval


def analyzed_verb(g: GkWord) -> int:
    tmpend = stripquant(_sacc(g.endstring.gkstring))
    endkeys = chckvend(tmpend)
    if endkeys is None:
        return 0
    tmp = g.copy()
    tmp.stem.gkstring = _sacc(tmp.stem.gkstring)
    rval = strippreverb(tmp, endkeys, 0)
    if rval:
        _cpanal(g, tmp)
    return rval


def doubled_cons(s: str) -> bool:
    c0 = at(s, 0)
    if c0 == "r":
        return False
    if not Is_cons(c0):
        return False
    if Is_cons(at(s, 2)):
        return False
    return c0 == at(s, 1)


def strippreverb(g: GkWord, endkeys: str, rval: int) -> int:
    if checkhalf1(g, endkeys):
        rval += 1
    work = g.copy()
    curstem = work.stem.gkstring
    a = 0
    while True:
        work.preverb.morphflags = 0
        if a >= len(curstem):
            return rval
        a += 1
        g.rawprvb = curstem[:a]
        g.stem.gkstring = curstem[a:]
        if Is_accent(at(curstem, a)):
            continue
        work = g.copy()
        ok, work.preverb.gkstring = is_preverb(work.rawprvb, work.preverb.gkstring, work.preverb)
        if not ok:
            continue
        if not work.stem.gkstring:
            continue
        ok, work.stem.gkstring, work.preverb.morphflags = CombPbStem(
            work.rawprvb, work.stem.gkstring, work.dialect, work.preverb.morphflags)
        if not ok:
            continue
        if has_morphflag(work.preverb.morphflags, C.APOCOPE) and (work.dialect & C.PROSE):
            continue
        if doubled_cons(work.stem.gkstring):
            if AndDialect(work.dialect, C.EPIC) < 0:
                continue
            if work.dialect & C.PROSE:
                continue
            work.stem.gkstring = work.stem.gkstring[1:]
            work.preverb.morphflags = add_morphflag(work.preverb.morphflags, C.DOUBLED_CONS)
            work.stem.dialect = _short(work.stem.dialect | C.EPIC | C.POETIC)
        if checkhalf1(work, endkeys):
            _cpanal(g, work)
            rval += 1


# ==========================================================================
# checkhalf1.c
# ==========================================================================


def checkhalf1(g: GkWord, endkeys: str) -> int:
    rval = 0
    stem = g.stem.gkstring
    savestem = stem
    if at(stem, 0) == "r" and getbreath(stem) == NOBREATH:
        g.stem.gkstring = Xstrncat("r(", stem[1:], MAXWORDSIZE)
        return checkhalf2(g, endkeys)
    if Is_vowel(at(stem, 0)) and getbreath(stem) == NOBREATH:
        savestem = g.stem.gkstring
        g.stem.gkstring = addbreath(g.stem.gkstring, ROUGHBR)
        rval += checkhalf2(g, endkeys)
        g.stem.gkstring = savestem
        g.stem.gkstring = addbreath(g.stem.gkstring, SMOOTHBR)
        unasp = False
        if has_morphflag(g.preverb.morphflags, C.UNASP_PREVERB):
            unasp = True
            g.preverb.morphflags = zap_morphflag(g.preverb.morphflags, C.UNASP_PREVERB)
        rval += checkhalf2(g, endkeys)
        if unasp:
            g.preverb.morphflags = add_morphflag(g.preverb.morphflags, C.UNASP_PREVERB)
        if not rval and starts_w_diphth(g.stem.gkstring):
            diaerstem = stripdiaer(savestem[:2]) + "+" + savestem[2:]
            g.stem.gkstring = diaerstem
            g.stem.gkstring = addbreath(g.stem.gkstring, ROUGHBR)
            rval += checkhalf2(g, endkeys)
            g.stem.gkstring = diaerstem
            unasp = False
            if has_morphflag(g.preverb.morphflags, C.UNASP_PREVERB):
                unasp = True
                g.preverb.morphflags = zap_morphflag(g.preverb.morphflags, C.UNASP_PREVERB)
            g.stem.gkstring = addbreath(g.stem.gkstring, SMOOTHBR)
            rval += checkhalf2(g, endkeys)
            if unasp:
                g.preverb.morphflags = add_morphflag(g.preverb.morphflags, C.UNASP_PREVERB)
            g.stem.gkstring = savestem
        return rval
    rval = checkhalf2(g, endkeys)
    if rval:
        return rval
    if g.rawprvb and starts_w_diphth(g.stem.gkstring):
        cbreath = getbreath(g.stem.gkstring)
        g.stem.gkstring = stripbreath(g.stem.gkstring)
        s = g.stem.gkstring
        diaerstem = at(s, 0) + "+" + s[1:]
        diaerstem = addbreath(diaerstem, cbreath)
        g.stem.gkstring = diaerstem
        rval += checkhalf2(g, endkeys)
        g.stem.gkstring = savestem
    if (not rval and g.preverb.gkstring and getbreath(savestem) == SMOOTHBR
            and AndDialect(g.dialect, C.IONIC) >= 0):
        g.morphflags = add_morphflag(g.morphflags, C.UNASP_PREVERB)
        g.stem.gkstring = addbreath(stripbreath(savestem), ROUGHBR)
        rval += checkhalf2(g, endkeys)
        g.stem.gkstring = savestem
        g.morphflags = zap_morphflag(g.morphflags, C.UNASP_PREVERB)
    return rval


MAX_POSS_STEMS = 10


def checkhalf2(g: GkWord, endkeys: str) -> int:
    stems = [GkString() for _ in range(MAX_POSS_STEMS)]
    keys = [""] * MAX_POSS_STEMS
    rval, g.stem.gkstring = checkstem(g.stem.gkstring, endkeys, stems, keys, MAX_POSS_STEMS - 1)
    if rval:
        rval = StemsWork(g, stems, keys, rval)
    return 1 if rval else 0


def StemsWork(g: GkWord, stems: list[GkString], keys: list[str], n: int) -> int:
    savestem = g.stem.gkstring
    result = 0
    for i in range(n):
        result += StemWorks(g, keys[i], stems[i])
    if not result:
        g.stem.gkstring = savestem
    return result


def StemWorks(g: GkWord, posskey: str, possstem: GkString) -> int:
    rval = 0
    workkey = posskey
    while True:
        nk = nextkey(workkey)
        if nk is None:
            break
        curkey, workkey = nk
        rval += checkdict(g, possstem, curkey)
    return rval


# ==========================================================================
# checkstem.c
# ==========================================================================

MAXAUGSTEMS = 12


def checkstem(poss_stem: str, endkeys: str, stemtab: list[GkString], keytab: list[str],
              maxstems: int) -> tuple[int, str]:
    from .morphlib import unaugment

    hits = 0
    tstem = [GkString() for _ in range(MAXAUGSTEMS)]
    tq = [GkString() for _ in range(MAXAUGSTEMS)]
    rval, curkeys, poss_stem = stemexists(poss_stem, endkeys, False)
    if rval and curkeys:
        stemtab[0].gkstring = poss_stem
        keytab[0] = curkeys
        hits += 1
    if Is_cons(at(poss_stem, 0)):
        return hits, poss_stem
    n = unaugment(poss_stem, tstem, tq, MAXAUGSTEMS, C.ALL_DIAL, True, False)
    for i in range(n):
        ok, curkeys, tstem[i].gkstring = stemexists(tstem[i].gkstring, endkeys, False)
        if ok and curkeys:
            while hits >= len(stemtab):
                stemtab.append(GkString())
                keytab.append("")
            stemtab[hits].assign(tstem[i])
            keytab[hits] = curkeys
            hits += 1
    return hits, poss_stem


def stemexists(s: str, endkeys: str, is_nom: bool) -> tuple[int, str, str]:
    """Returns ``(found, stemkeys, s)``; ``s`` comes back stripped of quantity/diaeresis."""
    rval, stemkeys, s = chckstem(s, is_nom)
    if not rval:
        return 0, stemkeys, s
    rval, stemkeys = comstemtypes(s, stemkeys, endkeys)
    return rval, stemkeys, s


def setstemvars(s: str) -> tuple[str, str, str, str]:
    cstem, s = parsefield(s, ":", MAXWORDSIZE)
    clemma, s = parsefield(s, ":", MAXWORDSIZE)
    cstemtype, s = parsefield(s, ":", MAXWORDSIZE)
    ckeys, s = parsefield(s, " ", LONGSTRING)
    return cstem, clemma, cstemtype, ckeys


def comstemtypes(stem: str, stemkeys: str, endkeys: str) -> tuple[int, str]:
    tmp = ""
    k = 0
    n = len(stemkeys)
    while k < n:
        cstem, clemma, cstemtype, stembuf = setstemvars(stemkeys[k:])
        if is_substring(cstemtype, endkeys) >= 0:
            if tmp:
                tmp = Xstrncat(tmp, " ", LONGSTRING)
            tmp = Xstrncat(tmp, clemma, LONGSTRING)
            tmp = Xstrncat(tmp, ":", LONGSTRING)
            tmp = Xstrncat(tmp, cstem if cstem else stem, LONGSTRING)
            tmp = Xstrncat(tmp, ":", LONGSTRING)
            tmp = Xstrncat(tmp, cstemtype, LONGSTRING)
            tmp = Xstrncat(tmp, ":", LONGSTRING)
            if stembuf:
                tmp = Xstrncat(tmp, stembuf, LONGSTRING)
        while k < n and not isspace(stemkeys[k]):
            k += 1
        while k < n and isspace(stemkeys[k]):
            k += 1
    return (1 if tmp else 0), tmp


# ==========================================================================
# checkdict.c
# ==========================================================================


def GetLemmStem(keys: str) -> tuple[str, str, str]:
    """Returns ``(rest, lemma, stem)``."""
    i, n = 0, len(keys)
    if i < n and keys[i] == ":":
        i += 1
    j = i
    while j < n and keys[j] != ":":
        j += 1
    lemma = keys[i:j]
    if j < n and keys[j] == ":":
        j += 1
    k = j
    while k < n and keys[k] != ":":
        k += 1
    stem = keys[j:k]
    if k < n and keys[k] == ":":
        k += 1
    return keys[k:], lemma, stem


def checkdict(g: GkWord, stem: GkString, stemkeys: str) -> int:
    hits = 0
    save = g.copy()
    curkeys = stemkeys
    g.stem.assign(stem)
    if has_morphflag(stem.morphflags, C.SYLL_AUGMENT):
        g.stem.morphflags = zap_morphflag(g.stem.morphflags, C.SYLL_AUGMENT)
        g.morphflags = add_morphflag(g.morphflags, C.SYLL_AUGMENT)
    else:
        g.morphflags = zap_morphflag(g.morphflags, C.SYLL_AUGMENT)
    keyp, g.lemma, g.stem.gkstring = GetLemmStem(curkeys)
    prevb = g.preverb.gkstring
    pbptr = is_substring("pb:", keyp)
    if pbptr > 0 and keyp[pbptr - 1] == "r":
        pbptr = -1
    if pbptr >= 0 and not prevb:
        return 0
    gkforms = None
    finish = False
    if prevb:
        if pbptr < 0:
            keyp = Xstrncat(keyp, ":pb:", LONGSTRING)
            keyp = Xstrncat(keyp, prevb, LONGSTRING)
        else:
            tmppb = keyp[pbptr + 3:]
            if tmppb.endswith(":"):
                tmppb = tmppb[:-1]
            if len(tmppb) > len(prevb) or tmppb != prevb[len(prevb) - len(tmppb):]:
                finish = True
            else:
                keyp = Xstrncat(keyp, ":pb:", LONGSTRING)
                keyp = Xstrncat(keyp, prevb, LONGSTRING)
    if not finish:
        keyp = keyp.replace(":", " ")
        gkforms = GenStemForms(g, keyp, ANALYSIS)
        if not gkforms:
            if (has_morphflag(g.morphflags, C.SUFF_ACC) or nsylls(g.stem.gkstring) == 0
                    or poss_thirdmono(g.stemtype, g.stem.gkstring, g.endstring.gkstring)):
                g.endstring.gkstring = _sacc(g.endstring.gkstring)
                gkforms = GenStemForms(g, keyp, ANALYSIS)
        if not gkforms:
            g.assign(save)
            return 0
        hits += CheckGenWords(g, gkforms)
    g.preverb.assign(save.preverb)
    g.aug1.assign(save.aug1)
    g.stem.assign(save.stem)
    g.endstring.assign(save.endstring)
    return hits


# ==========================================================================
# checkirreg.c
# ==========================================================================


class _Buf:
    """A mutable C char buffer that may alias a GkWord field."""

    __slots__ = ("get", "set")

    def __init__(self, getter, setter):
        self.get = getter
        self.set = setter


def _plain_buf(value: str = "") -> _Buf:
    box = [value]

    def _get():
        return box[0]

    def _set(v):
        box[0] = v

    return _Buf(_get, _set)


def _stem_buf(w: GkWord) -> _Buf:
    def _get():
        return w.stem.gkstring

    def _set(v):
        w.stem.gkstring = v

    return _Buf(_get, _set)


def mfi_prvb(rawprvb: str) -> bool:
    n = len(rawprvb)
    return at(rawprvb, n - 1) == "f" and at(rawprvb, n - 2) == "m"


def try_irregvb(g: GkWord) -> int:
    irrforms = [_plain_buf(), _plain_buf(), _plain_buf()]
    irrkeys = ["", "", ""]
    work = g.copy()
    rawprvb = work.rawprvb
    irr = _stem_buf(work)
    work.preverb.morphflags = 0
    work.preverb.gkstring = ""
    rval = 0
    unasp_prev = False

    def finish(r: int) -> int:
        if r:
            _cpanal(g, work)
        return r

    if rawprvb:
        ok, work.preverb.gkstring = is_preverb(rawprvb, work.preverb.gkstring, work.preverb)
        if not ok:
            return finish(0)
        work.stem.morphflags = add_morphflag(work.stem.morphflags, C.HAS_PREVERB)
    if has_morphflag(work.preverb.morphflags, C.APOCOPE):
        if AndDialect(work.dialect, C.PROSE) > 0:
            return finish(rval)
    if rawprvb:
        ok, newstem, work.preverb.morphflags = CombPbStem(rawprvb, irr.get(), work.dialect,
                                                          work.preverb.morphflags)
        irr.set(newstem)
        if not ok:
            return finish(0)
    work.stem.morphflags |= work.preverb.morphflags
    if not rawprvb or Is_cons(at(irr.get(), 0)):
        rval, irrkeys[0] = chckirrverb(irr.get())
        if rval:
            rval = ChckIrrLemms(work, irr, irrkeys[0])
            return finish(rval)
    if not Is_vowel(at(irr.get(), 0)):
        return finish(rval)
    if getbreath(irr.get()) != NOBREATH:
        rval, irrkeys[0] = chckirrverb(irr.get())
        irrforms[0].set(irr.get() if rval else "")
    saveirrform = irr.get()
    if ((not Is_asp(at(rawprvb, len(rawprvb) - 1))) or mfi_prvb(rawprvb)) and getbreath(irr.get()) == NOBREATH:
        irr.set(addbreath(irr.get(), SMOOTHBR))
        if has_morphflag(work.stem.morphflags, C.UNASP_PREVERB):
            unasp_prev = True
            work.stem.morphflags = zap_morphflag(work.stem.morphflags, C.UNASP_PREVERB)
        r, irrkeys[0] = chckirrverb(irr.get())
        rval += r
        if unasp_prev:
            unasp_prev = False
            work.stem.morphflags = add_morphflag(work.stem.morphflags, C.UNASP_PREVERB)
        irrforms[0].set(irr.get() if rval else "")
    irr.set(saveirrform)
    if getbreath(irr.get()) == NOBREATH and ((not Is_vowel(at(irr.get(), 0))) or rawprvb):
        irr.set(addbreath(irr.get(), ROUGHBR))
        rval, irrkeys[1] = chckirrverb(irr.get())
        if rval:
            irrforms[rval].set(irr.get())
        else:
            irrforms[1].set("")
    irr.set(saveirrform)
    rval = 0
    if irrforms[1].get():
        rval += ChckIrrLemms(work, irrforms[1], irrkeys[1])
    rval += ChckIrrLemms(work, irrforms[0], irrkeys[0])
    return finish(rval)


def ChckIrrLemms(g: GkWord, irr: _Buf, irrkey: str) -> int:
    rval = 0
    curval = 0
    while True:
        nk = nextkey(irrkey)
        if nk is None:
            break
        curlemma, irrkey = nk
        tmp = g.copy()
        tmpword, sp = parsefield(curlemma, ":", LONGSTRING)
        if tmpword:
            irr.set(tmpword)
        else:
            irr.set(stripdiaer(stripquant(_sacc(g.stem.gkstring))))
        tmp.lemma, sp = parsefield(sp, ":", LONGSTRING)
        stemkeys, sp = parsefield(sp, " ", LONGSTRING)
        stemkeys = stemkeys.replace(":", " ")
        curval += CheckIrregForm(tmp, irr.get(), stemkeys)
        if curval:
            _cpanal(g, tmp)
        rval += curval
    return rval


def CheckIrregForm(g: GkWord, stem: str, stemkeys: str) -> int:
    prevb = g.preverb.gkstring
    rval = 0
    stemforms = g.copy()
    stemforms.stem.gkstring = stem
    if prevb:
        pbptr = is_substring(stemkeys, "pb:")  # sic: arguments reversed in C
        if pbptr < 0:
            stemkeys = Xstrncat(stemkeys, " pb:", LONGSTRING)
            stemkeys = Xstrncat(stemkeys, prevb, LONGSTRING)
        elif Xstrncmp("pb:"[pbptr + 3:], prevb, len(prevb)):
            return 0
    forms = GenIrregForm(stemforms, stemkeys, 0)
    savemf = g.morphflags
    if forms:
        rval = CheckGenWords(g, forms)
    g.morphflags = savemf
    return rval


# ==========================================================================
# checkcrasis.c
# ==========================================================================

PossCras = (
    ("*)=w", "*)/a", "w)=", 0), ("*)=w", "*)e", "w)=", 0), ("ka)", "*)a", "kai/", 0),
    ("a(=", "a)/", "o(", 0), ("a(", "a)", "o(", 0), ("a(", "e)", "a(/", 0),
    ("ei(", "ei)", "a(/", 0), ("au(", "au)", "o(", 0), ("dau)", "au)", "de/", 0),
    ("dh)", "e)", "dh/", 0), ("da)", "a)", "dh/", 0), ("hu(", "eu)", "h(", 0),
    ("qat", "e(t", "tou=", 0), ("qa)/", "e(/", "to/", 0), ("qoi)", "i(", "to/", 0),
    ("qai)", "i(", "ta/", 0), ("qou)", "u(", "to/", 0), ("qou(", "e(", "to/", 0),
    ("qou)", "e(", "to/", 0), ("qh)", "h(", "th=|", 0), ("qh)", "h(", "tou=", 0),
    ("qh)", "h(", "to/", 0), ("qa)", "e(", "th=|", 0), ("qa)", "a(", "ta/", 0),
    ("qa)", "e(", "tou=", 0), ("qa/t", "e(/t", "to/", 0), ("kai)", "ai)", "kai/", C.DORIC | C.EPIC),
    ("kei)", "ei)", "kai/", 0), ("kei)", "ei)", "kai/", 0), ("keu)", "eu)", "kai/", 0),
    ("ka)=|", "ei)=", "kai/", 0), ("ka)|", "ai)", "kai/", 0), ("ta)|", "ai)", "ta/", 0),
    ("ka)=", "a)/", "kai/", 0), ("ka)", "a)", "kai/", 0), ("katta", "ta", "kata/", C.DORIC),
    ("kadd", "d", "kata/", C.EPIC), ("ka)", "e)", "kai/", 0), ("kw)", "o)", "kai/", 0),
    ("kw)", "w)", "kai/", 0), ("kou)", "ou)", "kai/", 0), ("kau)", "au)", "kai/", 0),
    ("khu)", "hu)", "kai/", 0), ("moi)", "oi)", "mou", 0), ("ma)", "a)", "mh/", 0),
    ("mh)/", "e)", "mh/", 0), ("mou)", "e)", "mou", 0), ("ou(", "e)", "o(/", 0),
    ("ou(", "o)", "o(", 0), ("ou(", "e(", "o(", 0), ("ou(", "u(", "o(", 0),
    ("qw)/", "o(/", "ta/", 0), ("pottw/s", "tw/s", "poti/", C.DORIC), ("ta)/|", "ai)/", "to/", 0),
    ("ta)=", "a)/", "ta/", 0), ("ta)", "a)", "ta/", 0), ("ta)", "a)", "tou=", 0),
    ("ta)", "a)", "to/", 0), ("ta)/", "*)/a", "to/", 0), ("ta)", "e)", "ta/", 0),
    ("th)", "e)", "th=|", 0), ("tau)", "au)", "tou=", 0), ("tau)", "au)", "to/", 0),
    ("tu/xa)gaqh=|", "a)gaqh=|", "tu/xh|", 0), ("tu/xa)gaqh|", "a)gaqh=|", "tu/xh|", 0),
    ("tw)", "*)a", "tou=", 0), ("tw)", "a)", "tou=", 0), ("tw)", "a)", "tou=", 0),
    ("tw)=", "a)/", "toi/", C.DORIC), ("tw)", "w)", "to/", 0), ("tw)", "h(", "to/", 0),
    ("tw)", "o)", "tw=|", 0), ("sou)", "o(", "sou", 0), ("sou)", "e(", "sou", 0),
    ("sou)", "e)", "sou", 0), ("tou)", "o)", "to/", 0), ("tou)", "e)", "to/", 0),
    ("tou)", "e)", "to/", 0), ("tou)", "e)", "tou=", 0), ("tou)=", "e)/", "tou=", 0),
    ("tou)=", "o)/", "to/", 0), ("tw)", "e)", "tw=|", 0), ("tou)", "ou)", "tou=", 0),
    ("tou)", "e(", "to/", 0), ("tw)u", "au)", "ta/", C.IONIC), ("tw)u", "au)", "to/", C.IONIC),
    ("tw)u", "au)", "tou=", C.IONIC), ("twu)", "au)", "ta/", C.IONIC),
    ("twu)", "au)", "to/", C.IONIC), ("twu)", "au)", "tou=", C.IONIC),
    ("tw)", "a)", "to/", C.IONIC), ("tw)", "a)", "toi/", C.DORIC), ("tau)", "au)", "to/", 0),
    ("ou(", "e)", "o(", 0), ("prou)", "proe", "", 0), ("sumprou", "sumproe", "", 0),
    ("cumprou", "cumproe", "", 0), ("a)ntiprou", "a)ntiproe", "", 0), ("prou", "proe", "", 0),
    ("prou", "proo", "", 0), ("prwu", "proau", "", 0), ("e)gw)=i", "oi)=", "e)gw/", 0),
    ("e)gw)=|", "oi)=", "e)gw/", 0), ("e)gw=|", "oi)=", "e)gw/", 0), ("e)mou)", "e)", "e)moi", 0),
    ("kh)", "E)", "kai/", 0), ("kh)", "e)", "kai/", 0), ("xh)", "h(", "kai/", 0),
    ("xh(", "h(", "kai/", 0), ("xa)", "a(", "kai/", C.DORIC), ("xa)", "e(", "kai/", 0),
    ("xai)", "ai(", "kai/", 0), ("xoi)", "oi(", "kai/", 0), ("xau)", "au(", "kai/", 0),
    ("xou)", "ou(", "kai/", 0), ("xu)", "u(", "kai/", 0), ("xw)", "o(", "kai/", 0),
    ("xw(", "o(", "kai/", 0), ("xw)", "w(", "kai/", 0), ("w(n", "a)n", "o(", 0),
    ("w(/n", "a)/n", "oi(", 0), ("w(u", "au)", "o(", 0), ("wu)", "au)", "o(", 0),
    ("w(u", "au)", "oi(", 0), ("w)=gaqe", "a)gaqe/", "w)=", 0), ("w)=", "a)/", "w)=", 0),
    ("w)|", "oi)", "w)=", 0), ("w)=", "o)/", "w)=", 0), ("w)", "a)", "w)=", 0),
    ("w(=", "a)/", "oi(", 0), ("w)/", "a)/", "w)=", 0),
)


def checkcrasis(g: GkWord) -> int:
    rval = 0
    for munged, wordstart, preword, possdial in PossCras:
        if g.workword.startswith(munged):
            rval += testcrasis(g, munged, wordstart, preword, possdial)
    return rval


def testcrasis(g: GkWord, munged: str, wordstart: str, preword: str, possdial: int) -> int:
    tmp = g.copy()
    saveword = tmp.workword
    tmp.workword = Xstrncat(wordstart, saveword[len(munged):], MAXWORDSIZE)
    tmp.crasis = preword
    tmp.dialect = _short(tmp.dialect | possdial)
    tmp.stem.dialect = _short(tmp.stem.dialect | possdial)
    rval = checkstring3(tmp)
    if rval:
        for i in range(tmp.totanal):
            a = tmp.analyses[i]
            a.dialect = _short(a.dialect | possdial)
        _cpanal(g, tmp)
    return rval


# ==========================================================================
# checkgenwds.c
# ==========================================================================


def CheckGenWords(g: GkWord, gkforms: list[GkWord]) -> int:
    preverb = gkforms[0].preverb.gkstring
    origword = g.workword
    accword = stripquant(stripdiaer(zap_extra_breath(origword)))
    wordnoacute = stripacute(accword)
    hits = 0
    for f in gkforms:
        if not f.workword:
            break
        curform = f.workword
        if g.prntflags & C.IGNORE_ACCENTS:
            checks = _sacc(wordnoacute)
            curform = _sacc(curform)
        elif has_morphflag(f.stem.morphflags, C.ENCLITIC) and not preverb:
            checks = wordnoacute
        else:
            checks = accword
        curform = zap2acc(zap_extra_breath(curform))
        if curform.endswith("_") and origword.endswith("^"):
            continue
        curform = stripmetachars(stripdiaer(curform))
        if not morphstrcmp(curform, checks):
            if has_morphflag(f.stem.morphflags, C.COMP_ONLY) and not preverb:
                continue
            if has_morphflag(f.stem.morphflags, C.NOT_IN_COMPOSITION) and preverb:
                continue
            if AddAnalysis(g, f):
                hits += 1
    return hits


def _compound_lemma(preverb: str, lemma: str) -> str:
    tmplem = f"{preverb}-{lemma}"
    s = tmplem
    tmphalf1 = ""
    cmplem = ""
    while True:
        cmplem = chckcmpvb(s) or ""
        if cmplem:
            if tmphalf1:
                cmplem = tmphalf1 + "-" + cmplem
            break
        t = s
        i = s.find(",")
        if i < 0:
            if tmphalf1:
                tmphalf1 += ","
            tmphalf1 += t
            tmplem = tmphalf1
            break
        t, s = s[:i], s[i + 1:]
        if tmphalf1:
            tmphalf1 += ","
        tmphalf1 += t
    return cmplem if cmplem else tmplem


def AddAnalysis(g: GkWord, gkform: GkWord) -> int:
    if g.analyses is None:
        g.analyses = [GkWord() for _ in range(MAXANALYSES + 1)]
        if g.totanal != 0:
            return 0
    if g.totanal >= MAXANALYSES:
        return 0
    cur = g.analyses[g.totanal]
    if gkform.crasis:
        cur.crasis = gkform.crasis
    if gkform.preverb.gkstring:
        cur.lemma = _compound_lemma(gkform.preverb.gkstring, gkform.lemma)
    else:
        cur.lemma = gkform.lemma
    cur.preverb.assign(gkform.preverb)
    cur.aug1.assign(gkform.aug1)
    cur.stem.assign(gkform.stem)
    cur.endstring.assign(gkform.endstring)
    cur.rawword = gkform.rawword
    cur.workword = gkform.workword
    cur.form = gkform.form.copy()
    cur.geogregion = gkform.geogregion
    cur.dialect = _short(cur.preverb.dialect | cur.aug1.dialect | cur.stem.dialect | cur.endstring.dialect)
    if has_morphflag(gkform.preverb.morphflags, C.APOCOPE):
        if g.dialect & C.HOMERIC:
            cur.dialect = _short(cur.dialect | C.HOMERIC)
        if g.dialect != C.HOMERIC:
            cur.morphflags = add_morphflag(cur.morphflags, C.POETIC)
    if (has_morphflag(gkform.preverb.morphflags, C.UNASP_PREVERB)
            and getbreath(gkform.stem.gkstring) == ROUGHBR):
        if AndDialect(gkform.preverb.dialect, C.IONIC) < 0:
            return 0
        cur.dialect = AndDialect(cur.dialect, C.IONIC)
    if has_morphflag(gkform.stem.morphflags, C.UNAUGMENTED):
        if cur.dialect:
            cur.dialect = _short(cur.dialect | (cur.dialect & (C.HOMERIC | C.IONIC)))
        else:
            cur.dialect = _short(cur.dialect | C.HOMERIC | C.IONIC)
        if cur.form.mood != C.INDICATIVE:
            return 0
    cur.stemtype = gkform.stemtype
    cur.derivtype = gkform.derivtype
    cur.morphflags = (gkform.morphflags | gkform.preverb.morphflags | gkform.stem.morphflags
                      | gkform.endstring.morphflags)
    for i in range(g.totanal):
        other = g.analyses[i]
        if equiv_anal(cur, other):
            if other.dialect:
                other.dialect = _short(other.dialect | cur.dialect)
            return 0
    g.totanal += 1
    return 1


def equiv_anal(a1: GkWord, a2: GkWord) -> bool:
    if a1.lemma != a2.lemma:
        return False
    if a1.aug1.gkstring != a2.aug1.gkstring:
        return False
    if a1.preverb.gkstring != a2.preverb.gkstring:
        return False
    if a1.workword != a2.workword:
        return False
    if a1.endstring.gkstring != a2.endstring.gkstring:
        return False
    if not eq_forminfo(a1.form, a2.form):
        return False
    if (has_morphflag(a1.stem.morphflags, C.R_E_I_ALPHA)
            != has_morphflag(a2.stem.morphflags, C.R_E_I_ALPHA)):
        return False
    return a1.stemtype == a2.stemtype


# ==========================================================================
# genwd.c
# ==========================================================================


def GenStemForms(g: GkWord, keys: str, mode: int) -> list[GkWord] | None:
    stemkeys = keys
    tmp = g.copy()
    stem_g = tmp.stem
    if not ScanAsciiKeys(stemkeys, tmp, stem_g, None):
        return None
    if has_morphflag(g.morphflags, C.SYLL_AUGMENT) and not has_morphflag(stem_g.morphflags, C.SYLL_AUGMENT):
        return None
    if g.preverb.gkstring and g.preverb.gkstring != tmp.preverb.gkstring:
        return None
    tmp.stemtype = stem_g.stemtype
    tmp.derivtype = stem_g.derivtype
    if AndDialect(tmp.dialect, stem_g.dialect) < 0:
        return None
    endings = chckendings(tmp.endstring.gkstring, stemkeys, tmp.stem.gkstring, tmp.preverb.gkstring,
                          tmp.dialect)
    if not endings:
        return None
    forms: list[GkWord] = []
    tmp.stemtype = endings[0].stemtype
    AddWdEndings(tmp, endings, forms)
    forms.append(GkWord())  # terminator
    return forms


def GenIrregForm(g: GkWord, keys: str, mode: int) -> list[GkWord] | None:
    stemkeys = keys
    gstring = GkString()
    forms = [GkWord() for _ in range(4)]
    if not ScanAsciiKeys(stemkeys, g, gstring, None):
        return None
    g.stem.morphflags |= gstring.morphflags
    if mode & INDECL:
        g.morphflags = add_morphflag(g.morphflags, C.INDECLFORM)
        gstring.morphflags = add_morphflag(gstring.morphflags, C.INDECLFORM)
    g.morphflags = add_morphflag(g.morphflags, C.IRREGFORM)
    gstring.morphflags = add_morphflag(gstring.morphflags, C.IRREGFORM)
    g.endstring.gkstring = ""
    g.stemtype = gstring.stemtype
    dial = AndDialect(gstring.dialect, g.dialect)
    if dial >= 0:
        if gstring.dialect:
            gstring.dialect = dial
    else:
        return None
    g.form = gstring.form.copy()
    if has_morphflag(g.stem.morphflags, C.UNAUGMENTED) and not needs_augment(gstring):
        return None
    BuildAWord(g, gstring, forms)
    g.stem.morphflags = 0
    g.morphflags = zap_morphflag(g.morphflags, C.INDECLFORM)
    return forms


def AddWdEndings(g: GkWord, endings: list[GkString], forms: list[GkWord]) -> None:
    curbuf = [GkWord() for _ in range(MAX_FORM_VARIANTS + 1)]
    save = g.copy()
    for e in endings:
        if not e.gkstring:
            break
        cur = e.copy()
        if has_morphflag(g.preverb.morphflags, C.PREVB_AUGMENT) and not needs_augment(e):
            continue
        if ((has_morphflag(g.stem.morphflags, C.UNAUGMENTED) or has_morphflag(g.morphflags, C.UNAUGMENTED)
             or has_morphflag(e.morphflags, C.UNAUGMENTED)) and not needs_augment(e)):
            continue
        if g.stem.form.mood:
            if g.stem.form.mood != e.form.mood:
                continue
        cur.stemtype = g.stemtype
        g.endstring.gkstring = e.gkstring
        g.form = cur.form.copy()
        formvars = BuildAWord(g, cur, curbuf)
        for k in range(formvars):
            forms.append(curbuf[k].copy())
        g.assign(save)


def BuildAWord(g: GkWord, cur_end: GkString, cf: list[GkWord]) -> int:
    c0 = cf[0]
    c0.assign(g)
    c0.endstring.assign(cur_end)
    c0.stem.morphflags |= g.morphflags
    if AndDialect(cur_end.dialect, g.dialect) < 0:
        return 0
    if g.stemtype & C.PPARTMASK:
        return BuildAVerb(g, cur_end, cf)
    return BuildANoun(g, cur_end, cf)


def BuildANoun(g: GkWord, cur_end: GkString, cf: list[GkWord]) -> int:
    c0 = cf[0]
    c0.endstring.assign(cur_end)
    if ((g.stemtype & C.NOUNSTEM) or (g.stemtype & C.ADJSTEM)
            or cur_end.form.mood == C.PARTICIPLE or cur_end.form.mood == C.INFINITIVE):
        word, _e = FixPersAcc(cur_end, cur_end.morphflags, c0.stem, cur_end.gkstring, cur_end.form, 1)
        cur_end.gkstring = word
    else:
        cur_end.gkstring = g.stem.gkstring
    if has_morphflag(g.stem.morphflags, C.ENCLITIC):
        cur_end.gkstring = stripacute(cur_end.gkstring)
    c0.workword = cur_end.gkstring
    return 1


def BuildAVerb(g: GkWord, cur_end: GkString, cf: list[GkWord]) -> int:
    c0 = cf[0]
    c0.endstring.assign(cur_end)
    tmpstem = g.stem.gkstring
    endstring = c0.endstring.gkstring
    if has_morphflag(g.stem.morphflags, C.HAS_PREVERB):
        preverb = _sacc(g.preverb.gkstring)
    else:
        preverb = ""
    if c0.form.mood == C.PARTICIPLE or c0.form.mood == C.INFINITIVE:
        c0.stem.morphflags = zap_morphflag(c0.stem.morphflags, C.SYLL_AUGMENT)
        nforms = BuildANoun(g, cur_end, cf)
        if preverb:
            for i in range(nforms):
                cf[i].workword = rstprevb(cf[i].workword, preverb, cf[i].preverb)
        return nforms
    if endstring and endstring[0] != "*":
        tmpstem = Xstrncat(tmpstem, "-", MAXWORDSIZE)
        tmpstem = Xstrncat(tmpstem, endstring, MAXWORDSIZE + 1)
    c0.workword = tmpstem
    if endstring and has_morphflag(c0.stem.morphflags, C.ENCLITIC):
        return 1
    if not endstring:
        c0.stem.morphflags |= cur_end.morphflags
        cur_end.morphflags = 0
        c0.endstring.morphflags = 0
        c0.morphflags = 0
        if preverb:
            if nsylls(c0.workword) == 1:
                MonoSyllVb(c0, cur_end.form, preverb)
                c0.workword = stripstemsep(c0.workword)
            else:
                if has_morphflag(c0.preverb.morphflags, C.PREVB_AUGMENT):
                    c0.stem.morphflags = add_morphflag(c0.stem.morphflags, C.PREVB_AUGMENT)
                c0.workword = rstprevb(c0.workword, preverb, c0.stem)
                c0.stem.morphflags = zap_morphflag(c0.stem.morphflags, C.PREVB_AUGMENT)
        enc = has_morphflag(c0.stem.morphflags, C.ENCLITIC)
        if not enc or (enc and preverb):
            if has_morphflag(c0.stem.morphflags, C.NO_CIRCUMFLEX):
                c0.endstring.morphflags = add_morphflag(c0.endstring.morphflags, C.NO_CIRCUMFLEX)
            tmpmf = c0.stem.morphflags
            c0.workword = FixRecAcc(c0, tmpmf, c0.workword)
            c0.workword = stripstemsep(c0.workword)
        else:
            c0.workword = _sacc(c0.workword)
    else:
        augs = add_augment(cf, 0, c0.stem.morphflags, MAX_FORM_VARIANTS)
        if augs or (Is_vowel(at(c0.workword, 0))
                    and c0.form.tense in (C.PLUPERF, C.FUTPERF, C.PERFECT)):
            if not augs:
                augs = 1
            for i in range(augs):
                ci = cf[i]
                if has_morphflag(ci.preverb.morphflags, C.PREVB_AUGMENT):
                    ci.workword = rstprevb(ci.workword, preverb, ci.preverb)
                    ci.workword = FixRecAcc(ci, ci.endstring.morphflags, ci.workword)
                    ci.workword = stripstemsep(ci.workword)
                else:
                    ci.workword = FixRecAcc(ci, ci.endstring.morphflags, ci.workword)
                    cf[0].workword = stripstemsep(cf[0].workword)
                    if preverb:
                        ci.workword = rstprevb(ci.workword, preverb, ci.preverb)
            return augs
        elif nsylls(c0.workword) == 1 and preverb:
            MonoSyllVb(c0, c0.form, preverb)
        else:
            if preverb:
                c0.workword = rstprevb(c0.workword, preverb, c0.preverb)
            c0.workword = FixRecAcc(c0, c0.stem.morphflags, c0.workword)
            c0.workword = stripstemsep(c0.workword)
    c0.workword = stripstemsep(c0.workword)
    return 1


def MonoSyllVb(cf: GkWord, winfo, preverb: str) -> None:
    if (winfo.mood == C.IMPERATIVE and winfo.tense == C.AORIST and (winfo.voice & C.MIDDLE)
            and (nsylls(preverb) == 1 or Is_vowel(at(cf.workword, 0)))):
        cf.workword = FixRecAcc(cf, cf.endstring.morphflags, cf.workword)
        cf.workword = rstprevb(cf.workword, preverb, cf.preverb)
    else:
        cf.workword = rstprevb(cf.workword, preverb, cf.preverb)
        cf.endstring.morphflags = add_morphflag(cf.endstring.morphflags, C.STEM_ACC)
        cf.workword = FixRecAcc(cf, cf.endstring.morphflags, cf.workword)
