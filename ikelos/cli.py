"""Command-line front end mimicking the C ``cruncher`` for Greek
(``src/anal/stdiomorph.c`` and the Perseus output of ``prntanal.c``).

    echo 'lo/gos' | ikelos -S
"""

from __future__ import annotations

import sys

from . import consts as C
from .analyzer import checkstring
from .gkstring import GkWord
from .greeklib import addbreath, isspace, stripbreath
from .morphkeys import (
    DialectNames,
    DomainNames,
    GeogRegionNames,
    MorphNames,
    NameOfCase,
    NameOfDegree,
    NameOfDerivtype,
    NameOfGender,
    NameOfMood,
    NameOfNumber,
    NameOfPerson,
    NameOfStemtype,
    NameOfTense,
    NameOfVoice,
)

DEFAULT_FLAGS = C.PERSEUS_FORMAT | C.STRICT_CASE


def parse_flags(opts: list[str]) -> int:
    flags = DEFAULT_FLAGS
    for opt in opts:
        if not opt.startswith("-"):
            raise ValueError(f"unexpected argument {opt!r}")
        for ch in opt[1:]:
            if ch == "a":
                flags |= C.SHOW_ANAL
            elif ch == "l":
                flags |= C.SHOW_LEMMA
            elif ch == "m":
                flags |= C.SHOW_MISSES
            elif ch == "b":
                flags |= C.BUFFER_ANALS
            elif ch == "c":
                flags |= C.CHECK_PREVERB
            elif ch == "k":
                flags |= C.KEEP_BETA
            elif ch == "i":
                flags |= C.SHOW_FULL_INFO
            elif ch == "d":
                flags &= ~C.PERSEUS_FORMAT
                flags &= ~C.LEXICON_OUTPUT
                flags |= C.DBASEFORMAT
            elif ch == "s":
                flags |= C.DBASESHORT
            elif ch == "n":
                flags |= C.IGNORE_ACCENTS
            elif ch == "x":
                flags |= C.LEXICON_OUTPUT
            elif ch == "V":
                flags |= C.VERBS_ONLY
            elif ch == "S":
                flags &= ~C.STRICT_CASE
            elif ch == "p":
                flags |= C.PARSE_FORMAT
            elif ch == "P":
                flags &= ~C.PERSEUS_FORMAT
            elif ch == "e":
                flags |= C.ENDING_INDEX
            elif ch in "TIL":
                if ch in "IL":
                    raise ValueError("only Greek is supported")
            else:
                raise ValueError(f"unknown option -{ch}")
    return flags


# --------------------------------------------------------------------------
# Output (prntanal.c / sprntGkflags.c)
# --------------------------------------------------------------------------


def GregSprintGkFlags(g, dels: str = " ", pretty: bool = True) -> str:
    buf = ""
    tab = dels[:1] == "\t"
    wf = g.form
    for s in (NameOfTense(wf), NameOfMood(wf), NameOfVoice(wf), NameOfGender(wf),
              NameOfCase(wf), NameOfDegree(wf), NameOfPerson(wf), NameOfNumber(wf)):
        if s or tab:
            buf += dels
        if s:
            buf += s
    buf += "\t" + DialectNames(g.dialect, dels)
    s = GeogRegionNames(g.geogregion, dels)
    if s or tab:
        buf += dels
    buf += s
    s = DomainNames(g.domains, dels)
    if s or tab:
        buf += dels
    buf += s
    buf += "\t" + MorphNames(g.morphflags, dels, pretty)
    buf += "\t" + NameOfStemtype(g.stemtype)
    s = NameOfDerivtype(g.derivtype)
    if s:
        buf += "," + s
    return buf


def perseus_analysis(anal: GkWord, prntflags: int) -> str:
    """``DumpPerseusAnalysis``: the text between ``<NL>`` and ``</NL>``."""
    if anal.form.mood == C.PARTICIPLE:
        out = "P "
    elif anal.stemtype & (C.NOUNSTEM | C.ADJSTEM):
        out = "E " if "A" <= anal.lemma[:1] <= "Z" else "N "
    elif anal.stemtype & C.PPARTMASK:
        out = "V "
    else:
        out = "I "
    if anal.rawword != anal.workword:
        out += anal.workword + ","
    out += anal.lemma + " "
    if prntflags & C.ENDING_INDEX:
        raise NotImplementedError("-e (ENDING_INDEX) output")
    return out + GregSprintGkFlags(anal, " ", True)


def sorted_analyses(g: GkWord) -> list[GkWord]:
    """``SortAnals``: by lemma (strcmp). glibc's qsort is a stable mergesort;
    Python's sort is stable too."""
    anals = g.analyses[: g.totanal] if g.analyses else []
    return sorted(anals, key=lambda a: a.lemma.encode("latin-1"))


def perseus_strings(g: GkWord, prntflags: int) -> list[str]:
    """``dump_all_anals`` in Perseus format (good analyses only)."""
    anals = sorted_analyses(g)
    goodanals = sum(1 for a in anals if "-" not in a.lemma)
    return [perseus_analysis(a, prntflags) for a in anals
            if not goodanals or "-" not in a.lemma]


def format_word(g: GkWord, prntflags: int) -> str:
    if not prntflags & C.PERSEUS_FORMAT or prntflags & C.SHOW_LEMMA:
        raise NotImplementedError("only the Perseus output format is implemented")
    return g.rawword + "\n" + "".join(f"<NL>{s}</NL>" for s in perseus_strings(g, prntflags)) + "\n"


# --------------------------------------------------------------------------
# Driver (stdiomorph.c)
# --------------------------------------------------------------------------


def _trimwhite(s: str) -> str:
    i = len(s) - 1
    while i > 0 and isspace(s[i]):
        i -= 1
    return s[: i + 1] if s else s


def _trimdigit(s: str) -> str:
    i = len(s) - 1
    while i > 0 and s[i].isdigit():
        i -= 1
    return s[: i + 1] if s else s


def analyze_line(word: str, flags: int) -> list[GkWord]:
    """Run ``checkstring`` as the C main loop does (with the ``-n`` breathing retries).
    Returns the successful GkWords (each printed by cruncher)."""
    out = []
    g = checkstring(word, flags)
    if g is not None and g.totanal > 0:
        out.append(g)
        return out
    if flags & C.IGNORE_ACCENTS:
        tmp = addbreath(stripbreath(word), ")")
        g = checkstring(tmp, flags)
        if g is not None and g.totanal > 0:
            out.append(g)
            return out
        tmp = addbreath(stripbreath(tmp), "(")
        g = checkstring(tmp, flags)
        if g is not None and g.totanal > 0:
            out.append(g)
    return out


def crunch(text: str, opts: list[str] | None = None) -> str:
    """Return what ``cruncher [opts]`` prints on stdout for ``text``."""
    flags = parse_flags(opts or [])
    out = []
    for raw in text.splitlines():
        line = _trimwhite(raw)
        if line.startswith("#"):
            out.append(line + "\n")
            continue
        line = _trimdigit(line)
        p = 0
        while p < len(line) and not isspace(line[p]):
            p += 1
        if p == 0:
            continue
        line = line[:p]
        for g in analyze_line(line, flags):
            out.append(format_word(g, flags))
    return "".join(out)


def analyses_strings(word: str, opts: list[str] | None = None) -> list[str]:
    """The ``<NL>`` entries cruncher prints for one Beta Code word."""
    flags = parse_flags(opts or [])
    res: list[str] = []
    for g in analyze_line(word, flags):
        res += perseus_strings(g, flags)
    return res


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    opts = [a for a in argv if a.startswith("-")]
    try:
        flags = parse_flags(opts)
    except ValueError as e:
        print(f"ikelos: {e}", file=sys.stderr)
        return 2
    for raw in sys.stdin:
        line = _trimwhite(raw.rstrip("\n"))
        if line.startswith("#"):
            sys.stdout.write(line + "\n")
            continue
        line = _trimdigit(line)
        word = line.split()[0] if line and not isspace(line[0]) else ""
        if not word:
            continue
        found = analyze_line(word, flags)
        for g in found:
            sys.stdout.write(format_word(g, flags))
        if not found:
            print(word, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
