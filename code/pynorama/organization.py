# coding=utf-8

""" organization.py contains code about collections of images. """

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


from gi.repository import GLib, GObject
from collections import MutableSequence
from . import utility

class Album(GObject.Object):
    ''' It organizes images '''
    
    __gsignals__ = {
        "image-added" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
        "image-removed" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
        "order-changed" : (GObject.SIGNAL_RUN_FIRST, None, []),
    }
    def __init__(self):
        GObject.GObject.__init__(self)
        MutableSequence.__init__(self)
        
        self.connect("notify::reverse", self.__queue_autosort)
        self.connect("notify::autosort", self.__queue_autosort)
        self.connect("notify::comparer", self.__queue_autosort)
        
        self._store = []
        self.__autosort_signal_id = None
        
    # --- Mutable sequence interface down this line ---#
    def __len__(self):
        return len(self._store)
        
    def __getitem__(self, item):
        return self._store[item]
        
    def __setitem__(self, item, value):
        self._store[item] = value
        
    def __delitem__(self, item):
        if isinstance(item, slice):
            indices = item.indices(len(self._store))
            removed_indices = []
            for i in range(*indices):
                if item.step and item.step < 0:
                    removed_indices.append(i)
                else:
                    removed_indices.append(i - len(removed_indices))
                    
            removed_images = self._store[item]
            del self._store[item]
            
            for i in range(len(removed_indices)):
                image, index = removed_images[i], removed_indices[i]
                self.emit("image-removed", image, index)
        else:
            image = self._store.pop(item)
            self.emit("image-removed", image, item)
    
    def insert(self, index, image):
        self._store.insert(index, image)
        self.emit("image-added", image, index)
        self.__queue_autosort()
    
    # --- "inheriting" down this line --- #
    
    __contains__ = MutableSequence.__contains__
    __iter__ = MutableSequence.__iter__
    __reversed__ = MutableSequence.__reversed__
    
    append = MutableSequence.append
    count = MutableSequence.count
    extend = MutableSequence.extend
    index = MutableSequence.index
    pop = MutableSequence.pop
    remove = MutableSequence.remove
    reverse = MutableSequence.reverse
    
    def sort(self):
        if self.__autosort_signal_id:
            GLib.source_remove(self.__autosort_signal_id)
            self.__autosort_signal_id = None
        
        if self.sort_list(self._store):
            self.emit("order-changed")
    
    def sort_list(self, a_list):
        if self.comparer and len(a_list) > 1:
            a_list.sort(key=self.comparer, reverse=self.reverse)
            return True
            
        else:
            return False
    
    def next(self, image):
        ''' Returns the image after the input '''
        index = self._store.index(image)
        return self._store[(index + 1) % len(self._store)]
        
    def previous(self, image):
        ''' Returns the image before the input '''
        index = self._store.index(image)
        return self._store[(index - 1) % len(self._store)]        
    
    def around(self, image, forward, backwards):
        ''' Returns "forward" images after "image" and
            "backwards" images before "image".
            This method cycles around the list '''
        result = []
        if forward or backwards:
            start = self._store.index(image)
            count = len(self._store)
        
            for i in range(1, 1 + forward):
                result.append(self._store[(start + i) % count])
            
            for i in range(1, 1 + backwards):
                result.append(self._store[(start - i) % count])
            
        return result
    
    # --- properties down this line --- #
    
    autosort = GObject.property(type=bool, default=False)
    comparer = GObject.property(type=object, default=None)
    reverse = GObject.property(type=bool, default=False)
    
    def __queue_autosort(self, *data):
        if self.autosort and not self.__autosort_signal_id:
            self.__autosort_signal_id = GLib.idle_add(
                self.__do_autosort, priority=GLib.PRIORITY_HIGH+10)
    
    def __do_autosort(self):
        self.__autosort_signal_id = None
        if self.autosort:
            self.sort()
        
        return False
        
class SortingKeys:
    ''' Contains functions to get keys in images for sorting them '''
    
    def ByName(image):
        return GLib.utf8_collate_key_for_filename(image.fullname, -1)
        
    def ByCharacters(image):
        return image.fullname.lower()
            
    def ByFileSize(image):
        return image.get_metadata().data_size
        
    def ByFileDate(image):
        return image.get_metadata().modification_date
        
    def ByImageSize(image):
        return image.get_metadata().get_area()
        
    def ByImageWidth(image):
        return image.get_metadata().width
        
    def ByImageHeight(image):
        return image.get_metadata().height
        
    Enum = [
        ByName, ByCharacters,
        ByFileSize, ByFileDate,
        ByImageSize, ByImageWidth, ByImageHeight
    ]


class AlbumViewLayout(GObject.Object):
    ''' Used to tell layouts the album used for a view
        Layouts should store data in this thing
        Just call this avl for short '''
    
    __gsignals__ = {
        "focus-changed" : (GObject.SIGNAL_RUN_FIRST, None, [object, bool])
    }
    
    
    def __init__(self, album=None, view=None, layout=None):
        GObject.Object.__init__(self)
        self.__is_clean = True
        self.__old_view = self.__old_album = self.__old_layout = None
        
        self.connect("notify::layout", self._layout_changed)
        
        self.layout = layout
        self.album = album
        self.view = view
    
    
    @property
    def focus_image(self):
        return self.__old_layout.get_focus_image(self)
    
    
    @property
    def focus_frame(self):
        return self.__old_layout.get_focus_frame(self)
    
    
    def go_index(self, index):
        self.__old_layout.go_image(self, self.album[index])
    
    
    def go_image(self, image):
        self.__old_layout.go_image(self, image)
    
    
    def go_next(self):
        self.__old_layout.go_next(self)
    
    
    def go_previous(self):
        self.__old_layout.go_previous(self)
    
    
    def clean(self):
        if not self.__is_clean:
            self.__old_layout.clean(self)
            self.__is_clean = True
    
    
    def _layout_changed(self, *data):
        focus_image = None
        if self.__old_layout:
            focus_image = self.focus_image
            self.__old_layout.unsubscribe(self)
            self.clean()
        
        self.__old_layout = self.layout
        if self.layout:
            self.__is_clean = False
            self.layout.start(self)
            self.layout.subscribe(self)
            self.go_image(focus_image)
    
    
    album = GObject.property(type=object, default=None)
    view = GObject.property(type=object, default=None)
    layout = GObject.property(type=object, default=None)


class AlbumLayout:
    ''' Places images from an album into a view '''
    def __init__(self):
        self.__subscribers = set()
        
        self.refresh_subscribers = utility.IdlyMethod(self.refresh_subscribers)
        self.refresh_subscribers.priority = GLib.PRIORITY_HIGH + 20
        
        # This value is set by the app when the layout is created
        self.source_option = None
        
        # Set this to a Gtk.ActionGroup to include custom menu items
        # into the ViewerWindow uimanager. You also have to implement
        # the add_ui method in that case.
        self.ui_action_group = None
        

    def subscribe(self, avl):
        self.__subscribers.add(avl)
        

    def unsubscribe(self, avl):
        self.__subscribers.discard(avl)
        

    def refresh_subscribers(self):
        ''' Layouts should call this or queue_refresh for
            propagating changes in the layout properites '''
            
        for avl in self.__subscribers:
            self.update(avl)    
    
    #~ Interface down this line ~#
    
    def get_focus_image(self, avl):
        ''' Returns the image in focus '''
        raise NotImplementedError

    
    def get_focus_frame(self, avl):
        ''' Returns the frame in focus '''
        raise NotImplementedError
                

    def go_image(self, avl, image):
        ''' Lays out an image '''
        raise NotImplementedError
        
    def go_next(self, avl):
        focus = avl.focus_image
        next_image = avl.album.next(focus)
        avl.go_image(next_image)
        
    def go_previous(self, avl):
        focus = avl.focus_image
        previous_image = avl.album.previous(focus)
        avl.go_image(previous_image)        
        

    def start(self, avl):
        ''' Set any initial variables in an AlbumViewLayout '''
        pass
        
    def clean(self, avl):
        ''' Reverse whatever was done at start '''
        pass    

    def update(self, avl):
        ''' Propagate changes in a layout property to an avl '''
        pass


class LayoutDirection:
    Left = "left"
    Right = "right"
    Up = "up"
    Down = "down"
    
    Enum = [Up, Right, Down, Left]
