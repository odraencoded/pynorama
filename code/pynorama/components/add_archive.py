""" archive.py adds experimental support to zipfile supported archives.
    
    To do before merge:
        Asynchronous support
        Temp directory cleaning up
        Somehow fix the filenames when they appear in the window title 
    
    Should be used with caution, can blow up anytime. """

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

import zipfile
import tempfile
from gettext import gettext as _
import os
from os.path import join as join_path

from gi.repository import Gio, GObject

from pynorama.extending import FileOpener
from pynorama import extending, opening

class ZipOpener(FileOpener):
    CODENAME = "zip"
    
    def __init__(self):
        FileOpener.__init__(self,
            ZipOpener.CODENAME,
            mime_types={"application/zip"}
        )
    
    
    @GObject.Property
    def label(self):
        return _("Zipfile Archives")
    
    
    def open_file(self, context, results, source):
        """ Opens a directory file and yields its contents """
        
        gfile = source.gfile
        path = gfile.get_path()
        try:
            with zipfile.ZipFile(path) as a_zipfile:
                directory = tempfile.mkdtemp(
                    suffix=os.sep,
                    dir=context.cache_directory
                )
                a_zipfile.extractall(directory)
                directory_gfile = Gio.File.new_for_path(directory)
                zip_result = opening.GFileFileSource(
                    directory_gfile, "", parent=source
                )
                results.sources.append(zip_result)
                '''
                # Momoizing append_file and join_path
                append_file = results.sources.append
                for a_name in a_zipfile.namelist():
                    a_filename = join_path(directory, a_name)
                    append_file(Gio.File.new_for_path(a_filename))'''
        finally:
            results.complete()


class ArchiveOpeners(extending.ComponentPackage):
    def add_on(self, app):
        components = app.components
        components.add(FileOpener.CATEGORY, ZipOpener())

extending.LoadedComponentPackages["archive-openers"] = ArchiveOpeners()
