''' point.py contains some tuple-y point math '''

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
    
import math
zero = 0, 0
center = .5, .5
one = 1, 1

def add(a, b):
	return a[0] + b[0], a[1] + b[1]
	
def subtract(a, b):
	return a[0] - b[0], a[1] - b[1]
	
def multiply(a, b):
	return a[0] * b[0], a[1] * b[1]
		
def divide(a, b):
	return a[0] / b[0], a[1] / b[1]

def flip(point, h, v):
	return point[0] * (-1 if h else 1), point[1] * (-1 if v else 1)

def scale(point, scalar):
	return point[0] * scalar, point[1] * scalar

def spin(point, r):
	x, y = point
	rx = x * math.cos(r) - y * math.sin(r)
	ry = x * math.sin(r) + y * math.cos(r)
	return rx, ry

def is_tall(point):
	return point[0] < point[1]
	
def is_wide(point):
	return point[0] > point[1]

def length(point):
	return (point[0] ** 2 + point[1] ** 2) ** .5

class Rectangle:
	def __init__(self, left=0, top=0, width=0, height=0):
		self.left = left
		self.top = top
		self.width = width
		self.height = height
		
	@property
	def right(self):
		return self.left + self.width
		
	@property
	def bottom(self):
		return self.top + self.height
	
	def unbox_point(relative_point):
		return add((self.left, self.top),
		            multiply((self.width, self.height), relative_point))
	
	def to_tuple(self):
		return self.left, self.top, self.width, self.height
	
	def copy(self):
		return Rectangle(self.left, self.top, self.width, self.height)
	
	def shift(self, displacement):
		l, t = add((self.left, self.top), displacement)
		return Rectangle(l, t, self.width, self.height)
	
	def spin(self, angle):
		''' Basic trigonometrics '''
		result = self.copy()
		if angle:
			a = spin((self.left, self.top), angle)
			b = spin((self.right, self.top), angle)
			c = spin((self.right, self.bottom), angle)
			d = spin((self.left, self.bottom), angle)
		
			(left, top), (right, bottom) = a, a
			for (x, y) in [b, c, d]:
				left = min(left, x)
				top = min(top, y)
				right = max(right, x)
				bottom = max(bottom, y)
			
			result.top, result.left = top, left
			result.width = right - left
			result.height = bottom - top
		
		return result
	
	def flip(self, horizontal, vertical):
		''' Basic conditions '''
		result = self.copy()
		if horizontal:
			result.left = -self.right
	
		if vertical:
			result.top = -self.bottom
				
		return result
		
	def scale(self, scale):
		''' Basic mathematics '''
		result = self.copy()
		result.left *= scale
		result.top *= scale
		result.width *= scale
		result.height *= scale
		return result
	
	@staticmethod
	def Union(*rectangles):
		''' Rectangles! UNITE!!! '''
		if rectangles:
			first = True
			t, l, r, b = 0,0,0,0
			for a_rectangle in rectangles:
				if a_rectangle:
					if first:
						t = a_rectangle.top
						l = a_rectangle.left
						b = a_rectangle.bottom
						r = a_rectangle.right
						first = False
					else:
						t = min(t, a_rectangle.top)
						l = min(l, a_rectangle.left)
						b = max(b, a_rectangle.bottom)
						r = max(r, a_rectangle.right)
					
			return Rectangle(l, t, r - l, b - t)
		
		else:
			return Rectangle()
