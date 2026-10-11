from pathlib import Path
from typing import Any, Dict, List, Optional
import openpyxl
from openpyxl.workbook import Workbook
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext


class ExcelCreateWorkbookAction(BaseAction):
    name = "excel.create"
    category = "excel"
    description = "Creates a new empty Excel workbook at the target file path."
    params_schema = {
        "file_path": {"type": "string", "label": "File Path", "required": True, "default": "data/output.xlsx"},
        "sheet_name": {"type": "string", "label": "Initial Sheet Name", "default": "Sheet1"},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        file_path = Path(params["file_path"])
        file_path.parent.mkdir(parents=True, exist_ok=True)
        sheet_name = params.get("sheet_name", "Sheet1")

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        wb.save(str(file_path))
        context.success(f"Created Excel workbook at {file_path}")
        return str(file_path)


class ExcelReadRangeAction(BaseAction):
    name = "excel.read_range"
    category = "excel"
    description = "Reads an Excel worksheet into a list of row dictionaries or values."
    params_schema = {
        "file_path": {"type": "string", "label": "File Path", "required": True},
        "sheet_name": {"type": "string", "label": "Sheet Name (optional)", "default": ""},
        "has_headers": {"type": "boolean", "label": "First row is header", "default": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        file_path = Path(params["file_path"])
        if not file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {file_path}")

        wb = openpyxl.load_workbook(str(file_path), data_only=True)
        sheet_name = params.get("sheet_name")
        ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

        has_headers = params.get("has_headers", True)
        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            context.info(f"Excel sheet '{ws.title}' is empty.")
            return []

        if has_headers:
            headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
            result = []
            for row in rows[1:]:
                if any(cell is not None for cell in row):
                    row_dict = {}
                    for i, header in enumerate(headers):
                        row_dict[header] = row[i] if i < len(row) else None
                    result.append(row_dict)
            context.success(f"Read {len(result)} records from Excel '{file_path.name}'")
            return result
        else:
            result = [list(r) for r in rows if any(cell is not None for cell in r)]
            context.success(f"Read {len(result)} raw rows from Excel '{file_path.name}'")
            return result


class ExcelWriteCellAction(BaseAction):
    name = "excel.write_cell"
    category = "excel"
    description = "Writes a value to a specific cell (e.g. A1 or row/col) in an Excel file."
    params_schema = {
        "file_path": {"type": "string", "label": "File Path", "required": True},
        "sheet_name": {"type": "string", "label": "Sheet Name (optional)", "default": ""},
        "cell": {"type": "string", "label": "Cell Address (e.g. B2)", "default": "A1"},
        "value": {"type": "any", "label": "Value to write", "required": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        file_path = Path(params["file_path"])
        if not file_path.exists():
            wb = Workbook()
        else:
            wb = openpyxl.load_workbook(str(file_path))

        sheet_name = params.get("sheet_name")
        ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

        cell = params.get("cell", "A1")
        value = params.get("value")
        ws[cell] = value
        wb.save(str(file_path))
        context.success(f"Wrote '{value}' to cell {cell} in {file_path.name}")
        return value


class ExcelAppendRowAction(BaseAction):
    name = "excel.append_row"
    category = "excel"
    description = "Appends a new row of data to the end of the Excel sheet."
    params_schema = {
        "file_path": {"type": "string", "label": "File Path", "required": True},
        "sheet_name": {"type": "string", "label": "Sheet Name (optional)", "default": ""},
        "row_data": {"type": "array", "label": "Row Data (list of values or dict)", "required": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        file_path = Path(params["file_path"])
        if not file_path.exists():
            wb = Workbook()
            ws = wb.active
        else:
            wb = openpyxl.load_workbook(str(file_path))
            sheet_name = params.get("sheet_name")
            ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

        row_data = params.get("row_data")
        if isinstance(row_data, dict):
            # If sheet has headers, match keys to header columns
            first_row = [cell.value for cell in ws[1]]
            if any(first_row):
                ordered = [row_data.get(str(h), "") for h in first_row]
                ws.append(ordered)
            else:
                ws.append(list(row_data.values()))
        elif isinstance(row_data, (list, tuple)):
            ws.append(list(row_data))
        else:
            ws.append([row_data])

        wb.save(str(file_path))
        context.success(f"Appended row to {file_path.name}")
        return True

