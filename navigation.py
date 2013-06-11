''' navigation.py defines viewing.py related navigation. '''

''' ...And this file is part of Pynorama.
    
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

from gi.repository import Gtk, Gdk, GLib, GObject
from gettext import gettext as _
import math, time
import point

class MouseAdapter(GObject.GObject):
	''' Adapts a widget mouse events '''
	EventMask = (Gdk.EventMask.BUTTON_PRESS_MASK |
	             Gdk.EventMask.BUTTON_RELEASE_MASK |
	             Gdk.EventMask.SCROLL_MASK |
	             Gdk.EventMask.SMOOTH_SCROLL_MASK |
	             Gdk.EventMask.ENTER_NOTIFY_MASK |
	             Gdk.EventMask.POINTER_MOTION_MASK |
	             Gdk.EventMask.POINTER_MOTION_HINT_MASK)
	
	# According to the docs, Gtk uses +10 for resizing and +20 for redrawing
	# +15 should dispatch events after resizing and before redrawing
	# TODO: Figure out whether that is a good idea
	IdlePriority = GLib.PRIORITY_HIGH_IDLE + 15
	
	__gsignals__ = {
		"motion" : (GObject.SIGNAL_RUN_FIRST, None, [object, object]),
		"drag" : (GObject.SIGNAL_RUN_FIRST, None, [object, object, int]),
		"pression" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"click" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"scroll" : (GObject.SIGNAL_RUN_FIRST, None, [object, object]),
		"start-dragging" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
		"stop-dragging" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
	}
	
	def __init__(self, widget=None):
		GObject.GObject.__init__(self)
		
		self.__from_point = None
		self.__pressure = dict()
		self.__widget = None
		
		self.__delayed_motion_id = None
		self.__widget_handler_ids = None
		self.__ice_cubes = 0
		self.__motion_from_outside = 2
		self.__pressure_from_outside = True
		
		if widget:
			self.set_widget(widget)
			
	def get_widget(self):
		return self.__widget
		
	def set_widget(self, widget):
		if self.__widget != widget:
			if self.__widget:
				self.__pressure.clear()
				
				for a_handler_id in self.__widget_handler_ids:
					self.__widget.disconnect(a_handler_id)
				self.__widget_handler_ids = None
				
				if self.__delayed_motion_id:
					GLib.source_remove(self.__delayed_motion_id)
					self.__delayed_motion_id = None
				
			self.__widget = widget
			if widget:			
				widget.add_events(MouseAdapter.EventMask)
				self.__widget_handler_ids = [
					widget.connect("button-press-event", self._button_press),
					widget.connect("button-release-event", self._button_release),
					widget.connect("scroll-event", self._mouse_scroll),
					widget.connect("enter-notify-event", self._mouse_enter),
					widget.connect("motion-notify-event", self._mouse_motion),
				]
				
	widget = GObject.property(get_widget, set_widget, type=Gtk.Widget)
	
	# icy-wut-i-did-thaw
	@property
	def is_frozen(self):
		return self.__ice_cubes > 0
		
	def freeze(self):
		self.__ice_cubes += 1
		
	def thaw(self):
		self.__ice_cubes -= 1
	
	def is_pressed(self, button=None):
		return bool(self.__pressure if button is None \
		            else self.__pressure.get(button, 0))
	
	# begins here the somewhat private functions
	def _button_press(self, widget, data):
		self.__pressure.setdefault(data.button, 1)
		if not self.is_frozen:
			point = data.x, data.y
			self.emit("pression", point, data.button)
		
	def _button_release(self, widget, data):
		if data.button in self.__pressure:
			if not self.is_frozen:
				button_pressure = self.__pressure.get(data.button, 0)
				if button_pressure:
					point = data.x, data.y
					if button_pressure == 2:
						self.emit("stop-dragging", point, data.button)
					
					self.emit("click", point, data.button)
				
			del self.__pressure[data.button]
			
	def _mouse_scroll(self, widget, data):
		if not self.is_frozen:
			point = data.x, data.y
			# I don't have one of those cool mice with smooth scrolling
			got_delta, xd, yd = data.get_scroll_deltas()
			if not got_delta:
				# So I'm not sure this is how it maps
				got_direction, direction = data.get_scroll_direction()
				if got_direction:
					xd, yd = [
						(0, -1), (0, 1),
						(-1, 0), (1, 0)
					][int(data.direction)] # it is [Up, right, down, left]
					got_delta = True
			
			if got_delta:
				self.emit("scroll", point, (xd, yd))
	
	def _mouse_enter(self, *data):
		self.__motion_from_outside = 2
		if not self.__pressure:
			self.__pressure_from_outside = True
								
	def _mouse_motion(self, widget, data):
		# Motion events are handled idly
		self.__current_point = data.x, data.y
		if not self.__delayed_motion_id:
			if not self.__from_point:
				self.__from_point = self.__current_point
			
			if self.__motion_from_outside:
				self.__motion_from_outside -= 1
				if not self.__motion_from_outside:
					self.__pressure_from_outside = False
			
			self.__delayed_motion_id = GLib.idle_add(
			                                self.__delayed_motion, widget,
			                                priority=MouseAdapter.IdlePriority)
			     
	def __delayed_motion(self, widget):
		self.__delayed_motion_id = None
		
		if not self.is_frozen:
			# You got to love tuple comparation
			if self.__from_point != self.__current_point:
				if not self.__pressure_from_outside:
					for button, pressure in self.__pressure.items():
						if pressure == 1:
							self.__pressure[button] = 2
							self.emit("start-dragging",
								      self.__current_point, button)
						
						if pressure:
							self.emit("pression", self.__current_point, button)
						
				if not self.__motion_from_outside:
					self.emit("motion", self.__current_point, self.__from_point)
					
				for button, pressure in self.__pressure.items():
					if pressure == 2:
						self.emit("drag",
						          self.__current_point, self.__from_point,
						          button)
				
		self.__from_point = self.__current_point
		return False
		
class MouseEvents:
	Nothing   =  0 #000000
	Moving    =  3 #000011
	Hovering  =  1 #000001
	Pressing  = 22 #010110
	Dragging  = 14 #001110
	Clicking  = 20 #010100
	Scrolling = 32 #100000
	
class MetaMouseHandler:
	''' Handles mouse events from mouse adapters for mouse handlers '''
	# It's So Meta Even This Acronym
	def __init__(self):
		self.__adapters = dict()
		self.__handlers = dict()
		self.__pression_handlers = set()
		self.__hovering_handlers = set()
		self.__dragging_handlers = set()
		self.__scrolling_handlers = set()
		self.__button_handlers = dict()
		
	def add(self, handler, button=None):
		if not handler in self.__handlers:
			if handler.needs_button:
				if button:
					button_set = self.__button_handlers.get(button, set())
					button_set.add(handler)
					self.__button_handlers[button] = button_set
					
				else:
					raise ValueError
					
			elif button:
				raise ValueError
				
			self.__handlers[handler] = dict()
			for handler_set in self.__get_handler_sets(handler):
				handler_set.add(handler)
				
	def remove(self, handler):
		if handler in self.__handlers:
			del self.__handlers[handler]
			for handler_set in self.__get_handler_sets(handler):
				handler_set.discard(handler)
			
			for a_button_set in self.__button_handlers.values():
				a_button_set.discard(handler)
	
	def __get_handler_sets(self, handler):
		if handler.handles(MouseEvents.Scrolling):
			yield self.__scrolling_handlers
			
		if handler.handles(MouseEvents.Pressing):
			yield self.__pression_handlers
			
		if handler.handles(MouseEvents.Hovering):
			yield self.__hovering_handlers
			
		if handler.handles(MouseEvents.Dragging):
			yield self.__dragging_handlers
				
	def attach(self, adapter):
		if not adapter in self.__adapters:
			signals = [
				adapter.connect("motion", self._motion),
				adapter.connect("pression", self._pression),
				adapter.connect("scroll", self._scroll),
				adapter.connect("start-dragging", self._start_dragging),
				adapter.connect("drag", self._drag),
				adapter.connect("stop-dragging", self._stop_dragging),
			]
			self.__adapters[adapter] = signals
			
	def detach(self, adapter):
		signals = self.__adapters.get(adapter, [])
		for a_signal in signals:
			adapter.disconnect(a_signal)
			
		del self.__adapters[adapter]
		
	def __overlap_button_set(self, handler_set, button):
		button_handlers = self.__button_handlers.get(button, set())
		
		if button_handlers:
			return handler_set & button_handlers
		else:
			return button_handlers
	
	def __basic_event_dispatch(self, adapter, event_handlers,
	                           function_name, *params):
	                           
		widget = adapter.get_widget()
		
		for a_handler in event_handlers:
			data = self.__handlers[a_handler].get(adapter, None)
			function = getattr(a_handler, function_name)
			data = function(widget, *(params + (data,)))
			if data:
				self.__handlers[a_handler][adapter] = data
	
	def _scroll(self, adapter, point, direction):
		if self.__scrolling_handlers:
			self.__basic_event_dispatch(adapter, self.__scrolling_handlers,
			                            "scroll", point, direction)
	
	def _motion(self, adapter, to_point, from_point):
		if adapter.is_pressed():
			hovering = not any((adapter.is_pressed(a_button) \
			                      for a_button, a_button_handlers \
			                      in self.__button_handlers.items() \
			                      if a_button_handlers))
		else:
			hovering = True
			
		if hovering:
			self.__basic_event_dispatch(adapter, self.__hovering_handlers,
			                            "hover", to_point, from_point)
	
	def _pression(self, adapter, point, button):
		active_handlers = self.__overlap_button_set(
		                       self.__pression_handlers, button)
		                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
			                            "press", point)
		
	def _start_dragging(self, adapter, point, button):
		active_handlers = self.__overlap_button_set(
		                       self.__dragging_handlers, button)
		                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
			                            "start_dragging", point)
		
	def _drag(self, adapter, to_point, from_point, button):		
		active_handlers = self.__overlap_button_set(
		                       self.__dragging_handlers, button)
		                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
					                    "drag", to_point, from_point)
			
	def _stop_dragging(self, adapter, point, button):
		active_handlers = self.__overlap_button_set(
                       self.__dragging_handlers, button)
                       
		if active_handlers:
			self.__basic_event_dispatch(adapter, active_handlers, 
				                        "stop_dragging", point)
		                            
class MouseHandler:
	''' Handles mouse events '''
	# The base of the totem pole
	
	def __init__(self):
		self.events = MouseEvents.Nothing
		
	def handles(self, event_type):
		return self.events & event_type == event_type \
		       if event_type != MouseEvents.Nothing \
		       else not bool(self.events)
		       
	@property
	def needs_button(self):
		return bool(self.events & MouseEvents.Pressing)
		
	def scroll(self, widget, point, direction, data):
		pass
		
	def press(self, widget, point, data):
		pass
	
	def hover(self, widget, to_point, from_point, data):
		pass
	
	def start_dragging(self, widget, point, data):
		pass
	
	def drag(self, widget, to_point, from_point, data):
		pass
		
	def stop_dragging(self, widget, point, data):
		pass
		
class HoverHandler(MouseHandler):
	''' Pans a view on mouse hovering '''
	def __init__(self, speed=1.0, magnify=False):
		MouseHandler.__init__(self)
		self.speed = speed
		self.magnify_speed = magnify
		self.events = MouseEvents.Hovering
	
	def hover(self, view, to_point, from_point, data):
		shift = point.subtract(to_point, from_point)
		
		scale = self.speed
		if not self.magnify_speed:
			scale /= view.get_magnification()
		
		scaled_shift = point.scale(shift, scale)
		view.pan(scaled_shift)

class DragHandler(HoverHandler):
	''' Pans a view on mouse dragging '''
	
	def __init__(self, speed=-1.0, magnify=False):
		HoverHandler.__init__(self, speed, magnify)
		self.events = MouseEvents.Dragging
		
	def start_dragging(self, view, *etc):
		fleur_cursor = Gdk.Cursor(Gdk.CursorType.FLEUR)
		view.get_window().set_cursor(fleur_cursor)
	
	drag = HoverHandler.hover # lol.
	
	def stop_dragging(self, view, *etc):
		view.get_window().set_cursor(None)

class MapHandler(MouseHandler):
	''' Adjusts a view to match a point inside.
	    In it's most basic way for "H" being a point in the widget,
	    "C" being the resulting adjustment, "B" being the widget size and
	    "S" being the boundaries of the viewing widget model: C = H / B * S '''
	def __init__(self, margin=32, mapping_mode="proportional"):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Pressing
		self.mapping_mode = mapping_mode
		self.margin = margin
		
	def press(self, view, point, data):
		# Clamp mouse pointer to map
		rx, ry, rw, rh = self.get_map_rectangle(view)
		mx, my = point
		x = max(0, min(rw, mx - rx))
		y = max(0, min(rh, my - ry))
		# The adjustments
		hadjust = view.get_hadjustment()
		vadjust = view.get_vadjustment()
		# Get content bounding box
		full_width = hadjust.get_upper() - hadjust.get_lower()
		full_height = vadjust.get_upper() - vadjust.get_lower()
		full_width -= hadjust.get_page_size()
		full_height -= vadjust.get_page_size()
		# Transform x and y to picture "adjustment" coordinates
		tx = x / rw * full_width + hadjust.get_lower()
		ty = y / rh * full_height + vadjust.get_lower()
		view.adjust_to(tx, ty)
		
	def get_map_rectangle(self, view):
		allocation = view.get_allocation()
		
		allocation.x = allocation.y = self.margin
		allocation.width -= self.margin * 2
		allocation.height -= self.margin * 2
		
		if allocation.width <= 0:
			diff = 1 - allocation.width
			allocation.width += diff
			allocation.x -= diff / 2
			
		if allocation.height <= 0:
			diff = 1 - allocation.height
			allocation.height += diff
			allocation.y -= diff / 2
		
		if self.mapping_mode == "square":
			if allocation.width > allocation.height:
				smallest_side = allocation.height
			else:
				smallest_side = allocation.width
			
			half_width_diff = (allocation.width - smallest_side) / 2
			half_height_diff = (allocation.height - smallest_side) / 2
			
			return (allocation.x + half_width_diff,
				    allocation.y + half_height_diff,
				    allocation.width - half_width_diff * 2,
				    allocation.height - half_height_diff * 2)
			
		elif self.mapping_mode == "proportional":
			hadjust = view.get_hadjustment()
			vadjust = view.get_vadjustment()
			full_width = hadjust.get_upper() - hadjust.get_lower()
			full_height = vadjust.get_upper() - vadjust.get_lower()
			fw_ratio = allocation.width / full_width
			fh_ratio = allocation.height / full_height
						
			if fw_ratio > fh_ratio:
				smallest_ratio = fh_ratio
			else:
				smallest_ratio = fw_ratio
			
			transformed_width = smallest_ratio * full_width
			transformed_height = smallest_ratio * full_height
			
			half_width_diff = (allocation.width - transformed_width) / 2
			half_height_diff = (allocation.height - transformed_height) / 2
			
			return (allocation.x + half_width_diff,
				    allocation.y + half_height_diff,
				    allocation.width - half_width_diff * 2,
				    allocation.height - half_height_diff * 2)
			
		else:
			return (allocation.x, allocation.y,
			        allocation.width, allocation.height)
			        
class SpinHandler(MouseHandler):
	''' Spins a view '''
	
	SpinThreshold = 5
	SoftRadius = 25
	
	def __init__(self, frequency=1, fixed_pivot=None):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Dragging
		# Number of complete turns in the view per revolution around the pivot
		self.frequency = frequency 
		# Use a fixed pivot instead of the dragging start point
		self.fixed_pivot = fixed_pivot
		
	def start_dragging(self, view, point, data):
		if self.fixed_pivot:
			w, h = view.get_allocated_width(), view.get_allocated_height()
			sx, sy = self.fixed_pivot
			pivot = sx * w, sy * h
		else:
			pivot = point
			
		return pivot, view.get_pin(pivot)
	
	def drag(self, view, to_point, from_point, data):
		pivot, pin = data
		
		# Get vectors from the pivot
		(tx, ty), (fx, fy), (px, py) = to_point, from_point, pivot
		tdx, tdy = tx - px, ty - py
		fdx, fdy = fx - px, fy - py
		
		# Get rotational delta, multiply it by frequency
		ta = math.atan2(tdy, tdx) / math.pi * 180
		fa = math.atan2(fdy, fdx) / math.pi * 180
		rotation_effect = (ta - fa) * self.frequency
		
		# Modulate degrees
		rotation_effect %= 360 if rotation_effect >= 0 else -360
		if rotation_effect > 180:
			rotation_effect -= 360
		if rotation_effect < -180:
			rotation_effect += 360 
			
		# Thresholding stuff
		square_distance = tdx ** 2 + tdy ** 2
		if square_distance > SpinHandler.SpinThreshold ** 2:
			# Falling out stuff
			square_soft_radius = SpinHandler.SoftRadius ** 2
			if square_distance < square_soft_radius:
				fallout_effect = square_distance / square_soft_radius
				rotation_effect *= fallout_effect
			
			# Changing the rotation(finally)
			view.set_rotation(view.get_rotation() + rotation_effect)
			# Anchoring!!!
			view.adjust_to_pin(pin)
			
		return data

class StretchHandler(MouseHandler):
	''' Stretches/shrinks a view '''
	
	MinDistance = 10
	
	def __init__(self, pivot=(.5, .5)):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Dragging
		self.pivot = pivot
		
	def start_dragging(self, view, start_point, data):
		widget_size = view.get_widget_size()
		widget_pivot = point.multiply(self.pivot, widget_size)
		
		start_diff = point.subtract(start_point, widget_pivot)
		distance = max(StretchHandler.MinDistance, point.length(start_diff))
		
		zoom = view.get_magnification()
		zoom_ratio = zoom / distance
		
		return zoom_ratio, widget_pivot, view.get_pin(widget_pivot)
	
	def drag(self, view, to_point, from_point, data):
		zoom_ratio, widget_pivot, pin = data
		
		# Get vectors from the pivot
		point_diff = point.subtract(to_point, widget_pivot)
		distance = max(StretchHandler.MinDistance, point.length(point_diff))
		
		new_zoom = distance * zoom_ratio
		
		view.set_magnification(new_zoom)
		view.adjust_to_pin(pin)
		
		return data

class ScrollModes:
	Normal   = 0 # Your garden variety scrolling
	InverseH = 1 # Invert H axis value
	InverseV = 2 # Invert V axis value
	Inverse  = 3 # Invert axis' values
	Swap     = 4 # Swaps vertical/horizontal scrolling
	Wide     = 8 # Vertical axis scrolls along the largest side
	Thin     = 12 # Vertical axis scrolls along the smallest side
	
class ScrollHandler(MouseHandler):
	''' Scrolls a view '''
	
	def __init__(self, mode=ScrollModes.Normal, factor=0.3, rotate=False):
		MouseHandler.__init__(self)
		self.events = MouseEvents.Scrolling
		self.factor = factor
		self.mode = mode
		self.rotate = rotate
		
	def scroll(self, view, position, direction, data):
		xd, yd = direction
		
		view_size = view.get_view()[2:]
		
		if self.rotate:
			xd, yd = point.spin((xd, yd), view.get_rotation_radians())
			scroll_along_size = view.get_frames_outline()[2:]
			
		else:
			scroll_along_size = view.get_boundary()[2:]
				
		if self.mode & ScrollModes.Wide:
			unviewed_ratio = point.divide(scroll_along_size, view_size)
			
			if point.is_wide(unviewed_ratio):
				xd, yd = yd, xd
			
		if self.mode & ScrollModes.Swap:
			xd, yd = yd, xd
		
		if self.mode & ScrollModes.InverseH:
			xd = -xd
			
		if self.mode & ScrollModes.InverseV:
			yd = -yd
		
		scaled_view_size = point.scale(view_size, self.factor)
		scaled_shift = point.multiply((xd, yd), scaled_view_size)
		view.pan(scaled_shift)
		
class ZoomHandler(MouseHandler):
	''' Zooms a view '''
	
	def __init__(self, minify_anchor=None, magnify_anchor=None,
	             mode=ScrollModes.Normal, power=2):
	             
		MouseHandler.__init__(self)
		self.events = MouseEvents.Scrolling
		self.power = power
		self.mode = mode
		self.anchors = minify_anchor, magnify_anchor
		
	def scroll(self, view, point, direction, data):
		dx, dy = direction
		delta = dx if self.mode & ScrollModes.Swap else dy
		
		if not self.mode & ScrollModes.Inverse:
			delta *= -1
		
		if self.power and delta:
			anchor = self.anchors[0 if delta < 0 else 1]
			if anchor:
				w, h = view.get_allocated_width(), view.get_allocated_height()
				anchor_point = anchor[0] * w, anchor[1] * h
			else:
				anchor_point = point
			
			pin = view.get_pin(anchor_point)
			
			zoom = view.get_magnification()
			zoom *= self.power ** delta
			view.set_magnification(zoom)
			
			view.adjust_to_pin(pin)

class GearHandler(MouseHandler):
	''' Spins a view with each scroll tick '''
	
	def __init__(self, anchor=None, mode=ScrollModes.Normal, effect=45):
	             
		MouseHandler.__init__(self)
		self.events = MouseEvents.Scrolling
		self.anchor = anchor
		self.mode = mode
		self.effect = effect
		
	def scroll(self, view, point, direction, data):
		dx, dy = direction
		delta = dx if self.mode & ScrollModes.Swap else dy
		
		if not self.mode & ScrollModes.Inverse:
			delta *= -1
			
		if self.anchor:
			w, h = view.get_allocated_width(), view.get_allocated_height()
			anchor_point = self.anchor[0] * w, self.anchor[1] * h
		else:
			anchor_point = point
			
		pin = view.get_pin(anchor_point)
		
		angle = view.get_rotation()
		angle += self.effect * delta
		view.set_rotation(angle)
		
		view.adjust_to_pin(pin)
