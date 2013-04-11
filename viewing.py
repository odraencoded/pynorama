import math
from gi.repository import Gtk, Gdk, GdkPixbuf, GObject
import cairo

class GalleryView(Gtk.DrawingArea, Gtk.Scrollable):
	''' This widget can display PictureFrames.
	    It can also zoom in, out, rotate, adjust and etc. '''
	
	__gsignals__ = {
		"transform-change" : (GObject.SIGNAL_RUN_FIRST, None, [])
	}
	
	def __init__(self):
		Gtk.DrawingArea.__init__(self)
		
		self.__frames = set()
		self.the_big_frame = Rectangle()
		self.need_computing = False
		
		self.offset = 0, 0
		self.magnification = 1
		self.rotation = 0
		self.flip = False, False
		# There are two interpolation settings: Zoom out and zoom in
		self.minify_interpolation = cairo.FILTER_BILINEAR
		self.magnify_interpolation = cairo.FILTER_NEAREST
		self.__hadjustment = self.__vadjustment = None
		self.hadjust_signal = self.vadjust_signal = None
		self.frame_signals = dict()
		
		self.connect("notify::magnification", self.matrix_changed)
		self.connect("notify::rotation", self.matrix_changed)
		self.connect("notify::flip", self.matrix_changed)
		self.connect("notify::minify-interpolation",
		             self.interpolation_changed)
		self.connect("notify::magnify-interpolation",
                     self.interpolation_changed)
		
	def add_frame(self, *frames):
		''' Adds one or more pictures to the gallery '''
		count = len(self.__frames)
		for a_frame in frames:
			self.__frames.add(a_frame)
			a_frame_signals = self.frame_signals.get(a_frame, None)
			if a_frame_signals is None:
				a_frame_signals = [
					a_frame.connect("notify::surface", self.frame_changed),
					a_frame.connect("notify::center", self.frame_changed)
				]
				self.frame_signals[a_frame] = a_frame_signals
			
		if count != len(self.__frames):	
			self.compute_frames()
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
			self.compute_frames()
			self.queue_draw()
	
	def adjust_to_frame(self, frame, rx=.5, ry=.5):
		hadjust = self.get_hadjustment()
		vadjust = self.get_vadjustment()
		vw, vh = hadjust.get_page_size(), vadjust.get_page_size()
		fw, fh = frame.get_size()
		fx, fy = frame.get_center()
		fl, ft = fx - fw / 2, fy - fh / 2
		
		x, y = rx * fw + fl, ry * fh + ft
		x, y = spin_point(x, y, self.get_rotation() / 180 * math.pi)
		
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
			hadjust.handler_block(self.hadjust_signal)
			hadjust.set_value(x)
			hadjust.handler_unblock(self.hadjust_signal)
			
		vadjust = self.get_vadjustment()
		if vadjust:
			ly, uy = vadjust.get_lower(), vadjust.get_upper()
			vh = vadjust.get_page_size()
			y = max(ly, min(uy, y))
			vadjust.handler_block(self.vadjust_signal)
			vadjust.set_value(y)
			vadjust.handler_unblock(self.vadjust_signal)
			
		self.need_computing = True
		self.queue_draw()
		
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
	
	def frame_changed(self, data, some_other_data_we_are_not_gonna_use_anyway):
		''' Callback for when a picture frame surface changes '''
		self.compute_frames()
		self.queue_draw()
		
	def compute_frames(self):
		''' Figure out the outline of all frames united '''
		rectangles = []
		for a_frame in self.__frames:
			cx, cy = a_frame.get_center()
			w, h = a_frame.get_size()
			
			a_rect = Rectangle(cx - w / 2.0, cy - h / 2.0, w, h)
			rectangles.append(a_rect)
			
		big_frame = Rectangle.Union(*rectangles)
		
		if self.the_big_frame != big_frame:
			self.the_big_frame = big_frame
			self.compute_adjustments()
			
	def compute_adjustments(self):
		''' Figure out lower, upper and page size of adjustments.
		    Also clamp them. Clamping is important. '''
		    
		# Name's Bounds, James Bounds
		bounds = Rectangle.Spin(self.the_big_frame,
		                        self.get_rotation() / 180 * math.pi)
		bounds = Rectangle.Flip(bounds, *self.get_flip())
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
				
		self.need_computing = True
			
	def compute_offset(self):
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
						
		self.need_computing = False
		self.offset = x, y
		
	def adjustment_changed(self, data):
		self.need_computing = True
		self.queue_draw()
		
	def do_size_allocate(self, allocation):
		Gtk.DrawingArea.do_size_allocate(self, allocation)
		self.compute_adjustments()
		
	def do_draw(self, cr):
		''' Draws everything! '''
		# Renders the BG. Not sure if it works
		Gtk.render_background(self.get_style_context(), cr, 0, 0,
		                      self.get_allocated_width(),
		                      self.get_allocated_height())
		if self.need_computing:
			self.compute_offset()
			
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
					
	def matrix_changed(self, *data):
		# I saw a black cat walk by. Twice.
		self.compute_adjustments()
		self.queue_draw()
		self.emit("transform-change")
	
	def interpolation_changed(self, *data):
		self.queue_draw()
		
	def get_hadjustment(self):
		return self.__hadjustment
	def set_hadjustment(self, adjustment):
		if self.__hadjustment:
			self.__hadjustment.disconnect(self.hadjust_signal)
			self.hadjust_signal = None
			
		self.__hadjustment = adjustment
		if adjustment:
			adjustment.set_lower(self.the_big_frame.left)
			adjustment.set_upper(self.the_big_frame.right)
			adjustment.set_page_size(self.get_magnified_width())
			self.hadjust_signal = adjustment.connect("value-changed",
			                                         self.adjustment_changed)
				
	def get_vadjustment(self):
		return self.__vadjustment
	def set_vadjustment(self, adjustment):
		if self.__vadjustment:
			self.__vadjustment.disconnect(self.vadjust_signal)
			self.vadjust_signal = None
			
		self.__vadjustment = adjustment
		if adjustment:
			adjustment.set_lower(self.the_big_frame.top)
			adjustment.set_upper(self.the_big_frame.bottom)
			adjustment.set_page_size(self.get_magnified_height())
			self.vadjust_signal = adjustment.connect("value-changed",
			                                         self.adjustment_changed)
			                                         
	hadjustment = GObject.property(get_hadjustment, set_hadjustment,
	                               type=Gtk.Adjustment)
	vadjustment = GObject.property(get_vadjustment, set_vadjustment,
	                               type=Gtk.Adjustment)
	hscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
	                                  default=Gtk.ScrollablePolicy.NATURAL)
	vscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
	                                  default=Gtk.ScrollablePolicy.NATURAL)
	
	def get_magnified_width(self):
		return self.get_allocated_width() / self.get_magnification()
	def get_magnified_height(self):
		return self.get_allocated_height() / self.get_magnification()
		
	def get_magnification(self):
		return self.magnification
	def set_magnification(self, magnification):
		self.magnification = magnification
		
	def get_rotation(self):
		return self.rotation
	def set_rotation(self, value):
		self.rotation = value
		
	def get_flip(self):
		return self.flip
	def set_flip(self, value):
		self.flip = value
		
	def flip_view(self, vertical):
		hflip, vflip = self.__flip
		if vertical:
			self.set_flip((hflip, not vflip))
		else:
			self.set_flip((not hflip, vflip))
			
	magnification = GObject.property(type=float, default=1)
	rotation = GObject.property(type=float, default=0)
	flip = GObject.property(type=GObject.TYPE_PYOBJECT)
		
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
	
	def get_minify_interpolation(self):
		return self.minify_interpolation
	def set_minify_interpolation(self, value):
		self.minify_interpolation = value
	
	def get_magnify_interpolation(self):
		return self.magnify_interpolation
	def set_magnify_interpolation(self, value):
		self.magnify_interpolation = value
	
	minify_interpolation = GObject.property(type=GObject.TYPE_INT)
	magnify_interpolation = GObject.property(type=GObject.TYPE_INT)
    
class PictureFrame(GObject.Object):
	''' Contains picture '''
	# TODO: Implement rotation and scale
	def __init__(self, surface=None):
		GObject.Object.__init__(self)
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
	
	def copy(self):
		return Rectangle(self.left, self.top, self.width, self.height)
		
	@staticmethod
	def Spin(rect, angle):
		''' Basic trigonometrics '''
		result = rect.copy()
		if angle:
			a = spin_point(rect.left, rect.top, angle)
			b = spin_point(rect.right, rect.top, angle)
			c = spin_point(rect.right, rect.bottom, angle)
			d = spin_point(rect.left, rect.bottom, angle)
		
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
	
	@staticmethod
	def Flip(rect, horizontal, vertical):
		''' Basic conditions '''
		result = rect.copy()
		if horizontal:
			result.left = -rect.right
	
		if vertical:
			result.top = -rect.bottom
				
		return result
	
	@staticmethod
	def Scale(rect, scale):
		''' Basic mathematics '''
		result = rect.copy()
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
		
def spin_point(x, y, r):
	rx = x * math.cos(r) - y * math.sin(r)
	ry = x * math.sin(r) + y * math.cos(r)
	return rx, ry
	
