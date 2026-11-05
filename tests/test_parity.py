"""Parity with the C ``cruncher`` (golden corpus from tools/make_golden.py).

Analyses are compared as multisets: the C output order is platform dependent.
By default every 20th golden word is checked; set MORPHEUS_FULL_GOLDEN=1 for
the whole corpus (about 10 minutes per flag set).
"""

import gzip
import json
import os
from collections import Counter
from pathlib import Path

import pytest

GOLDEN = Path(__file__).parent / "golden"
FIXTURE = Path(__file__).parent / "fixtures" / "cruncher_fixture.json"




def _golden(name):
    with gzip.open(GOLDEN / f"{name}.jsonl.gz", "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def _fixture_greek():
    data = json.loads(FIXTURE.read_text())
    return [ex for ex in data if "-L" not in ex.get("opts", [])]


@pytest.mark.parametrize("example", _fixture_greek(), ids=lambda e: f"{e['input']}{e.get('opts', [])}")
def test_fixture(example):
    from ikelos.cli import crunch

    assert crunch(example["input"], example.get("opts", [])) == example["expected"]


FULL = os.environ.get("MORPHEUS_FULL_GOLDEN") == "1"


@pytest.mark.parametrize("name,flags", [("default", ["-S"]), ("n", ["-S", "-n"])])
def test_golden(name, flags):
    from ikelos.cli import analyses_strings

    rows = _golden(name)
    if not FULL:
        rows = rows[::20]
    failures = [
        r["input"] for r in rows
        if Counter(analyses_strings(r["input"], flags)) != Counter(r["analyses"])
    ]
    rate = 1 - len(failures) / len(rows)
    assert rate >= 0.995, f"parity {rate:.4f}; first failures: {failures[:20]}"
