import os
import shutil
from pathlib import Path
from typing import Any, Dict
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext


class FileReadTextAction(BaseAction):
    name = "file.read_text"
    category = "file"
    description = "Reads the text contents of a file on disk."
    params_schema = {
        "file_path": {
            "type": "string",
            "label": "File Path",
            "required": True,
            "default": "data/sample.txt",
        },
        "encoding": {
            "type": "string",
            "label": "Encoding",
            "default": "utf-8",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> str:
        file_path = Path(str(params.get("file_path", "")))
        encoding = str(params.get("encoding", "utf-8"))

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding=encoding)
        context.info(f"Read {len(content)} characters from '{file_path}'")
        return content


class FileWriteTextAction(BaseAction):
    name = "file.write_text"
    category = "file"
    description = "Writes or appends text to a file on disk."
    params_schema = {
        "file_path": {
            "type": "string",
            "label": "File Path",
            "required": True,
            "default": "data/output.txt",
        },
        "content": {
            "type": "string",
            "label": "Text Content",
            "required": True,
            "default": "Hello RPA",
        },
        "append": {
            "type": "boolean",
            "label": "Append to file",
            "default": False,
        },
        "encoding": {
            "type": "string",
            "label": "Encoding",
            "default": "utf-8",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> str:
        file_path = Path(str(params.get("file_path", "")))
        content = str(params.get("content", ""))
        append = bool(params.get("append", False))
        encoding = str(params.get("encoding", "utf-8"))

        file_path.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)

        action_name = "Appended" if append else "Wrote"
        context.info(f"{action_name} {len(content)} characters to '{file_path}'")
        return str(file_path)


class FileCopyAction(BaseAction):
    name = "file.copy"
    category = "file"
    description = "Copies a file or directory from source to destination."
    params_schema = {
        "source": {
            "type": "string",
            "label": "Source Path",
            "required": True,
        },
        "destination": {
            "type": "string",
            "label": "Destination Path",
            "required": True,
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> str:
        src = Path(str(params.get("source", "")))
        dst = Path(str(params.get("destination", "")))

        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        context.info(f"Copied '{src}' -> '{dst}'")
        return str(dst)


class FileDeleteAction(BaseAction):
    name = "file.delete"
    category = "file"
    description = "Safely deletes a file if it exists."
    params_schema = {
        "file_path": {
            "type": "string",
            "label": "File Path",
            "required": True,
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        file_path = Path(str(params.get("file_path", "")))
        if file_path.exists():
            file_path.unlink()
            context.info(f"Deleted file '{file_path}'")
            return True
        context.info(f"File '{file_path}' does not exist, skipped deletion")
        return False


class FileExistsAction(BaseAction):
    name = "file.exists"
    category = "file"
    description = "Checks whether a file or directory exists on disk."
    params_schema = {
        "file_path": {
            "type": "string",
            "label": "File Path",
            "required": True,
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> bool:
        file_path = Path(str(params.get("file_path", "")))
        exists = file_path.exists()
        context.info(f"File exists check for '{file_path}': {exists}")
        return exists
