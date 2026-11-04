"""Port of the reachable parts of ``src/morphlib``.

Sections are named after their C files. Functions that modify ``char *``
arguments return the new strings; functions that modify ``gk_string`` /
``gk_word`` objects mutate them in place, as in C. Arrays of ``gk_word``
(``gkform + n``) are Python lists plus a base index.
"""

from __future__ import annotations

from functools import lru_cache

from . import consts as C
from .gkstring import (
    AndDialect,
    GkString,
    GkWord,
    add_morphflag,
    has_morphflag,
    no_morphflag,
    overlap_morphflags,
    zap_morphflag,
)
from .greeklib import (
    ACUTE,
    ANTEPENULT,
    CIRCUMFLEX,
    HARDSHORT,
    LONG,
    MAXWORDSIZE,
    NOBREATH,
    NUL,
    P_ERR,
    PENULT,
    ROUGHBR,
    SHORT,
    SMOOTHBR,
    ULTIMA,
    I_ERR,
    Is_accent,
    Is_cons,
    Is_labial,
    Is_liquid,
    Is_palatal,
    Is_stop,
    Is_unasp,
    Is_vowel,
    Xstrncat,
    addaccent,
    addbreath,
    aspirate,
    at,
    cinsert,
    ends_in,
    getbreath,
    getquantity,
    getsyll,
    getsyll2,
    is_diphth,
    isalpha,
    longbyposition,
    naccents,
    nsylls,
    quantprim,
    stripacc,
    stripbreath,
    striphyph,
    stripquant,
    strsqz,
)
from .morphkeys import ScanAsciiKeys, nextkey
from .stemlib import morphstrncmp as morphstrncmp_c, read_text

TEMP_AUGMENT = C.SYLL_AUGMENT * 2


def _flag(gs, n):
    return has_morphflag(gs.morphflags, n)


# ==========================================================================
# augment.c
# ==========================================================================

ALL_DIAL = C.ALL_DIAL

TempAugments = (
    ("ai)", "h)|", ALL_DIAL, 0),
    ("ai(", "h(|", ALL_DIAL, 0),
    ("ei)", "h)|", ALL_DIAL, 0),
    ("ei(", "h(|", ALL_DIAL, 0),
    ("oi)", "w)|", ALL_DIAL, 0),
    ("oi(", "w(|", ALL_DIAL, 0),
    ("oi)", "w)|", ALL_DIAL, 0),
    ("oi(", "w(|", ALL_DIAL, 0),
    ("au)", "hu)", ALL_DIAL, 0),
    ("au(", "hu(", ALL_DIAL, 0),
    ("au)", "au)", C.DORIC, 0),
    ("au(", "au(", C.DORIC, 0),
    ("eu)", "hu)", ALL_DIAL, 0),
    ("eu(", "hu(", ALL_DIAL, 0),
    ("e)e", "e)e", C.EPIC, 1),
    ("e(e", "e(e", C.EPIC, 1),
    ("a)", "h)", C.ATTIC | C.IONIC | C.EPIC, 0),
    ("a(", "h(", C.ATTIC | C.IONIC | C.EPIC, 0),
    ("a)", "a_)", C.DORIC | C.AEOLIC, 0),
    ("a(", "a_(", C.DORIC | C.AEOLIC, 0),
    ("e)", "h)", ALL_DIAL, 0),
    ("e(", "h(", ALL_DIAL, 0),
    ("h(", "h(", ALL_DIAL, 0),
    ("h)", "h)", ALL_DIAL, 0),
    ("i(", "i_(", ALL_DIAL, 0),
    ("i)", "i_)", ALL_DIAL, 0),
    ("o)", "w)", ALL_DIAL, 0),
    ("o(", "w(", ALL_DIAL, 0),
    ("w)", "w)", ALL_DIAL, 0),
    ("w(", "w(", ALL_DIAL, 0),
    ("u)", "u_)", ALL_DIAL, 0),
    ("u(", "u_(", ALL_DIAL, 0),
    ("ou)", "ou)", ALL_DIAL, 0),
    ("ou(", "ou(", ALL_DIAL, 0),
)

SyllAugments = (
    ("i)", "ei)", ALL_DIAL, 0),
    ("i(", "ei(", ALL_DIAL, 0),
    ("i)", "e)i", ALL_DIAL, 0),
    ("i(", "e(i", ALL_DIAL, 0),
    ("oi)w", "oi)w", ALL_DIAL, 0),
    ("e)oi", "e)w|", ALL_DIAL, 1),
    ("e(oi", "e(w|", ALL_DIAL, 1),
    ("oi)", "e)w|", ALL_DIAL, 0),
    ("oi(", "e(w|", ALL_DIAL, 0),
    ("ei(", "ei(", ALL_DIAL, 0),
    ("ei)", "ei)", ALL_DIAL, 0),
    ("e)", "ei)", ALL_DIAL, 0),
    ("e(", "ei(", ALL_DIAL, 0),
    ("a)", "e)a", ALL_DIAL, 0),
    ("a(", "e(a", ALL_DIAL, 0),
    ("h)", "e)h", ALL_DIAL, 0),
    ("h(", "e(h", ALL_DIAL, 0),
    ("w)", "e)w", ALL_DIAL, 0),
    ("w(", "e(w", ALL_DIAL, 0),
    ("o)", "e)w", ALL_DIAL, 0),
    ("o(", "e(w", ALL_DIAL, 0),
    ("e)", "ei)", ALL_DIAL, 0),
    ("e(", "ei(", ALL_DIAL, 0),
    ("eu)", "eu)", ALL_DIAL, 0),
    ("eu(", "eu(", ALL_DIAL, 0),
    ("ou)", "e)ou", ALL_DIAL, 0),
    ("ou(", "e(ou", ALL_DIAL, 0),
)


def _strncmp(s1: str, s2: str, n: int) -> int:
    from .greeklib import Xstrncmp

    return Xstrncmp(s1, s2, n)


def _do_aug(forms: list[GkWord], base: int, maxaugs: int, table, syll: bool) -> int:
    naugs = 0
    tmpword = forms[base].copy()
    tmpstem = striphyph(forms[base].workword)
    for noaug, withaug, augdial, unique in table:
        if _strncmp(noaug, tmpstem, len(noaug)):
            continue
        g = forms[base + naugs]
        g.assign(tmpword)
        d = AndDialect(g.dialect, augdial)
        if d < 0:
            continue
        if d:
            g.dialect = d
        wstart = len(noaug)
        if at(tmpstem, wstart) == HARDSHORT:
            wstart += 1
        tmp = Xstrncat(withaug, tmpstem[wstart:], MAXWORDSIZE)
        g.aug1.gkstring = f"{noaug}>{withaug}"
        g.aug1.dialect = augdial
        if syll:
            g.aug1.morphflags = add_morphflag(g.aug1.morphflags, C.SYLL_AUG)
            g.stem.morphflags = zap_morphflag(g.stem.morphflags, C.SYLL_AUG)
        g.workword = tmp
        naugs += 1
        if naugs >= maxaugs:
            break
        if unique:
            break
    return naugs


def do_syllaug(forms: list[GkWord], base: int, maxaugs: int) -> int:
    return _do_aug(forms, base, maxaugs, SyllAugments, True)


def do_tempaug(forms: list[GkWord], base: int, maxaugs: int) -> int:
    return _do_aug(forms, base, maxaugs, TempAugments, False)


def unaugment(s: str, possibs: list[GkString], qpossibs: list[GkString], maxstems: int,
              dial: int, wantsyllaugs: bool, wantredupl: bool) -> int:
    rval = 0
    if not _strncmp(s, "e)rr", 4):
        possibs[0].gkstring = Xstrncat("r(", s[4:], MAXWORDSIZE)
        if not wantredupl:
            possibs[0].form.mood = C.INDICATIVE
        return 1
    if not _strncmp(s, "e)r", 3):
        possibs[0].gkstring = Xstrncat("r(", s[3:], MAXWORDSIZE)
        possibs[0].morphflags = add_morphflag(possibs[0].morphflags, C.RAW_SONANT)
        if not wantredupl:
            possibs[0].form.mood = C.INDICATIVE
        return 1
    if not _strncmp(s, "e)", 2) and Is_cons(at(s, 2)):
        rval = 1
        possibs[0].gkstring = s[2:]
        if at(s, 2) == at(s, 3):
            rval = 2
            possibs[1].gkstring = s[3:]
            possibs[1].morphflags = add_morphflag(possibs[1].morphflags, C.SYLL_AUGMENT)
        if not wantredupl:
            possibs[0].form.mood = C.INDICATIVE
        return rval
    for noaug, withaug, augdial, _u in TempAugments:
        if rval >= maxstems:
            break
        augnoquant = stripquant(withaug)
        if morphstrncmp_c(augnoquant, s, len(augnoquant)):
            continue
        possibs[rval].gkstring = Xstrncat(noaug, s[len(augnoquant):], MAXWORDSIZE)
        if augnoquant != withaug:
            qpossibs[rval].gkstring = Xstrncat(withaug, s[len(augnoquant):], MAXWORDSIZE)
            possibs[rval].dialect = augdial
        if not wantredupl:
            possibs[rval].form.mood = C.INDICATIVE
        rval += 1
    if not wantsyllaugs:
        return rval
    for noaug, withaug, augdial, _u in SyllAugments:
        if rval >= maxstems:
            break
        augnoquant = stripquant(withaug)
        if morphstrncmp_c(augnoquant, s, len(augnoquant)):
            continue
        possibs[rval].gkstring = Xstrncat(noaug, s[len(augnoquant):], MAXWORDSIZE)
        possibs[rval].dialect = augdial
        possibs[rval].morphflags = add_morphflag(possibs[rval].morphflags, C.SYLL_AUGMENT)
        if not wantredupl:
            possibs[rval].form.mood = C.INDICATIVE
        rval += 1
    return rval


def unaugfromlemma(stem: str, lemma: str) -> tuple[int, str]:
    if not _strncmp(stem, "e)", 2):
        if Is_cons(at(lemma, 0)):
            return TEMP_AUGMENT, stem[2:]
    for noaug, withaug, _d, _u in TempAugments:
        if not _strncmp(withaug, stem, len(withaug)):
            if not _strncmp(noaug, lemma, len(noaug)):
                return TEMP_AUGMENT, Xstrncat(noaug, stem[len(withaug):], MAXWORDSIZE)
    for noaug, withaug, _d, _u in SyllAugments:
        if not _strncmp(withaug, stem, len(withaug)):
            if not _strncmp(noaug, lemma, len(noaug)):
                return C.SYLL_AUGMENT, Xstrncat(noaug, stem[len(withaug):], MAXWORDSIZE)
    return -1, stem


def needs_augment2(gkform, stem: str) -> int:
    v = gkform.form
    if has_morphflag(gkform.stem.morphflags, C.HAS_AUGMENT):
        return 0
    if v.mood != C.INDICATIVE:
        return 0
    t = v.tense
    if t == C.IMPERF or t == C.AORIST:
        return 1
    if t == C.PLUPERF:
        if has_morphflag(gkform.stem.morphflags, C.ATTIC_REDUPL):
            return 1
        if at(stem, 0) in ("e", "h"):
            return 0
        return 1
    return 0


def needs_augment(gstr: GkString) -> int:
    tmp = GkWord()
    tmp.stem = gstr.copy()
    tmp.form = gstr.form.copy()
    return needs_augment2(tmp, "")


def add_augment(forms: list[GkWord], base: int, mf: int, maxaugs: int) -> int:
    g = forms[base]
    syllabic = bool(has_morphflag(g.stem.morphflags, C.SYLL_AUGMENT))
    if has_morphflag(mf, C.UNAUGMENTED) or has_morphflag(g.endstring.morphflags, C.UNAUGMENTED):
        g.stem.morphflags = add_morphflag(g.stem.morphflags, C.UNAUGMENTED)
        return 0
    if not needs_augment2(g, g.workword):
        g.stem.morphflags = zap_morphflag(g.stem.morphflags, C.SYLL_AUGMENT)
        if has_morphflag(g.stem.morphflags, C.HAS_AUGMENT):
            return 1
        return 0
    rval = augmentit(forms, base, syllabic, maxaugs)
    g.stem.morphflags = add_morphflag(g.stem.morphflags, C.HAS_AUGMENT)
    return rval


def augmentit(forms: list[GkWord], base: int, syllabic: bool, maxaugs: int) -> int:
    g = forms[base]
    s = g.workword
    stem_mf = g.stem.morphflags
    if Is_cons(at(s, 0)):
        if s.startswith("r("):
            if has_morphflag(stem_mf, C.RAW_SONANT):
                s = stripbreath(s)
            else:
                s = s[0] + "r" + s[2:]
            g.aug1.gkstring = "r(>e)rr"
        elif has_morphflag(stem_mf, C.SYLL_AUGMENT):
            c = s[0]
            s = c + s
            g.aug1.gkstring = f"{c}>e){c}{c}"
        s = "e)" + s
        g.workword = s
        if not g.aug1.gkstring:
            g.aug1.gkstring = "e)"
        return 1
    if syllabic:
        return do_syllaug(forms, base, maxaugs)
    return do_tempaug(forms, base, maxaugs)


def simpleaugment(s: str, syllabic: bool) -> str:
    forms = [GkWord() for _ in range(6)]
    forms[0].workword = s
    augmentit(forms, 0, syllabic, 5)
    return forms[0].workword


def redupit2(forms: list[GkWord], base: int, syllabic: bool, redupc: str, nredups: int) -> int:
    g = forms[base]
    s = g.workword
    c0, c1 = at(s, 0), at(s, 1)
    if Is_cons(c0) and Is_cons(c1) and not Is_liquid(c1) and redupc != "i":
        return augmentit(forms, base, syllabic, nredups)
    if c0 in ("z", "c", "y"):
        return augmentit(forms, base, syllabic, nredups)
    if Is_vowel(c0) or c0 == "r":
        return augmentit(forms, base, syllabic, nredups)
    if (s.startswith("gn") or s.startswith("gl")) and redupc != "i":
        return augmentit(forms, base, syllabic, nredups)
    c = {"q": "t", "x": "k", "f": "p"}.get(c0, c0)
    g.workword = c + redupc + s
    return 1


def simpleredupit(s: str, syllabic: bool, redupc: str) -> str:
    forms = [GkWord() for _ in range(6)]
    forms[0].workword = s
    redupit2(forms, 0, syllabic, redupc, 5)
    return forms[0].workword


def un_redupl(src: str, redupc: str) -> tuple[int, str]:
    sbuf = stripacc(src)[0]
    if at(sbuf, 1) != redupc:
        return 0, ""
    c2 = {"q": "t", "x": "k", "f": "p"}.get(at(sbuf, 2), at(sbuf, 2))
    if at(sbuf, 0) == c2:
        return 1, src[2:]
    return 0, ""


def add_double_augment(s: str, oddpb: int) -> tuple[str, int]:
    return simpleaugment(s, False), add_morphflag(oddpb, C.HAS_AUGMENT)


# ==========================================================================
# loadeuph.c
# ==========================================================================


class EuphEntry(GkString):
    """A ``gk_string`` from load_euph_tab: ``gkstring`` is the raw string,
    ``cooked`` the string stored at offset MAXSUBSTRING."""

    __slots__ = ("cooked",)

    def __init__(self):
        super().__init__()
        self.cooked = ""


def load_euph_tab(rel: str, is_contr: bool) -> list[EuphEntry]:
    tmpword = GkWord()
    out: list[EuphEntry] = []
    for line in read_text(rel).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cur = EuphEntry()
        raw = cooked = ""
        nk = nextkey(line)
        if nk:
            raw, line = nk
            nk = nextkey(line)
            if nk:
                cooked, line = nk
        if is_contr and len(raw) > 1 and cooked[: len(raw)] == raw:
            cooked = Xstrncat(cooked[0] + "+", cooked[1:], MAXWORDSIZE)
        cur.gkstring = raw
        cur.cooked = cooked
        tmpword.preverb.morphflags = 0
        ScanAsciiKeys(line, tmpword, cur, None)
        cur.morphflags |= tmpword.preverb.morphflags
        out.append(cur)
    return out


# ==========================================================================
# preverb3.c
# ==========================================================================


class _PrevbState:
    table: list[EuphEntry] | None = None


@lru_cache(maxsize=None)
def _prevb_table() -> tuple[EuphEntry, ...]:
    return tuple(load_euph_tab("rule_files/raw_preverbs.table", False))


def has_rawpreverb(curpb: str, entry: GkString) -> bool:
    raw = entry.gkstring
    return curpb[: len(raw)] == raw


@lru_cache(maxsize=65536)
def _prevb_prefixes(word: str) -> tuple[int, ...]:
    """Indices of raw-preverb table entries that are prefixes of ``word``."""
    return tuple(i for i, e in enumerate(_prevb_table()) if word.startswith(e.gkstring))


def nextpreverb(word: str, oldprevb: str, gstr: GkString) -> tuple[int, str, str, str]:
    """Returns ``(found, word, oldprevb, pblemma)``; ``gstr`` is updated."""
    table = _prevb_table()
    _PrevbState.table = table
    n = len(table)
    pblemma = ""
    i = 0
    if oldprevb:
        hits = _prevb_prefixes(oldprevb)
        i = hits[0] + 1 if hits else n
    while i < n:
        cand = [j for j in _prevb_prefixes(word) if j >= i]
        if not cand:
            break
        i = cand[0]
        e = table[i]
        oldprevb = e.gkstring
        pblemma = e.cooked
        word = word[len(e.gkstring):]
        if (not no_morphflag(gstr.morphflags) and overlap_morphflags(gstr.morphflags, e.morphflags)
                and has_morphflag(gstr.morphflags, C.RAW_PREVERB)):
            i += 1
            continue  # sic: C keeps scanning with the shortened word
        gstr.morphflags |= e.morphflags
        if e.dialect:
            gstr.dialect = e.dialect
        return 1, word, oldprevb, pblemma
    return 0, word, oldprevb, pblemma


def is_rawpreverb(s: str) -> bool:
    table = _PrevbState.table  # empty until nextpreverb() first loads it, as in C
    if not table:
        return False
    return any(s == e.gkstring for e in table)


# ==========================================================================
# preverb2.c
# ==========================================================================


def CombPbStem(curpb: str, restofs: str, dial: int, pbflags: int) -> tuple[bool, str, int]:
    """Can preverb ``curpb`` combine with ``restofs``? Returns (ok, restofs, pbflags)."""
    if not restofs:
        return True, restofs, pbflags
    return CombPbStemG(curpb, restofs, dial, pbflags)


def CombPbStemG(curpb: str, restofs: str, dial: int, pbflags: int) -> tuple[bool, str, int]:
    from .greeklib import next_cons_rough

    if has_morphflag(pbflags, C.DISSIMILATION) and not next_cons_rough(restofs, 0):
        return False, restofs, pbflags
    noaccpb = stripbreath(stripacc(curpb)[0])
    L = len(noaccpb)
    lastc = at(noaccpb, L - 1)
    lastc2 = noaccpb[L - 2] if L > 1 else NUL
    lastc3 = noaccpb[L - 3] if L > 2 else NUL
    r0 = at(restofs, 0)

    if Is_cons(lastc) and lastc != "s" and lastc2 != "e" and Is_cons(r0):
        if lastc2 != "u" and lastc3 != "s":
            pbflags = add_morphflag(pbflags, C.APOCOPE)

    if lastc in ("q", "f"):
        if not Is_vowel(r0):
            return False, restofs, pbflags
        lp2 = curpb[len(curpb) - 2] if len(curpb) >= 2 else NUL
        if lp2 == "m" and lastc == "f":
            return True, restofs, add_morphflag(pbflags, C.ELIDE_PREVERB)
        curbreath = getbreath(restofs)
        if has_morphflag(pbflags, C.UNASP_PREVERB):
            pbflags = zap_morphflag(pbflags, C.UNASP_PREVERB)
        if curbreath == NOBREATH:
            restofs = addbreath(restofs, ROUGHBR)
        elif curbreath == SMOOTHBR:
            return False, restofs, pbflags
    elif lastc in ("t", "p") and Is_vowel(r0):
        curbreath = getbreath(restofs)
        if AndDialect(dial, C.AEOLIC | C.IONIC) >= 0 and curbreath in (ROUGHBR, NOBREATH):
            return True, restofs, add_morphflag(pbflags, C.UNASP_PREVERB)
        elif curbreath == NOBREATH:
            return True, restofs, pbflags
        elif curbreath == ROUGHBR:
            return False, restofs, pbflags
    elif lastc == "c":
        if not Is_vowel(r0):
            return False, restofs, pbflags
    elif lastc == "u":
        if r0 != "s" and r0 != "z":
            return False, restofs, pbflags

    r0 = at(restofs, 0)
    if (Is_palatal(r0) or r0 == "c" or Is_labial(r0) or r0 == "y" or r0 in ("l", "r", "m")):
        if lastc == "n":
            pbflags = add_morphflag(add_morphflag(pbflags, C.RAW_PREVERB), C.POETIC)
            return True, restofs, pbflags
    if lastc == "i" and lastc2 == "d":
        if not Is_vowel(r0):
            return False, restofs, pbflags
    if lastc == "g" and not Is_palatal(r0):
        return False, restofs, pbflags
    if lastc2 == "u" or (lastc2 == "e" and lastc3 != "p"):
        if lastc == "g":
            return (Is_palatal(r0) or r0 == "c"), restofs, pbflags
        if lastc == "m":
            return (Is_labial(r0) or r0 in ("y", "m")), restofs, pbflags
        if lastc == "l":
            return r0 == "l", restofs, pbflags
        if lastc == "r":
            if lastc2 == "u" and r0 != "r":
                return False, restofs, pbflags
            if r0 != "r" and not Is_vowel(r0):
                return False, restofs, pbflags
            return True, restofs, pbflags
        return True, restofs, pbflags
    last2 = noaccpb[L - 2:] if L >= 2 else noaccpb
    if Is_vowel(lastc) and Is_vowel(r0) and _strncmp(last2, "di", 2):
        pbflags = add_morphflag(pbflags, C.RAW_PREVERB)
        if lastc3 != "p" and lastc2 != "r":
            return True, restofs, add_morphflag(pbflags, C.POETIC)
    if Is_vowel(lastc) and r0 == "r":
        if at(restofs, 1) != "r":
            pbflags = add_morphflag(add_morphflag(pbflags, C.RAW_PREVERB), C.POETIC)
            restofs = "r(" + restofs[1:]
        else:
            restofs = "r(" + restofs[2:]
        return True, restofs, pbflags
    return True, restofs, pbflags


def _exp_prevb2(s: str, fullpb: str, gstr: GkString) -> tuple[int, str, str]:
    """Returns ``(rval, s, fullpb)``; ``gstr`` is updated (and restored on backtrack)."""
    gmf = 0
    startpb = s
    startfpb = fullpb
    save = gstr.copy()
    preverb = ""
    if not s:
        return 1, s, fullpb
    while True:
        rval, s, preverb, pblemma = nextpreverb(s, preverb, gstr)
        if not rval:
            return 0, s, fullpb
        if fullpb:
            fullpb += ","
        fullpb += pblemma
        ok, s, gmf = CombPbStem(preverb, s, 0, gmf)
        if not ok:
            return 0, s, fullpb
        rval, s, fullpb = _exp_prevb2(s, fullpb, gstr)
        if rval:
            if has_morphflag(gmf, C.UNASP_PREVERB):
                gstr.morphflags = add_morphflag(gstr.morphflags, C.UNASP_PREVERB)
            return rval, s, fullpb
        s = startpb
        fullpb = startfpb
        gstr.assign(save)


def exp_preverb(rawpb: str, fullpb: str, gstr: GkString) -> tuple[int, str]:
    """Break raw preverbs into dictionary parts ("parasummeta" -> "para/,su/n,meta/")."""
    if not rawpb:
        return 0, fullpb
    if "," in rawpb:
        return 1, rawpb
    savepb = stripacc(rawpb)[0]
    rval, _s, fullpb = _exp_prevb2(savepb, fullpb, gstr)
    return rval, fullpb


def is_preverb(rawpb: str, fullpb: str, gstr: GkString) -> tuple[int, str]:
    if not rawpb:
        return 0, fullpb
    gstr.morphflags = 0
    return exp_preverb(rawpb, "", gstr)


# ==========================================================================
# preverb.c (rstprevb and helpers)
# ==========================================================================


def _shift(s: str, old: str, new: str) -> str:
    i = s.find(old)
    return s if i < 0 else s[:i] + new + s[i + len(old):]


def shift_su_to_cu(s: str) -> str:
    out = list(s)
    for i in range(len(s)):
        if out[i] == "s" and at(s, i + 1) == "u":
            out[i] = "c"
    return "".join(out)


def shift_eis_to_es(s: str) -> str:
    for i in range(len(s)):
        if s.startswith("eis", i) or s.startswith("ei)s", i):
            return s[: i + 1] + s[i + 2:]
    return s


def shift_upo_to_upai(s: str) -> str:
    for i in range(len(s)):
        if s.startswith("upo", i):
            return s[:i] + "upai" + s[i + 3:]
        if s.startswith("u(po", i):
            return s[:i] + "u(pai" + s[i + 4:]
    return s


def shift_uper_to_upeir(s: str) -> str:
    for i in range(len(s)):
        if s.startswith("uper", i):
            return s[:i] + "upeir" + s[i + 4:]
        if s.startswith("u(per", i):
            return s[:i] + "u(peir" + s[i + 5:]
    return s


def shift_en_to_eni(s: str) -> str:
    for i in range(len(s)):
        if s.startswith("e)n", i) and not s.startswith("e)ni", i):
            return s[:i] + "e)ni" + s[i + 3:]
        if s.startswith("en", i) and not s.startswith("eni", i):
            return s[:i] + "eni" + s[i + 2:]
    return s


def set_odd_prvb(oddpb: int, work: str) -> str:
    if has_morphflag(oddpb, C.SIG_TO_CI):
        work = shift_su_to_cu(work)
    if has_morphflag(oddpb, C.SHORT_EIS):
        work = shift_eis_to_es(work)
    if has_morphflag(oddpb, C.PROS_TO_POTI):
        work = _shift(work, "pros", "poti")
    if has_morphflag(oddpb, C.PROS_TO_PROTI):
        work = _shift(work, "pros", "proti")
    if has_morphflag(oddpb, C.META_TO_PEDA):
        work = _shift(work, "meta", "peda")
    if has_morphflag(oddpb, C.UPO_TO_UPAI):
        work = shift_upo_to_upai(work)
    if has_morphflag(oddpb, C.PARA_TO_PARAI):
        work = _shift(work, "para", "parai")
    if has_morphflag(oddpb, C.UPER_TO_UPEIR):
        work = shift_uper_to_upeir(work)
    if has_morphflag(oddpb, C.EN_TO_ENI):
        work = shift_en_to_eni(work)
    return work


def _last(s: str, k: int) -> str:
    """``*lastn(s, k)``."""
    i = len(s) - k
    return s[i] if 0 <= i < len(s) else NUL


def _set_last(s: str, k: int, c: str) -> str:
    """``*lastn(s, k) = c`` (``c == NUL`` truncates)."""
    i = len(s) - k
    if i < 0:
        i = 0
    if c == NUL:
        return s[:i]
    return s[:i] + c + s[i + 1:]


def getprvbform(word: str, prevb: str, oddpb: int) -> tuple[str, str, int]:
    """Join preverb and stem euphonically. Returns (word, prevb, oddpb)."""
    prevb = stripacc(prevb)[0]
    w0 = at(word, 0)
    if (prevb[-4:] == "peri" or prevb[-5:] == "proti") and has_morphflag(oddpb, C.ELIDE_PREVERB):
        prevb = _set_last(prevb, 1, NUL)
    elif prevb[-3:] == "mfi":
        if has_morphflag(oddpb, C.DISSIMILATION):
            prevb = _set_last(prevb, 2, "p")
            if Is_vowel(w0):
                prevb = prevb[:-1]
            if getbreath(word) == ROUGHBR:
                prevb = _set_last(prevb, 1, "f")
                oddpb = zap_morphflag(oddpb, C.DISSIMILATION)
        elif w0 == "i" or has_morphflag(oddpb, C.ELIDE_PREVERB):
            prevb = prevb[:-1]
    elif prevb[-3:] == "nti" and Is_vowel(w0):
        elide = has_morphflag(oddpb, C.ELIDE_PREVERB)
        if w0 != "o" or elide:
            prevb = _set_last(prevb, 1, NUL)
        if _last(prevb, 1) == "t" and getbreath(word) == ROUGHBR and not has_morphflag(oddpb, C.UNASP_PREVERB):
            prevb = _set_last(prevb, 1, "q")
    elif Is_vowel(w0):
        if prevb[-3:] != "pro" and prevb[-4:] != "peri" and prevb[-5:] != "proti":
            if Is_vowel(_last(prevb, 1)):
                if _last(prevb, 1) != "i":
                    prevb = prevb[:-1]
                elif _last(prevb, 2) != "d":
                    prevb = prevb[:-1]
            if _last(prevb, 1) == "k":
                prevb = _set_last(prevb, 1, "c")
            elif Is_unasp(_last(prevb, 1)) and getbreath(word) == ROUGHBR and not has_morphflag(oddpb, C.UNASP_PREVERB):
                prevb = _set_last(prevb, 1, aspirate(_last(prevb, 1)))
        else:
            prevb += "+"
    elif _last(prevb, 1) == "t":
        if w0 == "f":
            prevb = _set_last(prevb, 1, "p")
        if w0 == "d":
            prevb = _set_last(prevb, 1, "d")
        if w0 == "n":
            prevb = _set_last(prevb, 1, "n")
        elif w0 == "s":
            prevb = _set_last(prevb, 1, NUL)
        elif Is_labial(w0) or Is_liquid(w0) or w0 in ("p", "b", "k"):
            prevb = _set_last(prevb, 1, w0)
    elif _last(prevb, 1) == "p":
        if w0 == "b":
            prevb = _set_last(prevb, 1, "b")
    elif _last(prevb, 1) == "n":
        if Is_labial(w0) or w0 in ("m", "y"):
            prevb = _set_last(prevb, 1, "m")
        elif Is_palatal(w0):
            prevb = _set_last(prevb, 1, "g")
        elif w0 in ("r", "l"):
            prevb = _set_last(prevb, 1, w0)
        elif w0 in ("s", "z") and _last(prevb, 2) == "u":
            if Is_stop(at(word, 1)) or w0 == "z":
                prevb = _set_last(prevb, 1, NUL)
            else:
                prevb = _set_last(prevb, 1, "s")
    elif w0 == "r" and Is_vowel(_last(prevb, 1)) and not has_morphflag(oddpb, C.RAW_PREVERB):
        word = "r" + word
    if getbreath(word) != NOBREATH:
        word = stripbreath(word)
    return word, prevb, oddpb


def comp_preverb(pb: str, unasp: bool, oddpb: int) -> tuple[str, int]:
    gmf = add_morphflag(0, C.HAS_PREVERB)
    if unasp:
        gmf = add_morphflag(gmf, C.UNASP_PREVERB)
    if has_morphflag(oddpb, C.EN_TO_ENI):
        gmf = add_morphflag(gmf, C.EN_TO_ENI)
    g = GkString()
    g.morphflags = gmf
    added_aug = False
    if "," not in pb and has_morphflag(oddpb, C.PREVB_AUGMENT) and not added_aug:
        pb, oddpb = add_double_augment(pb, oddpb)
        added_aug = True
    s = 0
    while s < len(pb):
        if pb[s] == ",":
            head, rest = pb[:s], pb[s + 1:]
            if "," not in rest and has_morphflag(oddpb, C.PREVB_AUGMENT) and not added_aug:
                rest, oddpb = add_double_augment(rest, oddpb)
                added_aug = True
            rest = rstprevb(rest, head, g)
            pb = rest
            s = 0
            continue
        s += 1
    return pb, oddpb


def rstprevb(word: str, prevb: str, gstr: GkString) -> str:
    """word <- prevb + word. ``gstr.morphflags`` (oddpb) may be updated."""
    oddpb = gstr.morphflags
    if has_morphflag(oddpb, C.INDECLFORM):
        return word
    prefix = ""  # chars the C "word" pointer was advanced past
    if has_morphflag(oddpb, C.DOUBLED_CONS):
        i = 0
        while i < len(word) and not Is_cons(word[i]):
            i += 1
        prefix = word[:i]
        if i < len(word):
            tmpword = prefix + word[i] + word[i:]
            word = word[i:]
        else:
            tmpword = prefix
            word = ""
    else:
        tmpword = word
    if has_morphflag(oddpb, C.RAW_PREVERB):
        work, oddpb = comp_preverb(prevb, False, oddpb)
        if Is_vowel(_last(work, 1)) and Is_vowel(at(word, 0)):
            work += "+"
        work = set_odd_prvb(oddpb, work)
        tmpword = stripbreath(tmpword)
        work = Xstrncat(work, tmpword, MAXWORDSIZE)
        gstr.morphflags = oddpb
        return prefix + work
    tg = GkString()
    _r, fullpb = exp_preverb(prevb, "", tg)
    work = fullpb if fullpb else prevb
    work = stripacc(work)[0]
    if has_morphflag(oddpb, C.APOCOPE):
        if work and work[-1] in ("a", "o"):
            work = work[:-1]
    if has_morphflag(oddpb, C.IOTA_INTENS) and _last(work, 1) == "n":
        work += "i"
    work, oddpb = comp_preverb(work, bool(has_morphflag(oddpb, C.UNASP_PREVERB)), oddpb)
    work = set_odd_prvb(oddpb, work)
    tmpword, work, oddpb = getprvbform(tmpword, work, oddpb)
    mx = MAXWORDSIZE - len(work)
    if len(tmpword) >= mx:
        tmpword = tmpword[: mx - 2] + C_CONTCHAR
    tmpword = stripbreath(tmpword)
    work = Xstrncat(work, tmpword, MAXWORDSIZE)
    gstr.morphflags = oddpb
    return prefix + work


C_CONTCHAR = ">"


# ==========================================================================
# fixacc.c, ulttakescirc.c, penultform.c, antepenform.c
# ==========================================================================


def ulttakescirc(gstring: GkString, form) -> int:
    mf = gstring.morphflags
    if has_morphflag(mf, C.NO_CIRCUMFLEX):
        return 0
    if has_morphflag(mf, C.CONTRACTED):
        return 1
    if has_morphflag(mf, C.ENCLITIC):
        return 0
    if form.case & C.ACCUSATIVE:
        return 0
    if form.case & C.NOMINATIVE:
        return 0
    return 1


def penult_form(gstring: GkString, f) -> int:
    if (f.case == C.VOCATIVE and f.number == C.SINGULAR and (gstring.stemtype & C.DECL3)
            and has_morphflag(gstring.morphflags, C.PERS_NAME)):
        return 0
    if has_morphflag(gstring.morphflags, C.STEM_ACC):
        return 1
    if ((f.voice == C.ACTIVE and f.mood == C.PARTICIPLE and f.gender == C.NEUTER
         and f.number == C.SINGULAR and (f.case == C.NOMINATIVE or f.case == C.ACCUSATIVE))
            or ((f.voice & C.MEDIO_PASS) and f.mood == C.INFINITIVE and f.tense == C.PERFECT)):
        return 1
    return 0


def antepen_form(gstring: GkString, f) -> int:
    return 1 if has_morphflag(gstring.morphflags, C.ANT_ACC) else 0


def _has_acc(s: str) -> bool:
    return any(Is_accent(c) for c in s)


def FixRecAcc(gkform: GkWord, mflags: int, word: str) -> str:
    """Add a recessive accent to ``word``."""
    form_info = gkform.form
    if _has_acc(word):
        return word
    if getsyll(word, ULTIMA) == P_ERR:
        return word
    if getquantity(word, ULTIMA, None, True, False) == LONG:
        p = getsyll(word, PENULT)
        if p == P_ERR:
            p = getsyll(word, ULTIMA)
            if has_morphflag(mflags, C.ACCENT_OPTIONAL):
                return word
            if ulttakescirc(gkform.endstring, gkform.endstring.form):
                return addaccent(word, CIRCUMFLEX, p)
            return addaccent(word, ACUTE, p)
        return addaccent(word, ACUTE, p)
    p = getsyll(word, ANTEPENULT)
    if p != P_ERR and not penult_form(gkform.endstring, form_info):
        return addaccent(word, ACUTE, p)
    if has_morphflag(mflags, C.ACCENT_OPTIONAL):
        return word
    p = getsyll(word, PENULT)
    if p == P_ERR:
        p = getsyll(word, ULTIMA)
    if getquantity(word, PENULT, None, True, False) == LONG and not has_morphflag(mflags, C.ENCLITIC):
        return addaccent(word, CIRCUMFLEX, p)
    return addaccent(word, ACUTE, p)


def putsimpleacc(s: str) -> str:
    g = GkWord()
    g.workword = s
    return FixRecAcc(g, 0, g.workword)


def fixnacc2(targ: str, gstring: GkString, form_info, is_ending: int, is_oblique: bool) -> str:
    mflags = gstring.morphflags
    is_contr = bool(has_morphflag(mflags, C.CONTRACTED))
    if _has_acc(targ):
        return targ
    is_ending = 1
    if (getquantity(targ, ULTIMA, None, is_ending, is_oblique) == LONG
            or (nsylls(targ) == 1 and (is_ending and is_contr))):
        p = getsyll(targ, PENULT)
        if p == P_ERR:
            if has_morphflag(mflags, C.ACCENT_OPTIONAL):
                return targ
            p = getsyll(targ, ULTIMA)
            if ulttakescirc(gstring, form_info):
                return addaccent(targ, CIRCUMFLEX, p)
            return addaccent(targ, ACUTE, p)
        return addaccent(targ, ACUTE, p)
    p = getsyll(targ, ANTEPENULT)
    if p != P_ERR:
        return addaccent(targ, ACUTE, p)
    if has_morphflag(mflags, C.ACCENT_OPTIONAL):
        return targ
    p = getsyll(targ, PENULT)
    if p == P_ERR:
        p = getsyll(targ, ULTIMA)
    if (getquantity(targ, PENULT, None, is_ending, is_oblique and not is_contr) == LONG
            and not has_morphflag(mflags, C.ENCLITIC)):
        return addaccent(targ, CIRCUMFLEX, p)
    return addaccent(targ, ACUTE, p)


def FixPersAcc(gstring: GkString, mflags: int, stemgstr: GkString, endstring: str, form_info,
               is_ending: int) -> tuple[str, str]:
    """Persistent accent. Returns ``(word, endstring)`` (endstring may get accented)."""
    word, endstring = FixPersAcc2(gstring, mflags, stemgstr, endstring, form_info, is_ending)
    if word.endswith("*"):
        word = word[:-1]
    return word, endstring


def FixPersAcc2(gstring: GkString, mflags: int, stemgstr: GkString, endstring: str, form_info,
                is_ending: int) -> tuple[str, str]:
    stem = stemgstr.gkstring
    word = ""
    if not nsylls(stem) and not nsylls(endstring):
        return Xstrncat(stem, endstring, MAXWORDSIZE), endstring
    if has_morphflag(mflags, C.PROCLITIC):
        return stem, endstring
    is_oblique = form_info.case == C.GENITIVE or form_info.case == C.DATIVE
    workstem = stem
    if _has_acc(endstring) or _has_acc(stem):
        return Xstrncat(stem, endstring, MAXWORDSIZE), endstring
    if has_morphflag(mflags, C.ACCENT_OPTIONAL) and has_morphflag(mflags, C.ENCLITIC):
        return Xstrncat(stem, endstring, MAXWORDSIZE), endstring

    if is_thirdmono(stemgstr, gstring, stem, endstring, form_info, is_ending) and nsylls(endstring) == 2:
        if has_morphflag(mflags, C.ACCENT_OPTIONAL):
            return Xstrncat(stem, endstring, MAXWORDSIZE), endstring
        ep = getsyll(endstring, ULTIMA)
        if is_diphth(endstring, ep):
            ep -= 1
        endstring = endstring[:ep] + fixnacc2(endstring[ep:], gstring, form_info, is_ending, is_oblique)
        return Xstrncat(workstem, endstring, MAXWORDSIZE), endstring
    elif (has_morphflag(stemgstr.morphflags, C.SUFF_ACC)
          or is_thirdmono(stemgstr, gstring, stem, endstring, form_info, is_ending)
          or nsylls(stem) == 0):
        if nsylls(endstring) >= 1:
            if not naccents(endstring):
                endstring = fixnacc2(endstring, gstring, form_info, is_ending, is_oblique)
            return Xstrncat(workstem, endstring, MAXWORDSIZE), endstring
        elif nsylls(endstring) == 0:
            tmp = Xstrncat(stem, endstring, MAXWORDSIZE)
            p = getsyll2(tmp, ULTIMA)
            if p != P_ERR:
                tmp = tmp[:p] + fixnacc2(tmp[p:], gstring, form_info, is_ending, is_oblique)
                word = tmp
            return word, endstring
    elif (penult_form(stemgstr, form_info) or has_morphflag(gstring.morphflags, C.STEM_ACC)
          or nsylls(stem) == 1):
        p = getsyll(workstem, ULTIMA)
        if (nsylls(endstring) == 1
                and quantprim(workstem, ULTIMA, False, is_oblique) == LONG
                and quantprim(endstring, ULTIMA, True, is_oblique) == SHORT
                and not has_morphflag(mflags, C.ENCLITIC)):
            if has_morphflag(mflags, C.ACCENT_OPTIONAL):
                return Xstrncat(stem, endstring, MAXWORDSIZE), endstring
            workstem = addaccent(workstem, CIRCUMFLEX, p)
        elif quantprim(endstring, ULTIMA, True, is_oblique) == LONG or nsylls(endstring) == 2:
            workstem = addaccent(workstem, ACUTE, p)
        elif (quantprim(workstem, ULTIMA, False, is_oblique) == LONG
              and has_morphflag(stemgstr.morphflags, C.CONTRACTED)):
            workstem = addaccent(workstem, CIRCUMFLEX, p)
        else:
            workstem = addaccent(workstem, ACUTE, p)
        return Xstrncat(workstem, endstring, MAXWORDSIZE), endstring
    elif antepen_form(stemgstr, form_info):
        p = getsyll(workstem, PENULT)
        if (nsylls(endstring) == 0
                and getquantity(workstem, PENULT, None, False, is_oblique) == LONG
                and getquantity(workstem, ULTIMA, None, False, is_oblique) == SHORT
                and not has_morphflag(mflags, C.ENCLITIC)):
            workstem = addaccent(workstem, CIRCUMFLEX, p)
        elif nsylls(endstring) > 1 or getquantity(endstring, ULTIMA, None, True, is_oblique) == LONG:
            p = getsyll(workstem, ULTIMA)
            workstem = addaccent(workstem, ACUTE, p)
        else:
            workstem = addaccent(workstem, ACUTE, p)
        return Xstrncat(workstem, endstring, MAXWORDSIZE), endstring
    tmp = Xstrncat(workstem, endstring, MAXWORDSIZE)
    tmp = fixnacc2(tmp, gstring, form_info, is_ending, is_oblique)
    return tmp, endstring


# ==========================================================================
# is_thirdmono.c
# ==========================================================================


def is_mono_stem(stem: str, ends: str) -> bool:
    return nsylls(stem) + nsylls(ends) == 2


def diphth_end(stem: str, endstring: str) -> bool:
    tmp = stem + endstring
    s = getsyll(tmp, ULTIMA)
    if s == P_ERR:
        return False
    if Is_vowel(at(tmp, s)) and Is_vowel(at(tmp, s - 1)):
        tmp = tmp[: s - 1]
        if nsylls(tmp) != 0:
            return True
    return False


def is_thirdmono(stemgstr: GkString, endgstr: GkString, stem: str, endstring: str, form_info,
                 is_ending: int) -> int:
    stemtype = stemgstr.stemtype
    if is_ending and not stem:
        return 0
    if not (stemtype & C.NOUNSTEM):
        return 0
    if (stemtype & C.DECL3) and is_mono_stem(stem, endstring):
        if has_morphflag(stemgstr.morphflags, C.CONTRACTED) or has_morphflag(endgstr.morphflags, C.CONTRACTED):
            return 0
        if diphth_end(stem, endstring) and form_info.number != C.DUAL:
            return 0
        if not (form_info.case & C.GENITIVE) and not (form_info.case & C.DATIVE):
            return 0
        return 1
    return 0


def poss_thirdmono(stemtype: int, stem: str, endstring: str) -> int:
    if (stemtype & C.DECL3) and getsyll(stem, PENULT) == P_ERR and getsyll(endstring, PENULT) == P_ERR:
        return 1
    return 0


# ==========================================================================
# markstem.c, standphon.c, cmpend.c, morphstrcmp.c (dictstrcmp)
# ==========================================================================


def markstem(stemstr: str, gstr: GkString) -> None:
    lastp = len(stemstr)
    while lastp > 0 and not isalpha(at(stemstr, lastp)):
        lastp -= 1
    lc = at(stemstr, lastp)
    st = gstr.stemtype
    if ((st & C.NOUNSTEM) or (st & C.ADJSTEM) or gstr.form.mood == C.PARTICIPLE
            or has_morphflag(gstr.morphflags, C.IS_DERIV)) and lc in ("r", "i", "e"):
        if not has_morphflag(gstr.morphflags, C.ENDS_IN_DIGAMMA):
            gstr.morphflags = add_morphflag(gstr.morphflags, C.R_E_I_ALPHA)
    if st & C.ADJSTEM:
        quant = getquantity(stemstr, ULTIMA, None, False, False)
        if quant != I_ERR:
            if quant == LONG or longbyposition(stemstr, getsyll(stemstr, ULTIMA)) or ends_in(stemstr, "hi"):
                gstr.morphflags = add_morphflag(gstr.morphflags, C.LONG_PEN)
            else:
                gstr.morphflags = add_morphflag(gstr.morphflags, C.SHORT_PEN)


def stand_phonetics(gkword: GkWord) -> None:
    w = gkword.workword
    s = 0
    lastc = NUL
    while s < len(w):
        c = w[s]
        if c == "!":
            if Is_vowel(lastc) and Is_vowel(at(w, s + 1)):
                w = w[:s] + "s" + w[s + 1:]
                gkword.morphflags = add_morphflag(gkword.morphflags, C.INTERV_S_TO_H)
                gkword.geogregion |= C.LACONIA
            else:
                w = w[:s] + addbreath(w[s + 1:], ROUGHBR)
            s += 1
            continue
        if c == "%":
            rest = addbreath(w[s + 1:], ROUGHBR)
            if rest and "a" <= rest[0] <= "z":
                rest = rest[0].upper() + rest[1:]
            w = w[:s] + rest
            continue
        if isalpha(c):
            lastc = c
        s += 1
    gkword.workword = w


def cmpend(word: str, ending: str) -> tuple[int, str]:
    """Does ``word`` end in ``ending`` (and is longer)? Returns (1, stem) or (0, "")."""
    if not word or not ending:
        return 0, ""
    if len(word) > len(ending) and word.endswith(ending):
        return 1, word[: len(word) - len(ending)]
    return 0, ""


# dictstrcmp skips everything but letters, '|' and '_', and compares '|' as 'i'
_DICT_KEEP = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ|_")
_DICT_TABLE = {c: (None if chr(c) not in _DICT_KEEP else ("i" if chr(c) == "|" else chr(c)))
               for c in range(128)}


def dictstrcmp(s1: str, s2: str) -> int:
    """C ``dictstrcmp`` (only the sign of the result is meaningful)."""
    a = s1.translate(_DICT_TABLE)
    b = s2.translate(_DICT_TABLE)
    return (a > b) - (a < b)
