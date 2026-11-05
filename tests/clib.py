"""ctypes access to the C Morpheus libraries (dev-only oracle).

Build with ``tools/build_clib.sh``; tests using this are skipped when the
library is missing.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIBPATH = ROOT / "build" / "clib" / ("libmorph.dylib" if sys.platform == "darwin" else "libmorph.so")
MORPHEUS_HOME = Path(os.environ.get("MORPHEUS_HOME", ROOT.parent / "morpheus"))
STEMLIB = MORPHEUS_HOME / "stemlib"

_lib = None


def lib():
    global _lib
    if _lib is None:
        if not LIBPATH.exists():
            return None
        os.environ.setdefault("MORPHLIB", str(STEMLIB))
        _lib = ctypes.CDLL(str(LIBPATH))
    return _lib


BUF = 1024


def cbuf(s: str, size: int = BUF):
    b = ctypes.create_string_buffer(size)
    raw = s.encode("latin-1")
    b[: len(raw)] = raw
    return b


def sval(b) -> str:
    return b.value.decode("latin-1")


def call_str(name: str, s: str, *args, restype=ctypes.c_int):
    """Call ``name(buf, *args)`` on a mutable copy of ``s``; return (result, buf)."""
    f = getattr(lib(), name)
    f.restype = restype
    b = cbuf(s)
    r = f(b, *args)
    return r, sval(b)


# --------------------------------------------------------------------------
# Struct mirrors (layout checked against the C compiler: gk_string 116 bytes,
# gk_word 960, gk_analysis 1116)
# --------------------------------------------------------------------------

from ikelos.gkstring import GkString, GkWord, WordForm  # noqa: E402


class CWordForm(ctypes.Structure):
    _fields_ = [("voice", ctypes.c_uint, 3), ("mood", ctypes.c_uint, 4), ("tense", ctypes.c_uint, 4),
                ("person", ctypes.c_uint, 3), ("number", ctypes.c_uint, 3), ("case", ctypes.c_uint, 6),
                ("degree", ctypes.c_uint, 2), ("gender", ctypes.c_uint, 4)]


class CGkString(ctypes.Structure):
    _fields_ = [("form", CWordForm), ("stemtype", ctypes.c_uint), ("derivtype", ctypes.c_uint),
                ("dialect", ctypes.c_short), ("geogregion", ctypes.c_uint),
                ("morphflags", ctypes.c_ubyte * 12), ("domains", ctypes.c_char * 21),
                ("gkstring", ctypes.c_char * 60)]


class CGkWord(ctypes.Structure):
    _fields_ = [("form", CWordForm), ("stemtype", ctypes.c_uint), ("derivtype", ctypes.c_uint),
                ("dialect", ctypes.c_short), ("geogregion", ctypes.c_uint),
                ("morphflags", ctypes.c_ubyte * 12), ("domains", ctypes.c_char * 21),
                ("prntflags", ctypes.c_int), ("totanal", ctypes.c_int), ("lemma", ctypes.c_char * 60),
                ("preverb", CGkString), ("aug1", CGkString), ("stem", CGkString),
                ("suffix", CGkString), ("endstring", CGkString),
                ("rawprvb", ctypes.c_char * 60), ("rawword", ctypes.c_char * 60),
                ("workword", ctypes.c_char * 60), ("crasis", ctypes.c_char * 60),
                ("oddkeys", ctypes.c_char_p), ("analysis", ctypes.c_void_p)]


assert ctypes.sizeof(CGkString) == 116 and ctypes.sizeof(CGkWord) == 960

_FORM = WordForm.__slots__


def form_to_c(f: WordForm, c: CWordForm) -> None:
    for k in _FORM:
        setattr(c, k, getattr(f, k))


def form_from_c(c: CWordForm) -> WordForm:
    return WordForm(*(getattr(c, k) for k in _FORM))


def mf_to_c(mf: int, arr) -> None:
    for i in range(12):
        arr[i] = (mf >> (8 * i)) & 0xFF


def mf_from_c(arr) -> int:
    return int.from_bytes(bytes(arr), "little")


def _enc(s: str) -> bytes:
    return s.encode("latin-1")


def _dec(b: bytes) -> str:
    return b.decode("latin-1")


def gs_to_c(g: GkString, c: CGkString | None = None) -> CGkString:
    c = c or CGkString()
    form_to_c(g.form, c.form)
    c.stemtype, c.derivtype, c.dialect, c.geogregion = g.stemtype, g.derivtype, g.dialect, g.geogregion
    mf_to_c(g.morphflags, c.morphflags)
    c.domains = _enc(g.domains)
    c.gkstring = _enc(g.gkstring)
    return c


def gs_from_c(c: CGkString) -> GkString:
    return GkString(_dec(c.gkstring), form_from_c(c.form), c.stemtype, c.derivtype, c.dialect,
                    c.geogregion, mf_from_c(c.morphflags), _dec(c.domains))


_WSTR = ("lemma", "rawprvb", "rawword", "workword", "crasis")
_WGS = ("preverb", "aug1", "stem", "suffix", "endstring")


def gw_to_c(w: GkWord, c: CGkWord | None = None) -> CGkWord:
    c = c or CGkWord()
    form_to_c(w.form, c.form)
    c.stemtype, c.derivtype, c.dialect, c.geogregion = w.stemtype, w.derivtype, w.dialect, w.geogregion
    mf_to_c(w.morphflags, c.morphflags)
    c.domains = _enc(w.domains)
    c.prntflags, c.totanal = w.prntflags, w.totanal
    for k in _WSTR:
        setattr(c, k, _enc(getattr(w, k)))
    for k in _WGS:
        gs_to_c(getattr(w, k), getattr(c, k))
    return c


def gw_from_c(c: CGkWord) -> GkWord:
    w = GkWord()
    w.form = form_from_c(c.form)
    w.stemtype, w.derivtype, w.dialect, w.geogregion = c.stemtype, c.derivtype, c.dialect, c.geogregion
    w.morphflags = mf_from_c(c.morphflags)
    w.domains = _dec(c.domains)
    w.prntflags, w.totanal = c.prntflags, c.totanal
    for k in _WSTR:
        setattr(w, k, _dec(getattr(c, k)))
    for k in _WGS:
        setattr(w, k, gs_from_c(getattr(c, k)))
    w.oddkeys = _dec(c.oddkeys) if c.oddkeys else None
    return w


def gs_tuple(g: GkString):
    return (g.gkstring, g.form.astuple(), g.stemtype, g.derivtype, g.dialect, g.geogregion,
            g.morphflags, g.domains)


def gw_tuple(w: GkWord):
    return ((w.form.astuple(), w.stemtype, w.derivtype, w.dialect, w.geogregion, w.morphflags,
             w.domains, w.prntflags, w.totanal) + tuple(getattr(w, k) for k in _WSTR)
            + tuple(gs_tuple(getattr(w, k)) for k in _WGS) + (w.oddkeys or None,))
