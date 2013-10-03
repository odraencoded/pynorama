''' navigation.py defines viewing.py related navigation. '''

''' ...And this file is part of Pynorama.
    
    Pynorama is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    Pynorama is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    
    You should have received a copy of the GNU General Public License
    along with Pynorama. If not, see <http://www.gnu.org/licenses/>. '''

from gi.repository import Gtk, Gdk, GLib, GObject
from gettext import gettext as _
import math, time
import point

class MouseAdapter(GObject.GObject):
    ''' Adapts a widget mouse events '''
    EventMask = (
        Gdk.EventMask.KEY_PRESS_MASK |
        Gdk.EventMask.KEY_RELEASE_MASK |
        Gdk.EventMask.BUTTON_PRESS_MASK |
        Gdk.EventMask.BUTTON_RELEASE_MASK |
        Gdk.EventMask.SCROLL_MASK |
        Gdk.EventMask.SMOOTH_SCROLL_MASK |
        Gdk.EventMask.ENTER_NOTIFY_MASK |
        Gdk.EventMask.POINTER_MOTION_MASK |
        Gdk.EventMask.POINTER_MOTION_HINT_MASK
    )
    
    ModifierKeys = (
        Gdk.ModifierType.SHIFT_MASK |
        Gdk.ModifierType.CONTROL_MASK |
        Gdk.ModifierType.MOD1_MASK
    )
    
    # According to the docs, Gtk uses +10 for resizing and +20 for redrawing
    # +15 should dispatch events after resizing and before redrawing
    # TODO: Figure out whether that is a good idea
    IdlePriority = GLib.PRIORITY_HIGH_IDLE + 15
    
    __gsignals__ = {
        "motion" : (GObject.SIGNAL_RUN_FIRST, None, [object, object]),
        "drag" : (GObject.SIGNAL_RUN_FIRST, None, [object, object, int]),
        "pression" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
        "click" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
        "scroll" : (GObject.SIGNAL_RUN_FIRST, None, [object, object]),
        "start-dragging" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
        "stop-dragging" : (GObject.SIGNAL_RUN_FIRST, None, [object, int]),
    }
    
    def __init__(self, widget=None):
        GObject.GObject.__init__(self)
        
        self.__from_point = None
        self.__pressure = dict()
        self.__widget = None
        
        self.__delayed_motion_id = None
        self.__widget_handler_ids = None
        self.__ice_cubes = 0
        self.__motion_from_outside = 2
        self.__pressure_from_outside = True
        
        if widget:
            self.set_widget(widget)
    
    def get_widget(self):
        return self.__widget
        
    def set_widget(self, widget):
        if self.__widget != widget:
            if self.__widget:
                self.__pressure.clear()
                
                for a_handler_id in self.__widget_handler_ids:
                    self.__widget.disconnect(a_handler_id)
                self.__widget_handler_ids = None
                
                if self.__delayed_motion_id:
                    GLib.source_remove(self.__delayed_motion_id)
                    self.__delayed_motion_id = None
                
            self.__widget = widget
            if widget:            
                widget.add_events(MouseAdapter.EventMask)
                connect = widget.connect
                self.__widget_handler_ids = [
                    connect("key-press-event", self._key_press),
                    connect("key-release-event", self._key_release),
                    connect("button-press-event", self._button_press),
                    connect("button-release-event", self._button_release),
                    connect("scroll-event", self._mouse_scroll),
                    connect("enter-notify-event", self._mouse_enter),
                    connect("motion-notify-event", self._mouse_motion),
                ]
                
    widget = GObject.Property(get_widget, set_widget, type=Gtk.Widget)
    keys = GObject.Property(type=int, default=0)
    
    # icy-wut-i-did-thaw
    @property
    def is_frozen(self):
        return self.__ice_cubes > 0
        
    def freeze(self):
        self.__ice_cubes += 1
        
    def thaw(self):
        self.__ice_cubes -= 1
    
    def is_pressed(self, button=None):
        return bool(self.__pressure if button is None \
                    else self.__pressure.get(button, 0))
    
    
    # begins here the somewhat private functions
    def _update_keys(self, mask):
        modifier_keys = mask & MouseAdapter.ModifierKeys
        if modifier_keys != self.keys:
            self.keys = modifier_keys
        
        
    def _key_press(self, widget, data, *other_data):
        self._update_keys(data.state)
        
        
    def _key_release(self, widget, data, *other_data):
        self._update_keys(data.state)
        
    
    def _button_press(self, widget, data):
        self.__pressure.setdefault(data.button, 1)
        self._update_keys(data.state)
        if not self.is_frozen:
            point = data.x, data.y
            self.emit("pression", point, data.button)
        
        
    def _button_release(self, widget, data):
        self._update_keys(data.state)
        if data.button in self.__pressure:
            if not self.is_frozen:
                button_pressure = self.__pressure.get(data.button, 0)
                if button_pressure:
                    point = data.x, data.y
                    if button_pressure == 2:
                        self.emit("stop-dragging", point, data.button)
                    
                    self.emit("click", point, data.button)
                
            del self.__pressure[data.button]
            
            
    def _mouse_scroll(self, widget, data):
        self._update_keys(data.state)
        if not self.is_frozen:
            point = data.x, data.y
            # I don't have one of those cool mice with smooth scrolling
            got_delta, xd, yd = data.get_scroll_deltas()
            if not got_delta:
                # So I'm not sure this is how it maps
                got_direction, direction = data.get_scroll_direction()
                if got_direction:
                    xd, yd = [
                        (0, -1), (0, 1),
                        (-1, 0), (1, 0)
                    ][int(data.direction)] # it is [Up, right, down, left]
                    got_delta = True
            
            if got_delta:
                self.emit("scroll", point, (xd, yd))
    
    
    def _mouse_enter(self, *data):
        self.__motion_from_outside = 2
        if not self.__pressure:
            self.__pressure_from_outside = True
            
                        
    def _mouse_motion(self, widget, data):
        self._update_keys(data.state)
        # Motion events are handled idly
        self.__current_point = data.x, data.y
        if not self.__delayed_motion_id:
            if not self.__from_point:
                self.__from_point = self.__current_point
            
            if self.__motion_from_outside:
                self.__motion_from_outside -= 1
                if not self.__motion_from_outside:
                    self.__pressure_from_outside = False
            
            self.__delayed_motion_id = GLib.idle_add(
                self.__delayed_motion, widget,
                priority=MouseAdapter.IdlePriority
            )
    
    
    def __delayed_motion(self, widget):
        self.__delayed_motion_id = None
        
        if not self.is_frozen:
            # You got to love tuple comparation
            if self.__from_point != self.__current_point:
                if not self.__pressure_from_outside:
                    for button, pressure in self.__pressure.items():
                        if pressure == 1:
                            self.__pressure[button] = 2
                            self.emit(
                                "start-dragging", self.__current_point, button
                            )
                        
                        if pressure:
                            self.emit("pression", self.__current_point, button)
                        
                if not self.__motion_from_outside:
                    self.emit(
                        "motion", self.__current_point, self.__from_point
                    )
                    
                for button, pressure in self.__pressure.items():
                    if pressure == 2:
                        self.emit(
                            "drag", self.__current_point,
                            self.__from_point, button
                        )
                
        self.__from_point = self.__current_point
        return False
    
class MetaMouseHandler(GObject.Object):
    ''' Handles mouse events from mouse adapters for mouse handlers '''
    __gsignals__ = {
        "handler-added" : (GObject.SIGNAL_ACTION, None, [object]),
        "handler-removed" : (GObject.SIGNAL_ACTION, None, [object]),
    }
    
    
    # It's So Meta Even This Acronym
    def __init__(self):
        GObject.Object.__init__(self)
        
        self._handlers_data = dict()
        self._adapters_data = dict()
        # These are sets of different kinds of mouse handlers
        self._pression_handlers = set()
        self._hovering_handlers = set()
        self._dragging_handlers = set()
        self._scrolling_handlers = set()
        # This is a button/mouse handler set
        self._button_handlers = dict()
        # This is a key modifier/mouse handler set
        self._keys_handlers = dict()
    
    
    def __getitem__(self, handler):
        return self._handlers_data[handler]
    
    
    def add(self, handler, button=0, keys=0):
        ''' Adds a handler to be handled '''
        if not handler in self._handlers_data:
            handler_data = MouseHandlerBinding()
            handler_data.connect(
                "notify::button",
                self._changed_handler_data_button, handler
            )
            handler_data.connect(
                "notify::keys",
                self._changed_handler_data_key, handler
            )
            
            self._handlers_data[handler] = handler_data
            for a_handler_set in self._get_handler_sets(handler):
                a_handler_set.add(handler)
            
            if button:
                handler_data.button = button
            handler_data.keys = keys
            
            self.emit("handler-added", handler)
            
            return handler_data
    
    
    def remove(self, handler):
        ''' Removes a handler to be handled '''
        handler_data = self._handlers_data.pop(handler, None)
        if handler_data:
            for an_adapter_data in self._adapters_data.values():
                an_adapter_data.handlers_data.pop(handler, None)
            
            for handler_set in self._get_handler_sets(handler):
                handler_set.discard(handler)
            
            self._remove_handler_from_sets_dict(self._button_handlers, handler)
            self._remove_handler_from_sets_dict(self._keys_handlers, handler)
            
        handler_data.emit("removed")
        self.emit("handler-removed", handler)
    
    
    def get_handlers(self):
        ''' Returns an iterator for the currently added handlers '''
        yield from self._handlers_data.keys()
    
    
    def _changed_handler_data_button(self, handler_data, spec, handler):
        self._remove_handler_from_sets_dict(self._button_handlers, handler)
        
        # Add handler to its button set
        button = handler_data.button
        try:
            button_set = self._button_handlers[button]
            
        except KeyError:
            self._button_handlers[button] = button_set = set()
            
        button_set.add(handler)
    
    
    def _changed_handler_data_key(self, handler_data, spec, handler):
        self._remove_handler_from_sets_dict(self._keys_handlers, handler)
        
        # Add handler to its keys set
        keys = handler_data.keys
        try:
            keys_set = self._keys_handlers[keys]
        
        except KeyError:
            self._keys_handlers[keys] = keys_set = set()
            
        keys_set.add(handler)
    
    
    def _remove_handler_from_sets_dict(self, dictionary, handler):
        ''' Utility for removing a handler from all sets in a dictionary and
            then removing the empty sets '''
        # Remove handler from any ditionary sets
        empty_set_keys = []
        for a_key, a_handler_set in dictionary.items():
            a_handler_set.discard(handler)
            if not a_handler_set:
                empty_set_keys.append(a_key)
        
        # Remove empty sets
        for a_key in empty_set_keys:
            del dictionary[a_key]
    
    
    def _get_handler_sets(self, handler):
        if handler.handles(MouseEvents.Scrolling):
            yield self._scrolling_handlers
            
        if handler.handles(MouseEvents.Pressing):
            yield self._pression_handlers
            
        if handler.handles(MouseEvents.Hovering):
            yield self._hovering_handlers
            
        if handler.handles(MouseEvents.Dragging):
            yield self._dragging_handlers
    
    
    def attach(self, adapter):
        ''' Attach itself to a mouse adapter '''
        if not adapter in self._adapters_data:
            signals = [
                adapter.connect("motion", self._motion),
                adapter.connect("pression", self._pression),
                adapter.connect("scroll", self._scroll),
                adapter.connect("start-dragging", self._start_dragging),
                adapter.connect("drag", self._drag),
                adapter.connect("stop-dragging", self._stop_dragging),
                adapter.connect("notify::keys", self._keys_changed),
            ]
            
            self._adapters_data[adapter] = MouseAdapterData(signals)
    
    
    def detach(self, adapter):
        ''' Detach itself from a mouse a adapter '''
        adapter_data = self._adapters_data.pop(adapter, None)
        if adapter_data:
            for a_signal in adapter_data.signals:
                adapter.disconnect(a_signal)
    
    
    def _overlap_handler_sets(self, base_set, keys, button=None):
        if not base_set:
            # Quickly return empty base sets
            return base_set
        
        
        # If there are not handlers with "keys" keys we default to keys=0        
        try:
            keys_set = self._keys_handlers[keys]
            
        except KeyError:
            keys_set = self._keys_handlers.get(0, set())
            
        result_set = base_set & keys_set
        
        # Overlapping the button set if any
        if button is not None:
            try:
                button_handlers = self._button_handlers[button]
            
            except KeyError:
                result_set = set()
                
            else:
                result_set &= button_handlers
        
        return result_set
    
    
    def _basic_event_dispatch(
        self, adapter, event_handlers, function_name, *params
    ):
        # This is an abomination made because all event methods do this
        if event_handlers:
            widget = adapter.get_widget()
            handler_params = (widget, ) + params
            handlers_data = self._adapters_data[adapter].handlers_data
            
            for a_handler in event_handlers:
                function = getattr(a_handler, function_name)
            
                # This is the custom data returned by the handler
                a_handler_data = handlers_data.get(a_handler, None)
                a_handler_data = function(
                    *(handler_params + (a_handler_data,))
                )
                if a_handler_data:
                    handlers_data[a_handler] = a_handler_data
    
    
    def _scroll(self, adapter, point, direction):
        active_handlers = self._overlap_handler_sets(
            self._scrolling_handlers, adapter.keys,
        )
        self._basic_event_dispatch(
            adapter, active_handlers, "scroll", point, direction
        )
    
    
    def _motion(self, adapter, to_point, from_point):
        active_handlers = self._overlap_handler_sets(
            self._hovering_handlers, adapter.keys,
        )
        if active_handlers:
            # If any button handlers are to be activated then this
            # is not a propert "hovering" event
            for a_button, a_button_set in self._button_handlers.items():
                if a_button_set and adapter.is_pressed(a_button):
                    break
            else:
                # This only happens when there are no buttons pressed or
                # when the buttons pressed have no handlers bound to them
                self._basic_event_dispatch(
                    adapter, active_handlers, "hover", to_point, from_point
                )
    
    
    def _pression(self, adapter, point, button):
        active_handlers = self._overlap_handler_sets(
            self._pression_handlers, adapter.keys, button=button
        )
        self._basic_event_dispatch(
            adapter, active_handlers, "press", point
        )
    
    
    def _start_dragging(self, adapter, point, button):
        adapter_data = self._adapters_data[adapter]
        adapter_data.drag_keys_changed = False
        
        active_handlers = self._overlap_handler_sets(
            self._dragging_handlers, adapter.keys, button=button
        )
        self._basic_event_dispatch(
            adapter, active_handlers, "start_dragging", point
        )
        
        adapter_data.handlers_dragging = active_handlers
    
    
    def _drag(self, adapter, to_point, from_point, button):
        adapter_data = self._adapters_data[adapter]
        handlers_dragging = adapter_data.handlers_dragging
        
        # if the modifier keys used in dragging changedm we stop the 
        # current dragging handlers and start dragging again with the new keys
        if adapter_data.drag_keys_changed:
            # Get the dragging handlers that fit the current set of keys
            active_handlers = self._overlap_handler_sets(
                self._dragging_handlers, adapter.keys, button=button
            )
            
            adapter_data.drag_keys_changed = False
            adapter_data.handlers_dragging = set()
            
            # Get the set of handlers that will not remain active after the
            # modifier keys have been changed and call stop_dragging on them
            old_dragging_handlers = handlers_dragging - active_handlers
            self._basic_event_dispatch(
                adapter, old_dragging_handlers, "stop_dragging", from_point
            )
            
            # start_dragging the set that hasn't started dragging yet
            new_dragging_handlers = active_handlers - handlers_dragging
            self._basic_event_dispatch(
                adapter, new_dragging_handlers, "start_dragging", from_point
            )
            adapter_data.handlers_dragging = active_handlers
        
        else:
            active_handlers = handlers_dragging
            
        self._basic_event_dispatch(
            adapter, active_handlers, "drag", to_point, from_point
        )
    
    
    def _stop_dragging(self, adapter, point, button):
        adapter_data = self._adapters_data[adapter]
        
        active_handlers = adapter_data.handlers_dragging
        adapter_data.handlers_dragging = set()
        
        self._basic_event_dispatch(
            adapter, active_handlers, "stop_dragging", point
        )
    
    
    def _keys_changed(self, adapter, *data):
        self._adapters_data[adapter].drag_keys_changed = True


class MouseAdapterData:
    ''' MetaMouseHandler data associated to an adapter '''
    
    def __init__(self, signals):
        self.signals = signals
        
        # Data returned by a handler method
        self.handlers_data = dict()
        
        # A set of handlers that start(ed)_dragging but didn't finish_dragging
        self.handlers_dragging = set()
        self.drag_keys_changed = False


class MouseHandlerBinding(GObject.Object):
    ''' Represents a condition required in order to activate a MouseHandler '''
    __gsignals__ = {
        "removed" : (GObject.SIGNAL_ACTION, None, []),
    }
    
    def __init__(self):
        GObject.Object.__init__(self)
        notify_keys = lambda s, d: s.notify("keys")
        self.connect("notify::control-key", notify_keys)
        self.connect("notify::shift-key", notify_keys)
        self.connect("notify::alt-key", notify_keys)
    
    
    def get_keys(self):
        result = 0
        if self.control_key:
            result |= Gdk.ModifierType.CONTROL_MASK
        if self.shift_key:
            result |= Gdk.ModifierType.SHIFT_MASK
        if self.alt_key:
            result |= Gdk.ModifierType.MOD1_MASK
        return result
    
    
    def set_keys(self, value):
        self.freeze_notify()
        control_key = bool(value & Gdk.ModifierType.CONTROL_MASK)
        shift_key = bool(value & Gdk.ModifierType.SHIFT_MASK)
        alt_key = bool(value & Gdk.ModifierType.MOD1_MASK)
        
        if control_key != self.control_key:
            self.control_key = control_key
        if shift_key != self.shift_key:
            self.shift_key = shift_key
        if alt_key != self.alt_key:
            self.alt_key = alt_key
        
        self.thaw_notify()
    
    button = GObject.Property(type=int, default=0)
    keys = GObject.Property(get_keys, set_keys, type=int)
    
    control_key = GObject.Property(type=bool, default=False)
    shift_key = GObject.Property(type=bool, default=False)
    alt_key = GObject.Property(type=bool, default=False)


class MouseEvents:
    Nothing   = 0b0000000
    Moving    = 0b0000011
    Hovering  = 0b0000001 # Movement without pressure
    Pressing  = 0b0010110 # Pressure regardless of movement
    Dragging  = 0b0001110 # Pressure and movement
    Clicking  = 0b0010100
    Scrolling = 0b0100000 # Handles either scrolling axes
    Rolling   = 0b1100000 # Handles both scrolling axes


class MouseHandler(GObject.Object):
    """Handles mouse events sent by MetaMouseHandler.
    
    In order to handle anything, a mouse handler must set its .events
    attribute, which should not be changed after initialization.
    
    """
    
    # The base of the totem pole
    def __init__(self, **kwargs):
        GObject.Object.__init__(self, **kwargs)
        self.events = MouseEvents.Nothing
        
        # These are set by the app.
        self.factory = None # The factory that made the handler
    
    # An user-set nickname for this instance
    nickname = GObject.Property(type=str)
    
    def handles(self, event_type):
        return self.events & event_type == event_type \
               if event_type != MouseEvents.Nothing \
               else not bool(self.events)
    
    
    @property
    def needs_button(self):
        ''' Returns whether this mouse handler needs a button to be pressed '''
        return bool(self.events & MouseEvents.Pressing)
    
    
    def scroll(self, widget, point, direction, data):
        ''' Handles a scroll wheel event '''
        pass
    
    
    def press(self, widget, point, data):
        ''' Handles the mouse being pressed somewhere '''
        pass
    
    
    def hover(self, widget, to_point, from_point, data):
        ''' Handles the mouse just hovering around '''
        pass
    
    
    def start_dragging(self, widget, point, data):
        ''' Setup dragging variables '''
        pass
    
    
    def drag(self, widget, to_point, from_point, data):
        ''' Drag to point A from B '''
        pass
    
    
    def stop_dragging(self, widget, point, data):
        ''' Finish dragging '''
        pass
    
    
class PivotMode:
    Mouse = 0
    Alignment = 1
    Fixed = 2
    
    
class MouseHandlerPivot(GObject.Object):
    ''' An utility class for mouse mechanisms which need a pivot point '''
    def __init__(self, **kwargs):
        GObject.Object.__init__(self, **kwargs)
        notify_fixed_point = lambda s, w: s.notify("fixed-point")
        self.connect("notify::fixed-x", notify_fixed_point)
        self.connect("notify::fixed-y", notify_fixed_point)
    
    
    def get_fixed_point(self):
        return self.fixed_x, self.fixed_y
    
    
    def set_fixed_point(self, value):
        self.freeze_notify()
        self.fixed_x, self.fixed_y = value
        self.thaw_notify()
    
    
    mode = GObject.Property(type=int, default=PivotMode.Mouse)
    # Fixed pivot point
    fixed_x = GObject.Property(type=float, default=.5)
    fixed_y = GObject.Property(type=float, default=.5)
    fixed_point = GObject.Property(
        get_fixed_point, set_fixed_point, type=object
    )
    
    
    def convert_point(self, view, pointer):
        ''' Returns a pivot point based on a view widget and
            the mouse pointer coordinates '''
        if self.mode == PivotMode.Mouse:
            result = pointer
        else:
            w, h = view.get_allocated_width(), view.get_allocated_height()
            
            if self.mode == PivotMode.Alignment:
                sx, sy = view.alignment_point
            else:
                sx, sy = self.fixed_point
                
            result = sx * w, sy * h
        return result
        
        
class HoverAndDragHandler(MouseHandler):
    ''' Pans a view on mouse dragging, or on mouse hovering '''
    
    def __init__(
        self, drag=False, speed=-1.0, relative_speed=True
    ):
        MouseHandler.__init__(self)
        
        if drag:
            self.events = MouseEvents.Dragging
        
        else:
            self.events = MouseEvents.Hovering
            
        self.speed = speed
        self.relative_speed = relative_speed
    
    speed = GObject.Property(type=float, default=1)
    relative_speed = GObject.Property(type=bool, default=True)
    
    def hover(self, view, to_point, from_point, data):
        shift = point.subtract(to_point, from_point)
        
        scale = self.speed
        if self.relative_speed:
            scale /= view.magnification
        
        scaled_shift = point.scale(shift, scale)
        view.pan(scaled_shift)
    
    
    def start_dragging(self, view, *etc):
        fleur_cursor = Gdk.Cursor(Gdk.CursorType.FLEUR)
        view.get_window().set_cursor(fleur_cursor)
    
    
    drag = hover # lol.
    
    
    def stop_dragging(self, view, *etc):
        view.get_window().set_cursor(None)


class MapHandler(MouseHandler):
    ''' Adjusts a view to match a point inside.
        In it's most basic way for "H" being a point in the widget,
        "C" being the resulting adjustment, "B" being the widget size and
        "S" being the boundaries of the viewing widget model: C = H / B * S '''
    def __init__(self, margin=32, mapping_mode="proportional"):
        MouseHandler.__init__(self)
        self.events = MouseEvents.Pressing
        self.mapping_mode = mapping_mode
        self.margin = margin
        
    def press(self, view, point, data):
        # Clamp mouse pointer to map
        rx, ry, rw, rh = self.get_map_rectangle(view)
        mx, my = point
        x = max(0, min(rw, mx - rx))
        y = max(0, min(rh, my - ry))
        # The adjustments
        hadjust = view.get_hadjustment()
        vadjust = view.get_vadjustment()
        # Get content bounding box
        full_width = hadjust.get_upper() - hadjust.get_lower()
        full_height = vadjust.get_upper() - vadjust.get_lower()
        full_width -= hadjust.get_page_size()
        full_height -= vadjust.get_page_size()
        # Transform x and y to picture "adjustment" coordinates
        tx = x / rw * full_width + hadjust.get_lower()
        ty = y / rh * full_height + vadjust.get_lower()
        view.adjust_to(tx, ty)
        
    def get_map_rectangle(self, view):
        allocation = view.get_allocation()
        
        allocation.x = allocation.y = self.margin
        allocation.width -= self.margin * 2
        allocation.height -= self.margin * 2
        
        if allocation.width <= 0:
            diff = 1 - allocation.width
            allocation.width += diff
            allocation.x -= diff / 2
            
        if allocation.height <= 0:
            diff = 1 - allocation.height
            allocation.height += diff
            allocation.y -= diff / 2
        
        if self.mapping_mode == "square":
            if allocation.width > allocation.height:
                smallest_side = allocation.height
            else:
                smallest_side = allocation.width
            
            half_width_diff = (allocation.width - smallest_side) / 2
            half_height_diff = (allocation.height - smallest_side) / 2
            
            return (allocation.x + half_width_diff,
                    allocation.y + half_height_diff,
                    allocation.width - half_width_diff * 2,
                    allocation.height - half_height_diff * 2)
            
        elif self.mapping_mode == "proportional":
            hadjust = view.get_hadjustment()
            vadjust = view.get_vadjustment()
            full_width = hadjust.get_upper() - hadjust.get_lower()
            full_height = vadjust.get_upper() - vadjust.get_lower()
            fw_ratio = allocation.width / full_width
            fh_ratio = allocation.height / full_height
                        
            if fw_ratio > fh_ratio:
                smallest_ratio = fh_ratio
            else:
                smallest_ratio = fw_ratio
            
            transformed_width = smallest_ratio * full_width
            transformed_height = smallest_ratio * full_height
            
            half_width_diff = (allocation.width - transformed_width) / 2
            half_height_diff = (allocation.height - transformed_height) / 2
            
            return (allocation.x + half_width_diff,
                    allocation.y + half_height_diff,
                    allocation.width - half_width_diff * 2,
                    allocation.height - half_height_diff * 2)
            
        else:
            return (allocation.x, allocation.y,
                    allocation.width, allocation.height)
        
class SpinHandler(MouseHandler):
    ''' Spins a view '''
    
    SpinThreshold = 5
    SoftRadius = 25
    
    
    def __init__(self, frequency=1, pivot=None):
        MouseHandler.__init__(self)
        
        self.events = MouseEvents.Dragging
        
        self.frequency = frequency
        
        if pivot:
            self.pivot = pivot
            
        else:
            self.pivot = MouseHandlerPivot()
    
    
    # Number of complete turns in the view per revolution around the pivot
    frequency = GObject.Property(type=float, default=1)
    
    def start_dragging(self, view, point, data):
        widget_pivot = self.pivot.convert_point(view, point)
        
        return widget_pivot, view.get_pin(widget_pivot)
    
    
    def drag(self, view, to_point, from_point, data):
        pivot, pin = data
        
        # Get vectors from the pivot
        (tx, ty), (fx, fy), (px, py) = to_point, from_point, pivot
        tdx, tdy = tx - px, ty - py
        fdx, fdy = fx - px, fy - py
        
        # Get rotational delta, multiply it by frequency
        ta = math.atan2(tdy, tdx) / math.pi * 180
        fa = math.atan2(fdy, fdx) / math.pi * 180
        rotation_effect = (ta - fa) * self.frequency
        
        # Modulate degrees
        rotation_effect %= 360 if rotation_effect >= 0 else -360
        if rotation_effect > 180:
            rotation_effect -= 360
        if rotation_effect < -180:
            rotation_effect += 360 
            
        # Thresholding stuff
        square_distance = tdx ** 2 + tdy ** 2
        if square_distance > SpinHandler.SpinThreshold ** 2:
            # Falling out stuff
            square_soft_radius = SpinHandler.SoftRadius ** 2
            if square_distance < square_soft_radius:
                fallout_effect = square_distance / square_soft_radius
                rotation_effect *= fallout_effect
            
            # Changing the rotation(finally)
            view.rotation = (view.rotation + rotation_effect) % 360
            # Anchoring!!!
            view.adjust_to_pin(pin)
            
        return data


class StretchHandler(MouseHandler):
    ''' Stretches/shrinks a view '''
    
    MinDistance = 10
    
    def __init__(self, pivot=None):
        MouseHandler.__init__(self)
        self.events = MouseEvents.Dragging
        
        if pivot:
            self.pivot = pivot
        else:
            self.pivot = MouseHandlerPivot(mode=PivotMode.Fixed)
    
        
    def start_dragging(self, view, start_point, data):
        widget_size = view.get_widget_size()
        widget_pivot = self.pivot.convert_point(view, start_point)
        
        start_diff = point.subtract(start_point, widget_pivot)
        distance = max(StretchHandler.MinDistance, point.length(start_diff))
        
        zoom = view.magnification
        zoom_ratio = zoom / distance
        
        return zoom_ratio, widget_pivot, view.get_pin(widget_pivot)
    
    
    def drag(self, view, to_point, from_point, data):
        zoom_ratio, widget_pivot, pin = data
        
        # Get vectors from the pivot
        point_diff = point.subtract(to_point, widget_pivot)
        distance = max(StretchHandler.MinDistance, point.length(point_diff))
        
        new_zoom = distance * zoom_ratio
        
        view.magnification = new_zoom
        view.adjust_to_pin(pin)
        
        return data


class ScrollHandler(MouseHandler):
    ''' Scrolls a view '''
    
    def __init__(self, inverse=None, **kwargs):
        MouseHandler.__init__(self, **kwargs)
        self.events = MouseEvents.Rolling
        
        if inverse:
            self.inverse_horizontal, self.inverse_vertical = inverse
    
    # Scrolling speed
    pixel_speed = GObject.Property(type=int, default=300)
    relative_speed = GObject.Property(type=float, default=.3)
    
    # If this is true, speed is scaled to the view dimensions
    relative_scrolling = GObject.Property(type=bool, default=True)
    
    # Inverse horizontal and vertical axis, this happens after everything else
    inverse_horizontal = GObject.Property(type=bool, default=False)
    inverse_vertical = GObject.Property(type=bool, default=False)
    
    # Whether to swap axes
    swap_axes = GObject.Property(type=bool, default=False)
    
    # Rotate scrolling shift with view rotation
    rotate = GObject.Property(type=bool, default=False)
    
    
    def scroll(self, view, position, direction, data):
        xd, yd = direction
        view_size = view.get_view()[2:]
        if self.relative_scrolling:
            scaled_view_size = point.scale(view_size, self.relative_speed)
            xd, yd = point.multiply((xd, yd), scaled_view_size)
            
        else:
            xd, yd = point.scale((xd, yd), self.pixel_speed)
            
        if self.rotate:
            xd, yd = point.spin((xd, yd), view.get_rotation_radians())
            scroll_along_size = view.get_frames_outline()[2:]
            
        else:
            scroll_along_size = view.get_boundary()[2:]
            
        if self.swap_axes:
            xd, yd = yd, xd
            
        view.pan((xd, yd))


class ZoomHandler(MouseHandler):
    ''' Zooms a view '''
    
    def __init__(
        self, effect=2, minify_anchor=None, magnify_anchor=None,
        horizontal=False, inverse=False
    ):
        MouseHandler.__init__(self)
        self.events = MouseEvents.Scrolling
        
        if not minify_anchor:
            minify_anchor = MouseHandlerPivot(mode=PivotMode.Mouse)
            
        if not magnify_anchor:
            magnify_anchor = MouseHandlerPivot(mode=PivotMode.Mouse)
            
        self.minify_anchor = minify_anchor
        self.magnify_anchor = magnify_anchor
        
        self.effect = effect
        self.inverse = inverse
        self.horizontal = horizontal
    
    
    effect = GObject.Property(type=float, default=2)
    inverse = GObject.Property(type=bool, default=False)
    horizontal = GObject.Property(type=bool, default=False)
    
    
    def scroll(self, view, point, direction, data):
        dx, dy = direction
        delta = (dx if self.horizontal else dy) * -1
        
        if delta and self.effect:
            if self.inverse:
                power = self.effect ** -delta
            else:
                power = self.effect ** delta
            
            pivot = self.minify_anchor if power < 0 else self.magnify_anchor
            anchor_point = pivot.convert_point(view, point)
            
            pin = view.get_pin(anchor_point)
            view.magnification *= power
            view.adjust_to_pin(pin)


class GearHandler(MouseHandler):
    ''' Spins a view with each scroll tick '''
    
    def __init__(self, pivot=None, horizontal=False, effect=30):
        MouseHandler.__init__(self)
        self.events = MouseEvents.Scrolling
        
        if pivot:
            self.pivot = pivot
        else:
            self.pivot = MouseHandlerPivot()
            
        self.effect = effect
        self.horizontal = horizontal
    
    
    effect = GObject.Property(type=float, default=30)
    horizontal = GObject.Property(type=bool, default=False)
    
    
    def scroll(self, view, point, direction, data):
        dx, dy = direction
        delta = (dx if self.horizontal else dy) * -1
        
        anchor_point = self.pivot.convert_point(view, point)
            
        pin = view.get_pin(anchor_point)
        view.rotate(self.effect * delta)
        view.adjust_to_pin(pin)
        
#-- Factories down this line --#

import extending, utility
from gettext import gettext as _

def GetPivotSettings(pivot):
    result = { "mode": pivot.mode }
    if pivot.mode == PivotMode.Fixed:
        result["fixed_point"] = pivot.fixed_point
        
    return result


def LoadPivotSettings(settings):
    return MouseHandlerPivot(**settings)


class HoverAndDragHandlerSettingsWidget(Gtk.Box):
    ''' A settings widget made for a HoverMouseHandler and DragMouseHandler ''' 
    def __init__(self, handler, drag=True):
        label = _("Panning speed")
        speed_label = Gtk.Label(label)
        speed_entry, speed_adjustment = utility.SpinAdjustment(
            0, -10, 10, .1, 1, align=True, digits=2
        )
        speed_line = utility.WidgetLine(speed_label, speed_entry)
        
        speed_scale = utility.ScaleAdjustment(adjustment=speed_adjustment,
            marks=[
                (-10, _("Pan Image")), (-1, None),
                (0, _("Inertia")),
                (10, _("Pan View")), (1, None)
            ], origin=False, percent=True, absolute=True
        )
        
        label = _("Speed relative to zoom")
        speed_relative = Gtk.CheckButton(label)
        
        utility.InitWidgetStack(self, speed_line, speed_scale, speed_relative)
        
        # Bind properties
        utility.Bind(handler,
            ("speed", speed_adjustment, "value"),
            ("relative-speed", speed_relative, "active"),
            bidirectional=True, synchronize=True
        )
        
        self.show_all()


class HoverAndDragHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self, drag):
        extending.MouseHandlerFactory.__init__(self)
        
        self.drag = drag
        if drag:
            self.codename = "drag"
            
        else:
            self.codename = "hover"
        
        self.create_settings_widget = HoverAndDragHandlerSettingsWidget
    
    
    @GObject.Property
    def label(self):
        return _("Drag to Pan" if self.drag else "Move Mouse to Pan")
    
    
    def create_default(self):
        return HoverAndDragHandler(
            drag = self.drag,
            speed = -1 if self.drag else 0.2
        )
        
        
    @staticmethod
    def get_settings(handler):
        return {
            "speed": handler.speed,
            "relative_speed": handler.relative_speed
        }
    
    
    def load_settings(self, settings):
        return HoverAndDragHandler(drag=self.drag, **settings)


# TODO: Fix MapHandler for multi-image layouts and create its factory

from preferences import PointScale
class PivotedHandlerSettingsWidget:
    def __init__(self):
        self.pivot_widgets = dict()
        self.pivot_radios = dict()
    
    def create_pivot_widgets(self, pivot, anchor=False):
        if anchor:
            mouse_label = _("Use mouse pointer as anchor")
            alignment_label = _("Use view alignment as anchor")
            fixed_label = _("Use a fixed point as anchor")
            xlabel = _("Anchor X")
            ylabel = _("Anchor Y")
            
        else:
            mouse_label = _("Use mouse pointer as pivot")
            alignment_label = _("Use view alignment as pivot")
            fixed_label = _("Use a fixed point as pivot")
            xlabel = _("Pivot X")
            ylabel = _("Pivot Y")
        
        pivot_mouse = Gtk.RadioButton(label=mouse_label)
        pivot_alignment = Gtk.RadioButton(
            label=alignment_label, group=pivot_mouse
        )

        pivot_fixed = Gtk.RadioButton(label=fixed_label, group=pivot_alignment)
        xadjust = Gtk.Adjustment(.5, 0, 1, .1, .25, 0)
        yadjust = Gtk.Adjustment(.5, 0, 1, .1, .25, 0)
        point_scale = PointScale(xadjust, yadjust)
        
        fixed_point_grid, xspin, yspin = utility.PointScaleGrid(
            point_scale, xlabel, ylabel, corner=pivot_fixed
        )
        
        self.pivot_radios[pivot] = pivot_radios = {
            PivotMode.Mouse : pivot_mouse,
            PivotMode.Alignment : pivot_alignment,
            PivotMode.Fixed : pivot_fixed
        }
        self.pivot_widgets[pivot] = pivot_widgets = [
            pivot_mouse, pivot_alignment, fixed_point_grid
        ]
        
        # Bind properties
        utility.Bind(pivot,
            ("fixed-x", xadjust, "value"), ("fixed-y", yadjust, "value"),
            bidirectional=True, synchronize=True
        )
        
        fixed_widgets = [xspin, yspin, point_scale]
        utility.Bind(pivot_fixed,
            *[("active", widget, "sensitive") for widget in fixed_widgets],
            synchronize=True
        )
        
        pivot.connect("notify::mode", self._refresh_pivot_mode)
        for value, radio in pivot_radios.items():
            radio.connect("toggled", self._pivot_mode_chosen, pivot, value)
        
        self._refresh_pivot_mode(pivot)
        
        return pivot_widgets
        
    def _refresh_pivot_mode(self, pivot, *data):
        self.pivot_radios[pivot][pivot.mode].set_active(True)
    
    def _pivot_mode_chosen(self, radio, pivot, value):
        if radio.get_active() and pivot.mode != value:
            pivot.mode = value
    
    
class SpinHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        self.handler = handler
        
        # Add line for fequency
        label = _("Frequency of turns")
        frequency_label = Gtk.Label(label)
        frequency_entry, frequency_adjustment = utility.SpinAdjustment(
            1, -9, 9, .1, 1, digits=2, align=True
        )
        frequency_line = utility.WidgetLine(
            frequency_label, frequency_entry, expand=frequency_entry
        )
        
        # Get pivot widgets, pack everyting
        pivot_widgets = self.create_pivot_widgets(handler.pivot)
        utility.InitWidgetStack(self, frequency_line, *pivot_widgets)
        self.show_all()
        
        # Bind properties
        utility.Bind(handler,
            ("frequency", frequency_adjustment, "value"),
            bidirectional=True, synchronize=True
        )


class SpinHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "spin")
        self.create_default = SpinHandler
        self.create_settings_widget = SpinHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Drag to Spin")
        
        
    @staticmethod
    def get_settings(handler):
        return {
            "frequency": handler.frequency,
            "pivot": GetPivotSettings(handler.pivot)
        }
        
        
    @staticmethod
    def load_settings(settings):
        clone = dict(settings)
        pivot = LoadPivotSettings(clone.pop("pivot"))
        return SpinHandler(pivot=pivot, **clone)


class StretchHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        widgets = self.create_pivot_widgets(handler.pivot, anchor=True)
        utility.InitWidgetStack(self, *widgets[1:])
        
        self.show_all()


class StretchHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "stretch")
        self.create_default = StretchHandler
        self.create_settings_widget = StretchHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Drag to Stretch")
    
    
    @staticmethod
    def get_settings(handler):
        return GetPivotSettings(handler.pivot)
    
    
    @staticmethod
    def load_settings(settings):
        return StretchHandler(pivot=LoadPivotSettings(settings))


class ScrollHandlerSettingsWidget(Gtk.Box):
    def __init__(self, handler):
        self.handler = handler
        
        # Fixed pixel speed
        label = _("Fixed pixel scrolling speed")
        pixel_radio = Gtk.RadioButton(label=label)
        pixel_entry, pixel_adjust = utility.SpinAdjustment(
            300, 0, 9001, 20, 150, align=True
        )
        pixel_line = utility.WidgetLine(
            pixel_radio, pixel_entry, expand=pixel_entry
        )
        self.pixel_radio = pixel_radio
        
        # Relative pixel speed
        label = _("Relative percentage scrolling speed")
        relative_radio = Gtk.RadioButton(label=label, group=pixel_radio)
        relative_scale, relative_adjust = utility.ScaleAdjustment(
            1, 0, 3, .04, .5, percent=True,
            marks = [(0, _("Inertia")), (1, _("Entire Window"))]
        )
        self.relative_radio = relative_radio
        
        label = _("Inverse vertical scrolling")
        inversev = Gtk.CheckButton(label=label)
        label = _("Inverse horizontal scrolling")
        inverseh = Gtk.CheckButton(label=label)
        
        label = _("Rotate scrolling to image coordinates")
        rotate = Gtk.CheckButton(label)
        
        label = _("Swap horizontal and vertical axes")
        swap = Gtk.CheckButton(label=label)
        
        utility.InitWidgetStack(self,
            pixel_line, relative_radio, relative_scale,
            inverseh, inversev, rotate, swap
        )
        self.show_all()
        
        # Bind properties
        handler.connect("notify::relative-scrolling", self._refresh_speed_mode)
        pixel_radio.connect("toggled", self._speed_mode_chosen, False)
        relative_radio.connect("toggled", self._speed_mode_chosen, True)
        
        utility.BindSame("active", "sensitive",
            (relative_radio, relative_scale),
            (pixel_radio, pixel_entry),
            synchronize=True
        )
        utility.Bind(handler, 
            ("pixel-speed", pixel_adjust, "value"),
            ("relative-speed", relative_adjust, "value"),
            ("inverse-horizontal", inverseh, "active"),
            ("inverse-vertical", inversev, "active"),
            ("rotate", rotate, "active"),
            ("swap-axes", swap, "active"),
            bidirectional=True, synchronize=True
        )    
        self._refresh_speed_mode(handler)
    
    
    def _refresh_speed_mode(self, handler, *data):
        if handler.relative_scrolling:
            self.relative_radio.set_active(True)
        else:
            self.pixel_radio.set_active(True)
    
    
    def _speed_mode_chosen(self, radio, value):
        if radio.get_active() and self.handler.relative_scrolling != value:
            self.handler.relative_scrolling = value


class ScrollHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "scroll")
        self.create_default = ScrollHandler
        self.create_settings_widget = ScrollHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Scroll to Pan")
        
    
    @staticmethod
    def get_settings(handler):
        result = {
            "relative-scrolling" : handler.relative_scrolling,
            "inverse": (handler.inverse_horizontal, handler.inverse_vertical),
            "rotate": handler.rotate,
            "swap-axes": handler.swap_axes,
        }
        if handler.relative_scrolling:
            result["relative-speed"] = handler.relative_speed
        else:
            result["pixel-speed"] = handler.pixel_speed
        return result
    
    
    @staticmethod
    def load_settings(settings):
        return ScrollHandler(**settings)


class ZoomHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        
        # Zoom effect label, entry and invert checkbox
        label = _("Zoom effect")
        effect_label = Gtk.Label(label)
        effect_entry, effect_adjust = utility.SpinAdjustment(
            2, 1, 4, .05, .25, align=True, digits=2
        )
        label = _("Inverse effect")
        effect_inverse = Gtk.CheckButton(label)
        
        # Pack effect widgets in a line
        effect_line = utility.WidgetLine(
            effect_label, effect_entry, effect_inverse, expand=effect_entry
        )
        
        # Create magnify and minify pivot widgets in a notebook
        pivot_book = Gtk.Notebook()
        pivot_labels = (
            (handler.magnify_anchor, _("Zoom in anchor")),
            (handler.minify_anchor, _("Zoom out anchor")),
        )
        for a_pivot, a_label in pivot_labels:
            # Create anchor widgets
            a_box_widgets = self.create_pivot_widgets(a_pivot, anchor=True)
            a_box = utility.WidgetStack(*a_box_widgets)
            
            # Add widgets to notebook
            a_box_pad = utility.PadNotebookContent(a_box)
            a_tab_label = Gtk.Label(a_label)        
            pivot_book.append_page(a_box_pad, a_tab_label)
        
        # Horizontal scrolling check
        label = _("Activate with horizontal scrolling")        
        horizontal_check = Gtk.CheckButton(label)
        
        # Pack everything
        utility.InitWidgetStack(self, effect_line, pivot_book, horizontal_check)
        self.show_all()
        
        # Bind properties
        utility.Bind(handler,
            ("effect", effect_adjust, "value"),
            ("inverse", effect_inverse, "active"),
            ("horizontal", horizontal_check, "active"),
            synchronize=True, bidirectional=True
        )


class ZoomHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "zoom")
        self.create_default = ZoomHandler
        self.create_settings_widget=ZoomHandlerSettingsWidget
    
    
    @GObject.Property
    def label(self):
        return _("Scroll to Zoom")
    
    
    @staticmethod
    def get_settings(handler):
        return {
            "effect": handler.effect,
            "horizontal": handler.horizontal,
            "inverse": handler.inverse,
            "minify_anchor": GetPivotSettings(handler.minify_anchor),
            "magnify_anchor": GetPivotSettings(handler.magnify_anchor),
        }
    
    
    @staticmethod
    def load_settings(settings):
        clone = dict(settings)
        minify_anchor = LoadPivotSettings(clone.pop("minify_anchor"))
        magnify_anchor = LoadPivotSettings(clone.pop("magnify_anchor"))
        return ZoomHandler(
            minify_anchor=minify_anchor, magnify_anchor=magnify_anchor, **clone
        )


class GearHandlerSettingsWidget(Gtk.Box, PivotedHandlerSettingsWidget):
    def __init__(self, handler):
        PivotedHandlerSettingsWidget.__init__(self)
        
        # Create effect line
        label = _("Spin effect")
        effect_label = Gtk.Label(label)
        effect_entry, effect_adjust = utility.SpinAdjustment(
            30, -180, 180, 10, 60, align=True, wrap=True
        )
        effect_line = utility.WidgetLine(
            effect_label, effect_entry
        )
        
        # Create pivot point widgets
        pivot_widgets = self.create_pivot_widgets(handler.pivot)
        
        # Create horizontal scrolling checkbox
        label = _("Activate with horizontal scrolling")        
        horizontal_check = Gtk.CheckButton(label)
        
        # Pack everything
        utility.InitWidgetStack(self,
            *([effect_line] + pivot_widgets + [horizontal_check])
        )
        self.show_all()
        
        # Bind properties
        utility.Bind(handler,
            ("effect", effect_adjust, "value"),
            ("horizontal", horizontal_check, "active"),
            bidirectional=True, synchronize=True
        )


class GearHandlerFactory(extending.MouseHandlerFactory):
    def __init__(self):
        extending.MouseHandlerFactory.__init__(self, "gear")
        self.create_default = GearHandler
        self.create_settings_widget = GearHandlerSettingsWidget
        
        
    @GObject.Property
    def label(self):
        return _("Scroll to Spin")
    
    
    @staticmethod
    def get_settings(handler):
        return {
            "effect": handler.effect,
            "horizontal": handler.horizontal,
            "pivot": GetPivotSettings(handler.pivot)
        }
    
    
    @staticmethod
    def load_settings(settings):
        clone = dict(settings)
        pivot = LoadPivotSettings(clone.pop("pivot"))
        return GearHandler(pivot=pivot, **clone)


class BuiltInMouseMechanismBrands(extending.ComponentPackage):
    @staticmethod
    def add_on(app):
        components = app.components
        components.add_category(
            "mouse-mechanism-brand", "Mouse Mechanism Brand"
        )
        
        brands = [
            HoverAndDragHandlerFactory(drag=True), # drag
            HoverAndDragHandlerFactory(drag=False), # hover
            ScrollHandlerFactory(),
            SpinHandlerFactory(),
            StretchHandlerFactory(),
            ZoomHandlerFactory(),
            GearHandlerFactory(),
        ]
        for a_brand in brands:
            components.add("mouse-mechanism-brand", a_brand)
            
extending.LoadedComponentPackages.add(BuiltInMouseMechanismBrands)
