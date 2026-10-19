import sys
import time
from typing import Any, Dict
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext

# Safely import uiautomation on Windows
HAS_UIAUTOMATION = False
if sys.platform == "win32":
    try:
        import uiautomation as auto
        HAS_UIAUTOMATION = True
    except Exception:
        HAS_UIAUTOMATION = False


def find_control(
    name: str = "",
    automation_id: str = "",
    control_type: str = "",
    window_title: str = "",
    timeout: float = 5,
):
    """Locates a UI Automation control, optionally scoped to a top-level window
    (searching inside one window is much faster and less ambiguous than the whole desktop)."""
    search_root = None
    if window_title:
        search_root = auto.Control(searchDepth=1, SubName=window_title)
        if not search_root.Exists(maxSearchSeconds=timeout):
            raise RuntimeError(f"Window '{window_title}' not found within {timeout}s")

    kwargs: Dict[str, Any] = {}
    if search_root is not None:
        kwargs["searchFromControl"] = search_root
    if name:
        kwargs["SubName"] = name
    if automation_id:
        kwargs["AutomationId"] = automation_id

    ctrl_class = getattr(auto, f"{control_type}Control", auto.Control) if control_type else auto.Control
    control = ctrl_class(**kwargs)
    if not control.Exists(maxSearchSeconds=timeout):
        raise RuntimeError(
            f"Desktop control (Name='{name}', AutoId='{automation_id}', Type='{control_type}'"
            f"{f', Window={window_title!r}' if window_title else ''}) not found"
        )
    return control


class DesktopFindWindowAction(BaseAction):
    name = "desktop.find_window"
    category = "desktop"
    description = "Finds a desktop application window by title and brings it to the front."
    params_schema = {
        "title": {"type": "string", "label": "Window Title / Regex", "required": True, "default": "Notepad"},
        "timeout": {"type": "number", "label": "Search Timeout (seconds)", "default": 5},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        title = params.get("title", "")
        timeout = float(params.get("timeout", 5))

        if not HAS_UIAUTOMATION:
            context.info(f"[SIMULATED] Window '{title}' focused (uiautomation not active)")
            return {"title": title, "found": True}

        try:
            window = auto.WindowControl(searchDepth=2, SubName=title)
            if not window.Exists(maxSearchSeconds=timeout):
                window = auto.WindowControl(searchDepth=2, RegexName=f".*{title}.*")

            if window.Exists(maxSearchSeconds=1):
                window.SetActive()
                window.SetTopmost(True)
                window.SetTopmost(False)
                context.success(f"Focused desktop window '{window.Name}'")
                return {"title": window.Name, "handle": window.NativeWindowHandle}
            else:
                raise RuntimeError(f"Window with title '{title}' not found within {timeout}s")
        except Exception as e:
            context.error(f"Failed to find window '{title}': {e}")
            raise


class DesktopClickAction(BaseAction):
    name = "desktop.click"
    category = "desktop"
    description = "Clicks a desktop UI element by Name, AutomationId, or ClassName."
    params_schema = {
        "name": {"type": "string", "label": "Control Name (optional)", "default": ""},
        "automation_id": {"type": "string", "label": "Automation ID (optional)", "default": ""},
        "control_type": {"type": "string", "label": "Control Type (Button, Edit, ListItem...)", "default": "Button"},
        "window_title": {"type": "string", "label": "Window Title (optional, scopes the search)", "default": ""},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 5},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        ctrl_name = params.get("name")
        auto_id = params.get("automation_id")
        ctrl_type = params.get("control_type", "Button")
        timeout = float(params.get("timeout", 5))

        if not HAS_UIAUTOMATION:
            context.info(f"[SIMULATED] Clicked desktop element (Name='{ctrl_name}', AutoId='{auto_id}')")
            return True

        control = find_control(ctrl_name, auto_id, ctrl_type, params.get("window_title", ""), timeout)
        control.Click()
        context.success(f"Clicked desktop control '{control.Name}'")
        return True


class DesktopTypeAction(BaseAction):
    name = "desktop.type"
    category = "desktop"
    description = "Types text into the active desktop window or a targeted input field."
    params_schema = {
        "text": {"type": "string", "label": "Text to Type", "required": True},
        "name": {"type": "string", "label": "Target Control Name (optional)", "default": ""},
        "automation_id": {"type": "string", "label": "Automation ID (optional)", "default": ""},
        "window_title": {"type": "string", "label": "Window Title (optional, scopes the search)", "default": ""},
        "clear_first": {"type": "boolean", "label": "Clear before typing", "default": False},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        text = str(params.get("text", ""))
        ctrl_name = params.get("name")
        auto_id = params.get("automation_id")
        clear_first = bool(params.get("clear_first", False))

        if not HAS_UIAUTOMATION:
            context.info(f"[SIMULATED] Typed '{text}' into desktop control")
            return text

        if ctrl_name or auto_id:
            edit = find_control(ctrl_name, auto_id, "", params.get("window_title", ""), 3)
            edit.Click()
            if clear_first:
                auto.SendKeys("{Ctrl}a{Delete}")
            auto.SendKeys(text)
            context.success(f"Typed '{text}' into control '{edit.Name}'")
            return text

        # Fallback to direct SendKeys to active focus
        if clear_first:
            auto.SendKeys("{Ctrl}a{Delete}")
        auto.SendKeys(text)
        context.success(f"Typed '{text}' to current active desktop focus")
        return text


class DesktopGetTextAction(BaseAction):
    name = "desktop.get_text"
    category = "desktop"
    description = "Reads text value or label from a desktop UI control."
    params_schema = {
        "name": {"type": "string", "label": "Control Name (optional)", "default": ""},
        "automation_id": {"type": "string", "label": "Automation ID (optional)", "default": ""},
        "control_type": {"type": "string", "label": "Control Type (Edit, Text, etc.)", "default": "Edit"},
        "window_title": {"type": "string", "label": "Window Title (optional, scopes the search)", "default": ""},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        ctrl_name = params.get("name")
        auto_id = params.get("automation_id")
        ctrl_type = params.get("control_type", "Edit")

        if not HAS_UIAUTOMATION:
            context.info(f"[SIMULATED] Read text from desktop control")
            return "Sample Desktop Text"

        control = find_control(ctrl_name, auto_id, ctrl_type, params.get("window_title", ""), 4)
        # Try ValuePattern first, otherwise fallback to Name
        val = ""
        try:
            pattern = control.GetValuePattern()
            if pattern:
                val = pattern.Value
        except Exception:
            pass
        if not val:
            val = control.Name

        context.success(f"Read text from desktop control '{control.Name}': '{val}'")
        return val


class DesktopSendKeysAction(BaseAction):
    name = "desktop.send_keys"
    category = "desktop"
    description = "Sends hotkeys / keyboard shortcuts to the system (e.g. '{Enter}', '{Ctrl}c')."
    params_schema = {
        "keys": {"type": "string", "label": "Keys Sequence (e.g. {Ctrl}s, {Enter})", "required": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        keys = params.get("keys", "")
        if not HAS_UIAUTOMATION:
            context.info(f"[SIMULATED] Sent keys '{keys}'")
            return True

        auto.SendKeys(keys)
        context.success(f"Sent keys '{keys}' to desktop")
        return True

