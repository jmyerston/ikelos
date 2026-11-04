"""Port of ``src/morphlib/morphkeys.c`` (+ ``nextkey.c``): the morphological
key vocabulary ("masc", "aor", "a_hs", ...) and ``ScanAsciiKeys``.
"""

from __future__ import annotations

import re
from functools import lru_cache

from . import keytables as kt
from .consts import (
    HAS_PREVERB,
    LONGSTRING,
    PROSEAUTHOR,
    ROOT_PREVERB,
)
from .gkstring import (
    SETTERS,
    GkString,
    GkWord,
    add_morphflag,
    has_morphflag,
    xfer_prvbflags,
    zap_morphflag,
)
from .greeklib import isspace, strcmp
from .stemlib import read_text


class MorphArg:
    __slots__ = ("key", "flags", "setter")

    def __init__(self, key: str, flags: int, setter: str):
        self.key = key
        self.flags = flags
        self.setter = SETTERS[setter]

    def __repr__(self):
        return f"MorphArg({self.key!r}, {self.flags:o})"


def nextkey(keylist: str) -> tuple[str, str] | None:
    """``nextkey``: split off the first whitespace-delimited key.
    Returns ``(key, rest)`` or None when the list is exhausted."""
    i, n = 0, len(keylist)
    while i < n and isspace(keylist[i]):
        i += 1
    if i >= n:
        return None
    j = i
    while j < n and not isspace(keylist[j]):
        j += 1
    key = keylist[i:j]
    while j < n and isspace(keylist[j]):
        j += 1
    return key, keylist[j:]


def _has_octal(line: str) -> bool:
    i, n = 0, len(line)
    while i < n and not isspace(line[i]):
        i += 1
    while i < n and isspace(line[i]):
        i += 1
    return i < n and line[i] == "0"


def GetStemClass(name: str) -> int:
    for cname, cnum in kt.arg_stemclass:
        if cname == name:
            return cnum & 0xFFFFFFFF
    return 0xFFFFFFFF  # (Stemtype) -1


def GetIsProse(name: str) -> int:
    return PROSEAUTHOR if name == "prose" else 0


def _table_lines(rel: str):
    """``GetTableLine``: non-blank lines not starting with '#'."""
    for line in read_text(rel).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        yield line


def _scan_int(tok: str, base: int) -> int:
    # sscanf %o / %d: leading valid digits only
    digits = "01234567" if base == 8 else "0123456789"
    i = 1 if tok[:1] in "+-" else 0
    j = i
    while j < len(tok) and tok[j] in digits:
        j += 1
    if j == i:
        return 0
    return int(tok[:j], base)


def InitStemSuffs(rel: str, setter: str, classfunc) -> list[MorphArg]:
    out = []
    for line in _table_lines(rel):
        parts = line.split()
        name = parts[0] if parts else ""
        n = _scan_int(parts[1], 8 if _has_octal(line) else 10) if len(parts) > 1 else 0
        decl = parts[2] if len(parts) > 2 else ""
        declnum = classfunc(decl)
        out.append(MorphArg(name, ((n & 0xFFFFFFFF) | declnum) & 0xFFFFFFFF, setter))
    return out


class Keys:
    def __init__(self):
        self.stemtype = InitStemSuffs("rule_files/stemtypes.table", "new_stemtype", GetStemClass)
        self.derivtype = InitStemSuffs("rule_files/derivtypes.table", "new_derivtype", GetStemClass)
        self.domain = InitStemSuffs("rule_files/domainlist.table", "new_domain", GetIsProse)

        def mk(rows):
            return [MorphArg(k, v, f) for k, v, f in rows]

        self.degree = mk(kt.arg_degree)
        self.person = mk(kt.arg_person)
        self.morphflags = mk(kt.arg_morphflags)
        self.gender = mk(kt.arg_gender)
        self.case = mk(kt.arg_case)
        self.number = mk(kt.arg_number)
        self.tense = mk(kt.arg_tense)
        self.voice = mk(kt.arg_voice)
        self.mood = mk(kt.arg_mood)
        self.dialect = mk(kt.arg_dialect)
        self.geogregion = mk(kt.arg_geogregion)

        # add_keyarr stops at the first entry with an empty key
        def until_blank(tab):
            out = []
            for a in tab:
                if not a.key:
                    break
                out.append(a)
            return out

        table = []
        for tab in (self.stemtype, self.derivtype, self.domain, self.degree, self.person,
                    self.gender, self.case, self.number, self.tense, self.voice, self.mood,
                    self.dialect, self.geogregion, self.morphflags):
            table += until_blank(tab)
        # qsort by strcmp; duplicate keys are resolved below
        table.sort(key=lambda a: a.key.encode("latin-1"))
        self.table = table
        self.by_key: dict[str, MorphArg] = {}
        for a in table:
            self.by_key.setdefault(a.key, a)

    def match(self, field: str) -> MorphArg | None:
        """``MatchMorphKey`` (exact binlook over the qsorted table).

        The only conflicting duplicate key in the data ("illw" in
        derivtypes.table) resolves to its first entry in C on macOS; we use
        first-in-table-order for all duplicates.
        """
        return self.by_key.get(field)


@lru_cache(maxsize=None)
def keys() -> Keys:
    return Keys()


def MatchMorphKey(field: str) -> MorphArg | None:
    return keys().match(field)


def GetStemNum(field: str) -> int:
    mp = MatchMorphKey(field)
    return mp.flags if mp else 0


def AddMorphKey(gstr, field: str) -> bool:
    mp = MatchMorphKey(field)
    if not mp:
        return False
    mp.setter(gstr, mp.flags)
    return True


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------


def _p_eq(flag: int, tab) -> str:
    if not flag:
        return ""
    for a in tab:
        if not a.key:
            break
        if flag == a.flags:
            return a.key
    return ""


def NameOfStemtype(st: int) -> str: return _p_eq(st, keys().stemtype)
def NameOfDerivtype(st: int) -> str: return _p_eq(st, keys().derivtype)
def NameOfDomain(n: int) -> str: return _p_eq(n, keys().domain)
def NameOfPerson(wf) -> str: return _p_eq(wf.person, keys().person)
def NameOfNumber(wf) -> str: return _p_eq(wf.number, keys().number)
def NameOfTense(wf) -> str: return _p_eq(wf.tense, keys().tense)
def NameOfMood(wf) -> str: return _p_eq(wf.mood, keys().mood)
def NameOfVoice(wf) -> str: return _p_eq(wf.voice, keys().voice)
def NameOfDialect(di: int) -> str: return _p_eq(di, keys().dialect)
def NameOfGender(wf) -> str: return _p_eq(wf.gender, keys().gender)
def NameOfCase(wf) -> str: return _p_eq(wf.case, keys().case)
def NameOfDegree(wf) -> str: return _p_eq(wf.degree, keys().degree)
def NameOfMorphFlags(n: int) -> str: return _p_eq(n, keys().morphflags)


def _flag_names(value: int, tab, dels: str) -> str:
    res = ""
    if not value:
        return res
    mf = value
    for a in tab:
        if not a.key:
            break
        if a.flags and (mf & a.flags) == a.flags:
            if res:
                res += dels
            res += a.key
            mf &= ~a.flags
    return res


def DialectNames(di: int, dels: str) -> str:
    return _flag_names(di, keys().dialect, dels)


def GeogRegionNames(gr: int, dels: str) -> str:
    return _flag_names(gr, keys().geogregion, dels)


def DomainNames(doms: str, dels: str) -> str:
    res = ""
    for c in doms:
        if res:
            res += dels
        res += NameOfDomain(ord(c))
    return res


_UGLY = None


def is_pretty_morphflag(n: int) -> bool:
    from . import consts as C

    global _UGLY
    if _UGLY is None:
        _UGLY = {C.PERS_NAME, C.SUFF_ACC, C.STEM_ACC, C.ANT_ACC, C.NO_COMP, C.SHORT_PEN,
                 C.LONG_PEN, C.ACCENT_OPTIONAL, C.NEEDS_ACCENT, C.NOT_IN_COMPOSITION,
                 C.HAS_PREVERB, C.HAS_AUGMENT}
    return n not in _UGLY


def MorphNames(mf: int, dels: str, pretty: bool) -> str:
    res = ""
    for i in range(12):
        for j in range(8):
            if mf >> (8 * i + j) & 1:
                curnum = 8 * i + j + 1
                if not pretty or is_pretty_morphflag(curnum):
                    s = NameOfMorphFlags(curnum)
                    if s:
                        if res:
                            res += dels
                        res += s
    return res


# --------------------------------------------------------------------------
# ScanAsciiKeys
# --------------------------------------------------------------------------


_OP_NOT, _OP_CRASIS, _OP_PB, _OP_RPB, _OP_KEY, _OP_END, _OP_PBC, _OP_RPBC, _OP_LE, _OP_ODD = range(10)

_WS = re.compile(r"[ \t\n\v\f\r]+")


@lru_cache(maxsize=65536)
def _compile_keys(s: str) -> tuple:
    """Tokenize a key string once (``nextkey``) and resolve each token."""
    toks = [t for t in _WS.split(s) if t]
    ops = []
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        i += 1
        if t == "not":
            ops.append((_OP_NOT, None))
        elif t in ("crasis", "pb", "rpb"):
            # the value is the next key; with none left, C reuses the stale one
            val = toks[i] if i < n else t
            i += 1 if i < n else 0
            ops.append(({"crasis": _OP_CRASIS, "pb": _OP_PB, "rpb": _OP_RPB}[t], val))
        else:
            mp = MatchMorphKey(t)
            if mp is not None:
                ops.append((_OP_KEY, mp))
            elif t.startswith("end:"):
                ops.append((_OP_END, t[4:]))
            elif t.startswith("pb:"):
                ops.append((_OP_PBC, t[3:]))
            elif t.startswith("rpb:"):
                ops.append((_OP_RPBC, t[4:]))
            elif t.startswith("le:"):
                ops.append((_OP_LE, t[3:]))
            else:
                ops.append((_OP_ODD, t))
    return tuple(ops)


def ScanAsciiKeys(s: str, gkword: GkWord, want: GkString, avoid: GkString | None) -> int:
    """Parse the keys in ``s`` into ``want`` (or ``avoid`` after "not")."""
    gstr = want
    if gkword.oddkeys:
        gkword.oddkeys = None
    for op, val in _compile_keys(s):
        if op == _OP_KEY:
            val.setter(gstr, val.flags)
        elif op == _OP_NOT:
            if avoid is None:
                break
            gstr = avoid
        elif op == _OP_CRASIS:
            gkword.crasis = val
        elif op == _OP_PB or op == _OP_PBC:
            gkword.preverb.gkstring = val
            gstr.morphflags = add_morphflag(zap_morphflag(gstr.morphflags, ROOT_PREVERB), HAS_PREVERB)
        elif op == _OP_RPB or op == _OP_RPBC:
            gkword.preverb.gkstring = val
            gstr.morphflags = add_morphflag(zap_morphflag(gstr.morphflags, HAS_PREVERB), ROOT_PREVERB)
        elif op == _OP_END:
            gkword.endstring.gkstring = val
        elif op == _OP_LE:
            gkword.lemma = val
        else:
            if gkword.oddkeys is None:
                gkword.oddkeys = ""
            if gkword.oddkeys:
                gkword.oddkeys += " "
            gkword.oddkeys = (gkword.oddkeys + val)[:LONGSTRING]
    if gkword.preverb.gkstring:
        st = gkword.stem
        if has_morphflag(gstr.morphflags, ROOT_PREVERB):
            gkword.morphflags = zap_morphflag(add_morphflag(gkword.morphflags, ROOT_PREVERB), HAS_PREVERB)
            st.morphflags = zap_morphflag(add_morphflag(st.morphflags, ROOT_PREVERB), HAS_PREVERB)
            gstr.morphflags = zap_morphflag(gstr.morphflags, HAS_PREVERB)
        else:
            gkword.morphflags = add_morphflag(zap_morphflag(gkword.morphflags, ROOT_PREVERB), HAS_PREVERB)
            st.morphflags = add_morphflag(zap_morphflag(st.morphflags, ROOT_PREVERB), HAS_PREVERB)
    # RearrangeMorphflags
    gkword.morphflags, gkword.preverb.morphflags = xfer_prvbflags(gkword.morphflags, gkword.preverb.morphflags)
    want.morphflags, gkword.preverb.morphflags = xfer_prvbflags(want.morphflags, gkword.preverb.morphflags)
    return 0 if want.stemtype == 0 else 1


# --------------------------------------------------------------------------
# Formatting helpers from gkstring.c that only need names
# --------------------------------------------------------------------------


def AddParadigmInfo(wf, dels: str) -> str:
    s = ""
    for p in (NameOfTense(wf), NameOfMood(wf), NameOfVoice(wf)):
        if p:
            s += dels + p
    return s


def AddPersNumInfo(wf, dels: str) -> str:
    s = ""
    for p in (NameOfPerson(wf), NameOfNumber(wf)):
        if p:
            s += dels + p
    return s


def AddAdjInfo(wf, dels: str) -> str:
    s = ""
    for p in (NameOfGender(wf), NameOfCase(wf), NameOfDegree(wf)):
        if p:
            s += dels + p
    return s


def SprintGkFlags(gstr: GkString, dels: str, pretty: bool) -> str:
    """``SprintGkFlags(gstr, buf, dels, pretty)``: returns what C appends to buf."""
    buf = ""
    tab = dels[:1] == "\t"
    wf = gstr.form

    def put(s: str) -> None:
        nonlocal buf
        if s or tab:
            buf += dels
        if s:
            buf += s

    put(NameOfStemtype(gstr.stemtype))
    put(NameOfDerivtype(gstr.derivtype))
    put(NameOfTense(wf))
    put(NameOfMood(wf))
    put(NameOfVoice(wf))
    put(NameOfGender(wf))
    put(NameOfCase(wf))
    put(NameOfDegree(wf))
    put(NameOfPerson(wf))
    put(NameOfNumber(wf))
    put(DialectNames(gstr.dialect, dels))
    put(GeogRegionNames(gstr.geogregion, dels))
    put(DomainNames(gstr.domains, dels))
    put(MorphNames(gstr.morphflags, dels, pretty))
    return buf
