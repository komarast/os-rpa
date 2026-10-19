import json
import subprocess
import time

import pytest
from playwright.sync_api import sync_playwright

from os_rpa.inspector import browsers
from os_rpa.inspector.web_picker import web_selectors_from_uia
from os_rpa.paths import module_cmd

PAGE = """<html><head><title>Attach Test</title></head><body>
<input name="user" placeholder="User name"><button id="go" onclick="document.title='clicked'">Go</button>
</body></html>"""


@pytest.fixture(scope="module")
def open_browser(tmp_path_factory):
    """An already running browser with a debug port, like a workflow's web.open_browser one."""
    html = tmp_path_factory.mktemp("attach") / "page.html"
    html.write_text(PAGE, encoding="utf-8")
    port = browsers.free_port()
    with sync_playwright() as pw:
        from os_rpa.actions.web import launch_with_fallback

        browser, _ = launch_with_fallback(
            pw.chromium.launch, "auto", headless=True, args=[f"--remote-debugging-port={port}"]
        )
        page = browser.new_page()
        page.goto(html.as_uri())
        yield {"port": port, "endpoint": f"http://127.0.0.1:{port}", "page": page, "url": html.as_uri()}
        browser.close()


def test_probe_lists_open_browser_tabs(open_browser):
    info = browsers.probe(open_browser["port"])
    assert info["endpoint"] == open_browser["endpoint"]
    assert any(p["title"] == "Attach Test" for p in info["pages"])


def test_registry_lists_workflow_browsers_and_prunes_dead(open_browser, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    browsers.register(open_browser["port"], "msedge")
    dead_port = browsers.free_port()
    browsers.register(dead_port, "msedge")

    found = {b["port"]: b for b in browsers.list_instances()}

    assert found[open_browser["port"]]["source"] == "workflow"
    assert dead_port not in found
    assert [e["port"] for e in json.loads(browsers.registry_file().read_text())] == [open_browser["port"]]
    browsers.unregister(open_browser["port"])
    assert json.loads(browsers.registry_file().read_text()) == []


def test_pick_in_open_browser_via_cli(open_browser):
    page = open_browser["page"]
    proc = subprocess.Popen(
        module_cmd(
            "os_rpa.inspector", "pick", "--target", "web", "--source", "cdp",
            "--endpoint", open_browser["endpoint"], "--timeout", "60",
        ),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.time() + 45
        while not page.evaluate("() => !!window.__osRpaPickerInstalled"):
            assert time.time() < deadline, "picker was not injected into the open browser"
            time.sleep(0.2)
        page.click("#go")
        out, err = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()

    res = json.loads(out.strip().splitlines()[-1])
    assert res["ok"] is True, res
    assert res["params"]["selector"] == "#go"
    assert res["params"]["url"] == open_browser["url"]
    # The browser stays open, the click never reached the page, and the overlay is removed
    assert page.title() == "Attach Test"
    assert page.evaluate("() => !!window.__osRpaPickerInstalled") is False
    assert page.evaluate("() => document.querySelector('[data-os-rpa-inspector]')") is None


def _validate_cli(open_browser, selector: str, timeout: str) -> dict:
    # Out of process like the server does (the fixture already owns Playwright in this thread)
    out = subprocess.run(
        module_cmd(
            "os_rpa.inspector", "validate", "--target", "web", "--endpoint", open_browser["endpoint"],
            "--url", open_browser["url"], "--timeout", timeout, "--params", json.dumps({"selector": selector}),
        ),
        capture_output=True, text=True, timeout=60,
    ).stdout
    return json.loads(out.strip().splitlines()[-1])


def test_validate_in_open_browser(open_browser):
    res = _validate_cli(open_browser, "input[name=user]", "5")
    assert res["ok"] is True and res["count"] == 1, res
    assert _validate_cli(open_browser, "#missing", "1")["count"] == 0
    assert open_browser["page"].title() == "Attach Test"


def test_web_selectors_from_accessibility_properties():
    sels = web_selectors_from_uia(
        {"automation_id": "login-btn", "name": "Log in", "control_type": "Button", "class_name": "btn btn-primary"}
    )
    assert [s["value"] for s in sels] == [
        "#login-btn",
        'role=button[name="Log in"]',
        'text="Log in"',
        ".btn.btn-primary",
    ]
    assert all(s["count"] == -1 for s in sels)
    assert web_selectors_from_uia({"automation_id": "a:b", "name": "", "control_type": "Edit"})[0]["value"] == '[id="a:b"]'
