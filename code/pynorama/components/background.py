""" background.py adds a background preferences tab to the image viewer """

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

from pynorama import utility, widgets, extending, notification
from pynorama.extending import PreferencesTab, LoadedComponentPackages
from gi.repository import Gdk, GObject, Gtk
from gettext import gettext as _
import cairo
logger = notification.Logger("preferences")

class BackgroundPreferencesTabProxy(Gtk.Box):
    def __init__(self, tab, dialog, label):
        # Enabled checkbutton at the top
        theme_option = Gtk.RadioButton(
            _("Theme background"),
            tooltip_text=_("Use the background set by the Gtk theme")
        )
        
        # Custom background color line
        custom_color_option = Gtk.RadioButton(
            _("Solid background color"),
            tooltip_text=_("Use one custom color as the window background"),
            group=theme_option
        )
        color_chooser = Gtk.ColorButton(
            title=_("Background Color"),
            tooltip_text=_("The color used as the window background"),
            use_alpha=True
        )
        bg_line = widgets.Line(custom_color_option, color_chooser)
        
        checkered_option = Gtk.RadioButton(
            _("Checkered background"),
            tooltip_text=_("Use a checkered pattern as the window background"),
            group=custom_color_option
        )
        
        # Checks size
        size_label = Gtk.Label(_("Checks size"))
        size_entry, size_adjust = widgets.SpinAdjustment(
            16, 4, 1280, 4, 32, align=True, digits=0,
        )
        size_entry.set_tooltip_text(_(
            "The size of the checks of the checkered pattern"
        ))
        # Checks colors
        colors_label = Gtk.Label(_("Colors"))
        primary_color_button = Gtk.ColorButton(
            title=_("Checkered Pattern Primary Color"), use_alpha=False
        )
        secondary_color_button = Gtk.ColorButton(
            title=_("Checkered Pattern Primary Color"), use_alpha=False
        )
        colors_box = Gtk.ButtonBox(
            tooltip_text=_("The checkered pattern colors")
        )
        colors_box.get_style_context().add_class(Gtk.STYLE_CLASS_LINKED)
        colors_box.add(primary_color_button)
        colors_box.add(secondary_color_button)
        
        checks_appearance_widgets = widgets.Grid(
            (size_label, size_entry),
            (colors_label, colors_box),
            align_first=True
        )
        
        # A box with the customizing widgets
        widgets.InitStack(self,
            theme_option, bg_line, checkered_option, checks_appearance_widgets
        )
        
        # Bind properties
        flags = GObject.BindingFlags
        tab.bind_property(
            "enabled", theme_option, "active",
            flags.BIDIRECTIONAL | flags.SYNC_CREATE | flags.INVERT_BOOLEAN
        )
        utility.Bind(tab,
            ("use-custom-color", custom_color_option, "active"),
            ("color", color_chooser, "rgba"),
            ("checkered", checkered_option, "active"),
            ("checks-size", size_adjust, "value"),
            ("checks-primary-color", primary_color_button, "rgba"),
            ("checks-secondary-color", secondary_color_button, "rgba"),
            bidirectional=True, synchronize=True
        )
        # Sensitivity binds
        utility.Bind(tab,
            ("use-custom-color", color_chooser, "sensitive"),
            ("checkered", checks_appearance_widgets, "sensitive"),
            synchronize=True
        )


class BackgroundPreferencesTab(extending.PreferencesTab):
    """ Allows for customizing the background of the image viewer window """
    CODENAME = "background-tab"
    def __init__(self, app):
        extending.PreferencesTab.__init__(
            self, BackgroundPreferencesTab.CODENAME
        )
        # Set default colors
        self.color = Gdk.RGBA(0, 0, 0 ,1)
        self.checks_primary_color = Gdk.RGBA(.93, .93, .93 ,1)
        self.checks_secondary_color = Gdk.RGBA(.82, .82, .82 ,1)
        self._enabled = False
        self._view_signals = {}
        self._checkered_pattern = None
        
        # Flag for creating a checkered pattern
        self._obsolete_checkered_pattern = True
        
        # Connect signals
        app.connect("new-window", self._new_window_cb)
        self.connect("notify::enabled", self._changed_enabled_cb)
        self.connect("notify::use-custom-color", self._changed_effect_cb)
        self.connect("notify::color", self._changed_effect_cb)
        self.connect("notify::checkered", self._changed_checkered_cb)
        self.connect("notify::checks-size", self._changed_checks_cb)
        self.connect("notify::checks-primary-color", self._changed_checks_cb)
        self.connect("notify::checks-secondary-color", self._changed_checks_cb)
        
        # Create settings
        settings = app.settings.get_groups(
            "view", "background", create=True
        )[-1]
        settings.connect("save", self._save_settings_cb)
        settings.connect("load", self._load_settings_cb)
    
    
    @GObject.Property
    def label(self):
        return _("Background")
    
    
    def get_enabled(self):
        return self._enabled
    
    
    def set_enabled(self, is_enabled):
        """ Sets whether to enable a custom background
        
        Setting this to false disconnects all signals handlers connected to
        the application image views.
        """
        if is_enabled != self._enabled:
            self._enabled = is_enabled
            if is_enabled:
                for a_view in self._view_signals:
                    self._connect_view(a_view)
            else:
                for a_view, some_signals in self._view_signals.items():
                    for a_signal in some_signals:
                        a_view.disconnect(a_signal)
                    
                    self._view_signals[a_view] = None
            
            
    enabled = GObject.Property(
        get_enabled, set_enabled, type=bool, default=False
    )
    color = GObject.Property(type=Gdk.RGBA)
    use_custom_color = GObject.Property(type=bool, default=False) 
    checkered = GObject.Property(type=bool, default=False)
    checks_size = GObject.Property(type=int, default=16)
    checks_primary_color = GObject.Property(type=Gdk.RGBA)
    checks_secondary_color = GObject.Property(type=Gdk.RGBA)
    
    
    def create_proxy(self, dialog, label):
        return BackgroundPreferencesTabProxy(self, dialog, label)
    
    
    def _connect_view(self, view):
        """ Connects to a view signals and stores the handler ids """
        self._view_signals[view] = [
            view.connect("destroy", self._destroy_view_cb),
            view.connect("draw-bg", self._draw_bg_cb)
        ]
    
    
    def _redraw_views(self):
        """ Redraws every view in the app """
        for a_view in self._view_signals:
            a_view.queue_draw()
    
    
    def _create_checkered_pattern(self):
        """ Creates the checkered background pattern """
        checks_size = self.checks_size
        checkered_surface = cairo.ImageSurface(
            cairo.FORMAT_RGB24, checks_size * 2, checks_size * 2
        )
        cr = cairo.Context(checkered_surface)
        
        Gdk.cairo_set_source_rgba(cr, self.checks_primary_color)
        cr.rectangle(0, 0, checks_size, checks_size)
        cr.rectangle(checks_size, checks_size, checks_size, checks_size)
        cr.fill()
        
        Gdk.cairo_set_source_rgba(cr, self.checks_secondary_color)
        cr.rectangle(checks_size, 0, checks_size, checks_size)
        cr.rectangle(0, checks_size, checks_size, checks_size)
        cr.fill()
        
        self._checkered_pattern = cairo.SurfacePattern(checkered_surface)
        self._checkered_pattern.set_extend(cairo.EXTEND_REPEAT)
    
    
    def _new_window_cb(self, app, window):
        """ Connects its background changing ability to a window view """
        if self.enabled:
            view = window.view
            self._connect_view(view)
            view.queue_draw()
        else:
            self._view_signals[window.view] = None
    
    
    def _changed_enabled_cb(self, *whatever):
        """ Redraw views when it's toggled on/off """
        self._redraw_views()
    
    
    def _changed_effect_cb(self, *whatever):
        """ Redraws views if it's enabled """
        if self.enabled:
            self._redraw_views()
    
    
    def _changed_checkered_cb(self, *whatever):
        """ Redraws views if the checkered property was turned on """
        
        if self.checkered:
            self._obsolete_checkered_pattern = True
        else:
            # Remove useless pattern
            self._checkered_pattern = None
        
        if self.enabled:
            self._redraw_views()
    
    
    def _changed_checks_cb(self, *whatever):
        """ Redraws views when its checks have been changed and they affect
        the views' background
        
        """
        self._obsolete_checkered_pattern = True
        if self.checkered and self.enabled:
            self._redraw_views()
    
    
    def _draw_bg_cb(self, view, cr, drawstate):
        """ Renders a background in a ImageView """
        use_custom_color, color, checkered, = self.get_properties(
            "use-custom-color", "color", "checkered"
        )
        if use_custom_color:
            Gdk.cairo_set_source_rgba(cr, color)
            cr.paint()
            
        if checkered:
            if self._obsolete_checkered_pattern:
                self._create_checkered_pattern()
            
            cr.set_source(self._checkered_pattern)
            cr.paint()
    
    
    def _destroy_view_cb(self, view):
        """ Disconnect signals and drop references to a ImageView """
        signals = self._view_signals.pop(view)
        for a_signal in signals:
            view.disconnect(a_signal)
    
    
    def _save_settings_cb(self, settings):
        """ Saves its settings """
        logger.debug("Saving background preferences...")
        utility.SetDictFromProperties(
            self, settings.data,
            "enabled", "use-custom-color",
            "checkered", "checks-size"
        )
        colors = "color", "checks-primary-color", "checks-secondary-color"
        for a_color_name in colors:
            a_color = self.get_property(a_color_name)
            settings.data[a_color_name] = a_color.to_string()
    
    
    def _load_settings_cb(self, settings):
        """ Loads its settings """
        logger.debug("Loading background preferences...")
        utility.SetPropertiesFromDict(
            self, settings.data,
            "enabled", "use-custom-color",
            "checkered", "checks-size"
        )
        
        colors = "color", "checks-primary-color", "checks-secondary-color"
        for a_color_name in colors:
            try:
                a_color_string = settings.data[a_color_name]
            except KeyError:
                pass
            else:
                # I don't get it either
                a_color = self.get_property(a_color_name)
                a_color.parse(a_color_string)
                self.set_property(a_color_name, a_color)


class BackgroundPreferencesTabPackage(extending.ComponentPackage):
    @staticmethod
    def add_on(app):
        background_tab = BackgroundPreferencesTab(app)
        app.components.add(PreferencesTab.CATEGORY, background_tab)

LoadedComponentPackages["background-tab"] =BackgroundPreferencesTabPackage
