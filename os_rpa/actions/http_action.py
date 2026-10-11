import json
from typing import Any, Dict, Optional
import httpx
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext


class HttpRequestAction(BaseAction):
    name = "http.request"
    category = "http"
    description = "Executes an HTTP request (GET, POST, PUT, DELETE, PATCH) and captures status, headers, and body."
    params_schema = {
        "method": {
            "type": "select",
            "options": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "label": "HTTP Method",
            "default": "GET",
        },
        "url": {
            "type": "string",
            "label": "URL Endpoint",
            "required": True,
            "default": "https://httpbin.org/get",
        },
        "headers": {
            "type": "object",
            "label": "Headers (Optional JSON / Map)",
            "default": {},
        },
        "json_body": {
            "type": "any",
            "label": "JSON Body (Optional)",
            "default": None,
        },
        "timeout": {
            "type": "number",
            "label": "Timeout (seconds)",
            "default": 30.0,
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        method = str(params.get("method", "GET")).upper()
        url = str(params.get("url", "")).strip()
        headers = params.get("headers") or {}
        json_body = params.get("json_body")
        timeout = float(params.get("timeout", 30.0))

        if not url:
            raise ValueError("URL is required for http.request")

        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except Exception:
                headers = {}

        if isinstance(json_body, str) and json_body.strip().startswith(("{", "[")):
            try:
                json_body = json.loads(json_body)
            except Exception:
                pass

        context.info(f"Sending HTTP {method} request to {url}")

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            req_kwargs: Dict[str, Any] = {"headers": headers}
            if json_body is not None and method in ("POST", "PUT", "PATCH"):
                req_kwargs["json"] = json_body

            response = client.request(method, url, **req_kwargs)

        parsed_data = None
        try:
            parsed_data = response.json()
        except Exception:
            parsed_data = response.text

        context.info(f"HTTP {method} {url} responded with status {response.status_code}")

        return {
            "status_code": response.status_code,
            "ok": response.is_success,
            "data": parsed_data,
            "text": response.text,
            "headers": dict(response.headers),
        }
