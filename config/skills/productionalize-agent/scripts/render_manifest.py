"""Render .adlc.json as a self-contained HTML dashboard.

A double-clicked file:// HTML can't fetch a local JSON (browser security), so we
*inject* the manifest into the template (manifest_view_template.html) and write a
standalone viewable file.

Usage:
  python render_manifest.py [path/to/.adlc.json]   # default: ./.adlc.json
  -> writes <manifest_dir>/.adlc.view.html
"""

import json
import sys
from pathlib import Path

TEMPLATE = Path(__file__).with_name("manifest_view_template.html")


def main(argv) -> int:
    src = Path(argv[0]) if argv else Path(".adlc.json")
    if not src.exists():
        print(f"manifest not found: {src}", file=sys.stderr)
        return 1
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "__MANIFEST_JSON__", json.dumps(json.loads(src.read_text(encoding="utf-8")))
    )
    out = src.parent / ".adlc.view.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  (open it in a browser)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
