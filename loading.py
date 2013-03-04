'''
	This script creates the file filters required to load files
'''

import os, re, urllib, datetime
from urllib import error, request

from gi.repository import Gtk, GdkPixbuf
from gettext import gettext as _

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
	'''
		Contains some assorted metadata of an image
		This should be used in sorting functions
	'''
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
		
class ImageFileNode(ImageNode):
	'''
		An ImageNode created from a file
	'''
	def __init__(self, filepath):
		ImageNode.__init__(self)
		
		self.fullname = self.filepath = filepath
		self.name = os.path.basename(self.filepath)
				
	def is_loaded(self):
		return self.pixbuf is not None
		
	def do_load(self):
		self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.filepath)
		
		self.load_metadata()
					
	def load_metadata(self):
		# Grab a bunch of info we aren't going to use in one go
		file_stat = os.stat(self.filepath)
		
		if self.metadata is None:
			self.metadata = ImageMeta()
		
		if self.pixbuf is None:
			pixformat, self.metadata.width, self.metadata.height = GdkPixbuf.Pixbuf.get_file_info(self.filepath)
			
		else:
			self.metadata.width = self.pixbuf.get_width()
			self.metadata.height = self.pixbuf.get_height()
			
		self.metadata.data_size = file_stat.st_size
		self.metadata.modification_date = datetime.datetime.fromtimestamp(file_stat.st_mtime)
		
	def do_unload(self):
		self.pixbuf = None
		
class ImageURINode(ImageNode):
	'''
		An ImageNode created from an URI
	'''
	def __init__(self, uri):
		ImageNode.__init__(self)
		
		self.fullname = self.name = self.uri = uri
	
	def is_loaded(self):
		return self.pixbuf is not None
	
	def do_load(self):
		loader = GdkPixbuf.PixbufLoader()
		
		try:		
			response = urllib.request.urlopen(self.uri)
			loader.write(response.read())
			
			self.pixbuf = loader.get_pixbuf()
			self.load_metadata(response)
			
		except urllib.error.URLError:
			raise Exception(_("Could not access \"%s\"" % self.uri))
			
		except:
			raise Exception(_("Could not load \"%s\"" % self.uri))
		
		finally:
			loader.close()
	
	def load_metadata(self, response=None):
		# Should go without saying that getting metadata over a network is
		# Well, expensive. Don't mind it, nobody will ever notice!
		# Gwahahaahahahhaahahahaha.
		
		if self.metadata is None:
			self.metadata = ImageMeta()
		
		self.metadata.data_size = 0
		self.metadata.modification_date = datetime.datetime.now()
		self.metadata.width = 0
		self.metadata.height = 0
			
	def do_unload(self):
		self.pixbuf = None
	
class ImageDataNode(ImageNode):
	'''
		An ImageNode created from a pixbuf
		This ImageNode can not be loaded or unloaded
		Because it can not find the data source by itself
	'''
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

def PathFromURI(uri):
	for prefix in ("file:\\\\\\", "file://", "file:"):
		if uri.startswith(prefix):
			uri_path = uri[len(prefix):]
			filepath = urllib.request.url2pathname(uri_path)
			return filepath
			
	return None

def get_image_paths(directory):
	# Iterate through all filepaths in the directory
	dir_paths = (os.path.join(directory, filename) for filename in os.listdir(directory))
	
	for a_path in dir_paths:
		# if it is a file, check if the extension is a valid image extension
		if os.path.isfile(a_path):
			file_ext = os.path.splitext(a_path)[1]
			if file_ext in Extensions:
				yield a_path
