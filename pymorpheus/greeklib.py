"""Port of ``src/greeklib`` (Beta Code phonology primitives) and the
character-class macros of ``src/includes/greek.h``.

Conventions used throughout the port:

* C strings are Python ``str``. C functions that modify their argument in
  place return the new string instead.
* A C ``char *`` into a word becomes an integer index into it. ``P_ERR`` is
  ``-1``. Reading past the end of a string yields ``"\\0"`` (see :func:`at`),
  just as C reads the terminating NUL.
* Character classes follow the C locale (ASCII only).
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# greek.h constants and macros
# --------------------------------------------------------------------------

MAXWORDSIZE = 60

YES, NO = 1, 0
P_ERR = -1
I_ERR = -1
C_ERR = "\xff"  # (char) -1

ACUTE = "/"
GRAVE = "\\"
CIRCUMFLEX = "="
NOACCENT = " "
DIAERESIS = "+"
BETA_UCASE_MARKER = "*"
SUBSCR = "|"
HARDLONG = "_"
HARDSHORT = "^"
STEMSEP = "-"
ROUGHBR = "("
SMOOTHBR = ")"
NOBREATH = " "
ZEROEND = "*"

ULTIMA, PENULT, ANTEPENULT = 0, 1, 2
LONG, SHORT = 1, 0

NUL = "\0"


def at(s: str, i: int) -> str:
    """``s[i]`` with C semantics at the edges: NUL past either end."""
    return s[i] if 0 <= i < len(s) else NUL


def isalpha(c: str) -> bool:
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def isupper(c: str) -> bool:
    return "A" <= c <= "Z"


def isspace(c: str) -> bool:
    return c in " \t\n\v\f\r"


def tolower(c: str) -> str:
    return c.lower() if isupper(c) else c


_SHVWL = frozenset("aeiouAEIOU")
_LVWL = frozenset("hwHW")
_VOWEL = _SHVWL | _LVWL


def Is_alph(c: str) -> bool:
    return isalpha(c) and c not in "jvJV"


def Is_shvwl(c: str) -> bool:
    return c in _SHVWL


def Is_lvwl(c: str) -> bool:
    return c in _LVWL


def Is_vowel(c: str) -> bool:
    return c in _VOWEL


def Is_cons(c: str) -> bool:
    return Is_alph(c) and c not in _VOWEL


def Is_dblcons(c: str) -> bool:
    return c in ("c", "y", "z")


def Is_accent(c: str) -> bool:
    return c in ("/", "\\", "=")


def Is_quant(c: str) -> bool:
    return c in ("_", "^")


def Is_stemsep(c: str) -> bool:
    return c == "-"


def Is_diaeresis(c: str) -> bool:
    return c == "+"


def Is_breath(c: str) -> bool:
    return c in ("(", ")")


def Is_diacrit(c: str) -> bool:
    return Is_accent(c) or Is_quant(c) or Is_breath(c) or c == "|" or c == "+"


def Is_greek(c: str) -> bool:
    return Is_alph(c) or Is_diacrit(c)


def Is_labial(c: str) -> bool:
    return c in ("p", "b", "f")


def Is_dental(c: str) -> bool:
    return c in ("t", "d", "q")


def Is_palatal(c: str) -> bool:
    return c in ("k", "g", "x", "c")


def Is_smooth(c: str) -> bool:
    return c in ("p", "t", "k")


def Is_middle(c: str) -> bool:
    return c in ("b", "d", "g")


def Is_rough(c: str) -> bool:
    return c in ("f", "q", "x")


def Is_unasp(c: str) -> bool:
    return Is_smooth(c) or Is_middle(c)


Is_asp = Is_rough


def Is_stop(c: str) -> bool:
    return Is_unasp(c) or Is_asp(c)


def Is_rei_char(c: str) -> bool:
    return c in ("r", "i", "e")


def Is_liquid(c: str) -> bool:
    return c in ("l", "r")


def Is_nasal(c: str) -> bool:
    return c in ("m", "n")


def Is_double(c: str) -> bool:
    return c in ("z", "c", "y")


def lastn(word: str, n: int) -> str:
    """``lastn(word,n)``: the last n characters (whole word if shorter)."""
    return word[len(word) - n:] if n <= len(word) else word


def A_CONTR(verb: str) -> bool:
    return verb.endswith("a/w") or verb.endswith("a/omai")


def E_CONTR(verb: str) -> bool:
    return verb.endswith("e/w") or verb.endswith("e/omai")


def O_CONTR(verb: str) -> bool:
    return verb.endswith("o/w") or verb.endswith("o/omai")


def Is_contr(verb: str) -> bool:
    return A_CONTR(verb) or E_CONTR(verb) or O_CONTR(verb)


# --------------------------------------------------------------------------
# String primitives
# --------------------------------------------------------------------------


def cstr(s: str) -> str:
    """Truncate at the first NUL, as C would see the string."""
    i = s.find(NUL)
    return s if i < 0 else s[:i]


def cinsert(c: str, word: str, p: int) -> str:
    """``cinsert``: insert ``c`` before index ``p``."""
    return word[:p] + c + word[p:]


def strsqz(word: str, p: int, n: int = 1) -> str:
    """``strsqz``: squeeze out ``n`` chars beginning at ``p``.

    The C loop stops copying early when it meets a NUL inside the squeezed
    range, which only matters if ``p + n`` runs past the end.
    """
    if p + n > len(word):
        return word[:p]
    return word[:p] + word[p + n:]


def subchar(s: str, c1: str, c2: str) -> str:
    return s.replace(c1, c2)


def is_blank(s: str) -> bool:
    return all(isspace(c) for c in s)


def is_substring(s1: str, s2: str) -> int:
    """Index of ``s1`` in ``s2``, or -1 (C returns NULL)."""
    if not s1 or len(s1) > len(s2):
        return -1
    return s2.find(s1)


def Xstrncmp(s1: str, s2: str, n: int) -> int:
    for i in range(n):
        c1, c2 = at(s1, i), at(s2, i)
        if c1 != c2:
            return ord(c1) - ord(c2)
        if c1 == NUL:
            return 0
    return 0


def strcmp(s1: str, s2: str) -> int:
    if s1 == s2:
        return 0
    return Xstrncmp(s1, s2, max(len(s1), len(s2)) + 1)


# --------------------------------------------------------------------------
# Accent, breathing, syllables
# --------------------------------------------------------------------------


def is_diphth(word: str, p: int) -> bool:
    """``is_diphth(p, word)``: is ``word[p]`` the second vowel of a diphthong?"""
    if p - 1 < 0:
        return False
    if Is_diaeresis(at(word, p + 1)):
        return False
    c2 = tolower(at(word, p))
    if c2 != "i" and c2 != "u":
        return False
    c1 = tolower(word[p - 1])
    if not Is_vowel(c1):
        return False
    if c1 in ("a", "e", "o"):
        return True
    if c2 == "i":
        return c1 == "u"
    return c1 == "h"  # c2 == 'u'


def starts_w_diphth(stem: str) -> bool:
    return is_diphth(stem, 1)


def nsylls(word: str, start: int = 0) -> int:
    """``nsylls(word + start)``."""
    count = 0
    for p in range(len(word) - 1, start - 1, -1):
        if Is_vowel(word[p]) and not _is_diphth_from(word, p, start):
            count += 1
    return count


def _is_diphth_from(word: str, p: int, start: int) -> bool:
    # is_diphth(p, word + start): the "word" boundary is ``start``
    if p - 1 < start:
        return False
    return is_diphth(word, p)


def getsyll(word: str, syll: int) -> int:
    """Index of the vowel of syllable ``syll`` (0 = ultima), or -1."""
    if syll < 0 or syll > 2:
        return P_ERR
    count = 0
    for p in range(len(word) - 1, -1, -1):
        if Is_vowel(word[p]):
            if count == syll:
                return p
            if not is_diphth(word, p):
                count += 1
    return P_ERR


def getsyll2(word: str, syll: int) -> int:
    if nsylls(word) == 0:
        return 0
    p = getsyll(word, syll)
    if p == P_ERR:
        return p
    return p - 1 if is_diphth(word, p) else p


def getaccp(word: str, syll: int) -> int:
    p = getsyll(word, syll)
    if p == P_ERR:
        return P_ERR
    p += 1
    while Is_breath(at(word, p)) or Is_quant(at(word, p)):
        p += 1
    return p


def getaccent(word: str, syll: int) -> str:
    p = getaccp(word, syll)
    if p == P_ERR:
        return C_ERR
    c = at(word, p)
    return c if Is_accent(c) else NOACCENT


def checkaccent(word: str) -> tuple[int, int, str]:
    """Return ``(rval, syll, acc)`` as the C out-parameters."""
    for syll in (ULTIMA, PENULT, ANTEPENULT):
        acc = getaccent(word, syll)
        if acc != NOACCENT:
            return syll, syll, acc
    return -1, -1, NOACCENT


def getbreath(s: str) -> str:
    for c in s:
        if Is_breath(c):
            return c
    return NOBREATH


def hasaccent(s: str) -> bool:
    return any(Is_accent(c) for c in s)


def has_diaeresis(s: str) -> bool:
    return DIAERESIS in s


def has_quant(s: str) -> bool:
    return HARDLONG in s or HARDSHORT in s


def naccents(s: str) -> int:
    return sum(1 for c in s if Is_accent(c))


def addaccent(word: str, accent: str, p: int) -> str:
    """``addaccent(word, accent, p)``: put ``accent`` on the vowel at ``p``."""
    if at(word, 0) == "*" and Is_breath(at(word, 1)):
        if p == 2:
            return cinsert(accent, word, 2)
        if p == 3 and is_diphth(word, p):
            return cinsert(accent, word, 2)
    p += 1
    while Is_breath(at(word, p)) or Is_quant(at(word, p)):
        p += 1
    if accent == CIRCUMFLEX and at(word, p - 1) == HARDLONG:
        word = strsqz(word, p - 1, 1)
        p -= 1
    return cinsert(accent, word, p)


def addbreath(w: str, c: str) -> str:
    """``addbreath``: add breathing ``c`` after the initial vowel/diphthong."""
    p = 0
    c0 = at(w, 0)
    if c0 in ("a", "e", "o"):
        if at(w, 2) != DIAERESIS and at(w, 1) in ("i", "u"):
            p = 2
        else:
            p = 1
    elif c0 in ("w", "h"):
        p = 2 if at(w, 1) == "u" else 1
    elif Is_vowel(c0):
        p = 1
    if Is_breath(c):
        if p > len(w):  # cinsert past the NUL: C writes garbage; keep sane
            return w + c
        return cinsert(c, w, p)
    return w


def aspirate(c: str) -> str:
    """``aspirate(p)``: the aspirated counterpart of an unaspirated stop."""
    if c in ("t", "d"):
        return "q"
    if c in ("p", "b"):
        return "f"
    if c in ("k", "g"):
        return "x"
    return c


def beta_tolower(word: str) -> str:
    """``*)/andra`` -> ``a)/ndra``."""
    if at(word, 0) != BETA_UCASE_MARKER:
        return word
    s = 0
    while s < len(word) and not isalpha(word[s]):
        s += 1
    if s >= len(word):
        # *word = NUL; Xstrcpy(s, s+1) past the end
        return ""
    return word[s] + word[1:s] + word[s + 1:]


# --------------------------------------------------------------------------
# Quantity
# --------------------------------------------------------------------------


def long_by_isub(word: str, p: int) -> bool:
    c1 = at(word, p + 1)
    return c1 == "|" or (Is_breath(c1) and at(word, p + 2) == "|")


def quantprim(word: str, syll: int, is_ending: bool, is_oblique: bool) -> int:
    p = getsyll(word, syll)
    if p == P_ERR:
        return I_ERR
    s = p
    while not Is_cons(at(word, s)) and at(word, s) != NUL:
        if word[s] == HARDLONG:
            return LONG
        if word[s] == HARDSHORT:
            return SHORT
        s += 1
    if long_by_isub(word, p):
        return LONG
    c = word[p]
    if is_diphth(word, p):
        if c == "i" and at(word, p - 1) in ("a", "o"):
            nxt = at(word, p + 1)
            if is_ending and not is_oblique and (
                nxt == NUL or (Is_accent(nxt) and at(word, p + 2) == NUL)
            ):
                return SHORT
            return LONG
        return LONG
    if Is_lvwl(c):
        return LONG
    if Is_shvwl(c):
        return LONG if at(word, p + 1) == SUBSCR else SHORT
    return I_ERR


def getquantity(word: str, syll: int, nom: str | None, is_ending: bool, is_oblique: bool) -> int:
    p = getsyll(word, syll)
    if p == P_ERR:
        return I_ERR
    c = at(word, p + 1)
    if Is_quant(c):
        return LONG if c == HARDLONG else SHORT
    return quantprim(word, syll, is_ending, is_oblique)


def longbyposition(s: str, p: int = 0) -> int:
    """0: not long by position, 1: definitely, 2: possibly."""
    while Is_vowel(at(s, p)) or (at(s, p) != NUL and not isalpha(s[p])):
        p += 1
    c = at(s, p)
    if Is_dblcons(c):
        return 1
    if not Is_cons(at(s, p + 1)):
        return 0
    # C bug preserved: Is_labial(*(s+1) && Is_stop(*s)) tests a boolean
    if Is_cons(c):
        return 1
    return 0


# --------------------------------------------------------------------------
# Stripping
# --------------------------------------------------------------------------


def stripacc(word: str) -> tuple[str, int]:
    """Remove all accents. Returns ``(word, n)`` where ``n`` is the
    1-based syllable (from the end) of the last accent in the word, 0 if none."""
    if "/" not in word and "\\" not in word and "=" not in word:
        return word, 0
    rval = 0
    out = list(word)
    for p in range(len(word) - 1, -1, -1):
        if Is_accent(word[p]):
            if not rval:
                rval = nsylls(word, p) + 1
            del out[p]
    return "".join(out), rval


def stripacc_s(word: str) -> str:
    return stripacc(word)[0]


def stripacute(s: str) -> str:
    # after squeezing, the C loop still advances: the next char is skipped
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == ACUTE:
            i += 1  # squeezed
            if i < n:
                out.append(s[i])  # skipped, kept as is
            else:
                break
            i += 1
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def stripbreath(word: str) -> str:
    return word.replace("(", "").replace(")", "")


def stripdiaer(word: str) -> str:
    return word.replace("+", "")


def stripshortmark(word: str) -> str:
    return word.replace("^", "")


def striplongmark(word: str) -> str:
    return word.replace("_", "")


def stripquant(word: str) -> str:
    return word.replace("^", "").replace("_", "")


def stripstemsep(word: str) -> str:
    return word.replace("-", "")


def stripzeroend(word: str) -> str:
    return word[:-1] if word.endswith("*") else word


def zap_rr_breath(s: str) -> str:
    """``a)nanti/r)r(hton`` -> ``a)nanti/rrhton`` (never at index 0)."""
    i = 1
    while i < len(s):
        if s[i] == "r" and at(s, i + 1) == ")" and at(s, i + 2) == "r" and at(s, i + 3) == "(":
            s = s[:i] + "rr" + s[i + 4:]
        i += 1
    return s


def stripmetachars(s: str) -> str:
    s = stripquant(s)
    s = stripzeroend(s)
    s = stripstemsep(s)
    return zap_rr_breath(s)


def zap_extra_breath(s: str) -> str:
    """``e)nh(/bwsa`` -> ``e)nh/bwsa``."""
    i = 2 if (at(s, 0) == "r" and at(s, 1) == ROUGHBR) else 0
    extra = 0
    while i < len(s):
        c = s[i]
        if Is_cons(c):
            extra += 1
            i += 1
            continue
        if c in (ROUGHBR, SMOOTHBR):
            if not extra:
                extra += 1
                i += 1
                continue
            s = s[:i] + s[i + 1:]
        i += 1
    return s


def has_extra_breath(s: str) -> bool:
    extra = 0
    for c in s:
        if Is_cons(c):
            extra += 1
            continue
        if c in (ROUGHBR, SMOOTHBR):
            if not extra:
                extra += 1
                continue
            return True
    return False


def _is_junk(c: str) -> bool:
    return c in ',.:;"<>[]^-'


def standword(word: str) -> str:
    """Strip leading junk, extra accents, diaereses and punctuation."""
    word = stripdiaer(word)
    word = zap_rr_breath(word)
    a = 0
    while a < len(word) and _is_junk(word[a]):
        a += 1
    out = []
    w = list(word)
    while a < len(w):
        c = w[a]
        if Is_accent(c):
            rest = "".join(w[a + 1:])
            w[a + 1:] = list(stripacc(rest)[0])
        if c == GRAVE:
            c = w[a] = ACUTE
        if c == "*" and a > 0:
            a += 1
            continue
        if not _is_junk(c):
            out.append(c)
        a += 1
    return "".join(out)


def zap2acc(s: str) -> str:
    out = []
    have = False
    for c in s:
        if c in (ACUTE, GRAVE, CIRCUMFLEX):
            if have:
                continue
            have = True
        out.append(c)
    return "".join(out)


def striphyph(s: str) -> str:
    # Xstrcpy(s, s+1) then s++: the char after each hyphen is not examined
    out = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "-":
            i += 1
            if i >= n:
                break
            out.append(s[i])
            i += 1
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def ends_in(s1: str, s2: str) -> bool:
    """Does ``s1`` end with ``s2`` (ignoring accents and diaereses)?"""
    t1 = stripdiaer(stripacc(s1)[0])
    t2 = stripdiaer(stripacc(s2)[0])
    return t1.endswith(t2)


# --------------------------------------------------------------------------
# do_dissim.c: Grassmann's law
# --------------------------------------------------------------------------


def next_cons(s: str, p: int) -> int:
    while Is_cons(at(s, p)) or Is_accent(at(s, p)):
        p += 1
    while Is_vowel(at(s, p)) or Is_accent(at(s, p)):
        p += 1
    return p


def next_cons_rough(s: str, p: int) -> bool:
    cp = next_cons(s, p)
    if Is_asp(at(s, cp)):
        return True
    return at(s, cp) == "s" and Is_asp(at(s, cp + 1))


_DEASPIRATE = {"q": "t", "x": "k", "f": "p"}


def do_dissim(s: str, stype: int) -> tuple[str, bool]:
    """Deaspirate the first aspirate followed by another one. ``(s, changed)``."""
    from .consts import PP_AP, VERBSTEM

    if s and Is_asp(s[-1]) and (stype & VERBSTEM) == PP_AP:
        return s, False
    for p, c in enumerate(s):
        if Is_asp(c) and next_cons_rough(s, p):
            return s[:p] + _DEASPIRATE[c] + s[p + 1:], True
    return s, False


# --------------------------------------------------------------------------
# binlook.c
# --------------------------------------------------------------------------


def binlook(table, tag, exact_match: bool, compare) -> int:
    """Binary search ``table`` (a sequence) for ``tag`` with ``compare``.

    Without ``exact_match``, returns the index of the last element <= tag
    (as the C code computes it); otherwise -1 when absent.
    """
    nelems = len(table)
    low, high, mid = 0, nelems - 1, 0
    while low <= high:
        mid = (low + high) // 2
        comp = compare(tag, table[mid])
        if comp < 0:
            high = mid - 1
        elif comp > 0:
            low = mid + 1
        else:
            return mid
    if exact_match:
        return -1
    if mid > 0:
        i = mid - 1
        while i < nelems:
            if compare(tag, table[i]) < 0:
                break
            i += 1
        if i > 0:
            i -= 1
    else:
        i = 0
    return i


def Xstrncat(s1: str, s2: str, n: int) -> str:
    """``Xstrncat(s1, s2, n)``: concatenate, truncating to ``n - 1`` chars."""
    s = s1 + s2
    return s[: n - 1] if len(s) > n - 1 else s
