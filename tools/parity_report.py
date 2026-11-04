"""Compare the Python analyzer with the golden C output; print the pass rate and failures.

    python tools/parity_report.py [default|n] [--limit N] [--out FILE]
"""
import argparse
import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from pymorpheus.cli import analyses_strings  # noqa: E402

FLAGS = {"default": ["-S"], "n": ["-S", "-n"]}

ap = argparse.ArgumentParser()
ap.add_argument("name", nargs="?", default="default")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--out", type=Path)
args = ap.parse_args()

rows = [json.loads(l) for l in gzip.open(HERE.parent / "tests" / "golden" / f"{args.name}.jsonl.gz", "rt")]
if args.limit:
    rows = rows[: args.limit]
t0 = time.time()
fails = []
for i, r in enumerate(rows):
    try:
        got = analyses_strings(r["input"], FLAGS[args.name])
    except Exception as e:  # noqa: BLE001
        got = [f"EXCEPTION {type(e).__name__}: {e}"]
    if Counter(got) != Counter(r["analyses"]):
        fails.append({"input": r["input"], "expected": r["analyses"], "got": got})
dt = time.time() - t0
print(f"{args.name}: {len(rows) - len(fails)}/{len(rows)} = {1 - len(fails)/len(rows):.5f}  "
      f"({len(rows)/dt:.0f} words/s)")
if args.out:
    with args.out.open("w") as fh:
        for f in fails:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
