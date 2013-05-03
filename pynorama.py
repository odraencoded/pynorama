#!/usr/bin/python3
# coding=utf-8
 
''' pynorama.py is the main module of an image viewer application. '''

''' ...and this file is part of Pynorama.
    
    Pynorama is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    Pynorama is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with Pynorama. If not, see <http://www.gnu.org/licenses/>. '''

import gc, math, random, os, sys
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib
import cairo
from gettext import gettext as _
import organization, navigation, loading, preferences, viewing
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
		for navi in navigation.NaviList:
			navi.load_settings()
			
		Gtk.Window.set_default_icon_name("pynorama")
		
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
			
	def show_about_dialog(self, *data):
		dialog = Gtk.AboutDialog(parent=self.get_window(),
		                         program_name="pynorama",
		                         version="0.1",
		                         comments="pynorama is an image viewer",
		                         logo_icon_name="pynorama",
		                         license_type=Gtk.License.GPL_3_0)
		dialog.set_copyright("Copyrght © 2013 Leonardo Augusto Pereira")
		dialog.connect("response", lambda a, b: a.destroy())
		dialog.run()
		
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
		
		self.manager.add_ui_from_string(ViewerWindow.ui_description)
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
			    ("sort-auto", _("Sort _Automatically"),
			     _("Sort images as they are added"), None),
			     ("sort-reverse", _("_Reverse Order"),
			      _("Order images in reverse"), None),
				("sort-name", _("By _Name"), _("Order images by name"),
				 None),
				("sort-char", _("By _Characters"),
				 _("Order images by name comparing only the characters"), None),
				("sort-file-date", _("By _Modification Date"),
				 _("Recently modified images appear first"), None),
				("sort-file-size", _("By _File Size"),
				 _("Smaller files appear first"), None),
				("sort-img-size", _("By Image Si_ze"),
				 _("Smaller images appear first"), None),
				("sort-img-width", _("By Image _Width"),
				 _("Narrower images appear first"), None),
				("sort-img-height", _("By Image _Height"),
				 _("Shorter images appear first"), None),
			("remove", _("_Remove"), _("Remove the image from the viewer"),
			 Gtk.STOCK_CLOSE),
			("clear", _("R_emove All"), _("Remove all images from the viewer"),
			 Gtk.STOCK_CLEAR),
			("quit", _("_Quit"), _("Exit the program"), Gtk.STOCK_QUIT),
		# Go menu
		("go", _("_Go"), None, None),
			("go-previous", _("P_revious Image"), _("Open the previous image"),
			 Gtk.STOCK_GO_BACK),
			("go-next", _("Nex_t Image"), _("Open the next image"),
			 Gtk.STOCK_GO_FORWARD),
			("go-first", _("Fir_st Image"), _("Open the first image"),
			 Gtk.STOCK_GOTO_FIRST),
			("go-last", _("L_ast Image"), _("Open the last image"),
			 Gtk.STOCK_GOTO_LAST),
 			("go-random", _("A_ny Image"), _("Open a random image"),
			 Gtk.STOCK_GOTO_LAST),
		# View menu
		("view", _("_View"), None, None),
			("zoom-in", _("Zoom _In"), _("Makes the image look larger"),
			 Gtk.STOCK_ZOOM_IN),
			("zoom-out", _("Zoom _Out"), _("Makes the image look smaller"),
			 Gtk.STOCK_ZOOM_OUT),
			("zoom-none", _("No _Zoom"), _("Shows the image at it's normal size"),
			 Gtk.STOCK_ZOOM_100),
			# Auto-zoom submenu
			("auto-zoom", _("_Automatic Zoom"), None, None),
				("auto-zoom-enable", _("Enable _Auto Zoom"), None, None),
				("auto-zoom-fit", _("Fi_t Image"), None, None),
				("auto-zoom-fill", _("Fi_ll Window"), None, None),
				("auto-zoom-match-width", _("Match _Width"), None, None),
				("auto-zoom-match-height", _("Match _Height"), None, None),
				("auto-zoom-minify", _("Mi_nify Large Images"), None, None),
				("auto-zoom-magnify", _("Ma_gnify Small Images"), None, None),
			# Transform submenu
			("transform", _("_Transform"), None, None),
				("rotate-cw", _("_Rotate Clockwise"),
				 _("Turns the image top side to the right side"), None),
				("rotate-ccw", _("Rotat_e Counter Clockwise"),
				 _("Turns the image top side to the left side"), None),
				("flip-h", _("Flip _Horizontally"), 
				 _("Inverts the left and right sides of the image"), None),
				("flip-v", _("Flip _Vertically"),
				 _("Inverts the top and bottom sides of the image"), None),
			# Interpolation submenu
			("interpolation", _("Inter_polation"), None, None),
				("interp-nearest", _("_Nearest Neighbour Filter"), _(""), None),
				("interp-bilinear", _("_Bilinear Filter"), _(""), None),
				("interp-fast", _("Fa_ster Fil_ter"), _(""), None),
				("interp-good", _("B_etter Filt_er"), _(""), None),
				("interp-best", _("St_ronger Filte_r"), _(""), None),
			# Interface submenu
			("interface", _("_Interface"), None, None),
				("ui-toolbar", _("T_oolbar"), _("Display a toolbar with the tools"), None),
				("ui-statusbar", _("Stat_usbar"), _("Display a statusbar with the status"), None),
				("ui-scrollbar-top", _("_Top Scroll Bar"),
				 _("Display the horizontal scrollbar at the top side"), None),
				("ui-scrollbar-bottom", _("_Bottom Scroll Bar"),
				 _("Display the horizontal scrollbar at the bottom side"), None),
				("ui-scrollbar-left", _("Le_ft Scroll Bar"),
				 _("Display the vertical scrollbar at the left side"), None),
				("ui-scrollbar-right", _("Rig_ht Scroll Bar"),
				 _("Display the vertical scrollbar at the right side"), None),
				("ui-keep-above", _("Keep Ab_ove"),
				 _("Keeps this window above other windows"), None),
				("ui-keep-below", _("Keep Be_low"),
				 _("Keeps this window below other windows"), None),
			("preferences", _("_Preferences..."), _("Configure Pynorama"),
			 Gtk.STOCK_PREFERENCES),
			("fullscreen", _("_Fullscreen"), _("Fill the entire screen"),
			 Gtk.STOCK_FULLSCREEN),
		("help", _("_Help"), None, None),
			("about", _("_About"), _("Show the about dialog"), Gtk.STOCK_ABOUT),
		]
		
		signaling_params = {
			"open" : (self.file_open,),
			"paste" : (self.pasted_data,),
			"sort" : (lambda data: self.sort_images(),),
			"sort-auto" : (self.toggle_autosort,),
			"sort-reverse" : (self.toggle_reverse_sort,),
			"sort-name" : (self.change_ordering,), # For group
			"remove" : (self.handle_remove,),
			"clear" : (self.handle_clear,),
			"quit" : (lambda data: self.destroy(),),
			"go-previous" : (self.go_previous,),
			"go-next" : (self.go_next,),
			"go-first" : (self.go_first,),
			"go-last" : (self.go_last,),
			"go-random" : (self.go_random,),
			"zoom-in" : (self.handle_zoom_change, 1),
			"zoom-out" : (self.handle_zoom_change, -1),
			"zoom-none" : (self.reset_zoom,),
			"auto-zoom-enable" : (self.change_auto_zoom,),
			"auto-zoom-fit" : (self.change_auto_zoom,),
			"auto-zoom-magnify" : (self.change_auto_zoom,),
			"auto-zoom-minify" : (self.change_auto_zoom,),
			"rotate-cw" : (self.handle_rotate, 1),
			"rotate-ccw" : (self.handle_rotate, -1),
			"flip-h" : (self.handle_flip, False),
			"flip-v" : (self.handle_flip, True),
			"interp-nearest" : (self.change_interp,), # For group
			"ui-toolbar" : (self.change_interface,),
			"ui-statusbar" : (self.change_interface,),
			"ui-scrollbar-top" : (self.change_scrollbars,),
			"ui-scrollbar-bottom" : (self.change_scrollbars,),
			"ui-scrollbar-right" : (self.change_scrollbars,),
			"ui-scrollbar-left" : (self.change_scrollbars,),
			"ui-keep-above" : (self.toggle_keep_above,),
			"ui-keep-below" : (self.toggle_keep_below,),
			"preferences" : (self.show_preferences,),
			"fullscreen" : (self.toggle_fullscreen,),
			"about" : (self.app.show_about_dialog,),
		}
		
		sort_group, interp_group, zoom_mode_group = [], [], []
		toggleable_actions = {
			"sort-auto" : None,
			"sort-reverse" : None,
			"auto-zoom-enable" : None,
			"auto-zoom-fit" : (3, zoom_mode_group),
			"auto-zoom-fill" : (0, zoom_mode_group),
			"auto-zoom-match-width" : (1, zoom_mode_group),
			"auto-zoom-match-height" : (2, zoom_mode_group),
			"auto-zoom-minify" : None,
			"auto-zoom-magnify" : None,
			"fullscreen" : None,
			"sort-name" : (0, sort_group),
			"sort-char" : (1, sort_group),
			"sort-file-date" : (2, sort_group),
			"sort-file-size" : (3, sort_group),
			"sort-img-size" : (4, sort_group),
			"sort-img-width" : (5, sort_group),
			"sort-img-height" : (6, sort_group),
			"interp-nearest" : (cairo.FILTER_NEAREST, interp_group),
			"interp-bilinear" : (cairo.FILTER_BILINEAR, interp_group),
			"interp-fast" : (cairo.FILTER_FAST, interp_group),
			"interp-good" : (cairo.FILTER_GOOD, interp_group),
			"interp-best" : (cairo.FILTER_BEST, interp_group),
			"ui-statusbar" : None,
			"ui-toolbar" :None,
			"ui-keep-above" : None,
			"ui-keep-below" : None,
			# The values seem inverted because... reasons
			"ui-scrollbar-top" : None,
			"ui-scrollbar-bottom" : None,
			"ui-scrollbar-right" : None,
			"ui-scrollbar-left" : None
		}
		
		accel_actions = {
			"open" : None,
			"paste" : None,
			"remove" : "Delete",
			"clear" : "<ctrl>Delete",
			"quit" : None,
			"go-next" : "Page_Down",
			"go-previous" : "Page_Up",
			"go-first" : "Home",
			"go-last" : "End",
			"zoom-none" : "KP_0",
			"zoom-in" : "KP_Add",
			"zoom-out" : "KP_Subtract",
			"auto-zoom-enable" : "KP_Multiply",
			"rotate-cw" : "R",
			"rotate-ccw" : "<ctrl>R",
			"flip-h" : "F",
			"flip-v" : "<ctrl>F",
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
		reverse_state = self.actions.get_action("sort-reverse").get_active()
		if self.reverse_sort != reverse_state:
			self.reverse_sort = reverse_state
			self.image_list.images.reverse()
			self.refresh_index()
		
	def toggle_autosort(self, data=None):
		self.autosort = self.actions.get_action("sort-auto").get_active()
	
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
		
		interp_group = self.actions.get_action("interp-nearest")
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
			can_goto_first = True
			can_goto_last = True
			
			count = len(images)
			count_chr_count = len(str(count))
			
			if self.current_image in images:
				image_index = images.index(self.current_image)
				can_goto_first = image_index != 0
				can_goto_last = image_index != count - 1
				
				index_text = str(image_index + 1).zfill(count_chr_count)
				
				index_fmt = _("#{index}/{count:d}") 
				label_text = index_fmt.format(index=index_text, count=count)
				self.index_label.set_text(label_text)
			else:
				question_marks = _("?") * count_chr_count
				index_fmt = _("{question_marks}/{count:d}")
				label_text = index_fmt.format(question_marks=question_marks, count=count)
				self.index_label.set_text(label_text)
		else:
			can_remove = self.current_image is not None
			can_goto_first = False
			can_goto_last = False
			
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
			("go-next", can_next),
			("go-previous", can_previous),
			("go-first", can_goto_first),
			("go-last", can_goto_last),
			("go-random", len(images) > 1)
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
		mode = self.actions.get_action("auto-zoom-fit").get_current_value()
		magnify = self.actions.get_action("auto-zoom-magnify").get_active()
		minify = self.actions.get_action("auto-zoom-minify").get_active()
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
		show_tools = self.actions.get_action("ui-toolbar").get_active()
		show_status = self.actions.get_action("ui-statusbar").get_active()
		self.toolbar.set_visible(show_tools)		
		self.statusbar.set_visible(show_status)		
	
	def toggle_keep_above(self, *data):
		keep_above = self.actions.get_action("ui-keep-above")
		keep_below = self.actions.get_action("ui-keep-below")
		if keep_above.get_active() and keep_below.get_active():
			keep_below.set_active(False)
			
		self.set_keep_above(keep_above.get_active())
				
	def toggle_keep_below(self, *data):
		keep_above = self.actions.get_action("ui-keep-above")
		keep_below = self.actions.get_action("ui-keep-below")
		if keep_below.get_active() and keep_above.get_active():
			keep_above.set_active(False)
			
		self.set_keep_below(keep_below.get_active())
		
	def change_scrollbars(self, *data):
		get_active = lambda name: self.actions.get_action(name).get_active()
		current_placement = self.image_scroller.get_placement()
		
		top_active = get_active("ui-scrollbar-top")
		bottom_active = get_active("ui-scrollbar-bottom")
		if top_active and bottom_active:
			if current_placement == Gtk.CornerType.TOP_LEFT or \
			   current_placement == Gtk.CornerType.TOP_RIGHT:
				self.actions.get_action("ui-scrollbar-bottom").set_active(False)
			else:
				self.actions.get_action("ui-scrollbar-top").set_active(False)
			return
			
		elif top_active or bottom_active:
			hpolicy = Gtk.PolicyType.AUTOMATIC
		else:
			hpolicy = Gtk.PolicyType.NEVER
		
		left_active = get_active("ui-scrollbar-left")
		right_active = get_active("ui-scrollbar-right")
		if left_active and right_active:
			if current_placement == Gtk.CornerType.TOP_LEFT or \
			   current_placement == Gtk.CornerType.BOTTOM_LEFT:
				self.actions.get_action("ui-scrollbar-right").set_active(False)
			else:
				self.actions.get_action("ui-scrollbar-left").set_active(False)
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
			
	def go_next(self, *data):
		if self.current_image and self.current_image.next:
			self.set_image(self.current_image.next)
		
	def go_previous(self, *data):
		if self.current_image and self.current_image.previous:
			self.set_image(self.current_image.previous)
			
	def go_first(self, *data):
		first_image = self.image_list.get_first()
		if first_image:
			self.set_image(first_image)
	
	def go_last(self, *data):
		last_image = self.image_list.get_last()
		if last_image:
			self.set_image(last_image)
			
	def go_random(self, *data):
		image_count = len(self.image_list)
		if image_count > 1:
			# Gets a new random index that is not the current one
			random_int = random.randint(0, image_count - 2)
			image_index = self.image_list.images.index(self.current_image)
			if random_int >= image_index:
				random_int += 1
			
			self.set_image(self.image_list.images[random_int])
			
	def handle_clear(self, *data):
		self.unlist(*self.image_list.images)
		
	def handle_remove(self, *data):
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
			some_pixels = selection.get_pixbuf()
			if some_pixels:
				self.insert_images(self.app.load_pixels(some_pixels))
								
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
		return self.actions.get_action("sort-auto").get_active()
	def set_enable_auto_sort(self, value):
		self.actions.get_action("sort-auto").set_active(value)
		
	def get_reverse_sort(self):
		return self.actions.get_action("sort-reverse").get_active()
	def set_reverse_sort(self, value):
		self.actions.get_action("sort-reverse").set_active(value)
	
	def get_auto_zoom(self):
		enabled = self.actions.get_action("auto-zoom-enable").get_active()
		minify = self.actions.get_action("auto-zoom-minify").get_active()
		magnify = self.actions.get_action("auto-zoom-magnify").get_active()
		return enabled, minify, magnify
		
	def set_auto_zoom(self, enabled, minify, magnify):
		self.actions.get_action("auto-zoom-minify").set_active(minify)
		self.actions.get_action("auto-zoom-magnify").set_active(magnify)
		self.actions.get_action("auto-zoom-enable").set_active(enabled)
		
	def get_auto_zoom_mode(self):
		return self.actions.get_action("auto-zoom-fit").get_current_value()
	def set_auto_zoom_mode(self, mode):
		self.actions.get_action("auto-zoom-fit").set_current_value(mode)
	
	def get_sort_mode(self):
		return self.actions.get_action("sort-name").get_current_value()
	def set_sort_mode(self, value):
		self.actions.get_action("sort-name").set_current_value(value)
	
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
		self.actions.get_action("ui-toolbar").set_active(value)
		self.toolbar.set_visible(value)
		
	def get_statusbar_visible(self):
		return self.statusbar.get_visible()
	def set_statusbar_visible(self, value):
		self.actions.get_action("ui-statusbar").set_active(value)
		self.statusbar.set_visible(value)
	
	def get_hscrollbar_placement(self):
		top = self.actions.get_action("ui-scrollbar-top").get_active()
		bottom = self.actions.get_action("ui-scrollbar-bottom").get_active()
		return 2 if bottom else 1 if top else 0
	
	def set_hscrollbar_placement(self, value):
		if value == 2:
			self.actions.get_action("ui-scrollbar-bottom").set_active(True)
		elif value == 1:
			self.actions.get_action("ui-scrollbar-top").set_active(True)
		else:
			self.actions.get_action("ui-scrollbar-top").set_active(False)
			self.actions.get_action("ui-scrollbar-bottom").set_active(False)
		
		self.change_scrollbars()
	
	def get_vscrollbar_placement(self):
		left = self.actions.get_action("ui-scrollbar-left").get_active()
		right = self.actions.get_action("ui-scrollbar-right").get_active()
		return 2 if right else 1 if left else 0
	
	def set_vscrollbar_placement(self, value):
		if value == 2:
			self.actions.get_action("ui-scrollbar-right").set_active(True)
		elif value == 1:
			self.actions.get_action("ui-scrollbar-left").set_active(True)
		else:
			self.actions.get_action("ui-scrollbar-left").set_active(False)
			self.actions.get_action("ui-scrollbar-right").set_active(False)
			
		self.change_scrollbars()
		
	def get_fullscreen(self):
		return self.actions.get_action("fullscreen").get_active()
		
	def set_fullscreen(self, value):
		self.actions.get_action("fullscreen").set_active(value)
	
	ui_description = '''<ui>
	<menubar>
		<menu action="file">
			<menuitem action="open" />
			<menuitem action="paste" />
			<separator />
			<menu action="ordering">
				<menuitem action="sort" />
				<separator />
				<menuitem action="sort-auto" />
				<menuitem action="sort-reverse" />
				<separator />
				<menuitem action="sort-name" />
				<menuitem action="sort-char" />
				<separator />
				<menuitem action="sort-file-date" />
				<menuitem action="sort-file-size" />
				<separator />
				<menuitem action="sort-img-size" />
				<menuitem action="sort-img-width" />
				<menuitem action="sort-img-height" />
			</menu>
			<separator />
			<menuitem action="remove" />
			<menuitem action="clear" />
			<separator />
			<menuitem action="quit" />
		</menu>
		<menu action="go">
			<menuitem action="go-next" />
			<menuitem action="go-previous" />
			<separator />
			<menuitem action="go-first" />
			<menuitem action="go-last" />
			<separator />
			<menuitem action="go-random" />
		</menu>
		<menu action="view">
			<menuitem action="zoom-in" />
			<menuitem action="zoom-out" />
			<menuitem action="zoom-none" />
			<menu action="auto-zoom" >
				<menuitem action="auto-zoom-enable" />
				<separator />
				<menuitem action="auto-zoom-fit" />
				<menuitem action="auto-zoom-fill" />
				<menuitem action="auto-zoom-match-width" />
				<menuitem action="auto-zoom-match-height" />
				<separator />
				<menuitem action="auto-zoom-magnify" />
				<menuitem action="auto-zoom-minify" />
			</menu>
			<separator />
			<menu action="transform">
				<menuitem action="rotate-ccw" />
				<menuitem action="rotate-cw" />
				<separator />
				<menuitem action="flip-h" />
				<menuitem action="flip-v" />
			</menu>
			<menu action="interpolation">
				<menuitem action="interp-nearest" />
				<menuitem action="interp-bilinear" />
				<separator />
				<menuitem action="interp-fast" />
				<menuitem action="interp-good" />
				<menuitem action="interp-best" />
			</menu>
			<separator />
			<menu action="interface">
				<menuitem action="ui-toolbar" />
				<menuitem action="ui-statusbar" />
				<separator />
				<menuitem action="ui-scrollbar-top" />
				<menuitem action="ui-scrollbar-bottom" />
				<menuitem action="ui-scrollbar-left" />
				<menuitem action="ui-scrollbar-right" />
				<separator />
				<menuitem action="ui-keep-above" />
				<menuitem action="ui-keep-below" />
			</menu>
			<menuitem action="fullscreen" />
			<separator />
			<menuitem action="preferences" />
		</menu>
		<menu action="help">
			<menuitem action="about" />
		</menu>
	</menubar>
	<toolbar>
		<toolitem action="open" />
		<toolitem action="paste" />
		<separator />
		<toolitem action="go-previous" />
		<toolitem action="go-next" />
		<separator/>
		<toolitem action="zoom-in" />
		<toolitem action="zoom-out" />
		<separator />
		<toolitem action="preferences" />
		<separator />
		<toolitem action="fullscreen" />
		<toolitem action="about" />
	</toolbar>
</ui>'''
	
if __name__ == "__main__":
	# Run the program
	app = ImageViewer()
	app.run(sys.argv)
