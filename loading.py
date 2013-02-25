'''
	This script creates the file filters required to load files
'''

import pygtk
pygtk.require("2.0")
import gtk, os, re
from gettext import gettext as _

Filters = []
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
	
class ImageNode:
	def __init__(self, filename):
		self.filename = filename
		self.title = os.path.basename(filename)
		self.pixbuf = self.previous = self.next = None
		
	def load(self, filename = None):
		if filename is None:
			if self.pixbuf is not None:
				return
		else:
			self.filename = filename
			self.title = os.path.basename(filename)
			
		self.pixbuf = gtk.gdk.pixbuf_new_from_file(self.filename)
	
	def cut_ties(self):
		if self.next and self.next.previous is self:
			self.next.previous = self.previous
			
		if self.previous and self.previous.next is self:
			self.previous.next = self.next
		
		self.previous = self.next = None
		
	def unload(self):
		self.pixbuf = None
		
def get_files(directory):
	result = []

	dirlist = os.listdir(directory)
		
	filepaths = [os.path.join(directory, filename) for filename in os.listdir(directory) if os.path.isfile(os.path.join(directory, filename))]
	
	for a_filepath in filepaths:
		filename, fileext = os.path.splitext(a_filepath)
		if fileext in Extensions:
			result.append(a_filepath)
			
	return result
