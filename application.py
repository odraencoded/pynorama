# coding=utf-8
 
'''
	Pynorama is an image viewer application.
'''

import gc, os, sys, urllib, math
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import organization, navigation, loading
from gettext import gettext as _
#import navigation, loading, organization
from ximage import xImage

resource_dir = os.path.dirname(__file__)
DND_URI_LIST, DND_IMAGE = range(2)

class Pynorama(object):
	def __init__(self):
		self.organizer = organization.ImageNodeList()
		self.current_image = None	
		self.autosort = True
		
		# Create Window
		self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
		self.window.set_default_size(600, 600)
		self.window.set_title(_("Pynorama"))
		self.window.show()
		
		# Set clipboard
		self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		
		# Create layout
		vlayout = Gtk.VBox()
		self.window.add(vlayout)
		vlayout.show()
		
		# Setup actions
		self.setup_actions()
		
		self.manager.add_ui_from_file(os.path.join(resource_dir, "viewer.xml"))
		self.menubar = self.manager.get_widget("/menubar")
		self.toolbar = self.manager.get_widget("/toolbar")
		
		vlayout.pack_start(self.menubar, False, False, 0)
		vlayout.pack_start(self.toolbar, False, False, 0)
		
		self.menubar.show_all()
		self.toolbar.show_all()
		
		# Create image and a scrolled window for it		
		self.image = GObject.new(xImage)
		self.image.connect("pixbuf-notify", self.pixbuf_changed)
		
		self.imageview = Gtk.ScrolledWindow()
		self.imageview.add_with_viewport(self.image)
		self.imageview.pixbuf =  None
		
		vlayout.pack_start(self.imageview, True, True, 0)
		
		# Add navigator
		self.navigator = navigation.MapNavigator(self.imageview)
		
		self.imageview.show_all()
				
		# Add a status bar
		self.statusbar = Gtk.Statusbar()
		self.statusbar.set_spacing(24)
		
		# With a label for image index
		self.index_label = Gtk.Label()
		self.index_label.set_alignment(1, 0.5)
		self.statusbar.pack_end(self.index_label, False, False, 0)
		
		# And a label for the image transformation
		self.transform_label = Gtk.Label()
		self.transform_label.set_alignment(0, 0.5)
		self.statusbar.pack_end(self.transform_label, False, False, 0)
		
		# Show status
		vlayout.pack_end(self.statusbar, False, False, 0)
		
		self.statusbar.show_all()
		self.refresh_transform()
		self.refresh_index()
		
		# Connect events
		self.window.connect("destroy", self._window_destroyed)
		
		# DnD setup	
		self.imageview.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
		
		target_list = Gtk.TargetList.new([])
		target_list.add_image_targets(DND_IMAGE, False)
		target_list.add_uri_targets(DND_URI_LIST)
		
		self.imageview.drag_dest_set_target_list(target_list)
		
		self.imageview.connect("drag-data-received", self.dragged_data)
		
	def setup_actions(self):
		self.manager = Gtk.UIManager()
		self.accelerators = self.manager.get_accel_group()
		self.window.add_accel_group(self.accelerators)
		
		self.actions = Gtk.ActionGroup("pynorama")
		self.manager.insert_action_group(self.actions)	
		
		filemenu = Gtk.Action("file", _("File"), None, None)		
				
		openaction = Gtk.Action("open", _("Open..."), _("Open an image"), Gtk.STOCK_OPEN)
		openaction.connect("activate", self.file_open)
		
		pasteaction = Gtk.Action("paste", _("Paste"), _("Show an image from the clipboard"), Gtk.STOCK_PASTE)
		pasteaction.connect("activate", self.pasted_data)
		
		orderingmenu = Gtk.Action("ordering", _("Ordering"), None, None)
		
		sortaction = Gtk.Action("sort", _("Sort Images"), _("Sort the images currently loaded"), None)
		sortaction.connect("activate", self.sort_list)
		
		sortautoaction = Gtk.ToggleAction("auto-sort", _("Sort Automatically"), _("Sort images as they are added"), None)
		sortautoaction.set_active(True)
		sortautoaction.connect("toggled", self.toggle_autosort)
		
		sortreverseaction = Gtk.ToggleAction("reverse-sort", _("Reverse"), _("Order images in reverse"), None)
		sortreverseaction.connect("toggled", self.toggle_reversesort)
		
		removeaction = Gtk.Action("remove", _("Remove"), _("Remove the image from the viewer"), Gtk.STOCK_CLOSE)
		removeaction.connect("activate", self.remove)
		removeaction.set_sensitive(False)
		
		clearaction = Gtk.Action("clear", _("Remove All"), _("Remove all images from the viewer"), Gtk.STOCK_CLEAR)
		clearaction.connect("activate", self.clear)
		clearaction.set_sensitive(False)
		
		quitaction = Gtk.Action("quit", _("_Quit"), _("Exit the program"), Gtk.STOCK_QUIT)
		quitaction.connect("activate", self.quit)
		
		# Gooooooo!!!
		gomenu = Gtk.Action("go", _("Go"), None, None)		
		
		prevaction = Gtk.Action("previous", _("Previous Image"), _("Open the previous image"), Gtk.STOCK_GO_BACK)
		prevaction.connect("activate", self.goprevious)
		prevaction.set_sensitive(False)
		
		nextaction = Gtk.Action("next", _("Next Image"), _("Open the next image"), Gtk.STOCK_GO_FORWARD)
		nextaction.connect("activate", self.gonext)
		nextaction.set_sensitive(False)
		
		# Not
		firstaction = Gtk.Action("first", _("First Image"), _("Open the first image"), Gtk.STOCK_GOTO_FIRST)
		firstaction.connect("activate", self.gofirst)
		firstaction.set_sensitive(False)
		
		# Neither
		lastaction = Gtk.Action("last", _("Last Image"), _("Open the last image"), Gtk.STOCK_GOTO_LAST)
		lastaction.connect("activate", self.golast)
		lastaction.set_sensitive(False)
		
		sortingaction = Gtk.Action("last", _("Last Image"), _("Open the last image"), Gtk.STOCK_GOTO_LAST)
		sortingaction.connect("activate", self.golast)
		sortingaction.set_sensitive(False)
		
		# These actions are actual actions, not options.
		viewmenu = Gtk.Action("view", _("View"), None, None)
		
		zoominaction = Gtk.Action("in-zoom", _("Zoom In"), _("Makes the image look larger"), Gtk.STOCK_ZOOM_IN)
		zoomoutaction = Gtk.Action("out-zoom", _("Zoom Out"), _("Makes the image look smaller"), Gtk.STOCK_ZOOM_OUT)
		nozoomaction = Gtk.Action("no-zoom", _("No Zoom"), _("Shows the image at it's normal size"), Gtk.STOCK_ZOOM_100)
		
		nozoomaction.connect("activate", self.reset_zoom)
		zoominaction.connect("activate", self.change_zoom, 1)
		zoomoutaction.connect("activate", self.change_zoom, -1)
		
		transformmenu = Gtk.Action("transform", _("Transform"), None, None)
		rotatecwaction = Gtk.Action("cw-rotate", _("Rotate Clockwise"), _("Turns the image top side to the right side"), -1)
		rotateccwaction = Gtk.Action("ccw-rotate", _("Rotate Counter Clockwise"), _("Turns the image top side to the left side"), -1)
		
		rotatecwaction.connect("activate", self.rotate, 90)
		rotateccwaction.connect("activate", self.rotate, -90)
		
		fliphorizontalaction = Gtk.Action("h-flip", _("Flip Horizontally"), _("Inverts the left and right sides of the image"), -1)
		flipverticalaction = Gtk.Action("v-flip", _("Flip Vertically"), _("Inverts the top and bottom sides of the image"), -1)
		
		flipverticalaction.connect("activate", self.flip, False)
		fliphorizontalaction.connect("activate", self.flip, True)
				
		# Choices for pixel interpolation
		interpolationmenu = Gtk.Action("interpolation", _("Inter_polation"), None, None)
		
		interpnearestaction = Gtk.RadioAction("nearest-interp", _("Nearest Neighbour"), _(""), -1, GdkPixbuf.InterpType.NEAREST)
		interptilesaction = Gtk.RadioAction("tiles-interp", _("Parallelogram Tiles"), _(""), -1, GdkPixbuf.InterpType.TILES)
		interpbilinearaction = Gtk.RadioAction("bilinear-interp", _("Bilinear Function"), _(""), -1, GdkPixbuf.InterpType.BILINEAR)
		interphyperaction = Gtk.RadioAction("hyper-interp", _("Hyperbolic Function"), _(""), -1, GdkPixbuf.InterpType.HYPER)
		
		interptilesaction.join_group(interpnearestaction)
		interpbilinearaction.join_group(interptilesaction)
		interphyperaction.join_group(interpbilinearaction)
		
		interpolationmenu.set_sensitive(False)
		interpnearestaction.connect("changed", self.change_interp)
		
		# This is a very original part of the entire program
		scrollbarsmenu = Gtk.Action("scrollbars", _("_Scrollbars"), None, None)
		
		noscrollbars = Gtk.RadioAction("no-scrollbars", _("No Scroll Bars"), _("Hide scroll bars"), -1, -1)
		brscrollbars = Gtk.RadioAction("br-scrollbars", _("At Bottom Right"), _("Show scroll bars at the bottom right corner"), -1, Gtk.CornerType.TOP_LEFT)
		trscrollbars = Gtk.RadioAction("tr-scrollbars", _("At Top Right"), _("Show scroll bars at the top right corner"), -1, Gtk.CornerType.BOTTOM_LEFT)
		tlscrollbars = Gtk.RadioAction("tl-scrollbars", _("At Top Left"), _("Show scroll bars at the top left corner"), -1, Gtk.CornerType.BOTTOM_RIGHT)
		blscrollbars = Gtk.RadioAction("bl-scrollbars", _("At Bottom Left"), _("Show scroll bars at the bottom left corner"), -1, Gtk.CornerType.TOP_RIGHT)
		
		brscrollbars.join_group(noscrollbars)
		trscrollbars.join_group(brscrollbars)
		tlscrollbars.join_group(trscrollbars)
		blscrollbars.join_group(tlscrollbars)
		
		noscrollbars.set_current_value(Gtk.CornerType.TOP_RIGHT)
		noscrollbars.connect("changed", self.change_scrollbars)
		
		fullscreenaction = Gtk.ToggleAction("fullscreen", _("Fullscreen"), _("Fill the entire screen"), Gtk.STOCK_FULLSCREEN)
		fullscreenaction.connect("toggled", self.toggle_fullscreen)
		
		# Add to the action group
		# ALL the actions!
		self.actions.add_action(filemenu)
		
		self.actions.add_action_with_accel(openaction, None)
		self.actions.add_action_with_accel(pasteaction, None)
				
		self.actions.add_action_with_accel(removeaction, "Delete")
		self.actions.add_action_with_accel(clearaction, "<ctrl>Delete")
		
		self.actions.add_action(orderingmenu)
		self.actions.add_action(sortaction)
		self.actions.add_action(sortautoaction)
		self.actions.add_action(sortreverseaction)
				
		self.actions.add_action_with_accel(quitaction, None)
		
		self.actions.add_action(gomenu)
		
		self.actions.add_action_with_accel(prevaction, "Page_Up")
		self.actions.add_action_with_accel(nextaction, "Page_Down")
		
		self.actions.add_action_with_accel(firstaction, "Home")
		self.actions.add_action_with_accel(lastaction, "End")
				
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
					
		previous_image = self.current_image
		self.current_image = image
		
		can_next, can_previous = True, True
		can_first, can_last = True, True
	
		if self.current_image is None:
			self.imageview.pixbuf = self.image.source = None
			
			self.window.set_title(_("Pynorama"))
					
			can_next = can_previous = False
			can_remove = False
			can_first = can_last = bool(self.organizer.images)
				
		else:
			try:
				if not self.current_image.is_loaded():
					self.log(_("Loading \"%s\"...")  % self.current_image.fullname)
					self.current_image.load()
					
			except:
				self.log(str(sys.exc_info()[1]))
				pixbuf = self.window.render_icon(Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.DIALOG)
								
			else:
				self.log(_("Loaded \"%s\"")  % self.current_image.fullname)
				pixbuf = self.current_image.pixbuf
				
			self.imageview.pixbuf = self.image.source = pixbuf
			can_remove = True
			
			if len(self.organizer.images) > 1 or self.current_image not in self.organizer.images:	
				can_first = can_last = True
				can_next, can_previous = self.current_image.next is not None, self.current_image.previous is not None
			else:
				can_next = can_previous = False
				can_first = can_last = False
	
			self.window.set_title(_("\"%s\" - Pynorama") % self.current_image.name)		
		
		self.image.refresh_pixbuf()
		self.readjust_view()
		
		self.actions.get_action("remove").set_sensitive(can_remove)
		self.actions.get_action("clear").set_sensitive(len(self.organizer.images) > 0)
		
		self.actions.get_action("next").set_sensitive(can_next)
		self.actions.get_action("previous").set_sensitive(can_previous)
		
		self.actions.get_action("first").set_sensitive(can_first)
		self.actions.get_action("last").set_sensitive(can_last)
		
		self.refresh_index()
			
		return True
		
	def load_pixels(self, pixels, title="Image Data"):
		loaded_image = loading.ImageDataNode(pixels, title)
		
		if self.current_image and self.current_image not in self.organizer.images:
			self.current_image.insert_links(self.current_image.previous, loaded_image)
			
		else:
			loaded_image.previous = self.current_image
		
		self.set_image(loaded_image)
	
	def load_uris(self, uris):
		# Organizer uris of the internet and file locations
		all_nodes, uri_nodes, file_nodes = [], [], []
		directories, real_paths = set(), set()
		
		# When loading filepaths, a real path should be checked against real_paths
		# And the ImageFilePath should be loaded with the "normal" path
		
		last_is_file = False
		for an_uri in uris:
			# Attempt to get a filepath from the URI
			a_path = loading.PathFromURI(an_uri)
			
			if a_path is None:
				# If the URI can't be converted into a path load it as an URI
				an_uri_node = loading.ImageURINode(an_uri)
				uri_nodes.append(an_uri_node)
				all_nodes.append(an_uri_node)
				
				last_is_file = False
			elif os.path.exists(a_path):
				# The URI is an existing filepath! 
				a_real_path = os.path.realpath(a_path)
				
				if not a_real_path in real_paths:
					if os.path.isfile(a_real_path):
						# If it is a file load a file node
						a_file_node = loading.ImageFileNode(a_path)
						file_nodes.append(a_file_node)
						all_nodes.append(a_file_node)
				
					# Add the directory to the directories set
					directories.add(os.path.dirname(a_real_path))
					
					real_paths.add(a_real_path)
					last_is_file = True
		
		# FIXME: Customize this into "disabled", "shallow" and "deep"
		directory_loading = "shallow"
		
		if directory_loading == "shallow":
			for a_directory in directories:
				for a_image_path in loading.get_image_paths(a_directory):
					a_real_image_path = os.path.realpath(a_image_path)
					
					# Recursive links are evil!
					if not a_real_image_path in real_paths:
						a_file_node = loading.ImageFileNode(a_image_path)
						file_nodes.append(a_file_node)
						all_nodes.append(a_file_node)
						
						real_paths.add(a_real_path)
		
		# Load files into the organizer
		if all_nodes:
			self.current_image = None
			self.organizer.clear()
			gc.collect()
			
			for a_node in all_nodes:
				self.organizer.add(a_node)
			
			if self.autosort:
				self.organizer.sort(organization.Sorting.ByFullname)
			
			self.set_image(all_nodes[0])
			
			if len(all_nodes) > 1:
				self.log(_("Found %d images") % len(all_nodes))
	
	# Adjusts the image to be on the top-center (so far)
	def readjust_view(self):		
		if self.image.pixbuf:
			w, h = self.image.pixbuf.get_width(), self.image.pixbuf.get_height()
			alloc = self.imageview.get_allocation()
			vw, vh = alloc.width, alloc.height
			
			x = (w - vw) // 2
			y = 0
			
			self.imageview.get_hadjustment().set_value(x)
			self.imageview.get_vadjustment().set_value(y)
		
	def run(self):
		Gdk.set_program_class("Pynorama")
		Gtk.main()
	
	# Events
	def toggle_reversesort(self, data=None):
		reverse = self.actions.get_action("reverse-sort").get_active()
		if self.organizer.reverse != reverse:
			self.organizer.reverse = reverse
			self.organizer.images.reverse()
			self.refresh_index()
		
	def toggle_autosort(self, data=None):
		self.autosort = self.actions.get_action("auto-sort").get_active()
		
	def sort_list(self, data=None):
		self.organizer.sort(organization.Sorting.ByFullname)
		self.refresh_index()
		
	def pixbuf_changed(self, data=None):
		self.refresh_transform()
		self.refresh_interp()
		
	def refresh_interp(self):	
		interp = self.image.get_interpolation()
		self.actions.get_action("interpolation").set_sensitive(interp is not None)
		
		interp_group = self.actions.get_action("nearest-interp")
		interp_group.block_activate()
		
		if interp is None:
			for interp_action in interp_group.get_group():
				interp_action.set_active(False)
		else:
			interp_group.set_current_value(interp)
			
		interp_group.unblock_activate()
		
	def refresh_index(self):
		if self.organizer.images:
			count = len(self.organizer.images)
			count_w = len(str(count))
			
			if self.current_image in self.organizer.images:
				index = self.organizer.images.index(self.current_image) + 1
				index_text = str(index).zfill(count_w)
				
				self.index_label.set_text(_("#%s/%d") % (index_text, count))
			else:
				index_text = _("?") * count_w
				self.index_label.set_text(_("%s/%d") % (index_text, count))
								
		else:
			self.index_label.set_text(u"∅")
		
	def refresh_transform(self):
		if self.current_image:
			if self.current_image.pixbuf and self.image.pixbuf:
				# The width and height are from the source
				p = "{width}x{height}".format(width=self.image.source.get_width(), height=self.image.source.get_height())
			else:
				# This just may happen
				p = _("Error")
				
		else:
			p = _("Nothing")
			
		# The the rotation used by gtk is counter clockwise
		# This converts the degrees to clockwise
		if self.image.rotation:
			r = " " + u"{angle}°".format(angle=int(360 - self.image.rotation))
		else:
			r = ""
			
		# Magnification is logaritimic, so it must be converted to a scale.
		# Furthermore, scales that make the image smaller start with : (division symbol)
		if self.image.magnification:
			scale = self.image.get_zoom()
			
			if self.image.magnification > 0:
				zoom_text = ("%.2f" % scale).rstrip("0").rstrip(".")
				z = " " + "x{zoom_in}".format(zoom_in=zoom_text)
			else:
				zoom_text = ("%.2f" % (1.0 / scale)).rstrip("0").rstrip(".")
				z = " " + ":{zoom_out}".format(zoom_out=zoom_text)
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
		self.transform_label.set_text("%s%s%s%s" % (p, z, r, f))
				
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
		if self.image.magnification:
			interpolation = current.props.value	
			self.image.set_interpolation(interpolation)
			
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
		# This simply tries to fullscreen / unfullscreen
		fullscreenaction = self.actions.get_action("fullscreen")
		
		if fullscreenaction.props.active:
			self.window.fullscreen()
			fullscreenaction.set_stock_id(Gtk.STOCK_LEAVE_FULLSCREEN)
		else:
			self.window.unfullscreen()
			fullscreenaction.set_stock_id(Gtk.STOCK_FULLSCREEN)
	
	def gofirst(self, data=None):
		first_image = self.organizer.get_first()
		if first_image:
			self.set_image(first_image)
	
	def golast(self, data=None):
		last_image = self.organizer.get_last()
		if last_image:
			self.set_image(last_image)
	
	
	def gonext(self, data=None):
		if self.current_image and self.current_image.next:
			self.set_image(self.current_image.next)
		
	def goprevious(self, data=None):
		if self.current_image and self.current_image.previous:
			self.set_image(self.current_image.previous)
	
	def clear(self, data=None):
		self.organizer.clear()
		self.set_image(None)
		gc.collect()
		
		self.refresh_index()
		self.log(_("Removed all images"))
		
	def remove(self, data=None):
		if self.current_image is None:
			return

		removed_image = self.current_image
		
		if self.current_image in self.organizer.images:
			# If there are no images left in the list, sets the image to None
			if len(self.organizer.images) > 1:
				last_image = self.organizer.get_last()
				
				if removed_image is last_image:
					new_image = removed_image.previous
				else:
					new_image = removed_image.next
					
			else:
				new_image = None
				
			self.organizer.remove(removed_image)
		else:
			if removed_image.next:
				new_image = removed_image.next
			else:
				new_image = removed_image.previous
				
			removed_image.remove_links()
		
		self.set_image(new_image)
		self.log(_("Removed \"%s\"") % removed_image.fullname)
	
	def pasted_data(self, data=None):
		uris = self.clipboard.wait_for_uris()
			
		if uris:
			self.load_uris(uris)
			return
			
		pixel_data = self.clipboard.wait_for_image()
		if pixel_data:
			self.load_pixels(pixel_data, "Pasted Image")
			return
			
		text = self.clipboard.wait_for_text()
		if text:
			if text.startswith(("http://", "https://", "ftp://")):
				self.load_uris([text])
			
	def dragged_data(self, widget, context, x, y, selection, info, timestamp):
		print "draggn"
		if info == DND_URI_LIST:
			self.load_uris(selection.get_uris())
			return
							
		elif info == DND_IMAGE:
			pixel_data = selection.data.get_pixbuf()
			if pixel_data:
				self.load_pixels(pixel_data, "Dropped Image")
		
	def file_open(self, widget, data=None):
		# Create image choosing dialog
		image_chooser = Gtk.FileChooserDialog(title = _("Open Image..."), action = Gtk.FileChooserAction.OPEN,
			buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
			
		image_chooser.set_default_response(Gtk.ResponseType.OK)
		image_chooser.set_select_multiple(True)
		
		# Add filters of supported formats from "loading" module
		for fileFilter in loading.Filters:
			image_chooser.add_filter(fileFilter)
		
		try:
			if image_chooser.run() == Gtk.ResponseType.OK:
				uris = image_chooser.get_uris()
				self.load_uris(uris)
								
		except:
			# Nothing to handle here
			raise
			
		else:
			# Destroy the dialog anyway
			image_chooser.destroy()
	
	def quit(self, widget=None, data=None):
		Gtk.main_quit()
	
	def _window_destroyed(self, widget, data=None):
		self.quit()
