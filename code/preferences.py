''' preferences.py contains the settings dialog
    and preferences loading methods. '''

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

from gi.repository import Gio, GLib, Gtk, Gdk, GObject
from gettext import gettext as _
import cairo, math, os
import extending, organization, notification

Settings = Gio.Settings("com.example.pynorama")
Directory = "preferences"

class Dialog(Gtk.Dialog):
	def __init__(self, app):
		Gtk.Dialog.__init__(self, _("Pynorama Preferences"), None,
			Gtk.DialogFlags.DESTROY_WITH_PARENT,
			(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
		
		self.app = app
		self.set_default_size(400, 400)
		self._mouse_handler_iters = dict()
		self._mm_handler_signals = list()
		self._mouse_handler_signals = dict()
		self.mm_handler = self.app.meta_mouse_handler
		
		self.connect("destroy", self._do_destroy)
		
		# Setup notebook
		self.tabs = tabs = Gtk.Notebook()
		tabs_align = Gtk.Alignment()
		tabs_align.set_padding(15, 15, 15, 15)
		tabs_align.add(tabs)
		self.get_content_area().pack_start(tabs_align, True, True, 0)
		tabs_align.show_all()
		
		# Create tabs
		tab_labels = [_("View"), _("Mouse")]
		tab_aligns = []
		for a_tab_label in tab_labels:
			a_tab_align = Gtk.Alignment()
			
			a_tab_align.set_padding(10, 15, 20, 20)
			tabs.append_page(a_tab_align, Gtk.Label(a_tab_label))
			tab_aligns.append(a_tab_align)
		
		view_tab_align, mouse_tab_align = tab_aligns
					
		# Setup view tad
		
		view_grid = Gtk.Grid()
		view_grid.set_column_spacing(20)
		view_grid.set_row_spacing(5)
		view_tab_align.add(view_grid)
				
		point_label = Gtk.Label(_("Image alignment"))
		alignment_tooltip = _('''This alignment setting is \
used for various alignment related things in the program''')
		
		point_label.set_hexpand(True)
		point_label.set_alignment(0, .5)
		point_label.set_line_wrap(True)
		
		hadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
		xlabel = Gtk.Label(_("Horizontal "))
		xlabel.set_alignment(0, 0.5)
		xspin = Gtk.SpinButton()
		xspin.set_adjustment(hadjust)
		
		vadjust = Gtk.Adjustment(0.5, 0, 1, .04, .2, 0)
		ylabel = Gtk.Label(_("Vertical "))
		ylabel.set_alignment(0, 0.5)
		yspin = Gtk.SpinButton()
		yspin.set_adjustment(vadjust)
		
		xspin.set_digits(2)
		yspin.set_digits(2)
		
		point_scale = PointScale(hadjust, vadjust, square=True)
		
		# Set tooltip
		xspin.set_tooltip_text(alignment_tooltip)
		yspin.set_tooltip_text(alignment_tooltip)
		xlabel.set_tooltip_text(alignment_tooltip)
		ylabel.set_tooltip_text(alignment_tooltip)
		point_label.set_tooltip_text(alignment_tooltip)
		point_scale.set_tooltip_text(alignment_tooltip)
		
		view_grid.attach(point_label, 0, 0, 2, 1)
		
		view_grid.attach(xlabel, 0, 1, 1, 1)
		view_grid.attach(ylabel, 0, 2, 1, 1)
		view_grid.attach(xspin, 1, 1, 1, 1)
		view_grid.attach(yspin, 1, 2, 1, 1)
		view_grid.attach(point_scale, 2, 0, 1, 3)
		self.alignment_x_adjust = hadjust
		self.alignment_y_adjust = vadjust
		
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		
		spin_button_specs = [
			(_("Spin effect"), "spin-effect", (0, -180, 180, 10, 60)),
			(_("Zoom in/out effect"), "zoom-effect", (0, 1.02, 4, 0.1, 0.25))
		]
		
		spin_buttons = []
		for a_label_string, a_property, an_adjustment_args in spin_button_specs:
			a_button_label = Gtk.Label(a_label_string)
			a_button_label.set_alignment(0, 0.5)
			
			an_adjustment = Gtk.Adjustment(*(an_adjustment_args + (0,)))
			if a_property:
				self.app.bind_property(a_property, an_adjustment, "value",
				                       bidi_flag | sync_flag)
				
			a_spin_button = Gtk.SpinButton()
			a_spin_button.set_adjustment(an_adjustment)
			
			row = len(spin_buttons) + 3
			view_grid.attach(a_button_label, 0, row, 2, 1)
			view_grid.attach(a_spin_button, 2, row, 1, 1)
			spin_buttons.append(a_spin_button)
		
		self.spin_effect, self.zoom_effect = spin_buttons
		self.zoom_effect.set_digits(2)
		self.spin_effect.set_wrap(True)
		
		# Setup mouse tab
		self._mouse_pseudo_notebook = very_mice_book = Gtk.Notebook()
		very_mice_book.set_show_tabs(False)
		very_mice_book.set_show_border(False)
		
		# This one is used for the labels on top of the pseudo notebook
		mouse_label_notebook = Gtk.Notebook()
		mouse_label_notebook.set_show_tabs(False)
		mouse_label_notebook.set_show_border(False)				
		
		# Add handler list label and widget container
		label = _('''Mouse based navigation programs currently used \
in the image viewer''')
		handlers_description = Gtk.Label(label)
		handlers_description.set_line_wrap(True)
		handlers_description.set_alignment(0, 0)
		mouse_label_notebook.append_page(handlers_description, None)
		view_handlers_box = Gtk.Box(spacing=8,
		                            orientation=Gtk.Orientation.VERTICAL)
		very_mice_book.append_page(view_handlers_box, None)
		
		# Add handler factory list label and widget container
		label = _('''Types of mouse based navigators currently avaiable \
for the image viewer''')
		brands_description = Gtk.Label(label)
		brands_description.set_line_wrap(True)
		brands_description.set_alignment(0, 0)
		mouse_label_notebook.append_page(brands_description, None)
		add_handler_box = Gtk.Box(spacing=8,
		                          orientation=Gtk.Orientation.VERTICAL)
		very_mice_book.append_page(add_handler_box, None)
		
		# Pack both notebooks in the mouse tab
		pseudo_notebook_box = Gtk.Box(spacing=12,
		                              orientation=Gtk.Orientation.VERTICAL)
		pseudo_notebook_box.pack_start(mouse_label_notebook, False, True, 0)
		pseudo_notebook_box.pack_start(very_mice_book, True, True, 0)
		
		mouse_tab_align.add(pseudo_notebook_box)
		
		# Setup handler list tab
		handler_liststore = Gtk.ListStore(object)
		self._handler_listview = handler_listview = Gtk.TreeView()
		handler_listview.set_model(handler_liststore)
		
		# Sync store
		for a_handler in self.app.meta_mouse_handler.get_handlers():
			self._add_mouse_handler(a_handler)
		
		handler_listview_selection = handler_listview.get_selection()
		handler_listview_selection.set_mode(Gtk.SelectionMode.MULTIPLE)
		
		name_renderer = Gtk.CellRendererText()
		name_column = Gtk.TreeViewColumn("Nickname")
		name_column.pack_start(name_renderer, True)
		name_column.set_cell_data_func(name_renderer, 
		                               self._handler_nick_data_func)
		
		handler_listview.append_column(name_column)
		
		# Create edit button box
		edit_handler_buttonbox = Gtk.ButtonBox(spacing=8,
		                             orientation=Gtk.Orientation.HORIZONTAL)
		edit_handler_buttonbox.set_layout(Gtk.ButtonBoxStyle.START)
		new_handler_button, configure_handler_button, remove_handler_button = (
			Gtk.Button.new_from_stock(Gtk.STOCK_NEW),
			Gtk.Button.new_from_stock(Gtk.STOCK_PROPERTIES),
			Gtk.Button.new_from_stock(Gtk.STOCK_DELETE),
		)
		# These are insensitive until something is selected
		remove_handler_button.set_sensitive(False)
		configure_handler_button.set_sensitive(False)
		configure_handler_button.set_can_default(True)
		
		edit_handler_buttonbox.add(configure_handler_button)
		edit_handler_buttonbox.add(new_handler_button)
		edit_handler_buttonbox.add(remove_handler_button)
		edit_handler_buttonbox.set_child_secondary(
		                       configure_handler_button, True)
		
		handler_listscroller = Gtk.ScrolledWindow()
		handler_listscroller.add(handler_listview)
		handler_listscroller.set_shadow_type(Gtk.ShadowType.IN)
		
		view_handlers_box.pack_start(handler_listscroller, True, True, 0)
		view_handlers_box.pack_start(edit_handler_buttonbox, False, True, 0)
		
		# Setup add handlers grid (it is used to add handlers)
		brand_liststore = Gtk.ListStore(object)
		
		for a_brand in extending.MouseHandlerBrands:
			brand_liststore.append([a_brand])
		
		self._brand_listview = brand_listview = Gtk.TreeView()
		brand_listview.set_model(brand_liststore)
		
		brand_selection = brand_listview.get_selection()
		brand_selection.set_mode(Gtk.SelectionMode.BROWSE)
		
		type_column = Gtk.TreeViewColumn("Type")
		label_renderer = Gtk.CellRendererText()
		type_column.pack_start(label_renderer, True)
		type_column.set_cell_data_func(label_renderer, 
		                               self._brand_label_data_func)
		
		brand_listview.append_column(type_column)
		
		brand_listscroller = Gtk.ScrolledWindow()
		brand_listscroller.add(brand_listview)
		brand_listscroller.set_shadow_type(Gtk.ShadowType.IN)
		
		# Create button box
		add_handler_buttonbox = Gtk.ButtonBox(spacing=8,
		                             orientation=Gtk.Orientation.HORIZONTAL)
		add_handler_buttonbox.set_layout(Gtk.ButtonBoxStyle.END)
		cancel_add_button, add_button = (
			Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL),
			Gtk.Button.new_from_stock(Gtk.STOCK_ADD),
		)
		add_button.set_can_default(True)
		add_handler_buttonbox.add(cancel_add_button)
		add_handler_buttonbox.add(add_button)
		
		add_handler_box.pack_start(brand_listscroller, True, True, 0)
		add_handler_box.pack_start(add_handler_buttonbox, False, True, 0)
		
		self._configure_handler_button = configure_handler_button
		self._add_handler_button = add_button
		
		# Bindings and events
		self._window_bindings, self._view_bindings = [], []
		self.connect("notify::target-window", self._changed_target_window)
		self.connect("notify::target-view", self._changed_target_view)
		
		# This is a bind for syncing pages betwen the label and widget books
		very_mice_book.bind_property("page", mouse_label_notebook,
		                             "page", sync_flag)
		
		
		new_handler_button.connect("clicked", self._clicked_new_handler)
		remove_handler_button.connect("clicked", self._clicked_remove_handler)
		configure_handler_button.connect("clicked",
		                                 self._clicked_configure_handler)
		handler_listview_selection.connect("changed",
		                                   self._changed_handler_list_selection,
		                                   remove_handler_button,
		                                   configure_handler_button)
		
		cancel_add_button.connect("clicked", self._clicked_cancel_add_handler)
		add_button.connect("clicked", self._clicked_add_handler)
		very_mice_book.connect("key-press-event", self._key_pressed_mice_book)
		self._handler_listview.connect("button-press-event",
		                               self._button_pressed_handlers)
		self._brand_listview.connect("button-press-event",
		                              self._button_pressed_brands)
		
		tabs.connect("switch-page", self._refresh_default)
		very_mice_book.connect("switch-page", self._refresh_default)
		self._refresh_default()
		
		self._mm_handler_signals = [
			self.mm_handler.connect("handler-added",
				                    self._added_mouse_handler),
			self.mm_handler.connect("handler-removed",
		                            self._removed_mouse_handler)
		]		
		tabs.show_all()

	
	def _refresh_default(self, *data):
		''' Resets the default widget of the window '''
		tab = self.tabs.get_current_page()
		if tab == 1:
			pseudo_tab = self._mouse_pseudo_notebook.get_current_page()
			if pseudo_tab == 0:
				new_default = self._configure_handler_button
			
			else:
				new_default = self._add_handler_button
				
		else:
			new_default = None
			
		if self.get_default_widget() != new_default:
			self.set_default(new_default)
		
		
	def _handler_nick_data_func(self, column, renderer, model, treeiter, *data):
		''' Gets the nickname of a handler for the textrenderer '''
		handler = model[treeiter][0]
		text = handler.nickname
		if not text:
			if handler.factory:
				text = handler.factory.label
				
			else:
				text = "???"
				
		renderer.props.text = text
	
	
	def _clicked_new_handler(self, *data):
		''' Handles a click on the new mouse handler button in the mouse tab '''
		self._mouse_pseudo_notebook.set_current_page(1)
	
	
	def _clicked_remove_handler(self, *data):
		''' Handles a click on the remove button in the mouse tab '''
		selection = self._handler_listview.get_selection()
		model, row_paths = selection.get_selected_rows()
		
		remove_handler = self.app.meta_mouse_handler.remove
		treeiters = [model.get_iter(a_path) for a_path in row_paths]
		for a_treeiter in treeiters:
			a_handler = model[a_treeiter][0]
			remove_handler(a_handler)
		
		
	def _removed_mouse_handler(self, meta, handler):
		''' Handles a handler actually being removed from
		    the meta mouse handler '''
		handler_iter = self._mouse_handler_iters.pop(handler, None)
		handler_signals = self._mouse_handler_signals.pop(handler, [])
		
		if handler_iter:
			del self._handler_listview.get_model()[handler_iter]
		
		for a_signal_id in handler_signals:
			handler.disconnect(a_signal_id)
		
	
	def _clicked_configure_handler(self, *data):
		''' Pops up the configure dialog of a mouse handler '''
		selection = self._handler_listview.get_selection()
		model, row_paths = selection.get_selected_rows()
		
		get_dialog = self.app.get_mouse_handler_dialog
		
		treeiters = [model.get_iter(a_path) for a_path in row_paths]
		for a_treeiter in treeiters:
			a_handler = model[a_treeiter][0]
			
			dialog = get_dialog(a_handler)
			dialog.present()
			
	
	def _changed_handler_list_selection(self, selection, 
	                                    remove_button, configure_button):
		''' Update sensitivity of some buttons based on whether anything is
		    selected in the handlers list view '''
		
		model, row_paths = selection.get_selected_rows()
		
		selected_anything = bool(row_paths)
		remove_button.set_sensitive(selected_anything)
		configure_button.set_sensitive(selected_anything)
	
	
	def _button_pressed_handlers(self, listview, event):
		''' Opens the configure dialog on double click '''
		if event.type == Gdk.EventType._2BUTTON_PRESS:
			self._clicked_configure_handler()
	
	
	def _key_pressed_mice_book(self, widget, event):
		''' Handles delete key on handlers listview '''
		if event.keyval == Gdk.KEY_Delete and \
		   self._mouse_pseudo_notebook.get_current_page() == 0:
			self._clicked_remove_handler()
			
			
	def _clicked_cancel_add_handler(self, *data):
		''' Go back to the handlers list when the user doesn't actually
		    want to create a new mouse handler '''
		self._mouse_pseudo_notebook.set_current_page(0)
	
	
	def _clicked_add_handler(self, *data):
		''' Creates and adds a new mouse handler to the meta mouse handler '''
		selection = self._brand_listview.get_selection()
		model, treeiter = selection.get_selected()
		if treeiter is not None:
			factory = model[treeiter][0]
			
			new_handler = factory.produce()
			
			handler_button = 1 if new_handler.needs_button else None
			self.mm_handler.add(new_handler, button=handler_button)
			
			# Go back to the handler list
			self._mouse_pseudo_notebook.set_current_page(0)
			
			# Scroll to new handler
			listview = self._handler_listview
			new_treeiter = self._mouse_handler_iters[new_handler]
			new_treepath = listview.get_model().get_path(new_treeiter)
			listview.scroll_to_cell(new_treepath, None, False, 0, 0)
			
	
	def _added_mouse_handler(self, meta, new_handler):
		''' Handles a mouse handler being added to the meta mouse handler '''
		self._add_mouse_handler(new_handler)
	
	
	def _add_mouse_handler(self, new_handler, *data):
		''' Actually and finally adds the mouse handler to the liststore '''
		# TODO: Change this to a meta mouse handler "added" signal handler
		listview = self._handler_listview
		model = listview.get_model()
		new_treeiter = model.append([new_handler])
		
		self._mouse_handler_iters[new_handler] = new_treeiter
		# Connect things
		self._mouse_handler_signals[new_handler] = [
			new_handler.connect("notify::nickname",
			                    self._refresh_handler_nickname,
		                        new_treeiter)
		]
		                    
	
	def _button_pressed_brands(self, listview, event):
		''' Creates a new handler on double click '''
		if event.type == Gdk.EventType._2BUTTON_PRESS:
			self._clicked_add_handler()
			
	
	def _brand_label_data_func(self, column, renderer, model, treeiter, *data):
		''' Gets the label of a factory for a text cellrenderer '''
		factory = model[treeiter][0]
		renderer.props.text = factory.label
		
		
	def _refresh_handler_nickname(self, handler, spec, treeiter):
		''' Refresh the list view when a handler nickname changes '''
		model = self._handler_listview.get_model()
		treepath = model.get_path(treeiter)
		model.row_changed(treepath, treeiter)
	
	
	def create_widget_group(self, *widgets):
		''' I don't even remember what this does '''
		alignment = Gtk.Alignment()
		alignment.set_padding(0, 0, 20, 0)
		
		box = Gtk.VBox()
		alignment.add(box)
		
		for a_widget in widgets:
			box.pack_start(a_widget, False, False, 3)
			
		return alignment
		
	
	def _changed_target_window(self, *data):
		self.set_transient_for(self.target_window)
		
		view, album = self.target_window.view, self.target_window.album
		
		if self.target_view != view:
			self.target_view = view
			
		if self.target_album != album:
			self.target_album = album
		
		
	def _changed_target_view(self, *data):
		bidi_flag = GObject.BindingFlags.BIDIRECTIONAL
		sync_flag = GObject.BindingFlags.SYNC_CREATE
		
		for a_binding in self._view_bindings:
			a_binding.unbind()
		
		view = self.target_view
		if view:
			self._view_bindings = [
				view.bind_property("alignment-x", self.alignment_x_adjust,
						           "value", bidi_flag | sync_flag),
			
				view.bind_property("alignment-y", self.alignment_y_adjust,
				                   "value", bidi_flag | sync_flag)
			]
		else:
			self._view_bindings = []
		
	target_window = GObject.Property(type=object)
	target_view = GObject.Property(type=object)
	target_album = GObject.Property(type=object)
	
	def _do_destroy(self, *data):
		''' Disconnect any connected signals '''
		for a_signal_id in self._mm_handler_signals:
			self.mm_handler.disconnect(a_signal_id)
		
		for a_handler, some_signals in self._mouse_handler_signals.items():
			for a_signal in some_signals:
				a_handler.disconnect(a_signal)
	

class MouseHandlerSettingDialog(Gtk.Dialog):
	def __init__(self, handler, handler_data):
		Gtk.Dialog.__init__(self, _("Mouse Navigation Settings"), None,
			Gtk.DialogFlags.DESTROY_WITH_PARENT,
			(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
		
		alignment = Gtk.Alignment()
		alignment.set_padding(15, 15, 15, 15)
		vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
		alignment.add(vbox)
		alignment.show_all()
		self.get_content_area().pack_start(alignment, True, True, 0)
		
		self.handler = handler
		self.handler_data = handler_data
		
		# Create nickname widgets
		label = _("Nickname")
		nickname_label = Gtk.Label(label)
		nickname_entry = Gtk.Entry()
		nickname_entry.set_hexpand(True)
		# Binding entry
		flags = GObject.BindingFlags
		handler.bind_property("nickname", nickname_entry, "text", 
		                      flags.BIDIRECTIONAL | flags.SYNC_CREATE)
		# Pack nickname entry
		nickname_line = Gtk.Box(spacing=20,
		                        orientation=Gtk.Orientation.HORIZONTAL)
		nickname_line.pack_start(nickname_label, False, True, 0)
		nickname_line.pack_start(nickname_entry, False, True, 0)
		vbox.pack_start(nickname_line, False, True, 0)
		
		# Create button setting widgets for handlers that need button setting
		if handler.needs_button:
			tooltip = _("Click here with a mouse button to change \
the chosen mouse button")
			
			mouse_button = self.mouse_button_button = Gtk.Button()
			mouse_button.set_tooltip_text(tooltip)
			mouse_button.connect("button-press-event",
			                     self._mouse_button_presssed)
			handler_data.connect("notify::button", self._refresh_mouse_button)
			
			vbox.pack_start(mouse_button, False, True, 0)
			self._refresh_mouse_button()
		
		vbox.pack_end(Gtk.Separator(), False, True, 0)
		vbox.set_vexpand(True)
		vbox.show_all()
		
		factory = handler.factory
		if factory:
			try:
				
				settings_widget = factory.create_settings_widget(handler)
			except Exception:
				notification.log_exception("Couldn't create settings widget")
			else:
				vbox.pack_end(settings_widget, True, True, 0)
				settings_widget.show()
				a_separator = Gtk.Separator()
				vbox.pack_end(a_separator, False, True, 0)
				a_separator.show()
		
		nickname_entry.connect("notify::text", self._refresh_title)
		handler_data.connect("removed", lambda hd: self.destroy())
		
		self._refresh_title()
	
	def _refresh_title(self, *data):
		nickname = self.handler.nickname
		factory =self.handler.factory
		if not nickname and factory:
			try:
				nickname = factory.label
				
			except Exception:
				notification.log_exception("Couldn't get factory label")
			
		if nickname:
			title = _("“{nickname}” Settings").format(nickname=nickname)
			
		else:
			title = _("Mouse Navigation Settings")
			
		self.set_title(title)
	
	def _mouse_button_presssed(self, widget, data):
		self.handler_data.button = data.button
	
	def _refresh_mouse_button(self, *data):
		button = self.handler_data.button
		if button == Gdk.BUTTON_PRIMARY:
			label = _("Primary Button")
			
		elif button == Gdk.BUTTON_MIDDLE:
			label = _("Middle Button")
			
		elif button == Gdk.BUTTON_SECONDARY:
			label = _("Secondary Button")
			
		else:
			label = _("Mouse Button #{number}").format(number=button)
		
		self.mouse_button_button.set_label(label)
		

import pynorama

def LoadForApp(app):
	app.zoom_effect = Settings.get_double("zoom-effect")
	app.spin_effect = Settings.get_int("rotation-effect")
	
	try:
		navigators_path = os.path.join(Directory, "navigators.xml")
		if not os.path.exists(navigators_path):
			data_dir = pynorama.ImageViewer.DataDirectory
			navigators_path = os.path.join(data_dir, "navigators.xml")
		
		LoadForMouseHandler(app.meta_mouse_handler, navigators_path)
		
	except Exception:
		notification.log_exception("Couldn't load mouse handler preferences")
		
		
def SaveFromApp(app):
	Settings.set_double("zoom-effect", app.zoom_effect)
	Settings.set_int("rotation-effect", app.spin_effect)
	
	try:
		os.makedirs(Directory, exist_ok=True)
		navigators_path = os.path.join(Directory, "navigators.xml")
		SaveFromMouseHandler(app.meta_mouse_handler, navigators_path)
		
	except Exception:
		notification.log_exception("Couldn't save mouse handler preferences")

def LoadForWindow(window):	
	window.toolbar_visible = Settings.get_boolean("interface-toolbar")
	window.statusbar_visible = Settings.get_boolean("interface-statusbar")
	
	hscrollbar = Settings.get_enum("interface-horizontal-scrollbar")
	vscrollbar = Settings.get_enum("interface-vertical-scrollbar")
	window.hscrollbar_placement = hscrollbar
	window.vscrollbar_placement = vscrollbar
	
	auto_zoom = Settings.get_boolean("auto-zoom")
	auto_zoom_minify = Settings.get_boolean("auto-zoom-minify")
	auto_zoom_magnify = Settings.get_boolean("auto-zoom-magnify")
	auto_zoom_mode = Settings.get_enum("auto-zoom-mode")
	
	window.set_auto_zoom_mode(auto_zoom_mode)
	window.set_auto_zoom(auto_zoom, auto_zoom_minify, auto_zoom_magnify)
	
	layout_codename = Settings.get_string("layout-codename")
	
	option_list = extending.LayoutOption.List
	for an_option in option_list:
		if an_option.codename == layout_codename:
			window.layout_option = an_option
			break

def SaveFromWindow(window):	
	Settings.set_boolean("interface-toolbar", window.toolbar_visible)
	Settings.set_boolean("interface-statusbar", window.statusbar_visible)
	
	hscrollbar = window.hscrollbar_placement
	vscrollbar = window.vscrollbar_placement
	Settings.set_enum("interface-horizontal-scrollbar", hscrollbar)
	Settings.set_enum("interface-vertical-scrollbar", vscrollbar)
	
	auto_zoom, auto_zoom_minify, auto_zoom_magnify = window.get_auto_zoom()
	auto_zoom_mode = window.get_auto_zoom_mode()
	
	Settings.set_boolean("auto-zoom", auto_zoom)
	Settings.set_boolean("auto-zoom-minify", auto_zoom_minify)
	Settings.set_boolean("auto-zoom-magnify", auto_zoom_magnify)
	Settings.set_enum("auto-zoom-mode", auto_zoom_mode)
	
	fullscreen = window.get_fullscreen()
	Settings.set_boolean("start-fullscreen", fullscreen)
	
	try:
		layout_codename = window.layout_option.codename
	except Exception:
		pass
		
	else:
		Settings.set_string("layout-codename", window.layout_option.codename)


def LoadForAlbum(album):
	album.freeze_notify()
	try:
		album.autosort = Settings.get_boolean("sort-auto")
		album.reverse = Settings.get_boolean("sort-reverse")
		
		comparer_value = Settings.get_enum("sort-mode")
		album.comparer = organization.SortingKeys.Enum[comparer_value]
		
	finally:
		album.thaw_notify()

	
def SaveFromAlbum(album):
	Settings.set_boolean("sort-auto", album.autosort)
	Settings.set_boolean("sort-reverse", album.reverse)
	
	comparer_value = organization.SortingKeys.Enum.index(album.comparer)
	Settings.set_enum("sort-mode", comparer_value)	


def LoadForView(view):
	view.freeze_notify()
	try:
		# Load alignment
		view.alignment_x = Settings.get_double("view-horizontal-alignment")
		view.alignment_y = Settings.get_double("view-vertical-alignment")
		
		# Load interpolation filter settings
		interp_min_value = Settings.get_enum("interpolation-minify")
		interp_mag_value = Settings.get_enum("interpolation-magnify")
		interp_map = [cairo.FILTER_NEAREST, cairo.FILTER_BILINEAR,
			          cairo.FILTER_FAST, cairo.FILTER_GOOD, cairo.FILTER_BEST]
		view.minify_filter = interp_map[interp_min_value]
		view.magnify_filter = interp_map[interp_mag_value]
	
	finally:
		view.thaw_notify()
	
	
def SaveFromView(view):
	# Save alignment
	Settings.set_double("view-horizontal-alignment", view.alignment_x)
	Settings.set_double("view-vertical-alignment", view.alignment_y)
	
	# Save interpolation filter settings
	interp_map = [cairo.FILTER_NEAREST, cairo.FILTER_BILINEAR,
	              cairo.FILTER_FAST, cairo.FILTER_GOOD, cairo.FILTER_BEST]
	interp_min_value = interp_map.index(view.minify_filter)
	interp_mag_value = interp_map.index(view.magnify_filter)
	Settings.set_enum("interpolation-minify", interp_min_value)
	Settings.set_enum("interpolation-magnify", interp_mag_value)


import xml.etree.ElementTree as ET
import collections

def LoadForMouseHandler(meta_mouse_handler, path):
	tree = ET.parse(path)
	mouse_el = tree.getroot()
	
	navigator_brands = dict()	
	for a_brand in extending.MouseHandlerBrands:
		navigator_brands[a_brand.codename] = a_brand
	
	# Create data structure for saving
	for a_handler_el in mouse_el:
		a_factory_codename = a_handler_el.get("brand", None)
		a_factory = navigator_brands.get(a_factory_codename, None)
		if a_factory:
			a_handler = a_factory.produce(element=a_handler_el)
			a_handler.nickname = a_handler_el.get("nickname", "")
			if a_handler.needs_button:
				button = int(a_handler_el.get("button", "0"))
			else:
				button = None
				
			meta_mouse_handler.add(a_handler, button=button)
			

def SaveFromMouseHandler(meta_mouse_handler, path):
	mouse_el = ET.Element("mouse")
	
	# Create data structure for saving
	for a_handler in meta_mouse_handler.get_handlers():
		a_factory = a_handler.factory
		if a_factory:
			a_handler_el = ET.SubElement(mouse_el, "navigator")
			# Set standard settings
			a_handler_data = meta_mouse_handler[a_handler]
			a_handler_el.set("brand", a_factory.codename)
			if a_handler.nickname:
				a_handler_el.set("nickname", a_handler.nickname)
	
			if a_handler.needs_button:
				a_handler_el.set("button", str(a_handler_data.button))
			
			# Fill element with abstract data
			a_factory.fill_xml(a_handler, a_handler_el)
			
	tree = ET.ElementTree(element=mouse_el)
	tree.write(path)


class PointScale(Gtk.DrawingArea):
	''' A widget like a Gtk.HScale and Gtk.VScale together. '''
	def __init__(self, hrange, vrange, square=False):
		Gtk.DrawingArea.__init__(self)
		self.set_size_request(50, 50)
		self.square = square
		if square:
			self.padding = 0
			self.mark_width = 32
			self.mark_height = 32
			
		else:
			self.padding = 4
			self.mark_width = 8
			self.mark_height = 8
			
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
		if self.square:
			hpadding = self.padding + self.mark_width / 2
			vpadding = self.padding + self.mark_height / 2
		else:
			hpadding, vpadding = self.padding, self.padding
		
		t, l = vpadding, hpadding
		r, b = w - hpadding, h - vpadding
		
		x, y = (max(0, min(r - l, x - l)) / (r - l),
		        max(0, min(b - t, y - t)) / (b - t))
		        
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
		return Gtk.SizeRequestMode.WIDTH_FOR_HEIGHT

	def do_get_preferred_width(self):
		hrange = self.get_hrange()
		lx, ux = hrange.get_lower(), hrange.get_upper()
		
		return 24, max(24, ux - lx)
					
	def do_get_preferred_height(self):
		vrange = self.get_vrange()
		ly, uy = vrange.get_lower(), vrange.get_upper()
		
		return 24, max(24, uy - ly)
	
	def do_get_preferred_height_for_width(self, width):
		hrange = self.get_hrange()
		vrange = self.get_vrange()
		lx, ux = hrange.get_lower(), hrange.get_upper()
		ly, uy = vrange.get_lower(), vrange.get_upper()
		
		ratio = (uy - ly) / (ux - lx)
		
		return width * ratio, width * ratio
			
	def do_get_preferred_width_for_height(self, height):
		hrange = self.get_hrange()
		vrange = self.get_vrange()
		lx, ux = hrange.get_lower(), hrange.get_upper()
		ly, uy = vrange.get_lower(), vrange.get_upper()
		
		ratio = (ux - lx) / (uy - ly)
		
		return height * ratio, height * ratio
		
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
		if self.square:
			hpadding = self.padding + self.mark_width / 2
			vpadding = self.padding + self.mark_height / 2
		else:
			hpadding, vpadding = self.padding, self.padding
		
		t, l = vpadding, hpadding
		r, b = w - hpadding, h - vpadding
				
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
		radius = style.get_property(Gtk.STYLE_PROPERTY_BORDER_RADIUS,
		                            Gtk.StateFlags.NORMAL)
		color = style.get_color(style.get_state())
		cr.arc(border.left + radius,
		       border.top + radius, radius, math.pi, math.pi * 1.5)
		cr.arc(w - border.right - radius -1,
		       border.top + radius, radius, math.pi * 1.5, math.pi * 2)
		cr.arc(w - border.right - radius -1,
		       h -border.bottom - radius -1, radius, 0, math.pi / 2)
		cr.arc(border.left + radius,
		       h - border.bottom - radius - 1, radius, math.pi / 2, math.pi)
		cr.clip()
		
		cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
		x, y = round(x), round(y)
		
		if self.square:
			ml, mt = x - self.mark_width / 2, y - self.mark_height / 2
			mr, mb = ml + self.mark_width, mt + self.mark_height
			ml, mt, mr, mb = round(ml), round(mt), round(mr), round(mb)
			
			cr.set_line_width(1)
			cr.set_dash([3, 7], x + y)
			cr.move_to(ml, 0); cr.line_to(ml, h); cr.stroke()
			cr.move_to(mr, 0); cr.line_to(mr, h); cr.stroke()
			cr.move_to(0, mt); cr.line_to(w, mt); cr.stroke()
			cr.move_to(0, mb); cr.line_to(w, mb); cr.stroke()
			
			cr.set_dash([], 0)
			cr.rectangle(ml, mt, self.mark_width, self.mark_height)
			cr.stroke()
		
		else:
			cr.set_line_width(1)
			cr.set_dash([3, 7], x + y)
			cr.move_to(x, 0); cr.line_to(x, h); cr.stroke()
			cr.move_to(0, y); cr.line_to(w, y); cr.stroke()
			
			cr.save()
			cr.translate(x, y)
			cr.scale(self.mark_width * 3, self.mark_height * 3)
			cr.arc(0, 0, 1, 0, 2 * math.pi)
			cr.restore()
			cr.stroke()
			
			cr.set_dash([], 0)
			
			cr.save()
			cr.translate(x, y)
			cr.scale(self.mark_width / 2, self.mark_height / 2)
			cr.arc(0, 0, 1, 0, 2 * math.pi)
			cr.restore()
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
