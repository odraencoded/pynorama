# coding=utf-8

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
        self.view_connector = utility.GPropertySignalsConnector(
            self, "view", **{
                "draw-fg": self._draw_fg_cb,
                "destroy": self._view_destroyed_cb
            }
        )
        
        self.connect("notify::enabled", self._changed_enabled_cb)
        self.connect("notify::magnification", self._changed_magnification_cb)
        
        appearance_properties = [
            "position-x", "position-y", "keep-inside",
            "base-width", "incremental-width",
            "base-height", "incremental-height",
            "circle-shape", "draw-outline",
            "outline-thickness", "outline-scale", "outline-color",
        ]
        for a_property in appearance_properties:
            self.connect("notify::" + a_property, self._changed_effect_cb)
    
    
    def get_width(self):
        self._get_dimension("width")
    
    def set_width(self, value):
        self._set_dimension("width", value)
    
    
    def get_height(self):
        self._get_dimension("height")
    
    def set_height(self, value):
        self._set_dimension("height", value)
    
    
    def _get_dimension(self, dimension):
        base, incremental, magnification = self.get_properties(
            "base-" + dimension, "incremental-" + dimension, "magnification"
        )
        return base + incremental * max(0, magnification - 1)
    
    
    def _set_dimension(self, dimension, value):
        incremental, magnification = self.get_properties(
            "incremental-" + dimension, "magnification"
        )
        
        self.set_property(
            "base-" + dimension, value - incremental * max(0, magnification - 1)
        ) 
    
    
    def get_visible(self):
        return self.enabled and self.magnification > 1
    
    
    view = GObject.Property(type=object)
    visible = GObject.Property(get_visible, type=bool, default=False)
    enabled = GObject.Property(type=bool, default=True)
    
    position = utility.PointProperty("position-x", "position-y")
    position_x = GObject.Property(type=int, default=0) 
    position_y = GObject.Property(type=int, default=0) 
    
    width = GObject.Property(get_width, set_width, type=float)
    base_width = GObject.Property(type=float, default=32)
    incremental_width = GObject.Property(type=float, default=32)
    
    height = GObject.Property(get_height, set_height, type=float)
    base_height = GObject.Property(type=float, default=32)
    incremental_height = GObject.Property(type=float, default=32)
    
    magnification = GObject.Property(type=float, default=1)
    
    circle_shape = GObject.Property(type=bool, default=False)
    keep_inside = GObject.Property(type=bool, default=True)
    
    draw_outline = GObject.Property(type=bool, default=True)
    outline_thickness = GObject.Property(type=float, default=.5)
    outline_scale = GObject.Property(type=bool, default=True)
    outline_color = GObject.Property(type=Gdk.RGBA)
    
    draw_background = GObject.Property(type=bool, default=False)
    
    
    def _changed_enabled_cb(self, *whatever):
        if self.view:
            self.view.queue_draw()
    
    
    def _changed_effect_cb(self, *whatever):
        if self.view and self.visible:
            self.view.queue_draw()
    
    
    def _changed_magnification_cb(self, *whatever):
        if self.view and self.enabled:
            self.view.queue_draw()
    
    
    def _draw_fg_cb(self, view, cr, drawstate):
        """ Callback for rendering the magnifier in a view """
        (
            enabled,
            base_width, incremental_width,
            base_height, incremental_height,
            magnification,
        ) = self.get_properties(
            "enabled",
            "base_width", "incremental_width",
            "base_height", "incremental_height",
            "magnification",
        )
        
        # Calculating dimensions
        width = base_width + incremental_width * max(0, magnification - 1)
        height = base_height + incremental_height * max(0, magnification - 1)
        
        if enabled and magnification > 1 and width > 0 and height > 0:
            (
                px, py, keep_inside,
                circle_shape, draw_outline, 
                outline_thickness, outline_scale, outline_color,
                draw_background
            ) = self.get_properties(
                "position-x", "position-y", "keep-inside",
                "circle-shape", "draw-outline",
                "outline-thickness", "outline-scale", "outline-color",
                "draw-background",
            )
            
            # Target coordinates
            tx, ty = px, py
            
            if circle_shape:
                if keep_inside:
                    width_b = width * .6
                    px = max(width_b, min(px, drawstate.width - width_b))
                    py = max(width_b, min(py, drawstate.height - width_b))
                
                cr.arc(px, py, width / 2, 0, PI * 2)
                
            else:
                # Rounding the values will result in making an integer
                # rectangle path before the .clip() which speeds up rendering
                
                left = px - width / 2
                top = py - height / 2
                width = round(width)
                height = round(height)
                if keep_inside:
                    left = max(0, min(left, drawstate.width - width))
                    top = max(0, min(top, drawstate.height - height))
                
                left, top = round(left), round(top)
                cr.rectangle(left, top, width, height)
                
            shape_path = cr.copy_path()
            
            # Drawing outline
            if draw_outline:
                cr.save()
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
            cr.append_path(shape_path)
            cr.clip()
            
            # Modify transform properties of the drawstate so drawstate
            # features can be used
            
            normal_zoom = drawstate.magnification
            normal_offset = drawstate.real_offset
            glass_zoom = normal_zoom * magnification
            # In order to use drawstate.transform() the tranlation is
            # calculated like this. This equals to
            # translate(px, py); scale(magnification); translate(-tx, -ty)
            # scale(drawstate.magnification); translate(*drawstate.translation)
            glass_offset = (
                normal_offset
                + Point(tx, ty).scale(1 / normal_zoom)
                - Point(px, py).scale(1 / glass_zoom)
            )
            drawstate.set_magnification(glass_zoom)
            drawstate.set_offset(glass_offset)
            
            if draw_background:
                cr.save()
                
                cr.translate(px, py)
                cr.scale(magnification, magnification)
                cr.translate(-tx, -ty)
                
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
        # Size controls
        base_size_label = Gtk.Label(_("Base size"))
        base_width_entry, base_width_adjust = widgets.SpinAdjustment(
            64, 0, 1024, 16, 128, align=True,
        )
        base_height_entry, base_height_adjust = widgets.SpinAdjustment(
            64, 0, 1024, 16, 128, align=True,
        )
        
        base_width_entry.set_tooltip_text(
            _("The starting width of the magnifying glass in pixels")
        )
        base_height_entry.set_tooltip_text(
            _("The starting height of the magnifying glass in pixels")
        )
        base_multiply_label = Gtk.Label(_("×"))
        
        # Incremental size controls
        increment_label = Gtk.Label(_("Incremental size"))
        (
            increment_width_entry,
            increment_width_adjust
        ) = widgets.SpinAdjustment(
            64, 0, 1024, 16, 128, align=True,
        )
        (
            increment_height_entry,
            increment_height_adjust
        ) = widgets.SpinAdjustment(
            64, 0, 1024, 16, 128, align=True,
        )
        increment_tooltip = _(
            "How much the magnifying glass will expand with each"
            " magnifying factor."
        )
        increment_width_entry.set_tooltip_text(increment_tooltip)
        increment_height_entry.set_tooltip_text(increment_tooltip)
        
        increment_multiply_label = Gtk.Label(_("×"))
        
        size_grid = widgets.Grid(
            (
                base_size_label,
                base_width_entry,
                base_multiply_label,
                base_height_entry
            ),
            (
                increment_label,
                increment_width_entry,
                increment_multiply_label,
                increment_height_entry
            ),
            align_first=True
        )
        
        # Shape controls
        circle_check = Gtk.CheckButton(
            _("Circle shaped"),
            tooltip_text=_(
                "Display a round magnifying glass instead of a"
                " square one. The circular shape is slower."
            )
        )
        keep_inside_check = Gtk.CheckButton(
            _("Keep inside"),
            tooltip_text=_("Keep the magnifying glass inside the window")
        )
        
        
        # Outline controls
        outline_check = Gtk.CheckButton(
            _("Outline magnifier"),
            tooltip_text=_("Draw an outline around the magnifying glass")
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
            tooltip_text=_(
                "Scale the outline thickness with the magnification"
            ),
        )
        
        # Outline colour controls
        outline_color_label = Gtk.Label(_("Color"))
        outline_color = Gtk.ColorButton(
            tooltip_text=_("The color of the magnifying glass outline"),
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
        
        # Pack everything
        widgets.InitStack(self,
            size_grid,
            circle_check,
            keep_inside_check,
            outline_check,
            outline_grid,
            background_check
        )
        
        # Show everything
        self.show_all()
        self.set_no_show_all(True)
        
        # Bind everything
        utility.Bind(tab.magnifier,
            ("base-width", base_width_adjust, "value"),
            ("base-height", base_height_adjust, "value"),
            ("incremental-width", increment_width_adjust, "value"),
            ("incremental-height", increment_height_adjust, "value"),
            ("circle-shape", circle_check, "active"),
            ("keep-inside", keep_inside_check, "active"),
            ("draw-outline", outline_check, "active"),
            ("outline-thickness", thickness_adjust, "value"),
            ("outline-scale", thickness_scale, "active"),
            ("outline-color", outline_color, "rgba"), 
            ("draw-background", background_check, "active"),
            synchronize=True, bidirectional=True
        )
        
        utility.Bind(tab.magnifier,
            ("draw-outline", outline_grid, "sensitive"),
            synchronize=True
        )
        
        utility.Bind(tab.magnifier,
            ("circle-shape", base_multiply_label, "sensitive"),
            ("circle-shape", base_height_entry, "sensitive"),
            ("circle-shape", increment_multiply_label, "sensitive"),
            ("circle-shape", increment_height_entry, "sensitive"),
            
            ("circle-shape", base_multiply_label, "visible"),
            ("circle-shape", base_height_entry, "visible"),
            ("circle-shape", increment_multiply_label, "visible"),
            ("circle-shape", increment_height_entry, "visible"),
            synchronize=True, invert=True
        )


class MagnifierPreferencesTab(extending.PreferencesTab):
    """ Allows for customizing the background of the image viewer window """
    CODENAME = "magnifier-tab"
    def __init__(self, app):
        extending.PreferencesTab.__init__(
            self, MagnifierPreferencesTab.CODENAME, label=_("Magnifier")
        )
        self.magnifier = Magnifier()
        
        # Create settings
        settings = app.settings.get_groups(
            "view", "magnifier", create=True
        )[-1]
        settings.connect("save", self._save_settings_cb)
        settings.connect("load", self._load_settings_cb)
    
    
    def create_proxy(self, dialog, label):
        return BackgroundPreferencesTabProxy(self, dialog, label)
    
    
    def get_magnifier(self, view):
        self.magnifier.view = view
        return self.magnifier
    
    
    def _save_settings_cb(self, settings):
        """ Saves its settings """
        logger.debug("Saving magnifier preferences...")
        utility.SetDictFromProperties(
            self.magnifier, settings.data,
            "base-width", "incremental-width",
            "base-height", "incremental-height",
            "circle-shape", "keep-inside",
            "draw-outline", "outline-thickness", "outline-scale",
            "draw-background"
        )
        color_string = self.magnifier.outline_color.to_string()
        settings.data["outline-color"] = color_string
    
    
    def _load_settings_cb(self, settings):
        """ Loads its settings """
        logger.debug("Loading magnifier preferences...")
        utility.SetPropertiesFromDict(
            self.magnifier, settings.data,
            "base-width", "incremental-width",
            "base-height", "incremental-height",
            "circle-shape", "keep-inside",
            "draw-outline", "outline-thickness", "outline-scale",
            "draw-background"
        )
        
        try:
            color_string = settings.data["outline-color"]
        except KeyError:
            pass
        else:
            color = self.magnifier.outline_color
            color.parse(color_string)
            self.magnifier.outline_color = color


class MoveMagnifyingGlass(MouseHandler):
    def __init__(self, drag, magnifier_context):
        MouseHandler.__init__(self)
        
        self.context = magnifier_context
        
        if drag:
            self.events = MouseEvents.Pressing
        else:
            self.events = MouseEvents.Moving | MouseEvents.Crossing
    
    
    def press(self, view, point, data):
        inside = (
            point.x >= 0 and point.y >= 0 and
            point.x < view.get_allocated_width() and 
            point.y < view.get_allocated_height()
        )
        self.context.get_magnifier(view).set_properties(
            position=point, enabled=inside
        )
    
    
    def cross(self, view, point, inside, data):
        magnifier = self.context.get_magnifier(view)
        magnifier.set_properties(position=point, enabled=inside)
    
    
    def move(self, view, to_point, from_point, pressed, data):
        self.context.get_magnifier(view).position = to_point


class ScrollMagnifyingGlass(MouseHandler):
    def __init__(self, magnifier_context, **kwargs):
        self.context = magnifier_context
        
        MouseHandler.__init__(self, **kwargs)
        self.events = MouseEvents.Scrolling
    
    
    change_zoom = GObject.Property(type=bool, default=True)
    zoom_effect = GObject.Property(type=float, default=1.5)
    
    
    change_size = GObject.Property(type=bool, default=False)
    width_effect = GObject.Property(type=float, default=32)
    height_effect = GObject.Property(type=float, default=32)
    
    
    def scroll(self, view, point, direction, data):
        dx, dy = direction
        
        (
            change_zoom, zoom_effect,
            change_size, width_effect, height_effect
        ) = self.get_properties(
            "change-zoom", "zoom-effect",
            "change-size", "width-effect", "height-effect"
        )
        
        magnifier = self.context.get_magnifier(view)
        magnification, base_width, base_height = magnifier.get_properties(
            "magnification", "base-width", "base-height"
        )
        
        props = {}
        if change_zoom:
            if dy < 0:
                if magnification < 1:
                    magnification = 1
                
                magnifier.magnification = magnification * -dy * zoom_effect
                
            elif dy > 0 and magnification > 1:
                props["magnification"] = magnification / (dy * zoom_effect)
        
        if change_size:
            new_width_effect = base_width + width_effect * -dy
            new_height_effect = base_height + height_effect * -dy
            
            if new_width_effect > 0:
                props["base-width"] = new_width_effect
            
            if new_height_effect > 0:
                props["base-height"] = new_height_effect
        
        magnifier.set_properties(**props)


class MoveMagnifyingGlassFactory(extending.MouseHandlerFactory):
    MOVE_CODENAME = "move-magnifying-glass"
    POINT_CODENAME = "drag-magnifying-glass"
    def __init__(self, drag, magnifier_context):
        if drag:
            codename = MoveMagnifyingGlassFactory.POINT_CODENAME
        else:
            codename = MoveMagnifyingGlassFactory.MOVE_CODENAME
            
        extending.MouseHandlerFactory.__init__(self, codename)
        
        self.drag = drag
        self.context = magnifier_context
    
    
    @GObject.Property
    def label(self):
        if self.drag:
            return _("Magnifying Glass: Drag")
        else:
            return _("Magnifying Glass: Hover")
    
    
    def create_default(self):
        return MoveMagnifyingGlass(self.drag, self.context)
    
    
    @staticmethod
    def get_settings(handler):
        return {}
    
    
    def load_settings(self, settings):
        return MoveMagnifyingGlass(self.drag, self.context)


class ScrollMagnifyingGlassSettingsWidget(Gtk.Box):
    def __init__(self, handler):
        # Zoom controls
        zoom_check = Gtk.CheckButton(_("Magnification effect"))
        zoom_entry, zoom_adjust = widgets.SpinAdjustment(
            1.5, 1.1, 4, .1, .5, align=True, digits=2
        )
        utility.SetProperties(
            zoom_check, zoom_entry, 
            tooltip_text=_("Changes the magnification of the glass")
        )
        
        # Size controls
        size_check = Gtk.CheckButton(_("Size effect"))
        width_entry, width_adjust = widgets.SpinAdjustment(
            32, 8, 512, 4, 32, align=True
        )
        height_entry, height_adjust = widgets.SpinAdjustment(
            32, 8, 512, 4, 32, align=True
        )
        size_multiply_label = Gtk.Label(_("×"))
        size_line = widgets.Line(
            width_entry,
            size_multiply_label,
            height_entry
        )
        
        utility.SetProperties(
            size_check, size_line, 
            tooltip_text=_("Changes the base size of the magnifying glass")
        )
        
        grid = widgets.Grid(
            (zoom_check, zoom_entry),
            (size_check, size_line),
        )
        
        widgets.InitStack(self, grid)
        
        self.show_all()
        self.set_no_show_all(True)
        
        # Bind properties
        utility.Bind(handler,
            ("change-zoom", zoom_check, "active"),
            ("zoom-effect", zoom_adjust, "value"),
            ("change-size", size_check, "active"),
            ("width-effect", width_adjust, "value"),
            ("height-effect", height_adjust, "value"),
            bidirectional=True, synchronize=True
        )
        
        # Bind sensitivity
        utility.Bind(handler,
            ("change-zoom", zoom_entry, "sensitive"),
            ("change-size", size_line, "sensitive"),
            synchronize=True
        )
        
        utility.Bind(handler.context.magnifier,
            ("circle-shape", height_entry, "sensitive"),
            ("circle-shape", size_multiply_label, "sensitive"),
            ("circle-shape", height_entry, "visible"),
            ("circle-shape", size_multiply_label, "visible"),
            synchronize=True, invert=True
        )


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
        return _("Magnifying Glass Zoom: Scroll Wheel")
    
    
    def create_default(self):
        return ScrollMagnifyingGlass(self.context)
    
    
    @staticmethod
    def get_settings(handler):
        return utility.GetPropertiesDict(handler,
            "change-zoom", "zoom-effect",
            "change-size", "width-effect", "height-effect"
        )
    
    
    def load_settings(self, settings):
        return ScrollMagnifyingGlass(self.context, **settings)


class MagnifierPackage(extending.ComponentPackage):
    def add_on(self, app):
        add_component = app.components.add
        magnifier_tab = MagnifierPreferencesTab(app)
        mouse_factories = (
            MoveMagnifyingGlassFactory(True, magnifier_tab),
            MoveMagnifyingGlassFactory(False, magnifier_tab),
            ScrollMagnifyingGlassFactory(magnifier_tab)
        )
        
        add_component(extending.PreferencesTab.CATEGORY, magnifier_tab)
        mouse_factory_category = extending.MouseHandlerFactory.CATEGORY
        for a_mouse_handler_factory in mouse_factories:
            add_component(mouse_factory_category, a_mouse_handler_factory)

LoadedComponentPackages["magnifying-glass"] = MagnifierPackage()
