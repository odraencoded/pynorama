''' utility.py contains utility classes and methods '''

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

from gi.repository import GLib

class IdlyMethod:
	''' Manages a simple idle callback signal in GLib '''
	def __init__(self, callback, *args, **kwargs):
		self.callback = callback
		self.priority = GLib.PRIORITY_DEFAULT_IDLE
		self.args = args
		self.kwargs = kwargs
		self._signal_id = None
		self._queued = False
	
	
	def __call__(self):
		self.cancel_queue()
		self.callback(*self.args, **self.kwargs)
		
	execute = __call__
	
	def queue(self):
		''' Queues the IdlyMethod to be called from the Gtk main loop later '''
		if not self._signal_id:
			self._signal_id = GLib.idle_add(
			     self._idly_execute_queue, priority=self.priority)
		
		self._queued = True


	def cancel_queue(self):
		''' Cancels the idle call '''
		if self._signal_id:
			GLib.source_remove(self._signal_id)
			self._signal_id = None
			self._queued = False
	
	
	def execute_queue(self):
		''' Executes the IdlyMethod if it has been queued.
			Nothing happens otherwise. '''
		if self._queued:
			self()
	
	
	def _idly_execute_queue(self):
		self._queued = False
		self()
		
		if not self._queued:
			self._signal_id = None
		
		return self._queued


#-- widget Creation macros down this line --#

from gi.repository import GObject, Gdk, Gtk
import cairo, math

def Bind(source, *properties, bidirectional=False, synchronize=False):
	''' Bind GObject properties '''
	
	flags = 0
	if bidirectional:
		flags |= GObject.BindingFlags.BIDIRECTIONAL
	if synchronize:
		flags |= GObject.BindingFlags.SYNC_CREATE
	
	for src_property, dest, dest_property in properties:
		source.bind_property(src_property, dest, dest_property, flags)


def BindSame(source_property, dest_property,
             *objects, bidirectional=False, synchronize=True):
	''' Bind a same source property to a dest property '''
	
	flags = 0
	if bidirectional:
		flags |= GObject.BindingFlags.BIDIRECTIONAL
	if synchronize:
		flags |= GObject.BindingFlags.SYNC_CREATE
	
	for a_src, a_dest in objects:
		a_src.bind_property(source_property, a_dest, dest_property, flags)


def LoneLabel(text):
	''' Creates a Gtk.Label appropriate for text that isn't beside a widget '''
	result = Gtk.Label(text)
	result.set_line_wrap(True)
	result.set_alignment(0, .5)
	return result


def WidgetLine(*widgets, expand=None):
	''' Creates a Gtk.Box for horizontally laid widgets,
	    maybe expanding one of them '''
	result = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
	                 spacing=WidgetLine.Spacing)
	
	for a_widget in widgets:
		if a_widget is expand:
			a_widget.set_hexpand(True)
			result.pack_start(a_widget, True, True, 0)
			
		else:
			result.pack_start(a_widget, False, True, 0)
	
	return result
	

def WidgetStack(*widgets, expand=None, stack=None):
	''' Creates a Gtk.Box for vertically laid widgets,
	    maybe expanding one of them '''
	
	if stack:
		result = stack
		
	else:
		result = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
		                 spacing=WidgetStack.Spacing)
	
	for a_widget in widgets:
		if a_widget is expand:
			a_widget.set_vexpand(True)
			result.pack_start(a_widget, True, True, 0)
			
		else:
			result.pack_start(a_widget, False, True, 0)
	
	return result


WidgetLine.Spacing = 16
WidgetStack.Spacing = 8


def InitWidgetStack(stack, *widgets, expand=None):
	''' Inits a Gtk.Box for vertically laid widgets '''
	Gtk.Box.__init__(stack, orientation=Gtk.Orientation.VERTICAL,
	                        spacing=WidgetStack.Spacing)
	
	WidgetStack(stack=stack, *widgets, expand=expand)


def WidgetGrid(*rows, align_first=False, expand_first=False, expand_last=False,
               grid=None, start_row=0):
	''' Creates a Gtk.Grid with standard spacing and rows of widgets'''
	if not grid:
		grid = Gtk.Grid()
		grid.set_row_spacing(WidgetStack.Spacing)
		grid.set_column_spacing(WidgetLine.Spacing)
	
	for y, a_row in enumerate(rows):
		real_y = start_row + y
		grid.insert_row(real_y)
		for x, a_cell in enumerate(a_row):
			if x == 0:
				if align_first:
					a_cell.set_alignment(0, .5)
					
				if expand_first:
					a_cell.set_hexpand(True)
					
			if expand_last and x == len(a_row) - 1:
				a_cell.set_hexpand(True)
			
			grid.attach(a_cell, x, real_y, 1, 1)
			
	return grid


def PadContainer(container=None, top=None, right=None, bottom=None, left=None):
	''' Creates a Gtk.Alignment for padding a container '''
	if top is None:
		top = WidgetStack.Spacing
		right = WidgetLine.Spacing if right is None else right
	
	else:
		right = top if right is None else right
		
	bottom = top if bottom is None else bottom
	left = right if left is None else left
	
	alignment = Gtk.Alignment()
	alignment.set_padding(top, bottom, left, right)
	
	if container:
		alignment.add(container)
	
	return alignment
	
	
def PadDialogContent(content=None):
	''' Creates a Gtk.Alignment for the top widget of a Gtk.Dialog '''
	return PadContainer(content, 15)
	

def PadNotebookContent(content=None):
	''' Creates a Gtk.Alignment for the top widget of a Gtk.Dialog '''
	return PadContainer(content, 8, 15, 12)
	
	
def ButtonBox(*buttons, secondary=None, alternative=False):
	''' Creates a button box with buttons '''
	
	layout = Gtk.ButtonBoxStyle.START if alternative else Gtk.ButtonBoxStyle.END
	result = Gtk.ButtonBox(spacing=8, orientation=Gtk.Orientation.HORIZONTAL)
	result.set_layout(layout)
	
	for a_button in buttons:
		result.add(a_button)
		
	if secondary:
		for a_button in secondary:
			result.add(a_button)
			result.set_child_secondary(a_button, True)
			
	return result
	

AbsolutePercentScaleFormat = lambda w, v: "{:.0%}".format(abs(v))
AbsoluteScaleFormat = lambda w, v: "{}".format(abs(v))
PercentScaleFormat = lambda w, v: "{:.0%}".format(v)

def ScaleAdjustment(value=0, lower=0, upper=0, step_incr=0, page_incr=0,
                    adjustment=None, marks=None,
                    vertical=False, origin=True,
                    percent=False, absolute=False):
	''' Creates a scale and maybe an adjustment '''
	# Create adjustment
	got_adjustment = adjustment is not None
	if not got_adjustment:
		adjustment = Gtk.Adjustment(
			value, lower, upper, step_incr, page_incr, 0
		)
	
	# Set orientation
	if vertical:
		orientation = Gtk.Orientation.VERTICAL
		mark_pos = Gtk.PositionType.RIGHT
	else:
		orientation = Gtk.Orientation.HORIZONTAL
		mark_pos = Gtk.PositionType.BOTTOM
	
	# Create scale
	scale = Gtk.Scale(adjustment=adjustment, orientation=orientation)
	scale.set_has_origin(origin)
	
	# Add marks
	if marks:
		for value, label in marks:
			scale.add_mark(value, mark_pos, label)
	
	# Setup formatting	
	if percent:
		if absolute:
			scale.connect("format-value", AbsolutePercentScaleFormat)
		else:
			scale.connect("format-value", AbsoluteScaleFormat)
			
	elif absolute:
		scale.connect("format-value", PercentScaleFormat)
	
	if got_adjustment:
		return scale
	else:
		return scale, adjustment
		

def SpinAdjustment(value=0, lower=0, upper=0, step_incr=0, page_incr=0,
                   adjustment=None, align=False, **kwargs):
	''' Creates a spin button and maybe an adjustment '''
	# Create adjustment
	got_adjustment = adjustment is not None
	if not got_adjustment:
		adjustment = Gtk.Adjustment(
			value, lower, upper, step_incr, page_incr, 0
		)
		
	# Create scale
	scale = Gtk.SpinButton(adjustment=adjustment, **kwargs)
	if align:
		scale.set_alignment(1)
	
	if got_adjustment:
		return scale
	else:
		return scale, adjustment
		


def PointScaleGrid(point_scale, xlabel, ylabel, corner=None, align=False):
	xlabel = Gtk.Label(xlabel)
	xspin = SpinAdjustment(adjustment=point_scale.hrange, digits=2, align=True)
	ylabel = Gtk.Label(ylabel)
	yspin = SpinAdjustment(adjustment=point_scale.vrange, digits=2, align=True)
	
	spin_grid = WidgetGrid(
		(xlabel, xspin), (ylabel, yspin),
		align_first=True, expand_first=True
	)
	
	if corner:
		if align:
			corner.set_alignment(0, .5)
		
		spin_stack = WidgetStack(corner, spin_grid)
		
	else:
		spin_stack = WidgetStack(spin_grid)
	
	return WidgetGrid((spin_stack, point_scale)), xspin, yspin
