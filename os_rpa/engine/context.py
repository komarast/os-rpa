from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from os_rpa.models import ExecutionLogMessage, QueueItem


class ExecutionContext:
    """Carries workflow state, variables, active queue item, and execution logs."""

    def __init__(
        self,
        initial_variables: Optional[Dict[str, Any]] = None,
        queue_item: Optional[QueueItem] = None,
        on_log: Optional[Callable[[ExecutionLogMessage], None]] = None,
    ):
        self.variables: Dict[str, Any] = initial_variables.copy() if initial_variables else {}
        self.current_item: Optional[QueueItem] = queue_item
        if queue_item:
            self.variables["item"] = queue_item.payload
            self.variables["queue_item_id"] = queue_item.id
        self.logs: List[ExecutionLogMessage] = []
        self.current_node_id: Optional[str] = None
        self._on_log = on_log
        # Set by WorkflowRunner: the runner executing this context and how deeply it is nested
        # inside flow.invoke_workflow calls (0 = top-level run)
        self.runner: Any = None
        self.call_depth: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def set(self, key: str, value: Any):
        self.variables[key] = value

    def log(self, level: str, message: str, details: Optional[Dict[str, Any]] = None):
        msg = ExecutionLogMessage(
            level=level,
            node_id=self.current_node_id,
            message=message,
            details=details,
        )
        self.logs.append(msg)
        if self._on_log:
            try:
                self._on_log(msg)
            except Exception:
                pass

    def info(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.log("INFO", message, details)

    def warning(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.log("WARNING", message, details)

    def error(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.log("ERROR", message, details)

    def success(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.log("SUCCESS", message, details)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variables": self.variables,
            "current_item_id": self.current_item.id if self.current_item else None,
            "log_count": len(self.logs),
        }

