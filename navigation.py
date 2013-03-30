'''
	Some panning interface related code
'''

from gi.repository import Gtk, Gdk, GObject, GLib
from gettext import gettext as _
import math, time

NaviList = []

class DragNavi:
	''' This navigator adjusts the view based on only mouse movement '''
	def __init__(self, imageview):
		self.imageview = imageview
		
		self.dragging = False
		self.last_step = None
		self.margin_handling_ref = None
		self.moving_timestamp = None
		
		# Setup events
		self.imageview.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
			Gdk.EventMask.BUTTON_RELEASE_MASK |
			Gdk.EventMask.POINTER_MOTION_MASK |
			Gdk.EventMask.POINTER_MOTION_HINT_MASK)
		
		self.view_handlers = [
			self.imageview.connect("button-press-event", self.button_press),
			self.imageview.connect("button-release-event", self.button_release),
			self.imageview.connect("motion-notify-event", self.motion_event)
			]
		
	def detach(self):
		for handler in self.view_handlers:
			self.imageview.disconnect(handler)
			
		self.imageview.get_bin_window().set_cursor(None)
	
	def button_press(self, widget, data):
		if data.button == 1:
			self.dragging = True
			self.last_step = self.imageview.get_pointer()
			self.imageview.get_bin_window().set_cursor(Gdk.Cursor(Gdk.CursorType.FLEUR))
			
			if self.margin_handling_ref is None and self.check_margin(False):
				self.attach_timeout()
			
	def button_release(self, widget, data):
		if data.button == 1:
			self.dragging = False
			self.last_step = None
			self.imageview.get_bin_window().set_cursor(None)
			
			if self.margin_handling_ref is not None:
				self.remove_timeout()
				
	def attach_timeout(self):
		self.margin_handling_ref = GLib.timeout_add(int(1000 * DragNavi.Frequency), self.margin_handler)
		self.moving_timestamp = time.time()
		
	def remove_timeout(self):
		self.moving_timestamp = None
		GLib.source_remove(self.margin_handling_ref)
		self.margin_handling_ref = None
		
	def motion_event(self, widget, data):		
		x, y = self.imageview.get_pointer()
		if self.dragging:
			if self.check_margin(False):
				if self.margin_handling_ref is None:
					self.attach_timeout()
			
			elif self.margin_handling_ref is not None:
				self.remove_timeout()
				self.imageview.get_bin_window().set_cursor(Gdk.Cursor(Gdk.CursorType.FLEUR))
			
			if self.margin_handling_ref is None and self.last_step:
				dx, dy = self.last_step
				dx, dy = int((x - dx) * DragNavi.Speed), int((y - dy) * DragNavi.Speed)
				
				if dx:
					hadjust = self.imageview.get_hadjustment()
					vw = hadjust.get_upper() - hadjust.get_page_size()
			
					nx = hadjust.get_value() + dx
			
					if nx < hadjust.get_lower():
						nx = hadjust.get_lower()
					if nx > vw:
						nx = vw
				
					hadjust.set_value(nx)
					self.imageview.set_hadjustment(hadjust)
				else:
					x = self.last_step[0]
			
				if dy:
					vadjust = self.imageview.get_vadjustment()
					vh = vadjust.get_upper() - vadjust.get_page_size()
			
					ny = vadjust.get_value() + dy
			
					if ny < vadjust.get_lower():
						ny = vadjust.get_lower()
					if ny > vh:
						ny = vh
				
					vadjust.set_value(ny)
					self.imageview.set_vadjustment(vadjust)
			
				else:
					y = self.last_step[1]
				
		self.last_step = x, y
		
		return True
		
	def margin_handler(self):
		return self.check_margin(True)
		
	def check_margin(self, move):
		x, y = self.imageview.get_pointer()
		allocation = self.imageview.get_allocation()
		
		if allocation.width > DragNavi.Margin * 2:
			xmargin = DragNavi.Margin
		else:
			xmargin = allocation.width / 2
		
		if allocation.height > DragNavi.Margin * 2:
			ymargin = DragNavi.Margin
		else:
			ymargin = allocation.height / 2
		
		if move:
			xshift = yshift = 0
			if x < xmargin:
				xshift = -1
				
			elif x > allocation.width - xmargin:
				xshift = 1
				
			if y < ymargin:
				yshift = -1
			
			elif y > allocation.height - ymargin:
				yshift = 1
			
			elif xshift and allocation.height > ymargin * 4:
				if y < ymargin * 2:
					yshift = -1
				elif y > allocation.height - ymargin * 2:
					yshift = 1
				
			if not xshift and yshift and allocation.width > xmargin * 4:
				if x < xmargin * 2:
					xshift = -1
				elif x > allocation.width - xmargin * 2:
					xshift = 1
			
			if xshift or yshift:
				cursor_type = None
				
				if xshift < 0:
					if yshift < 0:
						cursor_type = Gdk.CursorType.TOP_LEFT_CORNER
					elif yshift > 0:
						cursor_type = Gdk.CursorType.BOTTOM_LEFT_CORNER
					else:
						cursor_type = Gdk.CursorType.LEFT_SIDE
				elif xshift > 0:
					if yshift < 0:
						cursor_type = Gdk.CursorType.TOP_RIGHT_CORNER
					elif yshift > 0:
						cursor_type = Gdk.CursorType.BOTTOM_RIGHT_CORNER
					else:
						cursor_type = Gdk.CursorType.RIGHT_SIDE
				elif yshift < 0:
					cursor_type = Gdk.CursorType.TOP_SIDE
				elif yshift > 0:
					cursor_type = Gdk.CursorType.BOTTOM_SIDE
					
				self.imageview.get_bin_window().set_cursor(Gdk.Cursor(cursor_type))
				
				relatively_current_time = time.time()
				delta_time = relatively_current_time - self.moving_timestamp
				self.moving_timestamp = relatively_current_time
				
				xshift = xshift * delta_time * DragNavi.ContinuousSpeed * DragNavi.Speed
				yshift = yshift * delta_time * DragNavi.ContinuousSpeed * DragNavi.Speed
				
				hadjust = self.imageview.get_hadjustment()
				vadjust = self.imageview.get_vadjustment()
				for adjust, shift in ((hadjust, xshift), (vadjust, yshift)):
					new_value = adjust.get_value() + shift
					new_value = max(adjust.get_lower(),
					                min(adjust.get_upper() - adjust.get_page_size(),
					                new_value))
					
					adjust.set_value(new_value)
				
				return True
								
			else:
				self.moving_timestamp = None
				return False
			
		else:
			return x < xmargin or x > allocation.width - xmargin or \
				y < ymargin or y > allocation.height - ymargin
					
	Speed = -1.0
	ContinuousSpeed = 200
	Margin = 32
	Frequency = 0.05
	
	@staticmethod
	def create(imageview):
		return DragNavi(imageview)
	
	@staticmethod
	def get_name():
		return _("Drag")
	
	@staticmethod
	def get_settings_widgets():
		widgets = Gtk.Grid()
		widgets.set_column_spacing(20)
		widgets.set_row_spacing(5)
		
		# Someone should look up whether it is speed or velocity...
		# Then again we got no inertia here so whatever :D
		speed = Gtk.SpinButton()
		speed_label = Gtk.Label(_("Dragging speed"))
		speed_label.set_alignment(0, 0.5)
		speed_label.set_hexpand(True)
		speed.set_adjustment(Gtk.Adjustment(abs(DragNavi.Speed), 0.1, 10, 0.3, 2, 0))
		speed.set_digits(1)
		widgets.attach(speed_label, 0, 0, 1, 1)
		widgets.attach(speed, 1, 0, 1, 1)
		widgets.speed = speed
		
		# Unexpected dragging mode is unexpected.
		# Maybe I should have allowed for negative speed instead...
		image_drag = Gtk.RadioButton(_("Drag the image"))
		image_drag.set_alignment(0, 0.5)
		view_drag = Gtk.RadioButton(_("Drag the view"))
		view_drag.set_alignment(0, 0.5)
		view_drag.join_group(image_drag)
		
		if DragNavi.Speed < 0:
			image_drag.set_active(True)
		else:
			view_drag.set_active(True)
			
		mode_row = Gtk.HBox()
		mode_row.pack_start(image_drag, False, True, 10)
		mode_row.pack_start(view_drag, False, True, 10)
		
		widgets.attach(mode_row, 0, 1, 2, 1)
		widgets.drag_modes = { "image":image_drag, "view":view_drag }
		
		# If the mouse is pressed in the margin, it starts dragging... CONTINUOUSLY
		margin_label = Gtk.Label(_("Continuous dragging margin"))
		margin_label.set_alignment(0, 0.5)
		margin = Gtk.SpinButton()
		margin.set_adjustment(Gtk.Adjustment(DragNavi.Margin, 0, 128, 1, 8, 0))
		widgets.attach(margin_label, 0, 3, 1, 1)
		widgets.attach(margin, 1, 3, 1, 1)
		widgets.margin = margin
		
		# Continuous dragging "speed". Don't even ask me how this works.
		cont_speed_label = Gtk.Label(_("Continuous dragging speed"))
		cont_speed_label.set_alignment(0, 0.5)
		cont_speed = Gtk.SpinButton()
		cont_speed.set_adjustment(Gtk.Adjustment(DragNavi.ContinuousSpeed, 0, 5000, 10, 50, 0))
		widgets.attach(cont_speed_label, 0, 4, 1, 1)
		widgets.attach(cont_speed, 1, 4, 1, 1)
		widgets.cont_speed = cont_speed
		
		# What am I doing here...
		widgets.save_settings = DragNavi.apply_settings.__get__(widgets, None)
		
		return widgets

	@staticmethod
	def apply_settings(widgets):
		DragNavi.Margin = widgets.margin.get_value()
		
		if widgets.drag_modes["image"].get_active():
			DragNavi.Speed = widgets.speed.get_value() * -1
		else:
			DragNavi.Speed = widgets.speed.get_value()
			
		DragNavi.ContinuousSpeed = widgets.cont_speed.get_value()
		
class RollNavi:
	''' This navigator is almost the same as the DragNavi,
	    except without the dragging part '''
	def __init__(self, imageview):
		self.imageview = imageview
		
		self.roller_ref = None
		self.pointer = None
		self.movement_timestamp = None
		# Setup events
		self.imageview.add_events(
			Gdk.EventMask.LEAVE_NOTIFY_MASK |
			Gdk.EventMask.POINTER_MOTION_MASK |
			Gdk.EventMask.POINTER_MOTION_HINT_MASK)
		
		self.view_handlers = [
			self.imageview.connect("motion-notify-event", self.motion_event),
			self.imageview.connect("leave-notify-event", self.leave_event)
			]
	
	def detach(self):
		for handler in self.view_handlers:
			self.imageview.disconnect(handler)
			
		self.imageview.get_bin_window().set_cursor(None)
	
	def attach_timeout(self):
		self.roller_ref = GLib.timeout_add(int(1000 * RollNavi.Frequency), self.roll)
		self.movement_timestamp = time.time()
	
	def remove_timeout(self):
		GLib.source_remove(self.roller_ref)
		self.roller_ref = None
		self.movement_timestamp = None
	
	def motion_event(self, widget, data):
		# Get the mouse position relative to the center of the imageview
		allocation = self.imageview.get_allocation()
		w, h = allocation.width, allocation.height
		mx, my = self.imageview.get_pointer()
		rx, ry = mx - (w / 2), my - (h / 2)
		# The size of the "sphere"
		r = w / 2 if w > h else h  / 2
		r = max(r - RollNavi.Margin, 1)
		# The distance, aka vector length
		d = (rx ** 2 + ry ** 2) ** 0.5
		self.pointer = rx, ry, d, r
		
		# Check whether it is rolling
		rolling = False
		if d >= RollNavi.Threshold:
			rolling = True
			
		elif mx < RollNavi.Margin or my < RollNavi.Margin or mx > w - RollNavi.Margin or my > h - RollNavi.Margin:
			rolling = True
			
		if rolling:
			# Create a timeout callback if one doesn't exist
			if self.roller_ref is None:
				self.attach_timeout()
			# Trigonometricksf
			angle = math.atan2(rx, ry)
			angle_index = int(round((angle + math.pi) / (math.pi / 4) - 1))
			cursor_type = (
				Gdk.CursorType.TOP_LEFT_CORNER, 
				Gdk.CursorType.LEFT_SIDE,
				Gdk.CursorType.BOTTOM_LEFT_CORNER,
				Gdk.CursorType.BOTTOM_SIDE,
				Gdk.CursorType.BOTTOM_RIGHT_CORNER,
				Gdk.CursorType.RIGHT_SIDE,
				Gdk.CursorType.TOP_RIGHT_CORNER,
				Gdk.CursorType.TOP_SIDE,
				 )[angle_index]
			
			self.imageview.get_bin_window().set_cursor(Gdk.Cursor(cursor_type))
		else:
			# Cancel timeout callback
			if self.roller_ref is not None:
				self.remove_timeout()
				
			# Reset cursor
			self.imageview.get_bin_window().set_cursor(None)
			
	def leave_event(self, widget, data):
		self.pointer = None
		if self.roller_ref is not None:
			GLib.source_remove(self.roller_ref)
			self.roller_ref = None
			
	def roll(self): # 'n rock
		if self.pointer is None:
			return False
		
		# Calculate roll speed
		rx, ry, d, r = self.pointer
		s = min(1, (d - RollNavi.Threshold) / (r - RollNavi.Threshold))
		s = 1 - (1 - s) ** 3
		s *= RollNavi.Speed
		sx, sy = [min(1, max(-1, v / r)) * s for v in (rx, ry) ]
		# Apply delta
		relatively_current_time = time.time()
		delta_time = relatively_current_time - self.movement_timestamp
		self.movement_timestamp = relatively_current_time
		sx, sy = sx * delta_time, sy * delta_time
		# Move the thing
		hadjust, vadjust = self.imageview.get_hadjustment(), self.imageview.get_vadjustment()
		
		for adjust, offset in ((hadjust, sx), (vadjust, sy)):
			new_value = adjust.get_value() + offset
			new_value = max(adjust.get_lower(), min(adjust.get_upper() - adjust.get_page_size(), new_value))
			
			adjust.set_value(new_value)
			
		return True
		
	Frequency = 0.05
	Threshold = 32
	Speed = 200
	Margin = 32
	
	@staticmethod
	def create(imageview):
		return RollNavi(imageview)
	
	@staticmethod
	def get_name():
		return _("Roll")
	
	@staticmethod
	def get_settings_widgets():
		widgets = Gtk.Grid()
		widgets.set_column_spacing(20)
		widgets.set_row_spacing(5)
		
		# This is the speed on and after the edge of the sphere
		speed_label = Gtk.Label(_("Maximum rolling speed"))
		speed_label.set_alignment(0, 0.5)
		speed_label.set_hexpand(True)
		speed = Gtk.SpinButton()
		speed.set_adjustment(Gtk.Adjustment(RollNavi.Speed, 10, 2000, 20, 200, 0))
		widgets.attach(speed_label, 0, 0, 1, 1)
		widgets.attach(speed, 1, 0, 1, 1)
		widgets.speed = speed
		
		# Margins!
		margin_label = Gtk.Label(_("Sphere margin"))
		margin_label.set_alignment(0, 0.5)
		margin = Gtk.SpinButton()
		margin.set_adjustment(Gtk.Adjustment(RollNavi.Margin, 0, 128, 1, 8, 0))
		widgets.attach(margin_label, 0, 1, 1, 1)
		widgets.attach(margin, 1, 1, 1, 1)
		widgets.margin = margin
		
		# Sometimes you want to settle down, the middle
		threshold_label = Gtk.Label(_("Activation distance"))
		threshold_label.set_alignment(0, 0.5)
		threshold = Gtk.SpinButton()
		threshold.set_adjustment(Gtk.Adjustment(RollNavi.Threshold, 0, 256, 4, 16, 0))
		widgets.attach(threshold_label, 0, 2, 1, 1)
		widgets.attach(threshold, 1, 2, 1, 1)
		widgets.threshold = threshold
		
		# I still don't have the slightest idea of what I'm doing here
		widgets.save_settings = RollNavi.apply_settings.__get__(widgets, None)
		
		return widgets
		
	@staticmethod
	def apply_settings(widgets):
		RollNavi.Threshold = widgets.threshold.get_value()
		RollNavi.Speed = widgets.speed.get_value()
		RollNavi.Margin = widgets.margin.get_value()
		
class MapNavi:
	''' This navigator adjusts the view so that the adjustment of the image in the view is equal to the mouse position for the view
	    
	    The map mode is either of the following:
	    "stretched": The pointer position is divided by the viewport size and then scaled to the image size
	    "square": The pointer position is clamped and divided by a square whose side is the smallest of the viewport sides(width or height) and then scaled to the image size
	    "proportional": The pointer position is clamped and divided by a rectangle proportional to the image size and then to the image size
	    
	    The margin value is used to clamp before scaling '''
		
	def __init__(self, imageview):
		self.imageview = imageview
				
		# Setup events
		self.imageview.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
			Gdk.EventMask.BUTTON_PRESS_MASK |
			Gdk.EventMask.BUTTON_RELEASE_MASK |
			Gdk.EventMask.POINTER_MOTION_HINT_MASK)
		
		self.view_handlers = [
			self.imageview.connect("button-press-event", self.button_press),
			self.imageview.connect("button-release-event", self.button_release),
			self.imageview.connect("motion-notify-event", self.mouse_motion)
			]
			
		self.imageview.get_bin_window().set_cursor(Gdk.Cursor(Gdk.CursorType.CROSSHAIR))
		
		image = self.imageview.image
		self.image_handlers = [image.connect("size-allocate", self.refresh_adjustments)]
		
		self.clicked = False
		self.refresh_adjustments()
		
	def detach(self):		
		for handler in self.view_handlers:
			self.imageview.disconnect(handler)
		
		image = self.imageview.image
		for handler in self.image_handlers:
			image.disconnect(handler)
			
		self.imageview.get_bin_window().set_cursor(None)
	
	def button_press(self, widget=None, data=None):
		if data.button == 1:
			if not self.clicked:
				self.refresh_adjustments()
			
			self.clicked = True
		
	def button_release(self, widget=None, data=None):
		if data.button == 1:
			self.clicked = False
	
	def mouse_motion(self, widget=None, data=None):
		if not MapNavi.RequireClick or self.clicked:
			self.refresh_adjustments()
	
	def get_map_rectangle(self):
		allocation = self.imageview.get_allocation()
		
		allocation.x = allocation.y = MapNavi.Margin
		allocation.width -= MapNavi.Margin * 2
		allocation.height -= MapNavi.Margin * 2
		
		if allocation.width <= 0:
			diff = 1 - allocation.width
			allocation.width += diff
			allocation.x -= diff / 2
			
		if allocation.height <= 0:
			diff = 1 - allocation.height
			allocation.height += diff
			allocation.y -= diff / 2
		
		if MapNavi.MapMode == "square":
			if allocation.width > allocation.height:
				smallest_side = allocation.height
			else:
				smallest_side = allocation.width
			
			half_width_diff = (allocation.width - smallest_side) // 2
			half_height_diff = (allocation.height - smallest_side) // 2
			
			rect_tuple = (
				allocation.x + half_width_diff, allocation.y + half_height_diff,
				allocation.width - half_width_diff * 2, allocation.height - half_height_diff * 2
			)
			
		elif MapNavi.MapMode == "proportional":
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
				allocation.x + half_width_diff, allocation.y + half_height_diff,
				allocation.width - half_width_diff * 2, allocation.height - half_height_diff * 2
			)
			
		else:
			rect_tuple = allocation.x, allocation.y, allocation.width, allocation.height
		
		rect = Gdk.Rectangle()
		rect.x, rect.y, rect.width, rect.height = rect_tuple
				
		return rect
					
	def refresh_adjustments(self, widget=None, data=None):		
		x, y = self.imageview.get_pointer()
		rect = self.get_map_rectangle()
		
		allocation = self.imageview.get_allocation()
		hadjust = self.imageview.get_hadjustment()
		vadjust = self.imageview.get_vadjustment()
		vw = hadjust.props.upper - hadjust.props.page_size
		vh = vadjust.props.upper - vadjust.props.page_size
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
		tx = int(float(x) / rect.width * vw)
		ty = int(float(y) / rect.height * vh)
		
		hadjust.props.value, vadjust.props.value = tx, ty
	
	Margin = 32
	RequireClick = False
	MapMode = "proportional"
	
	Modes = ["stretched", "square", "proportional"]
	
	@staticmethod
	def create(imageview):
		return MapNavi(imageview)
	
	@staticmethod
	def get_name():
		return _("Map")
	
	@staticmethod
	def get_settings_widgets():
		widgets = Gtk.Grid()
		widgets.set_column_spacing(20)
		widgets.set_row_spacing(5)
		
		margin_label = Gtk.Label(_("Map margin"))
		margin_label.set_alignment(0, 0.5)
		margin_label.set_hexpand(True)
		margin = Gtk.SpinButton()
		margin.set_adjustment(Gtk.Adjustment(MapNavi.Margin, 0, 128, 1, 8, 0))
		widgets.attach(margin_label, 0, 0, 1, 1)
		widgets.attach(margin, 1, 0, 1, 1)
		
		require_click = Gtk.CheckButton(_("Require a click to move"))
		require_click.set_active(MapNavi.RequireClick)
		
		widgets.attach(require_click, 0, 1, 2, 1)
		
		stretched_mode = Gtk.RadioButton(_("Use a stretched map"))
		square_mode = Gtk.RadioButton(_("Use a square map"))
		proportional_mode = Gtk.RadioButton(
		                   _("Use a map proportional to the image"))
		
		square_mode.join_group(stretched_mode)
		proportional_mode.join_group(square_mode)
		
		if MapNavi.MapMode == "proportional":
			proportional_mode.set_active(True)
		elif MapNavi.MapMode == "square":
			square_mode.set_active(True)
		else:
			stretched_mode.set_active(True)
		
		mode_vbox = Gtk.VBox()
		mode_vbox.pack_start(stretched_mode, False, False, 0)
		mode_vbox.pack_start(square_mode, False, False, 0)
		mode_vbox.pack_start(proportional_mode, False, False, 0)
		
		mode_align = Gtk.Alignment()
		mode_align.set_padding(0, 0, 20, 0)
		mode_align.add(mode_vbox)
		
		mode_label = Gtk.Label(
		             _("Choose the map figure in relation to the window"))
		mode_label.set_alignment(0, 0.5)
		mode_label.set_line_wrap(True)
		
		widgets.attach(mode_label, 0, 2, 2, 1)
		widgets.attach(mode_align, 0, 3, 2, 1)
		
		widgets.margin = margin
		
		widgets.require_click = require_click
		
		widgets.stretched_mode = stretched_mode
		widgets.square_mode = square_mode
		widgets.proportional_mode = proportional_mode
		
		widgets.save_settings = MapNavi.apply_settings.__get__(widgets, None)
		
		return widgets
		
	@staticmethod
	def apply_settings(widgets):
		MapNavi.Margin = widgets.margin.get_value()
		MapNavi.RequireClick = widgets.require_click.get_active()
		
		if widgets.stretched_mode.get_active():
			MapNavi.MapMode = "stretched"
		elif widgets.square_mode.get_active():
			MapNavi.MapMode = "square"
		else:
			MapNavi.MapMode = "proportional"
	
NaviList.append(DragNavi)
NaviList.append(RollNavi)
NaviList.append(MapNavi)
