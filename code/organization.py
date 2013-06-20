# coding=utf-8

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
import utility

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
from gettext import gettext as _
import point, viewing

class AlbumViewLayout(GObject.Object):
	''' Used to tell layouts the album used for a view
	    Layouts should store data in this thing
	    Just call this avl for short '''
    
	__gsignals__ = {
		"focus-changed" : (GObject.SIGNAL_RUN_FIRST, None, [object, bool])
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
			self.__old_layout.unsubscribe(self)
			self.clean()
		
		self.__old_layout = self.layout
		if self.layout:
			self.__is_clean = False
			self.layout.start(self)
			self.layout.subscribe(self)
		
	album = GObject.property(type=object, default=None)
	view = GObject.property(type=object, default=None)
	layout = GObject.property(type=object, default=None)
	
class AlbumLayout:
	''' Places images from an album into a view '''
	def __init__(self):
		self.__subscribers = set()
		
		self.refresh_subscribers = utility.IdlyMethod(self.refresh_subscribers)
		self.refresh_subscribers.priority = GLib.PRIORITY_HIGH + 20
		
		# Set this value to true if the layout has a settings dialog
		self.has_settings_widget = False
		
	def subscribe(self, avl):
		self.__subscribers.add(avl)
		
	def unsubscribe(self, avl):
		self.__subscribers.discard(avl)
		
	def refresh_subscribers(self):
		''' Layouts should call this or queue_refresh for
		    propagating changes in the layout properites '''
		    
		for avl in self.__subscribers:
			self.update(avl)	
	
	#~ Interface down this line ~#
	
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
	
	def update(self, avl):
		''' Propagate changes in a layout property to an avl '''
		pass
		
	def create_settings_widget(self):
		''' Creates a widget for configuring the layout '''
		raise TypeError
		
class SingleImageLayout(AlbumLayout):
	''' Places a single album image in a view '''
	
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
		
		avl.emit("focus-changed", avl.current_image, False)
		
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

class LayoutDirection:
	Left = "left"
	Right = "right"
	Up = "up"
	Down = "down"
	
class ImageStripLayout(GObject.Object, AlbumLayout):
	''' Places a strip of album images, laid side by side, in a view '''
	
	def __init__(self, direction=LayoutDirection.Down,
	                   loop=False, repeat=False, alignment=0,
	                   margin=(0, 0), space=(2560, 3840), limit=(40, 60)):
		GObject.Object.__init__(self)
		AlbumLayout.__init__(self)
		self.has_settings_dialog = True
		
		self.connect("notify::direction", self._direction_changed)
		self.connect("notify::repeat", self._placement_args_changed)
		self.connect("notify::loop", self._placement_args_changed)
		self.connect("notify::space-before", self._placement_args_changed)
		self.connect("notify::space-after", self._placement_args_changed)
		self.connect("notify::limit-before", self._placement_args_changed)
		self.connect("notify::limit-after", self._placement_args_changed)
		self.connect("notify::margin-before", self._placement_args_changed)
		self.connect("notify::margin-after", self._placement_args_changed)
		self.connect("notify::alignment", self._placement_args_changed)
		
		self.direction = direction
		
		self.loop = loop
		self.repeat = repeat
		self.alignment = alignment
		
		self.margin_before, self.margin_after = margin
		self.space_before, self.space_after = space
		self.limit_before, self.limit_after = limit
		
	def create_settings_widget(self):
		return ImageStripLayout.SettingsWidget(self)
		
	def update(self, avl):
		self._update_sides(avl)		
		self._reposition_frames(avl)
		
	def start(self, avl):
		avl.center_index = avl.center_frame = avl.center_image = None
		avl.shown_images, avl.shown_frames = [], []
		avl.space_before = avl.space_after = 0
		avl.load_handles = {}
		
		avl.old_view = avl.old_album = None
		
		# Use PRIORITY_DEFAULT_IDLE - 10 to create frames after they
		# are drawn but before they can be unloaded (avoiding having to reload
		# images after a _clear_images(...)		
		avl.update_sides = utility.IdlyMethod(self._update_sides, avl)
		avl.update_sides.priority = GLib.PRIORITY_DEFAULT_IDLE - 10
		
		avl.album_signals = []
		avl.view_signals = []
		avl.notify_signals = [
			avl.connect("notify::album", self._album_changed, avl),
			avl.connect("notify::view", self._view_changed, avl)
		]
		self._view_changed(avl)
		self._album_changed(avl)
		
	def clean(self, avl):
		for an_image in avl.shown_images:
			an_image.uses -= 1
			
		for a_frame in avl.shown_frames:
			if a_frame:
				avl.view.remove_frame(a_frame)
				
		for an_image, a_handle_id in avl.load_handles.items():
			an_image.disconnect(a_handle_id)				
		
		del avl.center_image, avl.center_frame
		del avl.shown_images, avl.shown_frames
		del avl.space_before, avl.space_after
		del avl.load_handles
		
		for signal_id in avl.notify_signals:
			avl.disconnect(signal_id)
			
		if avl.old_album is not None:
			for signal_id in avl.album_signals:
				avl.old_album.disconnect(signal_id)
		
		if avl.old_view is not None:
			for signal_id in avl.view_signals:
				avl.old_view.disconnect(signal_id)			
		
		avl.update_sides.cancel_queue()
		del avl.update_sides
		
		del avl.old_album, avl.old_view
		del avl.notify_signals
		del avl.album_signals, avl.view_signals
			
	def get_focus_image(self, avl):
		return avl.center_image
	
	def get_focus_frame(self, avl):
		return avl.center_frame
		
	def go_next(self, avl):
		if avl.center_frame:
			new_index = avl.center_index + 1
			if new_index < len(avl.shown_images):
				avl.center_image = avl.shown_images[new_index]
				avl.center_frame = avl.shown_frames[new_index]
				avl.center_index = new_index
				avl.emit("focus-changed", avl.center_image, False)
				
			else:
				new_image = avl.album.next(avl.center_image)
				if not self.loop and new_image is avl.album[0]:
					self._clear_images(avl)
					new_index = 0
					
				avl.center_index = avl.center_frame = avl.center_image = None
				
				self._insert_image(avl, new_index, new_image)
				
			avl.update_sides.queue()
		
	def go_previous(self, avl):
		if avl.center_frame:
			new_index = avl.center_index - 1
			if new_index >= 0:
				avl.center_image = avl.shown_images[new_index]
				avl.center_frame = avl.shown_frames[new_index]
				avl.center_index = new_index
				avl.emit("focus-changed", avl.center_image, False)
				
			else:
				new_image = avl.album.previous(avl.center_image)
				if not self.loop and new_image is avl.album[-1]:
					self._clear_images(avl)
				
				avl.center_index = avl.center_frame = avl.center_image = None
				
				self._insert_image(avl, 0, new_image)
				
			avl.update_sides.queue()
			
	def go_image(self, avl, image):
		if avl.center_image is image:
			return
			
		self._clear_images(avl)
		avl.center_index = avl.center_image = avl.center_frame = None
		self._insert_image(avl, 0, image)
	
	#-- Properties down this line --#
	
	''' What direction a fore image should be in relation to a hind image...
	    or something like that '''
	direction = GObject.property(type=str, default="down")
	
	''' Whether to continue laying images to a side after finding
	    the center image on that side '''
	repeat = GObject.property(type=bool, default=False)
	
	''' Whether to add the last image of an album before the first image and
	    vice versa '''
	loop = GObject.property(type=bool, default=False)
	
	''' Alignment for the parallel axis, 0.5..0.5 = left/right or top/bottom '''
	alignment = GObject.property(type=float, default=0)
	
	''' Distance between two adjacent images '''
	margin_after = GObject.property(type=int, default=0)
	margin_before = GObject.property(type=int, default=0)
	
	''' Target for the number of pixels before or after the center image.
	    The space will be at least these values except when a limit is hit '''	
	space_before = GObject.property(type=int, default=2560)
	space_after = GObject.property(type=int, default=3840)
	
	''' Limit for the number of images placed after
	    and before the center image '''
	limit_before = GObject.property(type=int, default=40)
	limit_after = GObject.property(type=int, default=60)
	
	#-- Implementation detail down this line --#
	
	def _direction_changed(self, *data):
		self._get_length, self._get_rect_distance, \
		     self._place_before, self._place_after = \
		          ImageStripLayout.DirectionMethods[self.direction]
		
		self.refresh_subscribers.queue()
	
	def _placement_args_changed(self, *data):
		self.refresh_subscribers.queue()
	
	def _view_changed(self, avl, *data):
		# Handler for album changes in avl
		if avl.old_view is not None:
			for signal_id in avl.view_signals:
				avl.old_view.disconnect(signal_id)
				
			avl.view_signals = None
			
		avl.old_view = avl.view
		if avl.view is not None:
			avl.view_signals = [
				avl.view.connect("offset-change", self._offset_change, avl),
			]
				
	def _album_changed(self, avl, *data):
		# Handler for album changes in avl
		if avl.old_album is not None:
			for signal_id in avl.album_signals:
				avl.old_album.disconnect(signal_id)
				
			avl.album_signals = None
			
		avl.old_album = avl.album
		if avl.album is not None:
			avl.album_signals = [
				avl.album.connect("image-removed", self._image_removed, avl),
				avl.album.connect("image-added", self._image_added, avl),
				avl.album.connect("order-changed", self._order_changed, avl),
			]
			
	def _offset_change(self, view, avl, *data):
		if avl.center_frame and not view.frames_fit:
			w, h = avl.view.get_widget_size()
			tl = avl.view.get_absolute_point((0, 0))
			tr = avl.view.get_absolute_point((w, 0))
			bl = avl.view.get_absolute_point((0, h))
			br = avl.view.get_absolute_point((w, h))
			absolute_view_rect = point.Rectangle.FromPoints(tl, tr, bl, br)
			
			current_index = avl.center_index
			current_distance = None
			frame_distances = []
			margin_before, margin_after = self.margin_before, self.margin_after
			for i in range(len(avl.shown_frames)):
				a_frame = avl.shown_frames[i]
				if a_frame:
					a_rect = a_frame.rectangle.shift(a_frame.origin)
					
					if absolute_view_rect.overlaps_with(a_rect):
						margin = 0 if i == current_index \
						           else -margin_before if i > current_index \
						           else margin_after
						           
						a_distance = self._get_rect_distance(margin,
						                  absolute_view_rect, a_rect)
						
						if i == current_index:
							current_distance = a_distance
							
						frame_distances.append((i, a_distance))
			
			if frame_distances:
				best_index, best_distance = min(frame_distances,
				                                key=lambda v: v[1])
				                            
				if current_distance is None or best_distance < current_distance:
					best_image = avl.shown_images[best_index]
					best_frame = avl.shown_frames[best_index]
			
					if avl.center_image is not best_image:
						avl.center_index = best_index			
						avl.center_image = best_image
						avl.center_frame = best_frame
				
						avl.update_sides.queue()
						avl.emit("focus-changed", best_image, True)
					
	def _image_added(self, album, image, index, avl):
		# Handles an iamge added to an album
		next = album.next(image)
		prev = album.previous(image)
		
		if prev is image or prev is next:
			prev = None
			
		if next is image:
			next = None
			
		if prev or next:
			change = 0
			inserted_prev = False
			for i in range(len(avl.shown_images)):
				j = i + change
				an_image = avl.shown_images[j]
				if an_image is next and not inserted_prev:
					self._insert_image(avl, j, image)
					change += 1
					inserted_prev = False
					
				elif an_image is prev:
					self._insert_image(avl, j + 1, image)
					change += 1
					inserted_prev = True
					
				else:
					inserted_prev = False
					
	def _image_removed(self, album, image, index, avl):
		# Handles an image removed from an album
		removed_frame = False
		while image in avl.shown_images:
			removed_index = avl.shown_images.index(image)
			self._remove_image(avl, removed_index)
			removed_frame = True
				
		if removed_frame:
			if image is avl.center_image:
				new_index = avl.center_index
				if new_index < len(avl.shown_images):
					avl.center_image = avl.shown_images[new_index]
					avl.center_frame = avl.shown_frames[new_index]
					avl.center_index = new_index
					avl.emit("focus-changed", avl.center_image, True)
			
				else:
					avl.center_index = None
					avl.center_frame = avl.center_image = None
					if avl.album:
						new_image = avl.album.next(avl.album[index - 1])
						self._insert_image(avl, new_index, new_image)
			
			avl.update_sides.queue()
			self._reposition_frames(avl)
	
	def _order_changed(self, album, avl):
		self._clear_images(avl)
		old_center_image = avl.center_image
		avl.center_index = avl.center_image = avl.center_frame = None
		self._insert_image(avl, 0, old_center_image)
	
	def _insert_image(self, avl, index, image):
		''' Handles a image inserted in an album '''
		avl.shown_images.insert(index, image)
		avl.shown_frames.insert(index, None)
		
		image.uses += 1
		
		if not avl.center_image:
			# If there is no center image, set it to the newly inserted one
			avl.center_index = index
			avl.center_image = image
			
			self._load_frame(avl, image)
			avl.emit("focus-changed", image, False)
		else:
			if index <= avl.center_index:
				# Increment the center index because a frame was added before it
				avl.center_index += 1
				
			self._load_frame(avl, image)
			
	def _remove_image(self, avl, index):
		''' Handles a image removed from an album '''
		image = avl.shown_images.pop(index)
		frame = avl.shown_frames.pop(index)
		
		image.uses -= 1
		
		if frame: # Remove frame from view
			avl.view.remove_frame(frame)
		
		if image not in avl.shown_images:
			# If the image is no longer shown, remove the loading handler
			load_handle_id = avl.load_handles.pop(image, None)
			if load_handle_id:
				image.disconnect(load_handle_id)
		
		if avl.center_image and index < avl.center_index:
			# Decrement the center index because a frame was removed before it
			avl.center_index -= 1
	
	def _append_image(self, avl, image):
		self._insert_image(avl, len(avl.shown_images), image)
		
	def _prepend_image(self, avl, image):
		self._insert_image(avl, 0, image)
	
	def _clear_images(self, avl):
		while avl.shown_images:
			self._remove_image(avl, 0)
			
	def _load_frame(self, avl, image):
		if image.on_memory or image.is_bad:
			self._refresh_frames(avl, image)
			avl.update_sides.queue()
			
		else:
			load_handle_id = avl.load_handles.get(image, None)
			if not load_handle_id:
				load_handle_id = image.connect("finished-loading", 
				                               self._image_loaded, avl)
				avl.load_handles[image] = load_handle_id
				
	def _image_loaded(self, image, error, avl):
		load_handle_id = avl.load_handles.pop(image, None)
		if load_handle_id:
			image.disconnect(load_handle_id)
			
		if image in avl.shown_images:
			self._refresh_frames(avl, image)
			avl.update_sides.queue()
	
	def _update_sides(self, avl):
		# Adds or removes images at either side
		if avl.center_frame:
			# Cache some properties
			margin_before, margin_after = self.margin_before, self.margin_after
			space_before, space_after = self.space_before, self.space_after
			limit_before, limit_after = self.limit_before, self.limit_after
			loop, repeat = self.loop, self.repeat
			
			center_image = avl.center_image
			shown_frames, shown_images = avl.shown_frames, avl.shown_images
			album = avl.album
			
			if not loop:
				first_image = album[0]
				for i in range(avl.center_index, 0, -1):
					if shown_images[i] is first_image:
						for j in range(i):
							self._remove_image(avl, 0)
							
						break
						
				last_image = album[-1]
				for i in range(avl.center_index, len(shown_images)):
					if shown_images[i] is last_image:
						for j in range(len(shown_images) - i - 1):
							self._remove_image(avl, i + 1)
							
						break
						
			elif not repeat:
				# Removes the center image from around the center frame
				for i in range(avl.center_index -1, -1, -1):
					if shown_images[i] is center_image:
						for j in range(i + 1):
							self._remove_image(avl, 0)
							
						break
						
				for i in range(avl.center_index + 1, len(shown_images)):
					if shown_images[i] is center_image:
						for j in range(len(shown_images) - i):
							self._remove_image(avl, i)
							
						break
			
			self._compute_lengths(avl)
			
			before_count = avl.center_index
			after_count = len(shown_images) - avl.center_index - 1
						
			if after_count > limit_after:
				# Remove images after center image
				# if the count is over the limit
				for i in range(after_count - limit_after):
					a_length = self._get_length(shown_frames[-1])
					avl.space_after -= a_length + margin_after
					self._remove_image(avl, len(shown_frames) -1)
				
				after_count = limit_after
			
			if after_count < limit_after:
				foremost_frame = shown_frames[-1]
				# Add an image if there is extra space
				if avl.space_after < space_after:
					if foremost_frame:
						foremost_image = shown_images[-1]
						new_image = album.next(foremost_image)
						
						valid_insert = True
						if not repeat:
							valid_insert = new_image is not center_image
						
						if valid_insert and not loop:
							valid_insert = new_image is not album[0]
							
						if valid_insert:
							self._append_image(avl, new_image)
						
				else:
					# Remove images if there is no extra space
					foremost_length = self._get_length(foremost_frame)
					foremost_length += margin_after
					while avl.space_after - foremost_length > \
						  space_after if foremost_frame \
						  else avl.space_after > space_after:
						self._remove_image(avl, len(shown_frames) -1)
						avl.space_after -= foremost_length
						foremost_frame = shown_frames[-1]
						foremost_length = self._get_length(foremost_frame)
						foremost_length += margin_after
					
			if before_count > self.limit_before:
				# Remove images before center image
				# if the count is over the limit
				for i in range(before_count - limit_before):
					a_length = self._get_length(shown_frames[0])
					avl.space_before -= a_length + margin_before
					self._remove_image(avl, 0)
					
				before_count = self.limit_before
				
			if	before_count < limit_before:
				backmost_frame = shown_frames[0]
				# Add an image if there is extra space
				if avl.space_before < space_before:	
					if backmost_frame:
						backmost_image = shown_images[0]
						new_image = album.previous(backmost_image)
						
						valid_insert = True
						if not repeat:
							valid_insert = new_image is not center_image
						
						if valid_insert and not loop:
							valid_insert = new_image is not album[-1]
							
						if valid_insert:
							self._prepend_image(avl, new_image)
							
				else:
					# Remove images if there is no extra space
					backmost_length = self._get_length(backmost_frame)
					backmost_length += margin_before
					while avl.space_before - backmost_length > \
					      space_before if backmost_frame \
						  else avl.space_before > space_before:
						self._remove_image(avl, 0)
						avl.space_before -= backmost_length
						backmost_frame = shown_frames[0]
						backmost_length = self._get_length(backmost_frame)
						backmost_length += margin_before
						
	def _refresh_frames(self, avl, image, overwrite=False):
		# Create frames to represent an image
		error_surface = None
		new_frames = []
		for i in range(len(avl.shown_images)):
			shown_image = avl.shown_images[i]
			if image is shown_image:
				shown_frame = avl.shown_frames[i]
				if not shown_frame or overwrite:
					try:
						shown_frame = image.create_frame(avl.view)
						
					except Exception:
						if not error_surface:
							pixbuf = avl.view.render_icon(
							                 Gtk.STOCK_MISSING_IMAGE,
							                 Gtk.IconSize.DIALOG)
							                 
							error_surface = viewing.SurfaceFromPixbuf(pixbuf)
							
						shown_frame = viewing.ImageSurfaceFrame(error_surface)
					
					self._set_frame(avl, i, shown_frame)
					new_frames.append(shown_frame)
					
		if new_frames:
			if image is avl.center_image and not avl.center_frame:
				avl.center_frame = new_frames[0]
			
			self._reposition_frames(avl)
		
	def _set_frame(self, avl, index, new_frame):
		old_frame = avl.shown_frames[index]
		if new_frame is not old_frame:
			if old_frame:
				avl.view.remove_frame(old_frame)
			
			avl.shown_frames[index] = new_frame
			if new_frame:
				avl.view.add_frame(new_frame)
	
	def _reposition_frames(self, avl):
		''' Place the frames of images around the center image 
		    around the center frame '''
		    
		if avl.center_frame:
			shown_frames = avl.shown_frames
			frame_count = len(shown_frames)
			placement_data = (
				(self._place_before, self.margin_before,
				 range(avl.center_index, -1, -1)),
				 
				(self._place_after, self.margin_after,
				 range(avl.center_index, frame_count))
			)
			
			for a_coordinator, a_margin, a_range in placement_data:
				self._place_frames(a_coordinator, a_margin,
				                   (shown_frames[j] for j in a_range))
				
	def _compute_lengths(self, avl):
		''' Recalculate the space used by frames around the center frame '''
		if avl.center_frame:
			side_ranges = (range(avl.center_index),
			               range(avl.center_index + 1, len(avl.shown_frames)))
			margins = [self.margin_before, self.margin_after]
			side_lengths = []
			
			for i in range(2):
				a_margin, a_side_range = margins[i], side_ranges[i]
				a_side_length = 0
				for j in a_side_range:
					a_frame = avl.shown_frames[j]
					if a_frame:
						a_side_length += self._get_length(a_frame) + a_margin
				
				side_lengths.append(a_side_length)
				
			avl.space_before, avl.space_after = side_lengths
			
		else:
			avl.space_after = 0
			avl.space_before = 0
	
	def _place_frames(self, coordinate_modifier, margin, frames):
		''' Places a list of frames side by side '''
		previous_rect = None
		alignment = self.alignment
		for a_frame in frames:
			if a_frame:
				frame_rect = a_frame.rectangle
				ox, oy = a_frame.origin
				if previous_rect:
					ox, oy = coordinate_modifier(alignment, margin,
					                             previous_rect, frame_rect)
					a_frame.origin = ox, oy
					
				previous_rect = frame_rect.shift((ox, oy))
				previous_rect.ox, previous_rect.oy = ox, oy
				
	# lambda args are
	# alignment, margin, previous translated rectangle, current rectangle
	_CoordinateToRight = \
	lambda a, m, p, r: (p.right - r.left + m, p.oy + (p.height - r.height) * a)
	
	_CoordinateToLeft = \
	lambda a, m, p, r: (p.left - r.right - m, p.oy + (p.height - r.height) * a)
	
	_CoordinateToTop = \
	lambda a, m, p, r: (p.ox + (p.width - r.width) * a, p.top - r.bottom - m)
	
	_CoordinateToBottom = \
	lambda a, m, p, r: (p.ox + (p.width - r.width) * a, p.bottom - r.top + m)
	                      
	_GetFrameWidth = lambda f: f.rectangle.width if f else 0
	_GetFrameHeight = lambda f: f.rectangle.height if f else 0
	
	def _GetHorizontalRectDistance(offset, view_rect, rect):
		center = view_rect.left + view_rect.width / 2 + offset
		dist_a = abs(rect.left - center)
		dist_b = abs(rect.left + rect.width - center)
		return dist_a + dist_b
		
	def _GetVerticalRectDistance(offset, view_rect, rect):
		center = view_rect.top + view_rect.height / 2 + offset
		dist_a = abs(rect.top - center)
		dist_b = abs(rect.top + rect.height - center)
		return dist_a + dist_b
			
	DirectionMethods = {
		LayoutDirection.Right : (_GetFrameWidth, _GetHorizontalRectDistance,
		                         _CoordinateToLeft, _CoordinateToRight),
		LayoutDirection.Left : (_GetFrameWidth, _GetHorizontalRectDistance,
		                        _CoordinateToRight, _CoordinateToLeft),
		LayoutDirection.Up : (_GetFrameHeight, _GetVerticalRectDistance,
		                      _CoordinateToBottom, _CoordinateToTop),
		LayoutDirection.Down : (_GetFrameHeight, _GetVerticalRectDistance,
		                        _CoordinateToTop, _CoordinateToBottom)
	}
	
	class SettingsWidget(Gtk.Notebook):
		''' A widget for configuring a ImageStripLayout '''
		def __init__(self, layout):
			Gtk.Notebook.__init__(self)
			
			self.layout = layout	
			line_args = {
				"orientation": Gtk.Orientation.HORIZONTAL,
				"spacing": 24
			}
						
			#-- Create direction widgets --#
			label = _("Image strip direction")
			direction_label = Gtk.Label(label)
			direction_tooltip = _('''\
The images that come after the center image are placed \
towards this direction''')
			
			direction_model = Gtk.ListStore(str, str)
			
			direction_model.append([LayoutDirection.Up, _("Up")])
			direction_model.append([LayoutDirection.Right, _("Right")])
			direction_model.append([LayoutDirection.Down, _("Down")])
			direction_model.append([LayoutDirection.Left, _("Left")])
			
			#-- Create combobox --#
			direction_selector = Gtk.ComboBox.new_with_model(direction_model)
			direction_selector.set_id_column(0)
			direction_selector.set_tooltip_text(direction_tooltip)
			
			#-- Add text renderer --#
			text_renderer = Gtk.CellRendererText()
			direction_selector.pack_start(text_renderer, True)
			direction_selector.add_attribute(text_renderer, "text", 1)
			
			#-- Alignment --#
			label = _("Alignment")
			
			alignment_label = Gtk.Label(label)
			alignment_adjust = Gtk.Adjustment(0, -.5, .5, .1, .25)
			alignment_scale = Gtk.Scale(adjustment=alignment_adjust)
			alignment_scale.set_draw_value(False)
			
			#-- Loop checkbox --#
			label = _("Loop around the album")
			loop_tooltip = _('''\
Place the first image of an album after the last, and vice versa''')
			loop_button = Gtk.CheckButton.new_with_label(label)
			loop_button.set_tooltip_text(loop_tooltip)
			
			#-- Repeat checkbox --#
			label = _("Repeat the album images")
			repeat_tooltip = _('''\
In albums with few, small images, repeat those images indefinetely''')
			repeat_button = Gtk.CheckButton.new_with_label(label)
			repeat_button.set_tooltip_text(repeat_tooltip)
			
			#-- Pixel margin --#
			margin_tooltip = _('''Margin means distance''')

			label = _("Margin between images before center")
			margin_before_label = Gtk.Label(label)
			margin_before_adjust = Gtk.Adjustment(0, 0, 512, 8, 64)
			margin_before_entry = Gtk.SpinButton(
			                          adjustment=margin_before_adjust)
			margin_before_entry.set_tooltip_text(margin_tooltip)
			
			label = _("Margin between images after center")
			margin_after_label = Gtk.Label(label)
			margin_after_adjust = Gtk.Adjustment(0, 0, 512, 8, 64)
			margin_after_entry = Gtk.SpinButton(adjustment=margin_after_adjust)
			margin_after_entry.set_tooltip_text(margin_tooltip)
			
			#-- Performance stuff --#
			label = _('''\
These settings affect how many images are laid out at the same time.
If you are having performance problems, consider decreasing these values.''')
			performance_label = Gtk.Label(label)
						
			#-- Pixel target --#
			space_tooltip = _('''A good value is around twice your \
screen height or width, depending on the strip direction''')

			label = _("Pixels to fill before center")
			space_before_label = Gtk.Label(label)
			space_before_adjust = Gtk.Adjustment(0, 0, 8192, 32, 256)
			space_before_entry = Gtk.SpinButton(adjustment=space_before_adjust)
			space_before_entry.set_tooltip_text(space_tooltip)
			
			label = _("Pixels to fill after center")
			space_after_label = Gtk.Label(label)
			space_after_adjust = Gtk.Adjustment(0, 0, 8192, 32, 256)
			space_after_entry = Gtk.SpinButton(adjustment=space_after_adjust)
			space_after_entry.set_tooltip_text(space_tooltip)
			
			# Count limits
			limits_tooltip = _('''\
This is only useful if the images being laid out \
are too small to breach the pixel count limit''')
						
			label = _("Image limit before center")
			limit_before_label = Gtk.Label(label)
			limit_before_adjust = Gtk.Adjustment(0, 0, 512, 1, 10)
			limit_before_entry = Gtk.SpinButton(adjustment=limit_before_adjust)
			limit_before_entry.set_tooltip_text(limits_tooltip)
			
			label = _("Image limit after center")
			limit_after_label = Gtk.Label(label)
			limit_after_adjust = Gtk.Adjustment(0, 0, 512, 1, 10)
			limit_after_entry = Gtk.SpinButton(adjustment=limit_after_adjust)
			limit_after_entry.set_tooltip_text(limits_tooltip)
			
			# Bind properties
			direction_selector.connect("changed",
			                           self._refresh_marks, alignment_scale)
			binding_flags = GObject.BindingFlags
			flags = binding_flags.BIDIRECTIONAL | binding_flags.SYNC_CREATE
			self.layout.bind_property("direction", direction_selector,
			                          "active-id", flags)
			                          
			self.layout.bind_property("alignment", alignment_adjust,
			                          "value", flags)
			                          
			self.layout.bind_property("loop", loop_button,
			                          "active", flags)
			
			self.layout.bind_property("repeat", repeat_button,
			                          "active", flags)
			                          
			self.layout.bind_property("margin-before", margin_before_adjust,
			                          "value", flags)
			self.layout.bind_property("margin-after", margin_after_adjust,
			                          "value", flags)
			                          			
			self.layout.bind_property("limit-before", limit_before_adjust,
			                          "value", flags)
			self.layout.bind_property("limit-after", limit_after_adjust,
			                          "value", flags)
			self.layout.bind_property("space-before", space_before_adjust,
			                          "value", flags)
			self.layout.bind_property("space-after", space_after_adjust,
			                          "value", flags)
			                          
			# This is a special GUI bind, you can't really repeat 
			# the album without looping around it
			loop_button.bind_property("active", repeat_button,
			                          "sensitive", binding_flags.SYNC_CREATE)
			                          
			# Add tabs, pack lines
			def add_tab(self, label):
				gtk_label = Gtk.Label(label)
				box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
				box.set_border_width(24)
				self.append_page(box, gtk_label)
				return box
			
			left_aligned_labels = [
				direction_label, 
				margin_before_label, margin_after_label,
				performance_label,
				space_before_label, space_after_label,
				limit_before_label, limit_after_label
			]
			for label in left_aligned_labels:
				label.set_alignment(0, .5)
				
			alignment_label.set_alignment(0, 0)
			direction_label.set_hexpand(True)
			space_before_label.set_hexpand(True)
			performance_label.set_line_wrap(True)
			
			appearance_grid = Gtk.Grid()
			appearance_grid.set_row_spacing(12)
			appearance_grid.set_column_spacing(24)
			
			appearance_grid.attach(direction_label, 0, 0, 1, 1)
			appearance_grid.attach(direction_selector, 1, 0, 1, 1)
			
			appearance_grid.attach(alignment_label, 0, 1, 1, 1)
			appearance_grid.attach(alignment_scale, 1, 1, 1, 1)
			
			appearance_grid.attach(Gtk.Separator(), 0, 2, 2, 1)
			
			appearance_grid.attach(margin_before_label, 0, 3, 1, 1)
			appearance_grid.attach(margin_before_entry, 1, 3, 1, 1)
			appearance_grid.attach(margin_after_label, 0, 4, 1, 1)
			appearance_grid.attach(margin_after_entry, 1, 4, 1, 1)
			
			appearance_grid.attach(Gtk.Separator(), 0, 5, 2, 1)
			
			loop_line = Gtk.Box(**line_args)
			loop_line.pack_start(loop_button, False, True, 0)
			loop_line.pack_start(repeat_button, False, True, 0)
			
			appearance_grid.attach(loop_line, 0, 6, 2, 1)
			
			performance_grid = Gtk.Grid()
			performance_grid.set_row_spacing(12)
			performance_grid.set_column_spacing(24)
			
			performance_grid.attach(performance_label, 0, 0, 2, 1)
			performance_grid.attach(Gtk.Separator(), 0, 1, 2, 1)
			
			performance_grid.attach(space_before_label, 0, 2, 1, 1)
			performance_grid.attach(space_before_entry, 1, 2, 1, 1)
			performance_grid.attach(space_after_label, 0, 3, 1, 1)
			performance_grid.attach(space_after_entry, 1, 3, 1, 1)
			performance_grid.attach(Gtk.Separator(), 0, 4, 2, 1)
			
			performance_grid.attach(limit_before_label, 0, 5, 1, 1)
			performance_grid.attach(limit_before_entry, 1, 5, 1, 1)
			performance_grid.attach(limit_after_label, 0, 6, 1, 1)
			performance_grid.attach(limit_after_entry, 1, 6, 1, 1)
			
			appearance_alignment = Gtk.Alignment()
			appearance_alignment.set_padding(12, 12, 24, 24)
			appearance_alignment.add(appearance_grid)
			
			performance_alignment = Gtk.Alignment()
			performance_alignment.set_padding(12, 12, 24, 24)
			performance_alignment.add(performance_grid)
			
			label = _("Appearance")
			appearance_label = Gtk.Label(label)
			self.append_page(appearance_alignment, appearance_label)
			
			label = _("Performance")
			performance_label = Gtk.Label(label)
			self.append_page(performance_alignment, performance_label)
			
			self.show_all()
			
		def _refresh_marks(self, combobox, scale):
			scale.clear_marks()
			active_id = combobox.get_active_id()
			if active_id in ("left", "right"):
				scale.add_mark(-.5, Gtk.PositionType.BOTTOM, _("Top"))
				scale.add_mark(0, Gtk.PositionType.BOTTOM, _("Middle"))
				scale.add_mark(.5, Gtk.PositionType.BOTTOM, _("Bottom"))
					
			else:
				scale.add_mark(-.5, Gtk.PositionType.BOTTOM, _("Left"))
				scale.add_mark(0, Gtk.PositionType.BOTTOM, _("Center"))
				scale.add_mark(.5, Gtk.PositionType.BOTTOM, _("Right"))
