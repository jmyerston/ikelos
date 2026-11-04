"""Loaders for the bundled Greek stemlib (see ``tools/export_data.py``).

Everything is loaded lazily and cached for the lifetime of the process.
"""

from __future__ import annotations

import gzip
import json
import struct
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import NamedTuple


# src/includes/endtags.h
KEYLEN = 8


def _data_dir():
    return resources.files("pymorpheus").joinpath("data", "greek")


def _open_gz(rel: str) -> bytes:
    """Read a gzipped data file from the package, e.g. ``rule_files/stemtypes.table``."""
    ref = _data_dir().joinpath(rel + ".gz")
    with ref.open("rb") as raw:
        return gzip.decompress(raw.read())


@lru_cache(maxsize=None)
def read_text(rel: str) -> str:
    """Return a bundled text file (latin-1: Morpheus data is 7-bit Beta Code)."""
    return _open_gz(rel).decode("latin-1")


@lru_cache(maxsize=None)
def read_lines(rel: str) -> tuple[str, ...]:
    return tuple(read_text(rel).splitlines())


# --------------------------------------------------------------------------
# Endtables (decoded from the binary *.out files by the C reader)
# --------------------------------------------------------------------------


class EndRecord(NamedTuple):
    """One ``gk_string`` record from an ``*.out`` endtable (src/morphlib/endio.c)."""

    ending: str
    voice: int
    mood: int
    tense: int
    person: int
    number: int
    case: int
    degree: int
    gender: int
    dialect: int
    geogregion: int
    stemtype: int
    derivtype: int
    morphflags: bytes
    domains: bytes


@lru_cache(maxsize=None)
def _load_tables(kind: str) -> dict[str, tuple[EndRecord, ...]]:
    payload = json.loads(_open_gz_json(kind))
    out: dict[str, tuple[EndRecord, ...]] = {}
    for name, rows in payload["tables"].items():
        out[name] = tuple(
            EndRecord(*row[:13], bytes.fromhex(row[13]), bytes.fromhex(row[14])) for row in rows
        )
    return out


def _open_gz_json(kind: str) -> str:
    ref = _data_dir().joinpath(f"{kind}.json.gz")
    with ref.open("rb") as raw:
        return gzip.decompress(raw.read()).decode("utf-8")


def endtable(stemtype_name: str) -> tuple[EndRecord, ...]:
    """Records of ``endtables/out/<stemtype_name>.out``, in file order."""
    return _load_tables("endtables")[stemtype_name]


def derivtable(name: str) -> tuple[EndRecord, ...]:
    """Records of ``derivs/out/<name>.out``, in file order."""
    return _load_tables("derivs")[name]


def endtable_names() -> list[str]:
    return sorted(_load_tables("endtables"))


def derivtable_names() -> list[str]:
    return sorted(_load_tables("derivs"))


# --------------------------------------------------------------------------
# String comparison (src/morphlib/morphstrcmp.c)
# --------------------------------------------------------------------------


_COMPTAB = str.maketrans("|", "i")  # comptab: iota subscript compares as 'i'


def _mapped(s: str) -> str:
    return s.translate(_COMPTAB) if "|" in s else s


def morphstrcmp(s1: str, s2: str) -> int:
    """C ``morphstrcmp`` (only the sign of the result is meaningful)."""
    a, b = _mapped(s1), _mapped(s2)
    return (a > b) - (a < b)


def morphstrncmp(s1: str, s2: str, n: int) -> int:
    """C ``morphstrncmp`` (only the sign of the result is meaningful)."""
    if n <= 0:
        return 0
    a, b = _mapped(s1[:n]), _mapped(s2[:n])
    return (a > b) - (a < b)


# --------------------------------------------------------------------------
# Stem indices: steminds/{nomind,vbind} + their sparse .lindex pre-indices
# (src/morphlib/retrentry.c, src/greeklib/binlook.c, src/gkdict/dictio.c)
# --------------------------------------------------------------------------


@dataclass
class StemIndex:
    name: str
    lines: tuple[str, ...]
    line_offsets: tuple[int, ...]  # byte offset of each line start
    tags: tuple[str, ...]  # pre-index keys, in file order
    tag_offsets: tuple[int, ...]

    @classmethod
    def load(cls, name: str) -> "StemIndex":
        text = read_text(f"steminds/{name}")
        lines: list[str] = []
        offsets: list[int] = []
        pos = 0
        for line in text.splitlines(keepends=True):
            lines.append(line)
            offsets.append(pos)
            pos += len(line)
        raw = _open_gz(f"steminds/{name}.lindex")
        tags, tag_offsets = [], []
        for i in range(0, len(raw) - len(raw) % 12, 12):
            key, off = struct.unpack_from("<8si", raw, i)
            tags.append(key.split(b"\0", 1)[0].decode("latin-1"))
            tag_offsets.append(off)
        return cls(name, tuple(lines), tuple(offsets), tuple(tags), tuple(tag_offsets))

    # -- C emulation ------------------------------------------------------

    def _binlook(self, tag: str, exact_match: bool) -> int:
        tags = self.tags
        nelems = len(tags)
        low, high, mid = 0, nelems - 1, 0
        while low <= high:
            mid = (low + high) // 2
            comp = morphstrcmp(tag, tags[mid])
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
                if morphstrcmp(tag, tags[i]) < 0:
                    break
                i += 1
            if i > 0:
                i -= 1
        else:
            i = 0
        return i

    def pre_index(self, tag: str, exact_match: bool) -> int:
        """``ChckPreIndex``: byte offset to start scanning from, or -1."""
        if len(tag) > KEYLEN:
            exact_match = False
        rval = self._binlook(tag[:KEYLEN], exact_match)
        if rval < 0:
            return -1
        return 0 if rval == 0 else self.tag_offsets[rval]

    def full_index(self, s: str, offset: int) -> str | None:
        """``ChckFullIndex``: scan from ``offset``; return the text after the key, or None."""
        start = bisect_right(self.line_offsets, offset) - 1
        slen = len(s)
        for line in self.lines[start:]:
            comp = morphstrncmp(s, line, slen)
            if comp == 0 and slen < len(line) and line[slen].isspace():
                # C keeps the trailing newline from fgets
                return line[slen:].lstrip(" \t\n\v\f\r")
            if comp < 0:
                return None
        return None

    def lookup(self, stem: str, *, exact_match: bool) -> str | None:
        """Pre-index + full scan, as in ``gkdict/dictio.c``. Returns the stem keys."""
        off = self.pre_index(stem, exact_match)
        if off < 0:
            return None
        return self.full_index(stem, off)


@lru_cache(maxsize=None)
def nom_index() -> StemIndex:
    """``steminds/nomind``: noun stems (``gkdict/dictio.c:chckstem`` with is_nom)."""
    return StemIndex.load("nomind")


# --------------------------------------------------------------------------
# In-memory line indices (src/gkends/endindex.c: init_endind/checkendind)
# --------------------------------------------------------------------------


class EndIndex:
    """A text file of sorted lines ``key<SPACE>value...``, binary-searched in memory."""

    def __init__(self, lines: tuple[str, ...], use_morphstrcmp: bool):
        self.lines = lines
        self.use_morphstrcmp = use_morphstrcmp
        # lines as the comparison function sees them
        self._cmp_lines = tuple(_mapped(l) for l in lines) if use_morphstrcmp else lines

    @classmethod
    def load(cls, rel: str, *, use_morphstrcmp: bool) -> "EndIndex":
        # init_endind: split on '\n'; a trailing newline yields a final "" entry
        return cls(tuple(read_text(rel).split("\n")), use_morphstrcmp)

    def check(self, key: str) -> str | None:
        """``checkendind``: return the text after ``key + ' '``, or None."""
        curtag = key + " "
        if len(curtag) > 59:  # Xstrncat(curtag, " ", MAXWORDSIZE)
            curtag = curtag[:59]
        taglen = len(curtag)
        if self.use_morphstrcmp:
            curtag = _mapped(curtag)
        lines = self._cmp_lines
        low, high = 0, len(lines) - 1
        while low <= high:
            mid = (low + high) // 2
            pref = lines[mid][:taglen]
            if curtag < pref:
                high = mid - 1
            elif curtag > pref:
                low = mid + 1
            else:
                return self.lines[mid][taglen:]
        return None


@lru_cache(maxsize=None)
def vb_index() -> EndIndex:
    """``steminds/vbind``: verb stems (``chckvstem``)."""
    return EndIndex.load("steminds/vbind", use_morphstrcmp=True)


@lru_cache(maxsize=None)
def noun_end_index() -> EndIndex:
    """``endtables/indices/nendind`` (``chcknend``)."""
    return EndIndex.load("endtables/indices/nendind", use_morphstrcmp=True)


@lru_cache(maxsize=None)
def verb_end_index() -> EndIndex:
    """``endtables/indices/vbendind`` (``chckvend``)."""
    return EndIndex.load("endtables/indices/vbendind", use_morphstrcmp=True)


@lru_cache(maxsize=None)
def deriv_end_index() -> EndIndex:
    """``derivs/indices/derivind`` (``chckdvend``)."""
    return EndIndex.load("derivs/indices/derivind", use_morphstrcmp=True)


@lru_cache(maxsize=None)
def dict_entry_index() -> EndIndex:
    """``stemsrc/lemlist`` (``chckdictent``; plain strncmp)."""
    return EndIndex.load("stemsrc/lemlist", use_morphstrcmp=False)


@lru_cache(maxsize=None)
def compound_verb_index() -> EndIndex:
    """``stemsrc/vbs.cmp.ml`` (``chckcmpvb``; plain strncmp)."""
    return EndIndex.load("stemsrc/vbs.cmp.ml", use_morphstrcmp=False)
