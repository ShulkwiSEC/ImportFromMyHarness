# Positioning canvas

Method: April Dunford, *Obviously Awesome*. Status as of 2026-11-22. Nothing here comes from customer interviews yet; every line says what backs it.

| Component | Answer | Backing |
| --- | --- | --- |
| Competitive alternatives | 1. Copy and rewrite by hand. 2. A one-off script. 3. Stay on one harness. 4. Config-sync tools: [rulesync](https://github.com/dyoshikawa/rulesync) (has `import`, many targets), [ruler](https://github.com/intellectronica/ruler), [AgentSync](https://github.com/yelmuratoff/agent_sync). | 1-3: author's own case, not interviews. 4: web search and the rulesync README, 2026-11-22. |
| Unique attributes | Reads the plugin layer too (`oh-my-opencode-slim` agents and prompt files). Prints a written list of what could not convert, and saves those items under `.importfrommyharness/unmapped/`. A new harness is one TOML file. | The first and third are verified in this repo. The second is checked against the rulesync README only, not its code: **[ASSUMPTION]** that no listed alternative reports losses. Check before using "only". |
| Value themes | Nothing is silently lost. A big setup moves in minutes, with a preview first. | One real run: 1,708 files, 0.48 s dry run, 9 items saved for review (see the launch article). |
| Best-fit customer | Someone with a large setup (dozens of agents, hundreds of skills) already working in one harness who wants it in a second without a rewrite. | One case (the author). **[ASSUMPTION]** until interviews. |
| Not a fit | People starting fresh who want to write rules once and generate for every tool: rulesync and ruler are built for that. | Their READMEs. |
| Category | Subcategory: harness config migrator (move an existing setup), next to config sync (author once, generate everywhere). | Choice, not tested with prospects. |
| Trend | Teams run more than one AI coding harness. | **[ASSUMPTION]**, no source yet. |
| Statement | For people with a large agent setup in one harness who want it in another, importfrommyharness is the config migrator that tells you what it could not convert. | Derived from the rows above. |

## To reach a higher score

1. Interview 5 to 15 people who moved or wanted to move between harnesses. Ask what they did instead (Step 1).
2. Test the "no listed alternative reports losses" assumption against each tool's code and a real run.
3. Run the same bb-huge import through rulesync and record what it does with the plugin agents.
4. Replace every **[ASSUMPTION]** above or delete the row.
