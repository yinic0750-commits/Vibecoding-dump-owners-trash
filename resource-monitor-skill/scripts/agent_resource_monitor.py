#!/usr/bin/env python3
"""Low-overhead terminal CPU/GPU/memory monitor for CLI agent sessions."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple


BAR_WIDTH = 28
ANSI_HOME = "\033[H"
ANSI_CLEAR = "\033[2J"
ANSI_HIDE_CURSOR = "\033[?25l"
ANSI_SHOW_CURSOR = "\033[?25h"


@dataclass
class CpuSnapshot:
    idle: float
    total: float


@dataclass
class Metrics:
    cpu_percent: Optional[float]
    mem_percent: Optional[float]
    mem_used_gib: Optional[float]
    mem_total_gib: Optional[float]
    gpu_label: str
    gpu_percent: Optional[float]
    gpu_mem_percent: Optional[float]
    gpu_mem_used_mib: Optional[float]
    gpu_mem_total_mib: Optional[float]


class Monitor:
    def __init__(self, interval: float, enable_apple_gpu: bool) -> None:
        self.interval = max(interval, 1.0)
        self.system = platform.system().lower()
        self.enable_apple_gpu = enable_apple_gpu
        self.cpu_count = os.cpu_count() or 1
        self.prev_cpu = self._read_cpu_snapshot() if self.system == "linux" else None
        self.nvidia_smi = shutil.which("nvidia-smi")
        self.apple_gpu_disabled = False

    def sample(self) -> Metrics:
        cpu = self._cpu_percent()
        mem_percent, mem_used_gib, mem_total_gib = self._memory()
        gpu = self._gpu()
        return Metrics(
            cpu_percent=cpu,
            mem_percent=mem_percent,
            mem_used_gib=mem_used_gib,
            mem_total_gib=mem_total_gib,
            gpu_label=gpu[0],
            gpu_percent=gpu[1],
            gpu_mem_percent=gpu[2],
            gpu_mem_used_mib=gpu[3],
            gpu_mem_total_mib=gpu[4],
        )

    def _cpu_percent(self) -> Optional[float]:
        if self.system == "darwin":
            return self._darwin_cpu_percent()

        current = self._read_cpu_snapshot()
        if not current or not self.prev_cpu:
            self.prev_cpu = current
            return None

        idle_delta = current.idle - self.prev_cpu.idle
        total_delta = current.total - self.prev_cpu.total
        self.prev_cpu = current
        if total_delta <= 0:
            return None
        return clamp((1.0 - idle_delta / total_delta) * 100.0)

    def _read_cpu_snapshot(self) -> Optional[CpuSnapshot]:
        if self.system == "linux":
            try:
                with open("/proc/stat", "r", encoding="utf-8") as fh:
                    parts = fh.readline().strip().split()[1:]
                values = [float(v) for v in parts]
                idle = values[3] + (values[4] if len(values) > 4 else 0.0)
                return CpuSnapshot(idle=idle, total=sum(values))
            except (OSError, ValueError, IndexError):
                return None

        return None

    def _darwin_cpu_percent(self) -> Optional[float]:
        out = run_cmd(["ps", "-A", "-o", "%cpu="], timeout=2.0)
        if not out:
            return None
        try:
            total_process_cpu = sum(float(line.strip()) for line in out.splitlines() if line.strip())
        except ValueError:
            return None
        return clamp(total_process_cpu / self.cpu_count)

    def _memory(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if self.system == "linux":
            try:
                values = {}
                with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                    for line in fh:
                        key, value = line.split(":", 1)
                        values[key] = float(value.strip().split()[0])
                total_kib = values["MemTotal"]
                available_kib = values.get("MemAvailable", values.get("MemFree", 0.0))
                used_kib = total_kib - available_kib
                return (
                    clamp(used_kib / total_kib * 100.0),
                    used_kib / 1024 / 1024,
                    total_kib / 1024 / 1024,
                )
            except (OSError, ValueError, KeyError, ZeroDivisionError):
                return None, None, None

        if self.system == "darwin":
            total_out = run_cmd(["sysctl", "-n", "hw.memsize"], timeout=1.0)
            vm_out = run_cmd(["vm_stat"], timeout=1.5)
            if not total_out or not vm_out:
                return None, None, None
            try:
                total_bytes = float(total_out.strip())
                page_size_match = re.search(r"page size of (\d+) bytes", vm_out)
                page_size = float(page_size_match.group(1)) if page_size_match else 4096.0
                pages = {}
                for line in vm_out.splitlines():
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    number = re.sub(r"[^0-9]", "", value)
                    if number:
                        pages[key.strip()] = float(number)
                free = pages.get("Pages free", 0.0)
                speculative = pages.get("Pages speculative", 0.0)
                inactive = pages.get("Pages inactive", 0.0)
                available_bytes = (free + speculative + inactive) * page_size
                used_bytes = max(total_bytes - available_bytes, 0.0)
                return (
                    clamp(used_bytes / total_bytes * 100.0),
                    used_bytes / 1024**3,
                    total_bytes / 1024**3,
                )
            except (ValueError, AttributeError, ZeroDivisionError):
                return None, None, None

        return None, None, None

    def _gpu(self) -> Tuple[str, Optional[float], Optional[float], Optional[float], Optional[float]]:
        if self.nvidia_smi:
            out = run_cmd(
                [
                    self.nvidia_smi,
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                timeout=2.0,
            )
            if out:
                first = out.splitlines()[0]
                parts = [p.strip() for p in first.split(",")]
                if len(parts) >= 4:
                    try:
                        name = parts[0]
                        util = clamp(float(parts[1]))
                        mem_used = float(parts[2])
                        mem_total = float(parts[3])
                        mem_pct = clamp(mem_used / mem_total * 100.0) if mem_total > 0 else None
                        return name, util, mem_pct, mem_used, mem_total
                    except ValueError:
                        pass

        if self.system == "darwin":
            if self.enable_apple_gpu and not self.apple_gpu_disabled:
                gpu = self._apple_gpu_powermetrics()
                if gpu[1] is not None:
                    return gpu
            return "Apple/Integrated GPU", None, None, None, None

        return "GPU", None, None, None, None

    def _apple_gpu_powermetrics(self) -> Tuple[str, Optional[float], Optional[float], Optional[float], Optional[float]]:
        pm = shutil.which("powermetrics")
        if not pm:
            self.apple_gpu_disabled = True
            return "Apple GPU", None, None, None, None
        out = run_cmd([pm, "--samplers", "gpu_power", "-i", "1000", "-n", "1"], timeout=3.5)
        if not out:
            self.apple_gpu_disabled = True
            return "Apple GPU", None, None, None, None
        match = re.search(r"GPU active residency:\s+([\d.]+)%", out)
        if not match:
            match = re.search(r"GPU HW active residency:\s+([\d.]+)%", out)
        util = clamp(float(match.group(1))) if match else None
        return "Apple GPU", util, None, None, None


def run_cmd(args: list[str], timeout: float) -> Optional[str]:
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def bar(value: Optional[float], width: int = BAR_WIDTH) -> str:
    if value is None:
        return "[" + (" " * width) + "] n/a"
    filled = int(round(width * clamp(value) / 100.0))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + f"] {value:5.1f}%"


def format_gib(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:5.1f} GiB"


def format_mib(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:7.0f} MiB"


def render(metrics: Metrics, interval: float, plain: bool) -> str:
    lines = [
        "Agent Resource Monitor",
        f"Refresh: {interval:g}s  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"CPU        {bar(metrics.cpu_percent)}",
        f"Memory     {bar(metrics.mem_percent)}  {format_gib(metrics.mem_used_gib)} / {format_gib(metrics.mem_total_gib)}",
        f"GPU        {bar(metrics.gpu_percent)}  {metrics.gpu_label}",
        f"GPU memory {bar(metrics.gpu_mem_percent)}  {format_mib(metrics.gpu_mem_used_mib)} / {format_mib(metrics.gpu_mem_total_mib)}",
        "",
        "Ctrl-C to stop. Use --plain for log/pane output.",
    ]
    output = "\n".join(lines)
    if plain:
        return output + "\n"
    return ANSI_HOME + output + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Low-overhead terminal resource monitor for CLI agents.")
    parser.add_argument("--interval", type=float, default=5.0, help="Refresh interval in seconds. Default: 5.")
    parser.add_argument("--once", action="store_true", help="Print one sample and exit.")
    parser.add_argument("--plain", action="store_true", help="Do not use ANSI screen refresh codes.")
    parser.add_argument(
        "--apple-gpu",
        action="store_true",
        help="Try macOS powermetrics GPU sampling. May require sudo and adds overhead.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    monitor = Monitor(interval=args.interval, enable_apple_gpu=args.apple_gpu)
    stop_event = threading.Event()

    def handle_stop(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    if not args.plain and not args.once:
        sys.stdout.write(ANSI_CLEAR + ANSI_HIDE_CURSOR)
        sys.stdout.flush()

    try:
        while True:
            metrics = monitor.sample()
            sys.stdout.write(render(metrics, monitor.interval, args.plain or args.once))
            sys.stdout.flush()
            if args.once or stop_event.wait(monitor.interval):
                break
    finally:
        if not args.plain and not args.once:
            sys.stdout.write(ANSI_SHOW_CURSOR + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
