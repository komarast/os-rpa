from typing import Any, Dict, List, Type
from os_rpa.actions.base import BaseAction
from os_rpa.actions.queue_actions import QueueGetNextItemAction, QueueSetStatusAction, QueueAddItemAction
from os_rpa.actions.excel import (
    ExcelCreateWorkbookAction,
    ExcelReadRangeAction,
    ExcelWriteCellAction,
    ExcelAppendRowAction,
)
from os_rpa.actions.web import (
    WebOpenBrowserAction,
    WebNavigateAction,
    WebClickAction,
    WebTypeAction,
    WebGetTextAction,
    WebScreenshotAction,
    WebCloseBrowserAction,
)
from os_rpa.actions.desktop import (
    DesktopFindWindowAction,
    DesktopClickAction,
    DesktopTypeAction,
    DesktopGetTextAction,
    DesktopSendKeysAction,
)
from os_rpa.actions.script import PythonScriptAction
from os_rpa.actions.logic import (
    LogicLogAction,
    LogicDelayAction,
    LogicSetVariableAction,
    LogicConditionAction,
)
from os_rpa.actions.flow import (
    FlowStartAction,
    FlowEndAction,
    FlowAssignAction,
    FlowIfElseAction,
    FlowLoopAction,
    FlowTryCatchAction,
)
from os_rpa.actions.http_action import HttpRequestAction
from os_rpa.actions.file_system import (
    FileReadTextAction,
    FileWriteTextAction,
    FileCopyAction,
    FileDeleteAction,
    FileExistsAction,
)


class ActionRegistry:
    """Central registry of all available RPA actions."""

    _registry: Dict[str, Type[BaseAction]] = {}

    @classmethod
    def register(cls, action_cls: Type[BaseAction]):
        cls._registry[action_cls.name] = action_cls

    @classmethod
    def get(cls, name: str) -> BaseAction:
        action_cls = cls._registry.get(name)
        if not action_cls:
            raise KeyError(f"Action '{name}' is not registered in ActionRegistry")
        return action_cls()

    @classmethod
    def list_actions(cls) -> List[Dict[str, Any]]:
        actions = []
        for name, action_cls in cls._registry.items():
            actions.append({
                "type": name,
                "category": action_cls.category,
                "description": action_cls.description,
                "params_schema": action_cls.params_schema,
            })
        # Sort by category then type
        actions.sort(key=lambda a: (a["category"], a["type"]))
        return actions


# Automatically register all built-in actions
ALL_BUILTIN_ACTIONS = [
    # Control Flow
    FlowStartAction,
    FlowEndAction,
    FlowAssignAction,
    FlowIfElseAction,
    FlowLoopAction,
    FlowTryCatchAction,
    # HTTP & Webhooks
    HttpRequestAction,
    # File Operations
    FileReadTextAction,
    FileWriteTextAction,
    FileCopyAction,
    FileDeleteAction,
    FileExistsAction,
    # Queue
    QueueGetNextItemAction,
    QueueSetStatusAction,
    QueueAddItemAction,
    # Excel
    ExcelCreateWorkbookAction,
    ExcelReadRangeAction,
    ExcelWriteCellAction,
    ExcelAppendRowAction,
    # Web
    WebOpenBrowserAction,
    WebNavigateAction,
    WebClickAction,
    WebTypeAction,
    WebGetTextAction,
    WebScreenshotAction,
    WebCloseBrowserAction,
    # Desktop
    DesktopFindWindowAction,
    DesktopClickAction,
    DesktopTypeAction,
    DesktopGetTextAction,
    DesktopSendKeysAction,
    # Script
    PythonScriptAction,
    # Logic
    LogicLogAction,
    LogicDelayAction,
    LogicSetVariableAction,
    LogicConditionAction,
]

for act in ALL_BUILTIN_ACTIONS:
    ActionRegistry.register(act)
