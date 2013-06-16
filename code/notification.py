# coding=utf-8

''' notification.py has contains functions to message the user '''

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

def log(message):
	print(message)

from traceback import print_exc
def log_exception(heading):
	print("=" * 60)
	print(heading)
	print("-" * 60)
	print_exc()
	
from gi.repository import Gtk

def alert(message, window = None, fatal_error = False):
	msg_type = Gtk.MessageType.ERROR if fatal_error else Gtk.MessageType.WARNING
	dialog = Gtk.MessageDialog(window, Gtk.DialogFlags.MODAL, msg_type,
	                           Gtk.ButtonsType.OK, message)
	dialog.run()
	dialog.destroy()

def alert_list(message, items, columns, window = None, fatal_error = False):
	msg_type = Gtk.MessageType.ERROR if fatal_error else Gtk.MessageType.WARNING
	dialog = Gtk.MessageDialog(window, Gtk.DialogFlags.MODAL, msg_type,
	                           Gtk.ButtonsType.OK, message)
	dialog.set_has_resize_grip(True)
	
	if columns:
		list_store = Gtk.ListStore(*([str] * len(columns)))
	else:
		list_store = Gtk.ListStore(str)
	
	for list_item in items:
		list_store.append(list_item)
		
	list_view = Gtk.TreeView(list_store)
	if columns:
		for i in range(len(columns)):
			a_column_title = columns[i]
			a_column = Gtk.TreeViewColumn(a_column_title,
			                              Gtk.CellRendererText(),
			                              text=i)
			list_view.append_column(a_column)
			
	list_view.set_reorderable(True)
	list_view.set_headers_visible(bool(columns))
	list_view.columns_autosize()
	list_view.set_grid_lines(Gtk.TreeViewGridLines.VERTICAL)
	list_view.set_rules_hint(True)
	list_scroller = Gtk.ScrolledWindow()
	list_scroller.add(list_view)
	list_scroller.set_size_request(400, 300)
	list_scroller.set_shadow_type(Gtk.ShadowType.IN)
	dialog.get_content_area().pack_end(list_scroller, True, True, 12)
	list_scroller.show_all()
	dialog.run()
	dialog.destroy()	

from gettext import gettext as _
class Lines:
	@staticmethod
	def Loading(something):
		return _("Loading “{something}”…").format(something=something)
		
	@staticmethod
	def Loaded(something):
		return _("Loaded “{something}”").format(something=something)
	
	@staticmethod
	def Unloaded(something):
		return _("Unloaded “{something}”").format(something=something)
				
	@staticmethod
	def Error(summary):
		return _("Error: {summary}").format(summary=summary)
