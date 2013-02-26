#!/usr/bin/python
 # coding=utf-8
 
'''
	Pynorama is going to be an image viewer.
'''

import pygtk
pygtk.require("2.0")
import gtk, os, urllib, math, gobject
from gettext import gettext as _
import navigation, loading, organization
from ximage import xImage

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
		self.image = gobject.new(xImage)
		self.image.connect("updated_pixbuf", self.refresh_size)
		
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
		noscrollbars.connect("changed", self.change_scrollbars)
		
		fullscreenaction = gtk.ToggleAction("fullscreen", _("Fullscreen"), _("Fill the entire screen"), gtk.STOCK_FULLSCREEN)
		fullscreenaction.connect("toggled", self.toggle_fullscreen)
		
		# These actions are actual actions, not options.
		zoominaction = gtk.Action("in-zoom", _("Zoom In"), _("Makes the image look larger"), gtk.STOCK_ZOOM_IN)
		zoomoutaction = gtk.Action("out-zoom", _("Zoom Out"), _("Makes the image look smaller"), gtk.STOCK_ZOOM_OUT)
		nozoomaction = gtk.Action("no-zoom", _("No Zoom"), _("Makes the image look normal"), gtk.STOCK_ZOOM_100)
		
		nozoomaction.connect("activate", self.reset_zoom)
		zoominaction.connect("activate", self.change_zoom, 1)
		zoomoutaction.connect("activate", self.change_zoom, -1)
		
		rotatecwaction = gtk.Action("cw-rotate", _("Rotate Clockwise"), _("Turns the image top side to the right side"), -1)
		rotateccwaction = gtk.Action("ccw-rotate", _("Rotate Counter Clockwise"), _("Turns the image top side to the left side"), -1)
		
		rotatecwaction.connect("activate", self.rotate, 90)
		rotateccwaction.connect("activate", self.rotate, -90)
		
		fliphorizontalaction = gtk.Action("h-flip", _("Flip Horizontally"), _("Inverts the left and right sides of the image"), -1)
		flipverticalaction = gtk.Action("v-flip", _("Flip Vertically"), _("Inverts the top and bottom sides of the image"), -1)
		
		flipverticalaction.connect("activate", self.flip, False)
		fliphorizontalaction.connect("activate", self.flip, True)
		
		# Choices for pixel interpolation
		interpnearestaction = gtk.RadioAction("nearest-interp", _("Nearest Neighbour"), _(""), -1, gtk.gdk.INTERP_NEAREST)
		interptilesaction = gtk.RadioAction("tiles-interp", _("Parallelogram Tiles"), _(""), -1, gtk.gdk.INTERP_TILES)
		interpbilinearaction = gtk.RadioAction("bilinear-interp", _("Bilinear Function"), _(""), -1, gtk.gdk.INTERP_BILINEAR)
		interphyperaction = gtk.RadioAction("hyper-interp", _("Hyperbolic Function"), _(""), -1, gtk.gdk.INTERP_HYPER)
		
		interptilesaction.set_group(interpnearestaction)
		interpbilinearaction.set_group(interpnearestaction)
		interphyperaction.set_group(interpnearestaction)
		
		interpnearestaction.set_current_value(self.image.interpolation)
		interpnearestaction.connect("changed", self.change_interp)
		
		# Add to the action group
		# ALL the actions!
		self.actions.add_action(openaction)
		self.actions.add_action(quitaction)
		self.actions.add_action(prevaction)
		self.actions.add_action(nextaction)
		self.actions.add_action(fullscreenaction)
		
		self.actions.add_action(nozoomaction)
		self.actions.add_action(zoominaction)
		self.actions.add_action(zoomoutaction)
		
		self.actions.add_action(noscrollbars)
		self.actions.add_action(brscrollbars)
		self.actions.add_action(blscrollbars)
		self.actions.add_action(tlscrollbars)
		self.actions.add_action(trscrollbars)
		
		self.actions.add_action(rotatecwaction)
		self.actions.add_action(rotateccwaction)
		
		self.actions.add_action(interpnearestaction)
		self.actions.add_action(interptilesaction)
		self.actions.add_action(interpbilinearaction)
		self.actions.add_action(interphyperaction)
		
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
		
		# Transform submenu
		transform = self.viewmenu.scrollbars = gtk.Menu()
		
		transformmi = gtk.MenuItem(label=_("Transform"))
		transformmi.set_submenu(transform)
		
		transform.append(rotatecwaction.create_menu_item())
		transform.append(rotateccwaction.create_menu_item())
		transform.append(gtk.SeparatorMenuItem())
		transform.append(fliphorizontalaction.create_menu_item())
		transform.append(flipverticalaction.create_menu_item())
		
		# Interpolation submenu
		interpolations = self.viewmenu.scrollbars = gtk.Menu()
		
		interpolationsmi = gtk.MenuItem(label=_("Pixel Interpolation"))
		interpolationsmi.set_submenu(interpolations)
		
		interpolations.append(interpnearestaction.create_menu_item())
		interpolations.append(interptilesaction.create_menu_item())
		interpolations.append(interpbilinearaction.create_menu_item())
		interpolations.append(interphyperaction.create_menu_item())
		
		# Scroll bars submenu
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
		self.viewmenu.append(nozoomaction.create_menu_item())		
		self.viewmenu.append(zoominaction.create_menu_item())
		self.viewmenu.append(zoomoutaction.create_menu_item())
		self.viewmenu.append(transformmi)
		self.viewmenu.append(interpolationsmi)
		
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
		self.toolbar.insert(zoomoutaction.create_tool_item(), -1)
		self.toolbar.insert(zoominaction.create_tool_item(), -1)
		self.toolbar.insert(nozoomaction.create_tool_item(), -1)
		
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
			self.window.set_title(_("Pynorama"))
			self.size_label.set_text("")
			self.imageview.pixbuf = None
			
		else:
			try:
				self.current_image.load()
			except:
				self.log(_("Could not load file \"%s\"")  % self.current_image.filename)
				raise # Raise here for debugging purposes
			
			#self.reset_pixbuf()
			self.image.source = self.current_image.pixbuf
			self.imageview.pixbuf = self.current_image.pixbuf
			self.image.refresh_pixbuf()
			
			self.readjust_view()
					
			self.window.set_title(_("\"%s\" - Pynorama") % self.current_image.title)
			self.log(_("Loaded file \"%s\"")  % self.current_image.filename)
			
		return True
		
	def reset_pixbuf(self):
		self.size_label.set_text("")
		if not self.current_image:
			return
		
		if self.current_image.pixbuf is None:
			try:
				self.current_image.load()
			except:
				self.log("Could not load image pixbuf")
				raise
			
		pixbuf = self.current_image.pixbuf
		
		w, h = pixbuf.get_width(), pixbuf.get_height()
		
		if self.imageview.magnification != 0:
			zoom = 2 ** self.imageview.magnification
			
			if self.imageview.magnification > 0:
				self.size_label.set_text(_("%dx%dx%d")  % (w, h, zoom))
			else:
				self.size_label.set_text(_("%dx%d:%d")  % (w, h, 1.0 / zoom))
			
			w, h = int(math.ceil(pixbuf.get_width() * zoom)), int(math.ceil(pixbuf.get_height() * zoom))
			
			pixbuf = self.current_image.pixbuf.scale_simple(w, h, self.imageview.interpolation)
		else:
			self.size_label.set_text(_("%dx%d")  % (w, h))
					
		self.image.source = pixbuf
		self.imageview.pixbuf = pixbuf
		self.image.refresh_pixbuf()
		
	# Attempt to load a file, returns false when it fails
	def open(self, filename):
		if not os.path.exists(filename):
			self.log(_("\"%s\" does not exist.") % filename)
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
		hadjust, vadjust = self.imageview.get_hadjustment(), self.imageview.get_vadjustment()
		
		w, h = hadjust.props.upper - hadjust.props.page_size, vadjust.props.upper - vadjust.props.page_size
			
		hadjust.set_value(w // 2)
		vadjust.set_value(0)
		
	def run(self):
		gtk.main()
	
	# Events
	def refresh_size(self, data=None):
		if self.image.source:
			if self.image.pixbuf:
				# The the rotation used by gtk is counter clockwise
				# This converts the degrees to clockwise
				if self.image.rotation:
					r = u" %d°" % int(360 - self.image.rotation)
				else:
					r = ""
					
				# Magnification is logaritimic, so it must be converted to a scale.
				# Furthermore, scales that make the image smaller start with : (division symbol)
				if self.image.magnification:
					scale = int(2 ** math.fabs(self.image.magnification))
					if self.image.magnification > 0:
						z = "x%d" % scale
					else:
						z = ":%d" % scale
				else:
					z = ""
				
				# The width and height are from the source, not the pixbuf itself
				w, h = self.image.source.get_width(), self.image.source.get_height()
				
				# The format is WxH[x:]Z R°
				# e.g: 240x500x4 90° is a 240 width x 500 height image
				# Magnified 4 times and rotated 90 degrees clockwise
				self.size_label.set_text("%dx%d%s%s" % (w, h, z, r))
			else:
				# If self.image has a source but not a pixbuf, most likely
				# there is not enough momery to display it
				self.size_label.set_text(_("Error"))				
		else:
			self.size_label.set_text(_("Empty"))
				
	def flip (self, data=None, horizontal=False):
		if horizontal:
			self.image.flip_horizontal = not self.image.flip_horizontal
		else:
			self.image.flip_vertical = not self.image.flip_vertical
			
		self.image.refresh_pixbuf()
			
	def rotate(self, data=None, change=0):
		self.image.rotation = (int(self.image.rotation) - change + 360) % 360
		self.image.refresh_pixbuf()
		
	def change_zoom(self, data=None, change=0):
		self.image.magnification += change
		self.image.refresh_pixbuf()
		
	def reset_zoom(self, data=None):
		self.image.magnification = 0
		self.image.refresh_pixbuf()

	def change_interp(self, radioaction, current):
		interpolation = current.props.value
		self.image.interpolation = interpolation
		self.image.refresh_pixbuf()
	
	def change_scrollbars(self, radioaction, current):
		placement = current.props.value
#		placement = self.actions.get_action("no-scrollbars").get_current_value()
		
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
