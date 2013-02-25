#!/usr/bin/python

'''
	Pynorama is going to be an image viewer.
'''

import pygtk
pygtk.require("2.0")
import gtk, os
from gettext import gettext as _
import loading


class Pynorama:
	def __init__(self):
		# Create Window
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.set_title(_("Pynorama"))
		
		# Create image and a scrolled window for it
		self.image = gtk.Image()
		self.imageview = gtk.ScrolledWindow()
		self.imageview.set_size_request(256, 256)
		
		self.imageview.add_with_viewport(self.image)
		
		# Add a status bar
		self.statusbar = gtk.Statusbar()
		
		# With a label for the image size
		self.sizelabel = gtk.Label()
		self.sizelabel.set_alignment(1.0, 0.5)
		self.statusbar.pack_end(self.sizelabel, False, False)
		
		# Setup actions			
		openaction = gtk.Action("open", _("Open..."), _("Open an image"), gtk.STOCK_OPEN)
		openaction.connect("activate", self.file_open)
		
		quitaction = gtk.Action("quit", _("Quit"), _("Exit the program"), gtk.STOCK_QUIT)
		quitaction.connect("activate", self.quit)
		
		# Add a menu bar
		self.menubar = gtk.MenuBar()
		
		self.filemenu = gtk.Menu()
		self.menubar.file = gtk.MenuItem(_("File"))
		self.menubar.file.set_submenu(self.filemenu)
		
		openmi = openaction.create_menu_item()
		quitmi = quitaction.create_menu_item()
		
		self.filemenu.append(openmi)
		self.filemenu.append(gtk.SeparatorMenuItem())
		self.filemenu.append(quitmi)
		
		self.menubar.append(self.menubar.file)
				
		# Put everything in a nice layout
		vlayout = gtk.VBox()
		
		vlayout.pack_start(self.menubar, False, False)		
		vlayout.pack_start(self.imageview)
		vlayout.pack_end(self.statusbar, False, False)
		
		self.window.add(vlayout)
		
		# Connect events
		self.window.connect("destroy", self._window_destroyed)
		
		# Make everything visible
		self.window.show_all()
	
	# Logs a message into both console and status bar
	def log(self, message):
		self.statusbar.push(0, message)
		print message
			
	# Attempt to load a file, returns false when it fails
	def load(self, filename):
		if not os.path.exists(filename):
			self.log(_("\"%\" does not exist.") % filename)
			return False
			
		try:
			os.path.dirname(filename)
			self.image.set_from_file(filename)
			self.pixbuf = self.image.get_pixbuf()
			
			w, h = self.pixbuf.get_width(), self.pixbuf.get_height()
			
			self.image.set_size_request(w, h)
			
			self.sizelabel.set_text(_("%dx%d")  % (w, h))
			self.window.set_title(_("\"%s\" - Pynorama") % os.path.basename(filename))
			
			self.log(_("Loaded file \"%s\"")  % filename)
		except:
			self.log(_("Could not load file \"%s\"")  % filename)
			raise # Raise here for debugging purposes
		
		return True
	
	def run(self):
		gtk.main()
	
	# Events
	def file_open(self, widget, data=None):
		# Create image choosing dialog
		image_chooser = gtk.FileChooserDialog(title = _("Open Image..."), action = gtk.FILE_CHOOSER_ACTION_OPEN,
			buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
			
		image_chooser.set_default_response(gtk.RESPONSE_OK)
		
		# Add filters of supported formats from "loading" module
		for fileFilter in loading.Filters:
			image_chooser.add_filter(fileFilter)
		
		try:
			if image_chooser.run() == gtk.RESPONSE_OK:
				filename = image_chooser.get_filename()
				
				self.load(filename)
				
		except:
			# Nothing to handle here
			raise
			
		else:
			# Destroy the dialog anyway
			image_chooser.destroy()
	
	def quit(self, widget=None, data=None):
		gtk.main_quit()
	
	def _window_destroyed(self, widget, data=None):
		self.quit()
		
# When loaded directly, runs the app using ARGV arguments
if __name__ == "__main__":
	# Setup argument parser
	import argparse
	
	parser = argparse.ArgumentParser()
	parser.add_argument("-o", "--open", type=str)
	
	# Get arguments
	args = parser.parse_args()	
	
	app = Pynorama()
	
	# --open is used to load files
	if args.open:
		app.load(args.open)
	
	# Run app
	app.run()
