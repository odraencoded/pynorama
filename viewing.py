''' viewing.py contains widgets for drawing, displaying images and etc. '''

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
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import point
import cairo

# Quite possibly the least badly designed class in the whole program.
class ImageView(Gtk.DrawingArea, Gtk.Scrollable):
	''' This widget can display PictureFrames.
	    It can also zoom in, out, rotate, adjust and etc. '''
	
	__gsignals__ = {
		"transform-change" : (GObject.SIGNAL_RUN_FIRST, None, [])
	}
	
	def __init__(self):
		Gtk.DrawingArea.__init__(self)
		
		self.__frames = set()
		self.outline = point.Rectangle()
		self.__obsolete_offset = False
		
		self.offset = 0, 0
		self.magnification = 1
		self.rotation = 0
		self.flip = False, False
		# There are two interpolation settings: Zoom out and zoom in
		self.minify_interpolation = cairo.FILTER_BILINEAR
		self.magnify_interpolation = cairo.FILTER_NEAREST
		self.__hadjustment = self.__vadjustment = None
		self.__hadjust_signal = self.__vadjust_signal = None
		self.frame_signals = dict()
		
		self.connect("notify::magnification", self.__matrix_changed)
		self.connect("notify::rotation", self.__matrix_changed)
		self.connect("notify::flip", self.__matrix_changed)
		self.connect("notify::minify-interpolation",
		             self.__interpolation_changed)
		self.connect("notify::magnify-interpolation",
                     self.__interpolation_changed)
		
	def add_frame(self, *frames):
		''' Adds one or more pictures to the gallery '''
		count = len(self.__frames)
		for a_frame in frames:
			self.__frames.add(a_frame)
			a_frame_signals = self.frame_signals.get(a_frame, None)
			if a_frame_signals is None:
				a_frame_signals = [
					a_frame.connect("notify::surface", self.__frame_changed),
					a_frame.connect("notify::center", self.__frame_changed)
				]
				self.frame_signals[a_frame] = a_frame_signals
			
		if count != len(self.__frames):	
			self.__compute_outline()
			self.queue_draw()
	
	def remove_frame(self, *frames):
		''' Removes one or more pictures from the gallery '''
		count = len(self.__frames)
		for a_frame in frames:
			self.__frames.discard(a_frame)
			a_frame_signals = self.frame_signals.get(a_frame, None)
			if a_frame_signals is not None:
				for one_frame_signal in a_frame_signals:
					a_frame.disconnect(one_frame_signal)
				del self.frame_signals[a_frame]
				
		if count != len(self.__frames):
			self.__compute_outline()
			self.queue_draw()
									
	# --- view manipulation down this line --- #
	def pan(self, direction):
		self.adjust_to(*point.add(self.get_adjustment(), direction))
	
	def rotate(self, degrees):
		self.set_rotation(self.get_rotation() + degrees)
	
	def magnify(self, scale):
		self.set_magnification(self.get_magnification() * magnification)
		
	def flip(self, vertical):
		hflip, vflip = self.get_flip()
		if vertical:
			self.set_flip((hflip, not vflip))
		else:
			self.set_flip((not hflip, vflip))
	
	def adjust_to_pin(self, pin):
		''' Adjusts the view so that the same widget point in the pin can be
		    converted to the same absolute point in the pin '''
		(x, y), (px, py) = pin
		
		hflip, vflip = self.get_flip()
		if hflip:
			x *= -1
		if vflip:
			y *= -1
		
		rotation = self.get_rotation()
		if rotation:
			x, y = point.spin((x, y), rotation / 180 * math.pi)
		
		magw = self.get_magnified_width()
		magh = self.get_magnified_height()
		
		x -= px * magw
		y -= py * magh
		
		self.adjust_to(x, y)
	
	def adjust_to_frame(self, frame, rx=.5, ry=.5):
		hadjust = self.get_hadjustment()
		vadjust = self.get_vadjustment()
		vw, vh = hadjust.get_page_size(), vadjust.get_page_size()
		fw, fh = frame.get_size()
		fx, fy = frame.get_center()
		fl, ft = fx - fw / 2, fy - fh / 2
		
		x, y = rx * fw + fl, ry * fh + ft
		x, y = point.spin((x, y), self.get_rotation() / 180 * math.pi)
		
		self.adjust_to(x - vw * rx, y - vh * ry)
	
	def adjust_to_boundaries(self, rx, ry):
		hadjust = self.get_hadjustment()
		vadjust = self.get_vadjustment()
		vw, vh = hadjust.get_page_size(), vadjust.get_page_size()
		lx, ux = hadjust.get_lower(), hadjust.get_upper()
		ly, uy = vadjust.get_lower(), vadjust.get_upper()
		
		x = (ux - lx - vw) * rx + lx
		y = (uy - ly - vh) * ry + ly
		self.adjust_to(x, y)
	
	def adjust_to(self, x, y):
		hadjust = self.get_hadjustment()
		if hadjust:
			lx, ux = hadjust.get_lower(), hadjust.get_upper()
			vw = hadjust.get_page_size()
			x = max(lx, min(ux, x))
			hadjust.handler_block(self.__hadjust_signal)
			hadjust.set_value(x)
			hadjust.handler_unblock(self.__hadjust_signal)
			
		vadjust = self.get_vadjustment()
		if vadjust:
			ly, uy = vadjust.get_lower(), vadjust.get_upper()
			vh = vadjust.get_page_size()
			y = max(ly, min(uy, y))
			vadjust.handler_block(self.__vadjust_signal)
			vadjust.set_value(y)
			vadjust.handler_unblock(self.__vadjust_signal)
			
		self.__obsolete_offset = True
		self.queue_draw()
		
	# --- getter/setters down this line --- #
	def get_pin(self, widget_point=None):
		''' Gets a pin for readjusting the view to a point in the widget
		    after any transformations '''
		    
		size = self.get_widget_size()
		if not widget_point:
			widget_point = point.multiply(point.center, size)
			         		
		absolute_point = self.get_absolute_point(widget_point)
		scalar_point = point.divide(widget_point, size)
		
		return absolute_point, scalar_point
	
	def get_widget_point(self):
		''' Utility method, returns the mouse position if the mouse is over 
		    the widget, otherwise returns the point corresponding to the center
		    of the widget '''
		
		x, y = self.get_pointer()
		w, h = self.get_widget_size()
		if 0 <= x < w and 0 <= y < h:
			return x, y
		else:
			return w / 2, h / 2
		
	def get_absolute_point(self, widget_point):
		''' Returns a point with the view transformations of a point in the
		    widget reverted '''
		x, y = self.offset
		
		px, py = widget_point
		px /= self.get_allocated_width()
		py /= self.get_allocated_height()
		
		magw = self.get_magnified_width()
		magh = self.get_magnified_height()
		
		x, y = x + px * magw, y + py * magh
		
		rotation = self.get_rotation()
		if rotation:
			x, y = point.spin((x, y), rotation / 180 * math.pi * -1)
		
		hflip, vflip = self.get_flip()
		if hflip:
			x *= -1
		if vflip:
			y *= -1
			
		return (x, y)
				         
	def get_view(self):
		hadjust, vadjust = self.get_hadjustment(), self.get_vadjustment()
		return (hadjust.get_value() if hadjust else 0,
		        vadjust.get_value() if vadjust else 0,
		        hadjust.get_page_size() if hadjust else 1,
		        vadjust.get_page_size() if vadjust else 1)
	
	def get_boundary(self):
		hadjust, vadjust = self.get_hadjustment(), self.get_vadjustment()
		return (hadjust.get_lower() if hadjust else 0,
		        vadjust.get_lower() if vadjust else 0,
		        hadjust.get_upper() - hadjust.get_lower() if hadjust else 1,
		        vadjust.get_upper() - hadjust.get_lower() if vadjust else 1)
		        
	def get_frames_outline(self):
		return self.outline.to_tuple()
		
	def get_widget_size(self):
		return self.get_allocated_width(), self.get_allocated_height()
	
	def get_adjustment(self):
		hadjust, vadjust = self.get_hadjustment(), self.get_vadjustment()
		return (hadjust.get_value() if hadjust else 0,
		        vadjust.get_value() if vadjust else 0)
	def get_rotation_radians(self):
		return self.get_rotation() / 180 * math.pi * -1
		
	def get_magnified_width(self):
		return self.get_allocated_width() / self.get_magnification()
		
	def get_magnified_height(self):
		return self.get_allocated_height() / self.get_magnification()
	
	def get_interpolation_for_scale(self, scale):
		if scale > 1:
			return self.get_magnify_interpolation()
		elif scale < 1:
			return self.get_minify_interpolation()
		else:
			return None
			
	def set_interpolation_for_scale(self, scale, value):
		if scale > 1:
			self.set_magnify_interpolation(value)
		elif scale < 1:
			self.set_minify_interpolation(value)
			
	# --- basic properties down this line --- #
	def get_hadjustment(self):
		return self.__hadjustment
	def get_vadjustment(self):
		return self.__vadjustment
		
	def get_magnification(self):
		return self.magnification
	def get_rotation(self):
		return self.rotation
	def get_flip(self):
		return self.flip
		
	def get_minify_interpolation(self):
		return self.minify_interpolation	
	def get_magnify_interpolation(self):
		return self.magnify_interpolation
		
	def set_hadjustment(self, adjustment):
		if self.__hadjustment:
			self.__hadjustment.disconnect(self.__hadjust_signal)
			self.__hadjust_signal = None
			
		self.__hadjustment = adjustment
		if adjustment:
			adjustment.set_lower(self.outline.left)
			adjustment.set_upper(self.outline.right)
			adjustment.set_page_size(self.get_magnified_width())
			self.__hadjust_signal = adjustment.connect(
			                        "value-changed", self.__adjustment_changed)
			                                         
	def set_vadjustment(self, adjustment):
		if self.__vadjustment:
			self.__vadjustment.disconnect(self.__vadjust_signal)
			self.__vadjust_signal = None
			
		self.__vadjustment = adjustment
		if adjustment:
			adjustment.set_lower(self.outline.top)
			adjustment.set_upper(self.outline.bottom)
			adjustment.set_page_size(self.get_magnified_height())
			self.__vadjust_signal = adjustment.connect(
			                        "value-changed", self.__adjustment_changed)
			                        
	def set_magnification(self, magnification):
		self.magnification = magnification
		
	def set_rotation(self, value):
		self.rotation = value % 360
		
	def set_flip(self, value):
		self.flip = value
		
	def set_minify_interpolation(self, value):
		self.minify_interpolation = value
		
	def set_magnify_interpolation(self, value):
		self.magnify_interpolation = value
	
	hadjustment = GObject.property(get_hadjustment, set_hadjustment,
	                               type=Gtk.Adjustment)
	vadjustment = GObject.property(get_vadjustment, set_vadjustment,
	                               type=Gtk.Adjustment)
	                               
	hscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
	                                  default=Gtk.ScrollablePolicy.NATURAL)
	vscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
	                                  default=Gtk.ScrollablePolicy.NATURAL)
	                                  
	magnification = GObject.property(type=float, default=1)
	rotation = GObject.property(type=float, default=0)
	flip = GObject.property(type=GObject.TYPE_PYOBJECT)
	
	minify_interpolation = GObject.property(type=GObject.TYPE_INT)
	magnify_interpolation = GObject.property(type=GObject.TYPE_INT)
	
	# --- computing stuff down this line --- #
	def compute_side_scale(self, mode):
		''' Calculates the ratio between the combined frames size
		    and the allocated widget size '''
			  
		hadjust = self.get_hadjustment()
		vadjust = self.get_vadjustment()
		lx, ux = hadjust.get_lower(), hadjust.get_upper()
		ly, uy = vadjust.get_lower(), vadjust.get_upper()
		w, h = ux - lx, uy - ly
		vw, vh = self.get_allocated_width(), self.get_allocated_height()
			
		if mode == "width":
			# Match width
			side = w
			view = vw
			
		elif mode == "height":
			# Match height
			side = h
			view = vh
		else:
			rw, rh = vw / w, vh / h
			if mode == "smallest":
				# Smallest side = largest ratio
				if rw > rh:
					side = w
					view = vw
				else:
					side = h
					view = vh
			elif mode == "largest":
				# Largest side = smallest ratio
				if rw < rh:
					side = w
					view = vw
				else:
					side = h
					view = vh
			else:
			 view = side = 1
			 
		return view / side
		
	def __compute_outline(self):
		''' Figure out the outline of all frames united '''
		rectangles = []
		for a_frame in self.__frames:
			cx, cy = a_frame.get_center()
			w, h = a_frame.get_size()
			
			a_rect = point.Rectangle(cx - w / 2.0, cy - h / 2.0, w, h)
			rectangles.append(a_rect)
			
		new_outline = point.Rectangle.Union(*rectangles)
		
		if self.outline != new_outline:
			self.outline = new_outline
			self.__compute_adjustments()
			
	def __compute_adjustments(self):
		''' Figure out lower, upper and page size of adjustments.
		    Also clamp them. Clamping is important. '''
		    
		# Name's Bounds, James Bounds
		bounds = self.outline.spin(self.get_rotation() / 180 * math.pi)
		bounds = bounds.flip(*self.get_flip())
		hadjust, vadjust = self.get_hadjustment(), self.get_vadjustment()
		if hadjust:
			hadjust.set_lower(bounds.left)
			hadjust.set_upper(bounds.right)
			visible_span = min(self.get_magnified_width(), bounds.width)
			hadjust.set_page_size(visible_span)
			# Clamp value
			max_value = hadjust.get_upper() - hadjust.get_page_size()
			min_value = hadjust.get_lower()
			if hadjust.get_value() > max_value:
				hadjust.set_value(max_value)
			if hadjust.get_value() < min_value:
				hadjust.set_value(min_value)
			
		if vadjust:
			vadjust.set_lower(bounds.top)
			vadjust.set_upper(bounds.bottom)
			visible_span = min(self.get_magnified_height(), bounds.height)
			vadjust.set_page_size(visible_span)
			# Clamp value
			max_value = vadjust.get_upper() - vadjust.get_page_size()
			min_value = vadjust.get_lower()
			if vadjust.get_value() > max_value:
				vadjust.set_value(max_value)
			if vadjust.get_value() < min_value:
				vadjust.set_value(min_value)
				
		self.__obsolete_offset = True
			
	def __compute_offset(self):
		''' Figures out the x, y offset based on the adjustments '''
		x, y = self.offset
		allocation = self.get_allocation()
		hadjust = self.get_hadjustment()
		if hadjust:
			span = hadjust.get_upper() - hadjust.get_lower()
			diff = span - self.get_magnified_width()
			if diff > 0:
				x = hadjust.get_value()
				ox = 0
			else:
				x = -self.get_magnified_width() / 2
								
		vadjust = self.get_vadjustment()
		if vadjust:			
			span = vadjust.get_upper() - vadjust.get_lower()
			diff = span - self.get_magnified_height()
			if diff > 0:
				y = vadjust.get_value()
				oy = 0
			else:
				y = -self.get_magnified_height() / 2
						
		self.__obsolete_offset = False
		self.offset = x, y
	
	# --- event stuff down this line --- #
	def __frame_changed(self, *some_data_we_are_not_gonna_use_anyway):
		''' Callback for when a picture frame surface changes '''
		self.__compute_outline()
		self.queue_draw()
	
	def __adjustment_changed(self, data):
		self.__obsolete_offset = True
		self.queue_draw()
		
	def __matrix_changed(self, *data):
		# I saw a black cat walk by. Twice.
		self.__compute_adjustments()
		self.queue_draw()
		self.emit("transform-change")
	
	def __interpolation_changed(self, *data):
		self.queue_draw()
	
	def do_size_allocate(self, allocation):
		Gtk.DrawingArea.do_size_allocate(self, allocation)
		self.__compute_adjustments()
		
	def do_draw(self, cr):
		''' Draws everything! '''
		# Renders the BG. Not sure if it works
		Gtk.render_background(self.get_style_context(), cr, 0, 0,
		                      self.get_allocated_width(),
		                      self.get_allocated_height())
		if self.__obsolete_offset:
			self.__compute_offset()
			
		# Apply the zooooooom
		zoooooom = self.get_magnification()
		cr.scale(zoooooom, zoooooom)
		# Translate the offset
		x, y = self.offset
		cr.translate(-x, -y)
		# Rotate the radians
		rad = self.get_rotation() / 180 * math.pi
		cr.rotate(rad)
		# Flip the... thing
		hflip, vflip = self.get_flip()
		if hflip or vflip:
			cr.scale(-1 if hflip else 1,
			         -1 if vflip else 1)
		# Yes, this supports multiple frames!
		# No, we don't use that feature... not yet.
		for a_frame in self.__frames:
			a_surface = a_frame.get_surface()
			if a_surface:
				cr.save()
				try:					
					# My naming style is an_weird_one
					a_w, an_h = a_surface.get_width(), a_surface.get_height()
					an_x, an_y = a_frame.get_center()
					cr.translate(an_x, an_y)
					
					cr.set_source_surface(a_surface, -a_w / 2, -an_h / 2)
					
					# Set filter
					a_pattern = cr.get_source()
					a_filter = self.get_interpolation_for_scale(zoooooom)
					if a_filter is not None:
						a_pattern.set_filter(a_filter)
					
					cr.paint()
					
				except:
					pass
					
				finally:
					cr.restore()
    
class ImageFrame(GObject.GObject):
	''' Contains a image '''
	# TODO: Implement rotation and scale
	def __init__(self, surface=None):
		GObject.GObject.__init__(self)
		self.center = 0, 0
		self.surface = surface
	
	def get_center(self):
		return self.center
	def set_center(self, value):
		self.center = value
		
	def get_surface(self):
		return self.surface
	def set_surface(self, value):
		self.surface = value
	
	def get_size(self):
		if self.surface:
			w, h = self.surface.get_width(), self.surface.get_height()
			return w, h
		else:
			return 1, 1
			
	def set_pixbuf(self, pixbuf):
		''' Utility function, just in case'''
		if pixbuf:
			surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
			                                  pixbuf.get_width(),
			                                  pixbuf.get_height())
			cr = cairo.Context(surface)
			Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
			cr.paint()
			
		else:
			surface = None
			
		self.set_surface(surface)
	
	center = GObject.property(type=GObject.TYPE_PYOBJECT)
	surface = GObject.property(type=GObject.TYPE_PYOBJECT)
