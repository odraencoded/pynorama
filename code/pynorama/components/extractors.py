""" extrators.py adds support to open archive extractors."""

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

from pynorama.extending import Opener
from pynorama import extending, opening
from pynorama.components import openers

class ZipOpener(Opener, openers.GFileOpener):
    CODENAME = "zip"
    
    def __init__(self):
        Opener.__init__(self, ZipOpener.CODENAME, opening.GFileSource.KIND)
        openers.GFileOpener.__init__(self, mime_types={"application/zip"})
    
    
    @GObject.Property
    def label(self):
        return _("Zipfile Archives")
    
    
    def open_file_source(self, context, results, source):
        """ Opens a directory file and yields its contents """
        
        # TODO: Add asynchronous loading
        
        gfile = source.gfile
        path = gfile.get_path()
        a_zipfile = None
        try:
            a_zipfile = zipfile.ZipFile(path)
            
            # Caching files
            directory = tempfile.mkdtemp(
                suffix=os.sep, dir=context.cache_directory)
            zipfile_cache = opening.FileCache(directories=[directory])
            a_zipfile.extractall(directory)
            
            # Returning file source
            directory_gfile = Gio.File.new_for_path(directory)
            zip_result = opening.GFileSource(
                directory_gfile, "", parent=source)
            zip_result.cache = zipfile_cache
            results.sources.append(zip_result)
        
        except Exception as e:
            results.errors.append(e)
            
        finally:
            if a_zipfile:
                a_zipfile.close()
            results.complete()


class ArchiveOpeners(extending.ComponentPackage):
    def add_on(self, app):
        components = app.components
        components.add(Opener.CATEGORY, ZipOpener())

extending.LoadedComponentPackages["archive-openers"] = ArchiveOpeners()
