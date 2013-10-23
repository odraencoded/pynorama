""" utility.py contains utility classes and methods that are used by multiple
    modules in the image viewer and don't depend on any of them. """

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

from gi.repository import Gdk, GLib, GObject
from collections import namedtuple
import cairo
import math

class IdlyMethod:
    """ Manages a simple idle callback signal in GLib """
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        self.priority = GLib.PRIORITY_DEFAULT_IDLE
        self.args = args
        self.kwargs = kwargs
        self._signal_id = None
        self.is_queued = False
    
    
    def __call__(self):
        self.cancel_queue()
        self.callback(*self.args, **self.kwargs)
    
    
    execute = __call__
    
    
    def queue(self):
        """ Queues the IdlyMethod to be called from the Gtk main loop later """
        if not self._signal_id:
            self._signal_id = GLib.idle_add(
                 self._idly_execute_queue, priority=self.priority)
        
        self._queued = True
    
    
    def cancel_queue(self):
        """ Cancels the idle call """
        if self._signal_id:
            GLib.source_remove(self._signal_id)
            self._signal_id = None
            self.is_queued = False
    
    
    def execute_queue(self):
        """ Executes the IdlyMethod if it has been queued.
            Nothing happens otherwise. """
        if self.is_queued:
            self()
    
    
    def _idly_execute_queue(self):
        self.is_queued = False
        self()
        
        # If the .queue method was NOT called in self(), we remove the signal
        # ID and return False(that is we cancel this idle callback)
        if not self.is_queued:
            self._signal_id = None
        
        return self.is_queued


#~ 2D aritmetic utilities ~#
class Point(namedtuple("Point", ("x", "y"))):
    def __add__(a, b):
        return Point(a[0] + b[0], a[1] + b[1])
    
    
    def __sub__(a, b):
        return Point(a[0] - b[0], a[1] - b[1])
    
    
    def __mul__(a, b):
        return Point(a[0] * b[0], a[1] * b[1])
    
    
    def __div__(a, b):
        return Point(a[0] / b[0], a[1] / b[1])
    
    
    def __floordiv__(a, b):
        return Point(a[0] // b[0], a[1] // b[1])
    
    
    def __neg__(self):
        return Point(-self[0], -self[1])
    
    def __pos__(self):
        return Point(+self[0], +self[1])
    
    def __abs__(self):
        return Point(abs(self[0]), abs(self[1]))
    
    def __round__(self):
        return Point(round(self[0]), round(self[1]))
    
    sum = __add__
    difference = __sub__
    product = __mul__
    quotient = __div__
    
    
    def scale(a, b):
        return Point(a[0] * b, a[1] * b)
    
    
    def flip(self, h, v):
        return Point(self[0] * (-1 if h else 1), self[1] * (-1 if v else 1))
    
    def swap(self):
        return Point(self[0], self[1])
    
    def spin(self, r):
        x, y  = self
        cos, sin = math.cos, math.sin
        return Point(
            x * cos(r) - y * sin(r),
            x * sin(r) + y * cos(r)
        )
    
    def is_tall(point):
        return point[0] < point[1]
    
    
    def is_wide(point):
        return point[0] > point[1]
    
    
    def get_length(self):
        return math.sqrt(self[0] ** 2 + self[1] ** 2)
    
    def get_square_length(self):
        return self[0] ** 2 + self[1] ** 2


class SignalHandlerConnector:
    def __init__(self, source, source_property, **kwargs):
        self.source = source
        self.source_property = source_property
        self.signal_handlers = kwargs
        
        self._notify_signal_id = source.connect(
            "notify::" + source_property, self._changed_target_cb
        )
        
        self.target = source.get_property(source_property)
        
        self._target_signal_ids = None
        self.reconnect()
    
    
    def disconnect(self):
        if self.target and self._target_signal_ids:
            for a_signal_id in self._target_signal_ids:
                self.target.disconnect(a_signal_id)
            self._target_signal_ids = None
        
    
    def reconnect(self):
        if self.target and not self._target_signal_ids:
            self._target_signal_ids = [
                self.target.connect(a_signal, a_handler)
                for a_signal, a_handler in self.signal_handlers.items()
            ]
        
        
    def destroy(self):
        self.disconnect()
        self.source.disconnect(self._notify_signal_id)
        del self.source, self.target, self.signal_handlers
    
    
    def _changed_target_cb(self, *whatever):
        new_target = self.source.get_property(self.source_property)
        if self.target != new_target:
            self.disconnect()
            self.target = new_target
            self.reconnect()


Point.Zero = Point(0, 0)
Point.Center = Point(.5, .5)
Point.One = Point(1, 1)

class Rectangle(namedtuple("Rectangle", ("left", "top", "width", "height"))):
    @property
    def right(self):
        return self.left + self.width
    
    
    @property
    def bottom(self):
        return self.top + self.height
    
    
    @property
    def area(self):
        return self.width * self.height
    
    
    def corners(self):
        """ Returns a tuple of this rectangle four corners as points """
        left, top = self.left, self.top,
        right, bottom = left + self.width, top + self.height
        return (
            Point(left, top), Point(right, top),
            Point(left, bottom), Point(right, bottom)
        )
    
    
    def overlaps_with(self, other):
        """ Returns true if rectangle overlaps with other rectangle """
        return not (
            self.left >= other.left + other.width \
            or self.top >= other.top + other.height \
            or self.left + self.width < other.left \
            or self.top + self.height < other.top
        )
    
    
    def __and__(self, other):
        left = max(self.left, other.left)
        top = max(self.top, other.top)
        right = min(self.left + self.width, other.left + other.width)
        bottom = min(self.top + self.height, other.top + other.height)
        
        width = max(right - left, 0)
        height = max(bottom - top, 0)
        
        return Rectangle(left, top, width, height)
    
    
    def unbox_point(self, relative_point):
        scaled_point = relative_point * (self.width, self.height)
        return scaled_point + (self.left, self.top)
    
    
    def shift(self, displacement):
        l, t = Point(self.left, self.top) + displacement
        return Rectangle(l, t, self.width, self.height)
    
    
    def resize(self, width, height):
        return Rectangle(self.left, self.top, width, height)
    
    
    def spin(self, angle):
        """ Returns the smallest rectangle that can contain this rectangle
        rotated by a certain value in radians """
        if angle:
            new_corners = [a_corner.spin(angle) for a_corner in self.corners()]
            xs, ys = zip(*new_corners)
            
            left, right = min(xs), max(xs)
            top, bottom = min(ys), max(ys)
            
            return Rectangle(left, top, right - left, bottom - top)
            
        else:
            return self
    
    
    def flip(self, horizontal, vertical):
        """ Basic conditions """
        left, top, width, height = self
        if horizontal:
            left = -(left + width)
    
        if vertical:
            top = -(top + height)
                
        return Rectangle(left, top, width, height)
    
    
    def scale(self, scale):
        """ Basic mathematics """
        return Rectangle(*(e * scale for e in self))
    
    
    @staticmethod
    def Union(rectangles):
        """ Rectangles! UNITE!!! """
        if rectangles:
            top = min(r.top for r in rectangles)
            left = min(r.left for r in rectangles)
            bottom = max(r.top + r.height for r in rectangles)
            right = max(r.left + r.width for r in rectangles)
            
            return Rectangle(left, top, right - left, bottom - top)
        else:
            return Rectangle.Zero
    
    
    @staticmethod
    def FromPoints(*points):
        """ Returns the smallest rectangle that contains all points """
        xs, ys = zip(*points)
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        
        return Rectangle(left, top, right - left, bottom - top)

Rectangle.Zero = Rectangle(0, 0, 0, 0)

#~ GObject utilities ~#

def SetProperties(*objects, **kwargs):
    """ Sets properties of multiple GObjects to the same value
    
    Positional parameters should be the objects whose properties should be set.
    The key-value parameters should be a map of property names their values.
    
    """
    for an_object in objects:
        an_object.set_properties(**kwargs)


def SetPropertiesFromDict(obj, dct, *params, **kwargs):
    """ Sets a GObject properties from keys in a dictionary """
    names = dict((v, v) for v in params)
    names.update((v, k) for k, v in kwargs.items()) # swap prop=key to key=prop
    names_to_set = names.keys() & dct.keys()
    properties = dict((names[k], dct[k]) for k in names_to_set)
    obj.set_properties(**properties)


def SetDictFromProperties(obj, dct, *params, **kwargs):
    """ Sets a dictionary values from a GObject properties """
    names = dict((v, v) for v in params)
    names.update(kwargs) # swap prop=key to key=prop
    prop_values = obj.get_properties(*names.keys())
    dct.update(zip(names.values(), prop_values))


def GetPropertiesDict(obj, *properties):
    """ Returns a dictionary with the properties """
    return dict(zip(properties, obj.get_properties(*properties)))


def Bind(source, *properties, bidirectional=False, synchronize=False):
    """ Bind GObject properties """
    
    flags = 0
    if bidirectional:
        flags |= GObject.BindingFlags.BIDIRECTIONAL
    if synchronize:
        flags |= GObject.BindingFlags.SYNC_CREATE
    
    bind_property = source.bind_property
    return [
        bind_property(src_property, dest, dest_property, flags)
        for src_property, dest, dest_property in properties
    ]


def BindSame(source_property, dest_property,
             *objects, bidirectional=False, synchronize=True):
    """ Bind a same source property to a dest property """
    
    flags = 0
    if bidirectional:
        flags |= GObject.BindingFlags.BIDIRECTIONAL
    if synchronize:
        flags |= GObject.BindingFlags.SYNC_CREATE
    
    return [
        a_src.bind_property(source_property, a_dest, dest_property, flags)
        for a_src, a_dest in objects
    ]


def PointProperty(property_x, property_y):
    getter = lambda obj: Point(*obj.get_properties(property_x, property_y))
    setter = lambda obj, value: obj.set_properties(
        **{property_x: value[0], property_y: value[1]}
    )
    return GObject.Property(getter, setter, type=object)


#-- GdkPixbuf to Cairo surface conversion down this line --#
def SurfaceFromPixbuf(pixbuf):
    """Returns a cairo surface from a Gdk.Pixbuf"""
    if pixbuf.get_has_alpha():
        surface_format = cairo.FORMAT_ARGB32
    else:
        surface_format = cairo.FORMAT_RGB24
        
    surface = cairo.ImageSurface(
        surface_format, pixbuf.get_width(), pixbuf.get_height()
    )
    cr = cairo.Context(surface)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()
    
    return surface


def PixbufFromSurface(surface):
    """Returns a Gdk.Pixbuf from a cairo surface"""
    return Gdk.pixbuf_get_from_surface(
        surface, 0, 0, surface.get_width(), surface.get_height()
    )
