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

LoaderList = []

class CombinedDialogOption:
	List = []
	
	def __init__(self, loader, name, options):
		self.loader = loader
		self.name = name
		self.options = options
		
	def create_filter(self):
		''' Creates a Gtk.FileFilter for all these options '''
		result = Gtk.FileFilter()
		result.dialog_option = self
		
		result.set_name(self.name)
		for an_option in self.options:
			for a_pattern in an_option.patterns:
				result.add_pattern(a_pattern)
			
			for a_mime_type in an_option.mime_types:
				result.add_mime_type(a_mime_type)
		
		return result

class DialogOption:
	List = []
	
	def __init__(self, loader, name, patterns=[], mime_types=[]):
		self.loader = loader
		self.name = name
		self.patterns = patterns
		self.mime_types = mime_types
		
	def create_filter(self):
		''' Creates a Gtk.FileFilter for this option '''
		result = Gtk.FileFilter()
		result.dialog_option = self
		
		result.set_name(self.name)
		for a_pattern in self.patterns:
			result.add_pattern(a_pattern)
			
		for a_mime_type in self.mime_types:
			result.add_mime_type(a_mime_type)
		
		return result

class Context:
	''' A loading context is used to return data from loader functions.
	    Loaders can return loaded image nodes, new files to be loaded
	    by other loaders or uris and also report problems with this class. '''
	
	BasicFileInfo = ("standard::name," +
	                 "standard::type," +
	                 "standard::content-type")
	
	def __init__(self, uris=None, files=None, images=None):
		self.uris = uris or []
		self.files = files or []
		self.images = images or []
		self.problems = {}
		
	def uris_to_files(self):
		''' Converts all uris to files and removes them '''
		new_files = [Gio.File.new_for_uri(an_uri) for an_uri in self.uris]
		self.files.extend(new_files)
		del self.uris[:]
	
	def load_files_info(self):
		for a_file in self.files:
			try:
				Context.LoadFileInfo(a_file)
				
			except Exception as a_problem:
				self.problems[a_file] = a_problem
	
	def add_sibling_files(self, loader):
		Context.AddSiblingFiles(self, loader, self.files)
	
	@staticmethod
	def LoadFileInfo(gfile):
		if not hasattr(gfile, "info"):
			gfile.info = gfile.query_info(
			                   Context.BasicFileInfo,
				               Gio.FileQueryInfoFlags.NONE,
				               None)
				               
	@staticmethod
	def AddSiblingFiles(context, loader, gfiles):
		''' Add to context files that loader should open
			and are children of gfiles parents '''
	
		# Get parent files from input #
		parent_files = set()
		for a_gfile in gfiles:
			a_parent_file = a_gfile.get_parent()
			if a_parent_file:
				parent_files.add(a_parent_file)
	
		# Get children files from parent files from input #
		siblings = set()
		for a_parent_file in parent_files:
			# Use BasicFileInfo here to save trouble #
			enumerator = a_parent_file.enumerate_children(
				                       Context.BasicFileInfo, 0, None)
		
			for a_file_info in enumerator:
				a_sibling = Gio.File.get_child(
					            a_parent_file, a_file_info.get_name())
					            
				# Only add children files that do not equal an input file #
				for a_gfile in gfiles:
					if a_gfile.equal(a_sibling):
						break # cool trick, huh?
				else:
					a_sibling.info = a_file_info
					siblings.add(a_sibling)
					
		new_files = [a_file for a_file in siblings \
		                        if loader.should_open(a_file)]
		context.files.extend(new_files)

class LoadersLoader:
	''' This loader will dispatch calls to loaders in a list passed to it '''
	def __init__(self, loaders, reversed_open=False):
		self.loaders = loaders
		self.reversed_open = reversed_open
		
	def should_open(self, gfile):
		return any((a_loader.should_open(gfile) for a_loader in self.loaders))
		
	def open_file(self, context, gfile):
		loaders = reversed(self.loaders) if self.reversed_open else self.loaders
		
		for a_loader in loaders:
			if a_loader.should_open(gfile):
				a_loader.open_file(context, gfile)
				break
				
class DirectoryLoader:
	''' A directory loader. Returns files in a directory. '''
	@classmethod
	def should_open(cls, gfile):
		Context.LoadFileInfo(gfile)
		return gfile.info.get_file_type() == Gio.FileType.DIRECTORY
				
	@classmethod
	def open_file(cls, context, gfile):
		gfile_enumerator = gfile.enumerate_children(
		                         Context.BasicFileInfo, 0, None)
		for a_file_info in gfile_enumerator:
			try:
				a_child_file = Gio.File.get_child(gfile, a_file_info.get_name())
				a_child_file.info = a_file_info
				context.files.append(a_child_file)
				
			except Exception:
				raise
				
class PixbufFileLoader:
	''' A GdkPixbuf file loader. Should load images supported by GdkPixbuf '''
	Options = []
	Extensions = tuple()
	
	@classmethod
	def should_open(cls, gfile):
		uri = gfile.get_uri()
		return uri.endswith(PixbufFileLoader.Extensions)
		
	@classmethod
	def open_file(cls, context, gfile):
		try:
			new_image = PixbufFileImageNode(gfile)
			
		except Exception:
			pass
			
		else:
			context.images.append(new_image)
	
	@staticmethod
	def _setup():
		# Create dialog options for PixbufFileLoader
		_formats = GdkPixbuf.Pixbuf.get_formats()
		_mime_types = set()
		_patterns = set()
		_extensions = set()
		for a_format in _formats:
			# get mime types
			_mime_types.update(a_format.get_mime_types())
	
			# get extensions, create patterns
	
			for an_extension in a_format.get_extensions():
				_patterns.add("*." + an_extension)
				_extensions.add("." + an_extension)
		
		PixbufFileLoader.Extensions = tuple(_extensions)		
		PixbufFileLoader.DialogOption = DialogOption(
		                                PixbufFileLoader, _("Pixbuf Images"),
		                                _patterns, _mime_types)
		                                
class PixbufAnimationFileLoader:
	Extensions = (".gif")
	
	@classmethod
	def should_open(cls, gfile):
		uri = gfile.get_uri()
		return uri.endswith(PixbufAnimationFileLoader.Extensions)
		
	@classmethod
	def open_file(cls, context, gfile):
		try:
			new_image = PixbufAnimationFileImageNode(gfile)
			
		except Exception:
			pass
			
		else:
			context.images.append(new_image)

PixbufAnimationFileLoader.DialogOption = DialogOption(PixbufAnimationFileLoader,
                                                      _("Pixbuf Animations"),
                                                      ["*.gif"], ["image/gif"])
                                                      
LoadersLoader.LoaderListLoader = LoadersLoader(LoaderList, reversed_open=True)
SupportedFilesOption = CombinedDialogOption(LoadersLoader.LoaderListLoader,
                                            _("Supported Files"),
                                            DialogOption.List)
                                            
CombinedDialogOption.List.append(SupportedFilesOption)

PixbufFileLoader._setup()

LoaderList.append(PixbufFileLoader)
LoaderList.append(PixbufAnimationFileLoader)

DialogOption.List.append(PixbufFileLoader.DialogOption)
DialogOption.List.append(PixbufAnimationFileLoader.DialogOption)

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
		raise NotImplementedError
		
	def unload(self):
		raise NotImplementedError
		
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
				
	def __str__(self):
		return self.fullname
	
	def get_metadata(self):
		if not self.metadata:
			self.load_metadata()
			
		return self.metadata
	
	def create_frame(self, view):
		raise NotImplementedError

import viewing

class GFileImageNode(ImageNode):
	def __init__(self, gfile):
		super().__init__()
		self.gfile = gfile
		
		info = gfile.query_info("standard::display-name", 0, None)
		self.name = info.get_attribute_as_string("standard::display-name")
		self.fullname = self.gfile.get_parse_name()
		
		self.location = Location.Disk if gfile.is_native() else Location.Distant

class PixbufImageNode(ImageNode):
	def __init__(self, pixbuf=None):
		super().__init__()
		self.pixbuf = pixbuf
		self._surface = None
	
	@property
	def surface(self):
		if self._surface is None:
			self._surface = PixbufImageNode.SurfaceFromPixbuf(self.pixbuf)
			
		return self._surface
		
	def unload(self):
		self._surface = None

	def create_frame(self, view):
		return viewing.ImageSurfaceFrame(self.surface)
	
	@staticmethod
	def SurfaceFromPixbuf(pixbuf):
		''' Creates a cairo surface from a Gdk pixbuf'''
		if pixbuf:
			surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
				                         pixbuf.get_width(),
				                         pixbuf.get_height())
			cr = cairo.Context(surface)
			Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
			cr.paint()
		
		else:
			surface = None
		
		return surface

class PixbufDataImageNode(PixbufImageNode, ImageNode):
	''' An ImageNode created from a pixbuf
	    This ImageNode can not be loaded or unloaded
	    Because it can not find the data source by itself '''
	    
	def __init__(self, pixbuf, name="Image Data"):
		ImageNode.__init__(self)
		PixbufImageNode.__init__(self, pixbuf)
		
		self.fullname = self.name = name
		
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
		PixbufImageNode.unload(self)
		self.pixbuf = None
		self.location &= ~Location.Memory
		self.status = Status.Bad

class PixbufFileImageNode(GFileImageNode, PixbufImageNode):
	def __init__(self, gfile):
		super().__init__(gfile=gfile)
		
		self.status = Status.Good
		self.cancellable = None
		
	def load(self):
		if self.is_loading:
			raise Exception
			
		self.cancellable = Gio.Cancellable()
		
		stream = self.gfile.read(None)
		
		self.status = Status.Loading
		load_async = GdkPixbuf.Pixbuf.new_from_stream_async
		self.pixbuf = load_async(stream, self.cancellable, self._loaded, None)
		
	def _loaded(self, me, result, *data):
		e = None
		try:
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
		
		PixbufImageNode.unload(self)
		self.pixbuf = None
		self.location &= ~Location.Memory
		self.status = Status.Good
		
	def load_metadata(self):
		if self.metadata is None:
			self.metadata = ImageMeta()
		
		# These file properties are queried from the file info
		try:
			file_info = self.gfile.query_info(
			                       "standard::size,time::modified", 0, None)

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
		if self.pixbuf:
			self.metadata.width = self.pixbuf.get_width()
			self.metadata.height = self.pixbuf.get_height()
			
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

class PixbufAnimationFileImageNode(GFileImageNode, PixbufImageNode):
	def __init__(self, gfile):
		super().__init__(gfile=gfile)
		
		self.animation = None
		
		self.status = Status.Good
		self.cancellable = None
		
	def load(self):
		if self.is_loading:
			raise Exception
			
		self.cancellable = Gio.Cancellable()
		
		stream = self.gfile.read(None)
		parsename = self.gfile.get_parse_name()
		
		self.status = Status.Loading
		load_async = GdkPixbuf.PixbufAnimation.new_from_stream_async
		self.animation = load_async(stream, self.cancellable,
		                            self._loaded, None)
		
	def _loaded(self, me, result, *data):
		e = None
		try:
			async_finish = GdkPixbuf.PixbufAnimation.new_from_stream_finish
			self.animation = async_finish(result)
			
			if self.animation.is_static_image():
				self.pixbuf = self.animation.get_static_image()
				self.animation = None

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
	
	def create_frame(self, view):
		if self.pixbuf:
			return PixbufImageNode.create_frame(self, view)
		else:
			return viewing.AnimatedPixbufFrame(self.animation)
	
	def unload(self):
		if self.cancellable:
			self.cancellable.cancel()
			self.cancellable = None
		
		PixbufImageNode.unload(self)
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
			self.metadata.width = self.animation.get_width()
			self.metadata.height = self.animation.get_height()
			
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
