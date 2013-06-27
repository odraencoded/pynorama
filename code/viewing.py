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
from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Gtk
import point, utility
import cairo

class ZoomMode:
	FillView = 0
	MatchWidth = 1
	MatchHeight = 2
	FitContent = 3

# Quite possibly the least badly designed class in the whole program.
class ImageView(Gtk.DrawingArea, Gtk.Scrollable):
	''' This widget can display ImageFrames.
	    It can also zoom in, out, rotate, adjust and etc.
	    Pretty much the basis of the entire app '''
	
	__gsignals__ = {
		"transform-change" : (GObject.SIGNAL_RUN_FIRST, None, []),
		"offset-change" : ((GObject.SIGNAL_RUN_FIRST, None, []))
	}
	
	def __init__(self):
		Gtk.DrawingArea.__init__(self)
		
		# The set of frames being displayed in this widget
		self._frames = set()
		self._frame_signals = dict()
		
		# The outline is a the boundary of _frames before they are rotated
		self.refresh_outline = utility.IdlyMethod(self.refresh_outline)
		self.refresh_outline.priority = GLib.PRIORITY_HIGH
		
		self.outline = point.Rectangle(width=1, height=1)
		
		# Does this even do anything?
		self.get_style_context().add_class(Gtk.STYLE_CLASS_VIEW)
		
		# offset is usually the same as horizontal/vertical adjustments values
		# unless the outline fits inside the widget
		self.offset = 0, 0
		self._obsolete_offset = False
		
		self._hadjustment = self._vadjustment = None
		self._hadjust_signal = self._vadjust_signal = None
		
		self.connect("notify::magnification", self._matrix_changed)
		self.connect("notify::rotation", self._matrix_changed)
		self.connect("notify::flip", self._matrix_changed)
		self.connect("notify::minify-filter",
		             self._interpolation_changed)
		self.connect("notify::magnify-filter",
                     self._interpolation_changed)
		self.connect("notify::round-full-pixel-offset",
		             self._interpolation_changed)
		self.connect("notify::round-sub-pixel-offset",
                     self._interpolation_changed)
		
		self._magnification_watch = (0, None)
		self.connect("notify::magnification", self._magnification_changed)
		

	def add_frame(self, *frames):
		''' Adds one or more pictures to the gallery '''
		for a_frame in frames:
			self._frames.add(a_frame)
			a_frame_signals = self._frame_signals.get(a_frame, None)
			if a_frame_signals is None:
				a_frame_signals = [
					a_frame.connect("notify::origin", self._frame_changed)
				]
				self._frame_signals[a_frame] = a_frame_signals
				
			a_frame.added(self)
			
		self.refresh_outline.queue()
		self.queue_draw()


	def remove_frame(self, *frames):
		''' Removes one or more pictures from the gallery '''
		for a_frame in frames:
			self._frames.discard(a_frame)
			a_frame_signals = self._frame_signals.pop(a_frame, None)
			if a_frame_signals is not None:
				for one_frame_signal in a_frame_signals:
					a_frame.disconnect(one_frame_signal)
			
			a_frame.removed(self)
			
		self.refresh_outline.queue()
		self.queue_draw()


	def refresh_outline(self):
		''' Figure out the outline of all frames united '''
		rectangles = [a_frame.rectangle.shift(a_frame.origin) \
		                                for a_frame in self._frames]
		                                                      
		new_outline = point.Rectangle.Union(rectangles)
		new_outline.width = max(new_outline.width, 1)
		new_outline.height = max(new_outline.height, 1)
		
		if self.outline != new_outline:
			self.outline = new_outline
			self._compute_adjustments()
	
	@property
	def frames_fit(self):
		''' Whether all frames are within the widget view '''
		w, h = self.get_magnified_width(), self.get_magnified_height()
		return self.outline.width < w and self.outline.height < h
		
	# --- view manipulation down this line --- #
	def pan(self, direction):
		self.adjust_to(*point.add(self.get_adjustment(), direction))
	
	def rotate(self, degrees):
		self.rotation = self.rotation + degrees
	
	def magnify(self, scale):
		self.magnification = self.magnification * scale
		
	def flip(self, vertically=False, Horizontally=False):
		if vertically:
			self.vertical_flip = not self.vertical_flip
			
		if horziontally:
			self.horizontal_flip = not self.horizontal_flip
	
	def zoom_for_size(self, size, mode):
		''' Gets a zoom for a size based on a zoom mode '''
		w, h = self.get_widget_size()
		sw, sh = size
		
		if mode == ZoomMode.MatchWidth:
			# Match view and size width
			size_side = sw
			view_side = w
		
		elif mode == ZoomMode.MatchHeight:
			# Match view and size height
			size_side = sh
			view_side = h
		else:
			wr, hr = w / sw, h / sh
			
			if mode == ZoomMode.FitContent:
				# Fit size inside view
				if wr < hr:
					size_side = sw
					view_side = w
				else:
					size_side = sh
					view_side = h
										
			elif mode == ZoomMode.FillView:
				# Overflow size in view in only one side
				if wr > hr:
					size_side = sw
					view_side = w
				else:
					size_side = sh
					view_side = h
			
			else:
				size_side = view_size = 1
				
		return view_side / size_side
		
	def adjust_to_pin(self, pin):
		''' Adjusts the view so that the same widget point in the pin can be
		    converted to the same absolute point in the pin '''
		(x, y), (px, py) = pin
		
		hflip, vflip = self.flipping
		if hflip:
			x *= -1
		if vflip:
			y *= -1
		
		rotation = self.rotation
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
		x, y = frame.rectangle.shift(frame.origin).unbox_point((rx, ry))
		x, y = point.spin((x, y), self.rotation / 180 * math.pi)
		
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
			hadjust.handler_block(self._hadjust_signal)
			hadjust.set_value(x)
			hadjust.handler_unblock(self._hadjust_signal)
			
		vadjust = self.get_vadjustment()
		if vadjust:
			ly, uy = vadjust.get_lower(), vadjust.get_upper()
			vh = vadjust.get_page_size()
			y = max(ly, min(uy, y))
			vadjust.handler_block(self._vadjust_signal)
			vadjust.set_value(y)
			vadjust.handler_unblock(self._vadjust_signal)
			
		self._obsolete_offset = True
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
		inv_zoom = 1 / self.magnification
		x, y = point.add(self.offset, point.scale(widget_point, inv_zoom))
		
		rotation = self.rotation
		if rotation:
			x, y = point.spin((x, y), rotation / 180 * math.pi * -1)
		
		hflip, vflip = self.flipping
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
		return self.rotation / 180 * math.pi * -1
		
	def get_magnified_width(self):
		return self.get_allocated_width() / self.magnification
		
	def get_magnified_height(self):
		return self.get_allocated_height() / self.magnification
	
	def get_filter_for_magnification(self, zoom):
		if zoom > 1:
			return self.magnify_filter
		elif zoom < 1:
			return self.minify_filter
		else:
			return None
			
	def set_filter_for_magnification(self, zoom, value):
		if zoom > 1:
			self.magnify_filter = value
		elif zoom < 1:
			self.minify_filter = value
	
	@property
	def flipping(self):
		return self.horizontal_flip, self.vertical_flip
	
	@flipping.setter
	def flipping(self, value):
		self.horizontal_flip, self.vertical_flip = value
	
	@property
	def alignment_point(self):
		return self.alignment_x, self.alignment_y
	
	@alignment_point.setter
	def alignment_point(self, value):
		self.alignment_x, self.alignment_y = value
	
	# --- basic properties down this line --- #	
	def get_hadjustment(self):
		return self._hadjustment
	def get_vadjustment(self):
		return self._vadjustment
		
	def set_hadjustment(self, adjustment):
		if self._hadjustment:
			self._hadjustment.disconnect(self._hadjust_signal)
			self._hadjust_signal = None
			
		self._hadjustment = adjustment
		if adjustment:
			adjustment.set_lower(self.outline.left)
			adjustment.set_upper(self.outline.right)
			adjustment.set_page_size(self.get_magnified_width())
			self._hadjust_signal = adjustment.connect(
			                        "value-changed", self._adjustment_changed)
			                                         
	def set_vadjustment(self, adjustment):
		if self._vadjustment:
			self._vadjustment.disconnect(self._vadjust_signal)
			self._vadjust_signal = None
			
		self._vadjustment = adjustment
		if adjustment:
			adjustment.set_lower(self.outline.top)
			adjustment.set_upper(self.outline.bottom)
			adjustment.set_page_size(self.get_magnified_height())
			self._vadjust_signal = adjustment.connect(
			                        "value-changed", self._adjustment_changed)
	
	def get_current_interpolation_filter(self):
		'''' Returns the interpolation filter for the view magnification '''
		return self.get_filter_for_magnification(self.magnification)
		
	def set_current_interpolation_filter(self, value):
		self.set_filter_for_magnification(self.magnification, value)
	
	def is_zoomed(self):
		''' Returns whether magnification does not equal one '''
		return self.magnification != 1
	
	hadjustment = GObject.property(get_hadjustment, set_hadjustment,
	                               type=Gtk.Adjustment)
	vadjustment = GObject.property(get_vadjustment, set_vadjustment,
	                               type=Gtk.Adjustment)
	                               
	hscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
	                                  default=Gtk.ScrollablePolicy.NATURAL)
	vscroll_policy = GObject.property(type=Gtk.ScrollablePolicy,
	                                  default=Gtk.ScrollablePolicy.NATURAL)
	                                  
	# This is the alignment of the outline in the widget when the outline
	# fits completely inside the widget
	alignment_x = GObject.property(type=float, default=.5)
	alignment_y = GObject.property(type=float, default=.5)
	
	# Basic view transform
	magnification = GObject.property(type=float, default=1)
	rotation = GObject.property(type=float, default=0)
	horizontal_flip = GObject.property(type=bool, default=False)
	vertical_flip = GObject.property(type=bool, default=False)
	
	minify_filter = GObject.property(type=int, default=cairo.FILTER_BILINEAR)
	magnify_filter = GObject.property(type=int, default=cairo.FILTER_NEAREST)
	
	# These two properties are used for rounding the offset for drawing
	# round_full_pixel_offset will round the offset to a multiple
	# of magnification. E.g. it only shifts 8 pixels at a time at 800% zoom.
	# round_sub_pixel_offset is more useful. It aligns one widget pixel to
	# one image pixel so that the interpolation effect doesn't change after
	# panning the images.
	round_full_pixel_offset = GObject.property(type=bool, default=False)
	round_sub_pixel_offset = GObject.property(type=bool, default=True)
	
	zoomed = GObject.property(is_zoomed, type=bool, default=False)
	current_interpolation_filter = GObject.property(
	                               get_current_interpolation_filter,
	                               set_current_interpolation_filter,
	                               type=int)
	# --- computing stuff down this line --- #	
	
	def _compute_adjustments(self):
		''' Figure out lower, upper and page size of adjustments.
		    Also clamp them. Clamping is important. '''
		    
		# Name's Bounds, James Bounds
		bounds = self.outline.flip(*self.flipping)
		bounds = bounds.spin(self.rotation / 180 * math.pi)
		hadjust, vadjust = self.get_hadjustment(), self.get_vadjustment()
		if hadjust:
			hadjust.freeze_notify()
			
			hadjust.set_lower(bounds.left)
			hadjust.set_upper(bounds.right)
			
			# Set page size, get and align value
			visible_span = min(self.get_magnified_width(), bounds.width)
			visible_diff = hadjust.get_page_size() - visible_span
			hadjust.set_page_size(visible_span)
			value = hadjust.get_value() + visible_diff * self.alignment_x
						
			# Clamp value
			max_value = hadjust.get_upper() - hadjust.get_page_size()
			min_value = hadjust.get_lower()
			clamped_value = min(max_value, max(min_value, value))
			hadjust.set_value(clamped_value)
			
			hadjust.thaw_notify()
		if vadjust:
			vadjust.freeze_notify()
			
			vadjust.set_lower(bounds.top)
			vadjust.set_upper(bounds.bottom)
			
			# Set page size, get and align value
			visible_span = min(self.get_magnified_height(), bounds.height)
			visible_diff = vadjust.get_page_size() - visible_span
			vadjust.set_page_size(visible_span)
			value = vadjust.get_value() + visible_diff * self.alignment_y
			
			# Clamp value
			max_value = vadjust.get_upper() - vadjust.get_page_size()
			min_value = vadjust.get_lower()
			clamped_value = min(max_value, max(min_value, value))
			vadjust.set_value(clamped_value)
			
			vadjust.thaw_notify()
			
		self._obsolete_offset = True
			
	def _compute_offset(self):
		''' Figures out the x, y offset based on the adjustments '''
		x, y = self.offset
		hadjust = self.get_hadjustment()
		if hadjust:
			upper, lower = hadjust.get_upper(), hadjust.get_lower()
			span = upper - lower
			diff = span - self.get_magnified_width()
			if diff > 0:
				x = hadjust.get_value()
			else:
				x = lower + diff * self.alignment_x
								
		vadjust = self.get_vadjustment()
		if vadjust:
			upper, lower = vadjust.get_upper(), vadjust.get_lower()
			span = upper - lower
			diff = span - self.get_magnified_height()
			if diff > 0:
				y = vadjust.get_value()
			else:
				y = lower + diff * self.alignment_y
				
		self._obsolete_offset = False
		self.offset = x, y
		GLib.idle_add(self.emit, "offset-change", priority=GLib.PRIORITY_HIGH)
	
	# --- event stuff down this line --- #
	def _frame_changed(self, *some_data_we_are_not_gonna_use_anyway):
		''' Callback for when a picture frame surface changes '''
		self.refresh_outline.queue()
		self.queue_draw()
	
	def _adjustment_changed(self, data):
		self._obsolete_offset = True
		self.queue_draw()


	def _matrix_changed(self, *data):
		# I saw a black cat walk by. Twice.
		self._compute_adjustments()
		self.queue_draw()
		self.emit("transform-change")
	
	
	def _interpolation_changed(self, *data):
		self.queue_draw()
	
	
	def _magnification_changed(self, *data):
		''' handler for notify::magnification '''
		old_sign, filter_handler_id = self._magnification_watch
		mag = self.magnification
		changed = False
		if mag < 1:
			if old_sign >= 0:
				changed = True
				sign = -1
				new_handler_id = self.connect("notify::minify-filter",
				                              self._notify_interpolation_filter)
				
		elif mag > 1:
			if old_sign <= 0:
				changed = True
				sign = 1
				new_handler_id = self.connect("notify::magnify-filter",
				                              self._notify_interpolation_filter)
				
		else:
			if old_sign != 0:
				sign = 0
				changed = True
				new_handler_id = None
		
		if changed:
			if filter_handler_id:
				self.disconnect(filter_handler_id)
				
			self._magnification_watch = sign, new_handler_id
			if sign != 0:
				self._notify_interpolation_filter()
			
			if (sign == 0) != (old_sign == 0):
				self.notify("zoomed")

	def _notify_interpolation_filter(self, *data):
		self.notify("current-interpolation-filter")
	

	def do_size_allocate(self, allocation):
		Gtk.DrawingArea.do_size_allocate(self, allocation)
		self._compute_adjustments()
	

	class DrawState:
		''' Caches a bunch of properties '''
		def __init__(self, view):
			self.view = view
			self.magnification = zoom = view.magnification
			
			ox, oy = view.offset
			if(zoom > 1 and view.round_full_pixel_offset):
				# Round pixel offset, removing pixel fractions from it
				ox, oy = round(ox), round(oy)
				
			if(zoom != 1 and view.round_sub_pixel_offset):
				# Round offset to match pixels shown on display using
				# inverse magnification
				invzoom = 1 / zoom
				ox, oy = ox // invzoom * invzoom, oy // invzoom * invzoom
				
			self.offset = ox, oy
			self.translation = -ox, -oy
			self.rotation = view.rotation
			self.rad_rotation = self.rotation / 180 * math.pi
			
			self.hflip, self.vflip = self.flip = view.flipping
			self.is_flipped = self.hflip or self.vflip
			
			self.magnify_filter = view.magnify_filter
			self.minify_filter = view.minify_filter
			
			self.size = self.width, self.height = (
				view.get_allocated_width(),
				view.get_allocated_height()
			)
			
		def get_filter_for_magnification(self, zoom):
			if zoom > 1:
				return self.magnify_filter
			elif zoom < 1:
				return self.minify_filter
			else:
				return None		
	
	def do_draw(self, cr):
		''' Draws everything! '''
		if self._obsolete_offset:
			self._compute_offset()
		
		drawstate = ImageView.DrawState(self)
		
		# Renders the BG. Not sure if it works
		style = self.get_style_context()
		Gtk.render_background(style, cr, 0, 0, *drawstate.size)
		
		cr.save()
			
		# Apply the zooooooom
		cr.scale(drawstate.magnification, drawstate.magnification)
		# Translate the offset
		cr.translate(*drawstate.translation)
		# Rotate the radians
		cr.rotate(drawstate.rad_rotation)
		# Flip the... thing
		if drawstate.is_flipped:
			cr.scale(-1 if drawstate.hflip else 1,
			         -1 if drawstate.vflip else 1)
		# Yes, this supports multiple frames!
		# No, we don't use that feature... not yet.
		for a_frame in self._frames:
			cr.save()
			try:
				cr.translate(*a_frame.origin)
				a_frame.draw(cr, drawstate)
			
			except Exception:
				raise
				
			cr.restore()
		
		cr.restore()
		Gtk.render_frame(style, cr, 0, 0, *drawstate.size)
		
# --- Image frames related code down this line --- #

class ImageFrame(GObject.GObject):
	''' Contains a image '''
	
	# TODO: Implement rotation and scale
	def __init__(self):
		GObject.GObject.__init__(self)
		self.size = 0, 0
		self.rectangle = point.Rectangle()
		self.origin = 0, 0
	
	def added(self, view):
		pass
		
	def removed(self, view):
		pass
	
	def draw(self, cr, drawstate):
		raise NotImplementedError
		
	origin = GObject.property(type=GObject.TYPE_PYOBJECT)
	
class ImageSurfaceFrame(ImageFrame):
	def __init__(self, surface):
		ImageFrame.__init__(self)
		self.connect("notify::surface", self._surface_changed)
		self.surface = surface
	
	def draw(self, cr, drawstate):
		if self.surface:
			offset = point.multiply(self.size, (-.5, -.5))
			cr.set_source_surface(self.surface, *offset)
			
			# Set filter
			a_pattern = cr.get_source()
			zoom = drawstate.magnification
			a_filter = drawstate.get_filter_for_magnification(zoom)
			if a_filter is not None:
				a_pattern.set_filter(a_filter)
		
			cr.paint()
			
	surface = GObject.property(type=GObject.TYPE_PYOBJECT)
	def _surface_changed(self, *args):
		if self.surface:
			w, h = self.surface.get_width(), self.surface.get_height()
			self.rectangle = point.Rectangle(-w/2, -h/2, w, h)
			self.size = w, h
		else:
			self.size = 0, 0
			self.rectangle = point.Rectangle()
			
class AnimatedPixbufFrame(ImageFrame):
	def __init__(self, animation):
		ImageFrame.__init__(self)
		self.connect("notify::animation", self._animation_changed)
		self.animation = animation
		self._view_anim = dict()
	
	def added(self, view):
		anim_iter, anim_handle = self._view_anim.get(view, (None, None))
		if anim_handle:
			GLib.source_remove(anim_handle)
			anim_handle = None
		
		try:
			anim_iter = self.animation.get_iter(None)
			self._view_anim[view] = anim_iter, anim_handle
			self._schedule_advance(view)			
			
		except Exception:
			self._view_anim[view] = anim_iter, anim_handle
	
	def removed(self, view):
		anim_iter, anim_handle = self._view_anim[view]
		if anim_handle:
			GLib.source_remove(anim_handle)
			
		del self._view_anim[view]
	
	def _advance_animation(self, view):
		anim_iter, anim_handle = self._view_anim[view]
		anim_iter.advance(None)
		self._view_anim[view] = anim_iter, None
		
		view.queue_draw()
		
		self._schedule_advance(view)
		
	def _schedule_advance(self, view):
		anim_iter, anim_handle = self._view_anim[view]
		delay = anim_iter.get_delay_time()
		
		if delay != -1:
			anim_handle = GLib.timeout_add(delay, self._advance_animation, view)
			self._view_anim[view] = anim_iter, anim_handle
	
	def draw(self, cr, drawstate):
		anim_iter, anim_handle = self._view_anim[drawstate.view]
		pixbuf = anim_iter.get_pixbuf()
		if pixbuf:
			offset = point.multiply(self.size, (-.5, -.5))
			Gdk.cairo_set_source_pixbuf(cr, pixbuf, *offset)
			
			# Set filter
			a_pattern = cr.get_source()
			zoom = drawstate.magnification
			a_filter = drawstate.get_filter_for_magnification(zoom)
			if a_filter is not None:
				a_pattern.set_filter(a_filter)
		
			cr.paint()
				
	animation = GObject.property(type=GObject.TYPE_PYOBJECT)
	def _animation_changed(self, *args):
		if self.animation:
			w, h = self.animation.get_width(), self.animation.get_height()
			self.rectangle = point.Rectangle(-w/2, -h/2, w, h)
			self.size = w, h
		else:
			self.rectangle = point.Rectangle()
			self.size = 0, 0
	
def SurfaceFromPixbuf(pixbuf):
	''' Creates a cairo surface from a Gdk pixbuf'''
	surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
		                         pixbuf.get_width(),
		                         pixbuf.get_height())
	cr = cairo.Context(surface)
	Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
	cr.paint()
	
	return surface
