from pathlib import Path
from os_rpa.actions.registry import ActionRegistry
from os_rpa.engine.context import ExecutionContext


def test_excel_actions(tmp_path: Path):
    excel_file = tmp_path / "test_report.xlsx"
    ctx = ExecutionContext()

    # 1. Create workbook
    create_act = ActionRegistry.get("excel.create")
    create_act.execute({"file_path": str(excel_file), "sheet_name": "Invoices"}, ctx)
    assert excel_file.exists()

    # 2. Append header and rows
    append_act = ActionRegistry.get("excel.append_row")
    append_act.execute({"file_path": str(excel_file), "sheet_name": "Invoices", "row_data": ["InvoiceID", "Customer", "Amount"]}, ctx)
    append_act.execute({"file_path": str(excel_file), "sheet_name": "Invoices", "row_data": ["INV-001", "Acme Corp", 1500.50]}, ctx)
    append_act.execute({"file_path": str(excel_file), "sheet_name": "Invoices", "row_data": ["INV-002", "Globex", 2300.00]}, ctx)

    # 3. Read range
    read_act = ActionRegistry.get("excel.read_range")
    rows = read_act.execute({"file_path": str(excel_file), "sheet_name": "Invoices", "has_headers": True}, ctx)
    assert len(rows) == 2
    assert rows[0]["InvoiceID"] == "INV-001"
    assert rows[0]["Customer"] == "Acme Corp"
    assert rows[0]["Amount"] == 1500.50
    assert rows[1]["InvoiceID"] == "INV-002"

    # 4. Write cell
    write_act = ActionRegistry.get("excel.write_cell")
    write_act.execute({"file_path": str(excel_file), "sheet_name": "Invoices", "cell": "C2", "value": 9999}, ctx)

    updated_rows = read_act.execute({"file_path": str(excel_file), "sheet_name": "Invoices", "has_headers": True}, ctx)
    assert updated_rows[0]["Amount"] == 9999

