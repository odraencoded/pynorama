""" opening.py defines the image opening classes that interface with openers.
    
    The entirety of the process is: openers open input and output more input
    and image sources. These image sources can be used to load image data and
    to create frames. Finally, the frames can be displayed in an image view.
    
    Openers must implement either the FileOpener or the SelectionOpener
    interfaces, described in extending.py, and image sources must implement
    the ImageSource interface described in loading.py """

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

import os
from collections import deque, defaultdict
from gi.repository import Gdk, Gio, GLib, GObject, Gtk
from . import utility, notifying
from .extending import FileOpener, SelectionOpener

logger = notifying.Logger("opening")

STANDARD_GFILE_INFO = (
    "standard::display-name", 
    "standard::type",
    "standard::content-type"
)
STANDARD_GFILE_INFO_STRING = ",".join(STANDARD_GFILE_INFO)
PARENT_OPENER_CATEGORY = "parent-opener"

class OpeningHandler(GObject.Object):
    """ Provides methods to open things """
    
    __gsignals__ = {
       "new-context": (GObject.SIGNAL_ACTION, None, [object]),
    }
    
    def __init__(self, app, **kwargs):
        self.app = app
        GObject.Object.__init__(self, **kwargs)
    
    
    def open_file(self, context, session, source):
        """ Tries to open a FileSource with an appropriate FileOpener """
        results = OpeningResults()
        guessed_opener = self.guess_file_opener(context, session, source.info)
        if guessed_opener:
            results.opener = guessed_opener
            try:
                guessed_opener.open_file(context, results, source)
            except Exception as e:
                results.errors.append(e)
                results.complete()
                
        else:
            results.complete()
        
        session.set_source_results(source, results)
    
    
    def open_selection(self, selection_data):
        """
        Tries to open a Gtk.Selection with an appropriate SelectionOpener
        
        """
        
        results = OpeningResults()
        selection_openers = self.app.components[SelectionOpener.CATEGORY]
        
        opener, target = self.guess_selection_opener(
            selection_openers,
            selection=selection_data
        )
        if opener:
            results.opener = opener
            try:
                opener.open_selection(results, selection_data)
            except Exception as e:
                results.errors.append(e)
                results.complete()
            
        else:
            results.complete()
            
        return results
    
    
    def open_clipboard(self, clipboard):
        """ Opens a Gtk.Clipboard """
        results = OpeningResults()
        clipboard.request_contents(
            Gdk.Atom.intern("TARGETS", False),
            self._clipboard_targets_request_cb,
            results
        )
        
        return results
    
    
    def guess_file_opener(self, context, session, gfile_info):
        """
        Returns a FileOpener within the context that appears to be compatible
        with the file type specified by the file info
        
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
    
    
    def guess_selection_opener(self, openers, selection=None, targets=None):
        """
        Tries to guess a SelectionOpener for a selection
        
        Returns a tuple indicating which SelectionOpener matches the
        Gtk.SelectionData and which Gdk.Atom was used to determine that.
        
        If no SelectionOpener can be found it returns a tuple containing two
        None elements.
        
        """
        # Get targets for opener guessing
        if not targets:
            success, targets = selection.get_targets()
            if not success:
                logger.debug("get_targets failed, trying get_target")
                targets = [selection.get_target()]
        
        logger.debug("Selection targets")
        logger.debug_list(t.name() for t in targets)
        
        for an_opener in openers:
            for a_target in targets:
                for another_target in an_opener.atom_targets:
                    if a_target == another_target:
                        return an_opener, a_target
        else:
            return None, None
    
    
    def handle(self, context, album=None):
        """
        Handles the next opening sessions of a context in an app standard
        way that will add its results to the indicated album
        
        """
        self.emit("new-context", context)
        
        context.connect("new-session", self._new_session_cb)
        context.connect("open-next::gfile", self._open_next_gfile_cb)
        context.connect("open-next::uri", self._open_next_uri_cb)
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
        sources = []
        images = []
        errors = []
        
        if session.search_siblings:
            logger.debug("Depth %s sibling search..." % session.depth)
            parent_files = list()
            parent_uris = set()
            # FIXME: This method doesn't work if there are images and files
            # results, which never actually happens in the app because
            # search_files is only true when there is only one file to open
            # XXX: Also it's a hardcoded mess
            for a_key, some_results in session.results.items():
                if not some_results:
                    continue
                
                errors.extend(some_results.errors)
                if some_results.sources:
                    sources.append((a_key, some_results.sources))
                    
                elif a_key.type == GFileFileSource.TYPE:
                    if some_results.images:
                        try:
                            gfile = a_key.gfile
                            a_parent_gfile = gfile.get_parent()
                            a_parent_uri = a_parent_gfile.get_uri()
                        except (TypeError, AttributeError):
                            # Nevermind, key was not a GFile
                            pass
                        except Exception:
                            logger.log_error("Error getting file parent")
                            logger.log_exception()
                        else:
                            if a_parent_uri not in parent_uris:
                                parent_files.append(a_parent_gfile)
                                parent_uris.add(a_parent_uri)
            
            logger.debug("Found %s parent(s)" % len(parent_files))
            if parent_files:
                logger.debug_list(f.get_uri() for f in parent_files)
                
                parent_openers = self.app.components[PARENT_OPENER_CATEGORY]
                
                siblings_session = context.get_new_session()
                siblings_session.add_openers(parent_openers)
                siblings_session.add_sources(
                    map(GFileFileSource, parent_files)
                )
            
        else: # not session.search_siblings
            # TODO: Remove files in sessions created to search sibling
            # files of another session that were opened in that first session
            for key, some_results in session.results.items():
                if some_results:
                    images.extend(some_results.images)
                    errors.extend(some_results.errors)
                    if some_results.sources:
                        sources.append((key, some_results.sources))
        
        
        logger.debug(
            "Depth %d session results: %d images, %d sources, %d errors" % (
                session.depth, len(images), len(sources), len(errors)
            )
        )
        for an_error in errors:
            logger.log_exception(an_error)
            
        self.app.memory.observe(*images)
        album.extend(images)
        
        # TODO: New URIs handling, error handling, no opener found handling
        if sources:
            # TODO: Implement warning dialogs
            continue_opening = True
            if len(sources) >= self.warning_file_count_threshold:
                logger.log("File count exceeded warning threshold")
            
            if session.depth >= self.warning_depth_threshold:
                if len(images) > self.warning_image_count_threshold:
                    logger.log(
                        "Depth and image count exceeded warning threshold"
                    )
                    continue_opening = False
                else:
                    logger.debug("Going deeper; Too few images in results")
                
            if continue_opening:
                self._continue_opening(context, session, sources)
    
    
    def _continue_opening(self, context, session, sources):
        # If the session was created to open the siblings of
        # another session, the its child session will have the
        # same openers as the session it was created for.
        # </overcomplicated>
        if session.for_siblings_of_session:
            openers = session.for_siblings_of_session.openers
        else:
            openers = self.app.components[FileOpener.CATEGORY]
        
        for parent_source, some_sources in sources:
            logger.debug(
                "Starting depth %d session with %d files" % (
                    session.depth + 1, len(some_sources),
                )
            )
            new_session = context.get_new_session(session, parent_source)
            new_session.add_openers(openers)
            new_session.add_sources(some_sources)
    
    
    def _new_session_cb(self, context, session, *etc):
        """ Connect handlers for a new opening session """
        session.connect("added::gfile", self._added_gfile_cb, context)
        session.connect("added::uri", self._added_uri_cb, context)
    
    
    def _added_gfile_cb(self, session, sources, context):
        """ Queries file info of files added to a session and starts
            opening them if any of the files already has its information """
        
        sources_to_enqueue = []
        for a_source in sources:
            if a_source.fill_missing_info(STANDARD_GFILE_INFO):
                sources_to_enqueue.append(a_source)
            else:
                # XXX: too lazy to look up better way to disconnect on callback
                signal_id_list = []
                signal_id_list.append(a_source.connect(
                    "loaded-file-info",
                    self._loaded_file_info_cb,
                    session, context, signal_id_list
                ))
                
        context.enqueue_sources(session, sources_to_enqueue)
    
    
    def _added_uri_cb(self, session, sources, context):
        """ Removes local URIs(file://)
            and adds them back as GFiles instead. """
        
        local_uris = []
        for i in range(len(sources)):
            j = i - len(local_uris)
            an_uri = sources[j].uri
            if an_uri.lower().startswith("file:"):
                # Probably, all local URIs start with file: and then
                # some slashes... probably...
                local_uris.append(an_uri)
                del sources[j]
        
        # Generators, yo!
        files = map(GFileFileSource, map(Gio.File.new_for_uri, local_uris))
        session.add_sources(files)
        
        # Enqueue remaining non-local URIs to be opened
        context.enqueue_sources(session, sources)
    
    
    def _create_filter_info(self, context, gfile_info):
        """ Returns a Gtk.FileFilterInfo for filtering FileOpeners """
        flags = Gtk.FileFilterFlags
        result = Gtk.FileFilterInfo()
        result.contains = flags.DISPLAY_NAME | flags.MIME_TYPE
        result.display_name = gfile_info.get_display_name()
        result.mime_type = gfile_info.get_content_type()
        
        return result
    
    
    def _loaded_file_info_cb(self, source, session, context, signal_id_list):
        """ Enqueues a file that has got its file info to be opened """
        context.enqueue_sources(session, (source,))
        source.disconnect(signal_id_list[0])
    
    
    def _open_next_gfile_cb(self, context, session, source):
        """ Opens a Gio.File from a context's opening queue """
        
        self.open_file(context, session, source)
    
    
    def _open_next_uri_cb(self, context, session, source):
        """ Opens an URI string from a context's opening queue """
        
        # TODO: Implement some sort of URI opener here
        results = OpeningResults()
        opener = None
        if opener:
            pass
        else:
            # TODO: Fallback to cacheing the URI into a file
            converted_file = Gio.File.new_for_uri(source.uri)
            results.sources.append(GFileFileSource(converted_file))
            results.complete()
            
            session.set_source_results(source, results)
    
    
    def _clipboard_targets_request_cb(self, clipboard, selection, results):
        """ Callback for requesting the targets of a Gtk.Clipboard """
        selection_openers = self.app.components[SelectionOpener.CATEGORY]
        opener, target = self.guess_selection_opener(
            selection_openers,
            selection=selection
        )
        if opener:
            results.opener = opener
            clipboard.request_contents(
                target,
                self._clipboard_content_request_cb,
                results
            )
            
        else:
            # Can't open this
            results.complete()
    
    
    def _clipboard_content_request_cb(self, clipboard, selection, results):
        """ Callback for requesting the content of a Gtk.Clipboard """
        try:
            results.opener.open_selection(results, selection)
        except Exception as e:
            results.errors.append(e)
            results.complete()


class OpeningContext(GObject.Object):
    """ Represents a series """
    
    __gsignals__ = {
        "new-session" : (GObject.SIGNAL_ACTION, None, [object]),
        "finished-session" : (GObject.SIGNAL_ACTION, None, [object]),
        # The detail part is the opened source .type attribute
        "open-next": (GObject.SIGNAL_DETAILED, None, [object, object]),
        "finished": (GObject.SIGNAL_ACTION, None, []),
    }
    
    
    def __init__(self, app):
        GObject.Object.__init__(self)
        
        self.sessions = []
        self.open_sessions = set()
        # A set of sessions that aren't finished yet
        self.finished = False
        # Whether the context is finished
        self._keep_open_counter = 0
        # Freezes the context so that it doesn't emit a "finished" signal
        
        self.opening_queue = deque()
        
        self.open_next = utility.IdlyMethod(self.open_next)
        
        self.connect("notify::keep-open", self._notify_keep_open_cb)
        
        self.cache_directory = app.cache_directory.name
    
    # Whether to keep the context "unfinished" even if the criteria to
    # finish it is true
    @GObject.Property
    def keep_open(self):
        """ Whether the context should be kept opened """
        return self._keep_open_counter > 0
    
    
    def hold_open(self):
        """
        Forces the context not to emit the "finished" signal when the criteria
        for emitting that signal is met.
        
        let_close() should be called once for every time hold_open() is called.
        
        """
        self._keep_open_counter += 1
        if self._keep_open_counter == 1:
            self.notify("keep-open")
    
    
    def let_close(self):
        """
        Lets the context emit the "finished" signal when the criteria is met.
        
        """
        self._keep_open_counter -= 1
        if self._keep_open_counter == 0:
            self.notify("keep-open")
    
    
    def get_new_session(self, parent=None, parent_source=None):
        """ Gets the latest non-finished opening session """
        assert not self.finished
        
        new_session = OpeningSession(parent, parent_source)
        self.sessions.append(new_session)
        self.open_sessions.add(new_session)
        new_session.connect("finished", self._session_finished_cb)
        self.emit("new-session", new_session)
        
        return new_session
    
    
    def enqueue_sources(self, session, sources):
        """ Queues files to be opened """
        assert not self.finished
        
        self.opening_queue.extend((session, a_source) for a_source in sources)
        self.open_next.queue()
    
    
    def enqueue_selections(self, session, selections):
        """ Queues selections to be opened """
        assert not self.finished
        
        self.opening_queue.extend(
            ("selection", session, a_selection) for a_selection in selections
        )
        self.open_next.queue()
    
    
    def finish(self):
        assert not self.finished
        
        if not self.finished:
            self.finished = True
            self.emit("finished")
    
    
    def open_next(self):
        """
        Emits an "open-next" signal for a file that has its missing info
        
        """
        
        try:
            session, next_item = self.opening_queue.popleft()
        except IndexError: # There are no files in the queue!
            return False
        
        self.emit("open-next::" + next_item.type, session, next_item)
        self.open_next.queue()
        
        return True
    
    
    def _session_finished_cb(self, session):
        """
        Emits the "finished-session" signal and asserts whether the context
        itself is finished.
        
        """
        self.open_sessions.remove(session)
        self.emit("finished-session", session)
        if not self.open_sessions:
            if self.keep_open:
                logger.debug("Opening context kept open")
            else:
                self.finish()
    
    
    def _notify_keep_open_cb(self, *etc):
        """
        Emits the "finished" signal if the context was finished while it was
        kept open.
        
        """
        if not self.keep_open and not self.open_sessions:
            logger.debug("Opening context unfrozen and closing")
            self.finish()


class OpeningSession(GObject.Object):
    """
    Represents a single cycle in the opening system.
    
    A session contains opening input such as files and URIs which are then
    converted by an OpeningHandler into images, more files and uris.
    
    The output files and uris are then used to create new opening sessions.
    How and when exactly that happens should be OpeningHandler dependant.
    
    """
    
    __gsignals__ = {
        "added" : (GObject.SIGNAL_DETAILED, None, [object]),
        "opened" : (GObject.SIGNAL_DETAILED, None, [object, object]),
        "finished" : (GObject.SIGNAL_ACTION, None, []),
    }
    def __init__(self, parent, parent_source):
        GObject.Object.__init__(self)
        
        self.parent_source = parent_source
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
        self._results_completion_signals = {}
        self.incomplete_results = set()
        self.sources_missing_results = set()
        self.sources, self.openers = [], []
    
    
    def finish(self):
        assert not self.finished
        
        self.finished = True
        self.emit("finished")
    
    
    def add(self, sources=None, openers=None):
        if openers:
            self.add_openers(openers)
        if files:
            self.add_sources(files)
    
    
    def add_sources(self, sources):
        """ Adds FileSources objects to be opened in this session """
        assert not self.finished
        
        new_sources = list(sources)
        if new_sources:
            source_types = defaultdict(list)
            for a_source in new_sources:
                source_types[a_source.type].append(a_source)
            
            for a_source_type, some_sources in source_types.items():
                self.emit("added::" + a_source_type, some_sources)
                # some_sources are added after the signal is emitted
                # so that handlers can modify its contents
                self.sources.extend(some_sources)
                self.sources_missing_results.update(some_sources)
    
    
    def add_clipboards(self, clipboards):
        """ Adds Gtk.Clipboard objects to be opened in this session """
        assert not self.finished
        
        clipboard_list = list(clipboards)
        if clipboard_list:
            self.emit("added::clipboard", clipboard_list)
            self.clipboards.extend(clipboard_list)
    
    
    def add_openers(self, openers):
        """ Add openers to open stuff in this session """
        self.openers.extend(openers)
    
    
    def set_source_results(self, source, results):
        """ Set the results for trying to open a file """
        self.results[source] = results
        self.sources_missing_results.discard(source)
        if results.completed:
            self.emit("opened::" + source.type, results, source)
            self._check_finished()
        else:
            self.incomplete_results.add(results)
            self._results_completion_signals[results] = results.connect(
                "completed", self._results_completed_cb, source
            )
    
    
    def _results_completed_cb(self, results, source):
        """ Handle for opening results that complete asynchronously """
        self.incomplete_results.remove(results)
        # breaking reference cycle created by signal handlers
        results.disconnect(self._results_completion_signals.pop(results))
        self.emit("opened::" + source.type, results, source)
        self._check_finished()
    
    
    def _check_finished(self):
        if not (self.incomplete_results or self.sources_missing_results):
            self.finish()


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
        
        self.images, self.sources = [], []
        # Lists of images and data sources that were "opened" by the opener
        
        self.errors = []
        # A list of exceptions that have occurred while opening something
    
    
    def __iadd__(self, other):
        self.images += other.images
        self.sources += other.sources
        self.errors += other.errors
        
        return self
    
    
    def __str__(self):
        return "<OpeningResults: %d image(s), %d sources(s), %d error(s)>" % (
            len(self.images), len(self.sources), len(self.errors)
        )
    
    
    @property
    def empty(self):
        """ Returns whether there is any output contained in these results """
        return not(self.sources or self.images or self.errors)
    
    
    def complete(self):
        """
        Emits a "completed" signal on this object and sets its .completed
        attribute to true.
        
        This signals subscriber objects that the opener has finished
        opening the source of these results and they should be processed
        
        """
        assert not self.completed
        
        if not self.completed:
            self.completed = True
            self.emit("completed")


class FileSource:
    def __init__(self, type, name, parent=None, pathname=None):
        self.type = type
        self.name = name
        self.pathname = pathname
        self.parent = parent
    
    
    def ressembles(self, other):
        return self._ressembles(other) or other._ressembles(self)
    
    
    def get_ancestors(self):
        """ Yields this source ancestors from nearest to farthest """
        parent = self.parent
        while parent is not None:
            yield parent
            parent = parent.parent
  
  
    def get_fullname(self, sep=os.sep):
        if self.pathname:
            return self.pathname
        else:
            ancestry = [self.name]
            for ancestor in self.get_ancestors():
                if ancestor.pathname:
                    ancestry.append(ancestor.pathname)
                    break
                else:
                    ancestry.append(ancestor.name)
            
        return sep.join(name for name in reversed(ancestry) if name)
    
    
    def ressembles_ancestor(self, possible_ancestor):
        return any(
            an_ancestor.ressembles(possible_ancestor)
            for an_ancestor in self.get_ancestors()
        )
    
    
    def _ressembles(self):
        return False


class GFileFileSource(GObject.Object, FileSource):
    TYPE = "gfile"
    
    __gsignals__ = {
        "loaded-file-info": (GObject.SIGNAL_RUN_LAST, None, []),
    }
    
    def __init__(self, gfile, name=None, parent=None):
        GObject.Object.__init__(self)
        
        self.gfile = gfile
        self.info = None
        self.being_queried = False
        self.missing_info = None
        
        FileSource.__init__(self, GFileFileSource.TYPE, name, parent)
        
        self._fill_missing_name = name is None
        if name is None:
            self.pathname = gfile.get_parse_name()
            self.missing_info = {"standard::display-name",}
    
    
    def fill_missing_info(self, info_keys):
        if self.info is None:
            missing_info = set(info_keys)
        else:
            missing_info = {
                a_key for a_key in info_keys
                      if not self.info.has_attribute(a_key)
            }
        
        if self.missing_info:
            missing_info.update(self.missing_info)
            self.missing_info = None
        
        if missing_info:
            # There are attributes missing, so we are going to query them
            if not self.being_queried:
                self.gfile.query_info_async(
                    ",".join(missing_info), # comma separated attributes
                    Gio.FileQueryInfoFlags.NONE,
                    GLib.PRIORITY_LOW,
                    None,
                    self._queried_missing_info_cb,
                    None
                )
                self.being_queried = False
            else:
                # Store missing info so it can be queried later
                self.missing_info = missing_info
                
            return None
        else:
            return self.info
    
    
    def _queried_missing_info_cb(self, gfile, result, *etc):
        self.being_queried = False
        
        try:
            new_info = gfile.query_info_finish(result)
        except GLib.Error:
            raise Exception
        
        # Put new info into cache somehow
        if self.info is None:
            self.info = stored_info = new_info
        else:
            new_info.copy_into(self.info)
        
        if self._fill_missing_name:
            self.name = self.info.get_display_name()
            self._fill_missing_name = False
        
        # If this returns not None we have all the info, otherwise
        # a new query will be created for that missing info
        if self.missing_info:
            self.fill_missing_info(self.missing_info)
        else:
            self.emit("loaded-file-info")
    
    
    def _ressembles(self, other):
        if hasattr(other, "gfile"):
            if self.gfile.equal(other.gfile):
                return True
        
        if hasattr(other, "uri"):
            if self.gfile.get_uri() == other.uri:
                return True
        
        return False


class URIFileSource(FileSource):
    TYPE ="uri"
    
    def __init__(self, uri, name=None, parent=None):
        self.uri = uri
        if name is None:
            name = uri
        
        FileSource.__init__(self, URIFileSource.TYPE, name, parent)
    
    
    def _ressembles(self, other):
        if hasattr(other, "gfile"):
            if self.uri == other.gfile.get_uri():
                return True
        
        if hasattr(other, "uri"):
            if self.uri == other.uri:
                return True
        
        return False


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
