"""Desktop element picker: hover a control, press Ctrl to capture it (Esc cancels)."""
import ctypes
import os
import sys
import time
from typing import Any, Dict, List, Optional

VK_CONTROL = 0x11
VK_ESCAPE = 0x1B
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
WS_EX_NOACTIVATE = 0x08000000
GA_ROOT = 2


def _load_uiautomation():
    if sys.platform != "win32":
        raise RuntimeError("Desktop inspection is only available on Windows")
    try:
        # Physical pixel coordinates for both UI Automation rectangles and the Tk overlay
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    try:
        import uiautomation as auto
    except Exception as e:
        raise RuntimeError(f"Desktop inspection requires the 'uiautomation' package: {e}")
    return auto


def _key_down(vk: int) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def _short_type(control) -> str:
    name = control.ControlTypeName or ""
    return name[: -len("Control")] if name.endswith("Control") else name


def _top_level_window(control):
    """Walks up to the child of the desktop root (the application window)."""
    top = control
    for _ in range(64):
        parent = top.GetParentControl()
        if parent is None or parent.GetParentControl() is None:
            return top
        top = parent
    return top


def _ancestors(control, window) -> List[Dict[str, str]]:
    chain = []
    cur = control
    for _ in range(64):
        chain.append({
            "control_type": _short_type(cur),
            "name": cur.Name or "",
            "automation_id": cur.AutomationId or "",
            "class_name": cur.ClassName or "",
        })
        if window.NativeWindowHandle and cur.NativeWindowHandle == window.NativeWindowHandle:
            break
        cur = cur.GetParentControl()
        if cur is None or cur.GetParentControl() is None:
            break
    return list(reversed(chain))


def suggest_params(info: Dict[str, Any]) -> Dict[str, Any]:
    """Activity parameters (desktop.* params_schema keys) that target the described control.
    Empty strings are kept on purpose so applying them clears stale values on the node."""
    return {
        "name": info.get("name", ""),
        "automation_id": info.get("automation_id", ""),
        "control_type": info.get("control_type", ""),
        "window_title": info.get("window_title", ""),
        # desktop.find_window
        "title": info.get("window_title", ""),
    }


def describe_control(control) -> Dict[str, Any]:
    rect = control.BoundingRectangle
    window = _top_level_window(control)
    value = ""
    try:
        pattern = control.GetValuePattern()
        if pattern:
            value = str(pattern.Value or "")[:200]
    except Exception:
        pass
    return {
        "name": control.Name or "",
        "automation_id": control.AutomationId or "",
        "control_type": _short_type(control),
        "class_name": control.ClassName or "",
        "framework_id": control.FrameworkId or "",
        "process_id": control.ProcessId,
        "is_enabled": bool(control.IsEnabled),
        "value": value,
        "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
        "window_title": window.Name or "",
        "window_class": window.ClassName or "",
        "path": _ancestors(control, window),
    }


class Highlighter:
    """Click-through red frame around a rectangle plus a hint label, drawn with Tk toplevels."""

    def __init__(self, color: str = "#ff2d55", thickness: int = 3):
        import tkinter as tk

        self.tk = tk
        self.thickness = thickness
        self.root = tk.Tk()
        self.root.withdraw()
        self.edges = [self._overlay(bg=color) for _ in range(4)]
        self.label_win = self._overlay(bg="#0f172a")
        self.label = tk.Label(
            self.label_win, bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 9),
            justify="left", padx=8, pady=4,
        )
        self.label.pack()

    def _overlay(self, bg: str):
        win = self.tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.92)  # makes it a layered window, required for click-through
        win.configure(bg=bg)
        win.withdraw()
        win.update_idletasks()
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetAncestor(win.winfo_id(), GA_ROOT)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        except Exception:
            pass
        return win

    def show(self, rect: Dict[str, int], text: str = "", cursor: Optional[tuple] = None):
        t = self.thickness
        left, top, right, bottom = rect["left"], rect["top"], rect["right"], rect["bottom"]
        width, height = max(1, right - left), max(1, bottom - top)
        geoms = [
            (width + 2 * t, t, left - t, top - t),
            (width + 2 * t, t, left - t, bottom),
            (t, height, left - t, top),
            (t, height, right, top),
        ]
        for win, (w, h, x, y) in zip(self.edges, geoms):
            win.geometry(f"{w}x{h}+{x}+{y}")
            win.deiconify()
        if text:
            self.label.configure(text=text)
            lx, ly = (cursor[0] + 18, cursor[1] + 20) if cursor else (left, bottom + t + 2)
            self.label_win.geometry(f"+{lx}+{ly}")
            self.label_win.deiconify()
        else:
            self.label_win.withdraw()

    def hide(self):
        for win in self.edges + [self.label_win]:
            win.withdraw()

    def flash(self, rect: Dict[str, int], text: str, seconds: float = 1.5):
        self.show(rect, text)
        self.root.after(int(seconds * 1000), self.root.quit)
        self.root.mainloop()

    def destroy(self):
        try:
            self.root.destroy()
        except Exception:
            pass


def _check_selector(auto, control, params: Dict[str, Any]) -> Optional[str]:
    """Returns a warning when the suggested parameters resolve to a different control first."""
    from os_rpa.actions.desktop import find_control

    try:
        found = find_control(
            params["name"], params["automation_id"], params["control_type"], params["window_title"], timeout=1
        )
    except Exception as e:
        return f"Suggested parameters do not find the element again: {e}"
    if not auto.ControlsAreSame(found, control):
        return "Suggested parameters match a different element first; refine Name / Automation ID."
    return None


def pick_control(timeout: float = 120, hint: str = "Ctrl = select    Esc = cancel"):
    """Highlights the control under the cursor until Ctrl (select) or Esc (cancel).
    Returns (control, None) or (None, error_result)."""
    auto = _load_uiautomation()
    own_pid = os.getpid()
    deadline = time.time() + timeout
    state: Dict[str, Any] = {"control": None, "error": None, "cancelled": False}
    current: Dict[str, Any] = {"control": None, "pos": None}

    hl = Highlighter()

    def tick():
        if time.time() > deadline:
            state["error"] = f"No element selected within {int(timeout)}s"
            hl.root.quit()
            return
        if _key_down(VK_ESCAPE):
            state["cancelled"] = True
            hl.root.quit()
            return
        if _key_down(VK_CONTROL) and current["control"] is not None:
            state["control"] = current["control"]
            hl.root.quit()
            return

        pos = auto.GetCursorPos()
        if pos != current["pos"]:
            current["pos"] = pos
            try:
                ctrl = auto.ControlFromCursor()
            except Exception:
                ctrl = None
            if ctrl is not None and ctrl.ProcessId != own_pid:
                current["control"] = ctrl
                r = ctrl.BoundingRectangle
                label = f"{_short_type(ctrl)}  '{(ctrl.Name or '')[:60]}'"
                if ctrl.AutomationId:
                    label += f"  #{ctrl.AutomationId[:40]}"
                hl.show(
                    {"left": r.left, "top": r.top, "right": r.right, "bottom": r.bottom},
                    f"{label}\n{hint}",
                    pos,
                )
        hl.root.after(80, tick)

    try:
        # Don't capture immediately if Ctrl is still held from launching the inspector
        while _key_down(VK_CONTROL) and time.time() < deadline:
            time.sleep(0.05)
        hl.root.after(0, tick)
        hl.root.mainloop()
        hl.hide()
    finally:
        hl.destroy()

    if state["cancelled"]:
        return None, {"ok": False, "cancelled": True, "error": "Selection cancelled"}
    if state["error"]:
        return None, {"ok": False, "error": state["error"]}
    return state["control"], None


def pick(timeout: float = 120) -> Dict[str, Any]:
    control, failure = pick_control(timeout)
    if failure:
        return failure
    import uiautomation as auto

    info = describe_control(control)
    params = suggest_params(info)
    warnings = [w for w in [_check_selector(auto, control, params)] if w]
    return {"ok": True, "target": "desktop", "element": info, "params": params, "selectors": [], "warnings": warnings}


def validate(params: Dict[str, Any], timeout: float = 5) -> Dict[str, Any]:
    _load_uiautomation()
    from os_rpa.actions.desktop import find_control

    control = find_control(
        str(params.get("name") or ""),
        str(params.get("automation_id") or ""),
        str(params.get("control_type") or ""),
        str(params.get("window_title") or params.get("title") or ""),
        timeout,
    )
    info = describe_control(control)
    hl = Highlighter(color="#22c55e")
    try:
        hl.flash(info["rect"], f"Found: {info['control_type']} '{info['name'][:60]}'")
    finally:
        hl.destroy()
    return {"ok": True, "target": "desktop", "found": True, "count": 1, "element": info}
