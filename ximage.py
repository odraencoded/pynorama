import gc
from gi.repository import Gtk, GdkPixbuf, GObject

class xImage(Gtk.Viewport):
	# This provides some transform features for gtk.Image
	__gtype_name__ = "xImage"
	__gsignals__ = {
        "pixbuf-notify": (GObject.SIGNAL_RUN_FIRST, None, ())
    }
	''' This is a limit on the number of pixels of an
	    Image while zoomed in or out, it is silly.
	    Got to make it customizable one day '''
	zoom_pixel_limit = (512, 15000 * 15000)
	
	def __init__(self):
		Gtk.Layout.__init__(self)
		
		self.image = Gtk.Image()
		self.add(self.image)
		self.image.show()
		
		self.source = None
		self.pixbuf = None
		self.magnification = 1
		self.rotation = 0
		
		# There are two interpolation settings: Zoom out and zoom in
		self.interpolation = (GdkPixbuf.InterpType.BILINEAR, GdkPixbuf.InterpType.NEAREST)
		
		self.flip_horizontal = False
		self.flip_vertical = False
		
		#self.image.connect("size-allocate", self.update_size)
	
	def get_interpolation(self):
		# This gets the currently used interpolation.
		if self.magnification < 1:
			return self.interpolation[0]
			
		if self.magnification > 1:
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
			if self.magnification < 1:
				mag = self.magnification
				
				sw, sh = int(self.source.get_width() * mag), int(self.source.get_height() * mag)
				valid_size = (sw * sh) >= xImage.zoom_pixel_limit[0]
				if not valid_size:
					print("%sx%s is not a valid size" %(sw, sh))
					pixel_count = self.source.get_width() * self.source.get_height()
					mag = (xImage.zoom_pixel_limit[0] / float(pixel_count)) ** .5
					sw, sh = int(self.source.get_width() * mag), int(self.source.get_height() * mag)
					
				print("%sx%s is a valid size" %(sw, sh))
				if mag < 1:
					self.pixbuf = self.pixbuf.scale_simple(sw, sh, self.interpolation[0])
			
			if self.flip_vertical:
				self.pixbuf = self.pixbuf.flip(False)
			
			if self.flip_horizontal:
				self.pixbuf = self.pixbuf.flip(True)
		
			if self.rotation:
				self.pixbuf = self.pixbuf.rotate_simple(self.rotation)
			
			# The interpolation of "zoom in" is the second one in the tuple
			if self.magnification > 1:
				mag = self.magnification
				
				sw, sh = int(self.source.get_width() * mag), int(self.source.get_height() * mag)
				valid_size = (sw * sh) <= xImage.zoom_pixel_limit[1]
				if not valid_size:
					pixel_count = self.source.get_width() * self.source.get_height()
					mag = (xImage.zoom_pixel_limit[1] / float(pixel_count)) ** .5
					sw, sh = int(self.source.get_width() * mag), int(self.source.get_height() * mag)
					
				if mag > 1:
					self.pixbuf = self.pixbuf.scale_simple(sw, sh, self.interpolation[1])
			
			gc.collect()
			
		self.image.set_from_pixbuf(self.pixbuf)
		self.emit("pixbuf-notify")
	
	def update_size(self, widget=None, data=None):
		img_allocation = self.image.get_allocation()
		my_allocation = self.get_allocation()
		
		if img_allocation.width > my_allocation.width:
			width = img_allocation.width
		else:
			width = my_allocation.width
			
		if img_allocation.height > my_allocation.height:
			height = img_allocation.height
		else:
			height = my_allocation.height
			
		self.set_size(width, height)
		
GObject.type_register(xImage)
