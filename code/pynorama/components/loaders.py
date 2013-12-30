""" loaders.py defines the image loaders used by the openers.py components
    
    For the interface description see the loading.py module
    This module doesn't deal with displaying images, see viewing.py for that
    
    The image loaders defined here are:
        PixbufDataImageSource: For already on memory GdkPixbuf objects
        PixbufFileImageSource: For GdkPixbuf supported files not on memory
        PixbufAnimationFileImageSource: Anime adaptation of the above """

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


import time
from gi.repository import GdkPixbuf, Gio, GObject, GLib
from gettext import gettext as _
from pynorama import utility, loading, viewing
from pynorama.loading import Status, Location


class PixbufDataImageSource(loading.ImageSource):
    ''' An ImageSource created from a pixbuf
        This ImageSource can not be loaded or unloaded
        Because it can not find the data source by itself '''
        
    def __init__(self, pixbuf, name="Image Data"):
        loading.ImageSource.__init__(self)
        self.surface = utility.SurfaceFromPixbuf(pixbuf)
        
        self.fullname = self.name = name
        
        self.load_metadata()
        
        self.location = Location.Memory
        self.status = Status.Good
        
        
    def load_metadata(self):
        if self.metadata is None:
            self.metadata = loading.ImageMeta()
            
        self.metadata.width = self.surface.get_width()
        self.metadata.height = self.surface.get_height()
        self.metadata.modification_date = time.time()
        self.metadata.data_size = 0
    
    
    def unload(self):
        self.surface = None
        self.location &= ~Location.Memory
        self.status = Status.Bad
        
        
    def create_frame(self):
        return viewing.SurfaceSourceImageFrame(self)
    
    
    def copy_to_clipboard(self, clipboard):
        pixbuf = utility.PixbufFromSurface(self.surface)
        clipboard.set_image(pixbuf)


class PixbufFileImageSource(loading.GFileImageSource):
    def __init__(self, gfile, **kwargs):
        loading.GFileImageSource.__init__(self, gfile, **kwargs)
        
        self.status = Status.Good
        self.cancellable = None
    
    
    def load(self):
        if self.is_loading:
            raise Exception
            
        self.cancellable = Gio.Cancellable()
        
        stream = self.gfile.read(None)
        
        self.status = Status.Loading
        GdkPixbuf.Pixbuf.new_from_stream_async(
            stream, self.cancellable, self._loaded, None
        )
    
    
    def _loaded(self, me, result, *data):
        self.error = None
        try:
            async_finish = GdkPixbuf.Pixbuf.new_from_stream_finish
            pixbuf = async_finish(result)
            self.surface = utility.SurfaceFromPixbuf(pixbuf)

        except GLib.GError as gerror:
            # If cancellable is None, that means loading was cancelled
            if self.cancellable:
                self.location &= ~Location.Memory
                self.status = Status.Bad
                self.error = gerror
            
        else:
            self.location |= Location.Memory
            self.status = Status.Good
            self.load_metadata()
            
        finally:
            self.cancellable = None
            self.emit("finished-loading", self.error)
    
    
    def unload(self):
        if self.cancellable:
            self.cancellable.cancel()
            self.cancellable = None
        
        self.surface = None
        self.location &= ~Location.Memory
        self.status = Status.Good
    
    
    def load_metadata(self):
        if self.metadata is None:
            self.metadata = loading.ImageMeta()
        
        # These file properties are queried from the file info
        try:
            file_info = self.gfile.query_info(
                "standard::size,time::modified", 0, None
            )
        except Exception:
            self.metadata.modification_date = float(time.time())
            self.metadata.data_size = 0
        else:
            try:
                size_str = file_info.get_attribute_as_string("standard::size")
                self.metadata.data_size = int(size_str)
                
            except Exception:
                self.metadata.data_size = 0
                
            try:
                time_str = file_info.get_attribute_as_string("time::modified")
                self.metadata.modification_date = float(time_str)
                
            except Exception:
                self.metadata.modification_date = float(time.time())
        
        # The width and height of the image are loaded from guess where
        if self.surface:
            self.metadata.width = self.surface.get_width()
            self.metadata.height = self.surface.get_height()
            
        elif self.gfile.is_native():
            try:
                filepath = self.gfile.get_path()
                fmt, width, height = GdkPixbuf.Pixbuf.get_file_info(filepath)
                self.metadata.width = width
                self.metadata.height = height
                
            except Exception:
                self.metadata.width = 0
                self.metadata.height = 0
            
        # TODO: Add support for non-native files
    
    
    def create_frame(self):
        return viewing.SurfaceSourceImageFrame(self)
    
    
    def copy_to_clipboard(self, clipboard):
        pixbuf = utility.PixbufFromSurface(self.surface)
        clipboard.set_image(pixbuf)
    
    
class PixbufAnimationFileImageSource(loading.GFileImageSource):
    def __init__(self, gfile, **kwargs):
        loading.GFileImageSource.__init__(self, gfile, **kwargs)
        
        self.pixbuf_animation = None
        self.status = Status.Good
        self.cancellable = None
    
    
    def load(self):
        if self.is_loading:
            raise Exception
            
        self.cancellable = Gio.Cancellable()
        
        stream = self.gfile.read(None)
        
        self.status = Status.Loading
        GdkPixbuf.PixbufAnimation.new_from_stream_async(
            stream, self.cancellable, self._loaded, None
        )
    
    
    def _loaded(self, me, result, *data):
        self.error = None
        try:
            async_finish = GdkPixbuf.PixbufAnimation.new_from_stream_finish
            self.pixbuf_animation = async_finish(result)
        except GLib.GError as gerror:
            # If cancellable is None, that means loading was cancelled
            if self.cancellable:
                self.location &= ~Location.Memory
                self.status = Status.Bad
                self.error = gerror
        else:
            self.location |= Location.Memory
            self.status = Status.Good
            self.load_metadata()
            
        finally:
            self.cancellable = None
            self.emit("finished-loading", self.error)
    
    
    def unload(self):
        if self.cancellable:
            self.cancellable.cancel()
            self.cancellable = None
        
        self.pixbuf_animation = None
        self.location &= ~Location.Memory
        self.status = Status.Good
    
    
    def load_metadata(self):
        if self.metadata is None:
            self.metadata = loading.ImageMeta()
        
        # These file properties are queried from the file info
        try:
            file_info = self.gfile.query_info(
                "standard::size,time::modified", 0, None
            )
        except Exception:
            self.metadata.modification_date = float(time.time())
            self.metadata.data_size = 0
        else:
            try:
                size_str = file_info.get_attribute_as_string("standard::size")
                self.metadata.data_size = int(size_str)
            except Exception:
                self.metadata.data_size = 0
                
            try:
                time_str = file_info.get_attribute_as_string("time::modified")
                self.metadata.modification_date = float(time_str)
            except Exception:
                self.metadata.modification_date = float(time.time())
        
        # The width and height of the image are loaded from guess where
        if self.animation:
            self.metadata.width = self.pixbuf_animation.get_width()
            self.metadata.height = self.pixbuf_animation.get_height()
            
        elif self.gfile.is_native():
            try:
                filepath = self.gfile.get_path()
                fmt, width, height = GdkPixbuf.Pixbuf.get_file_info(filepath)
                self.metadata.width = width
                self.metadata.height = height
                
            except Exception:
                self.metadata.width = 0
                self.metadata.height = 0
            
        # TODO: Add support for non-native files
    
    
    def create_frame(self):
        return viewing.AnimatedPixbufSourceFrame(self)

    
    def copy_to_clipboard(self, clipboard):
        pixbuf = self.pixbuf_animation.get_iter(None).get_pixbuf()
        clipboard.set_image(pixbuf)
