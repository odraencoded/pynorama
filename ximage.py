import gtk, gobject

class xImage(gtk.Bin):
	'''
		This provides more features for gtk.Image
	'''
	__gtype_name__ = 'xImage'
		
	def __init__(self):
		gtk.Bin.__init__(self)
		
		self.image = gobject.new(gtk.Image)
		self.add(self.image)
		self.image.show()
				
		self.source = None
		self.pixbuf = None
		self.magnification = 0
		self.rotation = gtk.gdk.PIXBUF_ROTATE_NONE
		
		self.interpolation = gtk.gdk.INTERP_NEAREST
		
		self.flip_horizontal = False
		self.flip_vertical = False
		
	def refresh_pixbuf(self):
		self.pixbuf = self.source
		
		if self.pixbuf:
			if self.magnification:
				scale = 2 ** self.magnification
				sw, sh = int(self.source.get_width() * scale), int(self.source.get_height() * scale)
				
				self.pixbuf = self.pixbuf.scale_simple(sw, sh, self.interpolation)
				
			if self.flip_vertical:
				self.pixbuf = self.pixbuf.flip(False)
				
			if self.flip_horizontal:
				self.pixbuf = self.pixbuf.flip(True)
			
			if self.rotation:
				self.pixbuf = self.pixbuf.rotate_simple(self.rotation)
			
		self.image.set_from_pixbuf(self.pixbuf)
		
		self.emit("updated_pixbuf")
		
	def do_size_allocate(self, allocation):
		self.child.size_allocate(allocation)
		self.allocation = allocation
		
	def do_size_request(self, requisition):
		requisition.width, requisition.height = self.image.size_request()
		
		
gobject.type_register(xImage)
gobject.signal_new("updated_pixbuf", xImage, gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, ())
