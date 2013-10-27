""" widgets.py contains custom widgets and utility methods for
    creating Gtk widgets """

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

from gi.repository import Gdk, GObject, Gtk
from gi.repository.Gdk import EventMask
import math

# Spacing values that should be used by widgets
HORIZONTAL_SPACING = 16
VERTICAL_SPACING = 8

# Padding values, top/right/bottom/left
DIALOG_PADDING = (15,) * 4
NOTEBOOK_PADDING = (8, 15, 12, 15)

#-- custom widgets down this line --#
class PointScale(Gtk.DrawingArea):
    """ A widget like a Gtk.HScale and Gtk.VScale together. """
    def __init__(self, hrange=None, vrange=None, square=False, **kwargs):
        self.dragging = False
        self.__hrange = self.__vrange = None
        self.hrange_signal = self.vrange_signal = None
        
        kwargs.setdefault("square", square)
        kwargs.setdefault("hrange", hrange)
        kwargs.setdefault("vrange", vrange)
        Gtk.DrawingArea.__init__(self, **kwargs)
        
        self.set_size_request(50, 50)
        if self.square:
            self.padding = 0
            self.mark_width = 32
            self.mark_height = 32
            
        else:
            self.padding = 4
            self.mark_width = 8
            self.mark_height = 8
            
        self.add_events(
            EventMask.BUTTON_PRESS_MASK |
            EventMask.BUTTON_RELEASE_MASK |
            EventMask.POINTER_MOTION_MASK |
            EventMask.POINTER_MOTION_HINT_MASK
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
            x = l + (vx - lx) / (ux - lx) * (r - l - 1)
        else:
            x = l + (r - l - 1) / 2
            
        vrange = self.get_vrange()
        if vrange:
            ly, uy = vrange.get_lower(), vrange.get_upper()
            vy = vrange.get_value()
            y = t + (vy - ly) / (uy - ly) * (b - t - 1)
        else:
            y = t + (b - t - 1) / 2
        
        style = self.get_style_context()
        
        style.add_class(Gtk.STYLE_CLASS_ENTRY)
        Gtk.render_background(style, cr, 0, 0, w, h)
        cr.save()
        border = style.get_border(style.get_state())
        radius = style.get_property(
            Gtk.STYLE_PROPERTY_BORDER_RADIUS, Gtk.StateFlags.NORMAL
        )
        color = style.get_color(style.get_state())
        cr.arc(
            border.left + radius, border.top + radius,
            radius, math.pi, math.pi * 1.5
        )
        cr.arc(
            w - border.right - radius - 1, border.top + radius,
            radius, math.pi * 1.5, math.pi * 2
        )
        cr.arc(
            w - border.right - radius - 1, h -border.bottom - radius - 1,
            radius, 0, math.pi / 2)
        cr.arc(
            border.left + radius, h - border.bottom - radius - 1,
            radius, math.pi / 2, math.pi
        )
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
    
    
    def _adjustment_changed_cb(self, data):
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
                "value-changed", self._adjustment_changed_cb
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
                "value-changed", self._adjustment_changed_cb
            )
        self.queue_draw()
    
    hrange = GObject.property(get_hrange, set_hrange, type=Gtk.Adjustment)
    vrange = GObject.property(get_vrange, set_vrange, type=Gtk.Adjustment)
    square = GObject.Property(type=bool, default=False)


#-- widget creation macros down this line --#
def LoneLabel(text):
    """ Creates a Gtk.Label appropriate for text that isn't beside a widget """
    result = Gtk.Label(text)
    result.set_line_wrap(True)
    result.set_alignment(0, .5)
    return result


def Line(*widgets, expand=None):
    """ Creates a Gtk.Box for horizontally laid widgets,
        maybe expanding one of them """
    result = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL, spacing=HORIZONTAL_SPACING
    )
    
    for a_widget in widgets:
        if a_widget is expand:
            a_widget.set_hexpand(True)
            result.pack_start(a_widget, True, True, 0)
            
        else:
            result.pack_start(a_widget, False, True, 0)
    
    return result


def Stack(*widgets, expand=None, stack=None):
    """ Creates a Gtk.Box for vertically laid widgets,
        maybe expanding one of them """
    
    if stack:
        result = stack
        
    else:
        result = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=VERTICAL_SPACING
        )
    
    for a_widget in widgets:
        if a_widget is expand:
            a_widget.set_vexpand(True)
            result.pack_start(a_widget, True, True, 0)
            
        else:
            result.pack_start(a_widget, False, True, 0)
    
    return result


def InitStack(stack, *widgets, expand=None):
    """ Inits a Gtk.Box for vertically laid widgets """
    Gtk.Box.__init__(stack,
        orientation=Gtk.Orientation.VERTICAL, spacing=VERTICAL_SPACING
    )
    
    Stack(stack=stack, *widgets, expand=expand)


def Grid(*rows, align_first=False, expand_first=False, expand_last=False,
               grid=None, start_row=0):
    """ Creates a Gtk.Grid with standard spacing and rows of widgets"""
    if not grid:
        grid = Gtk.Grid()
        grid.set_row_spacing(VERTICAL_SPACING)
        grid.set_column_spacing(HORIZONTAL_SPACING)
    
    for y, a_row in enumerate(rows):
        real_y = start_row + y
        grid.insert_row(real_y)
        for x, a_cell in enumerate(a_row):
            if x == 0:
                if align_first:
                    a_cell.set_alignment(0, .5)
                    
                if expand_first:
                    a_cell.set_hexpand(True)
                    
            if expand_last and x == len(a_row) - 1:
                a_cell.set_hexpand(True)
            
            grid.attach(a_cell, x, real_y, 1, 1)
            
    return grid


def PadContainer(container=None, top=None, right=None, bottom=None, left=None):
    """ Creates a Gtk.Alignment for padding a container """
    if top is None:
        top = VERTICAL_SPACING
        right = HORIZONTAL_SPACING if right is None else right
    
    else:
        right = top if right is None else right
    
    bottom = top if bottom is None else bottom
    left = right if left is None else left
    
    alignment = Gtk.Alignment()
    alignment.set_padding(top, bottom, left, right)
    
    if container:
        alignment.add(container)
    
    return alignment


def PadDialogContent(content=None):
    """ Creates a Gtk.Alignment for the top widget of a Gtk.Dialog """
    return PadContainer(content, *DIALOG_PADDING)


def PadNotebookContent(content=None):
    """ Creates a Gtk.Alignment for the top widget of a Gtk.Dialog """
    return PadContainer(content, *NOTEBOOK_PADDING)


def ButtonBox(*buttons, secondary=None, alternative=False):
    """ Creates a button box with buttons """
    
    if alternative:
        layout = Gtk.ButtonBoxStyle.START
    else:
        layout = Gtk.ButtonBoxStyle.END
    
    result = Gtk.ButtonBox(spacing=8, orientation=Gtk.Orientation.HORIZONTAL)
    result.set_layout(layout)
    
    for a_button in buttons:
        result.add(a_button)
        
    if secondary:
        for a_button in secondary:
            result.add(a_button)
            result.set_child_secondary(a_button, True)
            
    return result
    

AbsolutePercentScaleFormat = lambda w, v: "{:.0%}".format(abs(v))
AbsoluteScaleFormat = lambda w, v: "{}".format(abs(v))
PercentScaleFormat = lambda w, v: "{:.0%}".format(v)

def ScaleAdjustment(value=0, lower=0, upper=0, step_incr=0, page_incr=0,
                    adjustment=None, marks=None,
                    vertical=False, origin=True,
                    percent=False, absolute=False):
    """ Creates a scale and maybe an adjustment """
    # Create adjustment
    got_adjustment = adjustment is not None
    if not got_adjustment:
        adjustment = Gtk.Adjustment(
            value, lower, upper, step_incr, page_incr, 0
        )
    
    # Set orientation
    if vertical:
        orientation = Gtk.Orientation.VERTICAL
        mark_pos = Gtk.PositionType.RIGHT
    else:
        orientation = Gtk.Orientation.HORIZONTAL
        mark_pos = Gtk.PositionType.BOTTOM
    
    # Create scale
    scale = Gtk.Scale(adjustment=adjustment, orientation=orientation)
    scale.set_has_origin(origin)
    
    # Add marks
    if marks:
        for value, label in marks:
            scale.add_mark(value, mark_pos, label)
    
    # Setup formatting
    if percent:
        if absolute:
            scale.connect("format-value", AbsolutePercentScaleFormat)
        else:
            scale.connect("format-value", PercentScaleFormat)
            
    elif absolute:
        scale.connect("format-value", AbsoluteScaleFormat)
    
    if got_adjustment:
        return scale
    else:
        return scale, adjustment


def SpinAdjustment(value=0, lower=0, upper=0, step_incr=0, page_incr=0,
                   adjustment=None, align=False, **kwargs):
    """ Creates a spin button and maybe an adjustment """
    # Create adjustment
    got_adjustment = adjustment is not None
    if not got_adjustment:
        adjustment = Gtk.Adjustment(
            value, lower, upper, step_incr, page_incr, 0
        )
        
    # Create scale
    scale = Gtk.SpinButton(adjustment=adjustment, **kwargs)
    if align:
        scale.set_alignment(1)
    
    if got_adjustment:
        return scale
    else:
        return scale, adjustment
        


def PointScaleGrid(point_scale, xlabel, ylabel, corner=None, align=False):
    xlabel = Gtk.Label(xlabel)
    xspin = SpinAdjustment(adjustment=point_scale.hrange, digits=2, align=True)
    ylabel = Gtk.Label(ylabel)
    yspin = SpinAdjustment(adjustment=point_scale.vrange, digits=2, align=True)
    
    spin_grid = Grid(
        (xlabel, xspin), (ylabel, yspin),
        align_first=True, expand_first=True
    )
    
    if corner:
        if align:
            corner.set_alignment(0, .5)
        
        spin_stack = Stack(corner, spin_grid)
        
    else:
        spin_stack = Stack(spin_grid)
    
    return Grid((spin_stack, point_scale)), xspin, yspin
