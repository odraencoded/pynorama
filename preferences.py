from gi.repository import Gtk, Gdk, GObject
from gettext import gettext as _
import cairo, math
import navigation

class Dialog(Gtk.Dialog):
	def __init__(self, app):
		Gtk.Dialog.__init__(self, _("Pynorama Preferences"), None,
			Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
			(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK))
		
		self.app = app
		
		# Setup notebook
		tabs = Gtk.Notebook()
		tabs_align = Gtk.Alignment()
		tabs_align.set_padding(15, 15, 15, 15)
		tabs_align.add(tabs)
		self.get_content_area().pack_start(tabs_align, True, True, 0)
		tabs_align.show_all()
		
		# Create tabs
		tab_labels = [_("Panning"), _("View")]
		tab_grids = []
		for a_tab_label in tab_labels:
			a_tab_align = Gtk.Alignment()
			a_tab_grid = Gtk.Grid()
			a_tab_grid.set_column_spacing(20)
			a_tab_grid.set_row_spacing(5)
			a_tab_align.set_padding(10, 15, 20, 20)
			a_tab_align.add(a_tab_grid)
			tabs.append_page(a_tab_align, Gtk.Label(a_tab_label))
			tab_grids.append(a_tab_grid)
		
		pan_grid, view_grid = tab_grids
		
		# Setup navigator tab				
		self.nav_book = Gtk.Notebook()
		self.nav_book.set_show_tabs(False)
		self.nav_book.set_show_border(False)
		self.nav_selection = Gtk.ComboBoxText()
		self.nav_selection.set_hexpand(True)
		self.navi_widgets = []
		self.navigators = []
		
		# Load navi widgets and names
		for navi in navigation.NaviList:
			name = navi.get_name()
			label = Gtk.Label(name)
			widgets = navi.get_settings_widgets()
			
			self.nav_book.append_page(widgets, label)
			self.nav_selection.append_text(name)
			self.navigators.append(navi)
		
		# Add navi selection widgets
		self.nav_selection.connect("changed", self.refresh_nav_book)	
		self.nav_enabler = Gtk.CheckButton(_("Enable mouse panning"))
		
		# If the navi_factory is none, then navi aided panning is disabled.
		current_navi = self.app.navi_factory		
		if current_navi is None:
			self.nav_enabler.set_active(False)
			self.nav_selection.set_active(0)
		else:
			self.nav_enabler.set_active(True)
			self.nav_selection.set_active(self.navigators.index(current_navi))
			
		nav_mode_label = Gtk.Label(_("Mouse panning mode"))
		pan_grid.attach(nav_mode_label, 0, 0, 1, 1)
		pan_grid.attach(self.nav_selection, 1, 0, 1, 1)
		pan_grid.attach(self.nav_enabler, 2, 0, 1, 1)
		pan_grid.attach(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL),
		                0, 1, 3, 1)
		pan_grid.attach(self.nav_book, 0, 2, 3, 1)
		
		# Setup view tab		
		point_label = Gtk.Label(_("Default scrollbar adjustment"))
		
		point_label.set_alignment(0, 0)
		point_label.set_line_wrap(True)
		
		adjust_x, adjust_y = self.app.default_position
		
		hadjust = Gtk.Adjustment(adjust_x, 0, 1, .04, .2, 0)
		xlabel = Gtk.Label(_("Horizontal "))
		xlabel.set_alignment(0, 0.5)
		xspin = Gtk.SpinButton()
		xspin.set_adjustment(hadjust)
		
		vadjust = Gtk.Adjustment(adjust_y, 0, 1, .04, .2, 0)
		ylabel = Gtk.Label(_("Vertical "))
		ylabel.set_alignment(0, 0.5)
		yspin = Gtk.SpinButton()
		yspin.set_adjustment(vadjust)
		
		xspin.set_digits(2)
		yspin.set_digits(2)
		
		point_scale = PointScale(hadjust, vadjust)
		view_grid.attach(point_label, 0, 0, 2, 1)
		
		view_grid.attach(xlabel, 0, 1, 1, 1)
		view_grid.attach(ylabel, 0, 2, 1, 1)
		view_grid.attach(xspin, 1, 1, 1, 1)
		view_grid.attach(yspin, 1, 2, 1, 1)
		view_grid.attach(point_scale, 2, 0, 1, 3)
		self.point_adjustments = hadjust, vadjust
		
		spin_button_specs = [
			(_("Rotation effect"),
			 (self.app.spin_effect, 1, 359, 3, 30)),
			(_("Zoom in/out effect"),
			 (self.app.zoom_effect, 1.02, 4, 0.1, 0.25))
		]		
		spin_buttons = []
		for a_label_string, an_adjustment_args in spin_button_specs:
			a_button_label = Gtk.Label(a_label_string)
			a_button_label.set_hexpand(True)
			a_button_label.set_alignment(0, 0.5)
			
			an_adjustment = Gtk.Adjustment(*(an_adjustment_args + (0,)))
			a_spin_button = Gtk.SpinButton()
			a_spin_button.set_adjustment(an_adjustment)
			
			row = len(spin_buttons) + 3
			view_grid.attach(a_button_label, 0, row, 2, 1)
			view_grid.attach(a_spin_button, 2, row, 1, 1)
			spin_buttons.append(a_spin_button)
		
		self.spin_effect, self.zoom_effect = spin_buttons
		self.zoom_effect.set_digits(2)
		
		tabs.show_all()
		self.refresh_nav_book()
		
	def create_widget_group(self, *widgets):
		alignment = Gtk.Alignment()
		alignment.set_padding(0, 0, 20, 0)
		
		box = Gtk.VBox()
		alignment.add(box)
		
		for a_widget in widgets:
			box.pack_start(a_widget, False, False, 3)
			
		return alignment
		
	def refresh_nav_book(self, data=None):
		active_page = self.nav_selection.get_active()
		if active_page >= 0:
			self.nav_book.set_current_page(active_page)
			
	def save_prefs(self):
		# Go through all pages to get the "widgets" and tell them to save themselves
		for the_n in range(self.nav_book.get_n_pages()):
			self.nav_book.get_nth_page(the_n).save_settings()
			
		if self.nav_enabler.get_active():
			selected_navi = self.navigators[self.nav_selection.get_active()]
		else:
			selected_navi = None
		# Maybe I should reattach the same navigator, maybe not
		self.app.set_navi_factory(selected_navi)
		self.app.zoom_effect = self.zoom_effect.get_value()
		self.app.spin_effect = self.spin_effect.get_value()
		
		self.app.default_position = [adjust.get_value() for adjust \
		                             in self.point_adjustments]
		
class PointScale(Gtk.DrawingArea):
	''' A widget like a Gtk.HScale and Gtk.VScale together. '''
	def __init__(self, hrange, vrange):
		Gtk.DrawingArea.__init__(self)
		self.set_size_request(50, 50)
		self.padding = 4
		self.dragging = False
		self.__hrange = self.__vrange = None
		self.hrange_signal = self.vrange_signal = None
		self.set_hrange(hrange)
		self.set_vrange(vrange)
		self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
			Gdk.EventMask.BUTTON_RELEASE_MASK |
			Gdk.EventMask.POINTER_MOTION_MASK |
			Gdk.EventMask.POINTER_MOTION_HINT_MASK)
			
	def adjust_from_point(self, x, y):
		w, h = self.get_allocated_width(), self.get_allocated_height()
		t, l = self.padding, self.padding
		r = w - self.padding
		b = h - self.padding
		
		x, y = max(0, min(r - l, x - l)) / (r - l), max(0, min(b - t, y - t)) / (b - t)
		hrange = self.get_hrange()
		if hrange:
			lx, ux = hrange.get_lower(), hrange.get_upper()
			vx = x * (ux - lx) + lx
			self.hrange.set_value(vx)
		
		vrange = self.get_vrange()
		if vrange:
			ly, uy = vrange.get_lower(), vrange.get_upper()
			vy = y * (uy - ly) + ly
			self.vrange.set_value(vy)
	
	def do_get_request_mode(self):
		return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH
		
	def do_get_preferred_width_for_height(self, height):
		hrange = self.get_hrange()
		vrange = self.get_vrange()
		lx, ux = hrange.get_lower(), hrange.get_upper()
		ly, uy = vrange.get_lower(), vrange.get_upper()
		return 24, max(24, int((ux - lx) / (uy - ly) * height))
	
	def do_get_preferred_height_for_width(self, width):
		hrange = self.get_hrange()
		vrange = self.get_vrange()
		lx, ux = hrange.get_lower(), hrange.get_upper()
		ly, uy = vrange.get_lower(), vrange.get_upper()
		return 24, max(24, int((uy - ly) / (ux - lx) * width))
		
	def do_button_press_event(self, data):
		self.dragging = True
		self.adjust_from_point(data.x, data.y)
			
	def do_button_release_event(self, data):
		self.dragging = False
		self.queue_draw()
	
	def do_motion_notify_event(self, data):
		if self.dragging:
			mx, my = data.x, data.y
			self.adjust_from_point(mx, my)
	
	def do_draw(self, cr):
		w, h = self.get_allocated_width(), self.get_allocated_height()		
		t, l = self.padding, self.padding
		r = w - self.padding
		b = h - self.padding
		
		hrange = self.get_hrange()
		if hrange:
			lx, ux = hrange.get_lower(), hrange.get_upper()
			vx = hrange.get_value()
			x = (r - l - 1) * (vx / (ux - lx) - lx) + l
		else:
			x = w / 2
			
		vrange = self.get_vrange()
		if vrange:
			ly, uy = vrange.get_lower(), vrange.get_upper()
			vy = vrange.get_value()
			y = (b - t - 1) * (vy / (uy - ly) - ly) + l
		else:
			y = h / 2
		
		style = self.get_style_context()
		
		style.add_class(Gtk.STYLE_CLASS_ENTRY)
		Gtk.render_background(style, cr, 0, 0, w, h)
		cr.save()
		border = style.get_border(style.get_state())
		radius = style.get_property(Gtk.STYLE_PROPERTY_BORDER_RADIUS, Gtk.StateFlags.NORMAL)
		color = style.get_color(style.get_state())
		cr.arc(border.left + radius, border.top + radius, radius, math.pi, math.pi * 1.5)
		cr.arc(w - border.right - radius -1, border.top + radius, radius, math.pi * 1.5, math.pi * 2)
		cr.arc(w - border.right - radius -1, h -border.bottom - radius -1, radius, 0, math.pi / 2)
		cr.arc(border.left + radius, h - border.bottom - radius - 1, radius, math.pi / 2, math.pi)
		cr.clip()
		
		cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
		
		dot_radius = 3
		out_radius = dot_radius * 4
		cr.set_line_width(1)
		cr.set_dash([dot_radius, out_radius], x)
		Gtk.render_line(style, cr, x, -out_radius, x, y -out_radius)
		Gtk.render_line(style, cr, x, y +out_radius, x, h +out_radius)
		cr.set_dash([dot_radius, out_radius], y)
		Gtk.render_line(style, cr, -out_radius, y, x -out_radius, y)
		Gtk.render_line(style, cr, x +out_radius, y, w +out_radius, y)
		
		cr.set_dash([], 0)
		cr.arc(x, y, out_radius, 0, 2 * math.pi)
		cr.stroke()
		cr.arc(x, y, dot_radius, 0, 2 * math.pi)
		cr.fill()
		
		cr.restore()
		Gtk.render_frame(style, cr, 0, 0, w, h)
			
	def adjustment_changed(self, data):
		self.queue_draw()
	
	def get_hrange(self):
		return self.__hrange
	def set_hrange(self, adjustment):
		if self.__hrange:
			self.__hrange.disconnect(self.hrange_signal)
			self.hrange_signal = None
			
		self.__hrange = adjustment
		if adjustment:
			self.hrange_signal = adjustment.connect("value-changed",
			                                         self.adjustment_changed)
		self.queue_draw()
		
	def get_vrange(self):
		return self.__vrange
	def set_vrange(self, adjustment):
		if self.__vrange:
			self.__vrange.disconnect(self.vrange_signal)
			self.vrange_signal = None
			
		self.__vrange = adjustment
		if adjustment:
			self.vrange_signal = adjustment.connect("value-changed",
			                                         self.adjustment_changed)
		self.queue_draw()
			                                         
	hrange = GObject.property(get_hrange, set_hrange, type=Gtk.Adjustment)
	vrange = GObject.property(get_vrange, set_vrange, type=Gtk.Adjustment)