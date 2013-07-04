# This was totally copied right from the documentation
# gsettings_SCHEMAS is a list of all the schemas you want to install
gsettings_SCHEMAS = pynorama.gschema.xml

# include the appropriate makefile rules for schema handling
@GSETTINGS_RULES@

icondir = /usr/share/icons/hicolor/scalable/apps
icon_DATA = pynorama.svg
desktopdir = $(datadir)/applications
desktop_DATA = pynorama.desktop
navigatorsdir = $(pkgdatadir)
navigators_DATA = navigators.xml
EXTRA_DIST = $(icon_DATA) $(desktop_DATA) $(navigators_DATA)

install-data-hook:
	chmod +x $(desktopdir)/$(desktop_DATA)
