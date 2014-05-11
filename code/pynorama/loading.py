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
from . import utility
import weakref

class DataError(Exception):
    ''' For exceptions due to the current state of the data loaded '''
    pass


Status = utility.Enum(
    UNLOADED   = 0b0001,
    LOADED     = 0b0010,
    DESTROYED  = 0b0100,
    LOADING    = 0b1010,
    UNLOADING  = 0b1001,
    DESTROYING = 0b1100
)


class Loadable(GObject.Object):
    __gsignals__ = {
        "finished-loading": (GObject.SIGNAL_RUN_LAST, None, [object]),
        "destroyed": (GObject.SIGNAL_RUN_LAST, None, []),
        "uses-changed": (GObject.SIGNAL_RUN_FIRST, None, [int]),
        "lists-changed":(GObject.SIGNAL_RUN_FIRST, None, [int])
    }
    
    def __init__(self):
        GObject.Object.__init__(self)
        self.status = Status.UNLOADED
        self.reloadable = True
        self.error = None
        
        self.__uses = 0
        self.__lists = 0
        self.__requests = 0
        
        self.__request_signal_handler_ids = []
        self.__data_requested = False
    
    
    def load(self):
        """Loads this resource somehow."""
        raise NotImplementedError
    
    
    def unload(self):
        """Unloads this resource somehow."""
        raise NotImplementedError
    
    
    def destroy(self):
        """Destroys this resource somehow."""
        self.status = Status.DESTROYED
        self.emit("destroyed")
    
    
    def request_data(self):
        """
        Convenience method for memory managed Loadables.
        
        Calling this will increment its use count by one, supposedly
        making the memory manager attempt to load this resource.
        
        Once loaded, it automatically subtracts from its use count the number
        of data requests it received.
        
        Use .cancel_request to undo a request.
        
        """
        
        if not self.is_loaded:
            self.__requests += 1
            self.uses += 1
    
    
    def cancel_request(self):
        """Reverts the effects of .request_data."""
        if not self.is_loaded and self.__requests > 0:
            self.__requests -= 1
            self.uses -= 1
    
    
    def do_finished_loading(self, *whatever):
        if self.__requests:
            requests = self.__requests
            self.__requests = 0
            self.uses -= requests
    
    
    def get_uses(self):
        return self.__uses
    
    
    def set_uses(self, value):
        diff = value - self.__uses
        self.__uses = value
        self.emit("uses-changed", diff)
    
    
    def get_lists(self):
        return self.__lists
    
    
    def set_lists(self, value):
        diff = value - self.__lists
        self.__lists = value
        self.emit("lists-changed", diff)
    
    
    uses = GObject.property(get_uses, set_uses, type=int, default=0)
    lists = GObject.property(get_lists, set_lists, type=int, default=0)
    
    
    @property
    def is_loaded(self):
        return self.status == Status.LOADED
    
    
    @property
    def is_loading(self):
        return self.status == Status.LOADING
    
    
    @property
    def is_bad(self):
        return bool(self.error)


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
            
            a_thing.connect("uses-changed", self._uses_changed_cb)
            a_thing.connect("lists-changed", self._lists_changed_cb)
    
    
    def _uses_changed_cb(self, thing, difference):
        if thing.uses == 1 and difference > 0:
            if thing in self.unused_stuff:
                self.unused_stuff.remove(thing)
            else:
                self.requested_stuff.add(thing)
                self.emit("thing-requested", thing)
                
        elif thing.uses == 0 and difference < 0:
            if thing in self.requested_stuff:
                self.requested_stuff.remove(thing)
            else:
                self.unused_stuff.add(thing)
                self.emit("thing-unused", thing)
    
    
    def _lists_changed_cb(self, thing, difference):
        if thing.lists == 1 and difference > 0:
            if thing in self.unlisted_stuff:
                self.unlisted_stuff.remove(thing)
            else:
                self.enlisted_stuff.add(thing)
                self.emit("thing-enlisted", thing)
        
        elif thing.lists == 0 and difference < 0:
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
        
        self.is_linked = False
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
    
    
    def link_source(self):
        """Associates this image's file source to itself"""
        if self.file_source and not self.is_linked:
            self.is_linked = True
            self.file_source.add_image(self)
    
    
    def unlink_source(self):
        """Reverts .link_source"""
        if self.file_source and self.is_linked:
            self.is_linked = False
            self.file_source.remove_image(self)
    
    
    def destroy(self):
        self.unlink_source()
        Loadable.destroy(self)
    
    
    def do_new_frame(self, frame):
        """Increases use count by one when a frame starts using this image"""
        self.uses += 1
    
    
    def do_lost_frame(self, frame):
        """Decreases use count by one when a frame stops using this image"""
        self.uses -= 1
    
    
    def get_metadata(self):
        if not self.metadata:
            self.load_metadata()
            
        return self.metadata
    
    
    def create_frame(self):
        """ Returns a new ImageFrame for rendering this ImageSource"""
        raise NotImplementedError
    
    
    def copy_to_clipboard(self, clipboard):
        """ Copies itself into the clipboard """
        raise NotImplementedError


class GFileImageSource(ImageSource):
    def __init__(self, file_source):
        ImageSource.__init__(self, file_source)
        self.gfile = gfile = file_source.gfile
    
    
    def copy_to_clipboard(self, clipboard):
        """ Copies itself into the clipboard """
        
        raise NotImplementedError
