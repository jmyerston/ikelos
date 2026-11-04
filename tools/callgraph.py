"""Approximate the C call graph reachable from cruncher's main().

Regex based: finds top-level function definitions and identifiers followed by
'(' inside their bodies. Function pointers passed by name are caught because
any identifier that names a known function counts as a reference.

    python tools/callgraph.py [root ...]     # prints reachable functions per file
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import os

# C Morpheus checkout (default: sibling directory ../morpheus)
SRC = Path(os.environ.get("MORPHEUS_HOME", Path(__file__).resolve().parents[2] / "morpheus")) / "src"
DIRS = ["anal", "gener", "gkends", "gkdict", "morphlib", "greeklib"]
SKIP_FILES = {"Copy of beta2smarta.c"}

IDENT = re.compile(r"[A-Za-z_]\w*")
KEYWORDS = {"if", "while", "for", "switch", "return", "sizeof", "else", "do", "case"}


def strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(\\.|[^'\\])'", "' '", text)
    # drop preprocessor lines
    return re.sub(r"^\s*#[^\n]*", "", text, flags=re.M)


def functions(path: Path):
    """Yield (name, body) for each top-level function definition."""
    text = strip(path.read_text(encoding="latin-1"))
    depth = 0
    i = 0
    n = len(text)
    last_top = 0
    while i < n:
        c = text[i]
        if c == "{":
            if depth == 0:
                header = text[last_top:i]
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                body = text[start:i + 1]
                m = re.search(r"([A-Za-z_]\w*)\s*\(([^()]*)\)\s*((?:[^;{}()]*;\s*)*)$", header, re.S)
                if m and m.group(1) not in KEYWORDS and "=" not in header[: m.start()].split("\n")[-1] and ";" not in header[: m.start()].split("\n")[-1]:
                    yield m.group(1), body
                last_top = i + 1
        i += 1


def main(roots: list[str]) -> None:
    defs: dict[str, tuple[str, str]] = {}
    # link order of cruncher: stdiomorph.o genwd.o anal.a gener.a gkends.a gkdict.a morphlib.a greeklib.a
    sources = [SRC / "anal/stdiomorph.c", SRC / "gener/genwd.c"]
    for lib in ["anal/anal.a", "gkends/gkends.a", "gkdict/gkdict.a", "morphlib/morphlib.a", "greeklib/greeklib.a"]:
        objs = subprocess.run(["ar", "t", str(SRC / lib)], capture_output=True, text=True).stdout.split()
        d = SRC / lib.split("/")[0]
        sources += [d / o.replace(".o", ".c") for o in objs if o.endswith(".o")]
    for path in sources:
        for name, body in functions(path):
            if name not in defs:
                defs[name] = (str(path.relative_to(SRC)), body)

    seen = set()
    stack = list(roots or ["main"])
    while stack:
        f = stack.pop()
        if f in seen or f not in defs:
            continue
        seen.add(f)
        _, body = defs[f]
        for ident in set(IDENT.findall(body)):
            if ident in defs and ident not in seen and ident not in KEYWORDS:
                stack.append(ident)
    by_file = defaultdict(list)
    for f in seen:
        by_file[defs[f][0]].append(f)
    total = 0
    for file in sorted(by_file):
        names = sorted(by_file[file])
        total += len(names)
        print(f"{file}: {' '.join(names)}")
    print(f"# {total} functions in {len(by_file)} files", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
