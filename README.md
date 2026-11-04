# pymorpheus

Pure-Python port of the Ancient Greek side of
[Morpheus](https://github.com/perseids-tools/morpheus), the Perseus morphological
analyzer. It installs as a `py3-none-any` wheel with the Greek stem library
bundled, so it needs no C compiler. It was built to run inside
[greCy](https://github.com/jmyerston/greCy) spaCy pipelines. Licensed MPL-2.0,
like Morpheus.

```bash
pip install git+https://github.com/jmyerston/pymorpheus
```

**Status: alpha.** The whole Greek runtime path of `cruncher` is ported
(about 317 C functions, found by `tools/callgraph.py`). It reproduces the C
output on the test fixtures and on the UD-derived golden corpus (see
`tests/test_parity.py`).

```python
>>> import pymorpheus
>>> pymorpheus.lemmatize("λόγους")
['λόγος', 'λογόω']
>>> a = pymorpheus.analyze("ἀνθρώπου")[0]
>>> a.lemma, a.pos, a.features
('ἄνθρωπος', 'noun', {'gender': 'masc', 'case': 'gen', 'number': 'sg'})
```

`pymorpheus [-S] [-n]` reads Beta Code words on stdin and prints the same
Perseus-format output as `cruncher`.

## Layout

| Path | What |
| - | - |
| `pymorpheus/betacode.py` | Morpheus Beta Code ↔ NFC Unicode (quantity marks, `ʼ` apostrophe) |
| `pymorpheus/stemlib.py` | Lazy loaders plus exact emulations of the C lookups (`binlook`, `ChckPreIndex`, `ChckFullIndex`, `checkendind`, `morphstrcmp`) |
| `pymorpheus/greeklib.py` | `src/greeklib` (accents, breathings, syllables, quantity) and the `greek.h` macros |
| `pymorpheus/gkstring.py` | `gk_string` / `gk_word` types, morph flags, dialect logic |
| `pymorpheus/morphkeys.py` | Key vocabulary and `ScanAsciiKeys` |
| `pymorpheus/morphlib.py` | Augment, preverbs, accentuation (`FixPersAcc`/`FixRecAcc`), euphony tables |
| `pymorpheus/gkends.py`, `gkdict.py` | Ending retrieval (`chckendings`, `WantGkEnd`) and stem/derivation lookups |
| `pymorpheus/analyzer.py` | `src/anal/check*.c` plus the generator `src/gener/genwd.c` |
| `pymorpheus/cli.py`, `api.py` | `cruncher` emulation (Perseus output) and the Python API |
| `pymorpheus/consts.py`, `keytables.py` | Generated from the C headers by `tools/gen_tables.py` |
| `pymorpheus/data/greek/` | Generated data (do not edit by hand) |
| `tools/export_data.py` | Regenerates `data/greek` from `$MORPHEUS_HOME/stemlib/Greek` |
| `tools/dump_endtables.c` | Dev-only decoder for the binary `*.out` endtables, built with the real C reader |
| `tools/make_golden.py` | Runs the C `cruncher` over UD treebank forms to produce `tests/golden/` |
| `tools/build_clib.sh` | Builds the C libraries as a shared library for the ctypes differential tests (`tests/test_c_*.py`, `tests/clib.py`) |
| `tools/parity_report.py` | Golden-corpus pass rate and a JSONL list of mismatches |
| `tools/callgraph.py` | Lists the C functions reachable from `cruncher`'s `main` |

## Development

Only the dev tools and the parity tests need the C original. Check it out next
to this repo, or point `MORPHEUS_HOME` at a checkout:

```bash
git clone https://github.com/perseids-tools/morpheus ../morpheus
(cd ../morpheus/src && CFLAGS='-std=gnu89 -fcommon -Wno-return-type -Wno-implicit-function-declaration -Wno-int-conversion -Wno-incompatible-pointer-types' make && make install)

python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
tools/build_clib.sh            # optional: enables the per-function C differential tests
.venv/bin/pytest -q            # MORPHEUS_FULL_GOLDEN=1 checks the whole golden corpus

# when the C stemlib changes
.venv/bin/python tools/export_data.py
.venv/bin/python tools/gen_tables.py
.venv/bin/python tools/make_golden.py path/to/UD_Ancient_Greek-*/*.conllu
```

The fixture and golden tests (`tests/fixtures/`, `tests/golden/`) are
self-contained. Tests that need the compiled C library are skipped when it is
missing.

## Notes for porters

* The binary endtables are decoded with the C reader and stored in **file
  order**. Their order is not plain ASCII order, and `RetrCompEnds` stops at
  the first `WantGkEnd < 0`, so the order has to be preserved.
* Noun stems are looked up through `nomind.lindex` (a sparse pre-index followed
  by a linear scan). Verb stems, ending indices, `lemlist` and `vbs.cmp.ml` use
  the in-memory binary search `checkendind`. Much of `gkdict/dictio.c` is dead
  code that sits after early `return`s.
* On macOS the C output order differs from Linux in some cases (2 of 94
  fixtures), so parity is checked on analysis multisets. The Python sort is
  stable, like glibc's `qsort`, so the CLI matches the Linux order.
* Functions are ported 1:1, C quirks included. A C function that writes into a
  `char *` returns the new string, and a pointer into a word becomes an index.
  Struct copies (`gk_word w = *g`) are `copy()`, and they share the analysis
  array the way the C structs share its pointer.
* The key `illw` appears twice in `derivtypes.table` with different values. C
  (macOS `qsort` plus `binlook`) resolves it to the first one, so duplicate keys
  resolve to the first entry in the table.
