""" mice.py adds a few basic mouse handlers to the image viewer """

""" ...And this file is part of Pynorama.
    
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


from gi.repository import Gdk, GObject, Gtk
from gettext import gettext as _
import math
from pynorama import utility, widgets, extending, mousing
from pynorama.mousing import (
    MouseHandler, MouseEvents,
    MouseHandlerPivot, MouseHandler,
    PivotedHandlerSettingsWidget
)

class HoverAndDragHandler(MouseHandler):
    ''' Pans a view on mouse dragging, or on mouse hovering '''
    
    def __init__(
        self, drag=False, speed=-1.0, relative_speed=True
    ):
        MouseHandler.__init__(self)
        
        if drag:
            self.events = MouseEvents.Dragging
        
        else:
            self.events = MouseEvents.Hovering
            
        self.speed = speed
        self.relative_speed = relative_speed
    
    speed = GObject.Property(type=float, default=1)
    relative_speed = GObject.Property(type=bool, default=True)
    
    def hover(self, view, to_point, from_point, data):
        shift = to_point - from_point
        scale, relative_speed = self.get_properties("speed", "relative-speed")
        if relative_speed:
            scale /= view.magnification
        
        scaled_shift = shift * (scale, scale)
        view.pan(scaled_shift)
    
    
    def start_dragging(self, view, *etc):
        fleur_cursor = Gdk.Cursor(Gdk.CursorType.FLEUR)
        view.get_window().set_cursor(fleur_cursor)
    
    
    drag = hover # lol.
    
    
    def stop_dragging(self, view, *etc):
        view.get_window().set_cursor(None)



class SpinHandler(MouseHandler):
    ''' Spins a view '''
    
    SpinThreshold = 5
    SoftRadius = 25
    
    
    def __init__(self, frequency=1, pivot=None):
        MouseHandler.__init__(self)
        
        self.events = MouseEvents.Dragging
        
        self.frequency = frequency
        
        if pivot:
            self.pivot = pivot
            
        else:
            self.pivot = MouseHandlerPivot()
    
    
    # Number of complete turns in the view per revolution around the pivot
    frequency = GObject.Property(type=float, default=1)
    
    def start_dragging(self, view, point, data):
        widget_pivot = self.pivot.convert_point(view, point)
        
        return widget_pivot, view.get_pin(widget_pivot)
    
    
    def drag(self, view, to_point, from_point, data):
        pivot, pin = data
        
        # Get vectors from the pivot
        to_delta = to_point - pivot
        from_delta = from_point - pivot
        
        # Get rotational delta, multiply it by frequency
        to_angle = math.degrees(math.atan2(*to_delta))
        from_angle = math.degrees(math.atan2(*from_delta))
        rotation_effect = (from_angle - to_angle) * self.frequency
        
        # Modulate degrees
        rotation_effect %= 360 if rotation_effect >= 0 else -360
        if rotation_effect > 180:
            rotation_effect -= 360
        if rotation_effect < -180:
            rotation_effect += 360 
            
        # Thresholding stuff
        square_distance = to_delta.get_square_length()
        if square_distance > SpinHandler.SpinThreshold ** 2:
            # Falling out stuff
            square_soft_radius = SpinHandler.SoftRadius ** 2
            if square_distance < square_soft_radius:
                fallout_effect = square_distance / square_soft_radius
                rotation_effect *= fallout_effect
            
            # Changing the rotation(finally)
            view.rotation = (view.rotation + rotation_effect) % 360
            # Anchoring!!!
            view.adjust_to_pin(pin)
            
        return data


class StretchHandler(MouseHandler):
    ''' Stretches/shrinks a view '''
    
    MinDistance = 10
    
    def __init__(self, pivot=None):
        MouseHandler.__init__(self)
        self.events = MouseEvents.Dragging
        
        if pivot:
            self.pivot = pivot
        else:
            self.pivot = MouseHandlerPivot(mode=mousing.PivotMode.Fixed)
        
        
    def start_dragging(self, view, start_point, data):
        widget_size = view.get_widget_size()
        widget_pivot = self.pivot.convert_point(view, start_point)
        
        start_diff = start_point - widget_pivot
        distance = max(StretchHandler.MinDistance, start_diff.get_length())
        
        zoom = view.magnification
        zoom_ratio = zoom / distance
        
        return zoom_ratio, widget_pivot, view.get_pin(widget_pivot)
    
    
    def drag(self, view, to_point, from_point, data):
        zoom_ratio, widget_pivot, pin = data
        
        # Get vectors from the pivot
        point_diff = to_point - widget_pivot
        distance = max(StretchHandler.MinDistance, point_diff.get_length())
        
        new_zoom = distance * zoom_ratio
        
        view.magnification = new_zoom
        view.adjust_to_pin(pin)
        
        return data


class ScrollHandler(MouseHandler):
    ''' Scrolls a view '''
    
    def __init__(self, inverse=None, **kwargs):
        MouseHandler.__init__(self, **kwargs)
        self.events = MouseEvents.Rolling
        
        if inverse:
            self.inverse_horizontal, self.inverse_vertical = inverse
    
    # Scrolling speed
    pixel_speed = GObject.Property(type=int, default=300)
    relative_speed = GObject.Property(type=float, default=.3)
    
    # If this is true, speed is scaled to the view dimensions
    relative_scrolling = GObject.Property(type=bool, default=True)
    
    # Inverse horizontal and vertical axis, this happens after everything else
    inverse_horizontal = GObject.Property(type=bool, default=False)
    inverse_vertical = GObject.Property(type=bool, default=False)
    
    # Whether to swap axes
    swap_axes = GObject.Property(type=bool, default=False)
    
    # Rotate scrolling shift with view rotation
    rotate = GObject.Property(type=bool, default=False)
    
    
    def scroll(self, view, position, direction, data):
        delta = direction
        view_size = view.get_view()[2:]
        
        (
            relative_scrolling,
            relative_speed, pixel_speed,
            rotate, swap_axes,
            inverse_horizontal, inverse_vertical
        ) = self.get_properties(
            "relative-scrolling",
            "relative-speed", "pixel-speed",
            "rotate", "swap-axes",
            "inverse-horizontal", "inverse-vertical"
        )
        
        if relative_scrolling:
            delta = delta.scale(relative_speed) * view_size
            
        else:
            delta = delta.scale(pixel_speed)
        
        delta = delta.flip(inverse_horizontal, inverse_vertical)
        if rotate:
            delta = delta.spin(view.get_rotation_radians())
        
        if swap_axes:
            delta = delta.swap()
        
        view.pan(delta)


class ZoomHandler(MouseHandler):
    ''' Zooms a view '''
    
    def __init__(
        self, effect=2, minify_anchor=None, magnify_anchor=None,
        horizontal=False, inverse=False
    ):
        MouseHandler.__init__(self)
        self.events = MouseEvents.Scrolling
        
        if not minify_anchor:
            minify_anchor = MouseHandlerPivot(mode=mousing.PivotMode.Mouse)
            
        if not magnify_anchor:
            magnify_anchor = MouseHandlerPivot(mode=mousing.PivotMode.Mouse)
            
        self.minify_anchor = minify_anchor
        self.magnify_anchor = magnify_anchor
        
        self.effect = effect
        self.inverse = inverse
        self.horizontal = horizontal
    
    
    effect = GObject.Property(type=float, default=2)
    inverse = GObject.Property(type=bool, default=False)
    horizontal = GObject.Property(type=bool, default=False)
    
    
    def scroll(self, view, point, direction, data):
        dx, dy = direction
        delta = (dx if self.horizontal else dy) * -1
        
        if delta and self.effect:
            if self.inverse:
                power = self.effect ** -delta
            else:
                power = self.effect ** delta
            
            pivot = self.minify_anchor if power < 0 else self.magnify_anchor
            anchor_point = pivot.convert_point(view, point)
            
            pin = view.get_pin(anchor_point)
            view.magnification *= power
            view.adjust_to_pin(pin)


class GearHandler(MouseHandler):
    ''' Spins a view with each scroll tick '''
    
    def __init__(self, pivot=None, horizontal=False, effect=30):
        MouseHandler.__init__(self)
        self.events = MouseEvents.Scrolling
        
        if pivot:
            self.pivot = pivot
        else:
            self.pivot = MouseHandlerPivot()
            
        self.effect = effect
        self.horizontal = horizontal
    
    
    effect = GObject.Property(type=float, default=30)
    horizontal = GObject.Property(type=bool, default=False)
    
    
    def scroll(self, view, point, direction, data):
        dx, dy = direction
        delta = (dx if self.horizontal else dy) * -1
        
        anchor_point = self.pivot.convert_point(view, point)
            
        pin = view.get_pin(anchor_point)
        view.rotate(self.effect * delta)
        view.adjust_to_pin(pin)


class HoverAndDragHandlerSettingsWidget(Gtk.Box):
    ''' A settings widget made for a HoverMouseHandler and DragMouseHandler ''' 
    def __init__(self, handler, drag=True):
        label = _("Panning speed")
        speed_label = Gtk.Label(label)
        speed_entry, speed_adjustment = widgets.SpinAdjustment(
            0, -10, 10, .1, 1, align=True, digits=2
        )
        speed_line = widgets.Line(speed_label, speed_entry)
        
        speed_scale = widgets.ScaleAdjustment(adjustment=speed_adjustment,
            marks=[
                (-10, _("Pan Image")), (-1, None),
                (0, _("Inertia")),
                (10, _("Pan View")), (1, None)
            ], origin=False, percent=True, absolute=True
        )
        
        label = _("Speed relative to zoom")
        speed_relative = Gtk.CheckButton(label)
        
        widgets.InitStack(self, speed_line, speed_scale, speed_relative)
        
        # Bind properties
        utility.Bind(handler,
            ("speed", speed_adjustment, "value"),
            ("relative-speed", speed_relative, "active"),
            bidirectional=True, synchronize=True
        )
        
        self.show_all()


class HoverAndDragHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self, drag):
        extending.MouseHandlerFactory.__init__(self)
        
        self.drag = drag
        if drag:
            self.codename = "drag"
            
        else:
            self.codename = "hover"
        
        self.create_settings_widget = HoverAndDragHandlerSettingsWidget
    
    
    @GObject.Property
    def label(self):
        return _("Drag to Pan" if self.drag else "Move Mouse to Pan")
    
    
    def create_default(self):
        return HoverAndDragHandler(
            drag = self.drag,
            speed = -1 if self.drag else 0.2
        )
        
        
    @staticmethod
    def get_settings(handler):
        return {
            "speed": handler.speed,
            "relative_speed": handler.relative_speed
        }
    
    
    def load_settings(self, settings):
        return HoverAndDragHandler(drag=self.drag, **settings)


class SpinHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        self.handler = handler
        
        # Add line for fequency
        label = _("Frequency of turns")
        frequency_label = Gtk.Label(label)
        frequency_entry, frequency_adjustment = widgets.SpinAdjustment(
            1, -9, 9, .1, 1, digits=2, align=True
        )
        frequency_line = widgets.Line(
            frequency_label, frequency_entry, expand=frequency_entry
        )
        
        # Get pivot widgets, pack everyting
        pivot_widgets = self.create_pivot_widgets(handler.pivot)
        widgets.InitStack(self, frequency_line, *pivot_widgets)
        self.show_all()
        
        # Bind properties
        utility.Bind(handler,
            ("frequency", frequency_adjustment, "value"),
            bidirectional=True, synchronize=True
        )


class SpinHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "spin")
        self.create_default = SpinHandler
        self.create_settings_widget = SpinHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Drag to Spin")
        
        
    @staticmethod
    def get_settings(handler):
        return {
            "frequency": handler.frequency,
            "pivot": handler.pivot.get_settings()
        }
        
        
    @staticmethod
    def load_settings(settings):
        clone = dict(settings)
        pivot = MouseHandlerPivot(settings=clone.pop("pivot"))
        return SpinHandler(pivot=pivot, **clone)


class StretchHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        pivot_widgets = self.create_pivot_widgets(handler.pivot, anchor=True)
        widgets.InitStack(self, *pivot_widgets[1:])
        
        self.show_all()


class StretchHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "stretch")
        self.create_default = StretchHandler
        self.create_settings_widget = StretchHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Drag to Stretch")
    
    
    @staticmethod
    def get_settings(handler):
        return handler.pivot.get_settings()
    
    
    @staticmethod
    def load_settings(settings):
        pivot = MouseHandlerPivot(settings=settings)
        return StretchHandler(pivot=pivot)


class ScrollHandlerSettingsWidget(Gtk.Box):
    def __init__(self, handler):
        self.handler = handler
        
        # Fixed pixel speed
        label = _("Fixed pixel scrolling speed")
        pixel_radio = Gtk.RadioButton(label=label)
        pixel_entry, pixel_adjust = widgets.SpinAdjustment(
            300, 0, 9001, 20, 150, align=True
        )
        pixel_line = widgets.Line(
            pixel_radio, pixel_entry, expand=pixel_entry
        )
        self.pixel_radio = pixel_radio
        
        # Relative pixel speed
        label = _("Relative percentage scrolling speed")
        relative_radio = Gtk.RadioButton(label=label, group=pixel_radio)
        relative_scale, relative_adjust = widgets.ScaleAdjustment(
            1, 0, 3, .04, .5, percent=True,
            marks = [(0, _("Inertia")), (1, _("Entire Window"))]
        )
        self.relative_radio = relative_radio
        
        label = _("Inverse vertical scrolling")
        inversev = Gtk.CheckButton(label=label)
        label = _("Inverse horizontal scrolling")
        inverseh = Gtk.CheckButton(label=label)
        
        label = _("Rotate scrolling to image coordinates")
        rotate = Gtk.CheckButton(label)
        
        label = _("Swap horizontal and vertical axes")
        swap = Gtk.CheckButton(label=label)
        
        widgets.InitStack(self,
            pixel_line, relative_radio, relative_scale,
            inverseh, inversev, rotate, swap
        )
        self.show_all()
        
        # Bind properties
        handler.connect("notify::relative-scrolling", self._refresh_speed_mode)
        pixel_radio.connect("toggled", self._speed_mode_chosen, False)
        relative_radio.connect("toggled", self._speed_mode_chosen, True)
        
        utility.BindSame("active", "sensitive",
            (relative_radio, relative_scale),
            (pixel_radio, pixel_entry),
            synchronize=True
        )
        utility.Bind(handler, 
            ("pixel-speed", pixel_adjust, "value"),
            ("relative-speed", relative_adjust, "value"),
            ("inverse-horizontal", inverseh, "active"),
            ("inverse-vertical", inversev, "active"),
            ("rotate", rotate, "active"),
            ("swap-axes", swap, "active"),
            bidirectional=True, synchronize=True
        )    
        self._refresh_speed_mode(handler)
    
    
    def _refresh_speed_mode(self, handler, *data):
        if handler.relative_scrolling:
            self.relative_radio.set_active(True)
        else:
            self.pixel_radio.set_active(True)
    
    
    def _speed_mode_chosen(self, radio, value):
        if radio.get_active() and self.handler.relative_scrolling != value:
            self.handler.relative_scrolling = value


class ScrollHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "scroll")
        self.create_default = ScrollHandler
        self.create_settings_widget = ScrollHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Scroll to Pan")
        
    
    @staticmethod
    def get_settings(handler):
        result = {
            "relative-scrolling" : handler.relative_scrolling,
            "inverse": (handler.inverse_horizontal, handler.inverse_vertical),
            "rotate": handler.rotate,
            "swap-axes": handler.swap_axes,
        }
        if handler.relative_scrolling:
            result["relative-speed"] = handler.relative_speed
        else:
            result["pixel-speed"] = handler.pixel_speed
        return result
    
    
    @staticmethod
    def load_settings(settings):
        return ScrollHandler(**settings)


class ZoomHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        
        # Zoom effect label, entry and invert checkbox
        label = _("Zoom effect")
        effect_label = Gtk.Label(label)
        effect_entry, effect_adjust = widgets.SpinAdjustment(
            2, 1, 4, .05, .25, align=True, digits=2
        )
        label = _("Inverse effect")
        effect_inverse = Gtk.CheckButton(label)
        
        # Pack effect widgets in a line
        effect_line = widgets.Line(
            effect_label, effect_entry, effect_inverse, expand=effect_entry
        )
        
        # Create magnify and minify pivot widgets in a notebook
        pivot_book = Gtk.Notebook()
        pivot_labels = (
            (handler.magnify_anchor, _("Zoom in anchor")),
            (handler.minify_anchor, _("Zoom out anchor")),
        )
        for a_pivot, a_label in pivot_labels:
            # Create anchor widgets
            a_box_widgets = self.create_pivot_widgets(a_pivot, anchor=True)
            a_box = widgets.Stack(*a_box_widgets)
            
            # Add widgets to notebook
            a_box_pad = widgets.PadNotebookContent(a_box)
            a_tab_label = Gtk.Label(a_label)        
            pivot_book.append_page(a_box_pad, a_tab_label)
        
        # Horizontal scrolling check
        label = _("Activate with horizontal scrolling")        
        horizontal_check = Gtk.CheckButton(label)
        
        # Pack everything
        widgets.InitStack(self, effect_line, pivot_book, horizontal_check)
        self.show_all()
        
        # Bind properties
        utility.Bind(handler,
            ("effect", effect_adjust, "value"),
            ("inverse", effect_inverse, "active"),
            ("horizontal", horizontal_check, "active"),
            synchronize=True, bidirectional=True
        )


class ZoomHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "zoom")
        self.create_default = ZoomHandler
        self.create_settings_widget=ZoomHandlerSettingsWidget
    
    
    @GObject.Property
    def label(self):
        return _("Scroll to Zoom")
    
    
    @staticmethod
    def get_settings(handler):
        return {
            "effect": handler.effect,
            "horizontal": handler.horizontal,
            "inverse": handler.inverse,
            "minify_anchor": handler.minify_anchor.get_settings(),
            "magnify_anchor": handler.magnify_anchor.get_settings(),
        }
    
    
    @staticmethod
    def load_settings(settings):
        clone = dict(settings)
        
        minify_settings = clone.pop("minify_anchor")
        minify_anchor = MouseHandlerPivot(settings=minify_settings)
        magnify_settings = clone.pop("magnify_anchor")
        magnify_anchor = MouseHandlerPivot(settings=magnify_settings)
        
        return ZoomHandler(
            minify_anchor=minify_anchor,
            magnify_anchor=magnify_anchor,
            **clone
        )


class GearHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        
        # Create effect line
        label = _("Spin effect")
        effect_label = Gtk.Label(label)
        effect_entry, effect_adjust = widgets.SpinAdjustment(
            30, -180, 180, 10, 60, align=True, wrap=True
        )
        effect_line = widgets.Line(
            effect_label, effect_entry
        )
        
        # Create pivot point widgets
        pivot_widgets = self.create_pivot_widgets(handler.pivot)
        
        # Create horizontal scrolling checkbox
        label = _("Activate with horizontal scrolling")        
        horizontal_check = Gtk.CheckButton(label)
        
        # Pack everything
        widgets.InitStack(self,
            *([effect_line] + pivot_widgets + [horizontal_check])
        )
        self.show_all()
        
        # Bind properties
        utility.Bind(handler,
            ("effect", effect_adjust, "value"),
            ("horizontal", horizontal_check, "active"),
            bidirectional=True, synchronize=True
        )


class GearHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "gear")
        self.create_default = GearHandler
        self.create_settings_widget = GearHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Scroll to Spin")
    
    
    @staticmethod
    def get_settings(handler):
        return {
            "effect": handler.effect,
            "horizontal": handler.horizontal,
            "pivot": handler.pivot.get_settings()
        }
    
    
    @staticmethod
    def load_settings(settings):
        clone = dict(settings)
        pivot = MouseHandlerPivot(settings=clone.pop("pivot"))
        return GearHandler(pivot=pivot, **clone)


class BuiltInMouseMechanismBrands(extending.ComponentPackage):
    def add_on(self, app):
        components = app.components
        brands = [
            HoverAndDragHandlerFactory(drag=True), # drag
            HoverAndDragHandlerFactory(drag=False), # hover
            ScrollHandlerFactory(),
            SpinHandlerFactory(),
            StretchHandlerFactory(),
            ZoomHandlerFactory(),
            GearHandlerFactory(),
        ]
        for a_brand in brands:
            components.add("mouse-mechanism-brand", a_brand)

extending.LoadedComponentPackages["mice"] = BuiltInMouseMechanismBrands()
