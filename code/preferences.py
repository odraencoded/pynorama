""" preferences.py contains the settings dialog
    and preferences loading methods. """

""" ...and this file is part of Pynorama.
    
    Pynorama is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    Pynorama is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with Pynorama. If not, see <http://www.gnu.org/licenses/>. """

from gi.repository import Gtk, GObject
from gettext import gettext as _
import os
import organization, notification, mousing, utility

logger = notification.Logger("preferences")

class Dialog(Gtk.Dialog):
    def __init__(self, app):
        Gtk.Dialog.__init__(
            self, _("Pynorama Preferences"), None,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        )
        
        self.set_default_size(400, 400)
        self.app = app
        self.mm_handler = self.app.meta_mouse_handler
        
        # Variables to remember what to remove or disconnect later.
        # Treeiters for mouse handlers, signal ids from mm_handler and
        # signal ids from individual mouse handlers
        self._mouse_handler_iters = dict()
        self._mm_handler_signals = list()
        self._mouse_handler_signals = dict()
        
        # TODO: Check if do_destroy can be used instead
        self.connect("destroy", self._do_destroy)
        
        
        #=== Setup view tab down this line ===#
        
        alignment_label = Gtk.Label(_("Image alignment"))
        alignment_tooltip = _("""This alignment setting is \
used for various alignment related things in the program""")
        
        hadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
        vadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
        self.alignment_x_adjust = hadjust
        self.alignment_y_adjust = vadjust
        
        point_scale = PointScale(hadjust, vadjust, square=True)
        view_tab_grid, xspin, yspin = utility.PointScaleGrid(
            point_scale, _("Horizontal"), _("Vertical"),
            corner=alignment_label, align=True
        )
        for a_widget in (point_scale, xspin, yspin):
            a_widget.set_tooltip_text(alignment_tooltip)
        
        label = _("Spin effect")
        spin_effect_label = Gtk.Label(label)
        spin_effect_entry, spin_effect_adjust = utility.SpinAdjustment(
            0, -180, 180, 10, 60, align=True, digits=2, wrap=True
        )
        label = _("Zoom in/out effect")
        zoom_effect_label = Gtk.Label(label)
        zoom_effect_entry, zoom_effect_adjust = utility.SpinAdjustment(
            2, 1, 4, 0.1, 0.25, align=True, digits=2
        )
        
        utility.WidgetGrid(
            (spin_effect_label, spin_effect_entry),
            (zoom_effect_label, zoom_effect_entry),
            align_first=True, expand_first=True,
            grid=view_tab_grid, start_row=1
        )
        
        bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
        sync_flag = GObject.BindingFlags.SYNC_CREATE
        
        
        #=== Setup mouse tab down this line ===#
        
        self._mouse_pseudo_notebook = very_mice_book = Gtk.Notebook()
        very_mice_book.set_show_tabs(False)
        very_mice_book.set_show_border(False)
        
        # This one is used for the labels on top of the pseudo notebook
        mouse_label_notebook = Gtk.Notebook()
        mouse_label_notebook.set_show_tabs(False)
        mouse_label_notebook.set_show_border(False)                
        
        # Add handler list label and widget container
        text = _("""Mouse mechanisms currently in use by the image viewer""")
        view_handlers_description = utility.LoneLabel(text)
        mouse_label_notebook.append_page(view_handlers_description, None)
        
        # Add handler factory list label and widget container
        text = _("""Types of mouse mechanisms currently avaiable \
for the image viewer""")
        brands_description = utility.LoneLabel(text)
        mouse_label_notebook.append_page(brands_description, None)
        
        # Pack both notebooks in the mouse tab
        mouse_tab_stack = utility.WidgetStack(
            mouse_label_notebook, very_mice_book,
            expand=very_mice_book
        )
        
        # Setup handler list tab
        # Create and sync mouse handler list store
        self._handlers_liststore = handlers_liststore = Gtk.ListStore(object)
        for a_handler in self.mm_handler.get_handlers():
            self._add_mouse_handler(a_handler)
        
        # Setup sorting
        handlers_liststore.set_sort_func(0, self._handler_nick_compare_func)
        handlers_liststore.set_sort_column_id(0, Gtk.SortType.ASCENDING)
        
        # Create mouse handler list view, set selection mode to multiple
        self._handlers_listview = handlers_listview = Gtk.TreeView()
        handlers_listview.set_model(handlers_liststore)
        handlers_listview_selection = handlers_listview.get_selection()
        handlers_listview_selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        
        # Create and setup "Nickname" column
        name_renderer = Gtk.CellRendererText()
        name_column = Gtk.TreeViewColumn("Nickname")
        name_column.pack_start(name_renderer, True)
        name_column.set_cell_data_func(
            name_renderer,  self._handler_nick_data_func
        )
        name_column.set_sort_indicator(True)
        name_column.set_sort_column_id(0)
        handlers_listview.append_column(name_column)
        
        # Make it scrollable
        handler_listscroller = Gtk.ScrolledWindow()
        handler_listscroller.add(handlers_listview)
        handler_listscroller.set_shadow_type(Gtk.ShadowType.IN)
        
        # Create the add/remove/configure button box
        new_handler_button, configure_handler_button, remove_handler_button = (
            Gtk.Button.new_from_stock(Gtk.STOCK_NEW),
            Gtk.Button.new_from_stock(Gtk.STOCK_PROPERTIES),
            Gtk.Button.new_from_stock(Gtk.STOCK_DELETE),
        )
        
        # These are insensitive until something is selected
        remove_handler_button.set_sensitive(False)
        configure_handler_button.set_sensitive(False)
        configure_handler_button.set_can_default(True)
        self._configure_handler_button = configure_handler_button
        
        edit_handler_buttonbox = utility.ButtonBox(
            configure_handler_button,
            secondary=[new_handler_button, remove_handler_button]
        )
        
        # Pack widgets into the notebook
        view_handlers_box = utility.WidgetStack(
            handler_listscroller, edit_handler_buttonbox,
            expand=handler_listscroller
        )
        very_mice_book.append_page(view_handlers_box, None)
        
        # Setup add handlers grid (it is used to add handlers)
        brand_liststore = Gtk.ListStore(object)
        
        for a_brand in app.components["mouse-mechanism-brand"]:
            brand_liststore.append([a_brand])
        
        # Setup listview and selection
        self._brand_listview = brand_listview = Gtk.TreeView()
        brand_listview.set_model(brand_liststore)
        brand_selection = brand_listview.get_selection()
        brand_selection.set_mode(Gtk.SelectionMode.BROWSE)
        
        # Add "type" column
        type_column = Gtk.TreeViewColumn("Type")
        label_renderer = Gtk.CellRendererText()
        type_column.pack_start(label_renderer, True)
        type_column.set_cell_data_func(
            label_renderer,  self._brand_label_data_func
        )
        
        brand_listview.append_column(type_column)
        
        # Make it scrollable
        brand_listscroller = Gtk.ScrolledWindow()
        brand_listscroller.add(brand_listview)
        brand_listscroller.set_shadow_type(Gtk.ShadowType.IN)
        
        # Create add/cancel button box
        cancel_add_button, add_button = (
            Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL),
            Gtk.Button.new_from_stock(Gtk.STOCK_ADD),
        )
        add_button.set_can_default(True)
        self._add_handler_button = add_button
        
        add_handler_buttonbox = utility.ButtonBox(
            cancel_add_button, add_button
        )
        
        # Pack widgets into the pseudo notebook
        add_handler_box = utility.WidgetStack(
            brand_listscroller, add_handler_buttonbox,
            expand=brand_listscroller
        )
        very_mice_book.append_page(add_handler_box, None)
        
        # Create tabs
        self.tabs = tabs = Gtk.Notebook()
        tab_specs = [
            (_("View"), view_tab_grid),
            (_("Mouse"), mouse_tab_stack),
        ]
        for a_label, a_stack in tab_specs:
            a_tab_pad = utility.PadNotebookContent(a_stack)
            a_tab_label = Gtk.Label(a_label)
            tabs.append_page(a_tab_pad, a_tab_label)
            
        # Pack tabs into dialog
        padded_tabs = utility.PadDialogContent(tabs)
        padded_tabs.show_all()
        self.get_content_area().pack_start(padded_tabs, True, True, 0)
        
        # Bindings and events
        self._window_bindings, self._view_bindings = [], []
        self.connect("notify::target-window", self._changed_target_window)
        self.connect("notify::target-view", self._changed_target_view)
        
        utility.Bind(self.app,
            ("spin-effect", spin_effect_adjust, "value"),
            ("zoom-effect", zoom_effect_adjust, "value"),
            bidirectional=True, synchronize=True
        )
        
        # This is a bind for syncing pages betwen the label and widget books
        very_mice_book.bind_property(
            "page", mouse_label_notebook, "page", sync_flag
        )
        
        
        new_handler_button.connect("clicked", self._clicked_new_handler)
        remove_handler_button.connect("clicked", self._clicked_remove_handler)
        configure_handler_button.connect(
            "clicked", self._clicked_configure_handler
        )
        handlers_listview_selection.connect(
            "changed", self._changed_handler_list_selection,
            remove_handler_button, configure_handler_button
        )
        
        cancel_add_button.connect("clicked", self._clicked_cancel_add_handler)
        add_button.connect("clicked", self._clicked_add_handler)
        very_mice_book.connect("key-press-event", self._key_pressed_mice_book)
        self._handlers_listview.connect(
            "button-press-event", self._button_pressed_handlers
        )
        self._brand_listview.connect(
            "button-press-event", self._button_pressed_brands
        )
        
        tabs.connect("notify::page", self._refresh_default)
        very_mice_book.connect("notify::page", self._refresh_default)
        self._refresh_default()
        
        self._mm_handler_signals = [
            self.mm_handler.connect(
                "handler-added", self._added_mouse_handler
            ),
            self.mm_handler.connect(
                "handler-removed", self._removed_mouse_handler
            )
        ]

    
    def _refresh_default(self, *data):
        """ Resets the default widget of the window """
        tab = self.tabs.get_current_page()
        if tab == 1:
            pseudo_tab = self._mouse_pseudo_notebook.get_current_page()
            if pseudo_tab == 0:
                new_default = self._configure_handler_button
            
            else:
                new_default = self._add_handler_button
                
        else:
            new_default = None
            
        if self.get_default_widget() != new_default:
            self.set_default(new_default)
        
        
    def _handler_nick_data_func(self, column, renderer, model, treeiter, *data):
        """ Gets the nickname of a handler for the textrenderer """
        handler = model[treeiter][0]
        renderer.props.text = GetMouseHandlerLabel(handler, default=_("???"))
    
    
    def _handler_nick_compare_func(self, model, a_iter, b_iter, *data):
        a = GetMouseHandlerLabel(model[a_iter][0], default=_("???"))
        b = GetMouseHandlerLabel(model[b_iter][0], default=_("???"))
        
        return 0 if a == b else 1 if a > b else -1
    
    
    def _clicked_new_handler(self, *data):
        """ Handles a click on the new mouse handler button in the mouse tab """
        self._mouse_pseudo_notebook.set_current_page(1)
    
    
    def _clicked_remove_handler(self, *data):
        """ Handles a click on the remove button in the mouse tab """
        selection = self._handlers_listview.get_selection()
        model, row_paths = selection.get_selected_rows()
        
        remove_handler = self.app.meta_mouse_handler.remove
        treeiters = [model.get_iter(a_path) for a_path in row_paths]
        for a_treeiter in treeiters:
            a_handler = model[a_treeiter][0]
            remove_handler(a_handler)
        
        
    def _removed_mouse_handler(self, meta, handler):
        """ Handles a handler actually being removed from
            the meta mouse handler """
        handler_iter = self._mouse_handler_iters.pop(handler, None)
        handler_signals = self._mouse_handler_signals.pop(handler, [])
        
        if handler_iter:
            del self._handlers_liststore[handler_iter]
        
        for a_signal_id in handler_signals:
            handler.disconnect(a_signal_id)
        
    
    def _clicked_configure_handler(self, *data):
        """ Pops up the configure dialog of a mouse handler """
        selection = self._handlers_listview.get_selection()
        model, row_paths = selection.get_selected_rows()
        
        get_dialog = self.app.get_mouse_handler_dialog
        
        treeiters = [model.get_iter(a_path) for a_path in row_paths]
        for a_treeiter in treeiters:
            a_handler = model[a_treeiter][0]
            
            dialog = get_dialog(a_handler)
            dialog.present()
            
    
    def _changed_handler_list_selection(self, selection, 
                                        remove_button, configure_button):
        """ Update sensitivity of some buttons based on whether anything is
            selected in the handlers list view """
        
        model, row_paths = selection.get_selected_rows()
        
        selected_anything = bool(row_paths)
        remove_button.set_sensitive(selected_anything)
        configure_button.set_sensitive(selected_anything)
    
    
    def _button_pressed_handlers(self, listview, event):
        """ Opens the configure dialog on double click """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._clicked_configure_handler()
    
    
    def _key_pressed_mice_book(self, widget, event):
        """ Handles delete key on handlers listview """
        if event.keyval == Gdk.KEY_Delete and \
           self._mouse_pseudo_notebook.get_current_page() == 0:
            self._clicked_remove_handler()
            
            
    def _clicked_cancel_add_handler(self, *data):
        """ Go back to the handlers list when the user doesn't actually
            want to create a new mouse handler """
        self._mouse_pseudo_notebook.set_current_page(0)
    
    
    def _clicked_add_handler(self, *data):
        """ Creates and adds a new mouse handler to the meta mouse handler """
        selection = self._brand_listview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            factory = model[treeiter][0]
            
            new_handler = factory.produce()
            
            handler_button = 1 if new_handler.needs_button else None
            self.mm_handler.add(new_handler, button=handler_button)
            
            # Go back to the handler list
            self._mouse_pseudo_notebook.set_current_page(0)
            
            # Scroll to new handler
            listview = self._handlers_listview
            new_treeiter = self._mouse_handler_iters[new_handler]
            new_treepath = listview.get_model().get_path(new_treeiter)
            listview.scroll_to_cell(new_treepath, None, False, 0, 0)
            
    
    def _added_mouse_handler(self, meta, new_handler):
        """ Handles a mouse handler being added to the meta mouse handler """
        self._add_mouse_handler(new_handler)
    
    
    def _add_mouse_handler(self, new_handler, *data):
        """ Actually and finally adds the mouse handler to the liststore """
        # TODO: Change this to a meta mouse handler "added" signal handler
        new_treeiter = self._handlers_liststore.append([new_handler])
        
        self._mouse_handler_iters[new_handler] = new_treeiter
        # Connect things
        self._mouse_handler_signals[new_handler] = [
            new_handler.connect("notify::nickname",
                                self._refresh_handler_nickname,
                                new_treeiter)
        ]
                            
    
    def _button_pressed_brands(self, listview, event):
        """ Creates a new handler on double click """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._clicked_add_handler()
            
    
    def _brand_label_data_func(self, column, renderer, model, treeiter, *data):
        """ Gets the label of a factory for a text cellrenderer """
        factory = model[treeiter][0]
        renderer.props.text = factory.label
        
        
    def _refresh_handler_nickname(self, handler, spec, treeiter):
        """ Refresh the list view when a handler nickname changes """
        model = self._handlers_liststore
        treepath = model.get_path(treeiter)
        model.row_changed(treepath, treeiter)
    
    
    def create_widget_group(self, *widgets):
        """ I don't even remember what this does """
        alignment = Gtk.Alignment()
        alignment.set_padding(0, 0, 20, 0)
        
        box = Gtk.VBox()
        alignment.add(box)
        
        for a_widget in widgets:
            box.pack_start(a_widget, False, False, 3)
            
        return alignment
        
    
    def _changed_target_window(self, *data):
        self.set_transient_for(self.target_window)
        
        view, album = self.target_window.view, self.target_window.album
        
        if self.target_view != view:
            self.target_view = view
            
        if self.target_album != album:
            self.target_album = album
        
        
    def _changed_target_view(self, *data):
        bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
        sync_flag = GObject.BindingFlags.SYNC_CREATE
        
        for a_binding in self._view_bindings:
            a_binding.unbind()
        
        view = self.target_view
        if view:
            self._view_bindings = [
                view.bind_property("alignment-x", self.alignment_x_adjust,
                                   "value", bidi_flag | sync_flag),
            
                view.bind_property("alignment-y", self.alignment_y_adjust,
                                   "value", bidi_flag | sync_flag)
            ]
        else:
            self._view_bindings = []
        
    target_window = GObject.Property(type=object)
    target_view = GObject.Property(type=object)
    target_album = GObject.Property(type=object)
    
    def _do_destroy(self, *data):
        """ Disconnect any connected signals """
        for a_signal_id in self._mm_handler_signals:
            self.mm_handler.disconnect(a_signal_id)
        
        for a_handler, some_signals in self._mouse_handler_signals.items():
            for a_signal in some_signals:
                a_handler.disconnect(a_signal)
    
    
class MouseHandlerSettingDialog(Gtk.Dialog):
    def __init__(self, handler, handler_data):
        Gtk.Dialog.__init__(self, _("Mouse Mechanism Settings"), None,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
        
        self.handler = handler
        self.handler_data = handler_data
        
        vbox = utility.WidgetStack()
        vbox_pad = utility.PadDialogContent(vbox)
        self.get_content_area().pack_start(vbox_pad, True, True, 0)
        
        # Create nickname widgets
        label = _("Nickname")
        nickname_label = Gtk.Label(label)
        nickname_entry = Gtk.Entry()
        # Pack nickname entry
        nickname_line = utility.WidgetLine(
            nickname_label, nickname_entry, expand=nickname_entry
        )
        vbox.pack_start(nickname_line, False, True, 0)
        
        # Create button setting widgets for handlers that need button setting
        if handler.needs_button:
            tooltip = _("Click here with a mouse button to change \
the chosen mouse button")
            
            mouse_button = self.mouse_button_button = Gtk.Button()
            mouse_button.set_tooltip_text(tooltip)
            mouse_button.connect(
                "button-press-event", self._mouse_button_presssed
            )
            handler_data.connect("notify::button", self._refresh_mouse_button)
            
            vbox.pack_start(mouse_button, False, True, 0)
            self._refresh_mouse_button()
        
        # Ctrl/Shift/Alt modifiers checkbuttons
        ctrl_check = Gtk.CheckButton(_("Ctrl"))
        shift_check = Gtk.CheckButton(_("Shift"))
        alt_check = Gtk.CheckButton(_("Alt"))
        
        modifier_line = utility.WidgetLine(
            ctrl_check, shift_check, alt_check
        )
        vbox.pack_start(modifier_line, False, True, 0)
        
        vbox.pack_start(Gtk.Separator(), False, True, 0)
        vbox.set_vexpand(True)
        vbox_pad.show_all()
        
        factory = handler.factory
        if factory:
            try:
                settings_widget = factory.create_settings_widget(handler)
                
            except Exception:
                logger.log_error("Couldn't create settings widget")
                logger.log_exception()
                
            else:
                vbox.pack_end(settings_widget, True, True, 0)
                settings_widget.show()
                
        # Binding entry
        flags = GObject.BindingFlags
        handler.bind_property(
            "nickname", nickname_entry, "text",
            flags.BIDIRECTIONAL | flags.SYNC_CREATE
        )
        utility.Bind(handler_data,
            ("control-key", ctrl_check, "active"),
            ("shift-key", shift_check, "active"),
            ("alt-key", alt_check, "active"),
            bidirectional=True, synchronize=True
        )
        nickname_entry.connect("notify::text", self._refresh_title)
        handler_data.connect("removed", lambda hd: self.destroy())
        
        self._refresh_title()
    
    def _refresh_title(self, *data):
        label = GetMouseHandlerLabel(self.handler, default=None)
        
        if label:
            title = _("“{something}” Settings").format(something=label)
            
        else:
            title = _("Mouse Mechanism Settings")
            
        self.set_title(title)
    
    def _mouse_button_presssed(self, widget, data):
        self.handler_data.button = data.button
        self.handler_data.keys = data.state & mousing.MouseAdapter.ModifierKeys
    
    def _refresh_mouse_button(self, *data):
        button = self.handler_data.button
        if button == Gdk.BUTTON_PRIMARY:
            label = _("Primary Button")
            
        elif button == Gdk.BUTTON_MIDDLE:
            label = _("Middle Button")
            
        elif button == Gdk.BUTTON_SECONDARY:
            label = _("Secondary Button")
            
        else:
            label = _("Mouse Button #{number}").format(number=button)
        
        self.mouse_button_button.set_label(label)


def GetMouseHandlerLabel(handler, default=""):
    """ Utility to return either nickname or factory label """
    if handler.nickname:
        return handler.nickname
        
    elif handler.factory:
        return handler.factory.label
    
    else:
        return default


import json
from os.path import join as join_path


class SettingsGroup(GObject.Object):
    """An object for storing application settings in.
    
    This object is serialized into JSON as one single object using
    key/values from .data and then codename/settings from its subgroups.
    
    On application start up, any and all extensions that use the preferences
    module should create a settings group using create_settings_group
    and connect the "load" signal.
    
    The "save" signal is called before saving. It's a good idea to populate
    .data with data that can't be mapped to a dictionary using that signal.
    
    For most cases, the settings data should be stored in the .data.
    A subgroup should only be created for supporting extensions in that
    settings namespace.
    
    """
    
    __gsignals__ = {
        "save": (GObject.SIGNAL_NO_HOOKS, None, []),
        "load": (GObject.SIGNAL_NO_HOOKS, None, [])
    }
    
    
    def __init__(self):
        GObject.Object.__init__(self)
        self._subgroups = {}
        self.data = {}
    
    
    def __getitem__(self, codename):
        """Returns a subgroup under codename"""
        if isinstance(codename, tuple):
            return self.get_groups(*codename)[-1]
        else:
            return self._subgroups[codename]
    
    def get_groups(self, *some_codenames, create=False):
        """Returns a list of settings groups children of this group"""
        result = []
        a_group = self
        for a_codename in some_codenames:
            some_subgroups = a_group._subgroups
            try:
                a_group = some_subgroups[a_codename]
            except KeyError:
                if create:
                    some_subgroups[a_codename] = a_group = SettingsGroup()
                    
                else:
                    raise
            
            result.append(a_group)
            
        return result
        
    def create_group(self, codename):
        """Creates and returns a subgroup using codename as key.
        
        KeyError is raised if a subgroup already exists under the same codename
        
        """
        
        if codename in self._subgroups:
            raise KeyError
        
        new_group = SettingsGroup()
        self._subgroups[codename] = new_group
        return new_group
        
    
    #~ A bunch of recursive methods down this line ~#
    def set_all_data(self, data):
        """Sets its .data and its subgroups .data from a dictionary
        
        If a key in the dictionary is a subgroup codename, then the key will
        be removed from the dictionary and the value of that key is used to
        set the subgroup .data
        
        """
        some_codename_keys = self._subgroups.keys() & data.keys()
        for a_codename_key in some_codename_keys:
            a_subdata = data.pop(a_codename_key)
            a_subgroup = self._subgroups[a_codename_key]
            a_subgroup.set_all_data(a_subdata)
            
        self.data = data
    
    def get_all_data(self):
        """Returns a dict combining its .data with all its subgroups .data
        
        If a key in .data is also a subgroup codename, the subgroup.data
        will replace that key value.
        
        """
        all_dat_data = dict(self.data)
        
        for a_codename, a_subgroup in self._subgroups.items():
            all_dat_data[a_codename] = a_subgroup.get_all_data()
        
        return all_dat_data
    
    
    def save_everything(self):
        """Emits a "save" signal to it self and its subgroups"""
        self.emit("save")
        for a_subgroup in self._subgroups.values():
            a_subgroup.save_everything()
    
    def load_everything(self):
        """Emits a "load" signal to it self and its subgroups"""
        self.emit("load")
        for a_subgroup in self._subgroups.values():
            a_subgroup.load_everything()


#~ Functions that are on this module for convenience but really should have ~#
#~ been made instance methods down this double line.                        ~#

def LoadForApp(app):
    """ Loads preferences for the application """
    logger.log("Loading application preferences...")
    try:
        # Directory is preferences.Directory
        json_path = join_path(app.preferences_directory, "preferences.json")
        if not os.path.exists(json_path):
            json_path = join_path(app.data_directory, "preferences.json")
            notification.log("Preferences file doesn't exist. Using defaults")
        
        try:
            with open(json_path) as prefs_file:
                root_obj = json.load(prefs_file)
        except Exception:
            logger.log_error("Failed to load preferences file")
            logger.log_exception()
        else:
            app.settings.set_all_data(root_obj)
            app.settings.load_everything()
            
    except Exception:
        logger.log_error("Couldn't load mouse handler preferences")
        logger.log_exception()


def SaveFromApp(app):
    """ Saves preferences from the application """
    logger.log("Saving application preferences...")
    try:
        os.makedirs(app.preferences_directory, exist_ok=True)
        
    except FileExistsError:
        # For whatever reason, this still can happen
        pass
    
    json_path = join_path(app.preferences_directory, "preferences.json")
    try:
        app.settings.save_everything()
        settings_data = app.settings.get_all_data()
        
        with open(json_path, "w") as prefs_file:
            json.dump(
                settings_data, prefs_file,
                sort_keys=True, indent=2, separators=(",", ": ")
            )
            
    except Exception:
        logger.log_error("Couldn't save mouse handler preferences")
        logger.log_exception()


def LoadForWindow(window):
    """ Loads preferences for an Window object """
    logger.debug("Loading window preferences...")
    settings_data = window.app.settings["window"].data
    utility.SetPropertiesFromDict(
        window, settings_data,
        "autozoom-mode",
        "autozoom-enabled",
        "autozoom-can-minify",
        "autozoom-can-magnify",
        statusbar_visible="interface-statusbar",
        toolbar_visible="interface-toolbar",
        hscrollbar_placement= "scrollbar-horizontal-placement",
        vscrollbar_placement= "scrollbar-vertical-placement"
    )
    
    try:
        layout_codename = settings_data["layout-codename"]
    except KeyError:
        logger.log("Preferred layout not found in preferences, using default")
        layout_codename = organization.SingleImageLayoutOption.CODENAME
    
    try:
        layout_option = window.app.components["layout-option", layout_codename]
    except Exception:
        logger.log_error('Could not load layout codename "{codename}"'.format(
            codename=layout_codename
        ))
    else:
        window.layout_option = layout_option


def SaveFromWindow(window):
    """ Saves preferences from an Window object """
    logger.debug("Saving window preferences...")
    settings_data = window.app.settings["window"].data
    utility.SetDictFromProperties(window, settings_data,
        "autozoom-mode",
        "autozoom-enabled",
        "autozoom-can-minify",
        "autozoom-can-magnify",
        statusbar_visible="interface-statusbar",
        toolbar_visible="interface-toolbar",
        hscrollbar_placement="scrollbar-horizontal-placement",
        vscrollbar_placement="scrollbar-vertical-placement"
    )
    
    settings_data["start-fullscreen"] = window.get_fullscreen()
    
    try:
        settings_data["layout-codename"] = window.layout_option.codename
    except Exception:
        logger.log_error("Could not save preferred layout codename")


def LoadForAlbum(album, app_settings=None, album_settings=None):
    """ Loads preferences for an Album object """
    logger.debug("Loading album preferences...")
    if not album_settings:
        album_settings = album_settings or app_settings["album"]
    
    settings_data = album_settings.data
    album.freeze_notify()
    utility.SetPropertiesFromDict(
        album, settings_data, autosort="sort-auto", reverse="sort-reverse"
    )
    try:
        sort_mode = settings_data.get("sort-mode", 0)
        album.comparer = organization.SortingKeys.Enum[sort_mode]
    except KeyError:
        logger.log_error("Could not load album comparer mode {mode}".format(
            mode=sort_mode
        ))
    finally:
        album.thaw_notify()


def SaveFromAlbum(album, app_settings=None, album_settings=None):
    """ Saves preferences from an Album object """
    logger.debug("Saving album preferences...")
    if not album_settings:
        album_settings = app_settings["album"]
    
    settings_data = album_settings.data
    settings_data["sort-auto"] = album.autosort
    settings_data["sort-reverse"] = album.reverse
    
    sort_mode = organization.SortingKeys.Enum.index(album.comparer)
    settings_data["sort-mode"] = sort_mode


def LoadForView(view, app_settings=None, view_settings=None):
    """ Loads preferences for an ImageView object """
    logger.debug("Loading view preferences...")
    if not view_settings:
        view_settings = app_settings["view"]
    
    settings_data = view_settings.data
    utility.SetPropertiesFromDict(
        view, settings_data, "alignment-x", "alignment-y",
        minify_filter="interpolation-minify",
        magnify_filter="interpolation-magnify"
    )


def SaveFromView(view, app_settings=None, view_settings=None):
    """ Saves preferences from an ImageView object """
    logger.debug("Saving view preferences...")
    if not view_settings:
        view_settings = app_settings["view"]
    
    settings_data = view_settings.data
    # Save alignment
    utility.SetDictFromProperties(
        view, settings_data, "alignment-x", "alignment-y",
        minify_filter="interpolation-minify",
        magnify_filter="interpolation-magnify"
    )


def LoadMouseMechanismsSettings(app, meta_mouse_handler, mechanisms_settings):
    """ Loads mouse settings from a dictionary """
    
    mouse_factories = app.components["mouse-mechanism-brand"]
    add_mouse_mechanism = meta_mouse_handler.add
    for a_brand, some_mechanisms in mechanisms_settings.items():
        # Try to get the factory with a "a_brand" codename
        a_factory = mouse_factories[a_brand]
        if not a_factory:
            notification.log(
                "Couldn't find \"%s\" mouse mechanism brand" % a_brand
            )
            continue
        
        # Loop through brand instances,
        # creating and adding each of them
        for a_mechanism_obj in some_mechanisms:
            try:
                factory_data = a_mechanism_obj.get("settings", None)
                a_mechanism = a_factory.produce(settings=factory_data)
                
                # Set mechanism instance nickname
                a_nickname = a_mechanism_obj.get("nickname", "")
                if a_nickname:
                    a_mechanism.nickname = a_nickname
                
                a_binding = a_mechanism_obj["binding"]
                add_mouse_mechanism(a_mechanism, **a_binding)
                
            except Exception:
                notification.log_exception(
                    "Failed to load a mouse mechanism"
                )


def GetMouseMechanismsSettings(meta_mouse_handler):
    """ Returns a dictionary with all mouse settings to be stored as JSON """
    mechanism_objs = {}
    
    get_mechanisms = meta_mouse_handler.get_handlers
    brand_mechanisms = (m for m in get_mechanisms() if m.factory)
    
    for a_handler in brand_mechanisms:
        try:
            a_brand = a_handler.factory.codename
            a_binding = meta_mouse_handler[a_handler]
            
            a_mechanism_obj = {
                "binding": { 
                    "keys": a_binding.keys, "button": a_binding.button
                }
            }
            # Store a nickname, if any is set
            a_nickname = a_handler.nickname
            if a_nickname:
                a_mechanism_obj["nickname"] = a_nickname
            
            # Get some settings from the factory
            some_settings = a_handler.factory.get_settings(a_handler)
            if some_settings:
                a_mechanism_obj["settings"] = some_settings
            
        except Exception:
            logger.log_error("Couldn't save mouse mechanism")
            logger.log_exception()
        
        else:
            try:
                a_brand_mechanisms = mechanism_objs[a_brand]
                
            except KeyError:
                mechanism_objs[a_brand] = a_brand_mechanisms = []
                
            a_brand_mechanisms.append(a_mechanism_obj)
    return mechanism_objs

from gi.repository import Gdk
import math

class PointScale(Gtk.DrawingArea):
    """ A widget like a Gtk.HScale and Gtk.VScale together. """
    def __init__(self, hrange, vrange, square=False):
        Gtk.DrawingArea.__init__(self)
        self.set_size_request(50, 50)
        self.square = square
        if square:
            self.padding = 0
            self.mark_width = 32
            self.mark_height = 32
            
        else:
            self.padding = 4
            self.mark_width = 8
            self.mark_height = 8
            
        self.dragging = False
        self.__hrange = self.__vrange = None
        self.hrange_signal = self.vrange_signal = None
        self.set_hrange(hrange)
        self.set_vrange(vrange)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.POINTER_MOTION_HINT_MASK
        )
            
    def adjust_from_point(self, x, y):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        if self.square:
            hpadding = self.padding + self.mark_width / 2
            vpadding = self.padding + self.mark_height / 2
        else:
            hpadding, vpadding = self.padding, self.padding
        
        t, l = vpadding, hpadding
        r, b = w - hpadding, h - vpadding
        
        x, y = (max(0, min(r - l, x - l)) / (r - l),
                max(0, min(b - t, y - t)) / (b - t))
                
        hrange = self.get_hrange()
        if hrange:
            lx, ux = hrange.get_lower(), hrange.get_upper()
            vx = x * (ux - lx) + lx
            self.hrange.set_value(vx)
        
        vrange = self.get_vrange()
        if vrange:
            ly, uy = vrange.get_lower(), vrange.get_upper()
            vy = y * (uy - ly) + ly
            self.vrange.set_value(vy)
    
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_width(self):
        hrange = self.get_hrange()
        vrange = self.get_vrange()
        lx, ux = hrange.get_lower(), hrange.get_upper()
        ly, uy = vrange.get_lower(), vrange.get_upper()
        
        ratio = (ux - lx) / (uy - ly)
        w = self.get_allocated_height()
        return w * ratio, w * ratio
                    
    def do_get_preferred_height(self):
        hrange = self.get_hrange()
        vrange = self.get_vrange()
        lx, ux = hrange.get_lower(), hrange.get_upper()
        ly, uy = vrange.get_lower(), vrange.get_upper()
        
        ratio = (uy - ly) / (ux - lx)
        h = self.get_allocated_height()
        return h * ratio, h * ratio
    
    def do_get_preferred_height_for_width(self, width):
        hrange = self.get_hrange()
        vrange = self.get_vrange()
        lx, ux = hrange.get_lower(), hrange.get_upper()
        ly, uy = vrange.get_lower(), vrange.get_upper()
        
        ratio = (uy - ly) / (ux - lx)
        
        return width * ratio, width * ratio
            
    def do_get_preferred_width_for_height(self, height):
        hrange = self.get_hrange()
        vrange = self.get_vrange()
        lx, ux = hrange.get_lower(), hrange.get_upper()
        ly, uy = vrange.get_lower(), vrange.get_upper()
        
        ratio = (ux - lx) / (uy - ly)
        
        return height * ratio, height * ratio
        
    def do_button_press_event(self, data):
        self.dragging = True
        self.adjust_from_point(data.x, data.y)
            
    def do_button_release_event(self, data):
        self.dragging = False
        self.queue_draw()
    
    def do_motion_notify_event(self, data):
        if self.dragging:
            mx, my = data.x, data.y
            self.adjust_from_point(mx, my)
    
    def do_draw(self, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()        
        if self.square:
            hpadding = self.padding + self.mark_width / 2
            vpadding = self.padding + self.mark_height / 2
        else:
            hpadding, vpadding = self.padding, self.padding
        
        t, l = vpadding, hpadding
        r, b = w - hpadding, h - vpadding
                
        hrange = self.get_hrange()
        if hrange:
            lx, ux = hrange.get_lower(), hrange.get_upper()
            vx = hrange.get_value()
            x = (r - l - 1) * (vx / (ux - lx) - lx) + l
        else:
            x = w / 2
            
        vrange = self.get_vrange()
        if vrange:
            ly, uy = vrange.get_lower(), vrange.get_upper()
            vy = vrange.get_value()
            y = (b - t - 1) * (vy / (uy - ly) - ly) + l
        else:
            y = h / 2
        
        style = self.get_style_context()
        
        style.add_class(Gtk.STYLE_CLASS_ENTRY)
        Gtk.render_background(style, cr, 0, 0, w, h)
        cr.save()
        border = style.get_border(style.get_state())
        radius = style.get_property(Gtk.STYLE_PROPERTY_BORDER_RADIUS,
                                    Gtk.StateFlags.NORMAL)
        color = style.get_color(style.get_state())
        cr.arc(border.left + radius,
               border.top + radius, radius, math.pi, math.pi * 1.5)
        cr.arc(w - border.right - radius -1,
               border.top + radius, radius, math.pi * 1.5, math.pi * 2)
        cr.arc(w - border.right - radius -1,
               h -border.bottom - radius -1, radius, 0, math.pi / 2)
        cr.arc(border.left + radius,
               h - border.bottom - radius - 1, radius, math.pi / 2, math.pi)
        cr.clip()
        
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        x, y = round(x), round(y)
        
        if self.square:
            ml, mt = x - self.mark_width / 2, y - self.mark_height / 2
            mr, mb = ml + self.mark_width, mt + self.mark_height
            ml, mt, mr, mb = round(ml), round(mt), round(mr), round(mb)
            
            cr.set_line_width(1)
            cr.set_dash([3, 7], x + y)
            cr.move_to(ml, 0); cr.line_to(ml, h); cr.stroke()
            cr.move_to(mr, 0); cr.line_to(mr, h); cr.stroke()
            cr.move_to(0, mt); cr.line_to(w, mt); cr.stroke()
            cr.move_to(0, mb); cr.line_to(w, mb); cr.stroke()
            
            cr.set_dash([], 0)
            cr.rectangle(ml, mt, self.mark_width, self.mark_height)
            cr.stroke()
        
        else:
            cr.set_line_width(1)
            cr.set_dash([3, 7], x + y)
            cr.move_to(x, 0); cr.line_to(x, h); cr.stroke()
            cr.move_to(0, y); cr.line_to(w, y); cr.stroke()
            
            cr.save()
            cr.translate(x, y)
            cr.scale(self.mark_width * 3, self.mark_height * 3)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.stroke()
            
            cr.set_dash([], 0)
            
            cr.save()
            cr.translate(x, y)
            cr.scale(self.mark_width / 2, self.mark_height / 2)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.fill()
            
        cr.restore()
        Gtk.render_frame(style, cr, 0, 0, w, h)
        
    def adjustment_changed(self, data):
        self.queue_draw()
    
    def get_hrange(self):
        return self.__hrange
    def set_hrange(self, adjustment):
        if self.__hrange:
            self.__hrange.disconnect(self.hrange_signal)
            self.hrange_signal = None
            
        self.__hrange = adjustment
        if adjustment:
            self.hrange_signal = adjustment.connect(
                "value-changed", self.adjustment_changed
            )
        self.queue_draw()
        
    def get_vrange(self):
        return self.__vrange
    def set_vrange(self, adjustment):
        if self.__vrange:
            self.__vrange.disconnect(self.vrange_signal)
            self.vrange_signal = None
            
        self.__vrange = adjustment
        if adjustment:
            self.vrange_signal = adjustment.connect(
                "value-changed", self.adjustment_changed
            )
        self.queue_draw()
                                                     
    hrange = GObject.property(get_hrange, set_hrange, type=Gtk.Adjustment)
    vrange = GObject.property(get_vrange, set_vrange, type=Gtk.Adjustment)
