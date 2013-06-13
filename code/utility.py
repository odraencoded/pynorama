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
		if not self._signal_id:
			self._signal_id = GLib.idle_add(
			     self._execute_queue, priority=self.priority)
		
		self._queued = True
		
	def cancel_queue(self):
		if self._signal_id:
			GLib.source_remove(self._signal_id)
			self._signal_id = None
			self._queued = False
			
	def _execute_queue(self):
		self._queued = False
		self()
		
		if not self._queued:
			self._signal_id = None
		
		return self._queued
