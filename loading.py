''' loading.py is the loading and loading related module.
    It contains things for loading stuff. '''

''' ...and this file is part of Pynorama.
    
    Pynorama is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    Pynorama is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with Pynorama. If not, see <http://www.gnu.org/licenses/>. '''

import os, re, datetime, time

from gi.repository import Gdk, GdkPixbuf, Gio, GObject, GLib, Gtk
from gettext import gettext as _
import cairo
import sys
Filters = []
Mimes = []
Extensions = set()

# Create "All Files" filter
contradictory_filter = Gtk.FileFilter()
contradictory_filter.set_name(_("All Files"))
contradictory_filter.add_pattern("*")

# Create images filter
images_filter = Gtk.FileFilter()
images_filter.set_name(_("Images"))

# Add the "images" filter before "all files" filter
Filters.append(images_filter)
Filters.append(contradictory_filter)

# Create file filters from formats supported by gdk pixbuf
_formats = GdkPixbuf.Pixbuf.get_formats()
for a_format in _formats:
	format_filter = Gtk.FileFilter()
	filter_name = a_format.get_name() + " ("
	
	# Add mime types
	for a_mimetype in a_format.get_mime_types():
		format_filter.add_mime_type(a_mimetype)
		images_filter.add_mime_type(a_mimetype)
		Mimes.append(a_mimetype)
		
	# Add patterns based on extensions
	first_ext = True
	for an_extension in a_format.get_extensions():
		new_pattern = "*." + an_extension
		format_filter.add_pattern(new_pattern)
		images_filter.add_pattern(new_pattern)
		
		Extensions.add("." + an_extension)
		
		if first_ext:
			filter_name += new_pattern
		else:
			filter_name += "|" + new_pattern
			
		first_ext = False
	
	filter_name += ")"
	format_filter.set_name(filter_name)
	
	Filters.append(format_filter)
	
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
	
class Loadable(GObject.GObject):
	__gsignals__ = {
		"finished-loading": (GObject.SIGNAL_RUN_FIRST, None, [object])
	}
	
	def __init__(self):
		GObject.GObject.__init__(self)
		
		self.location = Location.Nowhere
		self.status = Status.Bad
		self.uses = 0
		self.lists = 0
		
	def load(self):
		raise NotImplemented
		
	def unload(self):
		raise NotImplemented
		
	@property
	def on_memory(self):
		return self.location & Location.Memory == Location.Memory
	
	@property
	def on_disk(self):
		return self.location & Location.Disk == Location.Disk
			
	@property
	def is_loading(self):
		return self.status == Status.Loading
		
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
		
		self.requested_stuff = set()
		self.unused_stuff = set()
		self.enlisted_stuff = set()
		self.unlisted_stuff = set()
		
	def request(self, thing):
		thing.uses += 1
		if thing.uses == 1:
			if thing in self.unused_stuff:
				self.unused_stuff.remove(thing)
			else:
				self.requested_stuff.add(thing)
				self.emit("thing-requested", thing)
		
	def free(self, thing):
		thing.uses -= 1
		if thing.uses == 0:
			if thing in self.requested_stuff:
				self.requested_stuff.remove(thing)
			else:
				self.unused_stuff.add(thing)
				self.emit("thing-unused", thing)
	
	def enlist(self, thing):
		thing.lists += 1
		
		if thing.lists == 1:
			if thing in self.unlisted_stuff:
				self.unlisted_stuff.remove(thing)
			else:
				self.enlisted_stuff.add(thing)
				self.emit("thing-enlisted", thing)
	
	def unlist(self, thing):
		thing.lists -= 1
		if thing.lists == 0:
			if thing in self.enlisted_stuff:
				self.enlisted_stuff.remove(thing)
			else:
				self.unlisted_stuff.add(thing)
				self.emit("thing-unlisted", thing)
		
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
	
class ImageNode(Loadable):
	def __init__(self):
		Loadable.__init__(self)
		
		self.pixbuf = None
		self.animation = None
		self.metadata = None
		
		self.fullname, self.name = "", ""
		self.next = self.previous = None
		
	def __str__(self):
		return self.fullname
	
	def get_metadata(self):
		if not self.metadata:
			self.load_metadata()
			
		return self.metadata
	
	def insert_links(self, previous, next):
		if self.next:
			self.next.previous = self.previous
		if self.previous:
			self.previous.next = self.next
		
		self.next = next
		self.previous = previous
		
		if self.next:
			self.next.previous = self
		if self.previous:
			self.previous.next = self
					
	def remove_links(self):
		if self.next:
			self.next.previous = self.previous
			
		if self.previous:
			self.previous.next = self.next
			
		self.previous = self.next = None
	
	def cut_ties(self):
		if self.next and self.next.previous is self:
			self.next.previous = self.previous
			
		if self.previous and self.previous.next is self:
			self.previous.next = self.next
		
		self.previous = self.next = None
		
class ImageGFileNode(ImageNode):
	def __init__(self, gfile):
		ImageNode.__init__(self)
		self.gfile = gfile
		
		info = gfile.query_info("standard::display-name", 0, None)
		self.name = info.get_attribute_as_string("standard::display-name")
		self.fullname = self.gfile.get_parse_name()
		
		self.location = Location.Disk if gfile.is_native() else Location.Distant
		self.status = Status.Good
		
		self.cancellable = None
		
	def load(self):
		if self.is_loading:
			raise Exception
			
		self.cancellable = Gio.Cancellable()
		
		stream = self.gfile.read(None)
		parsename = self.gfile.get_parse_name()
		
		self.status = Status.Loading
		if parsename.endswith(".gif"):
			load_async = GdkPixbuf.PixbufAnimation.new_from_stream_async
			self.animation = load_async(stream, self.cancellable,
			                            self._loaded, True)
			                            
		else:
			load_async = GdkPixbuf.Pixbuf.new_from_stream_async
			self.pixbuf = load_async(stream, self.cancellable,
			                         self._loaded, False)
	def _loaded(self, me, result, is_gif):
		e = None
		try:
			if is_gif:
				async_finish = GdkPixbuf.PixbufAnimation.new_from_stream_finish
				self.animation = async_finish(result)
				
				if self.animation.is_static_image():
					self.pixbuf = self.animation.get_static_image()
					self.animation = None
			else:
				async_finish = GdkPixbuf.Pixbuf.new_from_stream_finish
				self.pixbuf = async_finish(result)

		except GLib.GError as gerror:
			# TODO: G_IO_ERROR_CANCELLED should not set status to bad
			# but I have absolutely no idea how to check the type of GError
			self.location &= ~Location.Memory
			self.status = Status.Bad
			
			e = gerror
		else:
			self.location |= Location.Memory
			self.status = Status.Good
			self.load_metadata()
		finally:
			self.emit("finished-loading", e)
			
	def unload(self):
		if self.cancellable:
			self.cancellable.cancel()
			self.cancellable = None
			
		self.pixbuf = None
		self.animation = None
		self.location &= ~Location.Memory
		self.status = Status.Good
		
	def load_metadata(self):
		if self.metadata is None:
			self.metadata = ImageMeta()
		
		# These file properties are queried from the file info
		try:
			file_info = self.gfile.query_info(
			                       "standard::size,time::modified", 0, None)
			try:
				size_str = file_info.get_attribute_as_string("standard::size")
				self.metadata.data_size = int(size_str)
			except:
				self.metadata.data_size = 0
			try:
				time_str = file_info.get_attribute_as_string("time::modified")
				self.metadata.modification_date = float(time_str)
			except:
				self.metadata.modification_date = float(time.time())
		except:
			self.metadata.modification_date = float(time.time())
			self.metadata.data_size = 0
		
		# The width and height of the image are loaded from guess where
		if self.pixbuf:
			self.metadata.width = self.pixbuf.get_width()
			self.metadata.height = self.pixbuf.get_height()
			
		elif self.animation:
			self.metadata.width = self.animation.get_width()
			self.metadata.height = self.animation.get_height()
			
		elif self.gfile.is_native():
			try:
				filepath = self.gfile.get_path()
				fmt, width, height = GdkPixbuf.Pixbuf.get_file_info(filepath)
				self.metadata.width = width
				self.metadata.height = height
			except:
				self.metadata.width = 0
				self.metadata.height = 0
			
		# TODO: Add support for non-native files
		
class ImageDataNode(ImageNode):
	''' An ImageNode created from a pixbuf
	    This ImageNode can not be loaded or unloaded
	    Because it can not find the data source by itself '''
	    
	def __init__(self, pixbuf, name="Image Data"):
		ImageNode.__init__(self)
		
		self.fullname = self.name = name
		self.pixbuf = pixbuf
		
		self.load_metadata()
		
		self.location = Location.Memory
		self.status = Status.Good
		
	def load_metadata(self):
		if self.metadata is None:
			self.metadata = ImageMeta()
			
		self.metadata.width = self.pixbuf.get_width()
		self.metadata.height = self.pixbuf.get_height()
		self.metadata.modification_date = time.time()
		self.metadata.data_size = 0
		
	def unload(self):			
		self.pixbuf = None
		self.location &= ~Location.Memory
		
def IsAlbumFile(possibly_album_file):
	file_type = possibly_album_file.query_file_type(0, None)
	return file_type == Gio.FileType.DIRECTORY
	
def GetAlbumImages(album_file):
	result = []
	album_enumerator = album_file.enumerate_children(
	                              "standard::type,standard::name", 0, None)
	for a_file_info in album_enumerator:
		if a_file_info.get_file_type() == Gio.FileType.REGULAR:
			a_file = Gio.File.get_child(album_file, a_file_info.get_name())
			if IsSupportedImage(a_file):
				an_image = ImageGFileNode(a_file)
				result.append(an_image)
				
	return result
	
def GetFileImageFiles(parent_file):
	result = []
	parent_enumerator = parent_file.enumerate_children(
	                                "standard::type,standard::name", 0, None)
	for a_file_info in parent_enumerator:
		if a_file_info.get_file_type() == Gio.FileType.REGULAR:
			a_file = Gio.File.get_child(parent_file, a_file_info.get_name())
			if IsSupportedImage(a_file):
				result.append(a_file)
				
	return result
	
def IsSupportedImage(a_file):
	an_uri = a_file.get_uri()
	extension_test = any((an_uri.endswith(an_extension) \
	                      for an_extension in Extensions))
	return extension_test
