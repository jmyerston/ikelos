#!/usr/bin/env python3
"""Generate a golden corpus by running the C ``cruncher`` over treebank word forms.

Usage:
    python tools/make_golden.py CONLLU [CONLLU ...] [--out tests/golden] [--limit N]

Writes one gzipped JSONL file per flag set (``default.jsonl.gz``, ``n.jsonl.gz``), each line
``{"input": beta, "analyses": [...]}`` where ``analyses`` is the list of
``<NL>...</NL>`` entries (empty list = cruncher found no analysis).

Analyses are compared as multisets by the tests, because the C output order
varies across platforms (see the two macOS failures in test/fixture.json).
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# C Morpheus checkout with a built bin/cruncher (default: sibling directory ../morpheus)
REPO = Path(os.environ.get("MORPHEUS_HOME", Path(__file__).resolve().parents[2] / "morpheus"))
sys.path.insert(0, str(ROOT))

from ikelos.betacode import unicode_to_beta  # noqa: E402

FLAG_SETS = {"default": ["-S"], "n": ["-S", "-n"]}
NL_RE = re.compile(r"<NL>(.*?)</NL>")
BETA_WORD_RE = re.compile(r"^[*a-z()/\\=+|']+$")


def read_forms(paths: list[Path]) -> list[str]:
    forms: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip() or line.startswith("#"):
                    continue
                cols = line.rstrip("\n").split("\t")
                if len(cols) < 4 or "-" in cols[0] or "." in cols[0] or cols[3] == "PUNCT":
                    continue
                beta = unicode_to_beta(unicodedata.normalize("NFC", cols[1]))
                if BETA_WORD_RE.match(beta):
                    forms.add(beta)
    return sorted(forms)


def run_cruncher(words: list[str], flags: list[str]) -> dict[str, list[str]]:
    env = dict(os.environ, MORPHLIB=str(REPO / "stemlib"))
    proc = subprocess.run(
        [str(REPO / "bin" / "cruncher"), *flags],
        input="\n".join(words) + "\n",
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    results: dict[str, list[str]] = {w: [] for w in words}
    # With -n, a word that only parses after the breathing retry is printed
    # under the retried form (e.g. "w" -> "w)"), so also match ignoring breathings.
    by_bare: dict[str, list[str]] = {}
    for w in words:
        by_bare.setdefault(w.replace("(", "").replace(")", ""), []).append(w)
    lines = proc.stdout.split("\n")
    i = 0
    while i < len(lines) - 1:
        word, anal = lines[i], lines[i + 1]
        if anal.startswith("<NL>"):
            if word in results:
                results[word] = NL_RE.findall(anal)
            else:
                for cand in by_bare.get(word.replace("(", "").replace(")", ""), []):
                    if not results[cand]:
                        results[cand] = NL_RE.findall(anal)
                        break
            i += 2
        else:
            i += 1
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("conllu", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "tests" / "golden")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=2000)
    args = ap.parse_args()

    words = read_forms(args.conllu)
    if args.limit:
        words = words[: args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    for name, flags in FLAG_SETS.items():
        out_path = args.out / f"{name}.jsonl.gz"
        hits = 0
        with gzip.open(out_path, "wt", encoding="utf-8") as fh:
            for start in range(0, len(words), args.chunk):
                chunk = words[start : start + args.chunk]
                for word, analyses in run_cruncher(chunk, flags).items():
                    hits += bool(analyses)
                    fh.write(json.dumps({"input": word, "analyses": analyses}, ensure_ascii=False) + "\n")
        print(f"{out_path}: {len(words)} words, {hits} analyzed", file=sys.stderr)


if __name__ == "__main__":
    main()
