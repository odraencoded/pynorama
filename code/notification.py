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

import traceback, sys

from sys import stdout, stderr

# ANSI color codes for console colouring
ColorCodes = {
    "preferences": "\x1b[34;1m", # Blue
    "interface": "\x1b[33;1m", # Bright yellow
    "opening": "\x1b[33m", # Yellow
    "loading": "\x1b[32;1m", # Green
    "error": "\x1b[37;41;1m", # Red
    "error": "\x1b[31;1m" # Red
}

RESET_COLOR_CODE = "\x1b[0m" # Resets the color
SEPARATOR_LENGTH = 40 # Length of ~~~~~~~....~~~~ separators.

class Logger:
    """ Fancy class for fancy logging """
    
    Last = ""
    
    def __init__(self, codename):
        self.codename = codename
        self._prefix = ColorCodes.get(codename, "")
        if self._prefix:
            self._suffix = RESET_COLOR_CODE
        else:
            self._suffix = ""
    
    
    def log(self, message):
        self._replace_last(stdout)
        print(self._prefix + message + self._suffix)
    
    
    def log_list(self, iterable):
        message = "\n".join("* " + str(i) for i in iterable)
        self.log(message)
    
    
    def log_dict(self,  dictionary):
        message = "\n".join("* %s: %s" % (k, v) for k, v in dictionary.items())
        self.log(message)
    
    
    def log_error(self, message):
        self._replace_last(stderr)
        
        error_code = ColorCodes["error"]
        print(error_code + message + RESET_COLOR_CODE, file=stderr)
    
    
    def log_exception(self, exception=None):
        if exception is None:
            # Print the current exception
            self.log_exception_info(*sys.exc_info())
        else:
            self.log_exception_info(None, exception, None)
    
    
    def log_exception_info(self, exc_type, exc, exc_tb):
        message_list = traceback.format_exception(exc_type, exc, exc_tb)
        message = "\n".join(message_list)
        self.log_error(message)
    
    
    if __debug__:
        debug = log
        debug_dict = log_dict
        debug_list = log_list
        def _replace_last(self, file):
            """
            Prints a separating line if the last Logger's codename
            was different from this logger codename.
            
            """
            if Logger.Last != self.codename:
                Logger.Last = self.codename
                sep_length = max(SEPARATOR_LENGTH - len(self.codename), 2)
                half_length = sep_length / 2
                separators = "~" * int(half_length)
                print(separators, self.codename, separators, file=file)
    else:
        def debug(*stuff, **more_stuff): pass
        _replace_last = debug_list = debug_dict = debug


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
