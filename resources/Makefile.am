icondir = /usr/share/icons/hicolor/scalable/apps
icon_DATA = pynorama.svg
desktopdir = $(datadir)/applications
desktop_DATA = pynorama.desktop
preferencesdir = $(pkgdatadir)
preferences_DATA = preferences.json
EXTRA_DIST = $(icon_DATA) $(desktop_DATA) $(preferences_DATA)

install-data-hook:
	chmod +x $(desktopdir)/$(desktop_DATA)
