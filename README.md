# ImportFromMyHarness

**Import your setup from one AI coding harness into another.** Instructions, rules, skills, agents, MCP servers and settings are converted by a small data-driven engine, and whatever can't be converted is listed instead of silently dropped.

![demo](https://raw.githubusercontent.com/ShulkwiSEC/ImportFromMyHarness/main/assets/demo.gif)

Need another harness? Add its TOML ([how](#add-a-harness)) or open an issue.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/ImportFromMyHarness/main/install.sh | sh
```

It checks for [uv](https://docs.astral.sh/uv/) (and offers to install it), installs the tool, then offers a guided first run. No sudo; re-running upgrades. Flags: `sh -s -- -y` (no questions), `sh -s -- --no-setup`. Or without the script: `uvx importfrommyharness` (run once) or `uv tool install importfrommyharness`.

## Use

```sh
importfrommyharness            # guided setup (in a terminal)
importfrommyharness scan   opencode:~/my-project
importfrommyharness import opencode:~/my-project --to claude            # dry run
importfrommyharness import opencode:~/my-project --to claude --apply    # write
```

Options: `--out DIR` (default: the source path), `--only skill,mcp`, `--json`.
Exit codes: 0 ok, 1 error, 2 bad usage, 3 done, with lossy or unmapped items (see report).

## What you get
- Dry run by default. Existing JSON entries are never overwritten; existing files that change get a `.bak`.
- Things with no safe equivalent (npm plugins, permission rules, hooks, plugin config) are saved under `.importfrommyharness/unmapped/` and listed in the report, never dropped silently.
- Literal secrets in MCP env/headers are replaced with `${NAME}` references; `.env` is never read.
- `opencode` modes become Claude agents; `default_agent` becomes `"agent"` in `.claude/settings.json`.
- Scriptable: `--json` report on stdout, messages on stderr, no prompts outside `setup`.

## Add a harness
Drop one file in `src/importfrommyharness/harnesses/<name>.toml`: a `name`, a `detect` list, and `[[item]]` rows (`kind`, `path`, `fmt`, optional `map`/`xform`/`docs`). Copy `claude.toml` as a template. A plugin pack sets `host` and `origin` instead of `name` (see `opencode+oh-my-opencode-slim.toml`). No Python changes unless you need a new field transform (add it to `XF` in `engine.py`).

## Tests
`uv run python -m unittest discover tests`

## Supported harnesses
A harness is just a TOML file, so supporting a new one means adding one file, not writing code.

| Harness | As source | As destination |
|---|---|---|
| opencode (+ `oh-my-opencode-slim`) | tested | experimental |
| Claude Code | experimental | tested |
