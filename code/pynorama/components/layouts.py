""" layouts.py adds a few album layouts to the image viewer """

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
    

from gi.repository import GLib, GObject, Gtk
from pynorama import utility, widgets, extending
from pynorama.organizing import AlbumLayout, LayoutDirection
from gettext import gettext as _

class SingleImageLayout(AlbumLayout):
    ''' Places a single album image in a view '''
    
    def __init__(self):
        AlbumLayout.__init__(self)
    
    
    def start(self, avl):
        avl.load_handle = None
        
        avl.current_image = None
        avl.current_frame = None
        avl.previous_frame = None
        avl.previous_image = None
        
        avl.old_album = None
        avl.removed_signal_id = None
        avl.album_notify_id = avl.connect(
            "notify::album", self._album_changed, avl
        )
        self._album_changed(avl)
    
    
    def clean(self, avl):
        if avl.load_handle:
            avl.current_image.disconnect(avl.load_handle)
        del avl.load_handle
        
        if avl.current_frame:
            avl.view.remove_frame(avl.current_frame)
        del avl.current_frame
        del avl.current_image
        
        if avl.previous_frame:
            avl.view.remove_frame(avl.previous_frame)
        del avl.previous_frame
        del avl.previous_image
        
        avl.disconnect(avl.album_notify_id)
        del avl.album_notify_id
        
        if not avl.old_album is None:
            avl.old_album.disconnect(avl.removed_signal_id)
            
        del avl.old_album
        del avl.removed_signal_id
    
    
    def get_focus_image(self, avl):
        return avl.current_image
    
    
    def get_focus_frame(self, avl):
        return avl.current_frame
    
    
    def go_image(self, avl, target_image):
        if avl.current_image == target_image:
            return
        
        if avl.load_handle: # remove "finished-loading" handle
            avl.current_image.disconnect(avl.load_handle)
            avl.load_handle = None
            if avl.current_image.is_loading:
                avl.current_image.cancel_request()
        
        if avl.previous_image is None and avl.current_frame is not None:
            avl.previous_image = avl.current_image
            avl.previous_frame = avl.current_frame
            
        avl.current_image = target_image
        
        if target_image is None:
            # Current image being none means nothing is displayed #
            self._refresh_frame(avl)
            
            if avl.previous_frame is not None:
                avl.view.remove_frame(avl.previous_frame)
            
            avl.previous_image = None
            avl.previous_frame = None
            
        else:
            target_image.request_data()
            if target_image.is_loaded or target_image.is_bad:
                self._refresh_frame(avl)
                
            else:
                avl.load_handle = avl.current_image.connect(
                    "finished-loading",
                    self._image_loaded, avl
                )
        
        avl.emit("focus-changed", avl.current_image, False)
    
    
    def _refresh_frame(self, avl):
        if avl.previous_frame:
            avl.view.remove_frame(avl.previous_frame)
            
        avl.previous_frame = None
        avl.previous_image = None
        
        if avl.current_image:
            new_frame = avl.current_image.create_frame()
            avl.current_frame = new_frame
            avl.view.add_frame(new_frame)
            avl.view.align_to_frame(new_frame)
    
    
    def _album_changed(self, avl, *data):
        if not avl.old_album is None:
            avl.old_album.disconnect(avl.removed_signal_id)
            avl.removed_signal_id = None
        
        avl.old_album = avl.album
        if not avl.album is None:
            avl.removed_signal_id = avl.album.connect(
                "image-removed",
                self._image_removed, avl
            )
    
    
    def _image_removed(self, album, image, index, avl):
        if image == avl.current_image:
            count = len(album)
            if index <= count:
                if count >= 1:
                    new_index = index - 1 if index == count else index
                    new_image = album[new_index]
                else:
                    new_image = None
                    
                self.go_image(avl, new_image)
                
        elif image == avl.previous_image:
            avl.view.remove_frame(avl.previous_frame)
            avl.previous_image = None
            avl.previous_frame = None
    
    
    def _image_loaded(self, image, error, avl):
        self._refresh_frame(avl)


class ImageStripLayout(GObject.Object, AlbumLayout):
    ''' Places a strip of album images, laid side by side, in a view '''
    
    def __init__(self, margin=None, space=None, limit=None, **kwargs):
        GObject.Object.__init__(self, **kwargs)
        AlbumLayout.__init__(self)
        
        if margin:
            self.margin_before, self.margin_after = margin
        if space:
            self.space_before, self.space_after = space
        if limit:
            self.limit_before, self.limit_after = limit
        
        self.connect("notify::direction", self._direction_changed)
        self.connect("notify::repeat", self._placement_args_changed)
        self.connect("notify::loop", self._placement_args_changed)
        self.connect("notify::space-before", self._placement_args_changed)
        self.connect("notify::space-after", self._placement_args_changed)
        self.connect("notify::limit-before", self._placement_args_changed)
        self.connect("notify::limit-after", self._placement_args_changed)
        self.connect("notify::margin-before", self._placement_args_changed)
        self.connect("notify::margin-after", self._placement_args_changed)
        self.connect("notify::alignment", self._placement_args_changed)
        self.connect("notify::own-alignment", self._placement_args_changed)
        self.connect("notify::loop", self._loop_changed)
        self.connect("notify::repeat", self._repeat_changed)
        
        # set internal methods
        (
            self._get_length, self._get_rect_distance,
            self._place_before, self._place_after
        ) = ImageStripLayout.DirectionMethods[self.direction]
        
    
    
    def update(self, avl):
        self._update_sides(avl)
        self._reposition_frames(avl)
    
    
    def start(self, avl):
        avl.center_index = avl.center_frame = avl.center_image = None
        avl.shown_images, avl.shown_frames = [], []
        avl.space_before = avl.space_after = 0
        avl.load_handles = {}
        
        avl.old_view = avl.old_album = None
        
        # Use PRIORITY_DEFAULT_IDLE - 10 to create frames after they
        # are drawn but before they can be unloaded (avoiding having to reload
        # images after a _clear_images(...)        
        avl.update_sides = utility.IdlyMethod(self._update_sides, avl)
        avl.update_sides.priority = GLib.PRIORITY_DEFAULT_IDLE - 10
        
        avl.album_signals = []
        avl.view_signals = []
        avl.notify_signals = [
            avl.connect("notify::album", self._album_changed, avl),
            avl.connect("notify::view", self._view_changed, avl)
        ]
        self._view_changed(avl)
        self._album_changed(avl)
    
    
    def clean(self, avl):
        for a_frame in avl.shown_frames:
            if a_frame:
                avl.view.remove_frame(a_frame)
                
        for an_image, a_handle_id in avl.load_handles.items():
            an_image.disconnect(a_handle_id)
            an_image.cancel_request()
        
        del avl.center_image, avl.center_frame
        del avl.shown_images, avl.shown_frames
        del avl.space_before, avl.space_after
        del avl.load_handles
        
        for signal_id in avl.notify_signals:
            avl.disconnect(signal_id)
            
        if avl.old_album is not None:
            for signal_id in avl.album_signals:
                avl.old_album.disconnect(signal_id)
        
        if avl.old_view is not None:
            for signal_id in avl.view_signals:
                avl.old_view.disconnect(signal_id)            
        
        avl.update_sides.cancel_queue()
        del avl.update_sides
        
        del avl.old_album, avl.old_view
        del avl.notify_signals
        del avl.album_signals, avl.view_signals
    
    
    def get_focus_image(self, avl):
        return avl.center_image
    
    
    def get_focus_frame(self, avl):
        return avl.center_frame
    
    
    def go_next(self, avl):
        if avl.center_frame:
            new_index = avl.center_index + 1
            if new_index < len(avl.shown_images):
                avl.center_image = avl.shown_images[new_index]
                avl.center_frame = avl.shown_frames[new_index]
                avl.center_index = new_index
                
                # If the center frame is already loaded, align the view to it.
                # If it's not, then that is handled in _refresh_frames
                if avl.center_frame:
                    avl.view.align_to_frame(avl.center_frame)
                    
                avl.emit("focus-changed", avl.center_image, False)
                
            else:
                new_image = avl.album.next(avl.center_image)
                if not self.loop and new_image is avl.album[0]:
                    self._clear_images(avl)
                    new_index = 0
                    
                avl.center_index = avl.center_frame = avl.center_image = None
                
                self._insert_image(avl, new_index, new_image)
                
            avl.update_sides.queue()
    
    
    def go_previous(self, avl):
        if avl.center_frame:
            new_index = avl.center_index - 1
            if new_index >= 0:
                avl.center_image = avl.shown_images[new_index]
                avl.center_frame = avl.shown_frames[new_index]
                avl.center_index = new_index
                
                if avl.center_frame:
                    avl.view.align_to_frame(avl.center_frame)
                    
                avl.emit("focus-changed", avl.center_image, False)
                
            else:
                new_image = avl.album.previous(avl.center_image)
                if not self.loop and new_image is avl.album[-1]:
                    self._clear_images(avl)
                
                avl.center_index = avl.center_frame = avl.center_image = None
                
                self._insert_image(avl, 0, new_image)
                
            avl.update_sides.queue()
    
    
    def go_image(self, avl, image):
        if avl.center_image is image:
            return
            
        self._clear_images(avl)
        avl.center_index = avl.center_image = avl.center_frame = None
        self._insert_image(avl, 0, image)
    
    #-- Properties down this line --#
    
    # What direction a fore image should be in relation to a hind image...
    # or something like that
    direction = GObject.property(type=str, default="down")
    
    # Whether to continue laying images to a side after finding
    # the center image on that side
    repeat = GObject.property(type=bool, default=False)
    
    # Whether to add the last image of an album before the first image and
    # vice versa
    loop = GObject.property(type=bool, default=False)
    
    # Set to true to use the alignment property instead 
    # of the view alignment
    own_alignment = GObject.property(type=bool, default=False)
    
    # Alignment for the perpendicular axis, 
    # 0..1 = left/right or top/bottom
    alignment = GObject.property(type=float, default=.5)
    
    # Distance between two adjacent images
    margin_after = GObject.property(type=int, default=0)
    margin_before = GObject.property(type=int, default=0)
    
    # Target for the number of pixels before or after the center image.
    # The space will be at least these values except when a limit is hit
    space_before = GObject.property(type=int, default=2560)
    space_after = GObject.property(type=int, default=3840)
    
    # Limit for the number of images placed after
    # and before the center image
    limit_before = GObject.property(type=int, default=40)
    limit_after = GObject.property(type=int, default=60)
    
    #-- Implementation detail down this line --#
    def _direction_changed(self, *data):
        (
            self._get_length, self._get_rect_distance,
            self._place_before, self._place_after
        ) = ImageStripLayout.DirectionMethods[self.direction]
        
        self.refresh_subscribers.queue()
    
    
    def _placement_args_changed(self, *data):
        self.refresh_subscribers.queue()
    
    
    # These two handlers keep loop/repeat synced
    def _loop_changed(self, *data):
        if not self.loop and self.repeat:
            self.repeat = False
            
    def _repeat_changed(self, *data):
        if self.repeat and not self.loop:
            self.loop = True
    
    def _view_changed(self, avl, *data):
        # Handler for album changes in avl
        if avl.old_view is not None:
            for signal_id in avl.view_signals:
                avl.old_view.disconnect(signal_id)
                
            avl.view_signals = None
            
        view = avl.old_view = avl.view
        if view is not None:
            avl.view_signals = [
                view.connect("offset-change", self._offset_changed, avl),
                view.connect(
                    "notify::alignment-x",self._alignment_changed, avl
                ),
                view.connect(
                    "notify::alignment-y", self._alignment_changed, avl
                )
            ]
                
    
    def _album_changed(self, avl, *data):
        # Handler for album changes in avl
        if avl.old_album is not None:
            for signal_id in avl.album_signals:
                avl.old_album.disconnect(signal_id)
                
            avl.album_signals = None
            
        avl.old_album = avl.album
        if avl.album is not None:
            avl.album_signals = [
                avl.album.connect("image-removed", self._image_removed, avl),
                avl.album.connect("image-added", self._image_added, avl),
                avl.album.connect("order-changed", self._order_changed, avl),
            ]


    def _offset_changed(self, view, avl, *data):
        ''' This checks whether an offset change in the view, caused by
            panning for example, was big enough to change the focus image '''
            
        if avl.center_frame and not view.frames_fit:
            w, h = avl.view.get_widget_size()
            get_absolute_point = avl.view.get_absolute_point
            corners = utility.Rectangle(0, 0, w, h).corners()
            absolute_view_rect = utility.Rectangle.FromPoints(
                *(get_absolute_point(a_corner) for a_corner in corners)
            )
            
            current_index = avl.center_index
            current_distance = None
            frame_distances = []
            margin_before, margin_after = self.margin_before, self.margin_after
            ax, ay = avl.view.alignment_point
            
            for i, a_frame in enumerate(avl.shown_frames):
                if a_frame:
                    a_rect = a_frame.rectangle.shift(a_frame.origin)
                    a_distance = self._get_rect_distance(
                        ax, ay, absolute_view_rect, a_rect
                    )
                    
                    if i == current_index:
                        current_distance = a_distance
                        
                    elif i > current_index:
                        a_distance += margin_after
                        
                    else:
                        a_distance += margin_before
                    
                    
                    frame_distances.append((i, a_distance))
            
            if frame_distances:
                best_index, best_distance = min(
                    frame_distances, key=lambda v: v[1]
                )
                                            
                if current_distance is None or best_distance < current_distance:
                    best_image = avl.shown_images[best_index]
                    best_frame = avl.shown_frames[best_index]
            
                    if avl.center_image is not best_image:
                        avl.center_index = best_index            
                        avl.center_image = best_image
                        avl.center_frame = best_frame
                        
                        avl.update_sides.queue()
                        self._reposition_frames(avl)
                        avl.emit("focus-changed", best_image, True)


    def _alignment_changed(self, view, data, avl):
        if not self.own_alignment:
            self._reposition_frames(avl)
    
    
    def _image_added(self, album, image, index, avl):
        # Handles an iamge added to an album
        next = album.next(image)
        prev = album.previous(image)
        
        if prev is image or prev is next:
            prev = None
            
        if next is image:
            next = None
            
        if prev or next:
            change = 0
            inserted_prev = False
            for i in range(len(avl.shown_images)):
                j = i + change
                an_image = avl.shown_images[j]
                if an_image is next and not inserted_prev:
                    self._insert_image(avl, j, image)
                    change += 1
                    inserted_prev = False
                    
                elif an_image is prev:
                    self._insert_image(avl, j + 1, image)
                    change += 1
                    inserted_prev = True
                    
                else:
                    inserted_prev = False


    def _image_removed(self, album, image, index, avl):
        # Handles an image removed from an album
        removed_frame = False
        while image in avl.shown_images:
            removed_index = avl.shown_images.index(image)
            self._remove_image(avl, removed_index)
            removed_frame = True
                
        if removed_frame:
            if image is avl.center_image:
                new_index = avl.center_index
                if new_index < len(avl.shown_images):
                    avl.center_image = avl.shown_images[new_index]
                    avl.center_frame = avl.shown_frames[new_index]
                    avl.center_index = new_index
                    avl.emit("focus-changed", avl.center_image, True)
            
                else:
                    avl.center_index = None
                    avl.center_frame = avl.center_image = None
                    if avl.album:
                        new_image = avl.album.next(avl.album[index - 1])
                        self._insert_image(avl, new_index, new_image)
                    else:
                        avl.emit("focus-changed", avl.center_image, True)
            
            avl.update_sides.queue()
            self._reposition_frames(avl)
    
    
    def _order_changed(self, album, avl):
        self._clear_images(avl)
        old_center_image = avl.center_image
        avl.center_index = avl.center_image = avl.center_frame = None
        if old_center_image is not None:
            self._insert_image(avl, 0, old_center_image)
    
    
    def _insert_image(self, avl, index, image):
        ''' Handles a image inserted in an album '''
        avl.shown_images.insert(index, image)
        avl.shown_frames.insert(index, None)
        
        image.request_data()
        
        if not avl.center_image:
            # If there is no center image, set it to the newly inserted one
            avl.center_index = index
            avl.center_image = image
            
            self._load_frame(avl, image)
            avl.emit("focus-changed", image, False)
        else:
            if index <= avl.center_index:
                # Increment the center index because a frame was added before it
                avl.center_index += 1
                
            self._load_frame(avl, image)
    
    
    def _remove_image(self, avl, index):
        ''' Handles a image removed from an album '''
        image = avl.shown_images.pop(index)
        frame = avl.shown_frames.pop(index)
        
        if frame: # Remove frame from view
            avl.view.remove_frame(frame)
        
        if image not in avl.shown_images:
            # If the image is no longer shown, remove the loading handler
            load_handle_id = avl.load_handles.pop(image, None)
            if load_handle_id:
                image.disconnect(load_handle_id)
                image.cancel_request()
        
        if avl.center_image and index < avl.center_index:
            # Decrement the center index because a frame was removed before it
            avl.center_index -= 1
    
    
    def _append_image(self, avl, image):
        self._insert_image(avl, len(avl.shown_images), image)
    
    
    def _prepend_image(self, avl, image):
        self._insert_image(avl, 0, image)
    
    
    def _clear_images(self, avl):
        while avl.shown_images:
            self._remove_image(avl, 0)
    
    
    def _load_frame(self, avl, image):
        if image.is_loaded or image.is_bad:
            self._refresh_frames(avl, image)
            avl.update_sides.queue()
            
        else:
            load_handle_id = avl.load_handles.get(image, None)
            if not load_handle_id:
                load_handle_id = image.connect(
                    "finished-loading", self._image_loaded, avl)
                avl.load_handles[image] = load_handle_id
    
    
    def _image_loaded(self, image, error, avl):
        load_handle_id = avl.load_handles.pop(image, None)
        if load_handle_id:
            image.disconnect(load_handle_id)
            
        if image in avl.shown_images:
            self._refresh_frames(avl, image)
            avl.update_sides.queue()
    
    
    def _update_sides(self, avl):
        # Adds or removes images at either side
        if avl.center_frame:
            # Cache some properties
            margin_before, margin_after = self.margin_before, self.margin_after
            space_before, space_after = self.space_before, self.space_after
            limit_before, limit_after = self.limit_before, self.limit_after
            loop, repeat = self.loop, self.repeat
            
            center_image = avl.center_image
            shown_frames, shown_images = avl.shown_frames, avl.shown_images
            album = avl.album
            
            if not loop:
                first_image = album[0]
                for i in range(avl.center_index, 0, -1):
                    if shown_images[i] is first_image:
                        for j in range(i):
                            self._remove_image(avl, 0)
                            
                        break
                        
                last_image = album[-1]
                for i in range(avl.center_index, len(shown_images)):
                    if shown_images[i] is last_image:
                        for j in range(len(shown_images) - i - 1):
                            self._remove_image(avl, i + 1)
                            
                        break
                        
            elif not repeat:
                # Removes the center image from around the center frame
                for i in range(avl.center_index -1, -1, -1):
                    if shown_images[i] is center_image:
                        for j in range(i + 1):
                            self._remove_image(avl, 0)
                            
                        break
                        
                for i in range(avl.center_index + 1, len(shown_images)):
                    if shown_images[i] is center_image:
                        for j in range(len(shown_images) - i):
                            self._remove_image(avl, i)
                            
                        break
            
            self._compute_lengths(avl)
            
            before_count = avl.center_index
            after_count = len(shown_images) - avl.center_index - 1
                        
            if after_count > limit_after:
                # Remove images after center image
                # if the count is over the limit
                for i in range(after_count - limit_after):
                    a_length = self._get_length(shown_frames[-1])
                    avl.space_after -= a_length + margin_after
                    self._remove_image(avl, len(shown_frames) -1)
                
                after_count = limit_after
            
            if after_count < limit_after:
                foremost_frame = shown_frames[-1]
                # Add an image if there is extra space
                if avl.space_after < space_after:
                    if foremost_frame:
                        foremost_image = shown_images[-1]
                        new_image = album.next(foremost_image)
                        
                        valid_insert = True
                        if not repeat:
                            valid_insert = new_image is not center_image
                        
                        if valid_insert and not loop:
                            valid_insert = new_image is not album[0]
                            
                        if valid_insert:
                            self._append_image(avl, new_image)
                        
                else:
                    # Remove images if there is no extra space
                    foremost_length = self._get_length(foremost_frame)
                    foremost_length += margin_after
                    while avl.space_after - foremost_length > \
                          space_after if foremost_frame \
                          else avl.space_after > space_after:
                        self._remove_image(avl, len(shown_frames) -1)
                        avl.space_after -= foremost_length
                        foremost_frame = shown_frames[-1]
                        foremost_length = self._get_length(foremost_frame)
                        foremost_length += margin_after
                    
            if before_count > self.limit_before:
                # Remove images before center image
                # if the count is over the limit
                for i in range(before_count - limit_before):
                    a_length = self._get_length(shown_frames[0])
                    avl.space_before -= a_length + margin_before
                    self._remove_image(avl, 0)
                    
                before_count = self.limit_before
                
            if before_count < limit_before:
                backmost_frame = shown_frames[0]
                # Add an image if there is extra space
                if avl.space_before < space_before:
                    if backmost_frame:
                        backmost_image = shown_images[0]
                        new_image = album.previous(backmost_image)
                        
                        valid_insert = True
                        if not repeat:
                            valid_insert = new_image is not center_image
                        
                        if valid_insert and not loop:
                            valid_insert = new_image is not album[-1]
                            
                        if valid_insert:
                            self._prepend_image(avl, new_image)
                            
                else:
                    # Remove images if there is no extra space
                    backmost_length = self._get_length(backmost_frame)
                    backmost_length += margin_before
                    while avl.space_before - backmost_length > \
                          space_before if backmost_frame \
                          else avl.space_before > space_before:
                        self._remove_image(avl, 0)
                        avl.space_before -= backmost_length
                        backmost_frame = shown_frames[0]
                        backmost_length = self._get_length(backmost_frame)
                        backmost_length += margin_before
                        
    def _refresh_frames(self, avl, image, overwrite=False):
        # Create and add frames to represent images
        error_surface = None
        new_frames = []
        for i in range(len(avl.shown_images)):
            shown_image = avl.shown_images[i]
            if image is shown_image:
                shown_frame = avl.shown_frames[i]
                if not shown_frame or overwrite:
                    shown_frame = image.create_frame()
                    self._set_frame(avl, i, shown_frame)
                    new_frames.append(shown_frame)
                    
        if new_frames:
            if image is avl.center_image and not avl.center_frame:
                avl.center_frame = new_frames[0]
                avl.view.align_to_frame(avl.center_frame)
            
            self._reposition_frames(avl)
        
    def _set_frame(self, avl, index, new_frame):
        old_frame = avl.shown_frames[index]
        if new_frame is not old_frame:
            if old_frame:
                avl.view.remove_frame(old_frame)
            
            avl.shown_frames[index] = new_frame
            if new_frame:
                avl.view.add_frame(new_frame)
    
    def _reposition_frames(self, avl):
        ''' Place the frames of images around the center image
            around the center frame '''
            
        if avl.center_frame:
            shown_frames = avl.shown_frames
            frame_count = len(shown_frames)
            placement_data = (
                (self._place_before, self.margin_before,
                 range(avl.center_index, -1, -1)),
                 
                (self._place_after, self.margin_after,
                 range(avl.center_index, frame_count))
            )
            
            for a_coordinator, a_margin, a_range in placement_data:
                self._place_frames(avl, a_coordinator, a_margin,
                                   (shown_frames[j] for j in a_range))
                
    def _compute_lengths(self, avl):
        ''' Recalculate the space used by frames around the center frame '''
        if avl.center_frame:
            side_stuff = (
                (self.margin_before, range(avl.center_index)),
                (
                    self.margin_after,
                    range(avl.center_index + 1, len(avl.shown_frames))
                )
            )
            side_lengths = []
            
            for a_margin, a_side_range in side_stuff:
                a_side_length = 0
                for j in a_side_range:
                    a_frame = avl.shown_frames[j]
                    if a_frame:
                        a_side_length += self._get_length(a_frame) + a_margin
                
                side_lengths.append(a_side_length)
                
            avl.space_before, avl.space_after = side_lengths
            
        else:
            avl.space_after = 0
            avl.space_before = 0
    
    def _place_frames(self, avl, coordinate_modifier, margin, frames):
        ''' Places a list of frames side by side '''
        
        # Get the alignment
        if self.own_alignment:
            alignment = self.alignment
            
        else:
            if self.direction in [LayoutDirection.Up, LayoutDirection.Down]:
                alignment = avl.view.alignment_x
                
            else:
                alignment = avl.view.alignment_y
        
        previous_rect = None
        for a_frame in frames:
            if a_frame:
                frame_rect = a_frame.rectangle
                ox, oy = a_frame.origin
                if previous_rect:
                    ox, oy = coordinate_modifier(alignment    , margin,
                                                 previous_rect, frame_rect)
                    a_frame.origin = ox, oy
                    
                previous_rect = frame_rect.shift((ox, oy))
                previous_rect.ox, previous_rect.oy = ox, oy
                
    # lambda args are
    # alignment, margin, previous translated rectangle, current rectangle
    _CoordinateToRight = lambda a, m, p, r: (
        p.right - r.left + m,
        p.top - r.top + (p.height - r.height) * a
    )
    _CoordinateToLeft = lambda a, m, p, r: (
        p.left - r.right - m,
        p.top - r.top + (p.height - r.height) * a
    )
    _CoordinateToTop = lambda a, m, p, r: (
        p.left - r.left + (p.width - r.width) * a,
        p.top - r.bottom - m
    )
    _CoordinateToBottom = lambda a, m, p, r: (
        p.left - r.left + (p.width - r.width) * a,
        p.bottom - r.top + m
    )
    _GetFrameWidth = lambda f: f.rectangle.width if f else 0
    _GetFrameHeight = lambda f: f.rectangle.height if f else 0
    
    # These calculate the distance of rectangles to figure out what
    # is the current frame after the offset changes
    # ax and ay are alignments
    def _GetHorizontalRectDistance(ax, ay, view_rect, rect):
        center = view_rect.left + view_rect.width * ax
        dist_a = abs(rect.left - center)
        dist_b = abs(rect.left + rect.width - center)
        
        # Use * (1 - ax) and * ax here so that the distance values
        # matches the alignment of frames with the view
        return dist_a * (1 - ax) + dist_b * ax
        
    def _GetVerticalRectDistance(ax, ay, view_rect, rect):
        center = view_rect.top + view_rect.height * ay
        dist_a = abs(rect.top - center)
        dist_b = abs(rect.top + rect.height - center)
        return dist_a * (1 - ay) + dist_b * ay
            
    DirectionMethods = {
        LayoutDirection.Right : (
            _GetFrameWidth, _GetHorizontalRectDistance,
            _CoordinateToLeft, _CoordinateToRight
        ),
        LayoutDirection.Left : (
            _GetFrameWidth, _GetHorizontalRectDistance,
            _CoordinateToRight, _CoordinateToLeft
        ),
        LayoutDirection.Up : (
            _GetFrameHeight, _GetVerticalRectDistance,
            _CoordinateToBottom, _CoordinateToTop
        ),
        LayoutDirection.Down : (
            _GetFrameHeight, _GetVerticalRectDistance,
            _CoordinateToTop, _CoordinateToBottom
        )
    }


#~~~ Making the built-in layouts avaiable ~~~#
class SingleImageLayoutOption(extending.LayoutOption):
    CODENAME = "single-image"
    def __init__(self):
        extending.LayoutOption.__init__(self, SingleImageLayoutOption.CODENAME)
    
    
    @GObject.Property
    def label(self):
        return _("Single Image")
    
    @GObject.Property
    def description(self):
        return _("Shows a single image")
    
    
    def create_layout(self, app):
        return SingleImageLayout()


class ImageStripLayoutOption(extending.LayoutOption):
    CODENAME = "image-strip"
    
    def __init__(self):
        extending.LayoutOption.__init__(self, ImageStripLayoutOption.CODENAME)
        self.has_settings_widget = True
        self.has_menu_items = True
    
    
    @GObject.Property
    def label(self):
        return _("Image Strip")
    
    @GObject.Property
    def description(self):
        return _("Shows multiple images side by side")
    
    
    def create_layout(self, app):
        result = ImageStripLayout()
        result.app = app
        result._action_group = None
        
        # load preferences
        preferences = app.settings["layout", "image-strip"].data
        utility.SetPropertiesFromDict(
            result, preferences,
            "alignment", "direction", "loop", "repeat",
            "margin-before", "margin-after",
            "space-before", "space-after",
            "limit-before", "limit-after",
            "own-alignment"
        )
        return result
    
    
    def save_preferences(self, layout):
        preferences = layout.app.settings["layout", "image-strip"].data
        
        utility.SetDictFromProperties(
            layout, preferences,
            "alignment", "direction", "loop", "repeat",
            "margin-before", "margin-after",
            "space-before", "space-after",
            "limit-before", "limit-after",
            "own-alignment"
        )
    
    def create_settings_widget(self, layout):
        return ImageStripLayoutSettingsWidget(layout)
        
    def add_ui(self, layout, uimanager, merge_id):
        placeholder_path = "/ui/menubar/view/layout/layout-configure-menu"
        
        direction_name = "image-strip-layout-direction"
        uimanager.add_ui(
            merge_id, placeholder_path, direction_name, direction_name,
            Gtk.UIManagerItemType.MENU, False
        )
        ui_list = [
            (placeholder_path, [
                "image-strip-layout-loop",
                "image-strip-layout-repeat",
            ]),
            (placeholder_path + "/image-strip-layout-direction", [
                "image-strip-layout-direction-up",
                "image-strip-layout-direction-right",
                "image-strip-layout-direction-down",
                "image-strip-layout-direction-left",
            ]),
        ]
        
        for a_path, a_name_list in ui_list:
            for a_name in a_name_list:
                uimanager.add_ui(
                    merge_id, a_path, a_name, a_name,
                    Gtk.UIManagerItemType.MENUITEM, False
                )
    
    def get_action_group(self, layout):
        if layout._action_group is None:
            self._setup_actions(layout)
            
        return layout._action_group
    
    def _setup_actions(self, layout):
        actions = layout._action_group = Gtk.ActionGroup("image-strip-layout")
        
        def direction_chosen(action, current_action, layout):
            current_value = current_action.get_current_value()
            new_value = LayoutDirection.Enum[current_value]
            if layout.direction != new_value:
                layout.direction = new_value
                
        def direction_changed(layout, something, some_action):
            direction_value = LayoutDirection.Enum.index(layout.direction)
            some_action.set_current_value(direction_value)
            
        
        action_params = [
            ("image-strip-layout-loop", _("Loop Album"),
             _("Place the first image of an album after the last, " + 
               "and vice versa"), None),
            ("image-strip-layout-repeat", _("Repeat Images"),
             _("In albums with few, small images, " +
               "repeat those images indefinetely"), None),
            ("image-strip-layout-direction", _("Direction"),
             _("Choose which direction are images placed toward"), None),
            ("image-strip-layout-direction-up", _("Up"),
             _("Places images one atop another"), None),
            ("image-strip-layout-direction-right", _("Right"),
             _("Places images one at right of another"), None),
            ("image-strip-layout-direction-down", _("Down"),
             _("Places images one under another"), None),
            ("image-strip-layout-direction-left", _("Left"),
             _("Places images one at left of another"), None)
        ]
        
        signaling_params = {
            "image-strip-layout-direction-up" : (direction_chosen, layout)
        }
        
        loop_group, direction_group = [], []
        
        toggleable_actions = {
            "image-strip-layout-loop" : None,
            "image-strip-layout-repeat" : None,
            "image-strip-layout-direction-up" : (0, direction_group),
            "image-strip-layout-direction-right" : (1, direction_group),
            "image-strip-layout-direction-down" : (2, direction_group),
            "image-strip-layout-direction-left" : (3, direction_group)
        }
        
        for name, label, tip, stock in action_params:
            some_signal_params = signaling_params.get(name, None)
            if name in toggleable_actions:
                # Toggleable actions :D
                group_data = toggleable_actions[name]
                if group_data is None:
                    # No group data = ToggleAction
                    signal_name = "toggled"
                    an_action = Gtk.ToggleAction(name, label, tip, stock)
                else:
                    # Group data = RadioAction
                    signal_name = "changed"
                    radio_value, group_list = group_data
                    an_action = Gtk.RadioAction(
                        name, label, tip, stock, radio_value
                    )
                    # Join the group of last radioaction in the list
                    if group_list:
                        an_action.join_group(group_list[-1])
                    group_list.append(an_action)
            else:
                # Non-rare kind of action
                signal_name = "activate"
                an_action = Gtk.Action(name, label, tip, stock)
            
            # Set signal
            if some_signal_params:
                an_action.connect(signal_name, *some_signal_params)
            
            # Add to action group
            actions.add_action(an_action)
        
        loop_action = actions.get_action("image-strip-layout-loop")
        repeat_action = actions.get_action("image-strip-layout-repeat")
        
        utility.Bind(
            layout, 
            ("loop", loop_action, "active"),
            ("repeat", repeat_action, "active"),
            bidirectional=True, synchronize=True
        )
        
        up_option = actions.get_action("image-strip-layout-direction-up")
        layout.connect("notify::direction", direction_changed, up_option)
        direction_value = LayoutDirection.Enum.index(layout.direction)
        up_option.set_current_value(direction_value)


class ImageStripLayoutSettingsWidget(Gtk.Notebook):
    ''' A widget for configuring a ImageStripLayout '''
    def __init__(self, layout):
        Gtk.Notebook.__init__(self)
        
        self.layout = layout    
        line_args = {
            "orientation": Gtk.Orientation.HORIZONTAL,
            "spacing": 24
        }
        
        #-- Create direction widgets --#
        label = _("Image strip direction")
        direction_label = Gtk.Label(label)
        direction_tooltip = _('''\
The images that come after the center image are placed \
towards this direction''')
        
        direction_model = Gtk.ListStore(str, str)
        
        direction_model.append([LayoutDirection.Up, _("Up")])
        direction_model.append([LayoutDirection.Right, _("Right")])
        direction_model.append([LayoutDirection.Down, _("Down")])
        direction_model.append([LayoutDirection.Left, _("Left")])
        
        #-- Create combobox --#
        direction_selector = Gtk.ComboBox.new_with_model(direction_model)
        direction_selector.set_id_column(0)
        direction_selector.set_tooltip_text(direction_tooltip)
        
        #-- Add text renderer --#
        text_renderer = Gtk.CellRendererText()
        direction_selector.pack_start(text_renderer, True)
        direction_selector.add_attribute(text_renderer, "text", 1)
        
        #-- Alignment --#
        label = _("Use own alignment")
        tooltip = _('''Whether to use a different alignment for \
the layout images than the general view alignment''')
        
        alignment_button = Gtk.CheckButton(label)
        alignment_adjust = Gtk.Adjustment(.5, 0, 1, .1, .25)
        alignment_scale = Gtk.Scale(adjustment=alignment_adjust)
        alignment_scale.set_draw_value(False)
        
        alignment_button.set_tooltip_text(tooltip)
        
        #-- Loop checkbox --#
        label = _("Loop around the album")
        loop_tooltip = _('''\
Place the first image of an album after the last, and vice versa''')
        loop_button = Gtk.CheckButton.new_with_label(label)
        loop_button.set_tooltip_text(loop_tooltip)
        
        #-- Repeat checkbox --#
        label = _("Repeat the album images")
        repeat_tooltip = _('''\
In albums with few, small images, repeat those images indefinetely''')
        repeat_button = Gtk.CheckButton.new_with_label(label)
        repeat_button.set_tooltip_text(repeat_tooltip)
        
        #-- Pixel margin --#
        margin_tooltip = _('''Margin means distance''')

        label = _("Margin between images before the center")
        margin_before_label = Gtk.Label(label)
        margin_before_adjust = Gtk.Adjustment(0, 0, 512, 8, 64)
        margin_before_entry = Gtk.SpinButton(
                                  adjustment=margin_before_adjust)
        margin_before_entry.set_tooltip_text(margin_tooltip)
        
        label = _("Margin between images after the center")
        margin_after_label = Gtk.Label(label)
        margin_after_adjust = Gtk.Adjustment(0, 0, 512, 8, 64)
        margin_after_entry = Gtk.SpinButton(adjustment=margin_after_adjust)
        margin_after_entry.set_tooltip_text(margin_tooltip)
        
        #-- Performance stuff --#
        label = _('''\
These settings affect how many images are laid out at the same time.
If you are having performance problems, consider decreasing these values.''')
        performance_label = Gtk.Label(label)
                    
        #-- Pixel target --#
        space_tooltip = _('''A good value is around twice your \
screen height or width, depending on the strip direction''')

        label = _("Pixels to fill before the center")
        space_before_label = Gtk.Label(label)
        space_before_entry, space_before_adjust = widgets.SpinAdjustment(
             0, 0, 8192, 32, 256, align=True,
         )
        space_before_entry.set_tooltip_text(space_tooltip)
        
        label = _("Pixels to fill after the center")
        space_after_label = Gtk.Label(label)
        space_after_entry, space_after_adjust = widgets.SpinAdjustment(
            0, 0, 8192, 32, 256, align=True,
        )
        space_after_entry.set_tooltip_text(space_tooltip)
        
        # Count limits
        limits_tooltip = _('''\
This is only useful if the images being laid out \
are too small to breach the pixel count limit''')
                    
        label = _("Image limit before the center")
        limit_before_label = Gtk.Label(label)
        limit_before_entry, limit_before_adjust = widgets.SpinAdjustment(
            0, 0, 512, 1, 10, align=True)
        limit_before_entry.set_tooltip_text(limits_tooltip)
        
        label = _("Image limit after the center")
        limit_after_label = Gtk.Label(label)
        limit_after_entry, limit_after_adjust = widgets.SpinAdjustment(
            0, 0, 512, 1, 10, align=True)
        limit_after_entry.set_tooltip_text(limits_tooltip)
        
        # Bind properties
        direction_selector.connect(
            "changed", self._refresh_marks, alignment_scale)
        utility.Bind(self.layout,
            ("direction", direction_selector, "active-id"),
            ("own-alignment", alignment_button, "active"),
            ("alignment", alignment_adjust, "value"),
            ("loop", loop_button, "active"),
            ("repeat", repeat_button, "active"),
            ("margin-before", margin_before_adjust, "value"),
            ("margin-after", margin_after_adjust, "value"),
            ("limit-before", limit_before_adjust, "value"),
            ("limit-after", limit_after_adjust, "value"),
            ("space-before", space_before_adjust, "value"),
            ("space-after", space_after_adjust, "value"),
            ("own-alignment", alignment_scale, "sensitive"),
            bidirectional=True, synchronize=True
        )
        
        # Add tabs, pack lines
        def add_tab(self, label):
            gtk_label = Gtk.Label(label)
            box = widgets.Stack()
            box_pad = widgets.PadNotebookContent(box)
            self.append_page(box_pad, gtk_label)
            return box
        
        left_aligned_labels = [
            direction_label,
            margin_before_label, margin_after_label,
            performance_label,
            space_before_label, space_after_label,
            limit_before_label, limit_after_label]
            
        for label in left_aligned_labels:
            label.set_alignment(0, .5)
            
        direction_label.set_hexpand(True)
        space_before_label.set_hexpand(True)
        performance_label.set_line_wrap(True)
        
        appearance_grid = widgets.Grid(
            (direction_label, direction_selector),
            (alignment_button, alignment_scale)
        )
        
        appearance_grid.attach(Gtk.Separator(), 0, 2, 2, 1)
        widgets.Grid(
            (margin_before_label, margin_before_entry),
            (margin_after_label, margin_after_entry),
            grid=appearance_grid, start_row=3
        )
        
        appearance_grid.attach(Gtk.Separator(), 0, 5, 2, 1)
        loop_line = widgets.Line(loop_button, repeat_button)
        appearance_grid.attach(loop_line, 0, 6, 2, 1)
        
        performance_grid = widgets.Grid()
        performance_grid.attach(performance_label, 0, 0, 2, 1)
        
        performance_grid.attach(Gtk.Separator(), 0, 1, 2, 1)
        widgets.Grid(
            (space_before_label, space_before_entry),
            (space_after_label, space_after_entry),
            grid=performance_grid, start_row=2,
        )
        
        performance_grid.attach(Gtk.Separator(), 0, 4, 2, 1)
        widgets.Grid(
            (limit_before_label, limit_before_entry),
            (limit_after_label, limit_after_entry),
            grid=performance_grid, start_row=5,
        )
        
        appearance_pad = widgets.PadNotebookContent(appearance_grid)
        performance_pad = widgets.PadNotebookContent(performance_grid)
            
        label = _("Appearance")
        appearance_label = Gtk.Label(label)
        self.append_page(appearance_pad, appearance_label)
        
        label = _("Performance")
        performance_label = Gtk.Label(label)
        self.append_page(performance_pad, performance_label)
        
        self.show_all()
        
    def _refresh_marks(self, combobox, scale):
        scale.clear_marks()
        active_id = combobox.get_active_id()
        if active_id in ("left", "right"):
            scale.add_mark(0, Gtk.PositionType.BOTTOM, _("Top"))
            scale.add_mark(.5, Gtk.PositionType.BOTTOM, _("Middle"))
            scale.add_mark(1, Gtk.PositionType.BOTTOM, _("Bottom"))
                
        else:
            scale.add_mark(0, Gtk.PositionType.BOTTOM, _("Left"))
            scale.add_mark(.5, Gtk.PositionType.BOTTOM, _("Center"))
            scale.add_mark(1, Gtk.PositionType.BOTTOM, _("Right"))


class BuiltInLayouts(extending.ComponentPackage):
    def add_on(self, app):
        components = app.components
        
        # Add settings
        app.settings.get_groups("layout", "image-strip", create=True)
        
        layout_options = [
            SingleImageLayoutOption(),
            ImageStripLayoutOption()
        ]
        
        LAYOUT_OPTION_CATEGORY = extending.LayoutOption.CATEGORY
        for a_layout_option in layout_options:
            components.add(LAYOUT_OPTION_CATEGORY, a_layout_option)

extending.LoadedComponentPackages["laying"] = BuiltInLayouts()
