""" loading.py defines classes and interfaces for loading data.
    For actual image loading, check the loaders.py component
    
    This is part of the file opening process which begins with opening.py. """

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

from gi.repository import Gio, GObject
import weakref

class DataError(Exception):
    ''' For exceptions due to the current state of the data loaded '''
    pass


class Status:
    ''' Statuses for loadable objects '''
    Bad = -1 # Something went wrong
    Good = 0 # Everything is amazing and nobody is happy
    Caching = 1 # Something is going into the disk
    Loading = 2 # Something is going into the memory


class Location:
    ''' Locations for loadable data to be. '''
    Nowhere = 0 # The data source is gone, 5ever
    Distant = 1 # The data is in a far away place, should be cached
    Disk = 2 # The data is on disk, easy to load
    Memory = 4 # The data is on memory, already loaded


class Loadable(GObject.Object):
    __gsignals__ = {
        "finished-loading": (GObject.SIGNAL_RUN_FIRST, None, [object])
    }
    
    def __init__(self):
        GObject.Object.__init__(self)
        self.location = Location.Nowhere
        self.status = Status.Bad
        
    def load(self):
        raise NotImplementedError
        
    def unload(self):
        raise NotImplementedError
        
    uses = GObject.property(type=int, default=0)
    lists = GObject.property(type=int, default=0)
    
    @property
    def on_memory(self):
        return self.location & Location.Memory == Location.Memory
    
    @property
    def on_disk(self):
        return self.location & Location.Disk == Location.Disk
            
    @property
    def is_loading(self):
        return self.status == Status.Loading
        
    @property
    def is_bad(self):
        return self.status == Status.Bad


class Memory(GObject.GObject):
    ''' A very basic memory management thing '''
    
    __gsignals__ = {
        "thing-enlisted": (GObject.SIGNAL_RUN_FIRST, None, (Loadable,)),
        "thing-requested": (GObject.SIGNAL_RUN_FIRST, None, (Loadable,)),
        "thing-unused": (GObject.SIGNAL_RUN_FIRST, None, (Loadable,)),
        "thing-unlisted": (GObject.SIGNAL_RUN_FIRST, None, (Loadable,)),
    }
    
    def __init__(self):
        GObject.GObject.__init__(self)
        
        self.observed_stuff = weakref.WeakSet()
        
        self.requested_stuff = set()
        self.unused_stuff = set()
        self.enlisted_stuff = set()
        self.unlisted_stuff = set()
    
    
    def observe(self, *stuff):
        """ Starts generating signals for certain resources """
        self.observe_stuff(stuff)
    
    
    def observe_stuff(self, stuff):
        for a_thing in stuff:
            assert a_thing not in self.observed_stuff
            self.observed_stuff.add(a_thing)
            
            a_thing.connect("notify::uses", self._uses_changed)
            a_thing.connect("notify::lists", self._lists_changed)
    
    
    def _uses_changed(self, thing, *data):
        if thing.uses == 1:
            if thing in self.unused_stuff:
                self.unused_stuff.remove(thing)
            else:
                self.requested_stuff.add(thing)
                self.emit("thing-requested", thing)
                
        elif thing.uses == 0:
            if thing in self.requested_stuff:
                self.requested_stuff.remove(thing)
            else:
                self.unused_stuff.add(thing)
                self.emit("thing-unused", thing)
    
    
    def _lists_changed(self, thing, *data):
        if thing.lists == 1:
            if thing in self.unlisted_stuff:
                self.unlisted_stuff.remove(thing)
            else:
                self.enlisted_stuff.add(thing)
                self.emit("thing-enlisted", thing)
        
        elif thing.lists == 0:
            if thing in self.enlisted_stuff:
                self.enlisted_stuff.remove(thing)
            else:
                self.unlisted_stuff.add(thing)
                self.emit("thing-unlisted", thing)

# TODO: Make this thing better
class ImageMeta():
    ''' Contains some assorted metadata of an image
        This should be used in sorting functions '''
        
    def __init__(self):
        self.data_size = 0 # The size of the image on disk, in bytes
        self.width = 0 # The width of the image in pixels
        self.height = 0 # The height of the image in pixels
        self.modification_date = None # Modification date
    
    def get_area(self):
        return self.width * self.height


class ImageSource(Loadable):
    """ Represents an image  """
    
    __gsignals__ = {
        # "new-frame" and "lost-frame" are emitted when an ImageFrame
        # starts using and then stops using a source.
        "new-frame": (GObject.SIGNAL_RUN_FIRST, None, [object]),
        "lost-frame": (GObject.SIGNAL_RUN_LAST, None, [object]),
    }
    
    def __init__(self, file_source=None):
        Loadable.__init__(self)
        
        self.error = None
        self.pixbuf = None
        self.animation = None
        self.metadata = None
        self.file_source = file_source
        if(file_source):
            self.name = self.file_source.get_name()
            self.fullname = self.file_source.get_fullname()
        else:
            self.name = self.fullname = ""
    
    
    def __str__(self):
        return self.fullname
    
    
    def get_metadata(self):
        if not self.metadata:
            self.load_metadata()
            
        return self.metadata
    
    
    def create_frame(self):
        """ Returns a new ImageFrame for rendering this ImageSource"""
        raise NotImplementedError
    
    
    def matches_uri(self, uri):
        """
        Returns whether this image somehow matches an uri.
        A check isn't necessary and the uri isn't necessarily valid.
        By default this returns false.
        
        """
        return False
    
    
    def copy_to_clipboard(self, clipboard):
        """ Copies itself into the clipboard """
        raise NotImplementedError


class GFileImageSource(ImageSource):
    def __init__(self, file_source):
        ImageSource.__init__(self, file_source)
        self.gfile = gfile = file_source.gfile
        
        self.location = Location.Disk if gfile.is_native() else Location.Distant
    
    
    def matches_uri(self, uri):
        return self.gfile.get_uri() == uri
    
    
    def copy_to_clipboard(self, clipboard):
        """ Copies itself into the clipboard """
        
        raise NotImplementedError
