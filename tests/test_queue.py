import pytest
from pathlib import Path
from os_rpa.queue.manager import QueueManager
from os_rpa.models import QueueItemStatus


@pytest.fixture
def temp_queue_mgr(tmp_path: Path):
    db_file = tmp_path / "test_queues.db"
    return QueueManager(str(db_file))


def test_add_and_get_next_item(temp_queue_mgr: QueueManager):
    item1 = temp_queue_mgr.add_item("InvoiceQueue", {"invoice_no": "INV-001", "amount": 100}, priority=1)
    item2 = temp_queue_mgr.add_item("InvoiceQueue", {"invoice_no": "INV-002", "amount": 500}, priority=10)

    # item2 has higher priority, should be retrieved first
    next_item = temp_queue_mgr.get_next_item("InvoiceQueue")
    assert next_item is not None
    assert next_item.id == item2.id
    assert next_item.status == QueueItemStatus.IN_PROGRESS
    assert next_item.payload["invoice_no"] == "INV-002"

    # item1 should be retrieved next
    next_item_2 = temp_queue_mgr.get_next_item("InvoiceQueue")
    assert next_item_2 is not None
    assert next_item_2.id == item1.id
    assert next_item_2.status == QueueItemStatus.IN_PROGRESS

    # No more items
    assert temp_queue_mgr.get_next_item("InvoiceQueue") is None


def test_set_status(temp_queue_mgr: QueueManager):
    item = temp_queue_mgr.add_item("OrderQueue", {"order_id": 999})
    in_prog = temp_queue_mgr.get_next_item("OrderQueue")
    assert in_prog is not None

    success_item = temp_queue_mgr.set_status(
        in_prog.id,
        QueueItemStatus.SUCCESS,
        output_data={"processed_by": "robot_1"},
    )
    assert success_item.status == QueueItemStatus.SUCCESS
    assert success_item.output_data == {"processed_by": "robot_1"}


def test_fail_and_retry(temp_queue_mgr: QueueManager):
    item = temp_queue_mgr.add_item("RetryQueue", {"data": "test"}, max_retries=2)
    p = temp_queue_mgr.get_next_item("RetryQueue")

    # First failure -> should become NEW again with retry_count=1
    retried_1 = temp_queue_mgr.fail_and_retry(p.id, "Network timeout")
    assert retried_1.status == QueueItemStatus.NEW
    assert retried_1.retry_count == 1

    # Second pickup & failure -> should become NEW again with retry_count=2
    p2 = temp_queue_mgr.get_next_item("RetryQueue")
    retried_2 = temp_queue_mgr.fail_and_retry(p2.id, "Network timeout 2")
    assert retried_2.status == QueueItemStatus.NEW
    assert retried_2.retry_count == 2

    # Third failure -> exceeds max_retries (2), should now become FAILED
    p3 = temp_queue_mgr.get_next_item("RetryQueue")
    failed = temp_queue_mgr.fail_and_retry(p3.id, "Network timeout 3")
    assert failed.status == QueueItemStatus.FAILED
    assert failed.retry_count == 3


def test_list_queues(temp_queue_mgr: QueueManager):
    temp_queue_mgr.add_item("Q1", {"a": 1})
    temp_queue_mgr.add_item("Q1", {"a": 2})
    temp_queue_mgr.add_item("Q2", {"b": 1})

    summary = temp_queue_mgr.list_queues()
    assert len(summary) == 2
    q1_summary = next(q for q in summary if q["queue_name"] == "Q1")
    assert q1_summary["total_items"] == 2
    assert q1_summary["new_items"] == 2

