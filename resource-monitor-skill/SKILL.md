---
name: resource-monitor
description: Use when a user wants a low-overhead terminal monitor for CPU, GPU, and memory during vibe coding, local testing, model benchmarking, pressure tests, long-running CLI agent work, or when they ask to watch local machine resource usage without consuming conversation tokens. Works as a portable helper for Codex, Claude Code, OpenClaw, Hermes, and other terminal agents.
---

# Resource Monitor

Use this skill when the user wants live local CPU, GPU, and memory visibility while an agent keeps coding, testing, benchmarking, or running models.

## Core Rule

Do not stream resource samples into chat. Start the bundled terminal monitor as a local process so it refreshes in-place every 5 seconds and consumes no recurring conversation tokens.

## Start

From this skill directory:

```bash
scripts/monitor.sh --interval 5 --style statusline
```

If the agent must continue working in the same shell, start it in the background and redirect logs:

```bash
nohup scripts/monitor.sh --interval 5 --style statusline --plain > /tmp/agent-resource-monitor.log 2>&1 &
```

For a separate terminal pane/window, run the foreground command above. Prefer a separate pane because it keeps the monitor visible without mixing with build/test output.

## Stop

Foreground: press `Ctrl-C`.

Background:

```bash
pkill -f agent_resource_monitor.py
```

## Behavior

- Default refresh interval is 5 seconds.
- Default output is a compact two-line agent-style statusline with CPU, memory, and GPU progress bars.
- Use `--style panel` for the older multi-line dashboard.
- CPU and memory use are collected with OS-native low-frequency probes.
- NVIDIA GPU usage is read with `nvidia-smi` when available.
- Apple GPU utilization is not sampled by default because reliable utilization usually needs `powermetrics`, which may require sudo and adds overhead. Use `--apple-gpu` only when the user explicitly accepts that tradeoff.
- If GPU utilization is unavailable, show `n/a` instead of retrying expensive probes repeatedly.

## Agent Compatibility

For non-Codex agents, copy or symlink this folder into the agent's skills/tools/instructions area, then point that agent at this `SKILL.md` or the minimal adapter files in `references/agent-adapters.md`.

Keep agent-facing instructions short:

1. Start the script on request.
2. Do not summarize every sample.
3. Leave the monitor running only for the requested session.
4. Stop it when the user asks or when the long-running task ends.

## Verification

Run:

```bash
scripts/monitor.sh --once
scripts/monitor.sh --interval 5 --plain
scripts/monitor.sh --interval 5 --style panel
```

Confirm CPU and memory render, GPU either renders real data or `n/a`, and repeated refreshes do not flood the terminal.
