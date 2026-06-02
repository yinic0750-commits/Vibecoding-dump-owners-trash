# Resource Monitor

Purpose: low-overhead terminal monitoring for local CPU, GPU, and memory during agent coding, tests, benchmarks, and model load tests.

Command:

```bash
scripts/monitor.sh --interval 5 --style statusline
```

Behavior:

- Use this script instead of writing ad hoc monitoring loops.
- Keep the default interval at 5 seconds.
- Do not stream every sample into the conversation.
- Prefer a separate terminal pane/window for foreground monitoring.
- GPU detection is best-effort; unavailable GPU data must not fail the monitor.
- Stop with `Ctrl-C` or `pkill -f agent_resource_monitor.py`.
