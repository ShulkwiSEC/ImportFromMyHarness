import json, shutil, tempfile, unittest
from pathlib import Path
from importfrommyharness import main

FIX = Path(__file__).parent / "fixtures" / "opencode-min"


class OpencodeToClaude(unittest.TestCase):
    def setUp(self):
        self.src = Path(tempfile.mkdtemp()) / "proj"
        shutil.copytree(FIX, self.src)
        self.run_import = lambda *a: main(["import", f"opencode:{self.src}", "--to", "claude", *a])

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.run_import(), 3)
        self.assertFalse((self.src / ".claude").exists())

    def test_apply(self):
        self.assertEqual(self.run_import("--apply"), 3)  # 3 = lossy/unmapped items present
        c = self.src
        self.assertIn("Be careful.", (c / "CLAUDE.md").read_text())
        self.assertTrue((c / ".claude/rules/scope.md").exists())
        self.assertTrue((c / ".claude/skills/demo-skill/SKILL.md").exists())
        lead = (c / ".claude/agents/lead.md").read_text()
        self.assertIn("name: lead", lead)
        self.assertNotIn("tools:", lead)                      # {"*": true} -> claude default (all)
        helper = (c / ".claude/agents/helper.md").read_text()
        self.assertIn("Help.", helper)
        self.assertFalse((c / ".claude/agents/orchestrator.md").exists())  # config-only override
        s = json.loads((c / ".claude/settings.json").read_text())
        self.assertEqual(s["agent"], "lead")
        self.assertEqual(s["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"], "1")
        m = json.loads((c / ".mcp.json").read_text())["mcpServers"]
        self.assertEqual(m["local1"]["command"], "npx")
        self.assertEqual(m["local1"]["args"], ["-y", "srv"])
        self.assertEqual(m["local1"]["env"], {"API_TOKEN": "${API_TOKEN}", "MODE": "x"})  # secret not copied
        self.assertEqual(m["remote1"], {"type": "http", "url": "https://x.test/mcp", "headers": {"Authorization": "${TOK}"}})
        self.assertNotIn("off", m)
        self.assertNotIn("supersecret", json.dumps(m))
        un = c / ".importfrommyharness/unmapped"
        for kind in ("permission", "plugin", "plugin-config"):
            self.assertTrue((un / kind).exists(), kind)

    def test_opencode_v2_mcp_layout(self):
        cfg = self.src / ".opencode/opencode.json"
        cfg.write_text(json.dumps({"mcp": {"servers": {
            "a": {"type": "local", "command": ["npx", "x"]},
            "b": {"type": "local", "command": ["y"], "disabled": True}}}}))
        self.run_import("--apply")
        m = json.loads((self.src / ".mcp.json").read_text())["mcpServers"]
        self.assertEqual(m, {"a": {"command": "npx", "args": ["x"]}})   # no bogus "servers" entry, disabled skipped

    def test_setup_refuses_without_terminal(self):
        self.assertEqual(main(["setup"]), 2)  # tests run without a TTY

    def test_rerun_keeps_existing(self):
        self.run_import("--apply")
        (self.src / "CLAUDE.md").write_text("mine")
        self.run_import("--apply")
        self.assertTrue((self.src / "CLAUDE.md.bak").exists())


if __name__ == "__main__":
    unittest.main()
