"""python -m os_rpa.inspector pick|validate --target desktop|web ...

Prints a single JSON object on the last stdout line: {"ok": true, ...} or {"ok": false, "error": ...}.
"""
import argparse
import json
import sys
import traceback


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="OS RPA element inspector")
    parser.add_argument("command", choices=["pick", "validate"])
    parser.add_argument("--target", choices=["desktop", "web"], required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--channel", default="auto")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--params", default="{}", help="JSON object of activity params to validate")
    parser.add_argument("--source", choices=["new", "cdp", "window"], default="new",
                        help="web: launch a new browser, attach to an open one (--endpoint), or any open window")
    parser.add_argument("--endpoint", default="", help="CDP endpoint of an open browser, e.g. http://127.0.0.1:9222")
    args = parser.parse_args(argv)

    try:
        if args.target == "desktop":
            from os_rpa.inspector import desktop_picker as picker
        else:
            from os_rpa.inspector import web_picker as picker

        if args.command == "pick":
            if args.target == "web":
                result = picker.pick(
                    url=args.url, timeout=args.timeout, channel=args.channel,
                    source=args.source, endpoint=args.endpoint,
                )
            else:
                result = picker.pick(timeout=args.timeout)
        else:
            params = json.loads(args.params or "{}")
            if args.target == "web":
                result = picker.validate(
                    url=args.url or params.get("url", ""),
                    selector=str(params.get("selector") or ""),
                    timeout=args.timeout,
                    channel=args.channel,
                    endpoint=args.endpoint,
                )
            else:
                result = picker.validate(params, timeout=args.timeout)
    except Exception as e:
        result = {"ok": False, "error": str(e), "traceback": traceback.format_exc()}

    sys.stdout.write("\n" + json.dumps(result, default=str) + "\n")
    sys.stdout.flush()
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
