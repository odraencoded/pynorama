pynorama
========

Pynorama is an image viewer. It *views* images.

![a screenshot](http://i.imgur.com/vaXdV9C.png)
![another screenshot](http://i.imgur.com/HcmHecj.png)

Features
--------

* Supports zooming, spinning and flipping images
* Supports panning, zooming and spinning images _with the mouse_
* Opens directories, dropped files, pasted images, even from the internet
* Navigates through multiple opened images, can display multiples images at once
* Has _six_ automatic zoom options, including fit and fill
* Can hide scrollbars, statusbar and toolbar
* Comes with really, *really* many menu items
* Hardware accelerated

Things to Know
--------------

There is currently no way to customize hotkeys or mouse behavior.
The default mouse behaviour is:

- Move the mouse to pan the image
- Drag the left button to drag the image
- Drag the right button to spin the image
- Drag the middle button to stretch the image
- Scroll the scroll wheel to scroll the image

### Installing

Pynorama requires a python3 interpreter, Gtk3, Cairo and
GObject introspection bindings. Debian users can get the packages required with
`apt-get install libgtk-3-0 python3 python3-gi python3-gi-cairo python3-cairo`

You can install Pynorama using autotools with the command
`./configure && make && make install`

If there is no configure script, you can create it using
`aclocal && autoconf && automake --foreign --add-missing`

And then use the autotools command above to install Pynorama.

### License

Pynorama is licensed under the GNU General Public License 3.
