''' This is the loading module. It should have all the stuff
    loading related. Such as supported filters, mime types,
    methods to load things and other stuff. '''

import os, re, datetime, time

from gi.repository import Gtk, Gdk, GdkPixbuf, Gio, GObject
from gettext import gettext as _
import cairo

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
	
class ImageNode():
	def __init__(self):
		self.pixbuf = None
		self.animation = None
		self.metadata = None
		
		self.fullname, self.name = "", ""
		self.next = self.previous = None
	
	def reload(self):
		if self.is_loaded():
			self.do_unload()
			
		self.do_load()
	
	def load(self):
		if not self.is_loaded():
			self.do_load()
	
	def unload(self):
		if self.is_loaded():
			self.do_unload()
			
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
		
	def is_loaded(self):
		return not(self.pixbuf is None and self.animation is None)
		
	def do_load(self):		
		stream = self.gfile.read(None)
		
		parsename = self.gfile.get_parse_name()
		if self.gfile.is_native() and parsename.endswith(".gif"):
			self.animation = GdkPixbuf.PixbufAnimation.new_from_file(parsename)
			if self.animation.is_static_image():
				self.pixbuf = self.animation.get_static_image()
				self.animation = None
		else:
			self.pixbuf = GdkPixbuf.Pixbuf.new_from_stream(stream, None)
			
		self.load_metadata()
	
	def load_metadata(self):
		if self.metadata is None:
			self.metadata = ImageMeta()
		
		# These file properties are queried from the file info
		try:
			file_info = self.gfile.query_info("standard::size,time::modified", 0, None)
			try:
				size_str = file_info.get_attribute_as_string("standard::size")
				self.metadata.data_size = int(size_str)
			except:
				self.metadata.data_size = 0
			try:
				time_str = file_info.get_attribute_as_string("time::modified")
				self.metadata.modification_date = time.ctime(int(time_str))
			except:
				self.metadata.modification_date = time.time()
		except:
			self.metadata.modification_date = time.time()
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
		
	def do_unload(self):
		self.pixbuf = None
		self.animation = None
		
class ImageDataNode(ImageNode):
	''' An ImageNode created from a pixbuf
	    This ImageNode can not be loaded or unloaded
	    Because it can not find the data source by itself '''
	    
	def __init__(self, pixbuf, name="Image Data"):
		ImageNode.__init__(self)
		
		self.fullname = self.name = name
		self.pixbuf = pixbuf
		
		self.load_metadata()
				
	def is_loaded(self):
		return True # Data nodes are always loaded
		
	def do_load(self):
		pass # Can't load data nodes
	
	def load_metadata(self):
		if self.metadata is None:
			self.metadata = ImageMeta()
			
		self.metadata.width, self.metadata.height = self.pixbuf.get_width(), self.pixbuf.get_height()
		self.metadata.modification_date = datetime.datetime.now()
		self.metadata.data_size = 0
		
	def do_unload(self):
		pass # Can't unload data nodes
				
def IsAlbumFile(possibly_album_file):
	file_type = possibly_album_file.query_file_type(0, None)
	return file_type == Gio.FileType.DIRECTORY
	
def GetAlbumImages(album_file):
	result = []
	album_enumerator = album_file.enumerate_children("standard::type,standard::name", 0, None)
	for a_file_info in album_enumerator:
		if a_file_info.get_file_type() == Gio.FileType.REGULAR:
			a_file = Gio.File.get_child(album_file, a_file_info.get_name())
			if IsSupportedImage(a_file):
				an_image = ImageGFileNode(a_file)
				result.append(an_image)
				
	return result
	
def GetFileImageFiles(parent_file):
	result = []
	parent_enumerator = parent_file.enumerate_children("standard::type,standard::name", 0, None)
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
