SUBDIRS = pynorama

imageviewer_PYTHON = imageviewer.py
imageviewerdir = $(pkglibdir)
CLEANFILES = $(imageviewer_PYTHON)
do_substitution = sed \
	-e 's,[@]pkgdatadir[@],$(pkgdatadir),g'

EXTRA_DIST = imageviewer.py.in

imageviewer.py: imageviewer.py.in Makefile
	$(do_substitution) < $(srcdir)/imageviewer.py.in > imageviewer.py
