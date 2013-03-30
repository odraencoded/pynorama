#!/usr/bin/python3
# coding=utf-8
 
''' Pynorama is an image viewer application. '''

import gc, os, sys, urllib, math
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib
from gettext import gettext as _
import organization, navigation, loading, preferences
from ximage import xImage
import argparse

resource_dir = os.path.dirname(__file__)
DND_URI_LIST, DND_IMAGE = range(2)

class ImageViewer(Gtk.Application):
	def __init__(self):
		Gtk.Application.__init__(self)
		self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)
		
		# Default prefs stuff
		self.zoom_effect = 2
		self.navi_factory = navigation.MapNavi
		self.loaded_imagery = set()
		
	def do_startup(self):
		Gtk.Application.do_startup(self)
	
	def get_window(self):
		windows = self.get_windows() # XP, Vista, 7, 8?
		if windows:
			# Return most recently focused window
			return windows[0]
		else:
			# Create a window and return it
			a_window = ViewerWindow(self)
			a_window.show()
			a_window.set_navigator(self.navi_factory)
			return a_window
		
	def do_activate(self):
		some_window = self.get_window()
		some_window.present()
		
	def do_open(self, files, file_count, hint):
		some_window = self.get_window()
		images = self.load_files(files)
		if images:
			some_window.enlist(*images)
			some_window.set_image(images[0])
			
		some_window.present()
	
	def load_files(self, files):
		loaded_images = []
		front_image = None
		if len(files) == 1:
			single_file = files[0]
			if not loading.IsAlbumFile(single_file) \
			   and single_file.has_parent(None) \
			   and loading.IsSupportedImage(single_file):
				parent_file = single_file.get_parent()
				# Try to get some images from the parent
				# This will fail if it's a network file
				try:
					some_files = loading.GetFileImageFiles(parent_file)
				except GLib.GError:
					pass # Blimey, it didn't work!
				else:
					files = some_files
					# Move the former single image file to the start
					for a_file in files:
						if a_file.equal(single_file):
							files.remove(a_file)
							break
					files.insert(0, single_file)
										
		# Load images from files!
		for a_file in files:
			if loading.IsAlbumFile(a_file):
				some_images = loading.GetAlbumImages(a_file)
				loaded_images.extend(some_images)
			else:
				an_image = loading.ImageGFileNode(a_file)
				loaded_images.append(an_image)
				
		return loaded_images
		if new_images:
			self.organizer.add(*new_images)
			if front_image is None:
				front_image = new_images[0]
			
			# Do some sorting
			if self.main_window.autosort:
				self.organizer.sort(self.main_window.active_ordering)
							
			self.main_window.set_image(front_image)
			self.tell_info(_("Added %d images for viewing") % len(new_images))
			
	def load_paths(self, paths):			
		gfiles = [Gio.File.new_for_path(a_path) for a_path in paths]
		return self.load_files(gfiles)
	
	def load_uris(self, uris):
		gfiles = [Gio.File.new_for_uri(an_uri) for an_uri in uris]
		return self.load_files(gfiles)
	
	def load_pixels(self, pixels):
		pixelated_image = loading.ImageDataNode(pixels, "Pixels")
		return [pixelated_image]
			
	''' These methods control loading, unloading and the
	    caching of images. Basically, the loading module
	    defines what can be loaded and how, but instead
	    of calling those image loading methods directly,
	    the images are passed to the application so
	    they can be calculated into memory usage. '''
    # TODO: Add the above mentioned caching support.
	def flag_listed(self, window, *images):
		''' Marks images as being listed by something,
		    that means it could be cached or something '''
		
		pass
		
	def flag_unlisted(self, window, *images):
		''' Marks images as not being listed by something,
		    that means it no longer requires caching '''
		
		pass
	    
	def flag_unrequired(self, window, *images):
		''' Marks images as not being used right now,
		    that means it can be unloaded anytime '''
		    
		# TODO: Add preloading support
		for an_image in images:
			an_image.unload()
			self.loaded_imagery.discard(an_image)
		
	def flag_required(self, window, *images):
		''' Marks images as required by a window,
		    that means we need it loaded.
		    Like, right now. '''
		    
		loading_fmt = _("Loading “%s”")
		loaded_fmt = _("“%s” is loaded")
		for an_image in images:
			if not an_image.is_loaded():
				try:
					self.tell_info(loading_fmt % an_image.fullname, window)
					an_image.load()
					self.loaded_imagery.add(an_image)
				except:
					self.tell_exception(window)
				else:
					self.tell_info(loaded_fmt % an_image.fullname, window)
	
	''' These methods tell things
	    And stuff '''	
	def tell_info(self, message, window):
		window.statusbar.push(0, message)
		print(message)
	
	def tell_exception(self, window):
		info = sys.exc_info()
		window.statusbar.push(0, _("Error: %s" % info[1]))
		print(info[1])
		
	def set_navi_factory(self, navi_factory):
		self.navi_factory = navi_factory
		for a_window in self.get_windows():
			if a_window.navi_mode != navi_factory:
				a_window.set_navigator(self, navi_factory)
	
class ViewerWindow(Gtk.ApplicationWindow):
	def __init__(self, app):
		Gtk.ApplicationWindow.__init__(self,
		                               title=_("Pynorama"),
		                               application=app)
		self.app = app
		self.set_default_size(600, 600)
		self.current_image = None
		self.autosort = True
		self.navigator = None
		self.navi_mode = None
		self.image_list = organization.ImageList()
		# Set clipboard
		self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		
		# Create layout
		vlayout = Gtk.VBox()
		self.add(vlayout)
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
		self.image_scroller = Gtk.ScrolledWindow()
		# FIXME: There ought to be a better way
		# to drop the default key behaviour
		self.image_scroller.connect("key-press-event", lambda x, y: True)
		self.image_scroller.connect("key-release-event", lambda x, y: True)
		self.image_scroller.connect("scroll-event", lambda x, y: True)
		self.imageview = xImage()
		self.imageview.connect("pixbuf-notify", self.pixbuf_changed)
		
		self.image_scroller.add(self.imageview)
		self.image_scroller.show_all()
		
		vlayout.pack_start(self.image_scroller, True, True, 0)
						
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
		
		# DnD setup	
		self.imageview.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
		
		target_list = Gtk.TargetList.new([])
		target_list.add_image_targets(DND_IMAGE, False)
		target_list.add_uri_targets(DND_URI_LIST)
		
		self.imageview.drag_dest_set_target_list(target_list)
		self.imageview.add_events(Gdk.EventMask.SCROLL_MASK)
		self.imageview.connect("scroll-event", self.imageview_scrolling)
		self.imageview.connect("drag-data-received", self.dragged_data)
		
	def setup_actions(self):
		self.manager = Gtk.UIManager()
		self.accelerators = self.manager.get_accel_group()
		self.add_accel_group(self.accelerators)
		
		self.actions = Gtk.ActionGroup("pynorama")
		self.manager.insert_action_group(self.actions)
		
		filemenu = Gtk.Action("file", _("File"), None, None)		
				
		openaction = Gtk.Action("open", _("Open..."), _("Open an image"), Gtk.STOCK_OPEN)
		openaction.connect("activate", self.file_open)
		
		pasteaction = Gtk.Action("paste", _("Paste"), _("Show an image from the clipboard"), Gtk.STOCK_PASTE)
		pasteaction.connect("activate", self.pasted_data)
		
		orderingmenu = Gtk.Action("ordering", _("Ordering"), None, None)
		
		sortaction = Gtk.Action("sort", _("Sort Images"), _("Sort the images currently loaded"), None)
		sortaction.connect("activate", lambda data: self.sort_images())
		
		sort_auto_action = Gtk.ToggleAction("auto-sort", _("Sort Automatically"), _("Sort images as they are added"), None)
		sort_auto_action.set_active(True)
		sort_auto_action.connect("toggled", self.toggle_autosort)
		
		sort_reverse_action = Gtk.ToggleAction("reverse-sort", _("Reverse Order"), _("Order images in reverse"), None)
		sort_reverse_action.connect("toggled", self.toggle_reversesort)
		
		self.ordering_modes = [
			organization.Ordering.ByName,
			organization.Ordering.ByFileDate,
			organization.Ordering.ByFileSize,
			organization.Ordering.ByImageSize,
			organization.Ordering.ByImageWidth,
			organization.Ordering.ByImageHeight
		]
		self.active_ordering = organization.Ordering.ByName
		
		sort_name_action = Gtk.RadioAction("name-sort", _("By Name"), _("Order images alphabetically"), None, 0)
		sort_filedate_action = Gtk.RadioAction("file-date-sort", _("By Modification Date"), _("Recently modified images appear first"), None, 1)
		sort_filesize_action = Gtk.RadioAction("file-size-sort", _("By File Size"), _("Smaller files appear first"), None, 2)
		
		sort_imgsize_action = Gtk.RadioAction("img-size-sort", _("By Image Size"), _("Smaller images appear first"), None, 3)
		sort_imgwidth_action = Gtk.RadioAction("img-width-sort", _("By Image Width"), _("Narrower images appear first"), None, 4)
		sort_imgheight_action = Gtk.RadioAction("img-height-sort", _("By Image Height"), _("Shorter images appear first"), None, 5)
		
		sort_filedate_action.join_group(sort_name_action)
		sort_filesize_action.join_group(sort_filedate_action)
		
		sort_imgsize_action.join_group(sort_filesize_action)
		sort_imgwidth_action.join_group(sort_imgsize_action)
		sort_imgheight_action.join_group(sort_imgwidth_action)
		
		sort_name_action.set_current_value(self.ordering_modes.index(self.active_ordering))
		sort_name_action.connect("changed", self.change_ordering)
		
		removeaction = Gtk.Action("remove", _("Remove"), _("Remove the image from the viewer"), Gtk.STOCK_CLOSE)
		removeaction.connect("activate", self.remove)
		removeaction.set_sensitive(False)
		
		clearaction = Gtk.Action("clear", _("Remove All"), _("Remove all images from the viewer"), Gtk.STOCK_CLEAR)
		clearaction.connect("activate", self.clear)
		clearaction.set_sensitive(False)
		
		quitaction = Gtk.Action("quit", _("_Quit"), _("Exit the program"), Gtk.STOCK_QUIT)
		quitaction.connect("activate", lambda w: self.destroy())
		
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
		zoominaction.connect("activate", self.handle_zoom_change, 1)
		zoomoutaction.connect("activate", self.handle_zoom_change, -1)
		
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
		
		preferencesaction = Gtk.Action("preferences", _("Preferences..."), _("Configure Pynorama"), Gtk.STOCK_PREFERENCES)
		preferencesaction.connect("activate", self.show_preferences)
		
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
		self.actions.add_action(sort_auto_action)
		self.actions.add_action(sort_reverse_action)
		
		self.actions.add_action(sort_name_action)
		self.actions.add_action(sort_filedate_action)
		self.actions.add_action(sort_filesize_action)
		
		self.actions.add_action(sort_imgsize_action)
		self.actions.add_action(sort_imgwidth_action)
		self.actions.add_action(sort_imgheight_action)
				
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
		
		self.actions.add_action(preferencesaction)
		
		self.actions.add_action_with_accel(fullscreenaction, "F4")
		
	# Events		
	def show_preferences(self, data=None):
		prefs_dialog = preferences.Dialog(self.app)
			
		prefs_dialog.set_transient_for(self)
		prefs_dialog.set_modal(True)
		
		if prefs_dialog.run() == Gtk.ResponseType.OK:
			prefs_dialog.save_prefs()
						
		prefs_dialog.destroy()
		
	def change_ordering(self, radioaction, current):
		sort_value = current.get_current_value()
		self.active_ordering = self.ordering_modes[sort_value]
		
		self.image_list.sort(self.active_ordering)
		self.refresh_index()
		
	def toggle_reversesort(self, data=None):
		reverse = self.actions.get_action("reverse-sort").get_active()
		if self.image_list.reverse != reverse:
			self.image_list.reverse = reverse
			self.image_list.images.reverse()
			self.refresh_index()
		
	def toggle_autosort(self, data=None):
		self.autosort = self.actions.get_action("auto-sort").get_active()
		
	def pixbuf_changed(self, data=None):
		self.refresh_transform()
		self.refresh_interp()
		
	def refresh_interp(self):	
		interp = self.imageview.get_interpolation()
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
		images = self.image_list.images
		if images:
			can_remove = True
			can_goto_extremity = True
			
			count = len(images)
			count_w = len(str(count))
			
			if self.current_image in images:
				index = images.index(self.current_image) + 1
				index_text = str(index).zfill(count_w)
				
				self.index_label.set_text(_("#%s/%d") % (index_text, count))
			else:
				index_text = _("?") * count_w
				self.index_label.set_text(_("%s/%d") % (index_text, count))
								
		else:
			can_remove = self.current_image is not None
			can_goto_extremity = False
			
			self.index_label.set_text("∅")
		
		if self.current_image:
			can_remove = True
			if not (len(images) <= 1 and self.current_image in images):
				can_previous = bool(self.current_image.previous)
				can_next = bool(self.current_image.next)
			else:
				can_next = can_previous = False
		else:
			can_remove = can_previous = can_next = False
			
		self.actions.get_action("remove").set_sensitive(can_remove)
		self.actions.get_action("clear").set_sensitive(len(images) > 0)
		
		self.actions.get_action("next").set_sensitive(can_next)
		self.actions.get_action("previous").set_sensitive(can_previous)
		
		self.actions.get_action("first").set_sensitive(can_goto_extremity)
		self.actions.get_action("last").set_sensitive(can_goto_extremity)
		
	def refresh_transform(self):
		if self.current_image:
			if self.current_image.pixbuf and self.imageview.pixbuf:
				# The width and height are from the source
				width = self.imageview.source.get_width()
				height = self.imageview.source.get_height()
				pic = "{width}x{height}".format(width=width, height=height)
			else:
				# This just may happen
				pic = _("Error")
			
			# Cache magnification because it is kind of a long variable
			mag = self.imageview.magnification
			if mag != 1:			
				if mag > 1 and mag == int(mag):
					zoom_fmt = " " + _("x{zoom_in:d}")
					zoom = zoom_fmt.format(zoom_in=int(mag))
				elif mag < 1 and 1.0 / mag == int(1.0 / mag):
					zoom_fmt = " " + _(":{zoom_out:d}")
					zoom = zoom_fmt.format(zoom_out=int(1.0 / mag))
				else:
					zoom_fmt = " " +  _("{zoom:.0%}")
					zoom = zoom_fmt.format(zoom=mag)
			else:
				zoom = ""
		
			''' The the rotation used by gtk is counter clockwise
			    This converts the degrees to clockwise '''
			if self.imageview.rotation:
				rot_fmt = " " + _("{angle}°")
				rot = rot_fmt.format(angle=int(360 - self.imageview.rotation))
			else:
				rot = ""
			
			''' For flipping/inverting/mirroring
				Pro-tip: Rotation affects it '''
			if self.imageview.flip_horizontal:
				if int(self.imageview.rotation) % 180:
					mirror = " ↕"
				else:
					mirror = " ↔"
			elif self.imageview.flip_vertical:
				if int(self.imageview.rotation) % 180:
					mirror = " ↔"
				else:
					mirror = " ↕"
			else: 
				mirror = ""
				
			''' Sets the transform label to Width x Height or "Error",
			    zoom, rotation and mirroring combined '''
			transform = (pic, zoom, rot, mirror)
			self.transform_label.set_text("%s%s%s%s" % transform)
		else:
			''' Sets the transform label to nothing.
			    Because there is nothing to transform. '''
			self.transform_label.set_text(_("Nothing"))
							
	def flip(self, data=None, horizontal=False):
		# Horizontal mirroring depends on the rotation of the image
		if int(self.imageview.rotation) % 180:
			# 90 or 270 degrees
			if horizontal:
				self.imageview.flip_vertical = not self.imageview.flip_vertical
			else:
				self.imageview.flip_horizontal = not self.imageview.flip_horizontal
			
		else:
			# 0 or 180 degrees
			if horizontal:
				self.imageview.flip_horizontal = not self.imageview.flip_horizontal
			else:
				self.imageview.flip_vertical = not self.imageview.flip_vertical
		
		# If the image if flipped both horizontally and vertically
		# Then it is rotated 180 degrees
		if self.imageview.flip_vertical and self.imageview.flip_horizontal:
			self.imageview.flip_vertical = self.imageview.flip_horizontal = False
			self.imageview.rotation = (int(self.imageview.rotation) + 180) % 360
		
		self.imageview.refresh_pixbuf()
			
	def rotate(self, data=None, change=0):
		self.imageview.rotation = (int(self.imageview.rotation) - change + 360) % 360
		self.imageview.refresh_pixbuf()
	
	def handle_zoom_change(self, data, change):
		self.change_zoom(change)
		
	def reset_zoom(self, data=None):
		self.imageview.magnification = 1
		self.imageview.refresh_pixbuf()

	def change_interp(self, radioaction, current):
		if self.imageview.magnification:
			interpolation = current.props.value	
			self.imageview.set_interpolation(interpolation)
			
			self.imageview.refresh_pixbuf()
	
	def change_scrollbars(self, radioaction, current):
		placement = current.props.value
		
		if placement == -1:
			self.image_scroller.get_hscrollbar().set_child_visible(False)
			self.image_scroller.get_vscrollbar().set_child_visible(False)
		else:
			self.image_scroller.get_hscrollbar().set_child_visible(True)
			self.image_scroller.get_vscrollbar().set_child_visible(True)
			
			self.image_scroller.set_placement(placement)
			
	def toggle_fullscreen(self, data=None):
		# This simply tries to fullscreen / unfullscreen
		fullscreenaction = self.actions.get_action("fullscreen")
		
		if fullscreenaction.props.active:
			self.fullscreen()
			fullscreenaction.set_stock_id(Gtk.STOCK_LEAVE_FULLSCREEN)
		else:
			self.unfullscreen()
			fullscreenaction.set_stock_id(Gtk.STOCK_FULLSCREEN)
	
	def gofirst(self, data=None):
		first_image = self.image_list.get_first()
		if first_image:
			self.set_image(first_image)
	
	def golast(self, data=None):
		last_image = self.image_list.get_last()
		if last_image:
			self.set_image(last_image)
	
	
	def gonext(self, data=None):
		if self.current_image and self.current_image.next:
			self.set_image(self.current_image.next)
		
	def goprevious(self, data=None):
		if self.current_image and self.current_image.previous:
			self.set_image(self.current_image.previous)
	
	def clear(self, data=None):
		self.image_list.clear()
		self.set_image(None)
		gc.collect()
		
		self.refresh_index()
		self.log(_("Removed all images"))
		
	def remove(self, data=None):
		if self.current_image is not None:
			self.unlist(self.current_image)
	
	def pasted_data(self, data=None):
		some_uris = self.clipboard.wait_for_uris()
			
		if some_uris:
			self.insert_images(self.app.load_uris(some_uris))
				
		some_pixels = self.clipboard.wait_for_image()
		if some_pixels:
			self.insert_images(self.app.load_pixels(some_pixels))
			
	def dragged_data(self, widget, context, x, y, selection, info, timestamp):
		if info == DND_URI_LIST:
			some_uris = selection.get_uris()
			self.insert_images(self.app.load_uris(some_uris))
							
		elif info == DND_IMAGE:
			some_pixels = selection.data.get_pixbuf()
			if some_pixels:
				self.insert_images(self.app.view_pixels(some_pixels))
								
	def file_open(self, widget, data=None):
		# Create image choosing dialog
		image_chooser = Gtk.FileChooserDialog(
		                title = _("Open Image..."),
		                action = Gtk.FileChooserAction.OPEN,
		                buttons = (Gtk.STOCK_CANCEL,
		                           Gtk.ResponseType.CANCEL,
		                           Gtk.STOCK_OPEN,
		                           Gtk.ResponseType.ACCEPT))
			
		image_chooser.set_default_response(Gtk.ResponseType.OK)
		image_chooser.set_select_multiple(True)
		image_chooser.set_transient_for(self)
		
		# Add filters of supported formats from "loading" module
		for fileFilter in loading.Filters:
			image_chooser.add_filter(fileFilter)
			
		try:
			if image_chooser.run() == Gtk.ResponseType.ACCEPT:
				filenames = image_chooser.get_filenames()
				self.insert_images(self.app.load_paths(filenames))
		finally:
			# Destroy the dialog anyway
			image_chooser.destroy()
			
	def imageview_scrolling(self, widget, data=None):
		image = self.imageview.image
		anchor = self.imageview.get_pointer()
		
		if data.direction == Gdk.ScrollDirection.UP:
			self.change_zoom(1, anchor)
		elif data.direction == Gdk.ScrollDirection.DOWN:
			self.change_zoom(-1, anchor)
					
		# Makes the scrolled window not scroll, I hope
		return True
	
	''' Methods after this comment are actually kind of a big deal.
	    Do not rename them. '''
	
	def set_image(self, image):
		''' Sets the image to be displayed in the window.
		    This is quite the important method '''
		if self.current_image == image:
			return
		previous_image = self.current_image
		self.current_image = image
		
		if previous_image is not None:
			# Flags the previous image as unrequired
			self.app.flag_unrequired(self, previous_image)
		
		if self.current_image is None:
			# Current image being none means nothing is displayed.
			self.imageview.source = None
			self.set_title(_("Pynorama"))
			
		else:
			# Flags this new current image as a required image,
			# because we require it. Like, right now.
			self.app.flag_required(self, self.current_image)
			if self.current_image.is_loaded():
				# Since we just required it, it should be loaded
				pixbuf = self.current_image.pixbuf
			else:
				# Case it's not that means the loading has failed terribly.
				pixbuf = self.render_icon(Gtk.STOCK_MISSING_IMAGE,
				                          Gtk.IconSize.DIALOG)
				
			self.imageview.source = pixbuf
			# Sets the window title
			img_name = self.current_image.name
			img_fullname = self.current_image.fullname
			if img_name == img_fullname:
				title_fmt = _("“{name}” - Pynorama")
			else:
				title_fmt = _("“{name}” [“{fullname}”] - Pynorama")
				
			new_title = title_fmt.format(name=img_name, fullname=img_fullname)
			self.set_title(new_title)
			
		self.imageview.refresh_pixbuf()
		self.readjust_view()
		self.refresh_index()
		
	def readjust_view(self):
		# TODO: Make this thing useful
		if self.imageview.pixbuf:
			w = self.imageview.pixbuf.get_width()
			h = self.imageview.pixbuf.get_height()
			alloc = self.imageview.get_allocation()
			vw, vh = alloc.width, alloc.height
			
			x = (w - vw) // 2
			y = 0
			
			self.imageview.get_hadjustment().set_value(x)
			self.imageview.get_vadjustment().set_value(y)
	
	def enlist(self, *images):
		if images:
			self.image_list.add(*images)
			self.app.flag_listed(self, *images)
			if self.autosort:
				self.sort_images()
		
	def unlist(self, *images):
		if images:
			new_current_image = self.current_image
			for removed_image in images:
				if removed_image == new_current_image:
					if len(self.image_list) > 1:
					
						if new_current_image is self.image_list[-1]:
							new_current_image = new_current_image.previous
						else:
							new_current_image = new_current_image.next
					else:
						new_current_image = None
					
				self.image_list.remove(removed_image)
			self.set_image(new_current_image)
			self.app.flag_unlisted(self, *images)
	
	def insert_images(self, images):
		if images:
			self.enlist(*images)
			self.set_image(images[0])
	
	def sort_images(self):
		self.image_list.sort(self.active_ordering)
		self.refresh_index()
	
	def set_navigator(self, navi_factory):
		if self.navigator is not None:
			self.navigator.detach()
		
		self.navi_mode = navi_factory
		if navi_factory:
			self.navigator = navi_factory.create(self.imageview)
		else:
			self.navigator = None
			
	def change_zoom(self, power, anchor=None):
		zoom_effect = self.app.zoom_effect
		if zoom_effect and power:
			self.imageview.magnification *= zoom_effect ** power
			self.imageview.refresh_pixbuf()
			
if __name__ == "__main__":
	# Run the program
	app = ImageViewer()
	app.run(sys.argv)
