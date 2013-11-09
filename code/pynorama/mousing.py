""" mousing.py defines classes and interfaces for handling mouse events. """

""" ...And this file is part of Pynorama.
    
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

from gi.repository import Gtk, GLib, GObject
from gi.repository.Gdk import EventMask, ModifierType
from gettext import gettext as _
from . import utility, widgets
from .utility import Point

# Mask of events added to a widget attached to a MouseAdapater
MOUSE_EVENT_MASK = (
    EventMask.KEY_PRESS_MASK |
    EventMask.KEY_RELEASE_MASK |
    EventMask.BUTTON_PRESS_MASK |
    EventMask.BUTTON_RELEASE_MASK |
    EventMask.SCROLL_MASK |
    EventMask.SMOOTH_SCROLL_MASK |
    EventMask.ENTER_NOTIFY_MASK |
    EventMask.LEAVE_NOTIFY_MASK |
    EventMask.POINTER_MOTION_MASK |
    EventMask.POINTER_MOTION_HINT_MASK
)

MOUSE_MODIFIER_KEYS = (
    ModifierType.SHIFT_MASK |
    ModifierType.CONTROL_MASK |
    ModifierType.MOD1_MASK
)

# According to the docs, Gtk uses +10 for resizing and +20 for redrawing
# +15 should dispatch events after resizing and before redrawing
# TODO: Figure out whether that is a good idea
PRIORITY_MOUSE_IDLE = GLib.PRIORITY_HIGH_IDLE + 15


class MouseAdapter(GObject.GObject):
    """ Emits signals based on a widget mouse events """
    __gsignals__ = {
        "cross" : (GObject.SIGNAL_RUN_FIRST, None, [object, bool]),
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
        
        # The modifier keys in place
        self.keys = 0
        
        self._current_point = self._from_point = None
        
        # A dictionary of mouse buttons:pressure values, the pressure value
        # is 1 when a button is pressed and 2 after the idle delayed motion
        # callback that dispatches most events. It is never set to 0.
        self._pressure = dict()
        self._widget = None
        
        self._delayed_motion = utility.IdlyMethod(self._delayed_motion_cb)
        self._delayed_motion.priority = PRIORITY_MOUSE_IDLE
        # If the mouse pointer goes outside the widget this is set to 2.
        # While it is greater than zero the "motion" signal won't be emitted.
        # Basically, this means it takes two pointer coordinates samples
        # inside the widget for a motion from-point-to-point to be emitted.
        self._motion_from_outside = 2
        self._pressure_from_outside = True
        
        # This thing connects the signals of .widget
        utility.GPropertySignalsConnector(
            self, "widget", **{
                "key-press-event": self._key_press_cb,
                "key-release-event": self._key_release_cb,
                "button-press-event": self._button_press_cb,
                "button-release-event": self._button_release_cb,
                "scroll-event": self._mouse_scroll_cb,
                "enter-notify-event": self._mouse_enter_cb,
                "leave-notify-event": self._mouse_leave_cb,
                "motion-notify-event": self._mouse_motion_cb
            }
        )
        self.connect("notify::widget", self._widget_changed_cb)
        
        if widget:
            self.widget = widget
    
    
    widget = GObject.Property(type=Gtk.Widget)
    
    
    def is_pressed(self, button=None):
        """ If button is None, returns whether any button is pressed.
        Otherwise, returns whether that specific button is pressed.
        
        The button should be an integer from Gdk enumerations
        
        """
        
        return bool(
            self._pressure if button is None
            else self._pressure.get(button, 0)
        )
    
    
    # begins here the somewhat private functions
    def _update_keys(self, mask):
        """ Sets .keys to a bitmask of modifier keys """
        modifier_keys = mask & MOUSE_MODIFIER_KEYS
        if modifier_keys != self.keys:
            self.keys = modifier_keys
    
    
    def _widget_changed_cb(self, *whatever):
        widget = self.widget
        
        self._pressure.clear()
        self._delayed_motion.cancel_queue()
        self._delayed_motion.args = (widget,)
        
        if widget:
            widget.add_events(MOUSE_EVENT_MASK)
    
    
    def _key_press_cb(self, widget, data, *other_data):
        self._update_keys(data.state)
    
    
    def _key_release_cb(self, widget, data, *other_data):
        self._update_keys(data.state)
    
    
    def _button_press_cb(self, widget, data):
        self._pressure.setdefault(data.button, 1)
        self._update_keys(data.state)
        
        # Emit pression signal
        point = Point(data.x, data.y)
        self.emit("pression", point, data.button)
    
    
    def _button_release_cb(self, widget, data):
        self._update_keys(data.state)
        if data.button in self._pressure:
            button_pressure = self._pressure[data.button]
            
            # Emit signals
            point = Point(data.x, data.y)
            if button_pressure == 2:
                self.emit("stop-dragging", point, data.button)
            self.emit("click", point, data.button)
            
            del self._pressure[data.button]
    
    
    def _mouse_scroll_cb(self, widget, data):
        self._update_keys(data.state)
        # I don't have one of those cool mice with smooth scrolling
        got_delta, xd, yd = data.get_scroll_deltas()
        if not got_delta:
            # So I'm not sure this is how it maps
            got_direction, direction = data.get_scroll_direction()
            if got_direction:
                xd, yd = (
                    (0, -1), (0, 1),
                    (-1, 0), (1, 0)
                )[int(data.direction)] # it is [Up, right, down, left]
                got_delta = True
        
        if got_delta:
            self.emit("scroll", Point(data.x, data.y), Point(xd, yd))
    
    
    def _mouse_enter_cb(self, widget, data):
        self._motion_from_outside = 2
        if not self._pressure:
            self._pressure_from_outside = True
        
        self.emit("cross", Point(data.x, data.y), True)
    
    
    def _mouse_leave_cb(self, widget, data):
        self.emit("cross", Point(data.x, data.y), False)
    
    
    def _mouse_motion_cb(self, widget, data):
        self._update_keys(data.state)
        # Motion events are handled idly
        self._current_point = Point(data.x, data.y)
        
        if not self._delayed_motion.is_queued:
            if not self._from_point:
                self._from_point = self._current_point
            
            if self._motion_from_outside:
                self._motion_from_outside -= 1
                if not self._motion_from_outside:
                    self._pressure_from_outside = False
            
            self._delayed_motion.queue()
    
    
    def _delayed_motion_cb(self, widget):
        """ Emits motion signals idly
        
        This is used because handling every Gtk motion-notify-event is waaaaaaa
        aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaay too slow.
        
        """
        
        to_point = self._current_point
        from_point = self._from_point
        pressure_dict = self._pressure
        
        if from_point != to_point:
            if not self._pressure_from_outside:
                for button, pressure in pressure_dict.items():
                    if pressure == 1:
                        pressure_dict[button] = 2
                        self.emit("start-dragging", to_point, button)
                    
                    self.emit("pression", to_point, button)
                    
            if not self._motion_from_outside:
                self.emit("motion", to_point, from_point)
                
            for button, pressure in pressure_dict.items():
                if pressure == 2:
                    self.emit("drag", to_point, from_point, button)
        
        self._from_point = to_point


class MetaMouseHandler(GObject.Object):
    """ Handles mouse events from mouse adapters for mouse handlers """
    __gsignals__ = {
        "handler-added" : (GObject.SIGNAL_ACTION, None, [object]),
        "handler-removed" : (GObject.SIGNAL_ACTION, None, [object]),
    }
    
    
    # It's So Meta Even This Acronym
    def __init__(self):
        GObject.Object.__init__(self)
        
        self._bindings = dict()
        self._adapters_data = dict()
        # These are sets of different kinds of mouse handlers
        self._pression_handlers = set()
        self._moving_handlers = set()
        self._dragging_handlers = set()
        self._scrolling_handlers = set()
        self._crossing_handlers = set()
        # This is a button/mouse handler set
        self._button_handlers = dict()
        # This is a key modifier/mouse handler set
        self._keys_handlers = dict()
    
    
    def __getitem__(self, handler):
        return self._bindings[handler]
    
    
    def add(self, handler, button=0, keys=0):
        """ Adds a handler to be handled """
        if not handler in self._bindings:
            binding = MouseHandlerBinding()
            binding.connect(
                "notify::button",
                self._changed_binding_button_cb, handler
            )
            binding.connect(
                "notify::keys",
                self._changed_binding_key_cb, handler
            )
            self._bindings[handler] = binding
            
            for a_handler_set in self._get_handler_sets(handler):
                a_handler_set.add(handler)
            
            if button:
                binding.button = button
            binding.keys = keys
            
            self.emit("handler-added", handler)
            
            return binding
    
    
    def remove(self, handler):
        """ Removes a handler to be handled """
        binding = self._bindings.pop(handler, None)
        if binding:
            for an_adapter_data in self._adapters_data.values():
                an_adapter_data.bindings.pop(handler, None)
            
            for handler_set in self._get_handler_sets(handler):
                handler_set.discard(handler)
            
            self._remove_handler_from_sets_dict(self._button_handlers, handler)
            self._remove_handler_from_sets_dict(self._keys_handlers, handler)
            
        binding.emit("removed")
        self.emit("handler-removed", handler)
    
    
    def get_handlers(self):
        """ Returns an iterator for the currently added handlers """
        yield from self._bindings.keys()
    
    
    def _changed_binding_button_cb(self, binding, spec, handler):
        self._remove_handler_from_sets_dict(self._button_handlers, handler)
        
        # Add handler to its button set
        button = binding.button
        try:
            button_set = self._button_handlers[button]
            
        except KeyError:
            self._button_handlers[button] = button_set = set()
            
        button_set.add(handler)
    
    
    def _changed_binding_key_cb(self, binding, spec, handler):
        self._remove_handler_from_sets_dict(self._keys_handlers, handler)
        
        # Add handler to its keys set
        keys = binding.keys
        try:
            keys_set = self._keys_handlers[keys]
        
        except KeyError:
            self._keys_handlers[keys] = keys_set = set()
            
        keys_set.add(handler)
    
    
    def _remove_handler_from_sets_dict(self, dictionary, handler):
        """ Utility for removing a handler from all sets in a dictionary and
            then removing the empty sets """
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
            
        if handler.handles(MouseEvents.Moving):
            yield self._moving_handlers
            
        if handler.handles(MouseEvents.Dragging):
            yield self._dragging_handlers
        
        if handler.handles(MouseEvents.Crossing):
            yield self._crossing_handlers
    
    
    def attach(self, adapter):
        """ Attach itself to a mouse adapter """
        if not adapter in self._adapters_data:
            signals = [
                adapter.connect("cross", self._cross),
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
        """ Detach itself from a mouse a adapter """
        adapter_data = self._adapters_data.pop(adapter, None)
        if adapter_data:
            for a_signal in adapter_data.signals:
                adapter.disconnect(a_signal)
    
    
    def _overlap_handler_sets(self, base_set, keys, button=None):
        if not base_set:
            # Quickly return empty base sets
            return base_set
        
        # First we create a set from the overlap between the base set and the
        # set which contains handlers associated to "button"
        if button is None:
            pressed_set = base_set
        else:
            button_handlers = self._button_handlers.get(button, None)
            if button_handlers:
                pressed_set = base_set & button_handlers
            else:
                pressed_set = None
        
        # If there are not handlers inside that we just return an empty set
        # otherwise we overlap with the modifier keys
        if pressed_set:
            keys_set = self._keys_handlers.get(keys, None)
            if keys_set:
                overlapped_set = pressed_set & keys_set
            else:
                overlapped_set = None
            
            # If the overlapped set is empty and there are modifier keys
            # pressed, we make a new overlapped set with the handlers that
            # are not bound to modifier keys
            if not overlapped_set and keys != 0:
                keys_set = self._keys_handlers.get(0, None)
                overlapped_set = pressed_set & keys_set
            
            # If this is None we return an empty set in the last line
            if overlapped_set is not None:
                return overlapped_set
        
        return set()
    
    def _basic_event_dispatch(self,
                              adapter,
                              event_handlers,
                              function_name,
                              *params):
        
        # This is an abomination made because all event methods do this
        if event_handlers:
            widget = adapter.widget
            handler_params = (widget, ) + params
            bindings = self._adapters_data[adapter].bindings
            
            for a_handler in event_handlers:
                function = getattr(a_handler, function_name)
            
                # This is the custom data returned by the handler
                a_binding = bindings.get(a_handler, None)
                a_binding = function(
                    *(handler_params + (a_binding,))
                )
                if a_binding:
                    bindings[a_handler] = a_binding
    
    
    def _scroll(self, adapter, point, direction):
        active_handlers = self._overlap_handler_sets(
            self._scrolling_handlers, adapter.keys,
        )
        self._basic_event_dispatch(
            adapter, active_handlers, "scroll", point, direction
        )
    
    
    def _cross(self, adapter, point, inside):
        active_handlers = self._overlap_handler_sets(
            self._crossing_handlers, adapter.keys
        )
        self._basic_event_dispatch(
            adapter, active_handlers, "cross", point, inside
        )
    
    
    def _motion(self, adapter, to_point, from_point):
        active_handlers = self._overlap_handler_sets(
            self._moving_handlers, adapter.keys,
        )
        if active_handlers:
            self._basic_event_dispatch(
                adapter, active_handlers, "move",
                to_point, from_point, adapter.is_pressed()
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
    """ MetaMouseHandler data associated to an adapter """
    
    def __init__(self, signals):
        self.signals = signals
        
        # Data returned by a handler method
        self.bindings = dict()
        
        # A set of handlers that start(ed)_dragging but didn't finish_dragging
        self.handlers_dragging = set()
        self.drag_keys_changed = False


class MouseHandlerBinding(GObject.Object):
    """ Represents a condition required in order to activate a MouseHandler """
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
            result |= ModifierType.CONTROL_MASK
        if self.shift_key:
            result |= ModifierType.SHIFT_MASK
        if self.alt_key:
            result |= ModifierType.MOD1_MASK
        return result
    
    
    def set_keys(self, value):
        self.freeze_notify()
        control_key = bool(value & ModifierType.CONTROL_MASK)
        shift_key = bool(value & ModifierType.SHIFT_MASK)
        alt_key = bool(value & ModifierType.MOD1_MASK)
        
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
    Nothing   = 0b00000000
    Moving    = 0b00000001
    Pressing  = 0b00010110 # Pressure regardless of movement
    Dragging  = 0b00001110 # Pressure and movement
    Clicking  = 0b00010100
    Scrolling = 0b00100000 # Handles either scrolling axes
    Rolling   = 0b01100000 # Handles both scrolling axes
    Crossing  = 0b10000000 # Entering and exiting the widget


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
        return (
            self.events & event_type == event_type
            if event_type != MouseEvents.Nothing
            else not bool(self.events)
        )
    
    
    @property
    def needs_button(self):
        """ Returns whether this mouse handler needs a button to be pressed """
        return bool(self.events & MouseEvents.Pressing)
    
    
    def scroll(self, widget, point, direction, data):
        """ Handles a scroll wheel event """
        pass
    
    
    def press(self, widget, point, data):
        """ Handles the mouse being pressed somewhere """
        pass
    
    
    def cross(self, widget, point, inside, data):
        """ Handles the mouse entering or leaving the widget """
        pass
    
    
    def move(self, widget, to_point, from_point, pressed, data):
        """ Handles the mouse moving around """
        if not pressed:
            self.hover(widget, to_point, from_point, data)
    
    
    def hover(self, widget, to_point, from_point, data):
        """ Handles the mouse just hovering around """
        pass
    
    
    def start_dragging(self, widget, point, data):
        """ Setup dragging variables """
        pass
    
    
    def drag(self, widget, to_point, from_point, data):
        """ Drag to point A from B """
        pass
    
    
    def stop_dragging(self, widget, point, data):
        """ Finish dragging """
        pass


class PivotMode:
    Mouse = 0
    Alignment = 1
    Fixed = 2


class MouseHandlerPivot(GObject.Object):
    """ An utility class for mouse mechanisms which need a pivot point """
    def __init__(self, settings=None, **kwargs):
        GObject.Object.__init__(self, **kwargs)
        notify_fixed_point = lambda s, w: s.notify("fixed-point")
        if settings:
            self.load_settings(settings)
        
        self.connect("notify::fixed-x", notify_fixed_point)
        self.connect("notify::fixed-y", notify_fixed_point)
    
    
    def get_fixed_point(self):
        return Point(self.fixed_x, self.fixed_y)
    
    
    def set_fixed_point(self, value):
        self.set_properties(fixed_x=value[0], fixed_y=value[1])
    
    
    mode = GObject.Property(type=int, default=PivotMode.Mouse)
    # Fixed pivot point
    fixed_x = GObject.Property(type=float, default=.5)
    fixed_y = GObject.Property(type=float, default=.5)
    fixed_point = GObject.Property(
        get_fixed_point, set_fixed_point, type=object
    )
    
    
    def convert_point(self, view, pointer):
        """ Returns a pivot point based on a view widget and
            the mouse pointer coordinates """
        mode = self.mode
        if mode == PivotMode.Mouse:
            return pointer
            
        else:
            w, h = view.get_allocated_width(), view.get_allocated_height()
            
            if mode == PivotMode.Alignment:
                scale = view.alignment_point
            else:
                scale = self.fixed_point
                
            return Point(w, h) * scale
    
    
    def get_settings(self):
        """ Returns a dictionary which can be used to recreate this pivot """
        result = { "mode": self.mode }
        if self.mode == PivotMode.Fixed:
            result["fixed-point"] = self.fixed_point
        
        return result
    
    
    def load_settings(self, settings):
        self.mode = settings.get("mode", PivotMode.Mouse)
        self.fixed_point = settings.get("fixed-point", (.5, .5))


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
        point_scale = widgets.PointScale(xadjust, yadjust)
        
        fixed_point_grid, xspin, yspin = widgets.PointScaleGrid(
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
