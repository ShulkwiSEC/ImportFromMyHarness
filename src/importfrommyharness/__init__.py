"""importfrommyharness: import config from one AI-coding harness into another."""
import argparse
import json
import sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path

from . import engine, setup

EPILOG = """examples:
  importfrommyharness list
  importfrommyharness scan   opencode:~/my-project
  importfrommyharness import opencode:~/my-project --to claude --json   # dry run
  importfrommyharness import opencode:~/my-project --to claude --apply
exit codes: 0 ok, 1 error, 2 bad usage, 3 done but some items lossy/unmapped"""


def _die(msg, code):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _source(spec, hs):
    """'harness:path' or just 'path' (harness auto-detected when unambiguous)."""
    name, sep, rest = spec.partition(":")
    if sep and name in hs:
        return hs[name], Path(rest).expanduser()
    root = Path(spec).expanduser()
    found = engine.detect(hs, root)
    if len(found) != 1:
        _die(f"cannot tell the harness of {root} (matches: {found or 'none'}); use <harness>:<path>", 2)
    return hs[found[0]], root


def main(argv=None):
    ap = argparse.ArgumentParser(prog="importfrommyharness", description=__doc__, epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=version("importfrommyharness"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="guided interactive setup (default when run bare in a terminal)")
    sub.add_parser("list", help="show registered harnesses and plugin packs")
    for n, h in (("scan", "show what a source contains"), ("import", "convert source into another harness")):
        p = sub.add_parser(n, help=h)
        p.add_argument("src", help="<harness>:<path> or <path>")
        p.add_argument("--json", action="store_true", help="machine-readable report on stdout")
        if n == "import":
            p.add_argument("--to", required=True, help="destination harness")
            p.add_argument("--out", help="destination root (default: same as source path)")
            p.add_argument("--only", help="comma list of kinds, e.g. skill,mcp")
            p.add_argument("--apply", action="store_true", help="write files (default is dry run)")
    args = sys.argv[1:] if argv is None else argv
    if not args:  # bare run: wizard for humans, help for pipes and agents
        args = ["setup"] if sys.stdin.isatty() and sys.stdout.isatty() else ["--help"]
    a = ap.parse_args(args)
    hs, packs = engine.load_harnesses()
    if a.cmd == "setup":
        return setup.run(hs, packs)

    if a.cmd == "list":
        for n in sorted(hs):
            print(n, "+", ", ".join(p["origin"] for p in packs if p["host"] == n) or "-")
        return 0

    src, root = _source(a.src, hs)
    if not root.is_dir():
        _die(f"not a directory: {root}", 1)
    rep = engine.Report()
    items = engine.read(src, packs, root, rep)

    if a.cmd == "scan":
        c = Counter((i.kind, i.origin) for i in items)
        out = [{"kind": k, "origin": o, "count": n} for (k, o), n in sorted(c.items())]
        print(json.dumps(out, indent=2) if a.json else "\n".join(f"{x['kind']:<14}{x['count']:>5}  {x['origin']}" for x in out))
        return 0

    if a.to not in hs:
        _die(f"unknown harness '{a.to}' (try: list)", 2)
    out_root = Path(a.out).expanduser() if a.out else root
    plan = engine.build_plan(items, hs[a.to], out_root, rep, set(a.only.split(",")) if a.only else None)
    result = rep.as_dict(plan) | {"from": src["name"], "to": a.to, "out": str(out_root), "applied": False}
    if a.apply:
        result["written"], result["applied"] = engine.apply(plan, out_root), True
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{src['name']} -> {a.to}  ({'applied' if a.apply else 'dry run'}) out={out_root}")
        print("mapped:  ", ", ".join(f"{k}={v}" for k, v in result["mapped"].items()) or "-")
        print("files:   ", result["files"], result["by_dir"])
        print("lossy:   ", result["lossy"] or "-")
        print("unmapped:", Counter(u["kind"] for u in rep.unmapped) or "-")
        for n in result["notes"]:
            print("note:", n)
    return 3 if rep.lossy or rep.unmapped else 0


if __name__ == "__main__":
    sys.exit(main())
