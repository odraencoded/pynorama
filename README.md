pynorama
========

Pynorama is an image viewer. It *views* images.

Features
--------

As of version v0.2.1 pynorama is able to

* Load and display one image
* Find images in a directory and load them
* Open images dragged into the window 
* Open images pasted from the clipboard
* Navigate through multiple images
* Sort images by name, modification date or size
* Zoom, rotate and flip images
* Zoom, rotate and pan images using the mouse
* Automatically zoom an image to fit or fill the window
* Change how images are interpolated
* Display or hide the scrollbars, toolbar and statusbar
* Enter and leave fullscreen

Things to Know
--------------

There is currently no way to customize hotkeys or mouse behavior.
The default mouse behaviour is:

- Move the mouse to pan the image
- Drag the left button to drag the image
- Drag the right button to spin the image
- Drag the middle button to stretch the image
- Scroll the scroll wheel to scroll the image

There is currently __no build system__ for the application.

### Requirements

Pynorama requires a python3 interpreter, Gtk3 and gobject introspection modules.
It also requires pynorama.gschema.xml to be installed and compiled.

Good luck with that.

### License

Pynorama is licensed under the GNU General Public License 3.
