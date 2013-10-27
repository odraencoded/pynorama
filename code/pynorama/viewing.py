""" viewing.py contains widgets for drawing, displaying images and etc. """

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

from math import radians
from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Gtk
import cairo
from .utility import Point, Rectangle, SurfaceFromPixbuf, IdlyMethod

class ZoomMode:
    FillView = 0
    MatchWidth = 1
    MatchHeight = 2
    FitContent = 3

# Quite possibly the least badly designed class in the whole program.
class ImageView(Gtk.DrawingArea, Gtk.Scrollable):
    """
    This widget can display ImageFrames.
    
    It can also zoom in, out, rotate, adjust and etc.
    Pretty much the basis of the entire app
    
    """
    
    __gsignals__ = {
        "transform-change": (GObject.SIGNAL_RUN_FIRST, None, []),
        "offset-change": (GObject.SIGNAL_RUN_FIRST, None, []),
        "draw-bg": (GObject.SIGNAL_RUN_FIRST, None, [object, object]),
        "draw-fg": (GObject.SIGNAL_RUN_LAST, None, [object, object])
    }
    
    def __init__(self):
        Gtk.DrawingArea.__init__(self)
        
        # The set of frames being displayed in this widget
        self._frames = set()
        # This is used to store signal ids and then remove signals from frames
        self._frame_signals = dict()
        
        # The outline is a the boundary of _frames before they are rotated
        self.refresh_outline = IdlyMethod(self.refresh_outline)
        self.refresh_outline.priority = GLib.PRIORITY_HIGH
        
        self.outline = Rectangle(0, 0, 1, 1)
        
        # Does this even do anything?
        style = self.get_style_context().add_class(Gtk.STYLE_CLASS_VIEW)
        
        # offset is usually the same as horizontal/vertical adjustments values
        # unless the outline fits inside the widget
        self.offset = Point.Zero
        self._obsolete_offset = False
        
        self._hadjustment = self._vadjustment = None
        self._hadjust_signal = self._vadjust_signal = None
        
        # This is used to check whether the magnification has switched between
        # Zoom in and zoom out
        self._magnification_watch = (0, None)
        
        self.connect("notify::magnification", self._changed_matrix_cb)
        self.connect("notify::rotation", self._changed_matrix_cb)
        self.connect("notify::horizontal-flip", self._changed_matrix_cb)
        self.connect("notify::vertical-flip", self._changed_matrix_cb)
        self.connect("notify::alignment-x", self._changed_matrix_cb)
        self.connect("notify::alignment-y", self._changed_matrix_cb)
        self.connect(
            "notify::minify-filter", self._changed_interpolation_cb
        )
        self.connect(
            "notify::magnify-filter", self._changed_interpolation_cb
        )
        self.connect(
            "notify::round-full-pixel-offset", self._changed_interpolation_cb
        )
        self.connect(
            "notify::round-sub-pixel-offset", self._changed_interpolation_cb
        )
        self.connect("notify::magnification", self._changed_magnification_cb)

    def add_frame(self, *frames):
        """ Adds one or more frames to the ImageView """
        for a_frame in frames:
            self._frames.add(a_frame)
            if a_frame not in self._frame_signals:
                a_frame_signals = [
                    a_frame.connect(
                        "changed",
                        self._frame_contents_changed_cb
                    ),
                    a_frame.connect(
                        "notify::origin",
                        self._frame_may_have_changed_outline_cb
                    ),
                    a_frame.connect(
                        "notify::rectangle",
                        self._frame_may_have_changed_outline_cb
                    ),
                ]
                self._frame_signals[a_frame] = a_frame_signals
            
            a_frame.view = self
            a_frame.emit("placed")
            
        self.refresh_outline.queue()
        self.queue_draw()
    
    
    def remove_frame(self, *frames):
        """ Removes one or more frames from the ImageView """
        for a_frame in frames:
            self._frames.discard(a_frame)
            a_frame_signals = self._frame_signals.pop(a_frame, None)
            if a_frame_signals is not None:
                for one_frame_signal in a_frame_signals:
                    a_frame.disconnect(one_frame_signal)
            
            a_frame.emit("destroy")
            
        self.refresh_outline.queue()
        self.queue_draw()
    
    
    def refresh_outline(self):
        """ Figure out the outline of all frames united """
        rectangles = [
            a_frame.rectangle.shift(a_frame.origin) for a_frame in self._frames
        ]
        
        union = Rectangle.Union(rectangles)
        # Ensures at least 1 width and height
        width, height = max(union.width, 1), max(union.height, 1)
        new_outline = Rectangle(union.left, union.top, width, height)
        
        if self.outline != new_outline:
            self.outline = new_outline
            self._compute_adjustments()
    
    
    @property
    def frames_fit(self):
        """ Whether all frames are within the widget view """
        w, h = self.get_magnified_width(), self.get_magnified_height()
        return self.outline.width < w and self.outline.height < h
    
    
    # --- view manipulation down this line --- #
    def pan(self, direction):
        self.adjust_to(*(self.get_adjustment() + direction))
    
    
    def rotate(self, degrees):
        self.rotation = self.rotation + degrees
    
    
    def magnify(self, scale):
        self.magnification *= scale
    
    
    def flip(self, vertically=False, Horizontally=False):
        if vertically:
            self.vertical_flip = not self.vertical_flip
            
        if horziontally:
            self.horizontal_flip = not self.horizontal_flip
    
    
    def zoom_for_size(self, size, mode):
        """ Gets a zoom for a size based on a zoom mode """
        w, h = self.get_widget_size()
        sw, sh = size
        
        if mode == ZoomMode.MatchWidth:
            # Match view and size width
            size_side = sw
            view_side = w
        
        elif mode == ZoomMode.MatchHeight:
            # Match view and size height
            size_side = sh
            view_side = h
        else:
            wr, hr = w / sw, h / sh
            
            if mode == ZoomMode.FitContent:
                # Fit size inside view
                if wr < hr:
                    size_side = sw
                    view_side = w
                else:
                    size_side = sh
                    view_side = h
                                        
            elif mode == ZoomMode.FillView:
                # Overflow size in view in only one side
                if wr > hr:
                    size_side = sw
                    view_side = w
                else:
                    size_side = sh
                    view_side = h
            
            else:
                size_side = view_size = 1
                
        return view_side / size_side
    
    
    def adjust_to_pin(self, pin):
        """ Adjusts the view so that the same widget point in the pin can be
            converted to the same absolute point in the pin """
        abs_point, scalar_point = pin
        
        magnification, rotation, hflip, vflip = self.get_properties(
            "magnification", "rotation", "horizontal-flip", "vertical-flip"
        )
        magw = self.get_allocated_width() / magnification
        magh = self.get_allocated_height() / magnification
        rad_rotation = radians(rotation)
        inv_zoom = 1 / magnification
        
        transformed_point = abs_point.flip(*self.flipping).spin(rad_rotation)
        x, y = transformed_point - scalar_point * (magw, magh)
        
        self.adjust_to(x, y)
    
    
    def adjust_to_frame(self, frame, rx=.5, ry=.5):
        """ Adjusts the view to a frame using rx and ry as anchoring
            coordinates in the frame rectangle """
        
        hadjust, vadjust, rotation = self.get_properties(
            "hadjustment", "vadjustment", "rotation"
        )
        vw, vh = hadjust.get_page_size(), vadjust.get_page_size()
        relative_point = Point(rx, ry)
        rect = frame.rectangle.shift(frame.origin)
        point = rect.unbox_point(relative_point).spin(radians(rotation))
        
        self.adjust_to(*(point - relative_point * (vw, vh)))


    def align_to_frame(self, frame):
        """ Aligns the view to a frame """
        self.adjust_to_frame(frame, *self.alignment_point)
    
    
    def adjust_to_boundaries(self, rx, ry):
        """
        Adjusts the view to a normalized point on the combined frames outline.
        The adjustment should result in width * rx, height * ry
        
        """
        
        hadjust, vadjust = self.get_properties("hadjustment", "vadjustment")
        
        if hadjust:
            lx, ux, vw = hadjust.get_properties("lower", "upper", "page-size")
            x = (ux - lx - vw) * rx + lx
        else:
            x = 0
        
        if vadjust:
            ly, uy, vh = vadjust.get_properties("lower", "upper", "page-size")
            y = (uy - ly - vh) * ry + ly
        else:
            y = 0
        
        self.adjust_to(x, y)
    
    
    def adjust_to(self, x, y):
        """ Adjusts the view to an absolute x, y """
        # Refresh outline and adjustments
        self.refresh_outline.execute_queue()
        
        hadjust, vadjust = self.get_properties("hadjustment", "vadjustment")
        
        if hadjust:
            lx, ux, vw = hadjust.get_properties("lower", "upper", "page-size")
            x = max(lx, min(ux, x))
            hadjust.handler_block(self._hadjust_signal)
            hadjust.set_value(x)
            hadjust.handler_unblock(self._hadjust_signal)
        
        if vadjust:
            ly, uy, vh = vadjust.get_properties("lower", "upper", "page-size")
            y = max(ly, min(uy, y))
            vadjust.handler_block(self._vadjust_signal)
            vadjust.set_value(y)
            vadjust.handler_unblock(self._vadjust_signal)
            
        self._obsolete_offset = True
        self.queue_draw()
    
    
    # --- getter/setters down this line --- #
    def get_pin(self, widget_point=None):
        """
        Gets a "pin" for readjusting the view to a "fixed" point in the widget
        after other transformations.
        
        """
        
        size = self.get_widget_size()
        if not widget_point:
            # XXX: Should this be Point.Center and not the view alignment?
            scalar_point = Point.Center
            widget_point = scalar_point.product(size)
        else:
            scalar_point = widget_point.quotient(size)
        
        absolute_point = self.get_absolute_point(widget_point)
        
        return absolute_point, scalar_point
    
    
    def get_widget_point(self):
        """
        Utility method, returns the mouse position if the mouse is over
        the widget, otherwise returns the point corresponding to the center
        of the widget
        
        """
        
        x, y = self.get_pointer()
        w, h = self.get_widget_size()
        if 0 <= x < w and 0 <= y < h:
            return Point(x, y)
        else:
            # XXX: Should this really be the center?
            return Point(w / 2, h / 2)
    
    
    def get_absolute_point(self, widget_point):
        """
        Returns an absolute untransformed point in the model from a point
        in the widget.
        
        """
        magnification, rotation, hflip, vflip = self.get_properties(
            "magnification", "rotation", "horizontal-flip", "vertical-flip"
        )
        rad_rotation = radians(rotation)
        inv_zoom = 1 / magnification
        abs_point = self.offset + widget_point.scale(inv_zoom)
        
        return abs_point.spin(rad_rotation * -1).flip(hflip, vflip)
    
    
    def get_view(self):
        """
        Returns a 4-tuple containing the adjustment and dimensions
        of the view as (x, y, width, height)
        
        """
        hadjust, vadjust = self.get_properties("hadjustment", "vadjustment")
        
        if hadjust:
            x, width = hadjust.get_properties("value", "page-size")
        else:
            x, width = 0, 1
        
        if vadjust:
            y, height = vadjust.get_properties("value", "page-size")
        else:
            y, height = 0, 1
        
        return x, y, width, height
    
    
    def get_boundary(self):
        """
        Returns a 4-tuple containing the offset and dimensions
        of the model as (x, y, width, height)
        
        """
        hadjust, vadjust = self.get_properties("hadjustment", "vadjustment")
        
        if hadjust:
            hlower, hupper = hadjust.get_properties("lower", "upper")
        else:
            hlower, hupper = 0, 1
        
        if vadjust:
            vlower, vupper = vadjust.get_properties("lower", "upper")
        else:
            vlower, vupper = 0, 1
        
        return hlower, vlower, hupper - hlower, vupper - vlower
    
    
    def get_frames_outline(self):
        return self.outline
    
    
    def get_widget_size(self):
        return self.get_allocated_width(), self.get_allocated_height()
    
    
    def get_adjustment(self):
        hadjust, vadjust = self.get_properties("hadjustment", "vadjustment")
        return Point(
            hadjust.get_value() if hadjust else 0,
            vadjust.get_value() if vadjust else 0
        )
    
    
    def get_magnified_width(self):
        return self.get_allocated_width() / self.magnification
    
    def get_magnified_height(self):
        return self.get_allocated_height() / self.magnification
    
    
    def get_filter_for_magnification(self, zoom):
        if zoom > 1:
            return self.magnify_filter
        elif zoom < 1:
            return self.minify_filter
        else:
            return None
    
    
    def set_filter_for_magnification(self, zoom, value):
        if zoom > 1:
            self.magnify_filter = value
        elif zoom < 1:
            self.minify_filter = value
    
    
    @property
    def flipping(self):
        return self.get_properties("horizontal-flip", "vertical-flip")
    
    @flipping.setter
    def flipping(self, value):
        h, v = value
        self.set_properties(horizontal_flip=h, vertical_flip=v)
    
    
    @property
    def alignment_point(self):
        return self.get_properties("alignment-x", "alignment-y")
    
    @alignment_point.setter
    def alignment_point(self, value):
        x, y = value
        self.set_properties(alignment_x=x, alignment_y=y)
    
    
    # --- basic properties down this line --- #    
    def get_hadjustment(self):
        return self._hadjustment
    
    def get_vadjustment(self):
        return self._vadjustment
    
    
    def set_hadjustment(self, adjustment):
        if self._hadjustment:
            self._hadjustment.disconnect(self._hadjust_signal)
            self._hadjust_signal = None
            
        self._hadjustment = adjustment
        if adjustment:
            adjustment.set_properties(
                lower=self.outline.left,
                upper=self.outline.right,
                page_size=self.get_magnified_width()
            )
            self._hadjust_signal = adjustment.connect(
                "value-changed", self._changed_adjustment_cb
            )
    
    def set_vadjustment(self, adjustment):
        if self._vadjustment:
            self._vadjustment.disconnect(self._vadjust_signal)
            self._vadjust_signal = None
            
        self._vadjustment = adjustment
        if adjustment:
            adjustment.set_properties(
                lower=self.outline.top,
                upper=self.outline.bottom,
                page_size=self.get_magnified_height()
            )
            self._vadjust_signal = adjustment.connect(
                "value-changed", self._changed_adjustment_cb
            )
    
    
    def get_current_interpolation_filter(self):
        """ Returns the interpolation filter for the view magnification """
        return self.get_filter_for_magnification(self.magnification)
        
    def set_current_interpolation_filter(self, value):
        self.set_filter_for_magnification(self.magnification, value)
    
    
    def is_zoomed(self):
        """ Returns whether magnification does not equal one """
        return self.magnification != 1
    
    
    hadjustment = GObject.property(
        get_hadjustment, set_hadjustment, type=Gtk.Adjustment
    )
    vadjustment = GObject.property(
        get_vadjustment, set_vadjustment, type=Gtk.Adjustment
    )
    hscroll_policy = GObject.property(
        default=Gtk.ScrollablePolicy.NATURAL, type=Gtk.ScrollablePolicy
    )
    vscroll_policy = GObject.property(
        default=Gtk.ScrollablePolicy.NATURAL, type=Gtk.ScrollablePolicy
    )
                                      
    # This is the alignment of the outline in the widget when the outline
    # fits completely inside the widget
    alignment_x = GObject.property(type=float, default=.5)
    alignment_y = GObject.property(type=float, default=.5)
    
    # Basic view transform
    magnification = GObject.property(type=float, default=1)
    rotation = GObject.property(type=float, default=0)
    horizontal_flip = GObject.property(type=bool, default=False)
    vertical_flip = GObject.property(type=bool, default=False)
    
    minify_filter = GObject.property(type=int, default=cairo.FILTER_BILINEAR)
    magnify_filter = GObject.property(type=int, default=cairo.FILTER_NEAREST)
    
    # These two properties are used for rounding the offset for drawing
    # round_full_pixel_offset will round the offset to a multiple
    # of magnification. E.g. it only shifts 8 pixels at a time at 800% zoom.
    # round_sub_pixel_offset is more useful. It aligns one widget pixel to
    # one image pixel so that the interpolation effect doesn't change after
    # panning the images.
    round_full_pixel_offset = GObject.property(type=bool, default=False)
    round_sub_pixel_offset = GObject.property(type=bool, default=True)
    
    zoomed = GObject.property(is_zoomed, type=bool, default=False)
    current_interpolation_filter = GObject.property(
        get_current_interpolation_filter,
        set_current_interpolation_filter,
        type=int
    )
    
    # --- computing stuff down this line --- #
    def _compute_adjustments(self):
        """
        Figure out lower, upper and page size of adjustments.
        Also clamp them. Clamping is important.
        
        """
        
        hadjust, vadjust, hflip, vflip, rotation = self.get_properties(
            "hadjustment", "vadjustment", 
            "horizontal-flip", "vertical-flip", "rotation"
        )
        # Name's Bounds, James Bounds
        bounds = self.outline.flip(hflip, vflip)
        bounds = bounds.spin(radians(rotation))
        
        if hadjust:
            value, page_size = hadjust.get_properties("value", "page-size")
            lower = bounds.left
            upper = bounds.right
            
            # Figure out page size and align value
            visible_span = min(self.get_magnified_width(), bounds.width)
            visible_diff = page_size - visible_span
            value += visible_diff * self.alignment_x
            
            # Clamp value
            max_value = upper - visible_span
            clamped_value = min(max_value, max(lower, value))
            
            hadjust.set_properties(
                value=clamped_value,
                lower=lower,
                upper=upper,
                page_size=visible_span
            )
        
        if vadjust:
            value, page_size = vadjust.get_properties("value", "page-size")
            lower = bounds.top
            upper = bounds.bottom
            
            # Figure out page size and align value
            visible_span = min(self.get_magnified_height(), bounds.height)
            visible_diff = page_size - visible_span
            value += visible_diff * self.alignment_y
            
            # Clamp value
            max_value = upper - visible_span
            clamped_value = min(max_value, max(lower, value))
            
            vadjust.set_properties(
                value=clamped_value,
                lower=lower,
                upper=upper,
                page_size=visible_span
            )
            
        self._obsolete_offset = True
    
    
    def _compute_offset(self):
        """ Figures out the x, y offset based on the adjustments """
        x, y = self.offset
        hadjust, vadjust = self.get_properties("hadjustment", "vadjustment")
        
        if hadjust:
            value, upper, lower = hadjust.get_properties(
                "value", "upper", "lower"
            )
            span = upper - lower
            # Difference between "model" width and the "physical" view width.
            # We can't use page_size because the page_size is capped to
            # upper - lower due to a Gtk bug.
            diff = span - self.get_magnified_width()
            if diff > 0:
                x = value
            else: 
                # If there is more physical width than model width then
                # We align the image frames using this view alignment
                x = lower + diff * self.alignment_x
        
        if vadjust:
            value, upper, lower = vadjust.get_properties(
                "value", "upper", "lower"
            )
            span = upper - lower
            diff = span - self.get_magnified_height()
            if diff > 0:
                y = value
            else:
                y = lower + diff * self.alignment_y
        
        self._obsolete_offset = False
        self.offset = Point(x, y)
        GLib.idle_add(self.emit, "offset-change", priority=GLib.PRIORITY_HIGH)
    
    
    # --- event stuff down this line --- #
    def _frame_contents_changed_cb(self, *whatever):
        self.queue_draw()
    
    
    def _frame_may_have_changed_outline_cb(self, *whatever):
        self.refresh_outline.queue()
        self.queue_draw()
    
    
    def _changed_adjustment_cb(self, *whatever):
        self._obsolete_offset = True
        self.queue_draw()
    
    
    def _changed_matrix_cb(self, *whatever):
        # I saw a black cat walk by. Twice.
        self._compute_adjustments()
        self.queue_draw()
        self.emit("transform-change")
    
    
    def _changed_interpolation_cb(self, *whatever):
        self.queue_draw()
    
    
    def _changed_magnification_cb(self, *whatever):
        """ handler for notify::magnification """
        old_sign, filter_handler_id = self._magnification_watch
        mag = self.magnification
        changed = False
        # Check if the magnification changed from <1, ==1 or >1 to
        # something else
        if mag < 1:
            if old_sign >= 0:
                changed = True
                sign = -1
                new_handler_id = self.connect(
                    "notify::minify-filter",
                    self._notify_interpolation_filter
                )
                
        elif mag > 1:
            if old_sign <= 0:
                changed = True
                sign = 1
                new_handler_id = self.connect(
                    "notify::magnify-filter",
                    self._notify_interpolation_filter
                )
                
        elif old_sign != 0:
            sign = 0
            changed = True
            new_handler_id = None
        
        if changed:
            if filter_handler_id:
                self.disconnect(filter_handler_id)
                
            self._magnification_watch = sign, new_handler_id
            if sign != 0:
                self._notify_interpolation_filter()
            
            if (sign == 0) != (old_sign == 0):
                self.notify("zoomed")
    
    
    def _notify_interpolation_filter(self, *whatever):
        self.notify("current-interpolation-filter")
    
    
    def do_size_allocate(self, allocation):
        Gtk.DrawingArea.do_size_allocate(self, allocation)
        self._compute_adjustments()
    

    class DrawState:
        """ Caches a bunch of properties """
        def __init__(self, view):
            self.view = view
            (
                zoom, rotation,
                self.hflip, self.vflip,
                self.minify_filter, self.magnify_filter,
                self.round_full_pixel_offset, self.round_sub_pixel_offset
            ) = view.get_properties(
                "magnification", "rotation",
                "horizontal-flip", "vertical-flip",
                "minify-filter", "magnify-filter",
                "round-full-pixel-offset", "round-sub-pixel-offset"
            )
            
            self.rotation = rotation
            self.rad_rotation = radians(rotation)
            self.flip = self.hflip, self.vflip
            self.is_flipped = self.hflip or self.vflip
            
            alloc = view.get_allocation()
            self.size = self.width, self.height = alloc.width, alloc.height
            
            self.real_offset = view.offset
            self.set_magnification(zoom)
            
            self.style = view.get_style_context()
        
        
        def get_filter_for_magnification(self, zoom):
            """ Returns the appropriate cairo interpolation filter for a zoom.
            
            Returns None if zoom is 1.
            
            """
            if zoom > 1:
                return self.magnify_filter
            elif zoom < 1:
                return self.minify_filter
            else:
                return None
        
        
        def transform(self, cr):
            """ Applies the stored scaling, translation, rotation and flipping
            values to a cairo context.
            
            """
            cr.scale(self.magnification, self.magnification)
            cr.translate(*self.translation)
            cr.rotate(self.rad_rotation)
            if self.is_flipped:
                cr.scale(
                    -1 if self.hflip else 1,
                    -1 if self.vflip else 1
                )
        
        
        def set_magnification(self, zoom):
            self.magnification = zoom
            offset = self.real_offset
            if(zoom > 1 and self.round_full_pixel_offset):
                # Round pixel offset, removing pixel fractions from it
                offset = round(offset)
                
            if(zoom != 1 and self.round_sub_pixel_offset):
                # Round offset to match pixels shown on display using
                # inverse magnification
                
                invzoom = 1 / zoom
                invzoom_scale = Point(invzoom, invzoom)
                offset = offset // invzoom_scale * invzoom_scale
                
            self.offset = offset
            self.translation = -offset
        
        
        def set_offset(self, offset):
            self.real_offset = offset
            if(self.magnification > 1 and self.round_full_pixel_offset):
                # Round pixel offset, removing pixel fractions from it
                offset = round(offset)
                
            if(self.magnification != 1 and self.round_sub_pixel_offset):
                # Round offset to match pixels shown on display using
                # inverse magnification
                
                invzoom = 1 / self.magnification
                invzoom_scale = Point(invzoom, invzoom)
                offset = offset // invzoom_scale * invzoom_scale
                
            self.offset = offset
            self.translation = -offset
    
    
    def do_draw(self, cr):
        """ Draws everything! """
        if self._obsolete_offset:
            self._compute_offset()
        
        drawstate = ImageView.DrawState(self)
        self.emit("draw-bg", cr, drawstate)
        
        cr.save()
        drawstate.transform(cr)
        self.draw_frames(cr, drawstate)
        cr.restore()
        
        self.emit("draw-fg", cr, drawstate)
    
    
    def do_draw_bg(self, cr, drawstate):
        """ Renders the Gtk theme background """
        style = drawstate.style
        style.save()
        style.add_class(Gtk.STYLE_CLASS_CELL)
        Gtk.render_background(style, cr, 0, 0, *drawstate.size)
        style.restore()
    
    
    def draw_frames(self, cr, drawstate):
        """ Renders this ImageView frames to a cairo context """
        for a_frame in self._frames:
            cr.save()
            try:
                cr.translate(*a_frame.origin)
                a_frame.draw(cr, drawstate)
            
            except Exception:
                raise
                
            cr.restore()
    
    
    def do_draw_fg(self, cr, drawstate):
        """ Renders the Gtk theme frame """
        style = drawstate.style
        style.save()
        style.add_class(Gtk.STYLE_CLASS_CELL)
        Gtk.render_frame(style, cr, 0, 0, *drawstate.size)
        style.restore()


# --- Image frames related code down this line --- #

class BaseFrame(GObject.Object):
    """Abstract class for objects that can be rendered in an ImageView.
    
    Derived objects must implement the .draw method, and set
    a .rectangle attribute delimiting the area which it will
    be drawn into around its origin.
    
    """
    
    __gsignals__ = {
        # "placed" and "destroy" are emitted when a frame is
        # added to  and then removed from an ImageView respectively.
        # Both signals should only be emitted once.
        "placed": (GObject.SIGNAL_RUN_FIRST, None, []),
        "destroy": (GObject.SIGNAL_RUN_LAST, None, []),
        
        # This signal is emitted by a frame when its contents have
        # changed within the .rectangle delimitation
        "changed": (GObject.SIGNAL_NO_HOOKS, None, []),
    }
    
    
    def __init__(self):
        GObject.GObject.__init__(self)
        self.origin = 0, 0
        self.view = None
    
    
    def draw(self, cr, drawstate):
        """Draws the frame contents
        
        Translating to the origin isn't necessary as it's already done
        by the ImageView class
        
        """
        raise NotImplementedError
    
    origin = GObject.property(type=object)
    rectangle = GObject.property(type=object)
    
    @GObject.property
    def placed(self):
        return self.view is not None
    
    
    def set_rectangle_from_size(self, w, h):
        """Utility method for setting a symmetric .rectangle"""
        self.rectangle = Rectangle(-w // 2, -h // 2, w, h)
    
    
    def render_pattern(self, cr, drawstate, pattern):
        cr.set_source(pattern)
        
        # Setting the interpolation filter based on zoom
        zoom = drawstate.magnification
        if zoom != 1:
            interp_filter = drawstate.get_filter_for_magnification(zoom)
            pattern.set_filter(interp_filter)
        
        cr.paint()
    
    
    def render_surface(self, cr, drawstate, surface, offset):
        """Utility method for rendering a cairo surface"""
        cr.set_source_surface(surface, *offset)
        pattern = cr.get_source()
        
        # Setting the interpolation filter based on zoom
        zoom = drawstate.magnification
        if zoom != 1:
            interp_filter = drawstate.get_filter_for_magnification(zoom)
            pattern.set_filter(interp_filter)
        
        cr.paint()
        
        return pattern


class ImageFrame(BaseFrame):
    """Base class for frames containing an ImageSource"""
    
    # TODO: Implement rotation and scale
    def __init__(self, source):
        """Creates a new frame with the indicated image source"""
        BaseFrame.__init__(self)
        
        self.__missing_icon_pattern = None
        
        # .data contains any data set by .source
        self.data = None
        self.source = source
        
        source.emit("new-frame", self)
        source.connect("finished-loading", self.check_source)
        self.check_source()
        
        
    def draw_image_source(self, cr, drawstate):
        """Derived classes should implement this instead of .draw"""
        raise NotImplementedError
    
    
    def draw_missing_image(self, cr, drawstate):
        """Draws a missing image icon into the frame"""
        self.render_pattern(cr, drawstate, self.__missing_icon_pattern)
    
    
    #~ Signal handlers ~#
    def do_destroy(self):
        if self.source:
            self.source.emit("lost-frame", self)
    
    
    def do_placed(self):
        self.check_source()
    
    
    def check_source(self, *whatever):
        """Checks the .source status
        
        If .source is loaded, .rectangle will be set using the
        .source metadata and .draw_image_source will be used
        for rendering. If something is wrong with the .source
        then a missing error image will be used instead.
        
        """
        try:
            source_ok = self.source.on_memory
        except Exception:
            source_ok = False
            
        if source_ok:
            self.draw = self.draw_image_source
            metadata = self.source.metadata
            width, height = metadata.width, metadata.height
            
        else:
            self.draw = self.draw_missing_image
            
            # self.placed == has a .view
            if self.placed:
                # Setup the missing error icon
                if self.__missing_icon_pattern is None:
                    icon_pixbuf = self.view.render_icon(
                        Gtk.STOCK_MISSING_IMAGE, Gtk.IconSize.DIALOG
                    )
                    icon_surface = SurfaceFromPixbuf(icon_pixbuf)
                    icon_pattern = cairo.SurfacePattern(icon_surface)
                    
                    self.__missing_icon_pattern = icon_pattern
                else:
                    icon_pattern = self.__missing_icon_pattern
                    icon_surface = icon_pattern.get_surface()
                    
                width = icon_surface.get_width()
                height = icon_surface.get_height()
                
                icon_pattern.set_matrix(
                    cairo.Matrix(x0=width // 2, y0=height // 2)
                )
            
            else:
                width, height = 0, 0
        
        self.set_rectangle_from_size(width, height)


class SurfaceSourceImageFrame(ImageFrame):
    """ImageFrame for ImageSources exposing a .surface attribute"""
    
    def __init__(self, *args, **kwargs):
        ImageFrame.__init__(self, *args, **kwargs)
        
        self._surface_pattern = None
        self.source.connect("finished-loading", self._finished_loading_cb)
    
    def _finished_loading_cb(self, *whatever):
        self._surface_pattern = None
        
    
    def draw_image_source(self, cr, drawstate):
        """Renders an ImageSource with a .surface into the frame"""
        
        if self._surface_pattern is None:
            rectangle = self.rectangle
            self._surface_pattern = self.render_surface(
                cr, drawstate, self.source.surface,
                (rectangle.left, rectangle.top)
            )
        else:
            self.render_pattern(cr, drawstate, self._surface_pattern)


class AnimatedPixbufSourceFrame(ImageFrame):
    def __init__(self, source):
        ImageFrame.__init__(self, source)
        self._animation_iter = None
        self._current_frame_pattern = None
        self._animate_signal = None
    
    
    def do_placed(self):
        animation = self.source.pixbuf_animation
        
        if animation:
            if animation.is_static_image():
                pixbuf = animation.get_static_image()
                pattern = cairo.SurfacePattern(SurfaceFromPixbuf(pixbuf))
                pattern.set_matrix(cairo.Matrix(
                    x0=pixbuf.get_width() // 2, y0=pixbuf.get_height() // 2
                ))
                
                self._current_frame_pattern = pattern
                
            else:
                self._animation_iter = animation.get_iter(None)
                self._schedule_animation_advance()
        
        ImageFrame.do_placed(self)
    
    
    def do_destroy(self):
        # Remove any pending _advance_animation signal handler
        if self._animate_signal:
            GLib.source_remove(self._animate_signal)
    
    
    def draw_image_source(self, cr, drawstate):
        if self._current_frame_pattern is None:
            frame_pixbuf = self._animation_iter.get_pixbuf()
            frame_surface = SurfaceFromPixbuf(frame_pixbuf)
        
            rectangle = self.rectangle
            self._current_frame_pattern  = self.render_surface(
                cr, drawstate, frame_surface,
                (rectangle.left, rectangle.top)
            )
        else:
            self.render_pattern(cr, drawstate, self._current_frame_pattern)
    
    
    def _schedule_animation_advance(self):
        animation_delay = self._animation_iter.get_delay_time()
        if animation_delay != -1:
            self._animate_signal = GLib.timeout_add(
                animation_delay, self._advance_animation
            )
    
    
    def _advance_animation(self):
        self._animation_iter.advance(None)
        self._current_frame_pattern = None
        self._schedule_animation_advance()
        self.emit("changed")
