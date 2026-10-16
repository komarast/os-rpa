import re
from typing import Any, Dict
from os_rpa.engine.context import ExecutionContext

PATTERN = re.compile(r"\{\{(.+?)\}\}")


def evaluate_expression(expr: str, scope: Dict[str, Any]) -> Any:
    """Evaluates a single python expression within the scope safely."""
    expr = expr.strip()
    # Simple direct variable lookup optimization
    if expr in scope:
        return scope[expr]
    # Evaluate python expression with limited globals
    safe_globals = {
        "__builtins__": {
            "len": len,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "range": range,
            "enumerate": enumerate,
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "round": round,
            "all": all,
            "any": any,
            "sorted": sorted,
        }
    }
    return eval(expr, safe_globals, scope)


def evaluate_value(value: Any, context: ExecutionContext) -> Any:
    """Recursively evaluates strings, lists, and dicts against context variables."""
    if isinstance(value, str):
        # Case 1: Exact single placeholder e.g. "{{my_var}}" or "{{item['price'] * 2}}"
        trimmed = value.strip()
        match = PATTERN.fullmatch(trimmed)
        # "{{a}} and {{b}}" also fullmatches lazily across "}} ... {{"; treat that as interpolation
        if match and "{{" not in match.group(1) and "}}" not in match.group(1):
            inner_expr = match.group(1).strip()
            try:
                return evaluate_expression(inner_expr, context.variables)
            except Exception as e:
                context.warning(f"Failed to evaluate expression '{inner_expr}': {e}")
                return value

        # Case 2: String with embedded placeholders e.g. "Order {{id}} processed"
        if "{{" in value and "}}" in value:
            def replacer(m):
                expr = m.group(1).strip()
                try:
                    res = evaluate_expression(expr, context.variables)
                    return str(res)
                except Exception as e:
                    context.warning(f"Failed to interpolate '{expr}': {e}")
                    return m.group(0)

            return PATTERN.sub(replacer, value)

        return value

    elif isinstance(value, dict):
        return {k: evaluate_value(v, context) for k, v in value.items()}

    elif isinstance(value, list):
        return [evaluate_value(item, context) for item in value]

    return value

