#!/usr/bin/env python3
"""ADLC wizard — phase teaching menu.

Static content lives in ../references/curriculum.json (no LLM generation).

Usage:
  teach.py                 # interactive TUI (like /powerup): arrows + enter, q to quit
  teach.py --print <phase> # print one phase's explainer (non-interactive; for the orchestrator)
  teach.py --list          # list phase keys
"""
import json
import sys
from pathlib import Path

CURRICULUM = Path(__file__).resolve().parent.parent / "references" / "curriculum.json"


def load():
    return json.loads(CURRICULUM.read_text(encoding="utf-8"))["phases"]


def render_text(p: dict) -> str:
    lines = [f"  {p['title']} — what this stage is", "", f"  {p['what']}", "", "  What's in it:"]
    lines += [f"    • {x}" for x in p["in_it"]]
    lines += ["", "  Why it matters:", f"    {p['why']}"]
    if p.get("analogies"):
        lines += ["", "  Like traditional testing:"]
        lines += [f"    • {a['concept']} ≈ {a['like']}" for a in p["analogies"]]
    if p.get("links"):
        lines += ["", "  Learn more:"]
        lines += [f"    → {l['label']}: {l['url']}" for l in p["links"]]
    return "\n".join(lines)


def cmd_print(key: str) -> int:
    for p in load():
        if p["key"] == key:
            print(render_text(p))
            return 0
    print(f"unknown phase: {key} (use --list)", file=sys.stderr)
    return 1


def cmd_teaser(key: str) -> int:
    for p in load():
        if p["key"] == key:
            print(p["teaser"])
            return 0
    print(f"unknown phase: {key} (use --list)", file=sys.stderr)
    return 1


def cmd_list() -> int:
    print(" ".join(p["key"] for p in load()))
    return 0


def tui() -> int:
    import curses

    phases = load()

    def app(stdscr):
        curses.curs_set(0)
        curses.use_default_colors()
        for i in range(1, 7):
            curses.init_pair(i, i, -1)
        CYAN, GREEN, YELLOW, GREY = 6, 2, 3, 0
        idx, detail = 0, False

        def breadcrumb(win, row):
            win.addstr(row, 2, "ADLC  ", curses.A_BOLD)
            for i, p in enumerate(phases):
                mark = "▶" if i == idx else "○"
                attr = curses.color_pair(CYAN) | curses.A_BOLD if i == idx else curses.A_DIM
                win.addstr(f"{mark} {p['title']}  ", attr)

        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            breadcrumb(stdscr, 0)
            stdscr.addstr(1, 2, "─" * (w - 4), curses.A_DIM)
            if not detail:
                stdscr.addstr(3, 2, "Pick a stage to learn about it:", curses.A_BOLD)
                for i, p in enumerate(phases):
                    sel = i == idx
                    prefix = "  ❯ " if sel else "    "
                    attr = curses.color_pair(GREEN) | curses.A_BOLD if sel else curses.A_NORMAL
                    stdscr.addstr(5 + i, 2, f"{prefix}{p['title']:<10} {p['what']}"[: w - 4], attr)
                stdscr.addstr(h - 2, 2, "↑/↓ move    enter view   q quit", curses.A_DIM)
            else:
                p = phases[idx]
                stdscr.addstr(3, 2, p["title"], curses.color_pair(CYAN) | curses.A_BOLD)
                r = 5
                for line in render_text(p).splitlines():
                    if r >= h - 2:
                        break
                    stdscr.addstr(r, 2, line[: w - 4])
                    r += 1
                stdscr.addstr(h - 2, 2, "←/esc back   q quit", curses.A_DIM)
            stdscr.refresh()

            k = stdscr.getch()
            if k in (ord("q"), ord("Q")):
                return
            if not detail:
                if k in (curses.KEY_DOWN, ord("j")):
                    idx = (idx + 1) % len(phases)
                elif k in (curses.KEY_UP, ord("k")):
                    idx = (idx - 1) % len(phases)
                elif k in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT):
                    detail = True
            else:
                if k in (27, curses.KEY_LEFT, ord("h")):
                    detail = False

    try:
        curses.wrapper(app)
    except KeyboardInterrupt:
        pass
    return 0


def main(argv) -> int:
    if not argv:
        return tui()
    if argv[0] == "--list":
        return cmd_list()
    if argv[0] == "--print" and len(argv) > 1:
        return cmd_print(argv[1])
    if argv[0] == "--teaser" and len(argv) > 1:
        return cmd_teaser(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
