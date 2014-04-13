""" openers.py adds a few file openers to the image viewer.
    
    See opening.py for information on how openers work.
    
    The openers defined here are:
        DirectoryOpeneer for opening directory files;
        PixbufOpener for GdkPixbuf supported files and selection data;
        PixbufAnimationOpener for animated image files supported by GdkPixbuf;
        URIListOpener for D'n'D'd or pasted uri lists/files;
        TextOpener for parsing pasted text into URIs; """

""" ...and this file is part of Pynorama.
    
    Pynorama is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    Pynorama is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with Pynorama. If not, see <http://www.gnu.org/licenses/>. """


from gettext import gettext as _
from os import path as os_path
from urllib.parse import urlparse

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject

from pynorama.extending import FileOpener, SelectionOpener
from pynorama import extending, opening
from . import loaders

class DirectoryOpener(FileOpener):
    """ Opens directories and yields the files inside them """
    
    CODENAME = "directory"
    
    def __init__(self):
        FileOpener.__init__(self,
            DirectoryOpener.CODENAME,
            mime_types={"inode/directory"}
        )
        self.show_on_dialog = False
    
    
    @GObject.Property
    def label(self):
        return _("Directory")
    
    
    def open_file(self, context, results, source):
        """ Opens a directory file and yields its contents """
        
        source.gfile.enumerate_children_async(
            opening.STANDARD_GFILE_INFO_STRING,
            0,
            GLib.PRIORITY_DEFAULT,
            None,
            self._enumerate_children_async_cb,
            (context, results, source)
        )
    
    
    def _enumerate_children_async_cb(self, gfile, async_result, data):
        context, results, source = data
        gfile = source.gfile
        try:
            gfile_enumerator = gfile.enumerate_children_finish(async_result)
        except Exception as e:
            results.errors.append(e)
        else:
            get_child_for_display_name = gfile.get_child_for_display_name
            append_source = results.sources.append
            file_source = opening.GFileFileSource
            
            for a_file_info in gfile_enumerator:
                try:
                    child_name = a_file_info.get_display_name()
                    a_child_file = get_child_for_display_name(child_name)
                    a_file_source = file_source(
                        a_child_file, name=child_name, parent=source
                    )
                    a_file_source.info = a_file_info
                    append_source(a_file_source)
                    
                except Exception as e:
                    results.errors.append(e)
                
            gfile_enumerator.close_async(
                GLib.PRIORITY_DEFAULT,
                None,
                self._close_async_cb,
                None
            )
        finally:
            results.complete()
    
    
    def _close_async_cb(self, enumerator, async_result, *etc):
        enumerator.close_finish(async_result)


class PixbufOpener(SelectionOpener, FileOpener):
    """
    Opens image files supported by the GdkPixbuf library
    
    Also opens selections whose target is supported by the GdkPixbuf library
    
    """
    
    CODENAME = "gdk-pixbuf"
    
    def __init__(self):
        # Get the GdkPixbuf supported extensions and mime types
        extensions, mime_types = set(), set()
        formats = GdkPixbuf.Pixbuf.get_formats()
        for a_format in formats:
            mime_types.update(a_format.get_mime_types())
            for an_extension in a_format.get_extensions():
                extensions.add(an_extension)
        
        FileOpener.__init__(self, 
            PixbufOpener.CODENAME, 
            extensions, 
            mime_types
        )
        SelectionOpener.__init__(self,
            PixbufOpener.CODENAME,
            mime_types
        )
    
    
    @GObject.Property
    def label(self):
        return _("GdkPixbuf Images")
    
    
    def open_file(self, context, results, source):
        try:
            new_image = loaders.PixbufFileImageSource(source)
        except Exception as e:
            results.errors.append(e)
        else:
            results.images.append(new_image)
        results.complete()
    
    
    def open_selection(self, results, selection):
        """
        Gets a pixbuf from a Gtk.SelectionData and creates an image source
        from it.
        
        """
        pixbuf = selection.get_pixbuf()
        image_source = loaders.PixbufDataImageSource(pixbuf)
        results.images.append(image_source)
        results.complete()


class PixbufAnimationFileOpener(FileOpener):
    """ Opens animated image files supported by the GdkPixbuf library """
    
    # ...is what I'd like to say. But there is no way to check the
    # supported extensions/mimes for animations, so it only opens gif files.
    CODENAME = "gdk-pixbuf-animation"
    
    def __init__(self):
        FileOpener.__init__(self,
            PixbufAnimationFileOpener.CODENAME,
            {".gif"},
            {"image/gif"}
        )
    
    
    @GObject.Property
    def label(self):
        return _("GdkPixbuf Animations")
    
    
    def open_file(self, context, results, gfile):
        try:
            new_image = loaders.PixbufAnimationFileImageSource(
                gfile,
                opening_context=context
            )
        except Exception as e:
            results.errors.append(e)
        else:
            results.images.append(new_image)
            
        results.complete()


class URIListSelectionOpener(SelectionOpener):
    """ Opens selections whose target is "text/uri-list" """
    CODENAME = "uri-list"
    
    def __init__(self):
        SelectionOpener.__init__(self,
            URIListSelectionOpener.CODENAME,
            ["text/uri-list"]
        )
    
    
    @GObject.Property
    def label(self):
        return _("URI list")
    
    
    def open_selection(self, results, selection):
        uris = selection.get_uris()
        if uris:
            results.uris.extend(uris)
        results.complete()


class TextSelectionOpener(SelectionOpener):
    """ Opens selections whose target is "text/plain" as URIs """
    CODENAME = "uri-text"
    
    def __init__(self):
        # XXX: This is essentially the Gtk.SelectionData uses
        # for checking whether its targets_include_text
        # Except here it's missing the text/plain;charset=locale
        # because I can't find the g_get_charset method
        SelectionOpener.__init__(self,
            TextSelectionOpener.CODENAME,
            [
                "UTF8_STRING",
                "TEXT",
                "COMPOUND_TEXT",
                "text/plain",
                "text/plain;charset=utf-8",
            ]
        )
        self.atom_targets.add(Gdk.TARGET_STRING)
    
    
    @GObject.Property
    def label(self):
        return _("URI Text")
    
    
    def open_selection(self, results, selection):
        text = selection.get_text()
        
        parse_result = urlparse(text)
        if parse_result.scheme and parse_result.path \
                and (parse_result.netloc or parse_result.scheme == "file"):
            results.uris.append(text)
        else:
            # Expanding "~"
            text = os_path.expanduser(text)
            if os_path.isabs(text):
                # Wildly assuming this is a valid filename
                # just because it starts with a slash
                text = "file://" + os_path.normcase(os_path.normcase(text))
                results.uris.append(text)
            
        results.complete()


class BuiltInOpeners(extending.ComponentPackage):
    """ A component package for installing the built in openers """
    @staticmethod
    def add_on(app):
        components = app.components
        pixbuf_opener = PixbufOpener()
        directory_opener = DirectoryOpener()
        file_openers = (
            directory_opener, # Opens directories
            pixbuf_opener, # Opens images
            PixbufAnimationFileOpener(), # Opens animations
        )
        for an_opener in file_openers:
            components.add(FileOpener.CATEGORY, an_opener)
        
        selection_openers = (
            pixbuf_opener, # Opens images
            URIListSelectionOpener(), # Opens uri lists
            TextSelectionOpener() # Tries to parse text into uris
        )
        for an_opener in selection_openers:
            components.add(SelectionOpener.CATEGORY, an_opener)
        components.add(opening.PARENT_OPENER_CATEGORY, directory_opener)

extending.LoadedComponentPackages["openers"] = BuiltInOpeners
