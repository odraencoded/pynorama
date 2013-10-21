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
from gi.repository import Gtk, Gdk, GObject
from gettext import gettext as _
from math import pi as PI
logger = notifying.Logger("preferences")


class Magnifier(GObject.Object):
    def __init__(self, **kwargs):
        self._view = None
        
        kwargs.setdefault("outline-color", Gdk.RGBA(0, 0, 0 ,1))
        
        GObject.Object.__init__(self, **kwargs)
        self.view_connector = utility.SignalHandlerConnector(
            self, "view",
            draw_fg=self._draw_fg_cb,
            destroy=self._view_destroyed_cb
        )
        
        self.connect("notify::visible", self._changed_visibility_cb)
        appearance_properties = [
            "position-x", "position-y", "magnification", "draw-outline",
            "outline-thickness", "outline-scale", "outline-color"
        ]
        for a_property in appearance_properties:
            self.connect("notify::" + a_property, self._changed_effect_cb)
    
    def get_position(self):
        return Point(*self.get_properties("position-x", "position-y"))
    
    def set_position(self, value):
        self.set_properties(position_x=value[0], position_y=value[1])
    
    
    view = GObject.Property(type=object)
    visible = GObject.Property(type=bool, default=True)
    position = GObject.Property(get_position, set_position, type=object) 
    position_x = GObject.Property(type=int, default=0) 
    position_y = GObject.Property(type=int, default=0) 
    radius = GObject.Property(type=float, default=128)
    magnification = GObject.Property(type=float, default=2)
    
    draw_outline = GObject.Property(type=bool, default=True)
    outline_thickness = GObject.Property(type=float, default=.5)
    outline_scale = GObject.Property(type=bool, default=True)
    outline_color = GObject.Property(type=Gdk.RGBA)
    
    draw_background = GObject.Property(type=bool, default=False)
    
    def _changed_visibility_cb(self, *whatever):
        if self.view:
            self.view.queue_draw()
    
    
    def _changed_effect_cb(self, *whatever):
        if self.view and self.visible:
            self.view.queue_draw()
    
    
    def _draw_fg_cb(self, view, cr, drawstate):
        (
            visible, x, y, radius, magnification,
            draw_outline,
            outline_thickness, outline_scale, outline_color,
            draw_background
        ) = self.get_properties(
            "visible", "position-x", "position-y", "radius", "magnification",
            "draw-outline",
            "outline-thickness", "outline-scale", "outline-color",
            "draw-background",
        )
        if visible:
            if draw_outline:
                cr.save()
                cr.arc(x, y, radius, 0, PI * 2)
                
                # The thickness is always x2 because half of the arc path
                # is the center of the stroke, half of the stroke will be
                # overlaid by the magnified content so it is width is doubled
                # to compensate
                if outline_scale:
                    cr.set_line_width(outline_thickness * 2 * magnification)
                else:
                    cr.set_line_width(outline_thickness * 2)
                
                Gdk.cairo_set_source_rgba(cr, self.outline_color)
                cr.stroke()
                cr.restore()
        
            cr.save()
            cr.arc(x, y, radius, 0, PI * 2)
            cr.clip()
            
            # Modify transform properties of the drawstate so drawstate
            # features can be used
            
            normal_zoom = drawstate.magnification
            normal_offset = drawstate.real_offset
            glass_zoom = normal_zoom * magnification
            # In order to use drawstate.transform() the tranlation is
            # calculated like this. This equals to
            # translate(x, y); scale(magnification); translate(-x, -y)
            # scale(drawstate.magnification); translate(*drawstate.translation)
            glass_offset = (
                normal_offset
                + Point(x, y).scale(1 / normal_zoom)
                - Point(x, y).scale(1 / glass_zoom)
            )
            drawstate.set_magnification(glass_zoom)
            drawstate.set_offset(glass_offset)
            
            if draw_background:
                cr.save()
                cr.scale(drawstate.magnification, drawstate.magnification)
                cr.translate(*drawstate.translation)
                view.emit("draw-bg", cr, drawstate)
                cr.restore()
            
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
        outline_check = Gtk.CheckButton(
            _("Outline magnifier"),
            tooltip_text=_("Draw an outline around the magnifier")
        )
        
        # Outline thickness controls
        thickness_label = Gtk.Label(_("Thickness"))
        thickness_entry, thickness_adjust = widgets.SpinAdjustment(
            .5, .01, 256.0, .5, 6, align=True, digits=2,
        )
        thickness_entry.set_tooltip_text(
            _("The thickness of the outline in pixels")
        )
        thickness_scale = Gtk.CheckButton(
            _("Scale thickness"),
            tooltip_text=_("Increase the thickness with the magnifier zoom"),
        )
        
        # Outline colour controls
        outline_color_label = Gtk.Label(_("Color"))
        outline_color = Gtk.ColorButton(
            tooltip_text=_("The color of the magnifier outline"),
            title=_("Magnifier outline color"),
            use_alpha=True
        )
        
        outline_grid = widgets.Grid(
            (thickness_label, thickness_entry, thickness_scale),
            (outline_color_label, outline_color),
            align_first=True
        )
        
        background_check = Gtk.CheckButton(
            _("Draw background"),
            tooltip_text=_("Magnify the view background")
        )
        
        
        widgets.InitStack(self,
            outline_check,
            outline_grid,
            background_check
        )
        
        utility.Bind(tab.magnifier,
            ("draw-outline", outline_check, "active"),
            ("outline-thickness", thickness_adjust, "value"),
            ("outline-scale", thickness_scale, "active"),
            ("outline-color", outline_color, "rgba"), 
            ("draw-background", background_check, "active"),
            synchronize=True, bidirectional=True
        )
        
        utility.Bind(outline_check,
            ("active", outline_grid, "sensitive"),
            synchronize=True
        )
        
        self.show_all()


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


class ScrollMagnifyingGlass(MouseHandler):
    def __init__(self, magnifier_context, **kwargs):
        self.context = magnifier_context
        
        MouseHandler.__init__(self, **kwargs)
        self.events = MouseEvents.Scrolling
    
    
    zoom_effect = GObject.Property(type=float, default=1.5)
    radius_effect = GObject.Property(type=float, default=1.5)
    
    
    def scroll(self, view, point, direction, data):
        magnifier = self.context.get_magnifier(view)
        dx, dy = direction
        if dy < 0:
            magnifier.magnification *= -dy * self.zoom_effect
            magnifier.radius *= -dy * self.radius_effect
        elif dy > 0:
            magnifier.magnification /= dy * self.zoom_effect
            magnifier.radius /= dy * self.radius_effect


class HoverMagnifyingGlassFactory(extending.MouseHandlerFactory):
    CODENAME = "hover-magnifying-glass"
    def __init__(self, magnifier_context):
        extending.MouseHandlerFactory.__init__(
            self, HoverMagnifyingGlassFactory.CODENAME
        )
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


class ScrollMagnifyingGlassSettingsWidget(Gtk.Box):
    def __init__(self, handler):
        zoom_label = Gtk.Label(_("Zoom effect"))
        zoom_spin, zoom_adjust = widgets.SpinAdjustment(
            1.5, 1, 4, .1, .5, align=True, digits=2
        )
        zoom_line = widgets.Line(zoom_label, zoom_spin)
        
        radius_label = Gtk.Label(_("Radius effect"))
        radius_spin, radius_adjust = widgets.SpinAdjustment(
            1.5, 1, 4, .1, .5, align=True, digits=2
        )
        radius_line = widgets.Line(radius_label, radius_spin)
        
        utility.Bind(handler,
            ("zoom-effect", zoom_adjust, "value"),
            ("radius-effect", radius_adjust, "value"),
            bidirectional=True, synchronize=True
        )
        widgets.InitStack(self, zoom_line, radius_line)
        self.show_all()


class ScrollMagnifyingGlassFactory(extending.MouseHandlerFactory):
    CODENAME = "scroll-magnifying-glass"
    def __init__(self, magnifier_context):
        extending.MouseHandlerFactory.__init__(
            self, ScrollMagnifyingGlassFactory.CODENAME
        )
        self.context = magnifier_context
        self.create_settings_widget = ScrollMagnifyingGlassSettingsWidget
    
    
    @GObject.Property
    def label(self):
        return _("Scroll to Modify the Magnifying Glass")
    
    
    def create_default(self):
        return ScrollMagnifyingGlass(self.context)
    
    
    @staticmethod
    def get_settings(handler):
        return { "zoom-effect": handler.zoom_effect }
    
    
    def load_settings(self, settings):
        return ScrollMagnifyingGlass(self.context, **settings)


class MagnifierPackage(extending.ComponentPackage):
    def add_on(self, app):
        add_component = app.components.add
        magnifier_tab = MagnifierPreferencesTab(app)
        mouse_factories = (
            HoverMagnifyingGlassFactory(magnifier_tab),
            ScrollMagnifyingGlassFactory(magnifier_tab)
        )
        
        add_component(extending.PreferencesTab.CATEGORY, magnifier_tab)
        mouse_factory_category = extending.MouseHandlerFactory.CATEGORY
        for a_mouse_handler_factory in mouse_factories:
            add_component(mouse_factory_category, a_mouse_handler_factory)

LoadedComponentPackages["magnifying-glass"] = MagnifierPackage()
