#!/usr/bin/python

'''
	Pynorama is going to be an image viewer.
'''

import pygtk
pygtk.require("2.0")
import gtk, os, urllib
from gettext import gettext as _
import navigation, loading, organization

# Copy pasted utility, thanks Nikos :D
def get_file_path_from_dnd_dropped_uri(uri):
		# get the path to file
		path = ""
		if uri.startswith('file:\\\\\\'): # windows
			path = uri[8:] # 8 is len('file:///')
		elif uri.startswith('file://'): # nautilus, rox
			path = uri[7:] # 7 is len('file://')
		elif uri.startswith('file:'): # xffm
			path = uri[5:] # 5 is len('file:')

		path = urllib.url2pathname(path) # escape special chars
		path = path.strip('\r\n\x00') # remove \r\n and NULL

		return path

class Pynorama(object):
	def __init__(self):
		self.organizer = organization.Organizer()
		self.current_image = None
		
		# Create Window
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.set_default_size(600, 600)
		self.window.set_title(_("Pynorama"))
		
		# Create image and a scrolled window for it
		self.image = gtk.Image()
		
		self.imageview = gtk.ScrolledWindow()
		self.imageview.add_with_viewport(self.image)
		self.imageview.pixbuf =  None
		
		# Add a status bar
		self.statusbar = gtk.Statusbar()
		
		# With a label for the image size
		self.size_label = gtk.Label()
		self.size_label.set_alignment(1.0, 0.5)
		self.statusbar.pack_end(self.size_label, False, False)
		
		# Setup actions
		self.actions = gtk.ActionGroup("pynorama")
		
		openaction = gtk.Action("open", _("Open..."), _("Open an image"), gtk.STOCK_OPEN)
		openaction.connect("activate", self.file_open)
		
		quitaction = gtk.Action("quit", _("Quit"), _("Exit the program"), gtk.STOCK_QUIT)
		quitaction.connect("activate", self.quit)
			
		prevaction = gtk.Action("previous", _("Previous"), _("Open the previous image"), gtk.STOCK_GO_BACK)
		prevaction.connect("activate", self.goprevious)
		
		nextaction = gtk.Action("next", _("Next"), _("Open the next image"), gtk.STOCK_GO_FORWARD)
		nextaction.connect("activate", self.gonext)
				
		noscrollbars = gtk.RadioAction("no-scrollbars", _("No Scroll Bars"), _("Hide scroll bars"), -1, -1)
		brscrollbars = gtk.RadioAction("br-scrollbars", _("At Bottom Right"), _("Show scroll bars at the bottom right corner"), -1, gtk.CORNER_TOP_LEFT)
		trscrollbars = gtk.RadioAction("tr-scrollbars", _("At Top Right"), _("Show scroll bars at the top right corner"), -1, gtk.CORNER_BOTTOM_LEFT)
		tlscrollbars = gtk.RadioAction("tl-scrollbars", _("At Top Left"), _("Show scroll bars at the top left corner"), -1, gtk.CORNER_BOTTOM_RIGHT)
		blscrollbars = gtk.RadioAction("bl-scrollbars", _("At Bottom Left"), _("Show scroll bars at the bottom left corner"), -1, gtk.CORNER_TOP_RIGHT)
		
		brscrollbars.set_group(noscrollbars)
		trscrollbars.set_group(noscrollbars)
		tlscrollbars.set_group(noscrollbars)
		blscrollbars.set_group(noscrollbars)
		
		noscrollbars.set_current_value(gtk.CORNER_TOP_LEFT)
		
		noscrollbars.connect("toggled", self.set_scrollbars)
		brscrollbars.connect("toggled", self.set_scrollbars)
		blscrollbars.connect("toggled", self.set_scrollbars)
		tlscrollbars.connect("toggled", self.set_scrollbars)
		trscrollbars.connect("toggled", self.set_scrollbars)
		
		fullscreenaction = gtk.ToggleAction("fullscreen", _("Fullscreen"), _("Fill the entire screen"), gtk.STOCK_FULLSCREEN)
		fullscreenaction.connect("toggled", self.toggle_fullscreen)
		
		self.actions.add_action(openaction)
		self.actions.add_action(quitaction)
		self.actions.add_action(prevaction)
		self.actions.add_action(nextaction)
		self.actions.add_action(fullscreenaction)
		
		self.actions.add_action(noscrollbars)
		self.actions.add_action(brscrollbars)
		self.actions.add_action(blscrollbars)
		self.actions.add_action(tlscrollbars)
		self.actions.add_action(trscrollbars)
		
		# Add a menu bar
		self.menubar = gtk.MenuBar()
		
		self.filemenu = gtk.Menu()
		self.menubar.file = gtk.MenuItem(_("File"))
		self.menubar.file.set_submenu(self.filemenu)
		
		self.filemenu.append(openaction.create_menu_item())
		self.filemenu.append(gtk.SeparatorMenuItem())
		self.filemenu.append(quitaction.create_menu_item())
		
		self.viewmenu = gtk.Menu()
		self.menubar.view = gtk.MenuItem(_("View"))
		self.menubar.view.set_submenu(self.viewmenu)
		
		scrollbars = self.viewmenu.scrollbars = gtk.Menu()
		
		scrollbarsmi = gtk.MenuItem(label=_("Scroll Bars"))
		scrollbarsmi.set_submenu(scrollbars)
		
		scrollbars.append(noscrollbars.create_menu_item())
		scrollbars.append(gtk.SeparatorMenuItem())
		scrollbars.append(brscrollbars.create_menu_item())
		scrollbars.append(trscrollbars.create_menu_item())
		scrollbars.append(tlscrollbars.create_menu_item())
		scrollbars.append(blscrollbars.create_menu_item())
		
		self.viewmenu.append(nextaction.create_menu_item())
		self.viewmenu.append(prevaction.create_menu_item())
		self.viewmenu.append(gtk.SeparatorMenuItem())
		self.viewmenu.append(scrollbarsmi)
		self.viewmenu.append(gtk.SeparatorMenuItem())
		self.viewmenu.append(fullscreenaction.create_menu_item())
		
		self.menubar.append(self.menubar.file)
		self.menubar.append(self.menubar.view)
		
		# Add a toolbar
		self.toolbar = gtk.Toolbar()
		
		self.toolbar.insert(openaction.create_tool_item(), -1)
		self.toolbar.insert(gtk.SeparatorToolItem(), -1)
		self.toolbar.insert(prevaction.create_tool_item(), -1)
		self.toolbar.insert(nextaction.create_tool_item(), -1)
		self.toolbar.insert(gtk.SeparatorToolItem(), -1)
		self.toolbar.insert(fullscreenaction.create_tool_item(), -1)
		
		# Put everything in a nice layout
		vlayout = gtk.VBox()
		
		vlayout.pack_start(self.menubar, False, False)
		vlayout.pack_start(self.toolbar, False, False)
		vlayout.pack_start(self.imageview)
		vlayout.pack_end(self.statusbar, False, False)
		
		self.window.add(vlayout)
		
		# Connect events
		self.window.connect("destroy", self._window_destroyed)			
		self.navigator = navigation.MapNavigator(self.imageview)
		
		# Complicated looking DnD setup
		self.imageview.connect("drag_data_received", self.dragged_data)
		
		self.imageview.drag_dest_set(
			gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
			[("text/uri-list", 0, 80)],
			gtk.gdk.ACTION_COPY)
		
		# Make everything visible
		self.window.show_all()
	
	# Logs a message into both console and status bar
	def log(self, message):
		self.statusbar.push(0, message)
		print message
		
	# sets a image
	def set_image(self, image):
		if self.current_image == image:
			return
		
		if self.current_image is not None:
			self.current_image.unload()
			
		self.current_image = image
		
		if self.current_image is None:
			self.window.set_title(_("Pynorama") % self.current_image.title)
			self.size_label.set_text("")
			self.imageview.pixbuf = None
			
		else:
			try:
				self.current_image.load()
			except:
				self.log(_("Could not load file \"%s\"")  % self.current_image.filename)
				raise # Raise here for debugging purposes
			
			self.image.set_from_pixbuf(self.current_image.pixbuf)
			self.imageview.pixbuf = self.current_image.pixbuf
		
			w, h = self.imageview.pixbuf.get_width(), self.imageview.pixbuf.get_height()		
		
			#self.image.set_size_request(w, h)
			self.size_label.set_text(_("%dx%d")  % (w, h))
			self.readjust_view()
					
			self.window.set_title(_("\"%s\" - Pynorama") % self.current_image.title)
			self.log(_("Loaded file \"%s\"")  % self.current_image.filename)
			
		return True
	
	# Attempt to load a file, returns false when it fails
	def open(self, filename):
		if not os.path.exists(filename):
			self.log(_("\"%\" does not exist.") % filename)
			return False
			
		directory = os.path.dirname(filename)
		dir_images = loading.get_files(directory)
		
		# if the filename that triggered open() is a file
		# Remove the same file from the list and add it to the start
		was_file = os.path.isfile(filename)
		
		if was_file:
			found_source_filename = False
			for i in range(len(dir_images)):
				if os.path.samefile(filename, dir_images[i]):
					del dir_images[i]
					dir_images.insert(0, filename)
					found_source_filename = True
					break
			
			# This is required since the source filename may not
			# be discovered through loading.get_files
			# e.g wrong extension / invalid file
			if not found_source_filename:
				dir_images.insert(0, filename)
		
		# Remove any previous images in the organizer
		del self.organizer.images[:]
		self.set_image(None)
		
		# This is where the images are loaded	
		for a_filename in dir_images:
			a_image = loading.ImageNode(a_filename)			
			self.organizer.append(a_image)
				
		# Sort images
		self.organizer.sort(organization.ImageSort.Filenames)
		
		trigger_image = None
		if was_file:
			trigger_image = self.organizer.find_image(filename)
		
		if len(self.organizer.images) > 0:
			if trigger_image is None:	
				trigger_image = self.organizer.images[0]
				
			return self.set_image(trigger_image)
		else:
			self.log(_("No files were loaded"))
			return False
	
	# Adjusts the image to be on the top-center (so far)
	def readjust_view(self):
		w, h = self.imageview.pixbuf.get_width(), self.imageview.pixbuf.get_height()
		vrect = self.imageview.get_allocation()
		
		hadjust, vadjust = self.imageview.get_hadjustment(), self.imageview.get_vadjustment()
		
		hadjust.set_value(w // 2 - vrect.width // 2)
		vadjust.set_value(0)
	
	def run(self):
		gtk.main()
	
	# Events
	def set_scrollbars(self, data=None):
		placement = self.actions.get_action("no-scrollbars").get_current_value()
		
		if placement == -1:
			self.imageview.get_hscrollbar().set_child_visible(False)
			self.imageview.get_vscrollbar().set_child_visible(False)
		else:
			self.imageview.get_hscrollbar().set_child_visible(True)
			self.imageview.get_vscrollbar().set_child_visible(True)
			
			self.imageview.set_placement(placement)
			
	def toggle_fullscreen(self, data=None):
		fullscreenaction = self.actions.get_action("fullscreen")
		
		if fullscreenaction.props.active:
			self.window.fullscreen()
		else:
			self.window.unfullscreen()
	
	def gonext(self, data=None):
		if self.current_image and self.current_image.next:
			self.set_image(self.current_image.next)
		
	def goprevious(self, data=None):
		if self.current_image and self.current_image.previous:
			self.set_image(self.current_image.previous)
			
	def dragged_data(self, widget, context, x, y, selection, target_type, timestamp):
		uri = selection.data.strip('\r\n\x00')
		uri_splitted = uri.split() # we may have more than one file dropped
		
		dropped_paths = []
		for uri in uri_splitted:
			path = get_file_path_from_dnd_dropped_uri(uri)
			dropped_paths.append(path)
		
		# Open only last dropped file
		if dropped_paths:
			self.open(dropped_paths[-1])
							
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
				
				self.open(filename)
				
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
		app.open(args.open)
	
	# Run app
	app.run()
