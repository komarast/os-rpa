from pathlib import Path
from os_rpa.actions.registry import ActionRegistry
from os_rpa.actions.web import PlaywrightSession
from os_rpa.engine.context import ExecutionContext


def test_playwright_actions(tmp_path: Path):
    # Create a small local HTML file to test without external internet dependence
    html_file = tmp_path / "test.html"
    html_file.write_text("""
    <!DOCTYPE html>
    <html>
      <head><title>OS RPA Test Page</title></head>
      <body>
        <h1 id="header">Welcome to RPA</h1>
        <input id="username" type="text" />
        <button id="submit-btn" onclick="document.getElementById('header').innerText = 'Clicked!'">Submit</button>
      </body>
    </html>
    """, encoding="utf-8")

    file_url = html_file.as_uri()
    ctx = ExecutionContext()

    try:
        # 1. Open Browser
        open_act = ActionRegistry.get("web.open_browser")
        res = open_act.execute({"url": file_url, "headless": True}, ctx)
        assert "OS RPA Test Page" in res["title"]

        # 2. Type text
        type_act = ActionRegistry.get("web.type")
        typed = type_act.execute({"selector": "#username", "text": "robot_user"}, ctx)
        assert typed == "robot_user"

        # 3. Get text
        get_act = ActionRegistry.get("web.get_text")
        initial_text = get_act.execute({"selector": "#header"}, ctx)
        assert initial_text == "Welcome to RPA"

        # 4. Click button
        click_act = ActionRegistry.get("web.click")
        click_act.execute({"selector": "#submit-btn"}, ctx)

        # 5. Verify text changed
        new_text = get_act.execute({"selector": "#header"}, ctx)
        assert new_text == "Clicked!"

        # 6. Screenshot
        ss_path = tmp_path / "web_test.png"
        ss_act = ActionRegistry.get("web.screenshot")
        ss_act.execute({"output_path": str(ss_path)}, ctx)
        assert ss_path.exists()

    finally:
        # Close browser
        close_act = ActionRegistry.get("web.close_browser")
        close_act.execute({}, ctx)

