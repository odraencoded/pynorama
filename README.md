pynorama
========

Pynorama is an image viewer. It *views* images.

![a screenshot](http://i.imgur.com/vaXdV9C.png)
![another screenshot](http://i.imgur.com/HcmHecj.png)

Features
--------

*   Supports zooming, spinning and flipping images
*   Supports panning, zooming and spinning images _with the mouse_
*   Opens directories, dropped files, pasted images, even from the internet
*   Navigates through multiple opened images,
    can display multiple images at once
*   Has _six_ automatic zoom options, including fit and fill
*   Can hide scrollbars, statusbar and toolbar
*   Comes with really, *really* many menu items
*   Hardware accelerated

Things to Know
--------------

### Hotkeys

There is currently no way to customize hotkeys.


### Mouse Mechanisms

A mouse mechanism controls what mouse interaction does in pynorama. Currently,
there are seven different mouse mechanisms avaiable

*  Drag to Pan
*  Move Mouse to Pan
*  Drag to Spin
*  Drag to Stretch
*  Scroll to Pan
*  Scroll to Zoom
*  Scroll to Spin

Each of these mechanisms have their own settings and can be added multiple
times. For mechanisms that use a mouse button, the button can be choosen with
a mouse click in the mechanism setting dialog.

### Layouts

A layout is a way to place images in pynorama. Currently, there are two
different layouts avaiable

*   The Single Image Layout

    Places a single image in the image viewer.
    Any image viewer can do this.
  
*   The Image Strip Layout
  
    This one places sequential images side by side in the image viewer.
    A handful of comic viewers can do this.

The layout used by pynorama can be changed at any time in
the *Layout* submenu of the *View* menu.

### Installing

Pynorama requires a python3 interpreter, Gtk3, Cairo and
GObject introspection bindings. Debian users can get the packages required with
`apt-get install libgtk-3-0 python3 python3-gi python3-gi-cairo python3-cairo`

You can install Pynorama using autotools with the command
`./configure && make && make install`

If there is no configure script, you can create it using
`aclocal && autoconf && automake --foreign --add-missing`

And then use the autotools command above to install Pynorama.

Use the code/run.py script to run the program without installing it.

### License

Pynorama is licensed under the GNU General Public License 3.
