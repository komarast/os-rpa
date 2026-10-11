from pathlib import Path
from os_rpa.models import Workflow, WorkflowNode, QueueItemStatus
from os_rpa.queue.manager import QueueManager
from os_rpa.engine.runner import WorkflowRunner


def test_full_rpa_queue_excel_web_script_e2e(tmp_path: Path):
    db_file = tmp_path / "e2e_queues.db"
    excel_file = tmp_path / "processed_invoices.xlsx"
    queue_mgr = QueueManager(str(db_file))

    # 1. Enqueue 2 invoice items
    item1 = queue_mgr.add_item("InvoiceQueue", {"invoice_no": "INV-101", "client": "Global Tech", "subtotal": 1200.0})
    item2 = queue_mgr.add_item("InvoiceQueue", {"invoice_no": "INV-102", "client": "Apex Media", "subtotal": 850.0})

    # Create HTML form for web automation
    html_file = tmp_path / "invoice_portal.html"
    html_file.write_text("""
    <!DOCTYPE html>
    <html>
      <body>
        <h2>Portal</h2>
        <input id="inv_input" type="text" />
        <button id="post_btn" onclick="document.getElementById('status').innerText = 'Processed ' + document.getElementById('inv_input').value">Post</button>
        <span id="status">Waiting</span>
      </body>
    </html>
    """, encoding="utf-8")
    portal_url = html_file.as_uri()

    # 2. Build complete Workflow that:
    #   - Reads next item from queue
    #   - Runs custom Python script to calculate tax & total
    #   - Appends to Excel file
    #   - Fills browser form and clicks submit
    #   - Sets queue item status to SUCCESS
    workflow = Workflow(
        id="e2e_pipeline",
        name="Invoice Queue Processor",
        variables={"excel_path": str(excel_file), "portal_url": portal_url},
        nodes=[
            # Step 1: Pop queue item
            WorkflowNode(
                id="n_pop",
                type="queue.get_item",
                params={"queue_name": "InvoiceQueue"},
                output="current_item_payload",
            ),
            # Step 2: Custom Python script calculation
            WorkflowNode(
                id="n_calc",
                type="script.python",
                params={
                    "code": """
subtotal = item['subtotal']
tax = round(subtotal * 0.18, 2)
grand_total = round(subtotal + tax, 2)
context.set('tax_val', tax)
context.set('total_val', grand_total)
context.set('summary_str', f"{item['invoice_no']} - {item['client']} : ${grand_total}")
output = grand_total
"""
                },
                output="calc_total",
            ),
            # Step 3: Append to Excel
            WorkflowNode(
                id="n_excel",
                type="excel.append_row",
                params={
                    "file_path": "{{excel_path}}",
                    "sheet_name": "Invoices",
                    "row_data": ["{{item['invoice_no']}}", "{{item['client']}}", "{{total_val}}"],
                },
            ),
            # Step 4: Web Browser Automation
            WorkflowNode(
                id="n_web_open",
                type="web.open_browser",
                params={"url": "{{portal_url}}", "headless": True},
            ),
            WorkflowNode(
                id="n_web_type",
                type="web.type",
                params={"selector": "#inv_input", "text": "{{summary_str}}"},
            ),
            WorkflowNode(
                id="n_web_click",
                type="web.click",
                params={"selector": "#post_btn"},
            ),
            WorkflowNode(
                id="n_web_extract",
                type="web.get_text",
                params={"selector": "#status"},
                output="portal_status",
            ),
            WorkflowNode(
                id="n_web_close",
                type="web.close_browser",
                params={},
            ),
            # Step 5: Mark Queue Item SUCCESS
            WorkflowNode(
                id="n_queue_success",
                type="queue.set_status",
                params={
                    "status": "SUCCESS",
                    "output_data": {"grand_total": "{{total_val}}", "portal_response": "{{portal_status}}"},
                },
            ),
        ],
    )

    # First run: processes item1
    runner = WorkflowRunner(queue_manager=queue_mgr)
    result1 = runner.run(workflow)
    assert result1.success is True
    assert result1.variables["calc_total"] == 1416.0
    assert "Processed INV-101" in result1.variables["portal_status"]

    # Check item1 status in DB
    refreshed_item1 = queue_mgr.get_item(item1.id)
    assert refreshed_item1.status == QueueItemStatus.SUCCESS
    assert refreshed_item1.output_data["grand_total"] == 1416.0

    # Second run: processes item2
    result2 = runner.run(workflow)
    assert result2.success is True
    assert result2.variables["calc_total"] == 1003.0

    refreshed_item2 = queue_mgr.get_item(item2.id)
    assert refreshed_item2.status == QueueItemStatus.SUCCESS
    assert refreshed_item2.output_data["grand_total"] == 1003.0

    # Verify Excel file contains both appended records
    read_act = runner.run(
        Workflow(
            id="read_check",
            nodes=[
                WorkflowNode(
                    id="read_step",
                    type="excel.read_range",
                    params={"file_path": str(excel_file), "sheet_name": "Invoices", "has_headers": False},
                    output="all_rows",
                )
            ],
        )
    )
    rows = read_act.variables["all_rows"]
    assert len(rows) == 2
    assert rows[0][0] == "INV-101"
    assert rows[1][0] == "INV-102"

