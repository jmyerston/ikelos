#!/usr/bin/env python3
"""Export the Greek stemlib into the pymorpheus package data directory.

Binary endtables (``endtables/out/*.out``, ``derivs/out/*.out``) are decoded
with the real C reader (``tools/dump_endtables.c``, linked against the built
Morpheus libraries) and stored as gzipped JSON, preserving record order, which
the analyzer depends on. Text indices and rule tables are gzipped verbatim.

Prerequisite: build the C libraries (``cd src && make``).

Usage:  python tools/export_data.py
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# C Morpheus checkout (default: sibling directory ../morpheus)
REPO = Path(os.environ.get("MORPHEUS_HOME", Path(__file__).resolve().parents[2] / "morpheus"))
SRC = REPO / "src"
GREEK = REPO / "stemlib" / "Greek"
OUT = ROOT / "pymorpheus" / "data" / "greek"

LIBS = [
    "gener/genwd.o", "anal/anal.a", "gener/gener.a", "gkends/gkends.a",
    "gkdict/gkdict.a", "morphlib/morphlib.a", "greeklib/greeklib.a",
]

# Text files read at runtime (see src/includes/{libfiles,endfiles,gkdict}.h).
TEXT_FILES = [
    "rule_files/vowcontr.table",
    "rule_files/conseuph.table",
    "rule_files/stemtypes.table",
    "rule_files/derivtypes.table",
    "rule_files/domainlist.table",
    "rule_files/ppasslist.table",
    "rule_files/raw_preverbs.table",
    "endtables/indices/vbendind",
    "endtables/indices/nendind",
    "derivs/indices/derivind",
    "stemsrc/vbs.cmp.ml",
    "stemsrc/lemlist",
    "steminds/nomind",
    "steminds/vbind",
    # sparse binary pre-index for nomind (8-byte key + int32 offset), kept verbatim.
    # vbind is searched in memory by gkends/endindex.c:checkendind instead.
    "steminds/nomind.lindex",
]

FIELDS = [
    "ending", "voice", "mood", "tense", "person", "number", "case", "degree",
    "gender", "dialect", "geogregion", "stemtype", "derivtype",
]


def build_dumper(tmp: Path) -> Path:
    exe = tmp / "dump_endtables"
    subprocess.run(
        ["cc", "-std=gnu89", "-fcommon", "-w", f"-I{SRC / 'includes'}", "-o", str(exe),
         str(ROOT / "tools" / "dump_endtables.c"), *[str(SRC / lib) for lib in LIBS]],
        check=True,
    )
    return exe


def dump_tables(exe: Path, subdir: str) -> dict[str, list[list]]:
    files = sorted((GREEK / subdir / "out").glob("*.out"))
    rel = [str(f.relative_to(GREEK)) for f in files]
    proc = subprocess.run(
        [str(exe), *rel], cwd=GREEK, env=dict(os.environ, MORPHLIB=str(REPO / "stemlib")),
        capture_output=True, text=True, check=True,
    )
    tables: dict[str, list[list]] = {}
    current: list[list] | None = None
    expected = 0
    for line in proc.stdout.splitlines():
        if line.startswith("#file\t"):
            _, path, count, _maxend = line.split("\t")
            current = tables.setdefault(Path(path).stem, [])
            expected = int(count)
            continue
        cols = line.split("\t")
        assert current is not None and len(cols) == len(FIELDS) + 2, line
        record = [cols[0], *map(int, cols[1:len(FIELDS)]), cols[-2], cols[-1]]
        current.append(record)
        if len(current) == expected:
            current = None
    return tables


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        exe = build_dumper(Path(tmp))
        for subdir in ("endtables", "derivs"):
            tables = dump_tables(exe, subdir)
            payload = {"fields": FIELDS + ["morphflags", "domains"], "tables": tables}
            with gzip.open(OUT / f"{subdir}.json.gz", "wt", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
            print(f"{subdir}: {len(tables)} tables, {sum(map(len, tables.values()))} records")
    for rel in TEXT_FILES:
        dest = OUT / (rel + ".gz")
        dest.parent.mkdir(parents=True, exist_ok=True)
        # mtime=0 keeps the output byte-identical across runs
        with (GREEK / rel).open("rb") as src, open(dest, "wb") as raw, \
                gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as fh:
            shutil.copyfileobj(src, fh)
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"wrote {OUT} ({total / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
