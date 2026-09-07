"""pygetwindow-compatible shim for Linux/X11 (XWayland), backed by python-xlib + EWMH.

Only implements the subset of the pygetwindow API actually used by this project:
title, left/top/width/height, isMaximized/isMinimized, moveTo, resizeTo, restore, activate.
"""
from Xlib import display, X
from Xlib.error import XError
from Xlib.protocol import event

_d = display.Display()
_root = _d.screen().root

_NET_CLIENT_LIST = _d.intern_atom('_NET_CLIENT_LIST')
_NET_WM_NAME = _d.intern_atom('_NET_WM_NAME')
_NET_WM_STATE = _d.intern_atom('_NET_WM_STATE')
_NET_WM_STATE_MAXIMIZED_VERT = _d.intern_atom('_NET_WM_STATE_MAXIMIZED_VERT')
_NET_WM_STATE_MAXIMIZED_HORZ = _d.intern_atom('_NET_WM_STATE_MAXIMIZED_HORZ')
_NET_WM_STATE_HIDDEN = _d.intern_atom('_NET_WM_STATE_HIDDEN')
_NET_ACTIVE_WINDOW = _d.intern_atom('_NET_ACTIVE_WINDOW')

_WM_STATE_REMOVE = 0
_WM_STATE_ADD = 1


def _get_prop(win, atom):
    try:
        return win.get_full_property(atom, X.AnyPropertyType)
    except XError:
        return None


def _title_of(win):
    prop = _get_prop(win, _NET_WM_NAME)
    if prop and prop.value:
        value = prop.value
        return value.decode('utf-8') if isinstance(value, bytes) else value
    return ''


def _all_client_windows():
    prop = _get_prop(_root, _NET_CLIENT_LIST)
    if not prop:
        return []
    windows = []
    for wid in prop.value:
        try:
            windows.append(_d.create_resource_object('window', wid))
        except XError:
            continue
    return windows


def _send_root_client_message(win, msg_type, data):
    ev = event.ClientMessage(window=win, client_type=msg_type, data=(32, data))
    mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
    _root.send_event(ev, event_mask=mask)
    _d.flush()


class LinuxWindow:
    def __init__(self, win):
        self._win = win

    @property
    def title(self):
        return _title_of(self._win)

    def _geometry(self):
        geom = self._win.get_geometry()
        coords = self._win.translate_coords(_root, 0, 0)
        return coords.x, coords.y, geom.width, geom.height

    @property
    def left(self):
        return self._geometry()[0]

    @property
    def top(self):
        return self._geometry()[1]

    @property
    def width(self):
        return self._geometry()[2]

    @property
    def height(self):
        return self._geometry()[3]

    def _wm_state(self):
        prop = _get_prop(self._win, _NET_WM_STATE)
        return set(prop.value) if prop else set()

    @property
    def isMaximized(self):
        state = self._wm_state()
        return _NET_WM_STATE_MAXIMIZED_VERT in state and _NET_WM_STATE_MAXIMIZED_HORZ in state

    @property
    def isMinimized(self):
        return _NET_WM_STATE_HIDDEN in self._wm_state()

    def restore(self):
        _send_root_client_message(self._win, _NET_WM_STATE,
            (_WM_STATE_REMOVE, _NET_WM_STATE_MAXIMIZED_VERT, _NET_WM_STATE_MAXIMIZED_HORZ, 1, 0))
        self._win.map()
        _d.flush()

    def moveTo(self, x, y):
        self._win.configure(x=x, y=y)
        _d.flush()

    def resizeTo(self, w, h):
        self._win.configure(width=w, height=h)
        _d.flush()

    def activate(self):
        _send_root_client_message(self._win, _NET_ACTIVE_WINDOW, (1, X.CurrentTime, 0, 0, 0))


def getAllTitles():
    return [_title_of(w) for w in _all_client_windows()]


def getWindowsWithTitle(title):
    return [LinuxWindow(w) for w in _all_client_windows() if title in _title_of(w)]
