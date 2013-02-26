import os

class Organizer:
	'''
		It organizes files
	'''
	
	def __init__(self):
		self.images = []
		
	def append(self, image):
		if self.images:
			image.previous = self.images[-1]
			image.next = self.images[0]
			
			image.previous.next = image
			image.next.previous = image
		else:
			image.next = image.previous = image
		
		self.images.append(image)
		
	def sort(self, comparer, reverse=False):
		if len(self.images) == 0:
			return
			
		# Sorts list
		self.images = sorted(self.images, cmp=comparer, reverse=reverse)
		
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
	
class ImageSort:
	'''
		Contains organizing methods
	'''
	@staticmethod
	def Filenames(image_a, image_b):
		return cmp(image_a.filename, image_a.filename)
	
