'''
	Some panning interface related code
'''

import gtk

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
			gtk.gdk.LEAVE_NOTIFY_MASK |
			gtk.gdk.POINTER_MOTION_MASK |
			gtk.gdk.POINTER_MOTION_HINT_MASK)
			
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
	'''
	def __init__(self, imageview):
		self.imageview = imageview
		
		# Setup events
		imagevp = imageview.get_child() # this should be the viewport between image and scrolledwindow
		imagevp.set_events(imagevp.get_events() | 
			gtk.gdk.POINTER_MOTION_MASK |
			gtk.gdk.POINTER_MOTION_HINT_MASK)
			
		imagevp.connect("motion_notify_event", self.motion)	
			
	def motion(self, widget, data=None):
		x, y = data.x, data.y
			
		hadjust, vadjust = self.imageview.props.hadjustment, self.imageview.props.vadjustment
		vx, vy = x - hadjust.props.value, y - vadjust.props.value
		vw, vh = hadjust.props.page_size, vadjust.props.page_size
		
		rx, ry = (hadjust.props.upper - vw) - hadjust.props.lower, (vadjust.props.upper - vh) - vadjust.props.lower
		
		if vx > vw:
			vx = vw

		if vy > vh:
			vy = vh
		
		print vx, vh, rx
		
		hadjust.props.value, vadjust.props.value = int(float(vx) / vw * rx), int(float(vy) / vh * ry)
		'''
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
			self.last_step = (x, y)'''
