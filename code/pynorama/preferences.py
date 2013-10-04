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

import os
from os.path import join as join_path
import json
import math
from gi.repository import Gdk, GObject, Gtk
from gettext import gettext as _
from . import utility, widgets, notifying, extending, organizing
from .mousing import MOUSE_MODIFIER_KEYS
from .extending import PreferencesTab

logger = notifying.Logger("preferences")

class Dialog(Gtk.Dialog):
    def __init__(self, app):
        Gtk.Dialog.__init__(
            self, _("Pynorama Preferences"), None,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        )
        
        self.set_default_size(400, 400)
        self.app = app
        
        # Create tabs
        self.tabs = tabs = Gtk.Notebook()
        for a_tab in self.app.components[extending.PreferencesTab.CATEGORY]:
            try:
                a_tab_label = a_tab.create_label(self)
                a_proxy = a_tab.create_proxy(self, a_tab_label)
                a_tab_pad = widgets.PadNotebookContent(a_proxy)
                tabs.append_page(a_tab_pad, a_tab_label)
            except Exception:
                name = None
                try:
                    name = str(a_tab.label)
                except Exception:
                    try:
                        codename = str(a_tab.codename)
                    except Exception:
                        # Treatment of exception of exception of exception
                        # What an exceptional treatment!
                        logger.log_error("Couldn't get some tab's codename")
                        logger.log_exception()
                    else:
                        logger.log_error((
                                "Couldn't get the '{codename}'" +
                                " preferences tab label"
                            ).format(codename=codename)
                        )
                        name = codename
                
                if name:
                    logger.log_error(
                        "Failed to create tab '{name}'".format(name=name)
                    )
                else:
                    logger.log_error("Failed to create some tab")
                    
                logger.log_exception()
            
        # Pack tabs into dialog
        padded_tabs = widgets.PadDialogContent(tabs)
        padded_tabs.show_all()
        self.get_content_area().pack_start(padded_tabs, True, True, 0)
        
        # Bindings and events
        self.connect("notify::target-window", self._changed_target_window_cb)
    
    
    def _changed_target_window_cb(self, *data):
        self.set_transient_for(self.target_window)
        
        view, album = self.target_window.view, self.target_window.album
        
        if self.target_view != view:
            self.target_view = view
            
        if self.target_album != album:
            self.target_album = album
        
    target_window = GObject.Property(type=object)
    target_view = GObject.Property(type=object)
    target_album = GObject.Property(type=object)


#~ Built in preferences tabs implementation ~#
class ViewPreferencesTabProxy(Gtk.Box):
    def __init__(self, dialog, label):
        Gtk.Box.__init__(self)
        # View alignment
        alignment_label = Gtk.Label(_("Image alignment"))
        xadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
        yadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
        point_scale = widgets.PointScale(xadjust, yadjust, square=True)
        grid, xspin, yspin = widgets.PointScaleGrid(
            point_scale, _("Horizontal"), _("Vertical"),
            corner=alignment_label, align=True
        )
        
        # Setting tooltip
        alignment_tooltip = _(
            "This alignment setting is used for various alignment" +
            " related things in the program"
        )
        utility.SetProperties(
            point_scale, xspin, yspin,
            tooltip_text=alignment_tooltip
        )
        
        # Spin effect
        label = _("Spin effect")
        spin_tooltip = _("Rotate clockwise/anti-clockwise effect in degrees")
        spin_effect_label = Gtk.Label(label)
        spin_effect_entry, spin_effect_adjust = widgets.SpinAdjustment(
            0, -180, 180, 10, 60, align=True, digits=2, wrap=True
        )
        # Seting spin tooltip
        utility.SetProperties(
            spin_effect_label, spin_effect_entry,
            tooltip_text=spin_tooltip
        )
        
        # Zoom effect
        label = _("Zoom in/out effect")
        zoom_tooltip = _("Zoom in/out effect as a multiplier/dividend")
        zoom_effect_label = Gtk.Label(label)
        zoom_effect_entry, zoom_effect_adjust = widgets.SpinAdjustment(
            2, 1, 4, 0.1, 0.25, align=True, digits=2
        )
        # Setting zoom tooltipip
        utility.SetProperties(
            zoom_effect_label, zoom_effect_entry,
            tooltip_text=zoom_tooltip
        )
        
        # packing widgets
        widgets.Grid(
            (spin_effect_label, spin_effect_entry),
            (zoom_effect_label, zoom_effect_entry),
            align_first=True, expand_first=True,
            grid=grid, start_row=1
        )
        utility.Bind(dialog.app,
            ("spin-effect", spin_effect_adjust, "value"),
            ("zoom-effect", zoom_effect_adjust, "value"),
            bidirectional=True, synchronize=True
        )
        
        # View binding variables
        self.__alignment_xadjust = xadjust
        self.__alignment_yadjust = yadjust
        self.__view_bindings = None
        
        dialog.connect(
            "notify::target-view", self._changed_target_view_cb
        )
        # Bind the current view
        self._changed_target_view_cb(dialog)
        
        self.add(grid)
        self.show_all()
    
    
    def _changed_target_view_cb(self, dialog, *etc):
        """ Reconnects view alignment bindings """
        if self.__view_bindings:
            for a_binding in self.__view_bindings:
                a_binding.unbind()
            self.__view_bindings = None
        
        view = dialog.target_view
        if view:
            self.__view_bindings = utility.Bind(view,
                ("alignment-x", self.__alignment_xadjust, "value"),
                ("alignment-y", self.__alignment_yadjust, "value"),
                bidirectional=True, synchronize=True
            )


class ViewPreferencesTab(PreferencesTab):
    CODENAME = "view-tab"
    def __init__(self):
        PreferencesTab.__init__(self, ViewPreferencesTab.CODENAME)
    
    
    @GObject.Property
    def label(self):
        return _("View")
    
    create_proxy = ViewPreferencesTabProxy


class MousePreferencesTabProxy(Gtk.Box):
    def __init__(self, dialog, label):
        self._app = dialog.app
        self._mm_handler = dialog.app.meta_mouse_handler
        
        # Variables to remember what to remove or disconnect later.
        # Treeiters for mouse handlers, signal ids from mm_handler and
        # signal ids from individual mouse handlers
        self._mouse_handler_iters = dict()
        self._mm_handler_signals = list()
        self._mouse_handler_signals = dict()
        
        self._mouse_pseudo_notebook = very_mice_book = Gtk.Notebook()
        very_mice_book.set_show_tabs(False)
        very_mice_book.set_show_border(False)
        
        # This one is used for the labels on top of the pseudo notebook
        mouse_label_notebook = Gtk.Notebook()
        mouse_label_notebook.set_show_tabs(False)
        mouse_label_notebook.set_show_border(False)
        
        # Add handler list label and widget container
        text = _("""Mouse mechanisms currently in use by the image viewer""")
        view_handlers_description = widgets.LoneLabel(text)
        mouse_label_notebook.append_page(view_handlers_description, None)
        
        # Add handler factory list label and widget container
        text = _("""Types of mouse mechanisms currently avaiable \
for the image viewer""")
        brands_description = widgets.LoneLabel(text)
        mouse_label_notebook.append_page(brands_description, None)
        
        # Init the proxy
        widgets.InitStack(self,
            mouse_label_notebook, very_mice_book,
            expand=very_mice_book
        )
        
        # Setup handler list tab
        # Create and sync mouse handler list store
        self._handlers_liststore = handlers_liststore = Gtk.ListStore(object)
        for a_handler in self._mm_handler.get_handlers():
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
        
        edit_handler_buttonbox = widgets.ButtonBox(
            configure_handler_button,
            secondary=[new_handler_button, remove_handler_button]
        )
        
        # Pack widgets into the notebook
        view_handlers_box = widgets.Stack(
            handler_listscroller, edit_handler_buttonbox,
            expand=handler_listscroller
        )
        very_mice_book.append_page(view_handlers_box, None)
        
        # Setup add handlers grid (it is used to add handlers)
        brand_liststore = Gtk.ListStore(object)
        
        for a_brand in self._app.components["mouse-mechanism-brand"]:
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
        
        add_handler_buttonbox = widgets.ButtonBox(
            cancel_add_button, add_button
        )
        
        # Pack widgets into the pseudo notebook
        add_handler_box = widgets.Stack(
            brand_listscroller, add_handler_buttonbox,
            expand=brand_listscroller
        )
        very_mice_book.append_page(add_handler_box, None)
        
        # This is a bind for syncing pages betwen the label and widget books
        self.connect("destroy", self._do_destroy_cb)
        
        utility.Bind(very_mice_book,
            ("page", mouse_label_notebook, "page"),
            synchronize=True
        )
        self._handlers_listview.connect(
            "button-press-event", self._button_pressed_handlers_cb
        )
        self._brand_listview.connect(
            "button-press-event", self._button_pressed_brands_cb
        )
        new_handler_button.connect(
            "clicked", self._clicked_new_handler_cb
        )
        remove_handler_button.connect(
            "clicked", self._clicked_remove_handler_cb
        )
        configure_handler_button.connect(
            "clicked", self._clicked_configure_handler_cb
        )
        handlers_listview_selection.connect(
            "changed", self._changed_handler_list_selection_cb,
            remove_handler_button, configure_handler_button
        )
        cancel_add_button.connect(
            "clicked", self._clicked_cancel_add_handler_cb
        )
        add_button.connect(
            "clicked", self._clicked_add_handler_cb
        )
        very_mice_book.connect(
            "key-press-event", self._key_pressed_mice_book_cb
        )
        
        self._mm_handler_signals = [
            self._mm_handler.connect(
                "handler-added", self._added_mouse_handler_cb
            ),
            self._mm_handler.connect(
                "handler-removed", self._removed_mouse_handler_cb
            )
        ]
    
    
    def _add_mouse_handler(self, new_handler, *etc):
        """ Actually and finally adds the mouse handler to the liststore """
        new_treeiter = self._handlers_liststore.append([new_handler])
        
        self._mouse_handler_iters[new_handler] = new_treeiter
        # Connect things
        self._mouse_handler_signals[new_handler] = [
            new_handler.connect(
                "notify::nickname",
                self._changed_handler_nickname_cb,
                new_treeiter
            )
        ]
        
    
    #~~ "Currently in use" handlers list part ~#
    def _show_configure_dialog(self):
        """ Pops up the configure dialog of a mouse handler """
        selection = self._handlers_listview.get_selection()
        model, row_paths = selection.get_selected_rows()
        
        get_dialog = self._app.get_mouse_handler_dialog
        
        treeiters = [model.get_iter(a_path) for a_path in row_paths]
        for a_treeiter in treeiters:
            a_handler = model[a_treeiter][0]
            
            dialog = get_dialog(a_handler)
            dialog.present()
    
    
    def _remove_selected_handler(self):
        selection = self._handlers_listview.get_selection()
        model, row_paths = selection.get_selected_rows()
        
        remove_handler = self._mm_handler.remove
        treeiters = [model.get_iter(a_path) for a_path in row_paths]
        for a_treeiter in treeiters:
            a_handler = model.get_value(a_treeiter, 0)
            remove_handler(a_handler)
    
    
    def _clicked_new_handler_cb(self, *whatever):
        """ Handles a click on the "new" in the mouse tab """
        self._mouse_pseudo_notebook.set_current_page(1)
    
    
    def _clicked_remove_handler_cb(self, *whatever):
        """ Handles a click on the "remove" button in the mouse tab """
        self._remove_selected_handler()
    
    
    def _clicked_configure_handler_cb(self, *whatever):
        self._show_configure_dialog()
    
    
    def _button_pressed_handlers_cb(self, listview, event):
        """ Opens the configure dialog on double click """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._show_configure_dialog()
    
    
    def _key_pressed_mice_book_cb(self, widget, event):
        """ Handles delete key on handlers listview """
        if event.keyval == Gdk.KEY_Delete and \
           self._mouse_pseudo_notebook.get_current_page() == 0:
            self._remove_selected_handler()
    
    
    def _changed_handler_list_selection_cb(
                self, selection, remove_button, configure_button):
        """ Update sensitivity of some buttons based on whether anything is
            selected in the handlers list view """
        
        model, row_paths = selection.get_selected_rows()
        
        selected_anything = bool(row_paths)
        remove_button.set_sensitive(selected_anything)
        configure_button.set_sensitive(selected_anything)
    
    
    #~~ Create new mouse handler part ~~#
    def _create_and_add_new_handler(self):
        """ Creates a new mouse handler based on the selected brand """
        selection = self._brand_listview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            factory = model[treeiter][0]
            
            new_handler = factory.produce()
            
            handler_button = 1 if new_handler.needs_button else None
            self._mm_handler.add(new_handler, button=handler_button)
            
            # Go back to the handler list
            self._mouse_pseudo_notebook.set_current_page(0)
            
            # Scroll to new handler
            listview = self._handlers_listview
            new_treeiter = self._mouse_handler_iters[new_handler]
            new_treepath = listview.get_model().get_path(new_treeiter)
            listview.scroll_to_cell(new_treepath, None, False, 0, 0)
    
    
    def _button_pressed_brands_cb(self, listview, event):
        """ Creates a new handler on double click """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._create_and_add_new_handler()
    
    
    def _clicked_add_handler_cb(self, *whatever):
        """ Handles clicking on the add button in the new handler "page" """
        self._create_and_add_new_handler()
    
    
    def _clicked_cancel_add_handler_cb(self, *whatever):
        """ Go back to the handlers list when the user doesn't actually
            want to create a new mouse handler """
        self._mouse_pseudo_notebook.set_current_page(0)
    
    
    #~ TreeView customization ~#
    def _handler_nick_data_func(self, column, renderer, model, treeiter, *etc):
        """ Gets the nickname of a handler for the TextRenderer """
        handler = model[treeiter][0]
        renderer.props.text = GetMouseHandlerLabel(handler, default=_("???"))
    
    
    def _handler_nick_compare_func(self, model, a_iter, b_iter, *etc):
        """ Compares two mouse handlers nicknames """
        a = GetMouseHandlerLabel(model[a_iter][0], default=_("???"))
        b = GetMouseHandlerLabel(model[b_iter][0], default=_("???"))
        
        return 0 if a == b else 1 if a > b else -1
    
    
    def _brand_label_data_func(self, column, renderer, model, treeiter, *etc):
        """ Gets the label of a factory for a text cellrenderer """
        factory = model[treeiter][0]
        renderer.props.text = factory.label
    
    
    #~ Model synchronization ~#
    def _added_mouse_handler_cb(self, meta, new_handler):
        """ Handles a mouse handler being added to the meta mouse handler """
        self._add_mouse_handler(new_handler)
    
    
    def _removed_mouse_handler_cb(self, meta, handler):
        """ Handles a handler actually being removed from
            the meta mouse handler """
        handler_iter = self._mouse_handler_iters.pop(handler, None)
        handler_signals = self._mouse_handler_signals.pop(handler, [])
        
        if handler_iter:
            del self._handlers_liststore[handler_iter]
        
        for a_signal_id in handler_signals:
            handler.disconnect(a_signal_id)
    
    
    def _changed_handler_nickname_cb(self, handler, spec, treeiter):
        """ Refresh the list view when a handler nickname changes """
        model = self._handlers_liststore
        treepath = model.get_path(treeiter)
        model.row_changed(treepath, treeiter)
    
    
    def _do_destroy_cb(self, *whatever):
        """ Disconnect any connected signals """
        for a_signal_id in self._mm_handler_signals:
            self._mm_handler.disconnect(a_signal_id)
        
        for a_handler, some_signals in self._mouse_handler_signals.items():
            for a_signal in some_signals:
                a_handler.disconnect(a_signal)


class MousePreferencesTab(PreferencesTab):
    CODENAME = "mouse-tab"
    def __init__(self):
        PreferencesTab.__init__(self, MousePreferencesTab.CODENAME)
    
    
    @GObject.Property
    def label(self):
        return _("Mouse")
    
    
    create_proxy = MousePreferencesTabProxy


class BuiltinPreferencesTabPackage(extending.ComponentPackage):
    def add_on(self, app):
        components = app.components
        preferences_tabs = (
            ViewPreferencesTab(),
            MousePreferencesTab(),
        )
        for a_preferences_tab in preferences_tabs:
            components.add(PreferencesTab.CATEGORY, a_preferences_tab)

extending.LoadedComponentPackages["prefs"] = BuiltinPreferencesTabPackage()


class MouseHandlerSettingDialog(Gtk.Dialog):
    def __init__(self, handler, handler_data):
        Gtk.Dialog.__init__(self, _("Mouse Mechanism Settings"), None,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
        
        self.handler = handler
        self.handler_data = handler_data
        
        vbox = widgets.Stack()
        vbox_pad = widgets.PadDialogContent(vbox)
        self.get_content_area().pack_start(vbox_pad, True, True, 0)
        
        # Create nickname widgets
        label = _("Nickname")
        nickname_label = Gtk.Label(label)
        nickname_entry = Gtk.Entry()
        # Pack nickname entry
        nickname_line = widgets.Line(
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
        
        modifier_line = widgets.Line(
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
        self.handler_data.keys = data.state & MOUSE_MODIFIER_KEYS
    
    
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
        """ Returns a subgroup under codename """
        if isinstance(codename, tuple):
            return self.get_groups(*codename)[-1]
        else:
            return self._subgroups[codename]
    
    
    def get_groups(self, *some_codenames, create=False):
        """ Returns a list of settings groups children of this group """
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
        """ Creates and returns a subgroup using codename as key
        
        KeyError is raised if a subgroup already exists under the same codename
        
        """
        
        if codename in self._subgroups:
            raise KeyError
        
        new_group = SettingsGroup()
        self._subgroups[codename] = new_group
        return new_group
        
    
    #~ A bunch of recursive methods down this line ~#
    def set_all_data(self, data):
        """ Sets its .data and its subgroups .data from a dictionary
        
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
        """ Returns a dict combining its .data with all its subgroups .data
        
        If a key in .data is also a subgroup codename, the subgroup.data
        will replace that key value.
        
        """
        all_dat_data = dict(self.data)
        
        for a_codename, a_subgroup in self._subgroups.items():
            all_dat_data[a_codename] = a_subgroup.get_all_data()
        
        return all_dat_data
    
    
    def save_everything(self):
        """ Emits a "save" signal to it self and its subgroups """
        self.emit("save")
        for a_subgroup in self._subgroups.values():
            a_subgroup.save_everything()
    
    def load_everything(self):
        """ Emits a "load" signal to it self and its subgroups """
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
            logger.log("Preferences file doesn't exist. Using defaults")
        
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
        from .components.layouts import SingleImageLayoutOption
        layout_codename = SingleImageLayoutOption.CODENAME
    
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
        album.comparer = organizing.SortingKeys.Enum[sort_mode]
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
    
    sort_mode = organizing.SortingKeys.Enum.index(album.comparer)
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
            logger.log_error(
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
                logger.log_error("Failed to load a mouse mechanism")
                logger.log_exception()


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
