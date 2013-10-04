SUBDIRS = code resources

bin_SCRIPTS = pynorama
CLEANFILES = $(bin_SCRIPTS)
do_substitution = sed \
	-e 's,[@]pynoramadir[@],$(pkglibdir),g'

EXTRA_DIST = pynorama.in

pynorama: pynorama.in Makefile
	$(do_substitution) < $(srcdir)/pynorama.in > pynorama
	chmod +x pynorama
