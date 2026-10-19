import sys

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from os_rpa.inspector.desktop_picker import suggest_params
from os_rpa.inspector.service import InspectorService
from os_rpa.inspector.web_picker import PICKER_JS
from os_rpa.server.app import app

PAGE = """
<!DOCTYPE html>
<html><head><title>Inspector Test</title></head>
<body>
  <form>
    <input id="username" name="user" />
    <input name="q" placeholder="Search products" />
    <input name="q" placeholder="Search orders" />
    <button id="submit-1712345678" type="button" onclick="document.title='clicked'">Log in</button>
  </form>
  <ul><li>Apples</li><li>Pears</li><li>Pears</li></ul>
  <div data-testid="banner"><span>Hello</span></div>
</body></html>
"""


@pytest.fixture(scope="module")
def page_url(tmp_path_factory):
    html = tmp_path_factory.mktemp("inspector") / "page.html"
    html.write_text(PAGE, encoding="utf-8")
    return html.as_uri()


def _open(page, url: str):
    # A real navigation gives a fresh window, like the init script sees in the inspector browser
    page.goto(url)
    page.evaluate(PICKER_JS)


@pytest.fixture(scope="module")
def page():
    with sync_playwright() as pw:
        from os_rpa.actions.web import launch_with_fallback

        browser, _ = launch_with_fallback(pw.chromium.launch, "auto", headless=True)
        pg = browser.new_page()
        yield pg
        browser.close()


def _pick(page, url: str, selector: str) -> dict:
    _open(page, url)
    title_before = page.title()
    page.click(selector)
    res = page.evaluate("() => window.__osRpaPick")
    assert page.title() == title_before, "picker must swallow the click so the page doesn't react"
    return res


@pytest.mark.parametrize(
    "target, expected_best",
    [
        ("#username", "#username"),
        ("input[placeholder='Search orders']", 'input[placeholder="Search orders"]'),
        ("div[data-testid=banner]", 'div[data-testid="banner"]'),
        ("ul li:nth-child(1)", 'li:text-is("Apples")'),
    ],
)
def test_web_picker_best_selector(page, page_url, target, expected_best):
    res = _pick(page, page_url, target)
    assert res["best"] == expected_best
    assert res["selectors"][0]["unique"] is True


def test_web_picker_skips_generated_ids_and_selectors_resolve(page, page_url):
    res = _pick(page, page_url, "button")
    assert res["element"]["tag"] == "button"
    assert res["element"]["text"] == "Log in"
    assert not res["best"].startswith("#submit-")
    for cand in res["selectors"]:
        count = page.locator(cand["value"]).count()
        assert count == cand["count"], cand
    assert all(page.locator(c["value"]).count() == 1 for c in res["selectors"] if c["unique"])


def test_web_picker_ambiguous_element_falls_back_to_unique_path(page, page_url):
    res = _pick(page, page_url, "ul li:nth-child(3)")
    by_kind = {c["kind"]: c for c in res["selectors"]}
    assert by_kind["text"]["unique"] is False  # two "Pears"
    assert res["selectors"][0]["unique"] is True
    assert page.locator(res["best"]).inner_text() == "Pears"
    assert page.locator(res["best"]).evaluate("el => el === el.parentElement.children[2]")


def test_web_picker_escape_cancels(page, page_url):
    _open(page, page_url)
    page.keyboard.press("Escape")
    assert page.evaluate("() => window.__osRpaPick") == {"cancelled": True}


def test_desktop_suggest_params_maps_activity_fields():
    params = suggest_params(
        {"name": "Save", "automation_id": "btnSave", "control_type": "Button", "window_title": "Editor"}
    )
    assert params == {
        "name": "Save",
        "automation_id": "btnSave",
        "control_type": "Button",
        "window_title": "Editor",
        "title": "Editor",
    }


@pytest.mark.skipif(sys.platform != "win32", reason="UI Automation is Windows-only")
def test_desktop_describe_real_control():
    import uiautomation as auto
    from os_rpa.inspector.desktop_picker import describe_control

    root = auto.GetRootControl()
    window = root.GetFirstChildControl() if root else None
    if not window:
        window = root
    if not window:
        pytest.skip("No desktop window accessible in current session")
    info = describe_control(window)
    assert set(info) >= {"name", "automation_id", "control_type", "window_title", "rect", "path"}
    assert info["path"], "path should contain at least the element itself"


def test_service_parses_last_json_line():
    out = 'noise from a library\n{"ok": true, "target": "web"}\n'
    assert InspectorService._parse(out, "") == {"ok": True, "target": "web"}
    assert InspectorService._parse("", "Traceback...\nBoom")["error"] == "Boom"


def test_inspector_api_rejects_unknown_target():
    client = TestClient(app)
    assert client.post("/api/inspector/pick", json={"target": "mainframe"}).status_code == 400
    assert client.post("/api/inspector/cancel").json() == {"cancelled": False}


def test_inspector_cli_validate_reports_errors():
    from os_rpa.inspector.__main__ import main

    # Web validation without a URL fails fast with a readable error instead of opening a browser
    assert main(["validate", "--target", "web", "--params", '{"selector": "#x"}']) == 1
