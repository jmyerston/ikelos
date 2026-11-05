"""Conversion between Morpheus Beta Code and Unicode polytonic Greek.

Morpheus' dialect of Beta Code:
  * lowercase ASCII letters (``a b g d e z h q i k l m n c o p r s t u f x y w``)
  * capitals are written ``*`` + diacritics + letter (``*(abask`` -> ``Ἁβασκ``)
  * ``)`` smooth, ``(`` rough breathing; ``/`` acute, ``\\`` grave, ``=`` circumflex
  * ``+`` diaeresis, ``|`` iota subscript
  * ``_`` long / ``^`` short vowel quantity (Morpheus-specific)
  * ``'`` apostrophe (elision)

Within a letter, diacritics are emitted in the order Morpheus uses:
breathing, diaeresis, accent, iota subscript, quantity.
"""

from __future__ import annotations

import unicodedata

BETA_TO_GREEK = {
    "a": "α", "b": "β", "g": "γ", "d": "δ", "e": "ε", "z": "ζ", "h": "η",
    "q": "θ", "i": "ι", "k": "κ", "l": "λ", "m": "μ", "n": "ν", "c": "ξ",
    "o": "ο", "p": "π", "r": "ρ", "s": "σ", "t": "τ", "u": "υ", "f": "φ",
    "x": "χ", "y": "ψ", "w": "ω", "v": "ϝ",
}
GREEK_TO_BETA = {g: b for b, g in BETA_TO_GREEK.items()}
GREEK_TO_BETA["ς"] = "s"
GREEK_TO_BETA["ϲ"] = "s"  # lunate sigma
GREEK_TO_BETA["ϐ"] = "b"
GREEK_TO_BETA["ϑ"] = "q"
GREEK_TO_BETA["ϕ"] = "f"
GREEK_TO_BETA["ϖ"] = "p"

# Morpheus diacritic -> combining character
BETA_DIACRITICS = {
    ")": "̓",  # psili
    "(": "̔",  # dasia
    "/": "́",  # acute
    "\\": "̀",  # grave
    "=": "͂",  # perispomeni
    "+": "̈",  # diaeresis
    "|": "ͅ",  # ypogegrammeni
    "_": "̄",  # macron
    "^": "̆",  # breve
}
COMBINING_TO_BETA = {c: b for b, c in BETA_DIACRITICS.items()}
COMBINING_TO_BETA["́"] = "/"  # combining acute tone mark
COMBINING_TO_BETA["̀"] = "\\"
COMBINING_TO_BETA["̓"] = ")"  # koronis -> smooth breathing

# Canonical Morpheus ordering of diacritics on one letter.
_DIACRITIC_ORDER = {d: i for i, d in enumerate(")(+/\\=|_^")}

# Characters used as an apostrophe in Greek texts; greCy uses U+02BC.
APOSTROPHES = {"'", "ʼ", "’", "᾽", "᾿", "̓"}

_UNICODE_COMPOSITION_ORDER = {d: i for i, d in enumerate("_^)(+/\\=|")}


def unicode_to_beta(text: str, *, keep_quantity: bool = False) -> str:
    """Convert Unicode Greek to Morpheus Beta Code.

    Non-Greek characters are passed through unchanged, except for the various
    apostrophe characters, which become ``'``.
    """
    out: list[str] = []
    for ch in text:
        if ch in ("ʼ", "’", "᾽", "᾿"):
            out.append("'")
            continue
        decomposed = unicodedata.normalize("NFD", ch)
        base, marks = decomposed[0], decomposed[1:]
        is_upper = base != base.lower()
        letter = base.lower()
        if letter in GREEK_TO_BETA:
            beta_marks = sorted(
                (COMBINING_TO_BETA[m] for m in marks if m in COMBINING_TO_BETA),
                key=_DIACRITIC_ORDER.__getitem__,
            )
            if not keep_quantity:
                beta_marks = [m for m in beta_marks if m not in "_^"]
            if is_upper:
                # *, breathing/diaeresis/accent, letter, then iota subscript & quantity
                pre = [m for m in beta_marks if m in ")(+/\\="]
                post = [m for m in beta_marks if m not in ")(+/\\="]
                out.append("*" + "".join(pre) + GREEK_TO_BETA[letter] + "".join(post))
            else:
                out.append(GREEK_TO_BETA[letter] + "".join(beta_marks))
        elif base in COMBINING_TO_BETA:
            # stray combining mark (already decomposed input)
            out.append(COMBINING_TO_BETA[base])
        else:
            out.append(ch)
    return "".join(out)


def beta_to_unicode(text: str, *, keep_quantity: bool = False, final_sigma: bool = True) -> str:
    """Convert Morpheus Beta Code to NFC Unicode Greek.

    Characters that are not part of Beta Code (digits, ``#``, ``-``, spaces,
    ``,`` ...) pass through unchanged, so Morpheus lemmas such as
    ``gallus#1`` or ``a)/nqrwpos,a)/nqrwpos`` remain readable.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "*":
            # capital: * + pre-diacritics + letter + post-diacritics
            j = i + 1
            pre = []
            while j < n and text[j] in ")(+/\\=":
                pre.append(text[j])
                j += 1
            if j < n and text[j].lower() in BETA_TO_GREEK:
                letter = BETA_TO_GREEK[text[j].lower()].upper()
                j += 1
                post = []
                while j < n and text[j] in BETA_DIACRITICS:
                    post.append(text[j])
                    j += 1
                out.append(_compose(letter, pre + post, keep_quantity))
                i = j
                continue
            out.append(ch)
            i += 1
            continue
        if ch in BETA_TO_GREEK:
            j = i + 1
            marks = []
            while j < n and text[j] in BETA_DIACRITICS:
                marks.append(text[j])
                j += 1
            letter = BETA_TO_GREEK[ch]
            if letter == "σ" and final_sigma and (j >= n or not _is_beta_letter_start(text, j)):
                letter = "ς"
            out.append(_compose(letter, marks, keep_quantity))
            i = j
            continue
        if ch == "'":
            out.append("ʼ")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _is_beta_letter_start(text: str, j: int) -> bool:
    return text[j] in BETA_TO_GREEK or text[j] == "*"


def _compose(letter: str, marks: list[str], keep_quantity: bool) -> str:
    if not keep_quantity:
        marks = [m for m in marks if m not in "_^"]
    marks = sorted(marks, key=_UNICODE_COMPOSITION_ORDER.__getitem__)
    return unicodedata.normalize("NFC", letter + "".join(BETA_DIACRITICS[m] for m in marks))


def normalize_beta(word: str) -> str:
    """Canonicalize the order of diacritics within each letter of a beta word."""
    return unicode_to_beta(beta_to_unicode(word, keep_quantity=True), keep_quantity=True)
