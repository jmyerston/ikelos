"""High-level API: analyze and lemmatize Greek words (Unicode or Beta Code)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from . import consts as C
from .betacode import beta_to_unicode, unicode_to_beta
from .cli import analyze_line, perseus_analysis, sorted_analyses
from .gkstring import GkWord
from .morphkeys import (
    DialectNames,
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

_POS = {"N": "noun", "E": "noun", "V": "verb", "P": "participle", "I": "indeclinable"}


@dataclass(frozen=True)
class Analysis:
    """One Morpheus analysis.

    ``form`` is the form Morpheus generated (it may carry quantity marks or a
    normalized accent); ``lemma`` may be a compound such as ``ἀπό-βάλλω``
    when no dictionary entry exists for the compound verb.
    """

    form: str
    lemma: str
    pos: str
    features: dict[str, str] = field(hash=False, compare=False)
    dialects: tuple[str, ...]
    flags: tuple[str, ...]
    stemtype: str
    derivtype: str
    beta_form: str
    beta_lemma: str
    perseus: str  # the C cruncher's Perseus-format string

    def __hash__(self):
        return hash(self.perseus)


def _is_beta(word: str) -> bool:
    return word.isascii()


def _to_beta(word: str) -> str:
    return word if _is_beta(word) else unicode_to_beta(word)


def _features(a: GkWord) -> dict[str, str]:
    wf = a.form
    out = {}
    for k, v in (("tense", NameOfTense(wf)), ("mood", NameOfMood(wf)), ("voice", NameOfVoice(wf)),
                 ("gender", NameOfGender(wf)), ("case", NameOfCase(wf)), ("degree", NameOfDegree(wf)),
                 ("person", NameOfPerson(wf)), ("number", NameOfNumber(wf))):
        if v:
            out[k] = v
    return out


def _flags(ignore_accents: bool, strict_case: bool) -> int:
    flags = C.PERSEUS_FORMAT
    if strict_case:
        flags |= C.STRICT_CASE
    if ignore_accents:
        flags |= C.IGNORE_ACCENTS
    return flags


@lru_cache(maxsize=65536)
def _analyze_beta(beta: str, flags: int) -> tuple[Analysis, ...]:
    out = []
    for g in analyze_line(beta, flags):
        anals = sorted_analyses(g)
        good = sum(1 for a in anals if "-" not in a.lemma)
        for a in anals:
            if good and "-" in a.lemma:
                continue
            perseus = perseus_analysis(a, flags)
            flagnames = tuple(MorphNames(a.morphflags, " ", True).split())
            pos = "indeclinable" if "indeclform" in flagnames else _POS[perseus[0]]
            out.append(Analysis(
                form=beta_to_unicode(a.workword, keep_quantity=False),
                lemma=beta_to_unicode(a.lemma),
                pos=pos,
                features=_features(a),
                dialects=tuple(DialectNames(a.dialect, " ").split()),
                flags=flagnames,
                stemtype=NameOfStemtype(a.stemtype),
                derivtype=NameOfDerivtype(a.derivtype),
                beta_form=a.workword,
                beta_lemma=a.lemma,
                perseus=perseus,
            ))
    return tuple(out)


def analyze(word: str, *, ignore_accents: bool = False, strict_case: bool = False) -> list[Analysis]:
    """All Morpheus analyses of ``word`` (Unicode Greek or Morpheus Beta Code).

    ``ignore_accents`` corresponds to cruncher ``-n``; ``strict_case=False``
    (cruncher ``-S``) also tries a lower-cased form of capitalized words.
    """
    word = word.strip()
    if not word:
        return []
    return list(_analyze_beta(_to_beta(word), _flags(ignore_accents, strict_case)))


def lemmatize(word: str, **kwargs) -> list[str]:
    """Distinct lemmas of ``word`` (Unicode), in analysis order."""
    seen: dict[str, None] = {}
    for a in analyze(word, **kwargs):
        seen.setdefault(a.lemma, None)
    return list(seen)
