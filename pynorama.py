#!/usr/bin/python3
# coding=utf-8
 
''' Pynorama is an image viewer application. '''

import gc, math, os, sys
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib
import cairo
from gettext import gettext as _
import organization, navigation, loading, preferences, viewing

resource_dir = os.path.dirname(__file__)
DND_URI_LIST, DND_IMAGE = range(2)

class ImageViewer(Gtk.Application):
	def __init__(self):
		Gtk.Application.__init__(self)
		self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)
		
		# Default prefs stuff
		self.zoom_effect = 2
		self.spin_effect = 90
		self.default_position = .5, .5
		self.navi_factory = navigation.DragNavi
		self.loaded_imagery = set()
		
	def do_startup(self):
		Gtk.Application.do_startup(self)
		preferences.load_into_app(self)
					
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
			fillscreen = preferences.Settings.get_boolean("start-fullscreen")
			a_window.set_fullscreen(fillscreen)
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
		recent_manager = Gtk.RecentManager.get_default()
		for a_file in files:
			an_uri = a_file.get_uri()
			recent_manager.add_item(an_uri)
						
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
			try:
				if loading.IsAlbumFile(a_file):
					some_images = loading.GetAlbumImages(a_file)
					loaded_images.extend(some_images)
				else:
					an_image = loading.ImageGFileNode(a_file)
					loaded_images.append(an_image)
			except:
				self.tell_exception()
								
		return loaded_images
		
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
		
		gc.collect()
	    
	def flag_unrequired(self, window, *images):
		''' Marks images as not being used right now,
		    that means it can be unloaded anytime '''
		    
		# TODO: Add preloading support
		for an_image in images:
			an_image.unload()
			self.loaded_imagery.discard(an_image)
		
		gc.collect()
		
	def flag_required(self, window, *images):
		''' Marks images as required by a window,
		    that means we need it loaded.
		    Like, right now. '''
		    
		loading_fmt = _("Loading “{filename}”")
		loaded_fmt = _("“{filename}” is loaded")
		for an_image in images:
			if not an_image.is_loaded():
				filename = an_image.fullname
				try:
					loading_msg = loading_fmt.format(filename=filename)
					self.tell_info(loading_msg, window)
					an_image.load()
					self.loaded_imagery.add(an_image)
				except:
					self.tell_exception(window)
				else:
					loaded_msg = loaded_fmt.format(filename=filename)
					self.tell_info(loaded_msg, window)
	
	''' These methods tell things
	    And stuff '''	
	def tell_info(self, message, window=None):
		print(message)
		if window:
			window.statusbar.push(0, message)
	
	def tell_exception(self, window=None):
		info = sys.exc_info()
		print(info[1])
		if window:
			window.statusbar.push(0, _("Error: %s" % info[1]))
		
	def set_navi_factory(self, navi_factory):
		self.navi_factory = navi_factory
		for a_window in self.get_windows():
			if a_window.navi_mode != navi_factory:
				a_window.set_navigator(navi_factory)
	
class ViewerWindow(Gtk.ApplicationWindow):
	def __init__(self, app):
		Gtk.ApplicationWindow.__init__(self,
		                               title=_("Pynorama"),
		                               application=app)
		self.app = app
		self.set_default_size(600, 600)
		# Setup variables
		self.current_image = None
		self.current_frame = viewing.PictureFrame()
		# Animation stuff
		self.anim_handle = None
		self.anim_iter = None
		# Auto zoom stuff
		self.auto_zoom_magnify = False
		self.auto_zoom_minify = True
		self.auto_zoom_mode = 0
		self.auto_zoom_enabled = False
		# If the user changes the zoom set by auto_zoom, 
		# then auto_zoom isn't called after rotating or resizing
		# the imageview
		self.auto_zoom_zoom_modified = False
		self.autosort = True
		self.reverse_sort = False
		self.navigator = None
		self.navi_mode = None
		self.ordering_modes = [
			organization.Ordering.ByName,
			organization.Ordering.ByCharacters,
			organization.Ordering.ByFileDate,
			organization.Ordering.ByFileSize,
			organization.Ordering.ByImageSize,
			organization.Ordering.ByImageWidth,
			organization.Ordering.ByImageHeight
		]
		self.active_ordering = organization.Ordering.ByName
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
		# Make the toolbar look primary
		toolbar_style = self.toolbar.get_style_context()
		toolbar_style.add_class(Gtk.STYLE_CLASS_PRIMARY_TOOLBAR)
		vlayout.pack_start(self.menubar, False, False, 0)
		vlayout.pack_start(self.toolbar, False, False, 0)
		self.menubar.show_all()
		self.toolbar.show_all()
		
		# Create a scrollwindow and a imagev--, galleryview,
		# and then set the VIEW style to the scrolled window,
		# NOT the galleryview, the scrolled window.
		self.image_scroller = Gtk.ScrolledWindow()
		scroller_style = self.image_scroller.get_style_context()
		scroller_style.add_class(Gtk.STYLE_CLASS_VIEW)
		# TODO: There ought to be a better way
		# to drop the default key behaviour
		self.image_scroller.connect("key-press-event", lambda x, y: True)
		self.image_scroller.connect("key-release-event", lambda x, y: True)
		self.image_scroller.connect("scroll-event", lambda x, y: True)
		self.imageview = viewing.GalleryView()
		self.imageview.add_frame(self.current_frame)
		# Setup a bunch of reactions to all sorts of things
		self.imageview.connect("notify::magnification", self.magnification_changed)
		self.imageview.connect("notify::rotation", self.reapply_auto_zoom)
		self.imageview.connect("size-allocate", self.reapply_auto_zoom)
		self.imageview.connect("notify::magnification", self.view_changed)
		self.imageview.connect("notify::rotation", self.view_changed)
		self.imageview.connect("notify::flip", self.view_changed)
		
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
		self.refresh_interp()
		
		# DnD setup	
		self.imageview.drag_dest_set(Gtk.DestDefaults.ALL,
		                             [], Gdk.DragAction.COPY)
		
		target_list = Gtk.TargetList.new([])
		target_list.add_image_targets(DND_IMAGE, False)
		target_list.add_uri_targets(DND_URI_LIST)
		
		self.imageview.drag_dest_set_target_list(target_list)
		self.imageview.add_events(Gdk.EventMask.SCROLL_MASK)
		self.imageview.connect("scroll-event", self.imageview_scrolling)
		self.imageview.connect("drag-data-received", self.dragged_data)
		
		preferences.load_into_window(self)
		
	def setup_actions(self):
		self.manager = Gtk.UIManager()
		self.accelerators = self.manager.get_accel_group()
		self.add_accel_group(self.accelerators)
		self.actions = Gtk.ActionGroup("pynorama")
		self.manager.insert_action_group(self.actions)
		
		action_params = [
		# File Menu
		("file", _("_File"), None, None),
			("open", _("_Open..."), _("Open an image in the viewer"), Gtk.STOCK_OPEN),
			("paste", _("_Paste"), _("Show an image from the clipboard"),
			 Gtk.STOCK_PASTE),
			# Ordering submenu
			("ordering", _("Or_dering"), None, None),
			    ("sort", _("_Sort Images"),
			     _("Sort the images currently loaded"), None),
			    ("auto-sort", _("Sort _Automatically"),
			     _("Sort images as they are added"), None),
			     ("reverse-sort", _("_Reverse Order"),
			      _("Order images in reverse"), None),
				("name-sort", _("By _Name"), _("Order images by name"),
				 None),
				("char-sort", _("By _Characters"),
				 _("Order images by name comparing only the characters"), None),
				("file-date-sort", _("By _Modification Date"),
				 _("Recently modified images appear first"), None),
				("file-size-sort", _("By _File Size"),
				 _("Smaller files appear first"), None),
				("img-size-sort", _("By Image Si_ze"),
				 _("Smaller images appear first"), None),
				("img-width-sort", _("By Image _Width"),
				 _("Narrower images appear first"), None),
				("img-height-sort", _("By Image _Height"),
				 _("Shorter images appear first"), None),
			("remove", _("_Remove"), _("Remove the image from the viewer"),
			 Gtk.STOCK_CLOSE),
			("clear", _("R_emove All"), _("Remove all images from the viewer"),
			 Gtk.STOCK_CLEAR),
			("quit", _("_Quit"), _("Exit the program"), Gtk.STOCK_QUIT),
		# Go menu
		("go", _("_Go"), None, None),
			("previous", _("P_revious Image"), _("Open the previous image"),
			 Gtk.STOCK_GO_BACK),
			("next", _("Nex_t Image"), _("Open the next image"),
			 Gtk.STOCK_GO_FORWARD),
			("first", _("Fir_st Image"), _("Open the first image"),
			 Gtk.STOCK_GOTO_FIRST),
			("last", _("Las_t Image"), _("Open the last image"),
			 Gtk.STOCK_GOTO_LAST),
		# View menu
		("view", _("_View"), None, None),
			("in-zoom", _("Zoom _In"), _("Makes the image look larger"),
			 Gtk.STOCK_ZOOM_IN),
			("out-zoom", _("Zoom _Out"), _("Makes the image look smaller"),
			 Gtk.STOCK_ZOOM_OUT),
			("no-zoom", _("No _Zoom"), _("Shows the image at it's normal size"),
			 Gtk.STOCK_ZOOM_100),
			# Auto-zoom submenu
			("auto-zoom", _("_Automatic Zoom"), None, None),
				("auto-zoom-enable", _("Enable _Auto Zoom"), None, None),
				("auto-fit", _("Fi_t Image"), None, None),
				("auto-fill", _("Fi_ll Window"), None, None),
				("auto-match-width", _("Match _Width"), None, None),
				("auto-match-height", _("Match _Height"), None, None),
				("auto-minify", _("Mi_nify Large Images"), None, None),
				("auto-magnify", _("Ma_gnify Small Images"), None, None),
			# Transform submenu
			("transform", _("_Transform"), None, None),
				("cw-rotate", _("_Rotate Clockwise"),
				 _("Turns the image top side to the right side"), None),
				("ccw-rotate", _("Rotat_e Counter Clockwise"),
				 _("Turns the image top side to the left side"), None),
				("h-flip", _("Flip _Horizontally"), 
				 _("Inverts the left and right sides of the image"), None),
				("v-flip", _("Flip _Vertically"),
				 _("Inverts the top and bottom sides of the image"), None),
			# Interpolation submenu
			("interpolation", _("Inter_polation"), None, None),
				("nearest-interp", _("_Nearest Neighbour Filter"), _(""), None),
				("bilinear-interp", _("_Bilinear Filter"), _(""), None),
				("fast-interp", _("Fa_ster Fil_ter"), _(""), None),
				("good-interp", _("B_etter Filt_er"), _(""), None),
				("best-interp", _("St_ronger Filte_r"), _(""), None),
			# Interface submenu
			("interface", _("_Interface"), None, None),
				("view-toolbar", _("T_oolbar"), _("Display a toolbar with the tools"), None),
				("view-statusbar", _("Stat_usbar"), _("Display a statusbar with the status"), None),
				("top-scrollbar", _("_Top Scroll Bar"),
				 _("Display the horizontal scrollbar at the top side"), None),
				("bottom-scrollbar", _("_Bottom Scroll Bar"),
				 _("Display the horizontal scrollbar at the bottom side"), None),
				("left-scrollbar", _("Le_ft Scroll Bar"),
				 _("Display the vertical scrollbar at the left side"), None),
				("right-scrollbar", _("Rig_ht Scroll Bar"),
				 _("Display the vertical scrollbar at the right side"), None),
			("preferences", _("_Preferences..."), _("Configure Pynorama"),
			 Gtk.STOCK_PREFERENCES),
			("fullscreen", _("_Fullscreen"), _("Fill the entire screen"),
			 Gtk.STOCK_FULLSCREEN),
		]
		
		signaling_params = {
			"open" : (self.file_open,),
			"paste" : (self.pasted_data,),
			"sort" : (lambda data: self.sort_images(),),
			"auto-sort" : (self.toggle_autosort,),
			"reverse-sort" : (self.toggle_reverse_sort,),
			"name-sort" : (self.change_ordering,), # For group
			"remove" : (self.handle_remove,),
			"clear" : (self.handle_clear,),
			"quit" : (lambda data: self.destroy(),),
			"previous" : (self.go_previous,),
			"next" : (self.go_next,),
			"first" : (self.go_first,),
			"last" : (self.go_last,),
			"in-zoom" : (self.handle_zoom_change, 1),
			"out-zoom" : (self.handle_zoom_change, -1),
			"no-zoom" : (self.reset_zoom,),
			"auto-zoom-enable" : (self.change_auto_zoom,),
			"auto-fit" : (self.change_auto_zoom,),
			"auto-magnify" : (self.change_auto_zoom,),
			"auto-minify" : (self.change_auto_zoom,),
			"cw-rotate" : (self.handle_rotate, 1),
			"ccw-rotate" : (self.handle_rotate, -1),
			"h-flip" : (self.handle_flip, False),
			"v-flip" : (self.handle_flip, True),
			"nearest-interp" : (self.change_interp,), # For group
			"view-toolbar" : (self.change_interface,),
			"view-statusbar" : (self.change_interface,),
			"top-scrollbar" : (self.change_scrollbars,),
			"bottom-scrollbar" : (self.change_scrollbars,),
			"right-scrollbar" : (self.change_scrollbars,),
			"left-scrollbar" : (self.change_scrollbars,),
			"preferences" : (self.show_preferences,),
			"fullscreen" : (self.toggle_fullscreen,)
		}
		
		sort_group, interp_group, zoom_mode_group = [], [], []
		toggleable_actions = {
			"auto-sort" : None,
			"reverse-sort" : None,
			"manual-zoom" : None,
			"auto-zoom-enable" : None,
			"auto-fit" : (3, zoom_mode_group),
			"auto-fill" : (0, zoom_mode_group),
			"auto-match-width" : (1, zoom_mode_group),
			"auto-match-height" : (2, zoom_mode_group),
			"auto-minify" : None,
			"auto-magnify" : None,
			"fullscreen" : None,
			"name-sort" : (0, sort_group),
			"char-sort" : (1, sort_group),
			"file-date-sort" : (2, sort_group),
			"file-size-sort" : (3, sort_group),
			"img-size-sort" : (4, sort_group),
			"img-width-sort" : (5, sort_group),
			"img-height-sort" : (6, sort_group),
			"nearest-interp" : (cairo.FILTER_NEAREST, interp_group),
			"bilinear-interp" : (cairo.FILTER_BILINEAR, interp_group),
			"fast-interp" : (cairo.FILTER_FAST, interp_group),
			"good-interp" : (cairo.FILTER_GOOD, interp_group),
			"best-interp" : (cairo.FILTER_BEST, interp_group),
			"view-statusbar" : None,
			"view-toolbar" :None,
			# The values seem inverted because... reasons
			"top-scrollbar" : None,
			"bottom-scrollbar" : None,
			"right-scrollbar" : None,
			"left-scrollbar" : None
		}
		
		accel_actions = {
			"open" : None,
			"paste" : None,
			"remove" : "Delete",
			"clear" : "<ctrl>Delete",
			"quit" : None,
			"next" : "Page_Down",
			"previous" : "Page_Up",
			"first" : "Home",
			"last" : "End",
			"no-zoom" : "KP_0",
			"in-zoom" : "KP_Add",
			"out-zoom" : "KP_Subtract",
			"auto-zoom-enable" : "KP_Multiply",
			"cw-rotate" : "R",
			"ccw-rotate" : "<ctrl>R",
			"h-flip" : "F",
			"v-flip" : "<ctrl>F",
			"fullscreen" : "F4",
		}
		
		for name, label, tip, stock in action_params:
			some_signal_params = signaling_params.get(name, None)
			if name in toggleable_actions:
				# Toggleable actions :D
				group_data = toggleable_actions[name]
				if group_data is None:
					# No group data = ToggleAction
					signal_name = "toggled"
					an_action = Gtk.ToggleAction(name, label, tip, stock)
				else:
					# Group data = RadioAction
					signal_name = "changed"
					radio_value, group_list = group_data
					an_action = Gtk.RadioAction(name, label, tip, stock,
					                            radio_value)
					# Join the group of last radioaction in the list
					if group_list:
						an_action.join_group(group_list[-1])
					group_list.append(an_action)
			else:
				# Non-rare kind of action
				signal_name = "activate"
				an_action = Gtk.Action(name, label, tip, stock)
			
			# Set signal
			if some_signal_params:
				an_action.connect(signal_name, *some_signal_params)
			
			# Add to action group
			try:
				an_accel = accel_actions[name]
			except KeyError:
				self.actions.add_action(an_action)
			else:
				self.actions.add_action_with_accel(an_action, an_accel)
				
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
		
	def toggle_reverse_sort(self, data=None):
		reverse_state = self.actions.get_action("reverse-sort").get_active()
		if self.reverse_sort != reverse_state:
			self.reverse_sort = reverse_state
			self.image_list.images.reverse()
			self.refresh_index()
		
	def toggle_autosort(self, data=None):
		self.autosort = self.actions.get_action("auto-sort").get_active()
	
	def magnification_changed(self, widget, data=None):
		self.refresh_interp()
		self.auto_zoom_zoom_modified = True
		
	def view_changed(self, widget, data):
		self.refresh_transform()
	
	def reapply_auto_zoom(self, *data):
		if self.auto_zoom_enabled and not self.auto_zoom_zoom_modified:
			self.auto_zoom()
			
	def refresh_interp(self):	
		magnification = self.imageview.get_magnification()
		interp = self.imageview.get_interpolation_for_scale(magnification)
		interp_menu_action = self.actions.get_action("interpolation")
		interp_menu_action.set_sensitive(interp is not None)
		
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
		
		sensible_list = [
			("remove", can_remove),
			("clear", len(images) > 0),
			("next", can_next),
			("previous", can_previous),
			("first", can_goto_extremity),
			("last", can_goto_extremity),
		]
		
		for action_name, sensitivity in sensible_list:
			self.actions.get_action(action_name).set_sensitive(sensitivity)
		
	def refresh_transform(self):
		if self.current_image:
			if self.current_image.is_loaded():
				metadata = self.current_image.metadata
				# The width and height are from the source
				pic = "{width}x{height}".format(width=metadata.width,
				                                height=metadata.height)
			else:
				# This just may happen
				pic = _("Error")
			
			# Cache magnification because it is kind of a long variable
			mag = self.imageview.get_magnification()
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
			
			
			# Cachin' variables
			rot = self.imageview.get_rotation()
			hflip, vflip = self.imageview.get_flip()
			if hflip or vflip:
				''' If the view is flipped in either direction apply this
				    intricate looking math stuff to rotation. Normally, there
				    would be another expression if both are true, but in that
				    is handled beforehand by rotating the view by 180° '''
				    
				rot = (rot + (45 - ((rot + 45) % 180)) * 2) % 360
				
				if hflip:
					mirror = " ↔"
				else:
					mirror = " ↕"
			else:
				mirror = ""
				
			# Create angle string for label
			if rot:
				angle_fmt = " " + _("{angle}°")
				angle = angle_fmt.format(angle=int(rot))
			else:
				angle = ""
				
			''' Sets the transform label to Width x Height or "Error",
			    zoom, rotation and mirroring combined '''
			transform = (pic, zoom, angle, mirror)
			self.transform_label.set_text("%s%s%s%s" % transform)
		else:
			''' Sets the transform label to nothing.
			    Because there is nothing to transform. '''
			self.transform_label.set_text(_("Nothing"))
							
	def handle_flip(self, data=None, vertical=False):
		# Horizontal mirroring depends on the rotation of the image
		hflip, vflip = self.imageview.get_flip()
		if vertical:
			vflip = not vflip
		else:
			hflip = not hflip
		
		# ih8triGNOMEtricks
		rot = self.imageview.get_rotation()
		angle_change = (45 - ((rot + 45) % 180)) * 2
		
		# If the image if flipped both horizontally and vertically
		# Then it is rotated 180 degrees
		if vflip and hflip:
			vflip = hflip = False
			angle_change += 180
		
		if angle_change:
			self.imageview.set_rotation((rot + angle_change) % 360)
			
		self.imageview.set_flip((hflip, vflip))
			
	def handle_rotate(self, data=None, power=0):
		change = self.app.spin_effect * power
		if change < 0:
			change += (change // 360) * -360
		
		altered_rotation = self.imageview.get_rotation() + change
		self.imageview.set_rotation(altered_rotation % 360)
	
	def handle_zoom_change(self, data, change):
		self.change_zoom(change)
		
	def reset_zoom(self, data=None):
		self.imageview.set_magnification(1)
	
	def auto_zoom(self):
		''' Zooms automatically!
			For future reference on auto zoom mode:
			  "fit" = magnify based on the largest side
			  "fill" = magnify based on the smallest side
			  "width" = magnify based on width
			  "height" = magnify based on height '''
			  
		if self.auto_zoom_magnify or self.auto_zoom_minify:
			side_name = ["smallest", "width", "height", "largest"][self.auto_zoom_mode]
			scale = self.imageview.compute_side_scale(side_name)
		
			if scale > 1 and self.auto_zoom_magnify or \
			   scale < 1 and self.auto_zoom_minify:
				self.imageview.set_magnification(scale)
				self.auto_zoom_zoom_modified = False
			else:
				self.imageview.set_magnification(1)
					
	def change_auto_zoom(self, *data):
		mode = self.actions.get_action("auto-fit").get_current_value()
		magnify = self.actions.get_action("auto-magnify").get_active()
		minify = self.actions.get_action("auto-minify").get_active()
		enabled = self.actions.get_action("auto-zoom-enable").get_active()
		
		self.auto_zoom_magnify = magnify
		self.auto_zoom_minify = minify
		self.auto_zoom_mode = mode
		self.auto_zoom_enabled = enabled
		if self.auto_zoom_enabled:
			self.auto_zoom()
	
	def change_interp(self, radioaction, current):
		if self.imageview.get_magnification():
			interpolation = current.props.value
			magnification = self.imageview.get_magnification()
			self.imageview.set_interpolation_for_scale(magnification,
			                                           interpolation)
			
	def change_interface(self, *data):
		show_tools = self.actions.get_action("view-toolbar").get_active()
		show_status = self.actions.get_action("view-statusbar").get_active()
		self.toolbar.set_visible(show_tools)		
		self.statusbar.set_visible(show_status)		
	
	def change_scrollbars(self, *data):
		get_active = lambda name: self.actions.get_action(name).get_active()
		current_placement = self.image_scroller.get_placement()
		
		top_active = get_active("top-scrollbar")
		bottom_active = get_active("bottom-scrollbar")
		if top_active and bottom_active:
			if current_placement == Gtk.CornerType.TOP_LEFT or \
			   current_placement == Gtk.CornerType.TOP_RIGHT:
				self.actions.get_action("bottom-scrollbar").set_active(False)
			else:
				self.actions.get_action("top-scrollbar").set_active(False)
			return
			
		elif top_active or bottom_active:
			hpolicy = Gtk.PolicyType.AUTOMATIC
		else:
			hpolicy = Gtk.PolicyType.NEVER
		
		left_active = get_active("left-scrollbar")
		right_active = get_active("right-scrollbar")
		if left_active and right_active:
			if current_placement == Gtk.CornerType.TOP_LEFT or \
			   current_placement == Gtk.CornerType.BOTTOM_LEFT:
				self.actions.get_action("right-scrollbar").set_active(False)
			else:
				self.actions.get_action("left-scrollbar").set_active(False)
			return
			
		elif left_active or right_active:
			vpolicy = Gtk.PolicyType.AUTOMATIC
		else:
			vpolicy = Gtk.PolicyType.NEVER
						
		if top_active:
			placement = Gtk.CornerType.BOTTOM_RIGHT if left_active \
			            else Gtk.CornerType.BOTTOM_LEFT
		else:
			placement = Gtk.CornerType.TOP_RIGHT if left_active \
			            else Gtk.CornerType.TOP_LEFT
		        
		self.image_scroller.set_policy(hpolicy, vpolicy)
		self.image_scroller.set_placement(placement)
			
	def toggle_fullscreen(self, data=None):
		# This simply tries to fullscreen / unfullscreen
		fullscreenaction = self.actions.get_action("fullscreen")
		
		if fullscreenaction.get_active():
			self.fullscreen()
		else:
			self.unfullscreen()
	
	def go_first(self, data=None):
		first_image = self.image_list.get_first()
		if first_image:
			self.set_image(first_image)
	
	def go_last(self, data=None):
		last_image = self.image_list.get_last()
		if last_image:
			self.set_image(last_image)
	
	
	def go_next(self, data=None):
		if self.current_image and self.current_image.next:
			self.set_image(self.current_image.next)
		
	def go_previous(self, data=None):
		if self.current_image and self.current_image.previous:
			self.set_image(self.current_image.previous)
	
	def handle_clear(self, data=None):
		self.unlist(*self.image_list.images)
		
	def handle_remove(self, data=None):
		if self.current_image is not None:
			self.unlist(self.current_image)
	
	def pasted_data(self, data=None):
		some_uris = self.clipboard.wait_for_uris()
			
		if some_uris:
			images = self.app.load_uris(some_uris)
			self.insert_images(images)
				
		some_pixels = self.clipboard.wait_for_image()
		if some_pixels:
			self.insert_images(self.app.load_pixels(some_pixels))
			
	def dragged_data(self, widget, context, x, y, selection, info, timestamp):
		if info == DND_URI_LIST:
			some_uris = selection.get_uris()
			images = self.app.load_uris(some_uris)
			self.insert_images(images)
							
		elif info == DND_IMAGE:
			some_pixels = selection.data.get_pixbuf()
			if some_pixels:
				self.insert_images(self.app.view_pixels(some_pixels))
								
	def file_open(self, widget, data=None):
		# Create image choosing dialog
		image_chooser = Gtk.FileChooserDialog(_("Open Image..."), self,
		                                      Gtk.FileChooserAction.OPEN,
		                                      (Gtk.STOCK_CANCEL,
		                                       Gtk.ResponseType.CANCEL,
		                                       Gtk.STOCK_ADD,
		                                       Gtk.ResponseType.APPLY,
		                                       Gtk.STOCK_OPEN,
		                                       Gtk.ResponseType.OK))
			
		image_chooser.set_default_response(Gtk.ResponseType.OK)
		image_chooser.set_select_multiple(True)
		
		# Add filters of supported formats from "loading" module
		for fileFilter in loading.Filters:
			image_chooser.add_filter(fileFilter)
			
		try:
			response = image_chooser.run()
			if response == Gtk.ResponseType.OK:
				self.unlist(*self.image_list.images)
				
			if response in [Gtk.ResponseType.APPLY, Gtk.ResponseType.OK]:
				filenames = image_chooser.get_filenames()
				images = self.app.load_paths(filenames)
				self.insert_images(images)
				
		finally:
			# Destroy the dialog anyway
			image_chooser.destroy()
			
	def imageview_scrolling(self, widget, data=None):
		anchor = self.imageview.get_pointer()
		
		if data.direction == Gdk.ScrollDirection.UP:
			self.change_zoom(1, anchor)
			
		elif data.direction == Gdk.ScrollDirection.DOWN:
			self.change_zoom(-1, anchor)
					
		# Makes the scrolled window not scroll, I hope
		return True
	
	''' Methods after this comment are actually kind of a big deal.
	    Do not rename them. '''
	
	def do_destroy(self, *data):
		try:
			preferences.set_from_window(self)
		except:
			self.app.tell_exception()
		finally:
			return Gtk.Window.do_destroy(self)
	
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
			if self.anim_handle is not None:
				GLib.source_remove(self.anim_handle)
				self.anim_handle = None
				self.anim_iter = None
				
		if self.current_image is None:
			# Current image being none means nothing is displayed.
			self.current_frame.set_surface(None)
			self.set_title(_("Pynorama"))
			
		else:
			# Flags this new current image as a required image,
			# because we require it. Like, right now.
			self.app.flag_required(self, self.current_image)
			if self.current_image.is_loaded():
				# Since we just required it, it should be loaded
				if self.current_image.animation:
					animation = self.current_image.animation
					self.anim_iter = animation.get_iter(None)
					delay = self.anim_iter.get_delay_time()
					if delay != -1:
						self.anim_handle = GLib.timeout_add(
						                        delay,
						                        self.refresh_animation)
						                        
					
					pixbuf = self.anim_iter.get_pixbuf()
					
				else:
					pixbuf = self.current_image.pixbuf
				
			else:
				# Case it's not that means the loading has failed terribly.
				pixbuf = self.render_icon(Gtk.STOCK_MISSING_IMAGE,
				                          Gtk.IconSize.DIALOG)
			
			self.current_frame.set_pixbuf(pixbuf)
			if self.auto_zoom_enabled:
				self.auto_zoom()
			self.imageview.adjust_to_boundaries(*self.app.default_position)
			# Sets the window title
			img_name = self.current_image.name
			img_fullname = self.current_image.fullname
			if img_name == img_fullname:
				title_fmt = _("“{name}” - Pynorama")
			else:
				title_fmt = _("“{name}” [“{fullname}”] - Pynorama")
				
			new_title = title_fmt.format(name=img_name, fullname=img_fullname)
			self.set_title(new_title)
			
		self.refresh_index()
		self.refresh_transform()
		
	def refresh_animation(self):
		self.anim_iter.advance(None)
		delay = self.anim_iter.get_delay_time()
		if delay != -1:
			self.anim_handle = GLib.timeout_add(
			                        delay,
			                        self.refresh_animation)
			                        
		
		pixbuf = self.anim_iter.get_pixbuf()
		self.current_frame.set_pixbuf(pixbuf)
		
		return False
		
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
			self.imageview.props.magnification *= zoom_effect ** power
	
	def get_enable_auto_sort(self):
		return self.actions.get_action("auto-sort").get_active()
	def set_enable_auto_sort(self, value):
		self.actions.get_action("auto-sort").set_active(value)
		
	def get_reverse_sort(self):
		return self.actions.get_action("reverse-sort").get_active()
	def set_reverse_sort(self, value):
		self.actions.get_action("reverse-sort").set_active(value)
	
	def get_auto_zoom(self):
		enabled = self.actions.get_action("auto-zoom-enable").get_active()
		minify = self.actions.get_action("auto-minify").get_active()
		magnify = self.actions.get_action("auto-magnify").get_active()
		return enabled, minify, magnify
		
	def set_auto_zoom(self, enabled, minify, magnify):
		self.actions.get_action("auto-minify").set_active(minify)
		self.actions.get_action("auto-magnify").set_active(magnify)
		self.actions.get_action("auto-zoom-enable").set_active(enabled)
		
	def get_auto_zoom_mode(self):
		return self.actions.get_action("auto-fit").get_current_value()
	def set_auto_zoom_mode(self, mode):
		self.actions.get_action("auto-fit").set_current_value(mode)
	
	def get_sort_mode(self):
		return self.actions.get_action("name-sort").get_current_value()
	def set_sort_mode(self, value):
		self.actions.get_action("name-sort").set_current_value(value)
	
	def get_interpolation(self):
		return (self.imageview.get_minify_interpolation(),
		        self.imageview.get_magnify_interpolation())
	def set_interpolation(self, minify, magnify):
		self.imageview.set_minify_interpolation(minify)
		self.imageview.set_magnify_interpolation(magnify)
		self.refresh_interp()
	
	def get_toolbar_visible(self):
		return self.toolbar.get_visible()
	def set_toolbar_visible(self, value):
		self.actions.get_action("view-toolbar").set_active(value)
		self.toolbar.set_visible(value)
		
	def get_statusbar_visible(self):
		return self.statusbar.get_visible()
	def set_statusbar_visible(self, value):
		self.actions.get_action("view-statusbar").set_active(value)
		self.statusbar.set_visible(value)
	
	def get_hscrollbar_placement(self):
		top = self.actions.get_action("top-scrollbar").get_active()
		bottom = self.actions.get_action("bottom-scrollbar").get_active()
		return 2 if bottom else 1 if top else 0
	
	def set_hscrollbar_placement(self, value):
		if value == 2:
			self.actions.get_action("bottom-scrollbar").set_active(True)
		elif value == 1:
			self.actions.get_action("top-scrollbar").set_active(True)
		else:
			self.actions.get_action("top-scrollbar").set_active(False)
			self.actions.get_action("bottom-scrollbar").set_active(False)
		
		self.change_scrollbars()
	
	def get_vscrollbar_placement(self):
		left = self.actions.get_action("left-scrollbar").get_active()
		right = self.actions.get_action("right-scrollbar").get_active()
		return 2 if right else 1 if left else 0
	
	def set_vscrollbar_placement(self, value):
		if value == 2:
			self.actions.get_action("right-scrollbar").set_active(True)
		elif value == 1:
			self.actions.get_action("left-scrollbar").set_active(True)
		else:
			self.actions.get_action("left-scrollbar").set_active(False)
			self.actions.get_action("right-scrollbar").set_active(False)
			
		self.change_scrollbars()
		
	def get_fullscreen(self):
		return self.actions.get_action("fullscreen").get_active()
		
	def set_fullscreen(self, value):
		self.actions.get_action("fullscreen").set_active(value)
	
if __name__ == "__main__":
	# Run the program
	app = ImageViewer()
	app.run(sys.argv)
