"""Core data types (``src/includes/gkstring.h``, ``greek.h``) and the
helpers of ``src/morphlib/{gkstring,morphflags,new_val,adddomain}.c``.

Morph flags (``MorphFlags gs_morphflags[12]``) are a Python ``int``: C flag
``n`` (1..96) is bit ``n - 1``, i.e. byte ``(n-1)//8``, bit ``(n-1)%8``,
exactly the C layout read little-endian.
"""

from __future__ import annotations

from .consts import (
    ATTIC,
    DISSIMILATION,
    PREVB_AUGMENT,
    ELIDE_PREVERB,
    ROOT_PREVERB,
    RAW_PREVERB,
    UNASP_PREVERB,
    APOCOPE,
    DOUBLED_CONS,
    ITERATIVE,
    UNAUGMENTED,
    PARADIGM,
    STEMTYPE,
    MAXDOMAINS,
)

MORPHFLAG_BYTES = 12
TABSIZE = MORPHFLAG_BYTES * 8

# bitfield widths of word_form (greek.h)
_W_VOICE, _W_MOOD, _W_TENSE, _W_PERSON, _W_NUMBER, _W_CASE, _W_DEGREE, _W_GENDER = (
    0o7, 0o17, 0o17, 0o7, 0o7, 0o77, 0o3, 0o17,
)


class WordForm:
    """``word_form``: verb and nominal features. Values are masked to the C bitfield widths
    by the ``set_*`` helpers; plain attribute assignment is used for already valid values."""

    __slots__ = ("voice", "mood", "tense", "person", "number", "case", "degree", "gender")

    def __init__(self, voice=0, mood=0, tense=0, person=0, number=0, case=0, degree=0, gender=0):
        self.voice = voice
        self.mood = mood
        self.tense = tense
        self.person = person
        self.number = number
        self.case = case
        self.degree = degree
        self.gender = gender

    def copy(self) -> "WordForm":
        return WordForm(self.voice, self.mood, self.tense, self.person, self.number,
                        self.case, self.degree, self.gender)

    def astuple(self):
        return (self.voice, self.mood, self.tense, self.person, self.number,
                self.case, self.degree, self.gender)

    def __eq__(self, other):
        return isinstance(other, WordForm) and self.astuple() == other.astuple()

    def __repr__(self):
        return "WordForm(%s)" % ", ".join(f"{k}={getattr(self, k)}" for k in self.__slots__ if getattr(self, k))

    # setters with C bitfield truncation
    def set_voice(self, v): self.voice = v & _W_VOICE
    def set_mood(self, v): self.mood = v & _W_MOOD
    def set_tense(self, v): self.tense = v & _W_TENSE
    def set_person(self, v): self.person = v & _W_PERSON
    def set_number(self, v): self.number = v & _W_NUMBER
    def set_case(self, v): self.case = v & _W_CASE
    def set_degree(self, v): self.degree = v & _W_DEGREE
    def set_gender(self, v): self.gender = v & _W_GENDER


def eq_forminfo(f1: WordForm, f2: WordForm) -> bool:
    return f1.astuple() == f2.astuple()


def _short(v: int) -> int:
    """Wrap to C ``short`` (Dialect)."""
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class GkString:
    """``gk_string``."""

    __slots__ = ("form", "stemtype", "derivtype", "dialect", "geogregion", "morphflags",
                 "domains", "gkstring")

    def __init__(self, gkstring: str = "", form: WordForm | None = None, stemtype: int = 0,
                 derivtype: int = 0, dialect: int = 0, geogregion: int = 0,
                 morphflags: int = 0, domains: str = ""):
        self.form = form if form is not None else WordForm()
        self.stemtype = stemtype
        self.derivtype = derivtype
        self.dialect = dialect
        self.geogregion = geogregion
        self.morphflags = morphflags
        self.domains = domains
        self.gkstring = gkstring

    def copy(self) -> "GkString":
        g = GkString.__new__(GkString)
        g.form = self.form.copy()
        g.stemtype = self.stemtype
        g.derivtype = self.derivtype
        g.dialect = self.dialect
        g.geogregion = self.geogregion
        g.morphflags = self.morphflags
        g.domains = self.domains
        g.gkstring = self.gkstring
        return g

    def assign(self, other: "GkString") -> None:
        """``*self = *other``."""
        self.form = other.form.copy()
        self.stemtype = other.stemtype
        self.derivtype = other.derivtype
        self.dialect = other.dialect
        self.geogregion = other.geogregion
        self.morphflags = other.morphflags
        self.domains = other.domains
        self.gkstring = other.gkstring

    def __repr__(self):
        return (f"GkString({self.gkstring!r}, {self.form!r}, stemtype={self.stemtype:o}, "
                f"deriv={self.derivtype:o}, dial={self.dialect:o}, mf={self.morphflags:x}, "
                f"dom={self.domains!r})")


_WORD_STRS = ("lemma", "dictform", "engform", "rawprvb", "rawword", "workword", "crasis")
_WORD_GSTRS = ("preverb", "aug1", "stem", "suffix", "endstring")


class GkWord:
    """``gk_word`` and ``gk_analysis`` (union of their fields).

    The ``gs_*`` members are ``GkString``s named ``preverb``, ``aug1``, ``stem``,
    ``suffix`` and ``endstring`` (C: ``prvb_gstr_of`` etc.); the C macros
    ``preverb_of(X)`` etc. are ``X.preverb.gkstring``.
    """

    __slots__ = ("form", "stemtype", "derivtype", "dialect", "geogregion", "morphflags",
                 "domains", "prntflags", "totanal", "lemma", "dictform", "engform",
                 "preverb", "aug1", "stem", "suffix", "endstring",
                 "rawprvb", "rawword", "workword", "crasis", "oddkeys", "analyses")

    def __init__(self):
        self.form = WordForm()
        self.stemtype = 0
        self.derivtype = 0
        self.dialect = 0
        self.geogregion = 0
        self.morphflags = 0
        self.domains = ""
        self.prntflags = 0
        self.totanal = 0
        self.lemma = ""
        self.dictform = ""
        self.engform = ""
        self.preverb = GkString()
        self.aug1 = GkString()
        self.stem = GkString()
        self.suffix = GkString()
        self.endstring = GkString()
        self.rawprvb = ""
        self.rawword = ""
        self.workword = ""
        self.crasis = ""
        self.oddkeys = None
        self.analyses = None

    def copy(self) -> "GkWord":
        w = GkWord.__new__(GkWord)
        w.form = self.form.copy()
        w.stemtype = self.stemtype
        w.derivtype = self.derivtype
        w.dialect = self.dialect
        w.geogregion = self.geogregion
        w.morphflags = self.morphflags
        w.domains = self.domains
        w.prntflags = self.prntflags
        w.totanal = self.totanal
        w.lemma = self.lemma
        w.dictform = self.dictform
        w.engform = self.engform
        w.preverb = self.preverb.copy()
        w.aug1 = self.aug1.copy()
        w.stem = self.stem.copy()
        w.suffix = self.suffix.copy()
        w.endstring = self.endstring.copy()
        w.rawprvb = self.rawprvb
        w.rawword = self.rawword
        w.workword = self.workword
        w.crasis = self.crasis
        w.oddkeys = self.oddkeys
        w.analyses = self.analyses  # pointer copy, as in C
        return w

    def assign(self, other: "GkWord") -> None:
        """``*self = *other``."""
        for k in GkWord.__slots__:
            v = getattr(other, k)
            if isinstance(v, (GkString, WordForm)):
                v = v.copy()
            setattr(self, k, v)

    def __repr__(self):
        return (f"GkWord(work={self.workword!r}, lemma={self.lemma!r}, pb={self.preverb.gkstring!r}, "
                f"aug={self.aug1.gkstring!r}, stem={self.stem.gkstring!r}, "
                f"suff={self.suffix.gkstring!r}, end={self.endstring.gkstring!r})")


GkAnalysis = GkWord


def CreatGkword(num: int = 1) -> list[GkWord]:
    return [GkWord() for _ in range(num)]


def CreatGkString(num: int = 1) -> list[GkString]:
    return [GkString() for _ in range(num)]


# --------------------------------------------------------------------------
# morphflags.c (flags as an int)
# --------------------------------------------------------------------------


# NB: flags > 96 (only GROUP_NAME = 110, "is_group", unused in the Greek data)
# overflow into st_domains in C; here they are just high bits.


def _bit(n: int) -> int:
    n &= 0o377
    if n == 0:
        return 0  # C reads Mf[-1]; in practice never set
    return 1 << (n - 1)


def has_morphflag(mf: int, n: int) -> int:
    """C value: the bit within its byte (``1 << ((n-1) % 8)``) or 0."""
    n &= 0o377
    if n == 0:
        return 0
    if mf >> (n - 1) & 1:
        return 1 << ((n - 1) % 8)
    return 0


def add_morphflag(mf: int, n: int) -> int:
    return mf | _bit(n)


def zap_morphflag(mf: int, n: int) -> int:
    return mf & ~_bit(n)


def set_morphflag(n: int) -> int:
    """``set_morphflag(Mf, n)``: clear all, then set ``n`` (if > 0)."""
    n &= 0o377
    return _bit(n) if n > 0 else 0


def no_morphflag(mf: int) -> bool:
    return (mf & ((1 << TABSIZE) - 1)) == 0


def overlap_morphflags(mf1: int, mf2: int) -> bool:
    return (mf1 & mf2 & ((1 << TABSIZE) - 1)) != 0


_PRVB_FLAGS = 0
for _f in (DISSIMILATION, PREVB_AUGMENT, ELIDE_PREVERB, ROOT_PREVERB, RAW_PREVERB,
           UNASP_PREVERB, APOCOPE, DOUBLED_CONS):
    _PRVB_FLAGS |= _bit(_f)


def is_prvb_morphflag(n: int) -> bool:
    return 0 < n <= TABSIZE and bool(_PRVB_FLAGS >> (n - 1) & 1)


def xfer_prvbflags(word_mf: int, prvb_mf: int) -> tuple[int, int]:
    """Move the preverb-specific flags from ``word_mf`` to ``prvb_mf``."""
    moving = word_mf & _PRVB_FLAGS
    return word_mf & ~moving, prvb_mf | moving


# --------------------------------------------------------------------------
# gkstring.c
# --------------------------------------------------------------------------


def AndDialect(d1: int, d2: int) -> int:
    """Combine two dialects; -1 if incompatible, 0 if neither is set."""
    if not d1 and not d2:
        return 0
    if d1 and d2:
        d = _short(d1 & d2)
        return d if d else -1
    return d2 if not d1 else d1


def low_bit_of(n: int) -> int:
    mask = 0
    for i in range(32):
        mask += i
        if n & mask:
            return n & mask
    return 0  # C falls off the end (undefined); callers never use it


def CompGkString(g1: GkString, g2: GkString) -> int:
    f1, f2 = g1.form, g2.form
    rval = 0
    while True:  # "goto finish"
        s1 = g1.stemtype & STEMTYPE
        s2 = g2.stemtype & STEMTYPE
        if s1 != s2:
            rval = s1 - s2
            break
        h1 = has_morphflag(g1.morphflags, ITERATIVE)
        h2 = has_morphflag(g2.morphflags, ITERATIVE)
        if h1 != h2:
            rval = h1 - h2
            break
        if f1.tense != f2.tense:
            rval = f1.tense - f2.tense
            break
        if f1.voice != f2.voice:
            rval = f1.voice - f2.voice
            break
        if f1.mood != f2.mood:
            rval = f1.mood - f2.mood
            break
        if f1.degree != f2.degree:
            rval = f1.degree - f2.degree
            break
        if f1.case and f2.case:
            c1 = 1000 * f1.number + 10 * low_bit_of(f1.case) + low_bit_of(f1.gender)
            c2 = 1000 * f2.number + 10 * low_bit_of(f2.case) + low_bit_of(f2.gender)
            if c1 != c2:
                rval = c1 - c2
                break
        if f1.gender and f2.gender:
            l1, l2 = low_bit_of(f1.gender), low_bit_of(f2.gender)
            if l1 != l2:
                rval = l1 - l2
                break
        h1 = has_morphflag(g1.morphflags, UNAUGMENTED)
        h2 = has_morphflag(g2.morphflags, UNAUGMENTED)
        if h1 != h2:
            rval = h1 - h2
            break
        if f1.person and f2.person:
            p1 = 10 * f1.number + f1.person
            p2 = 10 * f2.number + f2.person
            if p1 != p2:
                rval = p1 - p2
                break
        if f1.number and f2.number:
            n1, n2 = low_bit_of(f1.number), low_bit_of(f2.number)
            if n1 != n2:
                rval = n2 - n1
                break
        d1, d2 = g1.dialect & PARADIGM, g2.dialect & PARADIGM
        if d1 != d2:
            rval = d2 - d1
            break
        d1, d2 = g1.dialect & ATTIC, g2.dialect & ATTIC
        if d1 != d2:
            rval = d2 - d1
            break
        if g1.dialect != g2.dialect:
            rval = g1.dialect - g2.dialect
            break
        break
    if not rval:
        p1 = has_morphflag(g1.morphflags, PARADIGM)
        p2 = has_morphflag(g2.morphflags, PARADIGM)
        if p1 != p2:
            return p2 - p1
    return rval


# --------------------------------------------------------------------------
# new_val.c / adddomain.c (the add_val callbacks of the key tables)
# --------------------------------------------------------------------------


def add_domain(gstr, n: int) -> int:
    doms = gstr.domains
    if len(doms) >= MAXDOMAINS:
        return -1
    c = chr(n & 0xFF)
    if c in doms:
        return 0
    gstr.domains = doms + c
    return 1


def new_person(g, v): g.form.set_person(v)
def new_number(g, v): g.form.set_number(v)
def new_case(g, v): g.form.set_case(g.form.case | v)
def new_tense(g, v): g.form.set_tense(v)
def new_mood(g, v): g.form.set_mood(v)
def new_degree(g, v): g.form.set_degree(v)
def new_gender(g, v): g.form.set_gender(g.form.gender | v)


def new_voice(g, v):
    from .consts import ACTIVE, MEDIO_PASS

    cur = g.form.voice
    if v == ACTIVE and (cur & MEDIO_PASS):
        g.form.set_voice(v)
    elif (v & MEDIO_PASS) and cur == ACTIVE:
        g.form.set_voice(v)
    else:
        g.form.set_voice(cur | v)


def new_dialect(g, v): g.dialect = _short(g.dialect | v)
def new_region(g, v): g.geogregion = (g.geogregion | v) & 0xFFFFFFFF
def new_morphflags(g, v): g.morphflags = add_morphflag(g.morphflags, v)
def new_stemtype(g, v): g.stemtype = v & 0xFFFFFFFF
def new_derivtype(g, v): g.derivtype = v & 0xFFFFFFFF
def new_domain(g, v): add_domain(g, v)


SETTERS = {
    "new_person": new_person, "new_number": new_number, "new_case": new_case,
    "new_tense": new_tense, "new_voice": new_voice, "new_mood": new_mood,
    "new_degree": new_degree, "new_gender": new_gender, "new_dialect": new_dialect,
    "new_region": new_region, "new_morphflags": new_morphflags,
    "new_stemtype": new_stemtype, "new_domain": new_domain, "new_derivtype": new_derivtype,
}
