'''
	This script creates the file filters required to load files
'''

import pygtk
pygtk.require("2.0")
import gtk, os, re, urllib, urllib2
from gettext import gettext as _

Filters = []
Mimes = []
Extensions = set()

# Create "All Files" filter
contradictory_filter = gtk.FileFilter()
contradictory_filter.set_name(_("All Files"))
contradictory_filter.add_pattern("*")

# Create images filter
images_filter = gtk.FileFilter()
images_filter.set_name(_("Images"))

# Add the "images" filter before "all files" filter
Filters.append(images_filter)
Filters.append(contradictory_filter)

# Create file filters from formats supported by gdk pixbuf
_formats = gtk.gdk.pixbuf_get_formats()
for aformat in _formats:
	format_filter = gtk.FileFilter()
	filter_name = aformat["name"] + " ("
	
	# Add mime types
	for a_mimetype in aformat["mime_types"]:
		format_filter.add_mime_type(a_mimetype)
		images_filter.add_mime_type(a_mimetype)
		Mimes.append(a_mimetype)
		
	# Add patterns based on extensions
	first_ext = True
	for an_extension in aformat["extensions"]:
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
	
class ImageNode(object):
	def __init__(self):
		self.pixbuf = None
		self.name = ""
		self.fullname = ""
	
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
		self.pixbuf = None
		
	def is_loaded(self):
		return self.pixbuf is not None
		
	def do_load(self):
		self.pixbuf = gtk.gdk.pixbuf_new_from_file(self.filepath)
			
	def do_unload(self):
		self.pixbuf = None
		return True
		
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
		try:
			loader = gtk.gdk.PixbufLoader()
		
			response = urllib2.urlopen(self.uri)
			loader.write(response.read())
			loader.close()
		
			self.pixbuf = loader.get_pixbuf()
			
		except urllib2.URLError:
			raise Exception(_("Could not access \"%s\"" % self.uri))
			
		except:
			raise Exception(_("Could not load \"%s\"" % self.uri))
		
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
		
	def is_loaded(self):
		return True # Data nodes are always loaded
		
	def do_load(self):
		pass # Can't load data nodes
		
	def do_unload(self):
		pass # Can't unload data nodes

def PathFromURI(uri):
	for prefix in ("file:\\\\\\", "file://", "file:"):
		if uri.startswith(prefix):
			uri_path = uri[len(prefix):]
			filepath = urllib2.url2pathname(uri_path)
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
