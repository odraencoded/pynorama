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
import cairo

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
