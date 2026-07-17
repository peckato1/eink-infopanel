#!/usr/bin/env python3
"""Generate an HTML page showing the CHMI icon code -> Lucide icon mapping.

Writes ``icon_mapping.html`` next to the server package. CHMI source icons are
referenced from chmi.cz; Lucide icons from the local ``assets/icons`` directory.

Usage: uv run python tools/icon_mapping_page.py [output.html]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.data.chmi import _ICON_MAP

CHMI_URL = "https://www.chmi.cz/o/chmu-theme/images/icon/{code}.svg"


def build_html() -> str:
    cells = []
    for code in sorted(_ICON_MAP):
        lucide = _ICON_MAP[code]
        cells.append(
            f'<figure><div class="pair">'
            f'<img class="chmi" src="{CHMI_URL.format(code=code)}" alt="CHMI {code}">'
            f'<span class="arrow">&rarr;</span>'
            f'<img class="lucide" src="assets/icons/{lucide}.png" alt="{lucide}">'
            f'</div><figcaption><b>{code}</b> {lucide}</figcaption></figure>'
        )
    grid = "\n".join(cells)
    return f"""<!doctype html>
<meta charset="utf-8">
<title>CHMI &rarr; Lucide icon mapping</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem 0.5rem; background: #f4f7fa; color: #16212c; }}
  h1 {{ font-size: 1.4rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }}
  figure {{ margin: 0; background: #fff; border: 1px solid #d4dee8; border-radius: 8px; padding: 4px; }}
  .pair {{ display: flex; align-items: center; justify-content: center; gap: 10px; }}
  .pair img {{ width: 48px; height: 48px; }}
  .lucide {{ filter: none; }}
  .arrow {{ color: #2f6fb0; font-size: 1.5rem; }}
  figcaption {{ text-align: center; margin-top: 6px; font-size: 13px; color: #5b6b7c; }}
  figcaption b {{ color: #16212c; font-family: ui-monospace, monospace; }}
</style>
<h1>CHMI meteogram icon code &rarr; Lucide icon ({len(_ICON_MAP)} codes)</h1>
<div class="grid">
{grid}
</div>
"""


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "icon_mapping.html"
    out.write_text(build_html(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
