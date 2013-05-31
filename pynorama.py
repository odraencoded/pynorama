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
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GLib, GObject
import cairo
from gettext import gettext as _
import organization, navigation, loading, preferences, viewing, dialog
from loading import DirectoryLoader
DND_URI_LIST, DND_IMAGE = range(2)

class ImageViewer(Gtk.Application):
	Version = "v0.2.1"
	
	def __init__(self):
		Gtk.Application.__init__(self)
		self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)
		
		# Default prefs stuff
		self.zoom_effect = 2
		self.spin_effect = 90
		self.default_position = .5, .5
		self.memory_check_queued = False
		self.meta_mouse_handler = navigation.MetaMouseHandler()
	
	# --- Gtk.Application interface down this line --- #
	def do_startup(self):
		Gtk.Application.do_startup(self)
		
		preferences.load_into_app(self)
		
		drag_handler = navigation.DragHandler(-1)
		hover_handler = navigation.HoverHandler(0.2)
		scroll_handler = navigation.ScrollHandler(navigation.ScrollModes.Wide)
		spin_handler = navigation.SpinHandler()
		stretch_handler = navigation.StretchHandler((.5, .5))
		
		self.meta_mouse_handler.add(scroll_handler)
		self.meta_mouse_handler.add(hover_handler)
		self.meta_mouse_handler.add(drag_handler, Gdk.BUTTON_PRIMARY)
		self.meta_mouse_handler.add(spin_handler, Gdk.BUTTON_SECONDARY)
		self.meta_mouse_handler.add(stretch_handler, Gdk.BUTTON_MIDDLE)
		
		self.memory = loading.Memory()
		self.memory.connect("thing-requested", self.queue_memory_check)
		self.memory.connect("thing-unused", self.queue_memory_check)
		self.memory.connect("thing-unlisted", self.queue_memory_check)
			
		Gtk.Window.set_default_icon_name("pynorama")
	
	def do_activate(self):
		some_window = self.get_window()
		some_window.present()
		
	def do_open(self, files, file_count, hint):
		some_window = self.get_window()
		
		some_window.go_new = True
		self.open_files_for_album(some_window.image_list, files=files,
		                          search=file_count == 1)
		some_window.go_new = False
		
		some_window.present()
			
	def open_image_dialog(self, album, window=None):
		''' Creates an "open image..." dialog for
		    adding images into an album. '''
		    
		image_chooser = Gtk.FileChooserDialog(_("Open Image..."), window,
		                                      Gtk.FileChooserAction.OPEN,
		                                      (Gtk.STOCK_CANCEL,
		                                       Gtk.ResponseType.CANCEL,
		                                       Gtk.STOCK_ADD,
		                                       1,
		                                       Gtk.STOCK_OPEN,
		                                       Gtk.ResponseType.OK))
			
		image_chooser.set_default_response(Gtk.ResponseType.OK)
		image_chooser.set_select_multiple(True)
		image_chooser.set_local_only(False)
		
		# Add dialog options from "loading" module
		for a_dialog_option in loading.CombinedDialogOption.List:
			a_dialog_filter = a_dialog_option.create_filter()
			image_chooser.add_filter(a_dialog_filter)			
			
		for a_dialog_option in loading.DialogOption.List:
			a_dialog_filter = a_dialog_option.create_filter()
			image_chooser.add_filter(a_dialog_filter)
			
		clear_album = False
		search_siblings = False
		choosen_uris = None
		
		response = image_chooser.run()
		
		choosen_option = image_chooser.get_filter().dialog_option
		if response in [Gtk.ResponseType.OK, 1]:
			choosen_uris = image_chooser.get_uris()
		
		if response == Gtk.ResponseType.OK:
			clear_album = True
			if len(choosen_uris) == 1:
				search_siblings = True
				
		image_chooser.destroy()
			
		if choosen_uris:
			self.open_files_for_album(album, choosen_option.loader,
			                          uris=choosen_uris, search=search_siblings,
			                          replace=clear_album)
	
	def show_preferences_dialog(self, window=None):
		''' Show the preferences dialog '''
		dialog = preferences.Dialog(self)
			
		dialog.set_transient_for(window or self.get_window())
		dialog.set_modal(True)
		dialog.set_destroy_with_parent(True)
		
		if dialog.run() == Gtk.ResponseType.OK:
			dialog.save_prefs()
			
		dialog.destroy()
		
	def show_about_dialog(self, window=None):
		''' Shows the about dialog '''
		dialog = Gtk.AboutDialog(program_name="pynorama",
		                         version=ImageViewer.Version,
		                         comments=_("pynorama is an image viewer"),
		                         logo_icon_name="pynorama",
		                         license_type=Gtk.License.GPL_3_0)
		                         
		dialog.set_copyright("Copyrght © 2013 Leonardo Augusto Pereira")
		
		dialog.set_transient_for(window or self.get_window())
		dialog.set_modal(True)
		dialog.set_destroy_with_parent(True)
		
		#dialog.connect("response", lambda a, b: a.destroy())
		dialog.run()
		dialog.destroy()
		
	def get_window(self):
		windows = self.get_windows() # XP, Vista, 7, 8?
		if windows:
			# Return most recently focused window
			return windows[0]
		else:
			# Create a window and return it
			a_window = ViewerWindow(self)
			a_window.show()
			image_view = a_window.imageview
			image_view.mouse_adapter = navigation.MouseAdapter(image_view)
			self.meta_mouse_handler.attach(image_view.mouse_adapter)
			
			fillscreen = preferences.Settings.get_boolean("start-fullscreen")
			a_window.set_fullscreen(fillscreen)
			return a_window
			
	def queue_memory_check(self, *data):
		if not self.memory_check_queued:
			self.memory_check_queued = True
			GObject.idle_add(self.memory_check)
			
	def memory_check(self):
		self.memory_check_queued = False
		
		while self.memory.enlisted_stuff:
			enlisted_thing = self.memory.enlisted_stuff.pop()
			enlisted_thing.connect("finished-loading", self.log_loading_finish)
				
		if self.memory.unlisted_stuff or self.memory.unused_stuff:
			while self.memory.unlisted_stuff:
				unlisted_thing = self.memory.unlisted_stuff.pop()
				if unlisted_thing.is_loading or unlisted_thing.on_memory:
					unlisted_thing.unload()
					dialog.log(dialog.Lines.Unloaded(unlisted_thing))
					
			while self.memory.unused_stuff:
				unused_thing = self.memory.unused_stuff.pop()
				# Do not unload things that are not on disk (like pastes)
				if unused_thing.on_disk:
					if unused_thing.is_loading or unused_thing.on_memory:
						unused_thing.unload()
						dialog.log(dialog.Lines.Unloaded(unused_thing))
						
			gc.collect()
			
		while self.memory.requested_stuff:
			requested_thing = self.memory.requested_stuff.pop()
			if not (requested_thing.is_loading or requested_thing.on_memory):
				requested_thing.load()
				dialog.log(dialog.Lines.Loading(requested_thing))
				
		return False
		
	def log_loading_finish(self, thing, error):
		if error:
			dialog.log(dialog.Lines.Error(error))
			
		elif thing.on_memory:
			dialog.log(dialog.Lines.Loaded(thing))
	
	def open_files_for_album(self, album, loader=None, files=None, uris=None,
	                         replace=False, search=False, silent=False,
	                         manage=True):
		''' Open files or uris for an album '''
		album_context = loading.Context(files=files, uris=uris)
		context_sorting = lambda ctx: album.sort_list(ctx.images)
		
		self.open_files(album_context, context_sorting=context_sorting,
		                loader=loader, search=search, silent=silent)
		
		if album_context.images:
			if replace:
				del album[:]
			
			if manage:			
				for image in album_context.images:
					self.memory.observe(image)
					
			album.extend(album_context.images)
		
	def open_files(self, context, loader=None, search=False,
	                     context_sorting=None, silent=False):
	                     
		''' Open files using loading.LoadersLoader '''
		if loader is None:
			loader = loading.LoadersLoader.LoaderListLoader
		
		context.uris_to_files()
		context.load_files_info()
		for a_file, a_problem in context.problems.items():
			context.files.remove(a_file)
		
		directories = []
		removed_files = 0
		for i in range(len(context.files)):
			index = i - removed_files
			a_file = context.files[index]
			try:
				if DirectoryLoader.should_open(a_file):
					removed_files += 1
					directories.append(a_file)
					del context.files[index]
			except Exception:
				raise
		
		if search and context.files:
			# Sibling file loading is not sorted
			context.add_sibling_files(loader)
			files = list(context.files)
			del context.files[:]
			self.open_context_images(context, files, loader)
			                         
		if directories:
			self.open_context_images(context, directories, DirectoryLoader,
			                         sort_method=context_sorting)
			                         
		if context.files:
			self.open_context_images(context, context.files, loader,
			                         sort_method=context_sorting)
		
		if context.problems and not silent:
			problem_list = []
			for a_file, a_problem in context.problems.items():
				problem_list.append((a_file.get_parse_name(), str(a_problem))) 
			
			message = _("There were problems opening the following files:")
			columns = [_("File"), _("Error")]
			
			dialog.alert_list(message, problem_list, columns)
			
	def open_context_images(self, context, files, loader, sort_method=None):
		''' Opens files in a loader, sort the result with sort_method and
		    append it to context. '''
		loader_context = loading.Context()
		for a_file in files:
			loader.open_file(loader_context, a_file)
		
		if sort_method:
			sort_method(loader_context)
		
		context.images.extend(loader_context.images)
		context.files.extend(loader_context.files)
		context.uris.extend(loader_context.uris)
		
	def load_pixels(self, pixels):
		pixelated_image = loading.PixbufDataImageNode(pixels, "Pixels")
		return [pixelated_image]
	
class ViewerWindow(Gtk.ApplicationWindow):
	def __init__(self, app):
		Gtk.ApplicationWindow.__init__(self,
		                               title=_("Pynorama"),
		                               application=app)
		self.app = app
		self.set_default_size(600, 600)
		# Auto zoom stuff
		self.auto_zoom_magnify = False
		self.auto_zoom_minify = True
		self.auto_zoom_mode = 0
		self.auto_zoom_enabled = False
		# If the user changes the zoom set by auto_zoom, 
		# then auto_zoom isn't called after rotating or resizing
		# the imageview
		self.auto_zoom_zoom_modified = False
		# Album variables
		self.__idly_refresh_index_id = None
		self._focus_loaded_handler_id = None
		self._old_focused_image = None
		self.go_new = False
		self.ordering_modes = [
			organization.SortingKeys.ByName,
			organization.SortingKeys.ByCharacters,
			organization.SortingKeys.ByFileDate,
			organization.SortingKeys.ByFileSize,
			organization.SortingKeys.ByImageSize,
			organization.SortingKeys.ByImageWidth,
			organization.SortingKeys.ByImageHeight
		]
		self.active_ordering = organization.SortingKeys.ByName
		self.image_list = organization.Album()
		self.image_list.connect("image-added", self._image_added)
		self.image_list.connect("image-removed", self._image_removed)
		self.image_list.connect("order-changed", self._album_order_changed)
		# Set clipboard
		self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		
		# Create layout
		vlayout = Gtk.VBox()
		self.add(vlayout)
		vlayout.show()
		
		# Setup actions
		self.setup_actions()
		
		self.image_list.bind_property(
		     "reverse", self.actions.get_action("sort-reverse"),
		     "active", GObject.BindingFlags.BIDIRECTIONAL)
		self.image_list.bind_property(
		     "autosort", self.actions.get_action("sort-auto"),
		     "active", GObject.BindingFlags.BIDIRECTIONAL)
		
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
		
		# Create a scrollwindow and a imagev--, galleryv-- err.. imageview!
		self.view_scroller = Gtk.ScrolledWindow()
		# TODO: There ought to be a better way
		# to drop the default key behaviour
		self.view_scroller.connect("key-press-event", lambda x, y: True)
		self.view_scroller.connect("key-release-event", lambda x, y: True)
		self.view_scroller.connect("scroll-event", lambda x, y: True)
		
		self.imageview = viewing.ImageView()
		# Setup a bunch of reactions to all sorts of things
		self.imageview.connect("notify::magnification",
		                       self.magnification_changed)
		self.imageview.connect("notify::rotation", self.reapply_auto_zoom)
		self.imageview.connect("size-allocate", self.reapply_auto_zoom)
		self.imageview.connect("notify::magnification", self.view_changed)
		self.imageview.connect("notify::rotation", self.view_changed)
		self.imageview.connect("notify::flip", self.view_changed)
		
		self.view_scroller.add(self.imageview)
		self.view_scroller.show_all()
		
		vlayout.pack_start(self.view_scroller, True, True, 0)
		
		# Add a status bar, the statusbar box and a statusbar box box
		self.statusbarboxbox = Gtk.Box()
		self.statusbarboxbox.set_orientation(Gtk.Orientation.VERTICAL)
		separator = Gtk.Separator()
		self.statusbarboxbox.pack_start(separator, False, False, 0)
		
		self.statusbarbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
		self.statusbarbox.set_border_width(2)
		self.statusbarbox.set_spacing(8)
		
		# With a label for image index
		self.index_label = Gtk.Label()
		self.index_label.set_alignment(1, 0.5)
		self.statusbarbox.pack_start(self.index_label, False, True, 6)
		
		self.loading_spinner = Gtk.Spinner()
		self.statusbarbox.pack_start(self.loading_spinner, False, False, 6)
		
		self.statusbar = Gtk.Statusbar()
		self.statusbarbox.pack_start(self.statusbar, True, True, 6)
		
		# And a label for the image transformation
		self.transform_label = Gtk.Label()
		self.transform_label.set_alignment(0, 0.5)
		self.statusbarbox.pack_end(self.transform_label, False, False, 6)
		self.statusbarboxbox.pack_end(self.statusbarbox, False, False, 0)
		
		# Show status
		vlayout.pack_end(self.statusbarboxbox, False, True, 0)
		
		self.statusbarboxbox.show_all()
		self.loading_spinner.hide()
		
		# DnD setup	
		self.imageview.drag_dest_set(Gtk.DestDefaults.ALL,
		                             [], Gdk.DragAction.COPY)
		
		target_list = Gtk.TargetList.new([])
		target_list.add_image_targets(DND_IMAGE, False)
		target_list.add_uri_targets(DND_URI_LIST)
		
		self.imageview.drag_dest_set_target_list(target_list)
		self.imageview.connect("drag-data-received", self.dragged_data)
		
		self.layout = organization.SingleFrameLayout()
		self.avl = organization.AlbumViewLayout(album=self.image_list,
		                                        layout=self.layout,
		                                        view=self.imageview)
		
		self.avl.connect("focus-changed", self._focus_changed)
		
		preferences.load_into_window(self)
		
		self.refresh_transform()
		self.refresh_index()
		self.refresh_interp()
		
	def setup_actions(self):
		self.manager = Gtk.UIManager()
		self.accelerators = self.manager.get_accel_group()
		self.add_accel_group(self.accelerators)
		self.actions = Gtk.ActionGroup("pynorama")
		self.manager.insert_action_group(self.actions)
		
		action_params = [
		# File Menu
		("file", _("_File"), None, None),
			("open", _("_Open..."), _("Open an image in the viewer"),
			 Gtk.STOCK_OPEN),
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
			("zoom-none", _("No _Zoom"),
			 _("Shows the image at it's normal size"), Gtk.STOCK_ZOOM_100),
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
				("transform-reset", _("Re_set"),
				 _("Resets rotation and flip"), None),
			# Interpolation submenu
			("interpolation", _("Inter_polation"), None, None),
				("interp-nearest", _("_Nearest Neighbour Filter"), _(""), None),
				("interp-bilinear", _("_Bilinear Filter"), _(""), None),
				("interp-fast", _("Fa_ster Fil_ter"), _(""), None),
				("interp-good", _("B_etter Filt_er"), _(""), None),
				("interp-best", _("St_ronger Filte_r"), _(""), None),
			# Interface submenu
			("interface", _("_Interface"), None, None),
				("ui-toolbar", _("T_oolbar"),
				 _("Display a toolbar with the tools"), None),
				("ui-statusbar", _("Stat_usbar"),
				 _("Display a statusbar with the status"), None),
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
			"sort" : (lambda data: self.image_list.sort(),),
			"sort-reverse" : (self.__sort_changed,),
			"sort-name" : (self.__ordering_mode_changed,), # For group
			"remove" : (self.handle_remove,),
			"clear" : (self.handle_clear,),
			"quit" : (lambda data: self.destroy(),),
			"go-previous" : (self.go_previous,),
			"go-next" : (self.go_next,),
			"go-first" : (self.go_first,),
			"go-last" : (self.go_last,),
			"go-random" : (self.go_random,),
			"zoom-in" : (lambda data: self.zoom_view(1),),
			"zoom-out" : (lambda data: self.zoom_view(-1),),
			"zoom-none" : (lambda data: self.set_view_zoom(1),),
			"auto-zoom-enable" : (self.change_auto_zoom,),
			"auto-zoom-fit" : (self.change_auto_zoom,),
			"auto-zoom-magnify" : (self.change_auto_zoom,),
			"auto-zoom-minify" : (self.change_auto_zoom,),
			"rotate-cw" : (lambda data: self.rotate_view(1),),
			"rotate-ccw" : (lambda data: self.rotate_view(-1),),
			"flip-h" : (lambda data: self.flip_view(False),),
			"flip-v" : (lambda data: self.flip_view(True),),
			"transform-reset" : (lambda data: self.reset_view_transform(),),
			"interp-nearest" : (self.change_interp,), # For group
			"ui-toolbar" : (self.change_interface,),
			"ui-statusbar" : (self.change_interface,),
			"ui-scrollbar-top" : (self.change_scrollbars,),
			"ui-scrollbar-bottom" : (self.change_scrollbars,),
			"ui-scrollbar-right" : (self.change_scrollbars,),
			"ui-scrollbar-left" : (self.change_scrollbars,),
			"ui-keep-above" : (self.toggle_keep_above,),
			"ui-keep-below" : (self.toggle_keep_below,),
			"preferences" : (lambda data:
			                 self.app.show_preferences_dialog(self),),
			"fullscreen" : (self.toggle_fullscreen,),
			"about" : (lambda data: self.app.show_about_dialog(self),),
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
		
	# --- event handling down this line --- #
	def __ordering_mode_changed(self, radioaction, current):
		#TODO: Use GObject.bind_property_with_closure for this
		sort_value = current.get_current_value()
		self.active_ordering = self.ordering_modes[sort_value]
	
		self.image_list.comparer = self.active_ordering
		if not self.image_list.autosort:
			self.image_list.sort()
		
	def __sort_changed(self, *data):
		if not self.image_list.autosort:
			self.image_list.sort()
			
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
		focused_image = self.avl.focus_image
		can_remove = not focused_image is None
		can_goto_first = False
		can_goto_last = False
		can_previous = False
		can_next = False
			
		if self.image_list:
			can_remove = True
			
			count = len(self.image_list)
			count_chr_count = len(str(count))
			
			if focused_image in self.image_list:
				image_index = self.image_list.index(focused_image)
				can_goto_first = image_index != 0
				can_goto_last = image_index != count - 1
				can_previous = True
				can_next = True
				
				index_text = str(image_index + 1).zfill(count_chr_count)
				
				index_fmt = _("#{index}/{count:d}") 
				label_text = index_fmt.format(index=index_text, count=count)
				self.index_label.set_text(label_text)
			else:
				can_goto_first = True
				can_goto_last = True
				
				question_marks = _("?") * count_chr_count
				index_fmt = _("{question_marks}/{count:d}")
				label_text = index_fmt.format(question_marks=question_marks,
				                              count=count)
				self.index_label.set_text(label_text)
		else:
			self.index_label.set_text("∅")
			
		sensible_list = [
			("remove", can_remove),
			("clear", len(self.image_list) > 0),
			("go-next", can_next),
			("go-previous", can_previous),
			("go-first", can_goto_first),
			("go-last", can_goto_last),
			("go-random", len(self.image_list) > 1)
		]
		
		for action_name, sensitivity in sensible_list:
			self.actions.get_action(action_name).set_sensitive(sensitivity)
		
	def refresh_transform(self):
		focused_image = self.avl.focus_image
		if focused_image:
			if focused_image.is_bad:
				# This just may happen
				pic = _("Error")
				
			elif focused_image.on_memory:
				metadata = focused_image.metadata
				# The width and height are from the source
				pic = "{width}x{height}".format(width=metadata.width,
				                                height=metadata.height)
				                                
			else:
				pic = _("Loading")
				
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
			
	def set_view_rotation(self, angle):
		anchor = self.imageview.get_widget_point()
		pin = self.imageview.get_pin(anchor)
		self.imageview.set_rotation(angle)
		self.imageview.adjust_to_pin(pin)
	
	def set_view_zoom(self, magnification):
		anchor = self.imageview.get_widget_point()
		pin = self.imageview.get_pin(anchor)
		self.imageview.set_magnification(magnification)
		self.imageview.adjust_to_pin(pin)
		
	def set_view_flip(self, horizontal, vertical):
		hflip, vflip = self.imageview.get_flip()
		
		if hflip != horizontal or vflip != vertical:
			# ih8triGNOMEtricks
			rot = self.imageview.get_rotation()
			angle_change = (45 - ((rot + 45) % 180)) * 2
		
			# If the image if flipped both horizontally and vertically
			# Then it is rotated 180 degrees
			if horizontal and vertical:
				horizontal = vertical = False
				angle_change += 180
		
			anchor = self.imageview.get_widget_point()
			pin = self.imageview.get_pin(anchor)
			if angle_change:
				self.imageview.set_rotation((rot + angle_change) % 360)
			
			self.imageview.set_flip((horizontal, vertical))
			self.imageview.adjust_to_pin(pin)
		
	def zoom_view(self, power):
		''' Zooms the viewport '''		
		zoom_effect = self.app.zoom_effect
		if zoom_effect and power:
			old_zoom = self.imageview.get_magnification()
			new_zoom = self.app.zoom_effect ** power * old_zoom
			self.set_view_zoom(new_zoom)
			
	def flip_view(self, vertically):
		''' Flips the viewport '''
		# Horizontal mirroring depends on the rotation of the image
		hflip, vflip = self.imageview.get_flip()
		if vertically:
			vflip = not vflip
		else:
			hflip = not hflip
		
		self.set_view_flip(hflip, vflip)
		
	def rotate_view(self, effect):
		''' Rotates the viewport '''
		change = self.app.spin_effect * effect
		if change < 0:
			change += (change // 360) * -360
			
		if change:
			new_rotation = self.imageview.get_rotation() + change
			self.set_view_rotation(new_rotation % 360)
	
	def reset_view_transform(self):
		self.set_view_flip(False, False)
		self.set_view_rotation(0)
	
	def auto_zoom(self):
		''' Zooms automatically!
			For future reference on auto zoom mode:
			  "fit" = magnify based on the largest side
			  "fill" = magnify based on the smallest side
			  "width" = magnify based on width
			  "height" = magnify based on height '''
			  
		if self.auto_zoom_magnify or self.auto_zoom_minify:
			side_name = ["smallest", "width",
			             "height", "largest"][self.auto_zoom_mode]
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
		self.statusbarboxbox.set_visible(show_status)		
	
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
		current_placement = self.view_scroller.get_placement()
		
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
		        
		self.view_scroller.set_policy(hpolicy, vpolicy)
		self.view_scroller.set_placement(placement)
			
	def toggle_fullscreen(self, data=None):
		# This simply tries to fullscreen / unfullscreen
		fullscreenaction = self.actions.get_action("fullscreen")
		
		if fullscreenaction.get_active():
			self.fullscreen()
		else:
			self.unfullscreen()
	
	# --- Go go go!!! --- #
	def go_next(self, *data):
		self.avl.go_next()
		
	def go_previous(self, *data):
		self.avl.go_previous()
			
	def go_first(self, *data):
		self.avl.go_index(0)
		
	def go_last(self, *data):
		self.avl.go_index(-1)
		
	def go_random(self, *data):
		image_count = len(self.image_list)
		if image_count > 1:
			# Gets a new random index that is not the current one
			random_int = random.randint(0, image_count - 2)
			image_index = self.avl.album.index(self.avl.focus_image)
			if random_int >= image_index:
				random_int += 1
			
			self.avl.go_index(random_int)
			
	def handle_clear(self, *data):
		del self.image_list[:]
		
	def handle_remove(self, *data):
		focus = self.avl.focus_image
		if focus:
			self.image_list.remove(focus)
	
	def pasted_data(self, data=None):
		self.go_new = True
		some_uris = self.clipboard.wait_for_uris()
		
		if some_uris:
			self.app.open_files_for_album(self.image_list, uris=some_uris)
			
		some_pixels = self.clipboard.wait_for_image()
		if some_pixels:
			new_images = self.app.load_pixels(some_pixels)
			if new_images:
				self.image_list.extend(new_images)
				
		self.go_new = False
			
	def dragged_data(self, widget, context, x, y, selection, info, timestamp):
		self.go_new = True
		if info == DND_URI_LIST:
			some_uris = selection.get_uris()
			if some_uris:
				self.app.open_files_for_album(self.image_list, uris=some_uris,
				                                   search=len(some_uris) == 1,
				                                   replace=True)
				                                   
		elif info == DND_IMAGE:
			some_pixels = selection.get_pixbuf()
			if some_pixels:
				new_images = self.app.load_pixels(some_pixels)
				if new_images:
					self.image_list.extend(new_images)
					
		self.go_new = False
								
	def file_open(self, widget, data=None):
		self.app.open_image_dialog(self.image_list, self)
			
	def imageview_scrolling(self, widget, data=None):
		anchor = self.imageview.get_pointer()
		
		if data.direction == Gdk.ScrollDirection.UP:
			self.zoom_view(1)
			#self.change_zoom(1, anchor)
			
		elif data.direction == Gdk.ScrollDirection.DOWN:
			self.zoom_view(-1)
			#self.change_zoom(-1, anchor)
					
		# Makes the scrolled window not scroll, I hope
		return True
	
	''' Methods after this comment are actually kind of a big deal.
	    Do not rename them. '''
	
	def refresh_title(self, image=None):
		if image:
			if image.name == image.fullname:
				title_fmt = _("“{name}” - Pynorama")
			else:
				title_fmt = _("“{name}” [“{fullname}”] - Pynorama")
				
			new_title = title_fmt.format(
			                  name=image.name, fullname=image.fullname)
			self.set_title(new_title)
			
		else:
			self.set_title(_("Pynorama"))
			
	def do_destroy(self, *data):
		preferences.set_from_window(self)
		self.avl.clean()
		return Gtk.Window.do_destroy(self)
		
	def _image_added(self, album, image, index):
		image.lists += 1
		self.__queue_refresh_index()
		
		if self.go_new:
			self.go_new = False
			self.avl.go_image(image)
			
		elif self.avl.focus_image is None:
			self.avl.go_image(image)
		
	def _image_removed(self, album, image, index):
		image.lists -= 1
		self.__queue_refresh_index()
		
	def _album_order_changed(self, album):
		self.__queue_refresh_index()
	
	def _focus_changed(self, avl, focused_image):
		if self._focus_loaded_handler_id:
			self._old_focused_image.disconnect(self._focus_loaded_handler_id)
			self._focus_loaded_handler_id = None
		
		self._old_focused_image = focused_image
		
		self.__queue_refresh_index()
		self.refresh_title(focused_image)
		
		loading_ctx = self.statusbar.get_context_id("loading")
		self.statusbar.pop(loading_ctx)
		
		if focused_image:
			if focused_image.on_memory or focused_image.is_bad:
				self.loading_spinner.hide()
				self.loading_spinner.stop()
				
				# Show error in status bar #
				if focused_image.error:
					message = dialog.Lines.Error(focused_image.error)
					self.statusbar.push(loading_ctx, message)
					
				# Refresh frame #
				self._refresh_focus_frame()
			
			else:				
				# Show loading hints #
				message = dialog.Lines.Loading(focused_image)
				self.statusbar.push(loading_ctx, message)
				self.loading_spinner.show()
				self.loading_spinner.start() # ~like a record~
				
				self._focus_loaded_handler_id = focused_image.connect(
				     "finished-loading", self._focus_loaded)
		else:
			self.loading_spinner.hide()
			self.loading_spinner.stop()
			
	def _focus_loaded(self, image, error):
		focused_image = self.avl.focus_image
		if focused_image == image:
			# Hide loading hints #
			loading_ctx = self.statusbar.get_context_id("loading")
			self.statusbar.pop(loading_ctx)
			self.loading_spinner.hide()
			self.loading_spinner.stop()
			
			# Show error in status bar #
			if error:
				message = dialog.Lines.Error(error)
				self.statusbar.push(loading_ctx, message)
				
			# Refresh frame #
			self._refresh_focus_frame()
				
		self._old_focused_image.disconnect(self._focus_loaded_handler_id)
		self._focus_loaded_handler_id = None
		
	def _refresh_focus_frame(self):
		if self.auto_zoom_enabled:
			self.auto_zoom()
		
		self.imageview.adjust_to_boundaries(*self.app.default_position)
		self.refresh_transform()
			
	def __queue_refresh_index(self):
		if not self.__idly_refresh_index_id:
			self.__idly_refresh_index_id = GLib.idle_add(
			     self.__idly_refresh_index, priority=GLib.PRIORITY_HIGH_IDLE)
	
	def __idly_refresh_index(self):
		self.__idly_refresh_index_id = None
		self.refresh_index()
		
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
		return self.statusbarboxbox.get_visible()
	def set_statusbar_visible(self, value):
		self.actions.get_action("ui-statusbar").set_active(value)
		self.statusbarboxbox.set_visible(value)
	
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
				<separator />
				<menuitem action="transform-reset" />
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
