#!/bin/sh
# Build libmorph.dylib/.so from the compiled C libraries (dev-only oracle for
# tests/test_c_parity_*.py). Exports exactly the symbol set linked into cruncher.
# Usage: tools/build_clib.sh [outdir]   (run after building src/ with make)
set -e
HERE=$(cd "$(dirname "$0")/.." && pwd)
MORPHEUS_HOME=${MORPHEUS_HOME:-$HERE/../morpheus}  # C checkout, built with make
SRC=$MORPHEUS_HOME/src
OUT=${1:-$HERE/build/clib}
mkdir -p "$OUT"
case $(uname) in Darwin) EXT=dylib; SHARED=-dynamiclib; U=_ ;; *) EXT=so; SHARED=-shared; U= ;; esac
LIBS="$SRC/anal/anal.a $SRC/gener/genwd.o $SRC/gkends/gkends.a $SRC/gkdict/gkdict.a $SRC/morphlib/morphlib.a $SRC/greeklib/greeklib.a"
# symbols cruncher pulls from the libraries
nm -U "$MORPHEUS_HOME/bin/cruncher" 2>/dev/null | awk '$2=="T"{print $3}' | sed "s/^$U//" | sort -u > "$OUT/syms"
nm -A $LIBS 2>/dev/null | awk '$(NF-1)=="T"{print $NF}' | sed "s/^$U//" | sort -u > "$OUT/defs"
UFLAGS=$(comm -12 "$OUT/syms" "$OUT/defs" | grep -v '^main$' | sed "s/^/-Wl,-u,$U/")
echo 'int quickflag = 0;' > "$OUT/stub.c"
cc $SHARED -fPIC -o "$OUT/libmorph.$EXT" "$OUT/stub.c" $UFLAGS $LIBS -ll
echo "$OUT/libmorph.$EXT"
