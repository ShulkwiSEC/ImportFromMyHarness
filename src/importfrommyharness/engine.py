"""Read one harness into neutral Items, write them out as another harness.

Harnesses are data: harnesses/*.toml. Nothing here knows about a specific harness.
Row keys: kind, name, path[#json.key], fmt, map {native: ir}, xform [..], keep, ignore,
default, need_body, skip_disabled, requires, set, body, docs, note.
"""
import json
import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml

KIND_FALLBACK = {"mode": "agent"}  # kind with no native twin -> closest concept
UNMAPPED = ".importfrommyharness/unmapped"
SECRET_KEY = re.compile(r"KEY|TOKEN|SECRET|PASS|PAT$|AUTH|CRED", re.I)


@dataclass
class Item:
    kind: str
    name: str
    data: dict = field(default_factory=dict)
    body: str = ""
    files: dict = field(default_factory=dict)  # rel path -> bytes (tree/raw)
    origin: str = "docs"
    src: str = ""


class Report:
    def __init__(self):
        self.mapped, self.lossy = Counter(), Counter()
        self.unmapped, self.notes = [], []

    def as_dict(self, plan):
        by_dir = Counter("/".join(p.split("/")[:2]) for p in plan)
        return {"mapped": dict(self.mapped), "lossy": dict(self.lossy), "unmapped": self.unmapped,
                "notes": sorted(set(self.notes)), "files": len(plan), "by_dir": dict(by_dir)}


# ---------- small format helpers ----------
_JSONC = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/|,(?=\s*[}\]])', re.S)


def jsonc(text):
    return json.loads(_JSONC.sub(lambda m: m.group(1) or "", text))


def split_md(text, src, rep):
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?(.*)", text, re.S)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m[1]) or {}
        if isinstance(fm, dict):
            return fm, m[2]
    except yaml.YAMLError:
        pass
    rep.notes.append(f"unparseable frontmatter kept as body text: {src}")
    return {}, text


def dig(d, dotted):
    for k in dotted.split(".") if dotted else []:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def put(d, dotted, v):
    ks = dotted.split(".")
    for k in ks[:-1]:
        d = d.setdefault(k, {})
    d[ks[-1]] = v


def json_file(root, rel):
    for c in ([rel + "c"] if rel.endswith(".json") else []) + [rel]:  # .jsonc wins
        if (root / c).is_file():
            return root / c


# ---------- transforms: name -> (to_ir(native), from_ir(native)); may take rep ----------
_CLAUDE_TOOLS = {"webfetch": "WebFetch", "websearch": "WebSearch", "todowrite": "TodoWrite"}


def _argv_in(d, rep):
    d = dict(d)
    if isinstance(d.get("command"), str):
        d["command"] = [d["command"], *d.pop("args", [])]
    return d


def _argv_out(d, rep):
    d = dict(d)
    if isinstance(d.get("command"), list):
        c = d["command"]
        d["command"] = c[0]
        if c[1:]:
            d["args"] = c[1:]
    return d


def _refs_in(d, rep):
    d = dict(d)
    for key in ("env", "environment", "headers"):
        out = {}
        for k, v in (d.get(key) or {}).items():
            v = str(v)
            m = re.fullmatch(r"\{env:(\w+)\}", v)
            if m:
                v = "${%s}" % m[1]
            elif SECRET_KEY.search(k) and not re.fullmatch(r"\$\{\w+\}", v):
                v = "${%s}" % k  # never copy a literal secret
                rep.lossy["mcp.secret-literal-replaced"] += 1
            out[k] = v
        if out:
            d[key] = out
    return d


def _refs_oc_out(d, rep):
    d = dict(d)
    for key in ("environment", "headers"):
        if key in d:
            d[key] = {k: re.sub(r"\$\{(\w+)\}", r"{env:\1}", v) for k, v in d[key].items()}
    return d


def _mcp_type_in(d, rep):
    d = dict(d)
    if d.pop("type", None) == "remote":
        d["type"] = "http"
    return d


def _mcp_type_out(d, rep):
    d = dict(d)
    d["type"] = "remote" if "url" in d else "local"
    return d


def _tools_csv_in(d, rep):
    d = dict(d)
    if isinstance(d.get("tools"), str):
        d["tools"] = [t.strip().lower() for t in d["tools"].split(",") if t.strip()]
    return d


def _tools_csv_out(d, rep):
    d = dict(d)
    t = d.get("tools")
    if isinstance(t, list):
        if not t or "*" in t:
            d.pop("tools")  # claude: omitted = all tools
        else:
            d["tools"] = ", ".join(_CLAUDE_TOOLS.get(x, x.capitalize()) for x in t)
    return d


def _tools_map_in(d, rep):
    d = dict(d)
    if isinstance(d.get("tools"), dict):
        d["tools"] = [k for k, v in d["tools"].items() if v]
    return d


def _tools_map_out(d, rep):
    d = dict(d)
    if isinstance(d.get("tools"), list):
        d["tools"] = {t: True for t in d["tools"]}
    return d


def _disabled_in(d, rep):
    d = dict(d)
    if d.pop("disabled", False):
        d["enabled"] = False
    return d


def _disabled_out(d, rep):
    d = dict(d)
    if d.pop("enabled", True) is False:
        d["disabled"] = True
    return d


XF = {
    "disabled": (_disabled_in, _disabled_out),
    "argv": (_argv_in, _argv_out),
    "refs": (_refs_in, lambda d, r: d),
    "refs_oc": (_refs_in, _refs_oc_out),
    "mcp_type": (_mcp_type_in, _mcp_type_out),
    "tools_csv": (_tools_csv_in, _tools_csv_out),
    "tools_map": (_tools_map_in, _tools_map_out),
}


# ---------- registry (just reads the TOML files) ----------
def load_harnesses():
    hs, packs = {}, []
    for f in resources.files(__package__).joinpath("harnesses").iterdir():
        if f.name.endswith(".toml"):
            t = tomllib.loads(f.read_text(encoding="utf-8"))
            if "host" in t:
                packs.append(t)
            else:
                hs[t["name"]] = t
    return hs, packs


def detect(hs, root):
    return [n for n, h in hs.items() if any((root / d).exists() for d in h.get("detect", []))]


# ---------- read ----------
def _glob(root, path):
    if path.endswith("/"):
        return sorted(p for p in root.glob(path.rstrip("/")) if p.is_dir())
    return sorted(p for p in root.glob(path) if p.is_file())


def _attach_md(it, row, root, rep):
    fm, body = {}, ""
    main, extra = row["body"]
    p = root / main.format(name=it.name)
    if p.is_file():
        fm, body = split_md(p.read_text(encoding="utf-8"), str(p), rep)
    prompt = it.data.pop("prompt", None)  # inline prompt beats the file
    body = prompt or body
    a = root / extra.format(name=it.name)
    if a.is_file():
        body += "\n\n" + split_md(a.read_text(encoding="utf-8"), str(a), rep)[1]
    for k, v in fm.items():
        it.data.setdefault(k, v)
    it.body = body.strip()


def _to_ir(it, row, rep):
    d = it.data
    for x in row.get("xform", []):
        d = XF[x][0](d, rep)
    m, ignore, out = row.get("map", {}), row.get("ignore", []), {}
    for k, v in d.items():
        if k in m:
            out[m[k]] = v
        elif row.get("keep"):
            out[k] = v
        elif k not in ignore:
            rep.lossy[f"{it.kind}.{k}"] += 1
    it.data = out


def read_row(row, root, origin, rep):
    path, _, frag = row["path"].partition("#")
    fmt, kind, items = row["fmt"], row["kind"], []
    if fmt in ("json-path", "json-map", "json-map+md"):
        p = json_file(root, path)
        v = dig(jsonc(p.read_text(encoding="utf-8")), frag) if p else None
        if v is None:
            return []
        if fmt == "json-path":
            return [Item(kind, row["name"], {"value": v}, origin=origin, src=str(p))]
        for n, e in v.items():
            if n in row.get("exclude", []):  # e.g. opencode v1 `mcp` map must not read v2's `servers` key
                continue
            it = Item(kind, n, dict(e), origin=origin, src=f"{p}#{frag}")
            if fmt == "json-map+md":
                _attach_md(it, row, root, rep)
            _to_ir(it, row, rep)
            items.append(it)
        return items
    for p in _glob(root, path):
        name = p.name if p.is_dir() else (p.stem if "*" in path else row.get("name") or str(p.relative_to(root)))
        it = Item(kind, name, origin=origin, src=str(p))
        if fmt == "tree":
            it.files = {str(f.relative_to(p)): f.read_bytes() for f in p.rglob("*")
                        if f.is_file() and "__pycache__" not in f.parts}
        elif fmt == "raw":
            it.files = {p.name: p.read_bytes()}
        else:  # md
            it.data, it.body = split_md(p.read_text(encoding="utf-8"), str(p), rep)
            _to_ir(it, row, rep)
        items.append(it)
    return items


def read(h, packs, root, rep):
    rows = [(r, "docs") for r in h["item"]]
    for p in packs:
        if p["host"] == h["name"] and any((root / d).exists() for d in p["detect"]):
            rows += [(r, p["origin"]) for r in p["item"]]
    return [it for r, o in rows for it in read_row(r, root, o, rep)]


# ---------- write (builds a plan: relpath -> content; nothing touches disk) ----------
def _from_ir(it, row, rep):
    m = {v: k for k, v in row.get("map", {}).items()}
    ignore, out = row.get("ignore", []), {}
    for k, v in it.data.items():
        if k in m:
            out[m[k]] = v
        elif row.get("keep"):
            out[k] = v
        elif k not in ignore:
            rep.lossy[f"->{row['kind']}.{k}"] += 1
    for x in reversed(row.get("xform", [])):
        out = XF[x][1](out, rep)
    for k, v in row.get("default", {}).items():
        out.setdefault(k, v.format(name=it.name) if isinstance(v, str) else v)
    return out


def _unmapped(it, why, plan, rep):
    rep.unmapped.append({"kind": it.kind, "name": it.name, "origin": it.origin, "why": why})
    base = f"{UNMAPPED}/{it.kind}/{it.name}"
    if it.files:
        for rel, b in it.files.items():
            plan[f"{UNMAPPED}/{it.kind}/{rel}" if len(it.files) == 1 else f"{base}/{rel}"] = b
    else:
        plan[base + ".json"] = json.dumps({"data": it.data, "body": it.body, "src": it.src}, indent=2)


def build_plan(items, dst, out_root, rep, only=None):
    plan, docs = {}, {}
    rows = {}
    for r in dst["item"]:
        rows.setdefault((r["kind"], r.get("name")), r)

    def doc(rel):
        if rel not in docs:
            p = json_file(out_root, rel) or out_root / rel
            docs[rel] = jsonc(p.read_text(encoding="utf-8")) if p.is_file() else {}
        return docs[rel]

    for it in items:
        if only and it.kind not in only:
            continue
        row = rows.get((it.kind, it.name)) or rows.get((it.kind, None))
        if not row and it.kind in KIND_FALLBACK:
            row = rows.get((KIND_FALLBACK[it.kind], None))
            if row:
                rep.notes.append(f"{dst['name']} has no '{it.kind}'; imported as '{row['kind']}'")
        if not row:
            _unmapped(it, f"no equivalent in {dst['name']}", plan, rep)
            continue
        path, _, frag = row["path"].partition("#")
        fmt, dest = row["fmt"], path.replace("*", it.name)
        if row.get("note"):
            rep.notes.append(f"{it.kind} '{it.name}': {row['note']}")
        if fmt in ("tree", "raw"):
            for rel, b in it.files.items():
                plan[f"{dest.rstrip('/')}/{rel}" if fmt == "tree" else dest] = b
        elif fmt == "md":
            if row.get("need_body") and not it.body:
                _unmapped(it, "no prompt body (config-only override)", plan, rep)
                continue
            fm = _from_ir(it, row, rep)
            head = "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=10**6) + "---\n\n" if fm else ""
            if dest in plan:  # several sources -> one file (e.g. AGENTS.md + context.md -> CLAUDE.md)
                plan[dest] += f"\n\n<!-- imported from {it.src} -->\n{it.body}\n"
            else:
                plan[dest] = head + (f"<!-- imported from {it.src} -->\n" if "*" not in path else "") + it.body + "\n"
        elif fmt == "json-map":
            if row.get("skip_disabled") and it.data.get("enabled") is False:
                rep.notes.append(f"{it.kind} '{it.name}' skipped: disabled in source")
                continue
            cur = dig(doc(path), frag)
            if cur is None:
                put(doc(path), frag, {})
                cur = dig(doc(path), frag)
            if it.name in cur:
                rep.notes.append(f"{it.kind}: existing entries in {path} kept, not overwritten")
                continue
            cur[it.name] = _from_ir(it, row, rep)
        elif fmt == "json-path":
            val = row.get("set", it.data["value"])
            req = row.get("requires", "").format(value=val)
            if req and req not in plan and not (out_root / req).exists():
                _unmapped(it, f"needs {req}, which is not part of this import", plan, rep)
                continue
            if dig(doc(path), frag) is not None:
                rep.notes.append(f"setting '{it.name}' kept existing value in {path}")
                continue
            put(doc(path), frag, val)
        rep.mapped[it.kind] += 1
    for rel, d in docs.items():
        plan[rel] = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
    return plan


def apply(plan, out_root):
    """Write plan to disk; a changed existing file is saved as *.bak first."""
    n = 0
    for rel, content in plan.items():
        p = out_root / rel
        data = content if isinstance(content, bytes) else content.encode()
        if p.is_file():
            if p.read_bytes() == data:
                continue
            p.with_name(p.name + ".bak").write_bytes(p.read_bytes())
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        n += 1
    return n
