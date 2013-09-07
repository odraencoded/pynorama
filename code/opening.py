""" The opening module is the first part of the image opening process.
    Which is awfully more complex than it should be.
    
    This module is responsible for figuring out how a certain file, uri, or
    other resource should be processed. It does not actually load images,
    it only instantiates ImageSources that can potentially load those images
    properly.

"""

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
    along with Pynorama. If not, see <http://www.gnu.org/licenses/>.

"""

from gi.repository import GdkPixbuf, Gio, GObject, GLib, Gtk
from gettext import gettext as _
import notification, extending, utility, loading
from collections import deque

logger = notification.Logger("opening")

STANDARD_GFILE_INFO = (
    "standard::display-name", 
    "standard::type",
    "standard::content-type"
)
STANDARD_GFILE_INFO_STRING = ",".join(STANDARD_GFILE_INFO)

class OpeningHandler(GObject.Object):
    """ Provides methods to open things """
    
    __gsignals__ = {
       "new-context": (GObject.SIGNAL_ACTION, None, [object]),
    }
    
    def __init__(self, app, **kwargs):
        self.app = app
        GObject.Object.__init__(self, **kwargs)
    
    
    def open_file(self, context, session, gfile, gfile_info):
        """ Tries to open a file with an appropriate FileOpener """
        results = OpeningResults()
        guessed_opener = self.guess_opener(context, session, gfile_info)
        
        if guessed_opener:
            results.opener = guessed_opener
            try:
                guessed_opener.open_file(context, results, gfile)
            except Exception as e:
                results.errors.append(e)
                results.complete()
                
        else:
            results.complete()
        
        context.set_file_results(session, gfile, results)
    
    
    def guess_opener(self, context, session, gfile_info):
        """
        Returns a file opener within the context that appears to be compatible
        with the file type specified in the file info
        
        Returns None if it can't be guessed
        
        """
        
        # The context openers are iterated in reverse because the openers
        # added last have higher priority and may "override" how certain
        # types of files are opened
        
        gfile_filter_info = self._create_filter_info(context, gfile_info)
        for an_opener in reversed(session.openers):
            a_file_filter = an_opener.get_file_filter()
            if a_file_filter.filter(gfile_filter_info):
                return an_opener
                
        else:
            return None
    
    
    def handle(self, context, album=None):
        """
        Handles the next opening sessions of a context in an app standard
        way that will add its results to the indicated album
        
        """
        self.emit("new-context", context)
        
        context.connect("new-session", self._new_session_cb)
        context.connect("loaded-file-info", self._loaded_file_info_cb)
        context.connect("open-next::file", self._open_next_file_cb)
        if album is not None:
            context.connect(
                "finished-session",
                self._standard_session_finished_cb,
                album
            )
    
    
    def start_opening(self, context, files=None, uris=None, openers=None):
        """
        Starts to open input from a session
        
        An OpeningProgress is returned for controlling the process
        
        """
        
        self.handle(context)
        
        newest_session = context.get_new_session()
        
        if openers is not None:
            newest_session.add_openers(openers)
        if files is not None:
            newest_session.add_files(files)
        if uris is not None:
            newest_session.add_uris(uris)
    
    #-- Properties down this line --#
    warning_depth_threshold = GObject.Property(type=int, default=1)
    warning_file_count_threshold = GObject.Property(type=int, default=500)
    warning_image_count_threshold = GObject.Property(type=int, default=0)
    
    def _standard_session_finished_cb(self, context, session, album):
        """
        Standard handling for finished opening sessions
        
        It adds images to an album and 
        
        """
        files = []
        images = []
        errors = []
        
        if session.search_siblings:
            logger.debug("Depth %s sibling search..." % session.depth)
            parent_files = list()
            parent_uris = set()
            # FIXME: This method doesn't work if there are images and files
            # results, which never actually happens in the app because
            # search_files is only true when there is only one file to open
            for a_key, some_results in session.results.items():
                if some_results:
                    errors.extend(some_results.errors)
                    if some_results.files:
                        files.append((a_key, some_results.files))
                        
                    else:
                        try:
                            a_parent_key = a_key.get_parent()
                            a_parent_uri = a_parent_key.get_uri()
                        except (TypeError, AttributeError):
                            # Nevermind, key was not a GFile
                            pass
                        except Exception:
                            logger.log_error("Error getting file parent")
                            logger.log_exception()
                        else:
                            if a_parent_uri not in parent_uris:
                                parent_files.append(a_parent_key)
                                parent_uris.add(a_parent_uri)
            
            logger.debug("Found %s parent(s)" % len(parent_files))
            if parent_files:
                logger.debug_list(f.get_uri() for f in parent_files)
                
                directory_opener = self.app.components[
                    "file-opener",
                    DirectoryOpener.CODENAME
                ]
                
                siblings_session = context.get_new_session()
                siblings_session.add_openers([directory_opener])
                siblings_session.add_files(parent_files)
            
        else: # not session.search_siblings
            # TODO: Remove files in sessions created to search sibling
            # files of another session that were opened in that first session
            for key, some_results in session.results.items():
                if some_results:
                    images.extend(some_results.images)
                    errors.extend(some_results.errors)
                    if some_results.files:
                        files.append((key, some_results.files))
        
        
        logger.debug(
            "Depth %d session results: %d images, %d files, %d errors" % (
                session.depth, len(images), len(files), len(errors)
            )
        )
        
        self.app.memory.observe(*images)
        album.extend(images)
        
        # TODO: New URIs handling, error handling, no opener found handling
        if files:
            # TODO: Implement warning dialogs
            continue_opening = True
            if len(files) >= self.warning_file_count_threshold:
                logger.log("File count exceeded warning threshold")
                continue_opening = False
                
            if len(images) > self.warning_image_count_threshold:
                if session.depth >= self.warning_depth_threshold:
                    logger.log(
                        "Depth and image count exceeded warning threshold"
                    )
                    continue_opening = False
            else:
                logger.debug("Going deeper; Too few images in results")
                
            if continue_opening:
                # If the session was created to open the siblings of
                # another session, the its child session will have the
                # same openers as the session it was created for.
                # </overcomplicated>
                if session.for_siblings_of_session:
                    openers = session.for_siblings_of_session.openers
                else:
                    openers = self.app.components["file-opener"]
                
                for key, some_files in files:
                    logger.debug(
                        "Starting depth %d session with %d files" % (
                            session.depth + 1, len(some_files),
                        )
                    )
                    new_session = context.get_new_session(session, key)
                    
                    new_session.add(files=some_files, openers=openers)
    
    
    def _new_session_cb(self, context, session, *etc):
        session.connect("added::file", self._added_file_cb, context)
        session.connect("added::uri", self._added_uri_cb, context)
    
    
    def _added_file_cb(self, session, files, context):
        """
        Queries file info of files added to a session and starts
        opening them if any of the files already has its information
        
        """
        
        files_to_enqueue = []
        for a_file in files:
            if context.query_missing_info(a_file):
                files_to_enqueue.append(a_file)
                
        context.enqueue_files(session, files_to_enqueue)
    
    
    def _added_uri_cb(self, session, uris, context):
        """
        Removes URIs whose protocol is file:slashes and adds them as
        files instead
        
        """
        
        new_file_for_uri = Gio.File.new_for_uri
        converted_files = []
        for i in range(len(uris)):
            j = i -len(converted_files)
            an_uri = uris[j]
            if an_uri.lower().startswith("file:"):
                # Probably, all local URIs start with file: and then
                # some slashes... probably...
                a_converted_file = new_file_for_uri(an_uri)
                converted_files.append(a_converted_file)
                del uris[j]
        
        session.add_files(converted_files)
        context.enqueue_uris(session, uris)

        # If there are any non-local URIs, then we will open them
    
    def _create_filter_info(self, context, gfile_info):
        """ Returns a Gtk.FileFilterInfo for filtering FileOpeners """
        flags = Gtk.FileFilterFlags
        result = Gtk.FileFilterInfo()
        result.contains = flags.DISPLAY_NAME | flags.MIME_TYPE
        result.display_name = gfile_info.get_display_name()
        result.mime_type = gfile_info.get_content_type()
        
        return result
    
    
    def _loaded_file_info_cb(self, context, gfile, *etc):
        """ Enqueues a file that has got its file info to be opened """
        gfile_list = [gfile]
        for a_session in context.open_sessions:
            if gfile in a_session.files_set:
                context.enqueue_files(a_session, gfile_list)
    
    
    def _open_next_file_cb(self, context, session, gfile):
        """ Opens the next """
        
        gfile_info = context.file_info_cache[gfile]
        self.open_file(context, session, gfile, gfile_info)


class OpeningContext(GObject.Object):
    """ Represents a series """
    
    __gsignals__ = {
        "new-session" : (GObject.SIGNAL_ACTION, None, [object]),
        "finished-session" : (GObject.SIGNAL_ACTION, None, [object]),
        "opened" : (GObject.SIGNAL_DETAILED, None, [object, object]),
        # Valid details for the above signals are ::file and ::uri
        "loaded_file_info": (GObject.SIGNAL_RUN_LAST, None, [object, object]),
        "open-next": (GObject.SIGNAL_DETAILED, None, [object, object]),
        "finished": (GObject.SIGNAL_ACTION, None, []),
    }
    
    
    def __init__(self):
        GObject.Object.__init__(self)
        
        self.sessions = []
        self.open_sessions = set()
        self.finished = False
        
        self.file_info_cache = {}
        
        self.opening_queue = deque()
        self.incomplete_results = set()
        self.files_being_queried = set()
        self.open_next = utility.IdlyMethod(self.open_next)
    
    
    def get_new_session(self, parent=None, source=None):
        """ Gets the latest non-finished opening session """
        assert not self.finished
        
        new_session = OpeningSession(parent, source)
        self.sessions.append(new_session)
        self.open_sessions.add(new_session)
        new_session.connect("finished", self._session_finished_cb)
        self.emit("new-session", new_session)
        
        return new_session
    
    
    def enqueue_files(self, session, files):
        """ Queues files to be opened """
        if files:
            self.opening_queue.extend(
                ("file", session, a_file) for a_file in files
            )
            self.open_next.queue()
    
    
    def enqueue_uris(self, session, uris):
        """ Queues uris to be opened """ 
        if uris:
            self.opening_queue.extend(
                ("uri", session, an_uri) for an_uri in uris
            )
            self.open_next.queue()
    
    
    def finish(self):
        if not self.finished:
            self.finished = True
            self.emit("finished")
    
    
    def set_file_results(self, session, gfile, results):
        """ Set the results for trying to open a file """
        session.results[gfile] = results
        if results.completed:
            self.emit("opened::flie", results, gfile)
            self._check_finished(session)
        else:
            self.incomplete_results.add(results)
            results.connect(
                "completed",
                self._results_completed_cb,
                ("file", gfile, session)
            )
    
    
    def query_file_info(self, gfile, *attributes):
        try:
            stored_info = self.file_info_cache[gfile]
        except KeyError:
            self.file_info_cache[gfile] = stored_info = Gio.GFileInfo()
            missing_info = frozenset(attributes)
        else:
            missing_info = {
                k for k in attributes if not stored_info.has_attribute(k)
            }
        
        if missing_info:
            new_info = gfile.query_info(
                ",".join(missing_info), # comma separated attributes
                Gio.FileQueryInfoFlags.NONE,
                None,
            )
            new_info.copy_into(stored_info)
            
        return stored_info
    
    
    def query_missing_info(self, gfile):
        """ 
        Queries for a gfile's file info for attributes missing from the
        file info cache that are in the STANDARD_GFILE_INFO list
        
        This may trigger an async IO operation.
        
        Returns None if there are file info attributes missing, otherwise
        returns the GFileInfo object from the cache
        
        """
        
        try:
            stored_info = self.file_info_cache[gfile]
        except KeyError:
            missing_info = frozenset(STANDARD_GFILE_INFO)
        else:
            missing_info = {
                k for k in STANDARD_GFILE_INFO
                        if not stored_info.has_attribute(k)
            }
        
        if missing_info:
            # There are attributes missing, so we are going to query them
            if gfile not in self.files_being_queried:
                gfile.query_info_async(
                    ",".join(missing_info), # comma separated attributes
                    Gio.FileQueryInfoFlags.NONE,
                    GLib.PRIORITY_LOW,
                    None,
                    self._queried_missing_info_cb,
                    None
                )
                self.files_being_queried.add(gfile)
                
            return None
        else:
            return stored_info
    
    
    def open_next(self):
        """
        Emits an "open-next" signal for a file that has its missing info
        
        """
        
        try:
            kind, session, next_item = self.opening_queue.popleft()
        except IndexError: # There are no files in the queue!
            return False
        
        self.emit("open-next::" + kind, session, next_item)
        
        self.open_next.queue()
        
        return True
    
    
    def _check_finished(self, session):
        result_keys = session.results.keys()
        if not self.incomplete_results and result_keys >= session.files_set:
            session.finish()
    
    
    def _results_completed_cb(self, results, data):
        """ Handle for opening results that complete asynchronously """
        self.incomplete_results.remove(results)
        source_type, source, session = data
        self.emit("opened::" + source_type, results, source)
        self._check_finished(session)
    
    
    def _session_finished_cb(self, session):
        self.open_sessions.remove(session)
        self.emit("finished-session", session)
        if not self.open_sessions:
            self.finish()
    
    
    def _queried_missing_info_cb(self, gfile, result, *etc):
        """
        Handler for the async GFileInfo query triggered by .query_missing_info
        
        """
        try:
            new_info = gfile.query_info_finish(result)
        except GLib.Error:
            raise Exception
        
        # Put new info into cache somehow
        try:
            stored_info = self.file_info_cache[gfile]
        except KeyError:
            self.file_info_cache[gfile] = stored_info = new_info
        else:
            new_info.copy_into(stored_info)
        self.files_being_queried.remove(gfile)
        
        # If this returns not None we have all the info, otherwise
        # a new query will be created for that missing info
        if self.query_missing_info(gfile):
            self.emit("loaded-file-info", gfile, stored_info)


class OpeningSession(GObject.Object):
    __gsignals__ = {
        "added" : (GObject.SIGNAL_DETAILED, None, [object]),
        "finished" : (GObject.SIGNAL_ACTION, None, []),
    }
    def __init__(self, parent, source):
        GObject.Object.__init__(self)
        
        self.source = source
        self.parent_session = parent
        self.children_sessions = []
        if self.parent_session is None:
            self.depth = 0
        else:
            self.parent_session.children_sessions.append(self)
            ancestry = {parent}
            while parent.parent_session is not None:
                parent = parent.parent_session
                if parent in ancestry:
                    raise ValueError
                else:
                    ancestry.add(parent)
                    
            self.depth = len(ancestry)
            
        self.finished = False
        
        self.search_siblings = False
        self.search_siblings_session = None
        self.for_siblings_of_session = None
        
        self.results = {}
        
        self.files, self.uris = [], []
        self.files_set, self.uris_set = set(), set()
        self.openers = []
        
    
    def finish(self):
        assert not self.finished
        
        self.finished = True
        self.emit("finished")
    
    
    def add(self, files=None, uris=None, openers=None):
        if openers:
            self.add_openers(openers)
        if uris:
            self.add_uris(uris)
            
        if files:
            self.add_files(files)
    
    
    def add_files(self, files):
        """ Adds files to be opened in this session """
        if self.finished:
            raise Exception
        
        file_list = list(files)
        if file_list:
            self.emit("added::file", file_list)
            self.files.extend(file_list)
            self.files_set.update(file_list)
    
    
    def add_uris(self, uris):
        """ Adds uris to be opened in this session """
        if self.finished:
            raise Exception
        
        uri_list = list(uris)
        if uri_list:
            self.emit("added::uri", uri_list)
            self.uris.extend(uri_list)
            self.uris_set.update(uri_list)
    
    
    def add_openers(self, openers):
        """ Add openers to open stuff in this session """
        self.openers.extend(openers)


class OpeningResults(GObject.Object):
    """ A structure for the results of trying to open something """
    __gsignals__ = {
       "completed": (GObject.SIGNAL_ACTION, None, [])
    }
    
    
    def __init__(self):
        GObject.Object.__init__(self)
        
        self.completed = False
        # Whether more items will be added to these results
        
        self.opener = None
        # The opener that triggered these results
        
        self.images, self.files, self.uris = [], [], []
        # Lists of images, files and uris that were "opened" by the opener
        
        self.file_info_cache = {}
        # A dictionary of GFile and GFileInfo pairs, for openers that
        # query file metadata, settings this can speed up the whole process
        
        self.errors = []
        # A list of exceptions that have occurred while opening something
    
    
    def __iadd__(self, other):
        self.images += other.images
        self.files += other.files
        self.uris += other.uris
        self.errors += other.errors
        for key, other_cache in other.file_info_cache.items():
            try:
                my_cache = self.file_info_cache[key]
            except KeyError:
                self.file_info_cache[key] = other_cache
            else:
                other_cache.copy_into(my_cache)
        
        return self
    
    def __str__(self):
        return "<OpeningResults: %d image(s), %d file(s), %d error(s)>" % (
            len(self.images), len(self.files), len(self.errors)
        )
    
    @property
    def has_output(self):
        """ Whether files, images or uris have been added to the results """
        return bool(self.images or self.files or self.uris)
    
    
    @property
    def has_input(self):
        """ Whether the results contain data to start a new opening context """
        return self.files or self.uris
    
    
    @property
    def could_open(self):
        """ Whether the results' opener successfully opened the input """
        return bool(not self.has_output and self.errors)
    
    
    def complete(self):
        """
        Emits a "completed" signal on this object and sets its .completed
        attribute to true.
        
        This signals subscriber objects that the opener has finished
        opening the source of these results and they should be processed
        
        """
        
        if not self.completed:
            self.completed = True
            self.emit("completed")
            

class FileOpener(GObject.Object, extending.Component):
    """ An interface to open files for the image viewer.
    
    File openers yield image sources or other files which are then
    opened by other file openers.
    
    """
    
    def __init__(self, codename, extensions=None, mime_types=None):
        """ Initializes a file opener for certain extensions and mime_types """
        
        GObject.Object.__init__(self)
        extending.Component.__init__(self, codename)
        
        # These two variables are used to guess which 
        # file opener should open which file
        self.extensions = extensions if extensions is not None else set()
        """ A set of common extensions for this file opener supported files """
        
        self.mime_types = mime_types if mime_types is not None else set()
        """ A set of mime_types for this file opener supported files """
        
        self.show_on_dialog = True
        """ Whether to show this file opener in the "Open image" dialog """
        
        self._file_filter = None
    
    @GObject.Property
    def label(self):
        """ A label to be displayed in the GUI """
        raise NotImplementedError
    
    
    def open_file(self, context, results, gfile):
        """ Opens a GFile from context and adds its contents to the results """
        raise NotImplementedError
    
    
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


class FileOpenerGroup:
    """ Represents a set of file openers """
    
    def __init__(self, label, file_openers=None):
        self.label = label
        self.file_openers = file_openers if file_openers is not None else set()
    
    
    def create_file_filter(self):
        """ Returns a new file filter for this file opener group """
        result = Gtk.FileFilter()
        result.set_name(self.label)
        
        patterns, mime_types = set(), set()
        for a_file_opener in self.file_openers:
            for an_extension in a_file_opener.extensions:
                patterns.add("*." + an_extension)
            for a_mime_type in a_file_opener.mime_types:
                mime_types.add(a_mime_type)
        
        for a_pattern in patterns:
            result.add_pattern(a_pattern)
        for a_mime_type in mime_types:
            result.add_mime_type(a_mime_type)
        
        return result


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
    
    
    def open_file(self, context, results, gfile):
        """ Opens a directory file and yields its contents """
        
        gfile.enumerate_children_async(
            STANDARD_GFILE_INFO_STRING,
            0,
            GLib.PRIORITY_DEFAULT,
            None,
            self._enumerate_children_async_cb,
            (context, results)
        )
    
    def _enumerate_children_async_cb(self, gfile, async_result, data):
        context, results = data
        try:
            gfile_enumerator = gfile.enumerate_children_finish(async_result)
        except Exception as e:
            results.errors.append(e)
        else:
            get_child_for_display_name = gfile.get_child_for_display_name
            append_file = results.files.append
            file_info_cache = results.file_info_cache
            for a_file_info in gfile_enumerator:
                try:
                    child_name = a_file_info.get_display_name()
                    a_child_file = get_child_for_display_name(child_name)
                    append_file(a_child_file)
                    file_info_cache[a_child_file] = a_file_info
                    
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


class PixbufFileOpener(FileOpener):
    """ Opens image files supported by the GdkPixbuf library """
    
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
            PixbufFileOpener.CODENAME, 
            extensions, 
            mime_types
        )
    
    
    @GObject.Property
    def label(self):
        return _("GdkPixbuf Images")
    
    
    def open_file(self, context, results, gfile):
        try:
            new_image = loading.PixbufFileImageSource(
                gfile,
                opening_context=context
            )
        except Exception as e:
            results.errors.append(e)
        else:
            results.images.append(new_image)
            
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
            new_image = loading.PixbufAnimationFileImageSource(
                gfile,
                opening_context=context
            )
        except Exception as e:
            results.errors.append(e)
        else:
            results.images.append(new_image)
            
        results.complete()


class BuiltInOpeners(extending.ComponentPackage):
    """ A component package for installing the built in openers """
    @staticmethod
    def add_on(app):
        components = app.components
        components.add_category("file-opener", "File Opener")
        
        openers = [
            DirectoryOpener(),
            PixbufFileOpener(),
            PixbufAnimationFileOpener(),
        ]
        for an_opener in openers:
            components.add("file-opener", an_opener)

extending.LoadedComponentPackages.add(BuiltInOpeners)
