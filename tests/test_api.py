import pytest
from starlette.testclient import TestClient
from os_rpa.server.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_list_actions(client: TestClient):
    response = client.get("/api/actions")
    assert response.status_code == 200
    actions = response.json()
    assert len(actions) > 0
    types = [a["type"] for a in actions]
    assert "queue.get_item" in types
    assert "web.open_browser" in types
    assert "excel.append_row" in types
    assert "script.python" in types


def test_api_queues_lifecycle(client: TestClient):
    # Add an item
    post_res = client.post(
        "/api/queues/items",
        json={
            "queue_name": "ApiTestQueue",
            "payload": {"client_id": 42, "item": "widget"},
            "priority": 5,
        },
    )
    assert post_res.status_code == 200
    item = post_res.json()
    assert item["queue_name"] == "ApiTestQueue"
    assert item["status"] == "NEW"

    # List queues
    queues_res = client.get("/api/queues")
    assert queues_res.status_code == 200
    queues = queues_res.json()
    target_q = next((q for q in queues if q["queue_name"] == "ApiTestQueue"), None)
    assert target_q is not None
    assert target_q["total_items"] >= 1

    # List items in queue
    items_res = client.get("/api/queues/ApiTestQueue/items")
    assert items_res.status_code == 200
    items = items_res.json()
    assert any(i["id"] == item["id"] for i in items)


def test_api_workflows_save_and_run(client: TestClient):
    wf_payload = {
        "id": "api_test_wf",
        "name": "API Workflow",
        "variables": {"factor": 3},
        "nodes": [
            {
                "id": "calc",
                "type": "script.python",
                "params": {"code": "context.set('val', variables['factor'] * 7)"},
                "output": "res",
            }
        ],
        "edges": [],
    }

    # Save
    save_res = client.post("/api/workflows", json=wf_payload)
    assert save_res.status_code == 200

    # List
    list_res = client.get("/api/workflows")
    assert list_res.status_code == 200
    assert any(w["id"] == "api_test_wf" for w in list_res.json())

    # Run
    run_res = client.post(
        "/api/workflows/run",
        json={"workflow": wf_payload},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["success"] is True
    assert run_data["variables"]["val"] == 21


def test_api_serves_studio_ui(client: TestClient):
    # Tests that static build index.html is served at root
    res = client.get("/")
    assert res.status_code == 200
    assert "OS RPA Studio" in res.text or "<div id=\"root\">" in res.text

