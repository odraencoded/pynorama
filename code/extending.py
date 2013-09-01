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
from collections import OrderedDict

LoadedComponentPackages = set()

class ComponentPackage:
    """Represents a set of components that extend the app"""
    def add_on(self, app):
        """Adds its components to the app"""
        raise NotImplementedError


class Component:
    """Something that can be mapped into an component map"""
    def __init__(self, codename):
        self.codename = codename

class ComponentMap:
    """ A map of component categories specified by a codename
    
    All extensible parts of the application have a category in the app
    own component map. Component packages may then add app extensions
    onto their components categories
    
    """
    
    #TODO: Make it a GObject and add signals for adding/removing stuff
    
    def __init__(self):
        self._categories = OrderedDict()
    
    
    def __getitem__(self, key):
        """ Returns a component category or component from the component map
        
        If one string is passed, it returns the category whose codename
        matches that string.
        
        If a second string is passed, it returns the component whose codename
        is the second string inside the category specified by the first string.
        
        """
        
        if isinstance(key, tuple):
            category, codename = key
            return self._categories[category][codename]
            
        else:
            return self._categories[key]
     
     
    def add(self, category, component):
        """ Adds a component to a category in this component map """
        self._categories[category].add(component)
    
    
    def add_category(self, category, label=""):
        """ Adds a component category category to this component map """
        if category in self._categories:
            raise KeyError
        
        result = ComponentMap.Category(label)
        self._categories[category] = result
        return result
    
    
    class Category:
        def __init__(self, label=""):
            self._components = OrderedDict()
            self.label = label
        
        
        def __getitem__(self, codename):
            """ Gets a component with the specified codename """
            return self._components[codename]
        
        
        def __iter__(self):
            """ Returns an iterator for all components under this category """
            yield from self._components.values()
        
        
        def __len__(self):
            """ Returns the number of compoenents in this category """
            return len(self._components)
        
        
        def add(self, component):
            """ Adds a component to this category """
            if component.codename in self._components:
                raise KeyError
                
            self._components[component.codename] = component


from gi.repository import GObject
class LayoutOption(Component, GObject.Object):
    ''' Represents a layout choice. '''
    
    def __init__(self, codename=""):
        ''' codename must be a string identifier for this option
            name is a localized label for the layout
            description is a description, duh '''
        
        Component.__init__(self, codename)
        GObject.Object.__init__(self)
        
        # Set this value to true if the layout has a settings dialog
        self.has_settings_widget = False
        self.has_menu_items = False
    
    
    @GObject.Property
    def label(self):
        """A label for the UI"""
        raise NotImplementedError
    
    @GObject.Property
    def description(self):
        """A description for the UI"""
        raise NotImplementedError
    
    
    def create_layout(self, app):
        """Creates a layout that this option represents"""
        raise NotImplementedError
    
    
    def save_preferences(self, layout):
        """Save the preferences for this layout option based on a layout"""
        pass
        
        
    def create_settings_widget(self, layout):
        """Creates a settings widget for a layout instance"""
        raise NotImplementedError
    
    
    def get_action_group(self, layout):
        """Returns a Gtk.ActionGroup for a layout
        
        This is only called if .has_menu_items is set to True
        
        """
        raise NotImplementedError
    
    def add_ui(self, layout, uimanager, merge_id):
        """ Adds ui into an uimanager using the specified merge_id.
        
        This is only called if .has_menu_items is set to True, in which
        case the action group is added automatically by the ViewerWindow.
        
        """
        raise NotImplementedError


class MouseHandlerFactory(Component, GObject.Object):
    """Manufacturates a certain kind of mousing.MouseHandler"""
    
    def __init__(self, codename=""):
        Component.__init__(self, codename)
        GObject.Object.__init__(self)
    
    
    def produce(self, settings=None):
        if settings:
            product = self.load_settings(settings)
        else:
            product = self.create_default()
            
        product.factory = self
        return product
    
    
    @GObject.Property
    def label(self):
        """A label for the UI"""
        raise NotImplementedError
    
    
    def create_default(self):
        ''' This should create a mouse handler with default attributes '''
        
        raise NotImplementedError
        
        
    def create_settings_widget(self, handler):
        ''' Creates a widget for configuring a mouse handler '''
        
        raise NotImplementedError
    
    
    def get_settings(handler):
        ''' Returns an object representing a handler configuration '''
        
        return None
    
    def load_settings(settings):
        ''' Creates a mouse handler with the settings input '''
        
        raise NotImplementedError
