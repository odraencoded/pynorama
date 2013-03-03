'''
	Some panning interface related code
'''

from gi.repository import Gtk, Gdk

class SlideNavigator:
	'''
		This navigator adjusts the view based on only mouse movement
	'''
	def __init__(self, imageview):
		self.imageview = imageview
		
		self.sliding = False
		self.last_step = True
		
		# Setup events
		imagevp = imageview.get_child() # this should be the viewport between image and scrolledwindow
		imagevp.set_events(imagevp.get_events() | 
			Gdk.EventMask.LEAVE_NOTIFY_MASK |
			Gdk.EventMask.POINTER_MOTION_MASK |
			Gdk.EventMask.POINTER_MOTION_HINT_MASK)
			
		imagevp.connect("motion_notify_event", self.motion)	
		imagevp.connect("leave_notify_event", self.leave)
			
	def leave(self, widget, data=None):
		self.sliding = False
		self.last_step = None
	
	def motion(self, widget, data=None):
		x, y = data.x, data.y
		
		if self.imageview.pixbuf and self.sliding:
			dx, dy = x - self.last_step[0], y - self.last_step[1]
			hadjust, vadjust = self.imageview.props.hadjustment, self.imageview.props.vadjustment
			
			if (dx or dy):
				nx = hadjust.props.value + dx
				if nx > hadjust.props.upper - hadjust.props.page_size:
					nx = hadjust.props.upper - hadjust.props.page_size
					
				ny = vadjust.props.value + dy;
				if ny > vadjust.props.upper - vadjust.props.page_size:
					ny = vadjust.props.upper - vadjust.props.page_size
				px = hadjust.props.value
				hadjust.props.value = nx
				dx = hadjust.props.value - px
				
				py = vadjust.props.value
				vadjust.props.value = ny
				dy = vadjust.props.value - py
				
				# Updates last step using the previous x, y and the change in adjustment
				self.last_step = (x + dx, y + dy)
		else:
			self.sliding = True
			self.last_step = (x, y)
		
class MapNavigator:
	'''
		This navigator adjusts the view so that the adjustment of the image in the view is equal to the mouse position for the view
		
		The map mode is either of the following:
		"stretch": The pointer position is divided by the viewport size and then scaled to the image size
		"square": The pointer position is clamped and divided by a square whose side is the smallest of the viewport sides(width or height) and then scaled to the image size
		"proportional": The pointer position is clamped and divided by a rectangle proportional to the image size and then to the image size
		
		The margin value is used to clamp before scaling
	'''
		
	def __init__(self, imageview):
		self.imageview = imageview
		self.mode = "proportional"
		self.margin = 32
		
		# Setup events
		self.imageview.connect("scroll-event", self.scrolling)
		
		imagevp = imageview.get_child() # this should be the viewport between image and scrolledwindow
		imagevp.set_events(imagevp.get_events() | 
			Gdk.EventMask.POINTER_MOTION_MASK |
			Gdk.EventMask.POINTER_MOTION_HINT_MASK |
			Gdk.EventMask.SCROLL_MASK)
		
		if imagevp.get_realized():
			self.realize_handle_id = None
			self.set_cursor(None, imagevp)
		else:
			self.realize_handle_id = imagevp.connect("realize", self.set_cursor, imagevp)
		
		imagevp.connect("motion-notify-event", self.refresh_adjustments)
		
		image = imagevp.get_child() # this should be the image
		image.connect("size-allocate", self.refresh_adjustments)
		
		self.refresh_adjustments()
			
	def set_cursor(self, data=None, imagevp=None):
		# Sets the cursor to a crosshair
		imagevp.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.CROSSHAIR))
		if self.realize_handle_id is not None:
			imagevp.disconnect(self.realize_handle_id)
	
	def get_scalar_rectangle(self):
		rect = None
		allocation = self.imageview.get_allocation()
		if self.mode == "square":
			if allocation.width > allocation.height:
				smallest_side = allocation.height
			else:
				smallest_side = allocation.width
			
			half_width_diff = (allocation.width - smallest_side) // 2
			half_height_diff = (allocation.height - smallest_side) // 2
			
			rect_tuple = (
				half_width_diff, half_height_diff,
				allocation.width - half_width_diff * 2, allocation.height - half_height_diff * 2
			)
			
		elif self.mode == "proportional":
			hadjust, vadjust = self.imageview.props.hadjustment, self.imageview.props.vadjustment
			vw, vh = hadjust.props.upper, vadjust.props.upper
			vw_ratio, vh_ratio = float(allocation.width) / vw, float(allocation.height) / vh
			
			if vw_ratio > vh_ratio:
				smallest_ratio = vh_ratio
			else:
				smallest_ratio = vw_ratio
				
			tw, th = int(smallest_ratio * vw), int(smallest_ratio * vh)
			
			half_width_diff = (allocation.width - tw) // 2
			half_height_diff = (allocation.height - th) // 2
			
			rect_tuple = (
				half_width_diff, half_height_diff,
				allocation.width - half_width_diff * 2, allocation.height - half_height_diff * 2
			)
			
		else:
			rect = allocation
		
		if rect is None:
			rect = Gdk.Rectangle()
			rect.x, rect.y, rect.width, rect.height = rect_tuple
					
		if rect.width > self.margin * 2:		
			if rect.x < self.margin:
				rect.width -= self.margin - rect.x
				rect.x = self.margin
			
			if allocation.width - (rect.x + rect.width) < self.margin:
				rect.width = allocation.width - rect.x - self.margin
				
		if rect.height > self.margin * 2:		
			if rect.y < self.margin:
				rect.height -= self.margin - rect.y
				rect.y = self.margin
			
			if allocation.height - (rect.y + rect.height) < self.margin:
				rect.height = allocation.height - rect.y - self.margin
				
		return rect

	def scrolling(self, widget, data=None):
		image = self.imageview.get_child().get_child()
		
		if data.direction == Gdk.ScrollDirection.UP:
			image.magnification += 1
			image.refresh_pixbuf()
		
		if data.direction == Gdk.ScrollDirection.DOWN:
			image.magnification -= 1
			image.refresh_pixbuf()
		
		self.refresh_adjustments()
		
		# Makes the scrolled window not scroll
		return True
			
	def refresh_adjustments(self, widget=None, data=None):
		imagevp = self.imageview.get_child()
		image = imagevp.get_child()
		
		x, y = self.imageview.get_pointer()
		rect = self.get_scalar_rectangle()
			
		allocation = self.imageview.get_allocation()
		
		hadjust, vadjust = self.imageview.props.hadjustment, self.imageview.props.vadjustment
		vw, vh = hadjust.props.upper - hadjust.props.page_size, vadjust.props.upper - vadjust.props.page_size
				
		# Shift and clamp x and y
		x -= rect.x
		if x < 0:
			x = 0
		elif x > rect.width:
			x = rect.width
		
		y -= rect.y
		if y < 0:
			y = 0
		elif y > rect.height:
			y = rect.height
		
		# Transform x and y to picture "adjustment" coordinates
		tx, ty = int(float(x) / rect.width * vw), int(float(y) / rect.height * vh)
		
		hadjust.props.value, vadjust.props.value = tx, ty
