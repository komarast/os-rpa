from abc import ABC, abstractmethod
from typing import Any, Dict
from os_rpa.engine.context import ExecutionContext


class BaseAction(ABC):
    """Base class for all RPA workflow actions."""

    name: str = ""
    category: str = "general"
    description: str = ""
    params_schema: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        """Executes the action with evaluated parameters and context."""
        pass

