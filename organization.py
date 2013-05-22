''' organization.py contains code about collections of images. '''

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
    
import os
from functools import cmp_to_key
from gi.repository import GLib, GObject
from collections import MutableSequence

class Album(GObject.Object):
	''' It organizes images '''
	
	__gsignals__ = {
		"image-added" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"image-removed" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"order-changed" : (GObject.SIGNAL_RUN_FIRST, None, []),
	}
	def __init__(self):
		GObject.GObject.__init__(self)
		MutableSequence.__init__(self)
		
		self.connect("notify::reverse", self.__queue_autosort)
		self.connect("notify::autosort", self.__queue_autosort)
		self.connect("notify::comparer", self.__queue_autosort)
		
		self._store = []
		self.__autosort_signal_id = None
		
	# --- Mutable sequence interface down this line ---#
	def __len__(self):
		return len(self._store)
		
	def __getitem__(self, index):
		return self._store[index]
		
	def __setitem__(self, index):
		self._store[index] = value
		
	def __delitem__(self, index):
		image = self._store.pop(index)
		self.emit("image-removed", image, index)
	
	def insert(self, index, image):
		self._store.insert(index, image)
		self.emit("image-added", image, index)
		self.__queue_autosort()
	
	# --- "inheriting" down this line --- #
	
	__contains__ = MutableSequence.__contains__
	__iter__ = MutableSequence.__iter__
	__reversed__ = MutableSequence.__reversed__
	
	append = MutableSequence.append
	count = MutableSequence.count
	extend = MutableSequence.extend
	index = MutableSequence.index
	pop = MutableSequence.pop
	remove = MutableSequence.remove
	reverse = MutableSequence.reverse
	
	def sort(self):
		if self.__autosort_signal_id:
			GLib.source_remove(self.__autosort_signal_id)
			self.__autosort_signal_id = None
			
		if self.comparer and len(self._store) > 1:
			self._store.sort(key=cmp_to_key(self.comparer),
			                 reverse=self.reverse)
			
			self.emit("order-changed")
	
	def next(self, image):
		''' Returns the image after the input '''
		index = self._store.index(image)
		return self._store[(index + 1) % len(self._store)]
		
	def previous(self, image):
		''' Returns the image before the input '''
		index = self._store.index(image)
		return self._store[(index - 1) % len(self._store)]		
	
	def around(self, image, forward, backwards):
		''' Returns "forward" images after "image" and
		    "backwards" images before "image".
		    This method cycles around the list '''
		result = []
		if forward or backwards:
			start = self._store.index(image)
			count = len(self._store)
		
			for i in range(1, forward):
				result.append(self._store[(start + i) % count])
			
			for i in range(1, backwards):
				result.append(self._store[(start - i) % count])
			
		return result
	
	# --- properties down this line --- #
	
	autosort = GObject.property(type=bool, default=False)
	comparer = GObject.property(type=object, default=None)
	reverse = GObject.property(type=bool, default=False)
	
	def __queue_autosort(self, *data):
		if self.autosort and not self.__autosort_signal_id:
			self.__autosort_signal_id = GLib.idle_add(
			    self.__do_autosort, priority=GLib.PRIORITY_HIGH+10)
	
	def __do_autosort(self):
		self.__autosort_signal_id = None
		if self.autosort:
			self.sort()
		
		return False

def cmp(a, b):
	# Pfft, versions
	return (a > b) - (b > a)

class Ordering:
	''' Contains ordering functions '''
	
	@staticmethod
	def ByName(image_a, image_b):
		keymaker = GLib.utf8_collate_key_for_filename
		key_a = keymaker(image_a.fullname, len(image_a.fullname))
		key_b = keymaker(image_b.fullname, len(image_b.fullname))
		return cmp(key_a, key_b)
		
	@staticmethod
	def ByCharacters(image_a, image_b):
		return cmp(image_a.fullname.lower(), image_b.fullname.lower())
			
	@staticmethod
	def ByFileSize(image_a, image_b):
		meta_a = image_a.get_metadata()
		meta_b = image_b.get_metadata()
		
		return cmp(meta_a.data_size, meta_b.data_size)
		
	@staticmethod
	def ByFileDate(image_a, image_b):
		meta_a = image_a.get_metadata()
		meta_b = image_b.get_metadata()
		
		return cmp(meta_a.modification_date, meta_b.modification_date) * -1
		
	@staticmethod
	def ByImageSize(image_a, image_b):
		meta_a = image_a.get_metadata()
		meta_b = image_b.get_metadata()
		
		return cmp(meta_a.get_area(), meta_b.get_area())
		
	@staticmethod
	def ByImageWidth(image_a, image_b):
		meta_a = image_a.get_metadata()
		meta_b = image_b.get_metadata()
		
		return cmp(meta_a.width, meta_b.width)
		
	@staticmethod
	def ByImageHeight(image_a, image_b):
		meta_a = image_a.get_metadata()
		meta_b = image_b.get_metadata()
		
		return cmp(meta_a.height, meta_b.height)
	
