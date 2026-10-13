import pytest
from starlette.testclient import TestClient
from os_rpa.server.app import app
from os_rpa.paths import studio_dist


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


@pytest.mark.skipif(not studio_dist().exists(), reason="Studio not built: run `npm run build` in studio/")
def test_api_serves_studio_ui(client: TestClient):
    # Tests that static build index.html is served at root
    res = client.get("/")
    assert res.status_code == 200
    assert "OS RPA Studio" in res.text or "<div id=\"root\">" in res.text



def test_debug_ws_streams_and_edits_variables(client: TestClient):
    wf = {
        "id": "wf_ws_vars",
        "name": "WS Vars",
        "variables": {},
        "nodes": [
            {"id": "n1", "type": "logic.set_variable", "params": {"variable_name": "count", "value": 1}},
            {"id": "n2", "type": "logic.set_variable", "params": {"variable_name": "total", "value": "{{count + 1}}"}},
        ],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
    }

    def read_until(ws, event):
        while True:
            msg = ws.receive_json()
            if msg["event"] == event:
                return msg

    with client.websocket_connect("/ws/debug") as ws:
        ws.send_json({"workflow": wf, "breakpoints": ["n2"]})
        paused = read_until(ws, "paused")
        assert paused["node_id"] == "n2"
        assert paused["variables"]["count"] == 1
        assert paused["meta"]["count"]["source"] == "n1"

        ws.send_json({"cmd": "set_variable", "name": "count", "value": 41})
        snap = read_until(ws, "variables")
        assert snap["variables"]["count"] == 41
        assert snap["meta"]["count"]["source"] == "debugger"

        ws.send_json({"cmd": "set_variable", "name": "bad name", "value": 1})
        assert "Invalid variable name" in read_until(ws, "variable_error")["message"]

        ws.send_json({"cmd": "resume"})
        finished = read_until(ws, "finished")
        assert finished["result"]["variables"]["total"] == 42
