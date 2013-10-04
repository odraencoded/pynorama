""" magnifier.py adds a magnifying glass to the image viewer
    The magnifying glass can be used to zoom a small, focused part of the view
    
    This component includes mouse handlers to control the magnifying glass """

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

from pynorama import utility, widgets, extending, notifying
from pynorama.utility import Point
from pynorama.extending import PreferencesTab, LoadedComponentPackages
from pynorama.mousing import MouseHandler, MouseEvents
from gi.repository import GObject, Gtk
from gettext import gettext as _
from math import pi as PI
logger = notifying.Logger("preferences")


class Magnifier(GObject.Object):
    def __init__(self, **kwargs):
        self._view = None
        GObject.Object.__init__(self, **kwargs)
        self.view_connector = utility.SignalHandlerConnector(
            self, "view",
            draw_fg=self._draw_fg_cb,
            destroy=self._view_destroyed_cb
        )
        
        self.connect("notify::visible", self._changed_visibility_cb)
        self.connect("notify::position-x", self._changed_effect_cb)
        self.connect("notify::position-y", self._changed_effect_cb)
        self.connect("notify::magnification", self._changed_effect_cb)
    
    
    def get_position(self):
        return Point(*self.get_properties("position-x", "position-y"))
    
    def set_position(self, value):
        self.set_properties(position_x=value[0], position_y=value[1])
    
    
    view = GObject.Property(type=object)
    visible = GObject.Property(type=bool, default=True)
    position = GObject.Property(get_position, set_position, type=object) 
    position_x = GObject.Property(type=int, default=0) 
    position_y = GObject.Property(type=int, default=0) 
    radius = GObject.Property(type=float, default=64)
    magnification = GObject.Property(type=float, default=2)
    
    
    def _changed_visibility_cb(self, *whatever):
        if self.view:
            self.view.queue_draw()
    
    
    def _changed_effect_cb(self, *whatever):
        if self.view and self.visible:
            self.view.queue_draw()
    
    
    def _draw_fg_cb(self, view, cr, drawstate):
        visible, x, y, radius, magnification = self.get_properties(
            "visible", "position-x", "position-y", "radius", "magnification"
        )
        if visible:
            cr.save()
            cr.arc(x, y, radius, 0, PI * 2)
            cr.clip()
            
            # Modify transform properties of the drawstate so drawstate
            # features can be used
            normal_zoom = drawstate.magnification
            normal_offset = drawstate.real_offset
            glass_zoom = normal_zoom * magnification
            glass_offset = normal_offset + Point(x, y).scale(1 / glass_zoom)
            drawstate.set_magnification(glass_zoom)
            drawstate.set_offset(glass_offset)
            
            drawstate.transform(cr)
            view.draw_frames(cr, drawstate)
            
            # Restore drawstate transform
            drawstate.set_offset(normal_offset)
            drawstate.set_magnification(normal_zoom)
            
            cr.restore()
    
    
    def _view_destroyed_cb(self, view):
        self.view = None


class BackgroundPreferencesTabProxy(Gtk.Box):
    def __init__(self, tab, dialog, label):
        Gtk.Box.__init__(self)


class MagnifierPreferencesTab(extending.PreferencesTab):
    """ Allows for customizing the background of the image viewer window """
    CODENAME = "magnifier-tab"
    def __init__(self, app):
        extending.PreferencesTab.__init__(
            self, MagnifierPreferencesTab.CODENAME
        )
        self.magnifier = Magnifier()
        
        # Create settings
        settings = app.settings.get_groups(
            "view", "magnifier", create=True
        )[-1]
        settings.connect("save", self._save_settings_cb)
        settings.connect("load", self._load_settings_cb)
    
    
    @GObject.Property
    def label(self):
        return _("Magnifier")
    
    
    def create_proxy(self, dialog, label):
        return BackgroundPreferencesTabProxy(self, dialog, label)
    
    
    def get_magnifier(self, view):
        self.magnifier.view = view
        return self.magnifier
    
    
    def _save_settings_cb(self, settings):
        """ Saves its settings """
        logger.debug("Saving magnifier preferences...")
    
    
    def _load_settings_cb(self, settings):
        """ Loads its settings """
        logger.debug("Loading magnifier preferences...")


class HoverMagnifyingGlass(MouseHandler):
    def __init__(self, magnifier_context):
        MouseHandler.__init__(self)
        
        self.context = magnifier_context
        self.events = MouseEvents.Hovering
    
    
    def hover(self, view, to_point, from_point, data):
        self.context.get_magnifier(view).position = to_point


class HoverMagnifyingGlassFactory(extending.MouseHandlerFactory):
    def __init__(self, magnifier_context):
        extending.MouseHandlerFactory.__init__(self)
        self.context = magnifier_context
    
    
    @GObject.Property
    def label(self):
        return _("Hover Magnifying Glass")
    
    
    def create_default(self):
        return HoverMagnifyingGlass(self.context)
    
    
    @staticmethod
    def get_settings(handler):
        return {}
    
    
    def load_settings(self, settings):
        return HoverAndDragHandler(self.context)


class BackgroundPreferencesTabPackage(extending.ComponentPackage):
    def add_on(self, app):
        add_component = app.components.add
        magnifier_tab = MagnifierPreferencesTab(app)
        mice_factory = HoverMagnifyingGlassFactory(magnifier_tab)
        
        add_component(extending.PreferencesTab.CATEGORY, magnifier_tab)
        add_component(extending.MouseHandlerFactory.CATEGORY, mice_factory)

LoadedComponentPackages["magnifying-glass"] = BackgroundPreferencesTabPackage()
