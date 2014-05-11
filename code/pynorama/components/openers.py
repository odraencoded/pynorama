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


import os 
from os import path as os_path
import tempfile
from gettext import gettext as _
from urllib.parse import urlparse

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk

from pynorama import extending, opening
from pynorama.extending import Opener, OpenerGuesser, SelectionOpener
from pynorama.opening import GFileSource, URISource, SelectionSource
from . import loaders

class GFileOpener:
    """ An interface to open files for the image viewer.
    
    File openers yield image sources or other files which are then
    opened by other file openers.
    
    """
    
    def __init__(self, extensions=None, mime_types=None):
        """ Initializes a file opener for certain extensions and mime_types """
        
        # These two variables are used to guess which 
        # file opener should open which file
        self.extensions = extensions if extensions is not None else set()
        """ A set of common extensions for this file opener supported files """
        
        self.mime_types = mime_types if mime_types is not None else set()
        """ A set of mime_types for this file opener supported files """
        
        self.show_on_dialog = True
        """ Whether to show this file opener in the "Open image" dialog """
        
        self._file_filter = None
    
    
    def get_file_filter(self):
        """ Returns a file filter for this file opener """
        if not self._file_filter:
            self._file_filter = file_filter = Gtk.FileFilter()
            file_filter.set_name(self.label)
            
            for an_extension in self.extensions:
                file_filter.add_pattern("*." + an_extension)
            for a_mime_type in self.mime_types:
                file_filter.add_mime_type(a_mime_type)
                
        return self._file_filter


class GFileOpenerGuesser(OpenerGuesser):
    CODENAME = "gfile"
    def __init__(self):
        OpenerGuesser.__init__(self,
                               GFileOpenerGuesser.CODENAME,
                               GFileSource.KIND)
    
    
    def guess(self, source, openers):
        # The context openers are iterated in reverse because the openers
        # added last have higher priority and may "override" how certain
        # types of files are opened
        
        gfile_info = source.info
        
        flags = Gtk.FileFilterFlags
        gfile_filter_info = Gtk.FileFilterInfo()
        gfile_filter_info.contains = flags.DISPLAY_NAME | flags.MIME_TYPE
        gfile_filter_info.display_name = gfile_info.get_display_name()
        gfile_filter_info.mime_type = gfile_info.get_content_type()
        
        for an_opener in openers:
            if an_opener.get_file_filter().filter(gfile_filter_info):
                return an_opener
        else:
            return None


# TODO define this interface
class URIOpener:
    """ An interfaces to open images from URIs """
    def __init__(self):
        pass


# really only being used for the fallback now
class URIOpenerGuesser(OpenerGuesser):
    CODENAME = "uri"
    def __init__(self):
        OpenerGuesser.__init__(self,
                               URIOpenerGuesser.CODENAME,
                               URISource.KIND)
    
    
    def guess(self, source, openers):
        # TODO implement this
        return None


class DirectoryOpener(Opener, GFileOpener):
    """ Opens directories and yields the files inside them """
    
    CODENAME = "directory"
    
    def __init__(self):
        Opener.__init__(self, DirectoryOpener.CODENAME, GFileSource.KIND)
        GFileOpener.__init__(self, mime_types={"inode/directory"})
        self.show_on_dialog = False
    
    
    @GObject.Property
    def label(self):
        return _("Directory")
    
    
    def open_file_source(self, context, results, source):
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
            file_source = opening.GFileSource
            
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


class PixbufOpener(Opener, SelectionOpener, GFileOpener):
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
        
        Opener.__init__(
            self, PixbufOpener.CODENAME,
            GFileSource.KIND
        )
        GFileOpener.__init__(self, extensions, mime_types)
        SelectionOpener.__init__(self, PixbufOpener.CODENAME, mime_types)
    
    
    @GObject.Property
    def label(self):
        return _("GdkPixbuf Images")
    
    
    def open_file_source(self, context, results, source):
        if source.KIND == GFileSource.KIND:
            new_image = loaders.PixbufFileImageSource(source)
            results.images.append(new_image)
        
        results.complete()
    
    
    def open_selection(self, context, results, selection, source):
        """
        Gets a pixbuf from a Gtk.SelectionData and creates an image source
        from it.
        
        """
        pixbuf = selection.get_pixbuf()
        source.setImageContentName()
        
        image_source = loaders.PixbufDataImageSource(pixbuf, source)
        results.images.append(image_source)
        
        results.complete()


class PixbufAnimationFileOpener(Opener, GFileOpener):
    """ Opens animated image files supported by the GdkPixbuf library """
    
    # ...is what I'd like to say. But there is no way to check the
    # supported extensions/mimes for animations, so it only opens gif files.
    CODENAME = "gdk-pixbuf-animation"
    
    def __init__(self):
        Opener.__init__(
            self,PixbufAnimationFileOpener.CODENAME,
            GFileSource.KIND
        )
        GFileOpener.__init__(self, {".gif"}, {"image/gif"})
    
    
    @GObject.Property
    def label(self):
        return _("GdkPixbuf Animations")
    
    
    def open_file_source(self, context, results, source):
        try:
            new_image = loaders.PixbufAnimationFileImageSource(source)
        except Exception as e:
            results.errors.append(e)
        else:
            results.images.append(new_image)
            
        results.complete()


class URICacheFallbackOpener(Opener, URIOpener):
    """ Downloads URIs into the cache and returns GFiles to open them """
    CODENAME = "uri-cache"
    
    def __init__(self):
        Opener.__init__(self,
                        URICacheFallbackOpener.CODENAME,
                        GFileSource.KIND)
        URIOpener.__init__(self)
    
    
    @GObject.Property
    def label(self):
        return _("GdkPixbuf Animations")
    
    
    def open_file_source(self, context, results, source):
        state = URICacheFallbackOpener.CachingState(context, results, source)
        
        # Get extension from URI
        suffix = ""
        dot_split = source.uri.rsplit(".", maxsplit=1)
        if dot_split:
            after_dot_split = dot_split[-1]
            if "/" not in after_dot_split:
                suffix = "." + after_dot_split
        
        file_descriptor, state.cache_path = tempfile.mkstemp(
           dir=context.cache_directory, suffix=suffix)
        
        os.close(file_descriptor) # won't need this open... probably
        
        state.files = [
            Gio.File.new_for_uri(source.uri),
            Gio.File.new_for_path(state.cache_path)
        ]
        state.cancellables = [Gio.Cancellable(), Gio.Cancellable()]
        
        state.files[0].read_async(
            GLib.PRIORITY_DEFAULT,
            state.cancellables[0],
            self._async_cb,
            (True, state)
        )
        state.files[1].append_to_async(
            Gio.FileCreateFlags.REPLACE_DESTINATION,
            GLib.PRIORITY_DEFAULT,
            state.cancellables[1],
            self._async_cb,
            (False, state)
        )
    
    
    class CachingState:
        def __init__(self, context, results, source):
            self.context = context
            self.results = results
            self.source = source
            self.streams = [None, None]
            self.cancelled = False
    
    
    def _async_cb(self, gfile, result, data):
        uri_version, state = data
        this, other = (0, 1) if uri_version else (1, 0)
        
        try:
            if uri_version:
                stream = gfile.read_finish(result)
            else:
                stream = gfile.append_to_finish(result)
        except Exception as e:
            if not state.cancelled:
                state.cancelled = True
                state.cancellables[other].cancel()
                
                state.results.errors.append(e)
                state.results.complete()
        else:
            state.streams[this] = stream
            if state.streams[other]:
                state.splice_cancellable = Gio.Cancellable()
                state.streams[1].splice_async(
                    state.streams[0],
                    (Gio.OutputStreamSpliceFlags.CLOSE_SOURCE |
                     Gio.OutputStreamSpliceFlags.CLOSE_TARGET),
                    GLib.PRIORITY_LOW,
                    state.splice_cancellable,
                    self._splice_cb,
                    state
                )
                uri_stream = state.streams[0]
        finally:
            state.cancellables[this] = None
    
    
    def _splice_cb(self, stream, result, state):
        try:
            stream.splice_finish(result)
        except Exception as e:
            if not state.cancelled:
                state.results.errors.append(e)
        else:
            result = GFileSource(state.files[1], "", parent=state.source)
            result.cache = opening.FileCache([state.cache_path])
            state.results.sources.append(result)
        finally:
            state.results.complete()


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
    
    
    def open_selection(self, context, results, selection, source):
        uris = selection.get_uris()
        results.sources.extend(
            URISource(an_uri, parent=source) for an_uri in uris)
        # This code is just used to specify a fitting name for the source
        if uris:
            files_only = True
            for an_uri in uris:
                parse_result = urlparse(an_uri)
                if parse_result.scheme not in ("", "file"):
                    files_only = False
                    break
            
            count = len(uris)
            if files_only:
                source.setFileContentName(count)
            else:
                source.setURIContentName(count)
            
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
    
    
    def open_selection(self, context, results, selection, source):
        text = selection.get_text()
        got_results = False
        
        # Checks whether the text looks like a proper URI
        # .netloc would be "python.org" for http://python.org/, "cakes" for
        # file://cakes/cake.bmp but "" for file://cake.bmp, so it needs to
        # have either that or a "file" scheme.
        parse_result = urlparse(text)
        if (parse_result.scheme and parse_result.path
                and (parse_result.netloc or parse_result.scheme == "file")):
            results.sources.append(URISource(text, parent=source))
            got_results = True
            file_uri = parse_result.scheme == "file"
        else:
            # If not we assume it's an absolute filepath
            # Expanding "~"
            text = os_path.expanduser(text)
            if os_path.isabs(text):
                # Wildly assuming this is a valid filename
                # just because it starts with a slash
                text = "file://" + os_path.normcase(os_path.normcase(text))
                results.sources.append(URISource(text, parent=source))
                got_results = file_uri = True
        
        # Setting source name
        if got_results:
            if file_uri:
                source.setFileContentName()
            else:
                source.setURIContentName()
        
        results.complete()


class BuiltInOpeners(extending.ComponentPackage):
    """ A component package for installing the built in openers """
    @staticmethod
    def add_on(app):
        components = app.components
        uri_guesser = URIOpenerGuesser()
        uri_guesser.fallback = URICacheFallbackOpener()
        guessers = (
            GFileOpenerGuesser(),
            uri_guesser
        )
        for a_guesser in guessers:
            components.add(OpenerGuesser.CATEGORY, a_guesser)
            
        pixbuf_opener = PixbufOpener()
        directory_opener = DirectoryOpener()
        source_openers = (
            directory_opener, # Opens directories
            pixbuf_opener, # Opens images
            PixbufAnimationFileOpener(), # Opens animations
        )
        for an_opener in source_openers:
            components.add(Opener.CATEGORY, an_opener)
        
        selection_openers = (
            pixbuf_opener, # Opens images
            URIListSelectionOpener(), # Opens uri lists
            TextSelectionOpener() # Tries to parse text into uris
        )
        for an_opener in selection_openers:
            components.add(SelectionOpener.CATEGORY, an_opener)
        components.add(opening.PARENT_OPENER_CATEGORY, directory_opener)

extending.LoadedComponentPackages["openers"] = BuiltInOpeners
