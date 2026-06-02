# Resource Monitor

When the user asks to monitor local CPU, GPU, or memory during coding, testing, benchmarking, model pressure tests, or long-running Claude Code work, run:

```bash
scripts/monitor.sh --interval 5
```

Rules:

- Do not paste live samples into chat unless the user explicitly asks.
- Do not poll faster than every 5 seconds unless explicitly requested.
- Prefer a separate terminal pane/window.
- If backgrounded, redirect output to a local log and report only the PID/log path.
- Stop the monitor when the user asks or the long-running session ends.
- If GPU data is unavailable, keep CPU and memory monitoring running.
