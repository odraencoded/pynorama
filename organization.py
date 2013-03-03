import os

class ImageNodeList:
	'''
		It organizes files
	'''
	
	def __init__(self):
		self.images = []
		self.reverse = False
							
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
	
	# Adds images to the list	and tries to sort them
	def add(self, *images):
		sorting_index = len(self.images) / 2
		
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
		
	def sort(self, comparer):
		if len(self.images) <= 1:
			return
			
		# Sorts list
		self.images = sorted(self.images, cmp=comparer, reverse=self.reverse)
		
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
	
class Sorting:
	'''
		Contains organizing methods
	'''
	@staticmethod
	def ByFullname(image_a, image_b):
		return cmp(image_a.fullname, image_b.fullname)
	
