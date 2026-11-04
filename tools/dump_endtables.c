/*
 * Dev-only: dump Morpheus binary endtables (*.out) as TSV using the C reader,
 * so the Python port can ship an exact, platform-independent JSON copy.
 *
 * Build: see tools/export_data.py
 * Usage: MORPHLIB=../stemlib dump_endtables endtables/out/a_hs.out ...
 */
#include <stdio.h>
#include <stdlib.h>
#include <gkstring.h>

FILE * MorphFopen();

int main(int argc, char **argv)
{
	int a, i, j, maxend, lno;
	gk_string g;

	for (a = 1; a < argc; a++) {
		FILE *f = MorphFopen(argv[a], "rb");
		if (!f) { fprintf(stderr, "cannot open %s\n", argv[a]); return 1; }
		lno = get_endheader(f, &maxend);
		if (lno < 0) { fprintf(stderr, "bad header %s\n", argv[a]); return 1; }
		printf("#file\t%s\t%d\t%d\n", argv[a], lno, maxend);
		for (i = 0; i < lno; i++) {
			memset(&g, 0, sizeof g);
			if (ReadEnding(f, &g, maxend) <= 0) {
				fprintf(stderr, "short read %s at %d\n", argv[a], i);
				return 1;
			}
			printf("%s\t%u\t%u\t%u\t%u\t%u\t%u\t%u\t%u\t%d\t%u\t%u\t%u\t",
				gkstring_of(&g),
				voice_of(forminfo_of(&g)), mood_of(forminfo_of(&g)),
				tense_of(forminfo_of(&g)), person_of(forminfo_of(&g)),
				number_of(forminfo_of(&g)), case_of(forminfo_of(&g)),
				degree_of(forminfo_of(&g)), gender_of(forminfo_of(&g)),
				(int) (unsigned short) dialect_of(&g), (unsigned) geogregion_of(&g),
				(unsigned) stemtype_of(&g), (unsigned) derivtype_of(&g));
			for (j = 0; j < MORPHFLAG_BYTES; j++)
				printf("%02x", (unsigned char) morphflags_of(&g)[j]);
			putchar('\t');
			for (j = 0; j < MAXDOMAINS + 1; j++)
				printf("%02x", (unsigned char) domains_of(&g)[j]);
			putchar('\n');
		}
		fclose(f);
	}
	return 0;
}
