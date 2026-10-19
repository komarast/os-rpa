"""Web element picker: an in-page overlay highlights the hovered element; click captures it."""
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Kept in Python (not a .js file) so it ships inside packaged builds without data-file config.
# Installed as an init script, so it is re-injected on every navigation and in every frame.
PICKER_JS = r"""
(() => {
  if (window.__osRpaPickerInstalled) return;
  window.__osRpaPickerInstalled = true;
  window.__osRpaPick = null;

  const isTop = window === window.top;
  const GENERATED = /\d{4,}|[0-9a-f]{8,}|^(ember|react|mui|css|jsx|ext-gen|ng-|_)[-_]?\d/i;
  const TEXT_TAGS = new Set(['a', 'button', 'label', 'span', 'li', 'td', 'th', 'option', 'summary',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'strong', 'b', 'em', 'div']);

  const esc = (s) => (window.CSS && CSS.escape) ? CSS.escape(s) : String(s).replace(/([^\w-])/g, '\\$1');
  const quote = (s) => '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  const textOf = (el) => (el.textContent || '').replace(/\s+/g, ' ').trim();
  const cssCount = (sel) => { try { return document.querySelectorAll(sel).length; } catch (e) { return -1; } };
  const xpathCount = (xp) => {
    try {
      return document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null).snapshotLength;
    } catch (e) { return -1; }
  };
  const goodId = (el) => el.id && !GENERATED.test(el.id) && el.id.length <= 60 && cssCount('#' + esc(el.id)) === 1;

  function cssPath(el) {
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1) {
      if (cur !== el && goodId(cur)) { parts.unshift('#' + esc(cur.id)); break; }
      const tag = cur.tagName.toLowerCase();
      const parent = cur.parentElement;
      if (!parent) { parts.unshift(tag); break; }
      const same = Array.from(parent.children).filter((c) => c.tagName === cur.tagName);
      parts.unshift(same.length > 1 ? tag + ':nth-of-type(' + (same.indexOf(cur) + 1) + ')' : tag);
      cur = parent;
    }
    return parts.join(' > ');
  }

  function xPath(el) {
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1) {
      if (cur !== el && goodId(cur)) return '//*[@id=' + quote(cur.id) + ']/' + parts.join('/');
      const tag = cur.tagName.toLowerCase();
      const parent = cur.parentElement;
      const same = parent ? Array.from(parent.children).filter((c) => c.tagName === cur.tagName) : [cur];
      parts.unshift(same.length > 1 ? tag + '[' + (same.indexOf(cur) + 1) + ']' : tag);
      cur = parent;
    }
    return '/' + parts.join('/');
  }

  function candidates(el) {
    const tag = el.tagName.toLowerCase();
    const out = [];
    const add = (kind, value, count) => {
      if (value && !out.some((c) => c.value === value)) out.push({ kind, value, count, unique: count === 1 });
    };
    if (el.id && !GENERATED.test(el.id)) add('id', '#' + esc(el.id), cssCount('#' + esc(el.id)));
    for (const attr of ['data-testid', 'data-test-id', 'data-test', 'data-qa', 'data-cy', 'name', 'aria-label', 'placeholder', 'title']) {
      const v = el.getAttribute(attr);
      if (v && v.length <= 80) {
        const sel = tag + '[' + attr + '=' + quote(v) + ']';
        add(attr.startsWith('data-') ? 'test-id' : attr, sel, cssCount(sel));
      }
    }
    const text = textOf(el);
    if (TEXT_TAGS.has(tag) && text && text.length <= 60 && el.children.length <= 3) {
      const count = Array.from(document.querySelectorAll(tag)).filter((e) => textOf(e) === text).length;
      add('text', tag + ':text-is(' + quote(text) + ')', count);
    }
    const css = cssPath(el);
    add('css', css, cssCount(css));
    const xp = xPath(el);
    add('xpath', 'xpath=' + xp, xpathCount(xp));
    // Stable order: unique selectors first, otherwise by the priority above
    return out.map((c, i) => [c, i]).sort((a, b) => (b[0].unique - a[0].unique) || (a[1] - b[1])).map((p) => p[0]);
  }

  function describe(el) {
    const r = el.getBoundingClientRect();
    const attr = (n) => el.getAttribute(n) || '';
    return {
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      name: attr('name'),
      classes: typeof el.className === 'string' ? el.className.trim() : '',
      type: attr('type'),
      role: attr('role'),
      aria_label: attr('aria-label'),
      placeholder: attr('placeholder'),
      href: attr('href'),
      value: ('value' in el && typeof el.value === 'string') ? el.value.slice(0, 200) : '',
      text: textOf(el).slice(0, 200),
      rect: { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) },
      page_url: location.href,
      page_title: document.title,
      in_iframe: !isTop,
    };
  }

  function install() {
    if (!document.documentElement) return setTimeout(install, 30);
    const host = document.createElement('div');
    host.setAttribute('data-os-rpa-inspector', '');
    const shadow = host.attachShadow({ mode: 'closed' });
    shadow.innerHTML = `
      <style>
        .box { position: fixed; pointer-events: none; border: 2px solid #ff2d55; background: rgba(255,45,85,.12);
               z-index: 2147483647; display: none; box-sizing: border-box; border-radius: 2px; }
        .tip { position: fixed; pointer-events: none; z-index: 2147483647; background: #0f172a; color: #f8fafc;
               font: 12px 'Segoe UI', sans-serif; padding: 3px 7px; border-radius: 4px; display: none;
               max-width: 520px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .bar { position: fixed; bottom: 12px; right: 12px; z-index: 2147483647;
               background: #0f172a; color: #f8fafc; font: 13px 'Segoe UI', sans-serif; padding: 6px 10px;
               border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,.45); display: flex; gap: 10px;
               align-items: center; border: 1px solid #38bdf8; }
        .bar button { font: 600 12px 'Segoe UI', sans-serif; border: none; border-radius: 4px; padding: 4px 9px; cursor: pointer; }
        .toggle { background: #38bdf8; color: #0f172a; }
        .cancel { background: #334155; color: #f8fafc; }
      </style>
      <div class="box"></div><div class="tip"></div>
      ${isTop ? '<div class="bar"><span class="msg"></span><button class="toggle"></button><button class="cancel">Cancel (Esc)</button></div>' : ''}`;
    document.documentElement.appendChild(host);

    const box = shadow.querySelector('.box');
    const tip = shadow.querySelector('.tip');
    const msg = shadow.querySelector('.msg');
    const toggleBtn = shadow.querySelector('.toggle');
    let active = true;
    let done = false;

    const render = () => {
      if (!msg) return;
      msg.textContent = active
        ? 'OS RPA Inspector: click an element to select it'
        : 'Inspector paused: use the page normally (log in, navigate...)';
      toggleBtn.textContent = active ? 'Pause (F2)' : 'Resume picking (F2)';
      if (!active) { box.style.display = 'none'; tip.style.display = 'none'; }
    };
    const setActive = (v) => { active = v; render(); };

    const targetOf = (e) => {
      const path = e.composedPath ? e.composedPath() : [e.target];
      if (path.includes(host)) return null;
      const el = path.find((n) => n && n.nodeType === 1 && n.getRootNode() === document);
      return el || null;
    };
    const showBox = (el, color) => {
      const r = el.getBoundingClientRect();
      Object.assign(box.style, {
        display: 'block', left: r.left + 'px', top: r.top + 'px', width: r.width + 'px', height: r.height + 'px',
        borderColor: color, background: color === '#22c55e' ? 'rgba(34,197,94,.15)' : 'rgba(255,45,85,.12)',
      });
      return r;
    };

    const onMove = (e) => {
      if (!active || done) return;
      const el = targetOf(e);
      if (!el) return;
      const r = showBox(el, '#ff2d55');
      const cls = typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
      tip.textContent = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + cls + '  ' + textOf(el).slice(0, 40);
      Object.assign(tip.style, { display: 'block', left: Math.max(0, r.left) + 'px', top: (r.top > 26 ? r.top - 24 : r.bottom + 4) + 'px' });
    };
    const block = (e) => {
      if (!active || done || !targetOf(e)) return;
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
    };
    const onClick = (e) => {
      if (!active || done) return;
      const el = targetOf(e);
      if (!el) return;
      block(e);
      done = true;
      showBox(el, '#22c55e');
      tip.textContent = 'Captured - return to OS RPA Studio';
      const cands = candidates(el);
      window.__osRpaPick = { element: describe(el), selectors: cands, best: cands.length ? cands[0].value : '' };
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { block(e); done = true; window.__osRpaPick = { cancelled: true }; }
      else if (e.key === 'F2') { e.preventDefault(); setActive(!active); }
    };

    const BLOCKED = ['mousedown', 'mouseup', 'pointerdown', 'pointerup', 'dblclick', 'contextmenu', 'auxclick'];
    window.addEventListener('mousemove', onMove, true);
    for (const t of BLOCKED) window.addEventListener(t, block, true);
    window.addEventListener('click', onClick, true);
    window.addEventListener('keydown', onKey, true);

    // Attached (already open) browsers stay open after a pick, so the picker must remove itself
    window.__osRpaPickerUninstall = () => {
      window.removeEventListener('mousemove', onMove, true);
      for (const t of BLOCKED) window.removeEventListener(t, block, true);
      window.removeEventListener('click', onClick, true);
      window.removeEventListener('keydown', onKey, true);
      host.remove();
      window.__osRpaPick = null;
      window.__osRpaPickerInstalled = false;
    };
    if (toggleBtn) {
      toggleBtn.addEventListener('click', (e) => { e.stopPropagation(); setActive(!active); });
      shadow.querySelector('.cancel').addEventListener('click', (e) => {
        e.stopPropagation(); done = true; window.__osRpaPick = { cancelled: true };
      });
    }
    render();
  }

  install();
})();
"""

UNINSTALL_JS = "() => { if (window.__osRpaPickerUninstall) window.__osRpaPickerUninstall(); }"

# Self-removing outline used to show a validated match inside an attached browser
FLASH_JS = """el => {
  const prev = el.style.outline, prevOffset = el.style.outlineOffset;
  el.scrollIntoView({block: 'center', inline: 'center'});
  el.style.outline = '3px solid #22c55e';
  el.style.outlineOffset = '2px';
  setTimeout(() => { el.style.outline = prev; el.style.outlineOffset = prevOffset; }, 2500);
}"""


def _profile_dir() -> str:
    """Persistent browser profile so logins/cookies survive between inspections."""
    path = Path("data") / "inspector_profile"
    path.mkdir(parents=True, exist_ok=True)
    return str(path.resolve())


def _open(pw, channel: str):
    from os_rpa.actions.web import launch_with_fallback

    if channel in ("", "auto") and not Path(pw.chromium.executable_path).exists():
        channel = "msedge"  # bundled browser not downloaded; skip the failing launch attempt
    ctx, browser_name = launch_with_fallback(
        pw.chromium.launch_persistent_context,
        channel,
        user_data_dir=_profile_dir(),
        headless=False,
        no_viewport=True,
        args=["--start-maximized"],
    )
    return ctx, browser_name


def _poll_pick(ctx) -> Optional[Dict[str, Any]]:
    for page in list(ctx.pages):
        for frame in list(page.frames):
            try:
                res = frame.evaluate("() => window.__osRpaPick || null")
            except Exception:
                continue  # navigating or detached
            if res:
                res["frame_url"] = frame.url
                res["is_main_frame"] = frame == page.main_frame
                return res
    return None


def _pick_result(res: Dict[str, Any], browser_name: str) -> Dict[str, Any]:
    if res.get("cancelled"):
        return {"ok": False, "cancelled": True, "error": "Selection cancelled"}
    warnings = []
    if not res.get("is_main_frame"):
        warnings.append(f"Element is inside an iframe ({res.get('frame_url')}); web activities act on the main page.")
    if res["selectors"] and not res["selectors"][0]["unique"]:
        warnings.append("No unique selector found; the best candidate matches several elements.")
    return {
        "ok": True,
        "target": "web",
        "browser": browser_name,
        "element": res["element"],
        "selectors": res["selectors"],
        "params": {"selector": res.get("best", ""), "url": res["element"].get("page_url", "")},
        "warnings": warnings,
    }


def _all_frames(browser):
    for ctx in browser.contexts:
        for page in ctx.pages:
            for frame in page.frames:
                yield page, frame


def pick(
    url: str = "", timeout: float = 120, channel: str = "auto", source: str = "new", endpoint: str = ""
) -> Dict[str, Any]:
    """source: 'new' (launch an inspector browser), 'cdp' (attach to an open browser at `endpoint`),
    or 'window' (any open browser window, via its accessibility tree)."""
    if source == "cdp":
        return pick_attached(endpoint, timeout)
    if source == "window":
        return pick_from_window(timeout)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx, browser_name = _open(pw, channel)
        try:
            ctx.add_init_script(PICKER_JS)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if url:
                page.goto(url, wait_until="domcontentloaded")
            else:
                page.evaluate(PICKER_JS)  # init scripts don't run on the initial about:blank
            page.bring_to_front()

            deadline = time.time() + timeout
            res = None
            while time.time() < deadline:
                if not ctx.pages:
                    return {"ok": False, "cancelled": True, "error": "Browser was closed"}
                res = _poll_pick(ctx)
                if res:
                    break
                time.sleep(0.25)
            if not res:
                return {"ok": False, "error": f"No element selected within {int(timeout)}s"}
            return _pick_result(res, browser_name)
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def pick_attached(endpoint: str, timeout: float = 120) -> Dict[str, Any]:
    """Picks in an already open browser (debug port). The browser is left open; the picker overlay is
    injected into every tab/frame (re-injected after navigations) and removed afterwards."""
    from playwright.sync_api import sync_playwright

    if not endpoint:
        raise ValueError("No browser endpoint to attach to")
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(endpoint, timeout=15000)
        try:
            for _, frame in _all_frames(browser):  # drop leftovers of an interrupted session
                try:
                    frame.evaluate(UNINSTALL_JS)
                except Exception:
                    pass
            deadline = time.time() + timeout
            while time.time() < deadline:
                if not browser.is_connected():
                    return {"ok": False, "cancelled": True, "error": "Browser was closed"}
                for page, frame in list(_all_frames(browser)):
                    try:
                        if not frame.evaluate("() => !!window.__osRpaPickerInstalled"):
                            frame.evaluate(PICKER_JS)
                        res = frame.evaluate("() => window.__osRpaPick || null")
                    except Exception:
                        continue  # navigating or detached
                    if res:
                        res["frame_url"] = frame.url
                        res["is_main_frame"] = frame == page.main_frame
                        return _pick_result(res, browser.version)
                time.sleep(0.25)
            return {"ok": False, "error": f"No element selected within {int(timeout)}s"}
        finally:
            for _, frame in list(_all_frames(browser)):
                try:
                    frame.evaluate(UNINSTALL_JS)
                except Exception:
                    pass
            # Leaving sync_playwright disconnects without closing the user's browser


# UI Automation control types of Chromium web content -> ARIA roles usable in `role=` selectors
UIA_ROLES = {
    "Button": "button", "Hyperlink": "link", "Edit": "textbox", "CheckBox": "checkbox",
    "RadioButton": "radio", "ComboBox": "combobox", "ListItem": "listitem", "MenuItem": "menuitem",
    "TabItem": "tab", "Image": "img", "Header": "heading", "Table": "table", "List": "list",
    "Slider": "slider", "Spinner": "spinbutton", "Tree": "tree", "TreeItem": "treeitem",
}


def _quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def web_selectors_from_uia(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Selector candidates from a web element's accessibility properties (Chromium maps the HTML id to
    AutomationId and the class attribute to ClassName). Match counts are unknown (-1) until validated."""
    out: List[Dict[str, Any]] = []

    def add(kind: str, value: str):
        if value and not any(c["value"] == value for c in out):
            out.append({"kind": kind, "value": value, "count": -1, "unique": False})

    aid = info.get("automation_id", "")
    if aid:
        add("id", f"#{aid}" if re.fullmatch(r"[A-Za-z_][\w-]*", aid) else f"[id={_quote(aid)}]")
    name = (info.get("name") or "").strip()
    role = UIA_ROLES.get(info.get("control_type", ""))
    if role and name and len(name) <= 80:
        add("role", f"role={role}[name={_quote(name)}]")
    if name and len(name) <= 60:
        add("text", f"text={_quote(name)}")
    classes = [c for c in (info.get("class_name") or "").split() if re.fullmatch(r"[A-Za-z_][\w-]*", c)]
    if classes:
        add("css", "." + ".".join(classes[:2]))
    return out


def pick_from_window(timeout: float = 120) -> Dict[str, Any]:
    """Picks in any open browser window (no debug port needed) via UI Automation."""
    from os_rpa.inspector import desktop_picker

    control, failure = desktop_picker.pick_control(timeout, hint="Ctrl = select web element    Esc = cancel")
    if failure:
        return failure

    document = control
    for _ in range(64):
        if document is None or document.ControlTypeName == "DocumentControl":
            break
        document = document.GetParentControl()
    if document is None:
        return {"ok": False, "error": "The selected element is not inside a web page"}
    page_url = ""
    try:
        page_url = document.GetValuePattern().Value or ""
    except Exception:
        pass

    info = desktop_picker.describe_control(control)
    element = {
        "tag": info["control_type"].lower(),
        "id": info["automation_id"],
        "classes": info["class_name"],
        "text": info["name"],
        "value": info["value"],
        "page_url": page_url,
        "page_title": document.Name or info["window_title"],
        "browser_window": info["window_title"],
    }
    selectors = web_selectors_from_uia(info)
    if not selectors:
        return {"ok": False, "error": "The element has no id, accessible name or class to build a selector from"}
    return {
        "ok": True,
        "target": "web",
        "element": element,
        "selectors": selectors,
        "params": {"selector": selectors[0]["value"], "url": page_url},
        "warnings": [
            "Selectors were read from the browser's accessibility tree; use Validate to check they match exactly one element."
        ],
    }


def validate_attached(endpoint: str, selector: str, page_url: str = "", timeout: float = 10) -> Dict[str, Any]:
    """Counts matches in the open browser tab showing `page_url` (else the first tab) and outlines the first."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(endpoint, timeout=15000)
        pages = [p for ctx in browser.contexts for p in ctx.pages]
        if not pages:
            raise RuntimeError("The browser has no open tabs")
        page = next((p for p in pages if page_url and p.url == page_url), None) or next(
            (p for p in pages if page_url and p.url.split("#")[0] == page_url.split("#")[0]), pages[0]
        )
        locator = page.locator(selector)
        try:
            locator.first.wait_for(state="attached", timeout=timeout * 1000)
        except Exception:
            pass
        count = locator.count()
        element = None
        if count:
            element = locator.first.evaluate(
                "el => ({tag: el.tagName.toLowerCase(), id: el.id || '', "
                "text: (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 200)})"
            )
            locator.first.evaluate(FLASH_JS)
        return {"ok": True, "target": "web", "found": count > 0, "count": count, "unique": count == 1,
                "element": element, "page_url": page.url}


def validate(
    url: str, selector: str, timeout: float = 10, channel: str = "auto", endpoint: str = ""
) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    if not selector:
        raise ValueError("A selector is required")
    if endpoint:
        return validate_attached(endpoint, selector, url, timeout)
    if not url:
        raise ValueError("A page URL is required to validate a web selector")

    with sync_playwright() as pw:
        ctx, _ = _open(pw, channel)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")
            locator = page.locator(selector)
            try:
                locator.first.wait_for(state="attached", timeout=timeout * 1000)
            except Exception:
                pass
            count = locator.count()
            element = None
            if count:
                element = locator.first.evaluate(
                    "el => ({tag: el.tagName.toLowerCase(), id: el.id || '', "
                    "text: (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 200)})"
                )
                locator.first.scroll_into_view_if_needed()
                locator.first.highlight()
                page.wait_for_timeout(2000)
            return {
                "ok": True,
                "target": "web",
                "found": count > 0,
                "count": count,
                "unique": count == 1,
                "element": element,
            }
        finally:
            try:
                ctx.close()
            except Exception:
                pass
