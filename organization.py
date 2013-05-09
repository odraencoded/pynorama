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
    
#TODO: Make this module organize images better.

import os
from functools import cmp_to_key
from gi.repository import GLib

class Album:
	''' It organizes images '''
	
	def __init__(self):
		self.images = []
		self.reverse = False
	
	def __len__(self):
		return len(self.images)
	
	def __getitem__(self, index):
		return self.images[index]
	
	def clear(self):
		del self.images[:]
	
	def get_first(self):
		return self.images[0]
	
	def get_last(self):
		return self.images[-1]
	
	def remove(self, *images):
		for an_image in images:
			an_image.remove_links()
			
			self.images.remove(an_image)	
	
	# Adds images to the album and tries to sort them
	def add(self, *images):
		for an_image in images:
			index = len(self.images)
				
			self.images.insert(index, an_image)
			prev = self.images[index - 1]
			next = self.images[(index + 1) % len(self.images)]
			
			an_image.insert_links(prev, next)
			
	def append(self, new_image, previous_image = None):
		if previous is None:
			index = -1
			previous_image = self.images[-1]
		else:
			index = self.images.index(previous) + 1
			
		next_image = self.images[index + 1]
		self.images.insert(index, new_image)
		previous
		
		if self.images:
			image.previous = self.images[-1]
			image.next = self.images[0]
			
			image.previous.next = image
			image.next.previous = image
		else:
			image.next = image.previous = image
		
		self.images.append(image)
		
	def sort(self, comparer, reverse=False):
		if len(self.images) <= 1:
			return
			
		# Sorts album
		self.images = sorted(self.images, key=cmp_to_key(comparer), reverse=reverse)
		
		# Refreshes next/previous links
		first_image = self.images[0]
		previous_image = self.images[-1]
		for a_image in self.images:				
			if previous_image:
				previous_image.next = a_image
			
			a_image.next = first_image
			a_image.previous = previous_image
			previous_image = a_image
	
	def find_image(self, filename):
		for a_image in self.images:
			if os.path.samefile(a_image.filename, filename):
				return a_image
		
		return None

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
	
