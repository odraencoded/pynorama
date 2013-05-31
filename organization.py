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
		
	def __getitem__(self, item):
		return self._store[item]
		
	def __setitem__(self, item, value):
		self._store[item] = value
		
	def __delitem__(self, item):
		if isinstance(item, slice):
			indices = item.indices(len(self._store))
			removed_indices = []
			for i in range(*indices):
				if item.step and item.step < 0:
					removed_indices.append(i)
				else:
					removed_indices.append(i - len(removed_indices))
					
			removed_images = self._store[item]
			del self._store[item]
			
			for i in range(len(removed_indices)):
				image, index = removed_images[i], removed_indices[i]
				self.emit("image-removed", image, index)
		else:
			image = self._store.pop(item)
			self.emit("image-removed", image, item)
	
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
		
		if self.sort_list(self._store):
			self.emit("order-changed")
	
	def sort_list(self, a_list):
		if self.comparer and len(a_list) > 1:
			a_list.sort(key=self.comparer, reverse=self.reverse)
			return True
			
		else:
			return False
	
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
		
			for i in range(1, 1 + forward):
				result.append(self._store[(start + i) % count])
			
			for i in range(1, 1 + backwards):
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
		
class SortingKeys:
	''' Contains functions to get keys in images for sorting them '''
	
	@staticmethod
	def ByName(image):
		return GLib.utf8_collate_key_for_filename(image.fullname, -1)
		
	@staticmethod
	def ByCharacters(image):
		return image.fullname.lower()
			
	@staticmethod
	def ByFileSize(image):
		return image.get_metadata().data_size
		
	@staticmethod
	def ByFileDate(image):
		return image.get_metadata().modification_date
		
	@staticmethod
	def ByImageSize(image):
		return image.get_metadata().get_area()
		
	@staticmethod
	def ByImageWidth(image):
		return image.get_metadata().width
		
	@staticmethod
	def ByImageHeight(image):
		return image.get_metadata().height

from gi.repository import Gtk
import viewing

class AlbumViewLayout(GObject.Object):
	''' Used to tell layouts the album used for a view
	    Layouts should store data in this thing
	    Just call this avl for short '''
    
	__gsignals__ = {
		"focus-changed" : (GObject.SIGNAL_RUN_FIRST, None, [object])
	}
    
	def __init__(self, album, view, layout):
		GObject.Object.__init__(self)
		self.__is_clean = True
		self.__old_view = self.__old_album = self.__old_layout = None
		
		self.connect("notify::layout", self._layout_changed)
		
		self.layout = layout
		self.album = album
		self.view = view
	
	@property	
	def focus_image(self):
		return self.layout.get_focus_image(self)
	
	@property
	def focus_frame(self):
		return self.layout.get_focus_frame(self)
	
	def go_index(self, index):
		self.layout.go_image(self, self.album[index])
		
	def go_image(self, image):
		self.layout.go_image(self, image)
	
	def go_next(self):
		self.layout.go_next(self)
	
	def go_previous(self):
		self.layout.go_previous(self)
	
	def clean(self):
		if not self.__is_clean:
			self.__old_layout.clean(self)
			self.__is_clean = True
	
	def _layout_changed(self, *data):
		if self.__old_layout:
			self.clean()
		
		self.__old_layout = self.layout
		if self.layout:
			self.__is_clean = False
			self.layout.start(self)
		
	album = GObject.property(type=object, default=None)
	view = GObject.property(type=object, default=None)
	layout = GObject.property(type=object, default=None)
	
class AlbumLayout:
	''' Layout for an album '''
	def __init__(self):
		pass
	
	def get_focus_image(self, avl):
		''' Returns the image in focus '''
		raise NotImplementedError
	
	def get_focus_frame(self, avl):
		''' Returns the frame in focus '''
		raise NotImplementedError
				
	def go_image(self, avl, image):
		''' Lays out an image '''
		raise NotImplementedError
	
	def go_next(self, avl):
		focus = avl.focus_image
		next_image = avl.album.next(focus)
		avl.go_image(next_image)
	
	def go_previous(self, avl):
		focus = avl.focus_image
		previous_image = avl.album.previous(focus)
		avl.go_image(previous_image)		
		
	def start(self, avl):
		''' Set any initial variables in an AlbumViewLayout '''
		pass
		
	def clean(self, avl):
		''' Reverse whatever was done at start '''
		pass
	
	def update_setup(self, avl):
		pass
		
class SingleFrameLayout(AlbumLayout):
	''' Shows a single album image in a view '''
	def __init__(self):
		pass
	
	def start(self, avl):
		avl.current_image = None
		avl.current_frame = None
		avl.load_handle = None
		avl.old_album = None
		avl.removed_signal_id = None
		avl.album_notify_id = avl.connect(
		                          "notify::album", self._album_changed, avl)
		self._album_changed(avl)
		
	def clean(self, avl):
		if avl.load_handle:
			avl.current_image.disconnect(avl.load_handle)
		del avl.load_handle
		
		if avl.current_image:
			avl.current_image.uses -= 1
		del avl.current_image
		
		if avl.current_frame:
			avl.view.remove_frame(avl.current_frame)
		del avl.current_frame
		
		avl.disconnect(avl.album_notify_id)
		del avl.album_notify_id
		
		if not avl.old_album is None:
			avl.old_album.disconnect(avl.removed_signal_id)
			
		del avl.old_album
		del avl.removed_signal_id
			
	def get_focus_image(self, avl):
		return avl.current_image
	
	def get_focus_frame(self, avl):
		return avl.current_frame
	
	def go_image(self, avl, target_image):
		if avl.current_image == target_image:
			pass
			
		previous_image = avl.current_image
		avl.current_image = target_image
		
		if previous_image:
			previous_image.uses -= 1 # decrement use count
			if avl.load_handle: # remove "finished-loading" handle
				previous_image.disconnect(avl.load_handle)
				avl.load_handle = None
				
		if target_image is None:
			# Current image being none means nothing is displayed #
			self._refresh_frame(avl)
			
		else:
			target_image.uses += 1
			if target_image.on_memory or target_image.is_bad:
				self._refresh_frame(avl)
				
			else:
				avl.load_handle = avl.current_image.connect(
				                  "finished-loading", self._image_loaded, avl)
		
		avl.emit("focus-changed", avl.current_image)
		
	def _refresh_frame(self, avl):
		if avl.current_frame:
			avl.view.remove_frame(avl.current_frame)
			
		if avl.current_image:
			try:
				new_frame = avl.current_image.create_frame(avl.view)
				
			except Exception:
				new_frame = None
				
			finally:				
				if new_frame is None:
					# Create a missing icon frame #
					error_icon = avl.view.render_icon(Gtk.STOCK_MISSING_IMAGE,
						                              Gtk.IconSize.DIALOG)
						                            
					error_surface = viewing.SurfaceFromPixbuf(error_icon)
					new_frame = viewing.ImageSurfaceFrame(error_surface)
					
			avl.current_frame = new_frame
			avl.view.add_frame(new_frame)
	
	def _album_changed(self, avl, *data):
		if not avl.old_album is None:
			avl.old_album.disconnect(avl.removed_signal_id)
			avl.removed_signal_id = None
		
		avl.old_album = avl.album
		if not avl.album is None:
			avl.removed_signal_id = avl.album.connect(
			                        "image-removed", self._image_removed, avl)
			                        
	def _image_added(self, album, image, index, avl):
		pass
	
	def _image_removed(self, album, image, index, avl):
		if image == avl.current_image:
			count = len(album)
			if index <= count:
				if count >= 1:
					new_index = index - 1 if index == count else index
					new_image = album[new_index]
				else:
					new_image = None
					
				self.go_image(avl, new_image)
	
	def _image_loaded(self, image, error, avl):
		self._refresh_frame(avl)
