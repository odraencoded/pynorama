#!/usr/bin/env python3
# coding=utf-8
 
''' application.py is the main module of an image viewer application. '''

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
from gi.repository import Gtk, Gdk, Gio, GObject
import cairo
from gettext import gettext as _

from . import extending, notifying, utility, widgets, mousing, preferences
from . import viewing, organizing, loading, opening
from .viewing import ZoomMode

from . import components
from .components import *
components.import_addons()

DND_URI_LIST, DND_IMAGE = range(2)

# Log stuff
uilogger = notifying.Logger("interface")
applogger = notifying.Logger("app")

# Prints exceptions using the applogger logger printing
sys.excepthook = applogger.log_exception_info

class ImageViewer(Gtk.Application):
    Version = "v0.2.7"
    
    DataDirectory = "resources"
    PreferencesDirectory = "preferences"
    
    __gsignals__ = {
        "new-window": (GObject.SIGNAL_RUN_FIRST, None, [object]),
        "new-view": (GObject.SIGNAL_RUN_FIRST, None, [object])
    }
    
    def __init__(self):
        Gtk.Application.__init__(self)
        self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)
        
        # Directories
        self.data_directory = ImageViewer.DataDirectory
        self.preferences_directory = ImageViewer.PreferencesDirectory
        
        # Default prefs stuff
        self._preferences_dialog = None
        self.memory_check_queued = False
        self.meta_mouse_handler = mousing.MetaMouseHandler()
        self.meta_mouse_handler.connect(
            "handler-removed", self._removed_mouse_handler
        )
        
        self.mouse_handler_dialogs = dict()
        
        self.settings = preferences.SettingsGroup()
        self.settings.create_group("window")
        self.settings.create_group("album")
        self.settings.create_group("view")
        self.settings.create_group("layout")
        mouse_settings = self.settings.create_group("mouse")
        
        self.settings.connect("save", self._save_settings)
        self.settings.connect("load", self._load_settings)
        mouse_settings.connect("save", self._save_mouse_settings)
        mouse_settings.connect("load", self._load_mouse_settings)
    
    
    # --- Gtk.Application interface down this line --- #
    def do_startup(self):
        Gtk.Application.do_startup(self)
        
        # Setup components
        self.components = extending.ComponentMap()
        loaded_packages = extending.LoadedComponentPackages
        for a_codename, a_component in loaded_packages.items():
            a_component.add_on(self)
        
        preferences.LoadForApp(self)
        
        self.memory = loading.Memory()
        self.memory.connect("thing-requested", self.queue_memory_check)
        self.memory.connect("thing-unused", self.queue_memory_check)
        self.memory.connect("thing-unlisted", self.queue_memory_check)
        
        
        self.opener = opening.OpeningHandler(self)
        
        Gtk.Window.set_default_icon_name("pynorama")
    
    
    def do_activate(self):
        some_window = self.get_window()
        some_window.present()
    
    
    def do_open(self, files, file_count, hint):
        some_window = self.get_window()
        single_file = file_count == 1
        some_window.open_files(files, search_siblings=single_file)
        some_window.present()
    
    
    def do_shutdown(self):
        preferences.SaveFromApp(self)
        Gtk.Application.do_shutdown(self)
    
    
    #-- Some properties down this line --#
    zoom_effect = GObject.Property(type=float, default=1.25)
    spin_effect = GObject.Property(type=float, default=90)
    
    def show_open_image_dialog(self,
            open_cb,
            add_cb=None,
            cancel_cb=None,
            window=None,
            data=None):
        """
        Creates an "Open Image..." dialog for opening images.
        
        Its behaviour can be controlled with callbacks. The open and add
        callbacks are called when the user activates either open or add
        buttons. The add button will not be displayed if the add_cb
        is set to None.
        
        A list of URIs and a list of FileOpeners selected is passed to both
        open and add callback. Nothing is passed to the cancel callback.
        
        If a callback returns True the dialog will not be closed and that
        same callback might be called again.
        
        """
        
        # The dialog has two "open" buttons: "Open" and "Add"
        # The purpose is to let the user decide between replacing the
        # images being viewed and adding more images to view
        # Also, the "open" button can't "open" directories, only explore them.
        # That is kind of important!
        ADD_RESPONSE = 1
        OPEN_RESPONSE = Gtk.ResponseType.OK # <-- explores directories
        CANCEL_RESPONSE = Gtk.ResponseType.CANCEL
        
        buttons = (Gtk.STOCK_CLOSE, CANCEL_RESPONSE)
        if add_cb:
            buttons += (Gtk.STOCK_ADD, ADD_RESPONSE)
        buttons += (Gtk.STOCK_OPEN, OPEN_RESPONSE)
        
        image_chooser = Gtk.FileChooserDialog(
            _("Open Image..."),
            window,
            Gtk.FileChooserAction.OPEN,
            buttons
        )
        
        # The default response must have the "OK" value so that the dialog
        # goes inside directories instead of returning them
        image_chooser.set_modal(False)
        image_chooser.set_destroy_with_parent(True)
        image_chooser.set_default_response(Gtk.ResponseType.OK)
        image_chooser.set_select_multiple(True)
        image_chooser.set_local_only(False)
        
        #~ Create and add the file filters to the file chooser dialog ~#
        # Add the Supported Files filter
        file_openers = self.components["file-opener"]
        supported_files_group = opening.FileOpenerGroup(
            _("Supported Files"),
            file_openers
        )
        supported_files_filter = supported_files_group.create_file_filter()
        image_chooser.add_filter(supported_files_filter)
        
        # Add the File Openers filters that opted to be visible
        file_openers_filters = {}
        for a_file_opener in file_openers:
            if a_file_opener.show_on_dialog:
                a_file_filter = a_file_opener.get_file_filter()
                image_chooser.add_filter(a_file_filter)
                file_openers_filters[a_file_filter] = a_file_opener
        
        
        # Handles the dialog being destroyed after exiting .run
        def dialog_response_cb(image_chooser, response):
            if image_chooser.__destroyed:
                return
            
            uri_list = image_chooser.get_uris()
            # Get chosen openers list
            chosen_filter = image_chooser.get_filter()
            try:
                chosen_openers = [file_openers_filters[chosen_filter]]
            except KeyError:
                chosen_openers = supported_files_group.file_openers
            
            try:
                # Figure out what callback to call
                keep_dialog = False
                if response == OPEN_RESPONSE:
                    if open_cb:
                        keep_dialog = open_cb(uri_list, chosen_openers, data)
                        
                elif response == ADD_RESPONSE:
                    if add_cb:
                        keep_dialog = add_cb(uri_list, chosen_openers, data)
                    
                elif cancel_cb:
                    keep_dialog = cancel_cb(data)
            
            except:
                # In case something goes wrong when calling the callbacks
                # we don't want the to just hang there forever
                image_chooser.destroy()
                raise
            
            if not keep_dialog:
                image_chooser.destroy()
        
        image_chooser.connect("response", dialog_response_cb)
        
        # This avoids an error if the dialog is destroyed because its
        # parent has been destroyed
        image_chooser.__destroyed = False
        def dialog_destroy_cb(dialog, *etc):
            dialog.__destroyed = True
            
        image_chooser.connect("destroy", dialog_destroy_cb)
        
        image_chooser.present()
        return image_chooser
    
    
    def show_preferences_dialog(self, target_window=None):
        ''' Show the preferences dialog '''
        
        target_window = target_window or self.get_window()
        
        if not self._preferences_dialog:
            self._preferences_dialog = dialog = preferences.Dialog(self)
            
            dialog.connect("response", self._preferences_dialog_responded)
            
        self._preferences_dialog.target_window = target_window
        self._preferences_dialog.present()
    
    
    def _preferences_dialog_responded(self, *data):
        self._preferences_dialog.destroy()
        self._preferences_dialog = None
        preferences.SaveFromApp(self)
        
    
    def get_mouse_handler_dialog(self, handler):
        dialog = self.mouse_handler_dialogs.pop(handler, None)
        if not dialog:
            # Create a new dialog if there is not one
            create_dialog = preferences.MouseHandlerSettingDialog
            handler_data = self.meta_mouse_handler[handler]
            dialog = create_dialog(handler, handler_data)
            self.mouse_handler_dialogs[handler] = dialog
            dialog.connect("response", lambda d, v: d.destroy())
            dialog.connect("destroy", self._mouse_handler_dialog_destroyed)
            
        return dialog
    
    
    def _mouse_handler_dialog_destroyed(self, dialog, *data):
        self.mouse_handler_dialogs.pop(dialog.handler, None)
        
        
    def _removed_mouse_handler(self, meta, handler):
        dialog = self.mouse_handler_dialogs.pop(handler, None)
        if dialog:
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
        
        dialog.run()
        dialog.destroy()
        
        
    def get_window(self):
        windows = self.get_windows() # XP, Vista, 7, 8?
        if windows:
            # Return most recently focused window
            return windows[0]
        else:
            # Create a window and return it
            try:
                a_window = self.create_window()
            
            except Exception:
                # Doing this because I'm tired of ending up with a
                # frozen process when an exception occurs in the 
                # ViewerWindow constructor. Meaning a_window it doesn't get set
                # and thus a window not shown, but since the ApplicationWindow
                # constructor comes before any errors it gets added to the
                # application windows list, and the application will not quit
                # while the list is not empty.</programmerrage>
                applogger.log_error("Could not create the first window")
                windows = self.get_windows()
                if len(windows) > 0:
                    self.remove_window(windows[0])
                    
                raise
                
            a_window.show()
            image_view = a_window.view
            image_view.mouse_adapter = mousing.MouseAdapter(image_view)
            self.meta_mouse_handler.attach(image_view.mouse_adapter)
            
            try:
                fillscreen = self.settings["window"].data["start-fullscreen"]
                a_window.set_fullscreen(fillscreen)
            except KeyError:
                pass
                
            return a_window
    
    
    def create_window(self):
        """ Creates a new ViewerWindow and returns it """
        result = ViewerWindow(self)
        self.emit("new-window", result)
        return result
    
    
    def create_view(self):
        """ Creates a new ImageView and returns it """
        result = viewing.ImageView()
        self.emit("new-view", result)
        return result
    
    
    def queue_memory_check(self, *data):
        if not self.memory_check_queued:
            self.memory_check_queued = True
            GObject.idle_add(self.memory_check)
            
            
    def memory_check(self):
        logger = notifying.Logger("loading")
        
        self.memory_check_queued = False
        
        while self.memory.enlisted_stuff:
            enlisted_thing = self.memory.enlisted_stuff.pop()
            enlisted_thing.connect("finished-loading", self.log_loading_finish)
                
        if self.memory.unlisted_stuff or self.memory.unused_stuff:
            while self.memory.unlisted_stuff:
                unlisted_thing = self.memory.unlisted_stuff.pop()
                if unlisted_thing.is_loading or unlisted_thing.on_memory:
                    unlisted_thing.unload()
                    logger.debug(notifying.Lines.Unloaded(unlisted_thing))
                    
            while self.memory.unused_stuff:
                unused_thing = self.memory.unused_stuff.pop()
                # Do not unload things that are not on disk (like pastes)
                if unused_thing.on_disk:
                    if unused_thing.is_loading or unused_thing.on_memory:
                        unused_thing.unload()
                        logger.debug(notifying.Lines.Unloaded(unused_thing))
                        
            gc.collect()
            
        while self.memory.requested_stuff:
            requested_thing = self.memory.requested_stuff.pop()
            if not (requested_thing.is_loading or requested_thing.on_memory):
                requested_thing.load()
                logger.debug(notifying.Lines.Loading(requested_thing))
                
        return False
        
        
    def log_loading_finish(self, thing, error):
        logger = notifying.Logger("loading")
        
        if error:
            logger.log_error(notifying.Lines.Error(error))
            
        elif thing.on_memory:
            logger.log(notifying.Lines.Loaded(thing))
    
    
    def _save_settings(self, app_settings):
        utility.SetDictFromProperties(
            self, self.settings.data,
            "zoom-effect", "spin-effect"
        )
    
    def _load_settings(self, app_settings):
        utility.SetPropertiesFromDict(
            self, self.settings.data,
            "zoom-effect", "spin-effect"
        )
    
    def _save_mouse_settings(self, mouse_settings):
        """Populates the .settings["mouse"] .data"""
        mechanisms_data = preferences.GetMouseMechanismsSettings(
            self.meta_mouse_handler
        )
        mouse_settings.data["mechanisms"] = mechanisms_data
    
    
    def _load_mouse_settings(self, mouse_settings):
        
        preferences.LoadMouseMechanismsSettings(
            self, self.meta_mouse_handler, mouse_settings.data["mechanisms"]
        )


class ViewerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        Gtk.ApplicationWindow.__init__(
            self, title=_("Pynorama"), application=app
        )
        self.app = app
        self.set_default_size(600, 600)
        
        # Idly refresh index
        self._refresh_index = utility.IdlyMethod(self._refresh_index)
        self._refresh_transform = utility.IdlyMethod(self._refresh_transform)
        
        # If the user changes the magnification after its set by .autozoom, 
        # then .autozoom isn't called after rotating or resizing the imageview
        self._autozoom_zoom_modified = False
        # This is the rectangle of the frame that has been autozoomed.
        # It is used when reapplying the zoom after the window is resized
        # in order to changing the zoom because the current image changed and
        # so the image size due to the user panning the view
        self._autozoom_locked_rectangle = None
        self._focus_loaded_handler_id = None
        self._old_focused_image = None
        self.opening_context = None
        self.album = organizing.Album()
        self.album.connect("image-added", self._album_image_added_cb)
        self.album.connect("image-removed", self._album_image_removed_cb)
        self.album.connect("order-changed", self._album_order_changed_cb)
        
        # Create layout
        vlayout = Gtk.VBox()
        self.add(vlayout)
        vlayout.show()
        
        # Setup actions
        self.setup_actions()
        
        self.uimanager.add_ui_from_string(ViewerWindow.ui_description)
        self.menubar = self.uimanager.get_widget("/menubar")
        self.toolbar = self.uimanager.get_widget("/toolbar")
        
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
        
        self.view = app.create_view()
        # Setup a bunch of reactions to all sorts of things
        self.view.connect("notify::magnification", self._changed_magnification)
        self.view.connect("notify::rotation", self._reapply_autozoom)
        self.view.connect("size-allocate", self._reapply_autozoom)
        self.view.connect("notify::magnification", self._changed_view)
        self.view.connect("notify::rotation", self._changed_view)
        self.view.connect("notify::horizontal-flip", self._changed_view)
        self.view.connect("notify::vertical-flip", self._changed_view)
        
        self.view_scroller.add(self.view)
        self.view_scroller.show_all()
        
        vlayout.pack_start(self.view_scroller, True, True, 0)
        
        # Add a status bar, the statusbar box and a statusbar box box
        self.statusbarboxbox = Gtk.Box()
        self.statusbarboxbox.set_orientation(Gtk.Orientation.VERTICAL)
        separator = Gtk.Separator()
        self.statusbarboxbox.pack_start(separator, False, False, 0)
        
        self.statusbarbox = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        self.statusbarbox.set_spacing(8)
        
        # With a label for image index
        self.index_label = Gtk.Label()
        self.index_label.set_alignment(1, 0.5)
        self.index_label.set_tooltip_text(_("""The index of the current image \
/ the album image count"""))
        self.statusbarbox.pack_start(self.index_label, False, True, 0)
        
        # And a spinner for loading hint
        self.loading_spinner = Gtk.Spinner()
        self.statusbarbox.pack_start(self.loading_spinner, False, True, 0)
        
        self.statusbar = Gtk.Statusbar()
        self.statusbarbox.pack_start(self.statusbar, True, True, 0)
        
        # And a label for the image transformation
        transform_labels = (
            Gtk.Label(),
            Gtk.Label(), Gtk.Label(), Gtk.Label(), Gtk.Label()
        )
        for a_label in transform_labels:
            self.statusbarbox.pack_end(a_label, False, True, 0)
        
        self.flip_label, self.angle_label, self.zoom_label, \
            self.size_label, self.status_label = transform_labels
        
        self.size_label.set_tooltip_text(_("Image width×height"))
        self.flip_label.set_tooltip_text(_("Direction the image is flipped"))
        self.zoom_label.set_tooltip_text(_("Image magnification"))
        self.angle_label.set_tooltip_text(_("Rotation in degrees"))
        
        statusbarboxpad = Gtk.Alignment()
        statusbarboxpad.set_padding(3, 3, 12, 12)
        statusbarboxpad.add(self.statusbarbox)
        
        self.statusbarboxbox.pack_end(statusbarboxpad, False, True, 0)
        
        # Show status
        vlayout.pack_end(self.statusbarboxbox, False, True, 0)
        
        self.statusbarboxbox.show_all()
        self.loading_spinner.hide()
        
        # DnD setup
        # TODO: Allow this to be extensible
        self.view.drag_dest_set(
            Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY
        )
        target_list = Gtk.TargetList.new([])
        target_list.add_image_targets(DND_IMAGE, False)
        target_list.add_uri_targets(DND_URI_LIST)
        
        self.view.drag_dest_set_target_list(target_list)
        self.view.connect("drag-data-received", self._dnd_received_cb)
        
        
        # Setup layout stuff
        self.layout_dialog = None
        self.avl = organizing.AlbumViewLayout(
            album=self.album, view=self.view
        )
        
        self.avl.connect("notify::layout", self._layout_changed)
        self.avl.connect("focus-changed", self._focus_changed)
        
        # Build layout menu
        self._layout_action_group = None
        self._layout_ui_merge_id = None
        self._layout_options_merge_ids = dict()
        self._layout_options_codenames = []
        
        other_option = self.actions.get_action("layout-other-option")
        other_option.connect("changed", self._layout_option_chosen)
        
        option_list = self.app.components["layout-option"]
        for an_index, an_option in enumerate(option_list):
            a_merge_id = self.uimanager.new_merge_id()
            
            # create action
            an_action_name = "layout-option-" + an_option.codename
            an_action = Gtk.RadioAction(
                an_action_name, an_option.label, an_option.description,
                None, an_index
            )
            
            an_action.join_group(other_option)
            self.actions.add_action(an_action)
            
            # Insert UI
            self.uimanager.add_ui(
                a_merge_id,
                "/ui/menubar/view/layout/layout-options",
                an_action_name, # the item name
                an_action_name, # the action name
                Gtk.UIManagerItemType.MENUITEM,
                False
            )
            
            self._layout_options_merge_ids[an_option] = a_merge_id
            self._layout_options_codenames.append(an_option.codename)
            
        # Bind properties
        bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
        sync_flag = GObject.BindingFlags.SYNC_CREATE
        get_action = self.actions.get_action
        utility.Bind(self,
            ("sort-automatically", self.album, "autosort"),
            ("reverse-ordering", self.album, "reverse"),
            ("toolbar-visible", self.toolbar, "visible"),
            ("statusbar-visible", self.statusbarboxbox, "visible"),
            ("reverse-ordering", get_action("sort-reverse"), "active"),
            ("sort-automatically", get_action("sort-auto"), "active"),
            ("ordering-mode", get_action("sort-name"), "current-value"),
            ("toolbar-visible", get_action("ui-toolbar"), "active"),
            ("statusbar-visible", get_action("ui-statusbar"), "active"),
            ("autozoom-enabled", get_action("autozoom-enable"), "active"),
            ("autozoom-mode", get_action("autozoom-fit"), "current-value"),
            ("autozoom-can-minify", get_action("autozoom-magnify"), "active"),
            ("autozoom-can-magnify", get_action("autozoom-minify"), "active"),
            bidirectional=True, synchronize=True
        )
        
        self.view.bind_property(
            "current-interpolation-filter",
            get_action("interp-nearest"), "current-value",
            bidi_flag
        )
        self.view.bind_property(
            "zoomed",
            get_action("interpolation"), "sensitive",
            bidi_flag | sync_flag
        )
        
        
        self.connect("notify::autozoom-enabled", self._changed_autozoom)
        self.connect("notify::autozoom-mode", self._changed_autozoom)
        self.connect("notify::autozoom-can-magnify", self._changed_autozoom)
        self.connect("notify::autozoom-can-minify", self._changed_autozoom)
        self.connect("notify::vscrollbar-placement", self._changed_scrollbars)
        self.connect("notify::hscrollbar-placement", self._changed_scrollbars)
        self.connect("notify::ordering-mode", self._changed_ordering_mode)
        self.connect("notify::layout-option", self._changed_layout_option)
        
        self.album.connect("notify::comparer", self._changed_album_comparer)
        
        # Load preferences
        other_option.set_current_value(0)
        preferences.LoadForWindow(self)
        preferences.LoadForView(self.view, self.app.settings)
        preferences.LoadForAlbum(self.album, self.app.settings)
        
        # Refresh status widgets
        self._refresh_transform()
        self._refresh_index()
        
        
    def setup_actions(self):
        self.uimanager = Gtk.UIManager()
        self.uimanager.connect("connect-proxy",
                             lambda ui, a, w: self.connect_to_statusbar(a, w))
        
        self.accelerators = self.uimanager.get_accel_group()
        self.add_accel_group(self.accelerators)
        self.actions = Gtk.ActionGroup("pynorama")
        self.uimanager.insert_action_group(self.actions)
        
        action_params = [
        # File Menu
        ("file", _("_File"), None),
            ("open", _("_Open..."),
                _("Opens an image in the viewer"), Gtk.STOCK_OPEN),
            ("paste", _("_Paste"),
                _("Shows an image from the clipboard"), Gtk.STOCK_PASTE),
            # Ordering submenu
            ("ordering", _("Or_dering"), _("Image ordering settings")),
                ("sort", _("_Sort Images"),
                    _("Sorts the images currently loaded")),
                ("sort-auto", _("Sort _Automatically"),
                 _("Sorts images as they are added")),
                 ("sort-reverse", _("_Reverse Order"),
                    _("Reverts the image order")),
                ("sort-name", _("By _Name"),
                    _("Compares filenames and number sequences but not dots")),
                ("sort-char", _("By _Characters"),
                    _("Only compares characters in filenames")),
                ("sort-file-date", _("By _Modification Date"),
                    _("Compares dates when images were last modified")),
                ("sort-file-size", _("By _File Size"),
                    _("Compares files byte size")),
                ("sort-img-size", _("By Image Si_ze"),
                    _("Compares images pixel count, or width times height")),
                ("sort-img-width", _("By Image _Width"),
                    _("Compares images width"), None),
                ("sort-img-height", _("By Image _Height"),
                    _("Compares images height")),
            ("copy", _("_Copy"),
                _("Copies an image into the clipboard"), Gtk.STOCK_COPY),
            ("remove", _("_Remove"),
                _("Removes the image from the viewer"), Gtk.STOCK_CLOSE),
            ("clear", _("R_emove All"),
                _("Removes all images from the viewer"), Gtk.STOCK_CLEAR),
            ("quit", _("_Quit"), _("Exits the program"), Gtk.STOCK_QUIT),
        # Go menu
        ("go", _("_Go"), None),
            ("go-previous", _("P_revious Image"),
                _("Loads the previous image"), Gtk.STOCK_GO_BACK),
            ("go-next", _("Nex_t Image"),
                _("Loads the next image"), Gtk.STOCK_GO_FORWARD),
            ("go-first", _("Fir_st Image"),
                _("Loads the first image"), Gtk.STOCK_GOTO_FIRST),
            ("go-last", _("L_ast Image"),
                _("Loads the last image"), Gtk.STOCK_GOTO_LAST),
            ("go-random", _("A_ny Image"),
                _("Loads some random image"), Gtk.STOCK_GOTO_LAST),
        # View menu
        ("view", _("_View"), None),
            ("zoom-in", _("Zoom _In"),
                _("Makes the image look larger"), Gtk.STOCK_ZOOM_IN),
            ("zoom-out", _("Zoom _Out"),
                _("Makes the image look smaller"), Gtk.STOCK_ZOOM_OUT),
            ("zoom-none", _("No _Zoom"),
                _("Shows the image at it's normal size"), Gtk.STOCK_ZOOM_100),
            # autozoom submenu
            ("autozoom", _("_Automatic Zoom"), 
                    _("Automatic zooming features")),
                ("autozoom-enable", _("Enable _Automatic Zoom"),
                    _("Enables the automatic zoom features")),
                ("autozoom-fit", _("Fi_t Image"),
                    _("Fits the image completely inside the window")),
                ("autozoom-fill", _("Fi_ll Window"),
                    _("Fills the window completely with the image")),
                ("autozoom-match-width", _("Match _Width"),
                    _("Gives the image the same width as the window")),
                ("autozoom-match-height", _("Match _Height"),
                    _("Gives the image the same height as the window")),
                ("autozoom-minify", _("Mi_nify Large Images"),
                    _("Let the automatic zoom minify images")),
                ("autozoom-magnify", _("Ma_gnify Small Images"),
                    _("Let the automatic zoom magnify images")),
            # Transform submenu
            ("transform", _("_Transform"), _("Viewport transformation")),
                ("rotate-cw", _("_Rotate Clockwise"),
                    _("Turns the top side to the right side")),
                ("rotate-ccw", _("Rotat_e Counter Clockwise"),
                    _("Turns the top side to the left side")),
                ("flip-h", _("Flip _Horizontally"), 
                    _("Inverts the left and right sides")),
                ("flip-v", _("Flip _Vertically"),
                    _("Inverts the top and bottom sides")),
                ("transform-reset", _("Re_set"),
                    _("Resets the view transform")),
            # Interpolation submenu
            ("interpolation", _("Inter_polation"),
                    _("Pixel interpolation settings")),
                ("interp-nearest", _("_Nearest Neighbour Filter"),
                    _("A filter that does not blend pixels")),
                ("interp-bilinear", _("_Bilinear Filter"),
                    _("A filter that blends pixels in a linear way")),
                ("interp-fast", _("Fa_ster Fil_ter"),
                    _("A fast interpolation filter")),
                ("interp-good", _("B_etter Filt_er"),
                    _("A good interpolation filter")),
                ("interp-best", _("St_ronger Filte_r"),
                    _("The best interpolation filter avaiable")),
             # Layout submenu
            ("layout", _("_Layout"), _("Album layout settings")),
                ("layout-other-option","", "", None),
                ("layout-configure", _("_Configure..."),
                    _("Shows a dialog to configure the current album layout"),
                    None),
            # Interface submenu
            ("interface", _("_Interface"),
                    _("This window settings")),
                ("ui-toolbar", _("T_oolbar"),
                    _("Displays a toolbar with tools")),
                ("ui-statusbar", _("Stat_usbar"),
                    _("Displays a statusbar with status")),
                ("ui-scrollbar-top", _("_Top Scroll Bar"),
                    _("Displays the horizontal scrollbar at the top side")),
                ("ui-scrollbar-bottom", _("_Bottom Scroll Bar"),
                    _("Displays the horizontal scrollbar at the bottom side")),
                ("ui-scrollbar-left", _("Le_ft Scroll Bar"),
                    _("Displays the vertical scrollbar at the left side")),
                ("ui-scrollbar-right", _("Rig_ht Scroll Bar"),
                    _("Displays the vertical scrollbar at the right side")),
                ("ui-keep-above", _("Keep Ab_ove"),
                    _("Keeps this window above other windows")),
                ("ui-keep-below", _("Keep Be_low"),
                    _("Keeps this window below other windows")),
            ("preferences", _("_Preferences..."),
                _("Shows Pynorama preferences dialog"),
                Gtk.STOCK_PREFERENCES),
            ("fullscreen", _("_Fullscreen"),
               _("Fills the entire screen with this window"),
               Gtk.STOCK_FULLSCREEN),
        ("help", _("_Help"),
                _("Help! I'm locked inside an image viewer!" + 
                "I have wife and children! Please, save me!!!")),
            ("about", _("_About"),
                _("Shows the about dialog"), Gtk.STOCK_ABOUT),
        ]
        
        signaling_params = {
            "open" : (lambda w: self.show_open_image_dialog(),),
            "paste" : (lambda w: self.paste(),),
            "copy": (lambda w: self.copy_image(),),
            "sort" : (lambda data: self.album.sort(),),
            "sort-reverse" : (self._toggled_reverse_sort,),
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
            "rotate-cw" : (lambda data: self.rotate_view(1),),
            "rotate-ccw" : (lambda data: self.rotate_view(-1),),
            "flip-h" : (lambda data: self.flip_view(False),),
            "flip-v" : (lambda data: self.flip_view(True),),
            "transform-reset" : (lambda data: self.reset_view_transform(),),
            "layout-configure" : (self.show_layout_dialog,),
            "ui-scrollbar-top" : (self._toggled_hscroll,),
            "ui-scrollbar-bottom" : (self._toggled_hscroll,),
            "ui-scrollbar-left" : (self._toggled_vscroll,),
            "ui-scrollbar-right" : (self._toggled_vscroll,),
            "ui-keep-above" : (self.toggle_keep_above,),
            "ui-keep-below" : (self.toggle_keep_below,),
            "preferences" : (lambda data:
                             self.app.show_preferences_dialog(self),),
            "fullscreen" : (self.toggle_fullscreen,),
            "about" : (lambda data: self.app.show_about_dialog(self),),
        }
        
        sort_group, interp_group, zoom_mode_group = [], [], []
        hscroll_group, vscroll_group = [], []
        
        toggleable_actions = {
            "sort-auto" : None,
            "sort-reverse" : None,
            "autozoom-enable" : None,
            "autozoom-fit" : (ZoomMode.FitContent, zoom_mode_group),
            "autozoom-fill" : (ZoomMode.FillView, zoom_mode_group),
            "autozoom-match-width" : (ZoomMode.MatchWidth, zoom_mode_group),
            "autozoom-match-height" : (ZoomMode.MatchHeight, zoom_mode_group),
            "autozoom-minify" : None,
            "autozoom-magnify" : None,
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
            "layout-other-option" : (-1, []),
            "ui-statusbar" : None,
            "ui-toolbar" :None,
            "ui-scrollbar-top" : None,
            "ui-scrollbar-bottom" : None,
            "ui-scrollbar-left" : None,
            "ui-scrollbar-right" : None,
            "ui-keep-above" : None,
            "ui-keep-below" : None,
        }
        
        accel_actions = {
            "open" : None,
            "paste" : None,
            "copy" : None,
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
            "autozoom-enable" : "KP_Multiply",
            "rotate-cw" : "R",
            "rotate-ccw" : "<ctrl>R",
            "flip-h" : "F",
            "flip-v" : "<ctrl>F",
            "fullscreen" : "F4",
        }
        
        for an_action_params in action_params:
            if len(an_action_params) == 3:
                name, label, tip = an_action_params
                stock = None
            else:
                name, label, tip, stock = an_action_params
                
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
                    an_action = Gtk.RadioAction(
                        name, label, tip, stock, radio_value
                    )
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
                an_accel = ""
                
            self.actions.add_action_with_accel(an_action, an_accel)

        
    # --- event handling down this line --- #
    def connect_to_statusbar(self, action, proxy):
        ''' Connects an action's widget proxy enter-notify-event to show the
            action tooltip on the statusbar when the widget is hovered '''
            
        try:
            # Connect select/deselect events
            proxy.connect("select", self._tooltip_to_statusbar, action)
            proxy.connect("deselect", self._pop_tooltip_from_statusbar)
            
        except TypeError: # Not a menu item
            pass
            
    def _tooltip_to_statusbar(self, proxy, action):
        ''' Pushes a proxy action tooltip to the statusbar '''
        tooltip = action.get_tooltip()
        if tooltip:
            context_id = self.statusbar.get_context_id("tooltip")
            self.statusbar.pop(context_id)
            self.statusbar.push(context_id, tooltip)
            
    
    def _pop_tooltip_from_statusbar(self, *data):
        context_id = self.statusbar.get_context_id("tooltip")
        self.statusbar.pop(context_id)
    
    
    def _changed_ordering_mode(self, *data):
        #TODO: Use GObject.bind_property_with_closure for this
        new_comparer = organizing.SortingKeys.Enum[self.ordering_mode]
        if self.album.comparer != new_comparer:
            self.album.comparer = new_comparer
            
            if not self.album.autosort:
                self.album.sort()
    
    
    def _changed_album_comparer(self, album, *data):
        sorting_keys_enum = organizing.SortingKeys.Enum
        ordering_mode = sorting_keys_enum.index(album.comparer)
        
        self.ordering_mode = ordering_mode
    
        
    def _toggled_reverse_sort(self, *data):
        if not self.album.autosort:
            self.album.sort()

    
    def _layout_option_chosen(self, radio_action, current_action):
        """Handler for clicking on one of the layout option menu items"""
        current_value = current_action.get_current_value()
        
        if current_value >= 0:
            option_codename = self._layout_options_codenames[current_value]
            self.layout_option = self.app.components[
                "layout-option", option_codename
            ]
    
    def _changed_layout_option(self, *data):
        """notify::layout-option signal handler"""
        current_layout = self.avl.layout
        if not current_layout or \
               current_layout.source_option != self.layout_option:
            current_layout = self.layout_option.create_layout(self.app)
            current_layout.source_option = self.layout_option
            self.avl.layout = current_layout


    def _layout_changed(self, *args):
        """notify::layout signal handler for .avl"""
        
        layout = self.avl.layout
        source_option = layout.source_option
        
        # Synchronizing self.layout_option and layout.source_option
        if self.layout_option != source_option:
            self.layout_option = source_option
            
        # Update the layout options menu with the current layout option index
        codename_to_index = self._layout_options_codenames.index
        try:
            layout_option_index = codename_to_index(source_option.codename)
        except Exception:
            layout_option_index = -1
        other_option = self.actions.get_action("layout-other-option")
        other_option.set_current_value(layout_option_index)
        
        # Destroy a possibly open layout settings dialog
        if self.layout_dialog:
            self.layout_dialog.destroy()
            self.layout_dialog = None
        
        # Remove previosly merged ui/menu items from the menu
        if self._layout_action_group:
            self.uimanager.remove_action_group(self._layout_action_group)
            self.uimanager.remove_ui(self._layout_ui_merge_id)
            self._layout_action_group = None
            self._layout_ui_merge_id = None
        
        if source_option.has_menu_items:
            # Adding action group
            self._layout_action_group = source_option.get_action_group(layout)
            self.uimanager.insert_action_group(self._layout_action_group, -1)
            
            # Merging menu items
            merge_id = self.uimanager.new_merge_id()
            try:
                source_option.add_ui(layout, self.uimanager, merge_id)
            except Exception:
                uilogger.log_error("Error adding layout UI")
                uilogger.log_exception()
                self._layout_action_group = None
                self.uimanager.remove_ui(merge_id)
            else:
                self._layout_ui_merge_id = merge_id
        
        # Set whether the "configure" menu item is sensitive
        configure_action = self.actions.get_action("layout-configure")
        configure_action.set_sensitive(source_option.has_settings_widget)
        
        
    def _toggled_vscroll(self, action, *data):
        left = self.actions.get_action("ui-scrollbar-left")
        right = self.actions.get_action("ui-scrollbar-right")
        if left.get_active() and right.get_active():
            if action is left:
                right.set_active(False)
                
            else:
                left.set_active(False)
                
        new_value = 2 if right.get_active() else 1 if left.get_active() else 0
        self.vscrollbar_placement = new_value
    
        
    def _toggled_hscroll(self, action, *data):
        top = self.actions.get_action("ui-scrollbar-top")
        bottom = self.actions.get_action("ui-scrollbar-bottom")
        if top.get_active() and bottom.get_active():
            if action is top:
                bottom.set_active(False)
                
            else:
                top.set_active(False)
        
        new_value = 2 if bottom.get_active() else 1 if top.get_active() else 0
        self.hscrollbar_placement = new_value


    def _changed_scrollbars(self, *data):
        h = self.hscrollbar_placement
        v = self.vscrollbar_placement
        
        # Refresh actions
        actions = [
            self.actions.get_action("ui-scrollbar-top"),
            self.actions.get_action("ui-scrollbar-right"),
            self.actions.get_action("ui-scrollbar-bottom"),
            self.actions.get_action("ui-scrollbar-left")
        ]
        for an_action in actions:
            an_action.block_activate()
        
        top, right, bottom, left = actions
        left.set_active(v == 1)
        right.set_active(v == 2)
        top.set_active(h == 1)
        bottom.set_active(h == 2)
        
        for an_action in actions:
            an_action.unblock_activate()
        
        # Update scrollbars
        hpolicy = Gtk.PolicyType.NEVER if h == 0 else Gtk.PolicyType.AUTOMATIC
        vpolicy = Gtk.PolicyType.NEVER if v == 0 else Gtk.PolicyType.AUTOMATIC
        
        # This placement is the placement of the scrolled window 
        # child widget in comparison to the scrollbars.
        # Basically everything is inverted and swapped.
        if h == 2:
            # horizontal scrollbar at bottom
            if v == 2:
                # vertical scrollbar at right
                placement = Gtk.CornerType.TOP_LEFT
            else:
                placement = Gtk.CornerType.TOP_RIGHT
                
        else:
            if v == 2:
                placement = Gtk.CornerType.BOTTOM_LEFT
            else:
                placement = Gtk.CornerType.BOTTOM_RIGHT
        
        self.view_scroller.set_policy(hpolicy, vpolicy)
        self.view_scroller.set_placement(placement)
        
        
    def _refresh_index(self):
        focused_image = self.avl.focus_image
        can_copy = can_remove = focused_image is not None
        can_goto_first = False
        can_goto_last = False
        can_previous = False
        can_next = False
            
        if self.album:
            can_remove = True
            
            count = len(self.album)
            count_chr_count = len(str(count))
            
            if focused_image in self.album:
                image_index = self.album.index(focused_image)
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
            ("copy", can_copy),
            ("remove", can_remove),
            ("clear", len(self.album) > 0),
            ("go-next", can_next),
            ("go-previous", can_previous),
            ("go-first", can_goto_first),
            ("go-last", can_goto_last),
            ("go-random", len(self.album) > 1)
        ]
        
        for action_name, sensitivity in sensible_list:
            self.actions.get_action(action_name).set_sensitive(sensitivity)
        
    def _refresh_transform(self):
        focused_image = self.avl.focus_image
        if focused_image:
            if focused_image.is_bad:
                # This just may happen
                status_text = _("Error")
                status_tooltip_text = _("Something went wrong")
                size_text = ""
                
            elif focused_image.on_memory:
                metadata = focused_image.metadata
                # The width and height are from the source
                size_text = "{width}×{height}".format(
                    width=metadata.width, height=metadata.height
                )
                
                status_text, status_tooltip_text = "", ""
                                                
            else:
                # If it's not on memory and then it must be loading
                status_text = _("Loading")
                status_tooltip_text = _("Please wait...")
                size_text = ""
                
            # Set zoom text for zoom label
            mag = round(self.view.magnification, 3)
            if mag:
                zoom_text = _("{zoom:n}×").format(zoom=mag)
                
            else:
                zoom_text = ""
            
            # Set flip symbol for flip label and adjust rotation variable
            rot = self.view.rotation
            hflip, vflip = self.view.flipping
            if hflip or vflip:
                # If the view is flipped in either direction apply this
                # intricate looking math stuff to rotation. Normally, there
                # would be another expression if both are true, but in that
                # is handled beforehand by rotating the view by 180°
                    
                #rot = (rot + (45 - ((rot + 45) % 180)) * 2) % 360
                
                if hflip:
                    flip_text = "↔"
                    
                else:
                    flip_text = "↕"
                    
            else:
                flip_text = ""
                
            # Format angle text for label
            if rot:
                angle_text = _("{degrees:d}°").format(degrees=int(rot))
                
            else:
                angle_text = ""
                
            
            # Set label text, hide labels without text
            self.status_label.set_text(status_text)
            self.status_label.set_tooltip_text(status_tooltip_text)
            
            self.size_label.set_text(size_text)
            self.zoom_label.set_text(zoom_text)
            self.angle_label.set_text(angle_text)
            self.flip_label.set_text(flip_text)
            
            self.status_label.set_visible(bool(status_text))            
            self.size_label.set_visible(bool(size_text))
            self.zoom_label.set_visible(bool(zoom_text))
            self.angle_label.set_visible(bool(angle_text))
            self.flip_label.set_visible(bool(flip_text))
            
        else:
            # Set the status label to "Nothing" and hide all other labels
            # since there is nothing to transform
            
            self.status_label.set_text(_("Nothing"))
            self.status_label.set_tooltip_text(_("Nothing to see here"))
            self.status_label.show()
            
            self.size_label.hide()
            self.zoom_label.hide()
            self.angle_label.hide()
            self.flip_label.hide()
    
    
    def set_view_rotation(self, angle):
        anchor = self.view.get_widget_point()
        pin = self.view.get_pin(anchor)
        self.view.rotation = angle % 360
        self.view.adjust_to_pin(pin)
    
    
    def set_view_zoom(self, magnification):
        anchor = self.view.get_widget_point()
        pin = self.view.get_pin(anchor)
        self.view.magnification = magnification
        self.view.adjust_to_pin(pin)
    
    
    def set_view_flip(self, horizontal, vertical):
        hflip, vflip = self.view.flipping
        
        if hflip != horizontal or vflip != vertical:
            # ih8triGNOMEtricks
            rot = self.view.rotation
            angle_change = (45 - ((rot + 45) % 180)) * 2
        
            # If the image if flipped both horizontally and vertically
            # Then it is rotated 180 degrees
            if horizontal and vertical:
                horizontal = vertical = False
                angle_change += 180
        
            anchor = self.view.get_widget_point()
            pin = self.view.get_pin(anchor)
            if angle_change:
                self.view.rotation = (rot + angle_change) % 360
            
            self.view.flipping = (horizontal, vertical)
            self.view.adjust_to_pin(pin)
    
    
    def zoom_view(self, power):
        ''' Zooms the viewport '''        
        zoom_effect = self.app.zoom_effect
        if zoom_effect and power:
            old_zoom = self.view.magnification
            new_zoom = self.app.zoom_effect ** power * old_zoom
            self.set_view_zoom(new_zoom)
    
    
    def flip_view(self, vertically):
        ''' Flips the viewport '''
        # Horizontal mirroring depends on the rotation of the image
        hflip, vflip = self.view.flipping
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
            self.set_view_rotation(self.view.rotation + change)
    
    
    def reset_view_transform(self):
        self.set_view_flip(False, False)
        self.set_view_rotation(0)
    
    
    def autozoom(self, rectangle=None):
        ''' Zooms automatically! '''
        
        can_minify = self.autozoom_can_minify
        can_magnify = self.autozoom_can_magnify
        view = self.view
        if can_minify or can_magnify:
            if rectangle is None:
                frame = self.avl.focus_frame
                if frame:
                    rectangle = frame.rectangle
                
            if rectangle is not None:
                rotated_rectangle = rectangle.spin(math.radians(view.rotation))
                new_zoom = view.zoom_for_size(
                    (rotated_rectangle.width, rotated_rectangle.height),
                    self.autozoom_mode
                )
                
                will_minify_zoom = can_minify and new_zoom > 1
                will_magnify_zoom = can_magnify and new_zoom < 1
                if will_minify_zoom or will_magnify_zoom:
                    view.magnification = new_zoom
                    self._autozoom_zoom_modified = False
                    self._autozoom_locked_rectangle = rectangle
                else:
                    # Should this be here?
                    view.magnification = 1
    
    
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
        image_count = len(self.album)
        if image_count > 1:
            # Gets a new random index that is not the current one
            random_int = random.randint(0, image_count - 2)
            image_index = self.avl.album.index(self.avl.focus_image)
            if random_int >= image_index:
                random_int += 1
            
            self.avl.go_index(random_int)
    
    
    def handle_clear(self, *data):
        del self.album[:]
    
    
    def handle_remove(self, *data):
        focus = self.avl.focus_image
        if focus:
            self.album.remove(focus)
    
    
    def copy_image(self, clipboard=None):
        """ Copies the focus image to the clipboard """
        focus = self.avl.focus_image
        if focus:
            if clipboard is None:
                clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                
            focus.copy_to_clipboard(clipboard)
    
    
    def open_uris(self,
                  uris,
                  openers=None,
                  replace=False,
                  search_siblings=False,
                  go_to_first=True):
        """
        Opens a set of URIs and adds their results to this window album
        
        """
        
        uri_list = list(uris)
        if uri_list:
            # Logging just because
            uilogger.log("Opening %d URI(s)" % len(uri_list))
            uilogger.debug_list(uri_list)
            uilogger.debug("Parameters")
            uilogger.debug_dict({
                "Replace": replace,
                "Sibling Search": search_siblings,
                "Go to First": go_to_first
            })
            
            if openers is None:
                uilogger.debug("All openers included")
                openers = self.app.components["file-opener"]
            else:
                uilogger.debug("Selected openers")
                uilogger.debug_list(openers)
            
            if replace:
                del self.album[:]
            
            opening_context = self.get_opening_context()
            if not opening_context.__added_already:
                self.app.opener.handle(opening_context, album=self.album)
                opening_context.__added_already = True
            
            newest_session = opening_context.get_new_session()
            newest_session.search_siblings = search_siblings
            newest_session.add(openers=openers, uris=uri_list)
            opening_context.__go_to_uri = uri_list[0] if go_to_first else None
    
    
    def open_files(self,
                  files,
                  openers=None,
                  replace=False,
                  search_siblings=False,
                  go_to_first=True):
        """
        Opens a set of GFiles and adds their results to this window album
        
        """
        
        file_list = list(files)
        if file_list:
            # Logging just because
            uilogger.log("Opening %d GFile(s)" % len(file_list))
            uilogger.debug_list(a_file.get_uri() for a_file in file_list)
            uilogger.debug("Parameters")
            uilogger.debug_dict({
                "Replace": replace,
                "Sibling Search": search_siblings,
                "Go to First": go_to_first
            })
            
            if openers is None:
                uilogger.debug("All openers included")
                openers = self.app.components["file-opener"]
            else:
                uilogger.debug("Selected openers")
                uilogger.debug_list(openers)
            
            if replace:
                del self.album[:]
            
            opening_context = self.get_opening_context()
            if not opening_context.__added_already:
                self.app.opener.handle(opening_context, album=self.album)
                opening_context.__added_already = True
            
            newest_session = opening_context.get_new_session()
            newest_session.search_siblings = search_siblings
            newest_session.add(openers=openers, files=file_list)
            if go_to_first:
                opening_context.__go_to_uri = file_list[0].get_uri()
            else:
                opening_context.__go_to_uri = None
    
    def paste(self, clipboard=None):
        """ Pastes something from a clipboard """
        uilogger.log("Pasting...")
        if clipboard is None:
            # Get default clipboard
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            
        results = self.app.opener.open_clipboard(clipboard)
        if results.completed:
            self._completed_paste_results_cb(results)
        else:
            results.connect("completed", self._completed_paste_results_cb)
    
    
    def show_open_image_dialog(self):
        """ Shows the open image dialog for this window """
        opening_context = self.get_opening_context()
        
        try:
            dialog = opening_context.__open_dialog
        except AttributeError:
            # Show an open dialog
            opening_context.hold_open()
            
            dialog = self.app.show_open_image_dialog(
                self._open_dialog_open_cb,
                self._open_dialog_add_cb,
                None,
                self,
                opening_context
            )
            opening_context.__open_dialog = dialog
            
            dialog.connect("destroy", self._open_dialog_destroy_cb)
        else:
            dialog.present()
    
    
    def get_opening_context(self):
        """
        Returns this window OpeningContext creating one
        if it doesn't already exists.
        
        """
        if not self.opening_context:
            uilogger.debug("Creating new opening context")
            new_context = opening.OpeningContext()
            new_context.__added_already = False
            new_context.__go_to_uri = None
            new_context.connect("finished", self._opening_context_finished_cb)
            self.opening_context = new_context
            
        return self.opening_context
    
    
    def show_layout_dialog(self, *data):
        ''' Shows a dialog with the layout settings widget '''
        
        if self.layout_dialog:
            self.layout_dialog.present()
            
        else:
            layout = self.avl.layout
            source_option = layout.source_option
            flags = Gtk.DialogFlags
            try:
                widget = source_option.create_settings_widget(layout)
                widget.connect(
                    "destroy", self._layout_widget_destroyed, layout
                )
                
            except Exception:
                message = _("Could not create layout settings dialog!")
                uilogger.log_error(message)
                uilogger.log_exception()
                
                dialog = Gtk.MessageDialog(
                    self, flags.MODAL | flags.DESTROY_WITH_PARENT,
                    Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
                    message
                )
                dialog.run()
                dialog.destroy()
            
            else:
                dialog = Gtk.Dialog(
                    _("Layout Settings"), self, flags.DESTROY_WITH_PARENT,
                    (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
                )
                
                widget_pad = widgets.PadDialogContent(widget)
                widget_pad.show()
                content_area = dialog.get_content_area()
                content_area.pack_start(widget_pad, True, True, 0)
                
                dialog.connect("response", self._layout_dialog_response)
                dialog.present()
                
                self.layout_dialog = dialog
    
    
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
        # Saves this window preferences
        preferences.SaveFromWindow(self)
        preferences.SaveFromAlbum(self.album, self.app.settings)
        preferences.SaveFromView(self.view, self.app.settings)
        layout = self.avl.layout
        try:
            # Tries to save the layout preferences
            source_option = layout.source_option
            source_option.save_preferences(layout)
        except Exception:
            uilogger.log_error("Error destroying window")
            uilogger.log_exception()
        
        # Clean up the avl
        self.avl.clean()
        return Gtk.Window.do_destroy(self)
    
    
    #~ Album/view/layout stuff down this line ~#
    
    def _layout_widget_destroyed(self, widget, layout):
        layout.source_option.save_preferences(layout)
    
    
    def _layout_dialog_response(self, *data):
        self.layout_dialog.destroy()
        self.layout_dialog = None
    
    
    def _album_image_added_cb(self, album, image, index):
        image.lists += 1
        self._refresh_index.queue()
        
        if self.opening_context and self.opening_context.__go_to_uri:
            if image.matches_uri(self.opening_context.__go_to_uri):
                uilogger.debug("Going to image matching opening context URI")
                self.opening_context.__go_to_uri = None
                self.avl.go_image(image)
            
        elif self.avl.focus_image is None:
            uilogger.debug("No focus image, going to newly added image.")
            self.avl.go_image(image)
        
        
    def _album_image_removed_cb(self, album, image, index):
        image.lists -= 1
        self._refresh_index.queue()
        
        
    def _album_order_changed_cb(self, album):
        self._refresh_index.queue()


    def _focus_changed(self, avl, focused_image, hint):
        if self._focus_loaded_handler_id:
            self._old_focused_image.disconnect(self._focus_loaded_handler_id)
            self._focus_loaded_handler_id = None
        
        self._old_focused_image = focused_image
        self._focus_hint = hint
        
        self._refresh_index.queue()
        self.refresh_title(focused_image)
        
        loading_ctx = self.statusbar.get_context_id("loading")
        self.statusbar.pop(loading_ctx)
        
        if focused_image:
            if focused_image.on_memory or focused_image.is_bad:
                self.loading_spinner.hide()
                self.loading_spinner.stop()
                
                # Show error in status bar #
                if focused_image.error:
                    message = notifying.Lines.Error(focused_image.error)
                    self.statusbar.push(loading_ctx, message)
                    
                # Refresh frame #
                self._refresh_focus_frame()
            
            else:
                # Show loading hints #
                message = notifying.Lines.Loading(focused_image)
                self.statusbar.push(loading_ctx, message)
                self.loading_spinner.show()
                self.loading_spinner.start() # ~like a record~
                
                self._refresh_transform.queue()
                
                self._focus_loaded_handler_id = focused_image.connect(
                    "finished-loading", self._focus_loaded
                )
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
                message = notifying.Lines.Error(error)
                self.statusbar.push(loading_ctx, message)
                
            # Refresh frame #
            self._refresh_focus_frame()
                
        self._old_focused_image.disconnect(self._focus_loaded_handler_id)
        self._focus_loaded_handler_id = None
        
    def _refresh_focus_frame(self):
        if not self._focus_hint:
            if self.autozoom_enabled:
                self.autozoom()
                
            self._focus_hint = True
            
        self._refresh_transform.queue()
    
    
    #~ UI related callbacks down this line ~#
    
    def _dnd_received_cb(self, widget, ctx, x, y, selection, info, time):
        """ Callback for drag'n'drop "received" event """
        uilogger.log("Drag'n'dropping...")
        results = self.app.opener.open_selection(selection)
        if results.completed:
            self._completed_drop_results_cb(results)
        else:
            results.connect("completed", self._completed_drop_results_cb)
    
    
    def _completed_drop_results_cb(self, results, *etc):
        """
        Callback for the opening results of a drag'n'drop "complete" signal
        
        """
        if results.uris:
            uilogger.log("Found URIs in drop")
            is_single_uri = len(results.uris) == 1
            is_trigger = not self.get_opening_context().__added_already
            self.open_uris(
                results.uris, 
                replace=is_trigger,
                search_siblings=is_single_uri
            )
        
        if results.images:
            uilogger.log("Found images in drop")
            # TODO: Implement something so that ImageSources
            # don't have to be "manually" added to the memory thingy...
            # actually reimplement the entire memory management thingy.
            self.app.memory.observe_stuff(results.images)
            self.album.extend(results.images)
        
        if results.errors:
            uilogger.log_error("There were errors opening the drop")
            for e in results.errors:
                uilogger.log_exception(e)
        
        if results.empty:
            uilogger.log_error("Found nothing in drop")
    
    
    def _completed_paste_results_cb(self, results, *etc):
        """
        Callback for the opening results of a paste "complete" signal
        
        """
        if results.uris:
            uilogger.log("Found URIs in paste")
            self.open_uris(results.uris)
        
        if results.images:
            uilogger.log("Found images in paste")
            # TODO: Implement something so that ImageSources
            # don't have to be "manually" added to the memory thingy...
            # actually reimplement the entire memory management thingy.
            self.app.memory.observe_stuff(results.images)
            self.album.extend(results.images)
        
        if results.errors:
            uilogger.log_error("There were errors opening the paste")
            for e in results.errors:
                uilogger.log_exception(e)
        
        if results.empty:
            uilogger.log_error("Found nothing in paste")
    
    
    def _opening_context_finished_cb(self, context):
        assert self.opening_context is context, (self.opening_context, context)
        # If the center image is none for some reason, then it changes the
        # center image to the first image in the sorted album
        
        uilogger.log("Opening context finished")
        avl = self.avl
        if avl.focus_image is None:
            avl.album.sort()
            try:
                first_image = avl.album[0]
            except IndexError:
                pass
            else:
                uilogger.debug("No focus image, going to first image.")
                avl.go_image(first_image)
        
        self.opening_context = None
    
    
    def _open_dialog_open_cb(self, uris, openers, *etc):
        opening_context = self.get_opening_context()
        replace = not opening_context.__added_already
        search_siblings = replace and len(uris) == 1
        self.open_uris(
            uris,
            openers=openers,
            replace=replace,
            search_siblings=search_siblings
         )
    
    
    def _open_dialog_add_cb(self, uris, openers, *etc):
        opening_context = self.get_opening_context()
        self.open_uris(uris, openers=openers)
        return True
    
    
    def _open_dialog_destroy_cb(self, open_dialog):
        """
        Let the opening context emit the "finished" signal after the open
        dialog is destroyed.
        
        """
        context = self.get_opening_context()
        try:
            ctx_dialog = context.__open_dialog
        except AttributeError:
            pass
        else:
            if open_dialog is ctx_dialog:
                del context.__open_dialog
                context.let_close()
    
    
    #--- Properties down this line ---#
    
    view = GObject.Property(type=viewing.ImageView)
    album = GObject.Property(type=organizing.Album)
    
    sort_automatically = GObject.Property(type=bool, default=True)
    ordering_mode = GObject.Property(type=int, default=0)
    reverse_ordering = GObject.Property(type=bool, default=False)
    
    toolbar_visible = GObject.Property(type=bool, default=True)
    statusbar_visible = GObject.Property(type=bool, default=True)
    hscrollbar_placement = GObject.Property(type=int, default=1) 
    vscrollbar_placement = GObject.Property(type=int, default=1)
    
    autozoom_enabled = GObject.Property(type=bool, default=True)
    autozoom_can_minify = GObject.Property(type=bool, default=True)
    autozoom_can_magnify = GObject.Property(type=bool, default=False)
    autozoom_mode = GObject.Property(type=int, default=0)
    
    layout_option = GObject.Property(type=object)
    
    def get_fullscreen(self):
        return self.actions.get_action("fullscreen").get_active()
        
    def set_fullscreen(self, value):
        self.actions.get_action("fullscreen").set_active(value)
    
    
    def _reapply_autozoom(self, *data):
        if self.autozoom_enabled and not self._autozoom_zoom_modified:
            self.autozoom(self._autozoom_locked_rectangle)
    
    def _changed_autozoom(self, *data):
        if self.autozoom_enabled:
            self.autozoom()
    
    def _changed_view(self, widget, data):
        self._refresh_transform.queue()
    
    def _changed_magnification(self, widget, data=None):
        self._autozoom_zoom_modified = True
        self._autozoom_locked_rectangle = None
    
    
    ui_description = '''\
<ui>
    <menubar>
        <menu action="file">
            <menuitem action="open" />
            <menuitem action="paste" />
            <separator />
            <menuitem action="copy" />
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
            <menu action="autozoom" >
                <menuitem action="autozoom-enable" />
                <separator />
                <menuitem action="autozoom-fit" />
                <menuitem action="autozoom-fill" />
                <menuitem action="autozoom-match-width" />
                <menuitem action="autozoom-match-height" />
                <separator />
                <menuitem action="autozoom-magnify" />
                <menuitem action="autozoom-minify" />
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
            <menu action="layout">
                <placeholder name="layout-options"/>
                <separator />
                <menuitem action="layout-configure" />
                <separator />
                <placeholder name="layout-configure-menu"/>
            </menu>
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
