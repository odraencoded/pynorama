import gc
from gi.repository import Gtk, GdkPixbuf, GObject

class xImage(Gtk.Bin):
	'''
		This provides some features for gtk.Image
	'''
	__gtype_name__ = "xImage"
	__gsignals__ = {
        "pixbuf-notify": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
	# This is a limit on the number of pixels of an
	# Image while zoomed in or out
	# Got to make it customizable one day
	zoom_pixel_limit = (64, 15000 * 15000)
	
	def __init__(self):
		Gtk.Bin.__init__(self)
		
		self.image = Gtk.Image()
		self.add(self.image)
		self.image.show()
		
		self.source = None
		self.pixbuf = None
		self.magnification = 0
		self.zoom_base = 2
		self.rotation = 0
		
		# There are two interpolation settings: Zoom out and zoom in
		self.interpolation = (GdkPixbuf.InterpType.BILINEAR, GdkPixbuf.InterpType.NEAREST)
		
		self.flip_horizontal = False
		self.flip_vertical = False
		
	def get_zoom(self):
		return self.zoom_base ** self.magnification
	
	def get_interpolation(self):
		# This gets the currently used interpolation.
		if self.magnification < 0:
			return self.interpolation[0]
			
		if self.magnification > 0:
			return self.interpolation[1]
			
		# If not magnified, no interpolation is used, obviously
		return None
	
	def set_interpolation(self, value, other_value = None):
		# This sets the currently used interpolation or both
		if other_value is None:
			if self.magnification < 0:
				self.interpolation = (value, self.interpolation[1])
				
			elif self.magnification > 0:
				self.interpolation = (self.interpolation[0], value)
				
		else:
			self.interpolation = (value, other_value)
			
	def refresh_pixbuf(self):
		self.pixbuf = self.source
		
		if self.pixbuf:
			# The interpolation of "zoom-out" is the first one in the tuple
			if self.magnification < 0:
				valid_size = False
				while not valid_size:
					scale = self.get_zoom()					
					sw, sh = int(self.source.get_width() * scale), int(self.source.get_height() * scale)
					
					pixel_count = sw * sh
					valid_size = (sw * sh) >= xImage.zoom_pixel_limit[0]
					
					if self.magnification >= 0:
						break
					elif not valid_size:
						self.magnification += 1
						
				if self.magnification < 0:
					self.pixbuf = self.pixbuf.scale_simple(sw, sh, self.interpolation[0])
			
			if self.flip_vertical:
				self.pixbuf = self.pixbuf.flip(False)
			
			if self.flip_horizontal:
				self.pixbuf = self.pixbuf.flip(True)
		
			if self.rotation:
				self.pixbuf = self.pixbuf.rotate_simple(self.rotation)
			
			# The interpolation of "zoom in" is the second one in the tuple
			if self.magnification > 0:
				valid_size = False
				while not valid_size:
					scale = self.get_zoom()
					sw, sh = int(self.source.get_width() * scale), int(self.source.get_height() * scale)
					
					pixel_count = sw * sh
					valid_size = (sw * sh) <= xImage.zoom_pixel_limit[1]
					
					if self.magnification <= 0:
						break
					elif not valid_size:
						self.magnification -= 1
						
				if self.magnification > 0:
					self.pixbuf = self.pixbuf.scale_simple(sw, sh, self.interpolation[1])
			
			gc.collect()
			
		self.image.set_from_pixbuf(self.pixbuf)
		self.emit("pixbuf-notify")
		
	def do_size_allocate(self, allocation):
		self.get_child().size_allocate(allocation)
		self.set_allocation(allocation)
		
	def do_get_preferred_width(self):
		return self.image.get_preferred_width()
		
	def do_get_preferred_height(self):
		return self.image.get_preferred_height()
		
GObject.type_register(xImage)
