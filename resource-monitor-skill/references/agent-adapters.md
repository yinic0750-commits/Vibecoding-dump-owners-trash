# Agent Adapters

Use the smallest adapter that the target CLI agent already supports. Keep all sampling logic in `scripts/agent_resource_monitor.py`.

## Codex

Install as a normal skill folder:

```text
$CODEX_HOME/skills/resource-monitor/
```

Trigger wording: "monitor local CPU/GPU/memory while tests or benchmarks run".

## Claude Code

Use either a Claude Code skill location if available in the user's setup, or add the compact `CLAUDE.md` snippet below near the project root:

```markdown
When the user asks to monitor local CPU/GPU/memory during coding, testing, benchmarking, or model pressure tests, run:

resource-monitor-skill/scripts/monitor.sh --interval 5 --style statusline

Do not paste every sample into chat. Use a separate terminal pane when possible. Stop with Ctrl-C or pkill -f agent_resource_monitor.py.
```

## AGENTS.md-style CLIs

For agents that read `AGENTS.md`, add:

```markdown
### Resource Monitor

On request, start `resource-monitor-skill/scripts/monitor.sh --interval 5 --style statusline`.
Do not stream samples into the conversation. Prefer a separate terminal pane. Stop it when the session ends or the user asks.
```

## Generic CLI Agents

If no skill system exists, expose this as a tool command:

```bash
/absolute/path/to/resource-monitor-skill/scripts/monitor.sh --interval 5 --style statusline
```

The agent only needs to remember the command and the no-chat-streaming rule.
