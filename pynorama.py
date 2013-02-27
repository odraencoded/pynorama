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
		self.refresh_size()
		
		# Setup actions
		self.manager = gtk.UIManager()
		self.accelerators = self.manager.get_accel_group()
		self.window.add_accel_group(self.accelerators)
		
		self.actions = gtk.ActionGroup("pynorama")
		self.manager.insert_action_group(self.actions)	
		
		filemenu = gtk.Action("file", _("_File"), None, None)		
				
		openaction = gtk.Action("open", _("_Open..."), _("Open an image"), gtk.STOCK_OPEN)
		openaction.connect("activate", self.file_open)
		
		prevaction = gtk.Action("previous", _("Pr_evious Image"), _("Open the previous image"), gtk.STOCK_GO_BACK)
		prevaction.connect("activate", self.goprevious)
		prevaction.set_sensitive(False)
		
		nextaction = gtk.Action("next", _("Nex_t Image"), _("Open the next image"), gtk.STOCK_GO_FORWARD)
		nextaction.connect("activate", self.gonext)
		nextaction.set_sensitive(False)
		
		quitaction = gtk.Action("quit", _("_Quit"), _("Exit the program"), gtk.STOCK_QUIT)
		quitaction.connect("activate", self.quit)
		
		# These actions are actual actions, not options.
		viewmenu = gtk.Action("view", _("_View"), None, None)
		
		zoominaction = gtk.Action("in-zoom", _("Zoom _In"), _("Makes the image look larger"), gtk.STOCK_ZOOM_IN)
		zoomoutaction = gtk.Action("out-zoom", _("Zoom _Out"), _("Makes the image look smaller"), gtk.STOCK_ZOOM_OUT)
		nozoomaction = gtk.Action("no-zoom", _("No _Zoom"), _("Makes the image look normal"), gtk.STOCK_ZOOM_100)
		
		nozoomaction.connect("activate", self.reset_zoom)
		zoominaction.connect("activate", self.change_zoom, 1)
		zoomoutaction.connect("activate", self.change_zoom, -1)
		
		transformmenu = gtk.Action("transform", _("_Transform"), None, None)
		rotatecwaction = gtk.Action("cw-rotate", _("Rotate Clockwis_e"), _("Turns the image top side to the right side"), -1)
		rotateccwaction = gtk.Action("ccw-rotate", _("Rotate Counter Clock_wise"), _("Turns the image top side to the left side"), -1)
		
		rotatecwaction.connect("activate", self.rotate, 90)
		rotateccwaction.connect("activate", self.rotate, -90)
		
		fliphorizontalaction = gtk.Action("h-flip", _("Flip _Horizontally"), _("Inverts the left and right sides of the image"), -1)
		flipverticalaction = gtk.Action("v-flip", _("Flip _Vertically"), _("Inverts the top and bottom sides of the image"), -1)
		
		flipverticalaction.connect("activate", self.flip, False)
		fliphorizontalaction.connect("activate", self.flip, True)
				
		# Choices for pixel interpolation
		interpolationmenu = gtk.Action("interpolation", _("Inter_polation"), None, None)
		
		interpnearestaction = gtk.RadioAction("nearest-interp", _("_Nearest Neighbour"), _(""), -1, gtk.gdk.INTERP_NEAREST)
		interptilesaction = gtk.RadioAction("tiles-interp", _("Parallelo_gram Tiles"), _(""), -1, gtk.gdk.INTERP_TILES)
		interpbilinearaction = gtk.RadioAction("bilinear-interp", _("_Bilinear Function"), _(""), -1, gtk.gdk.INTERP_BILINEAR)
		interphyperaction = gtk.RadioAction("hyper-interp", _("_Hyperbolic Function"), _(""), -1, gtk.gdk.INTERP_HYPER)
		
		interptilesaction.set_group(interpnearestaction)
		interpbilinearaction.set_group(interpnearestaction)
		interphyperaction.set_group(interpnearestaction)
		
		interpnearestaction.set_current_value(self.image.interpolation)
		interpnearestaction.connect("changed", self.change_interp)
		
		# This is a very original part of the entire program
		scrollbarsmenu = gtk.Action("scrollbars", _("_Scrollbars"), None, None)
		
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
		
		# Add to the action group
		# ALL the actions!
		self.actions.add_action(filemenu)
		
		self.actions.add_action_with_accel(openaction, None)

		self.actions.add_action_with_accel(prevaction, "Page_Up")
		self.actions.add_action_with_accel(nextaction, "Page_Down")
				
		self.actions.add_action_with_accel(quitaction, None)
		
		self.actions.add_action(viewmenu)
		self.actions.add_action_with_accel(nozoomaction, "space")
		self.actions.add_action_with_accel(zoominaction, "KP_Add")
		self.actions.add_action_with_accel(zoomoutaction, "KP_Subtract")
		
		self.actions.add_action(transformmenu)
		self.actions.add_action_with_accel(rotatecwaction, "R")
		self.actions.add_action_with_accel(rotateccwaction, "<Ctrl>R")
		
		self.actions.add_action_with_accel(fliphorizontalaction, "F")
		self.actions.add_action_with_accel(flipverticalaction, "<Ctrl>F")
		
		self.actions.add_action(interpolationmenu)
		
		self.actions.add_action(interpnearestaction)
		self.actions.add_action(interptilesaction)
		self.actions.add_action(interpbilinearaction)
		self.actions.add_action(interphyperaction)
		
		self.actions.add_action(scrollbarsmenu)
		self.actions.add_action(noscrollbars)
		self.actions.add_action(brscrollbars)
		self.actions.add_action(blscrollbars)
		self.actions.add_action(tlscrollbars)
		self.actions.add_action(trscrollbars)
		
		self.actions.add_action_with_accel(fullscreenaction, "F4")
		
		self.manager.add_ui_from_file("viewer.xml")
		
		# Put everything in a nice layout
		vlayout = gtk.VBox()
		
		self.menubar = self.manager.get_widget("/menubar")
		self.toolbar = self.manager.get_widget("/toolbar")
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
		else:
			self.actions.get_action("previous").set_sensitive(True)
			self.actions.get_action("next").set_sensitive(True)
			
		self.current_image = image	
		if self.current_image is None:			
			self.window.set_title(_("Pynorama"))
			self.size_label.set_text("")
			self.imageview.pixbuf = None
			
			self.actions.get_action("previous").set_sensitive(False)
			self.actions.get_action("next").set_sensitive(False)
			
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
		if self.image.pixbuf:
			w, h = self.image.pixbuf.get_width(), self.image.pixbuf.get_height()
			alloc = self.imageview.get_allocation()
			vw, vh = alloc[2], alloc[3]
			
			x = (w - vw) // 2
			y = 0
			
			self.imageview.get_hadjustment().set_value(x)
			self.imageview.get_vadjustment().set_value(y)
		
	def run(self):
		gtk.main()
	
	# Events
	def refresh_size(self, data=None):
		if self.image.source:
			if self.image.pixbuf:
				# The width and height are from the source
				p = "%dx%d" % (self.image.source.get_width(), self.image.source.get_height())
			else:
				# If self.image has a source but not a pixbuf, most likely
				# there is not enough momery to display it
				p = _("Error")
		else:
			p = _("Nothing")
			
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
		
		# For flipping/inverting/mirroring
		# Pro-tip: Rotation affects it
		if self.image.flip_horizontal:
			if int(self.image.rotation) % 180:
				f = u" ↕"
			else:
				f = u" ↔"
		elif self.image.flip_vertical:
			if int(self.image.rotation) % 180:
				f = u" ↔"
			else:
				f = u" ↕"
		else: 
			f = ""
		
		# The format is WxH[x:]Z R° [↕↔] except when something goes wrong
		# e.g: 240x500x4 90° ↕ is a 240 width x 500 height image
		# Magnified 4 times rotated 90 degrees clockwise and
		# Mirrored vertically (horizontally at 0° though)
		self.size_label.set_text("%s%s%s%s" % (p, z, r, f))
				
	def flip(self, data=None, horizontal=False):
		# Horizontal mirroring depends on the rotation of the image
		if int(self.image.rotation) % 180:
			# 90 or 270 degrees
			if horizontal:
				self.image.flip_vertical = not self.image.flip_vertical
			else:
				self.image.flip_horizontal = not self.image.flip_horizontal
			
		else:
			# 0 or 180 degrees
			if horizontal:
				self.image.flip_horizontal = not self.image.flip_horizontal
			else:
				self.image.flip_vertical = not self.image.flip_vertical
		
		# If the image if flipped both horizontally and vertically
		# Then it is rotated 180 degrees
		if self.image.flip_vertical and self.image.flip_horizontal:
			self.image.flip_vertical = self.image.flip_horizontal = False
			self.image.rotation = (int(self.image.rotation) + 180) % 360
		
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
	gtk.gdk.set_program_class("Pynorama")
	app.run()
