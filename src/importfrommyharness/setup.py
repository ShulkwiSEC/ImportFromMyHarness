"""Guided setup wizard: `importfrommyharness setup` (also what a bare run does in a terminal)."""
import os
import sys
from collections import Counter
from pathlib import Path

from . import engine

USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def c(code, s):
    return f"\033[{code}m{s}\033[0m" if USE_COLOR else s


def ask(q, default=""):
    try:
        a = input(f"{c('1', q)} {c('2', f'[{default}]') if default else ''} ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nNothing was changed.")
        raise SystemExit(130)
    return a or default


def choose(q, options):
    print(c("1", q))
    for i, o in enumerate(options, 1):
        print(f"  {i}) {o}")
    while True:
        a = ask("Pick a number", "1")
        if a.isdigit() and 1 <= int(a) <= len(options):
            return options[int(a) - 1]


def run(hs, packs):
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("setup needs a terminal. Non-interactive: importfrommyharness import <harness>:<path> --to <harness> [--apply]",
              file=sys.stderr)
        return 2
    print(c("1;36", "\n  ImportFromMyHarness") + c("2", "  bring your whole harness with you\n"))
    root = Path(ask("Which project folder holds your harness config?", os.getcwd())).expanduser()
    found = engine.detect(hs, root) if root.is_dir() else []
    if not found:
        print(f"I can't see a known harness in {root}. Known: {', '.join(sorted(hs))}.", file=sys.stderr)
        return 1
    src = found[0] if len(found) == 1 else choose("I see more than one harness here. Import from:", found)
    rep = engine.Report()
    items = engine.read(hs[src], packs, root, rep)
    counts = Counter(i.kind for i in items)
    print(f"\nFound in {c('1', src)}:")
    for k, n in counts.most_common():
        print(f"  {k:<14}{n:>5} {c('36', '█' * max(1, n * 30 // max(counts.values())))}")
    targets = sorted(h for h in hs if h != src)
    dst = targets[0] if len(targets) == 1 else choose("\nImport into:", targets)
    plan = engine.build_plan(items, hs[dst], root, rep)
    r = rep.as_dict(plan)
    print(f"\nPreview (nothing written yet): {c('1', str(r['files']))} files for {dst}")
    print("  converted:", ", ".join(f"{k} x{v}" for k, v in r["mapped"].items()) or "nothing")
    if rep.unmapped:
        kinds = ", ".join(f"{k} x{v}" for k, v in Counter(u["kind"] for u in rep.unmapped).items())
        print(c("33", f"  needs your review: {kinds}") + "  (saved in .importfrommyharness/unmapped/)")
    if rep.lossy:
        top = ", ".join(k for k, _ in rep.lossy.most_common(3))
        print(c("33", f"  loses detail: {top}") + f" ... ({len(rep.lossy)} fields)")
    for n in r["notes"][:5]:
        print(c("2", f"  note: {n}"))
    cmd = f"importfrommyharness import {src}:{root} --to {dst} --apply"
    if ask("\nWrite these files into the project now? Changed files are backed up as .bak. (y/N)", "N").lower() != "y":
        print(f"\nNothing was changed. When you're ready:\n  {c('1', cmd)}")
        return 0
    print(f"\nDone: {engine.apply(plan, root)} files written in {root}.")
    print(f"Next time, skip the questions:\n  {c('1', cmd)}")
    return 3 if rep.lossy or rep.unmapped else 0
