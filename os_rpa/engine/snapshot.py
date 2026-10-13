"""JSON-safe views of runtime variables for the Studio debugger and Data Manager."""
from datetime import date, datetime
from typing import Any, Dict

MAX_ITEMS = 500
MAX_DEPTH = 8


def type_name(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (list, tuple, set)):
        return "list"
    return type(value).__name__


def to_jsonable(value: Any, depth: int = 0) -> Any:
    """Converts a runtime value to something json.dumps accepts; opaque objects become '<TypeName>'."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth >= MAX_DEPTH:
        return f"<{type_name(value)}>"
    if isinstance(value, dict):
        items = list(value.items())[:MAX_ITEMS]
        return {str(k): to_jsonable(v, depth + 1) for k, v in items}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v, depth + 1) for v in list(value)[:MAX_ITEMS]]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<bytes len={len(value)}>"
    return f"<{type(value).__name__}>"


def json_default(value: Any) -> Any:
    """`default=` hook for json.dumps on payloads that may contain runtime objects."""
    return to_jsonable(value) if isinstance(value, (set, tuple, datetime, date, bytes)) else f"<{type(value).__name__}>"


def public_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in variables.items() if not k.startswith("_")}
