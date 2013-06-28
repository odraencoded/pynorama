''' extending.py is all about making the program do more things '''

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

import utility

class LayoutOption:
	''' Represents a layout choice. '''
	
	# A list of layouts avaiable for the program
	List = []
	
	def __init__(self, codename="", name="", description=""):
		''' codename must be a string identifier for this option
		    name is a localized label for the layout
		    description is a description, duh '''
		self.codename = codename
		self.name = name
		self.description = description
	
	
	def create_layout(self):
		''' Replaces this with something that creates a layout '''
		raise NotImplementedError
		

class MouseHandlerFactory:
	''' Manufacturates mouse handlers & accessories '''
	
	def __init__(self):
		codename = "" # A string identifier
		label = "" # A label for the UI
		
	
	def produce(self):
		product = self.create_default()
		product.factory = self
		return product
		
	
	def create_default(self):
		''' This should create a mouse handler with default attributes '''
		
		raise NotImplementedError
		
		
	def create_settings_widget(self, handler):
		''' Creates a widget for configuring a mouse handler '''
		
		raise NotImplementedError

MouseHandlerBrands = list()
