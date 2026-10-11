import io
import sys
import json
import math
import re
import datetime
from pathlib import Path
from typing import Any, Dict
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext


class PythonScriptAction(BaseAction):
    name = "script.python"
    category = "script"
    description = "Executes custom Python code with full access to context, variables, and queue items."
    params_schema = {
        "code": {
            "type": "code",
            "language": "python",
            "label": "Python Script",
            "default": "# Write custom Python code here\n# Available: context, variables, item, print()\n\nresult = len(variables)\ncontext.set('result', result)\noutput = result\n",
            "required": True,
        }
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        code = params.get("code", "")
        if not code.strip():
            context.warning("Empty script supplied, skipping execution")
            return None

        # Prepare capture buffer for print statements
        stdout_capture = io.StringIO()
        original_stdout = sys.stdout

        # Local execution scope
        local_scope: Dict[str, Any] = {
            "context": context,
            "variables": context.variables,
            "item": context.variables.get("item", {}),
            "output": None,
            "json": json,
            "math": math,
            "re": re,
            "datetime": datetime,
            "Path": Path,
        }

        try:
            sys.stdout = stdout_capture
            exec(code, local_scope)
        except Exception as e:
            context.error(f"Script execution failed: {e}")
            raise
        finally:
            sys.stdout = original_stdout
            output_str = stdout_capture.getvalue()
            if output_str.strip():
                for line in output_str.strip().splitlines():
                    context.info(f"[Script stdout] {line}")

        # Check for output result
        result = local_scope.get("output")
        context.success("Python script executed successfully", {"output": str(result)[:200] if result else None})
        return result

