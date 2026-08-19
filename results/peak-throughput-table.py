#!/usr/bin/env python3
"""Print a "Peak throughput (closed loop)" markdown table row for each runtime in a
perf-lab run.

Same three sources as density-table.py, since it's the same pipeline producing them
(the loader helpers below are copied from there rather than imported - its hyphenated
filename isn't a valid Python module name):

  - /tmp/metrics.json (default) for throughput and the config's -Xmx, one value per run
  - the per-iteration Hyperfoil stats (logs/hyperfoil/<runtime>-<iteration>/run/*/all.json)
    for Max latency and the load-test phase's start/end time
  - the per-iteration pidstat log (logs/pidstat-<runtime>-<iteration>.log, needs `-r` for
    RSS - see main.yml's monitor-processes) for RSS and %CPU, averaged over just the
    load-test window so warmup/cooldown samples don't pull the numbers around

Unlike density-table.py, only Max latency is kept: this is closed-loop, where a stalled
connection just sends fewer requests rather than queueing a backlog (coordinated
omission), so mean/p50/p90/p99/p99.9/p99.99 are diluted by that shrunken, biased sample
and don't mean what they'd mean in the open-loop density run - see "Peak throughput
(closed loop)" in results/README.md. Monthly cost replaces density's own
Density/CPU-cores-adjusted columns, scaling this run's CPU and RSS linearly to a
1000 req/s target and pricing the result against Azure's Dadsv5/Eadsv5 on-demand Linux
rate (~$0.0375/vCPU-hour, ~$0.0035/GB RAM-hour, both times 730 hours/month) - same
formula as the existing README table, reverse-engineered from its transcribed rows since
it was never implemented in code before this script.

Usage:

    ./peak-throughput-table.py [metrics.json] [--logs-dir=PATH] [runtime ...]

With no runtime given, every runtime present in metrics.json is emitted. Both metrics.json
and the logs directory are the pipeline's live, overwritten-every-run locations - archive
first with archive.py if the run also needs to survive past the next one.
"""

import glob
import json
import sys
from datetime import datetime
from pathlib import Path

from _chartlib import kind

DEFAULT_METRICS = Path("/tmp/metrics.json")
DEFAULT_LOGS_DIR = Path.home() / "spring-quarkus-perf-comparison" / "logs"

NS_PER_MS = 1_000_000

VCPU_HOUR_RATE = 0.0375
RAM_GB_HOUR_RATE = 0.0035
HOURS_PER_MONTH = 730
TARGET_RATE = 1000


def xmx_label(metrics, runtime):
    if kind(runtime)[0] == "other":
        return "—"
    memory = ((metrics.get("config") or {}).get("jvm") or {}).get("memory") or ""
    if memory.startswith("-Xmx"):
        memory = memory[len("-Xmx"):]
    return memory or "—"


def load_test_summary(logs_dir, runtime, iteration):
    pattern = str(logs_dir / "hyperfoil" / f"{runtime}-{iteration}" / "run" / "*" / "all.json")
    matches = sorted(glob.glob(pattern))
    if not matches:
        return None
    data = json.load(open(matches[0]))
    for entry in data.get("stats", []):
        if entry.get("phase") == "loadTest":
            return entry["total"]["summary"]
    return None


def window_of(summary):
    start = datetime.fromtimestamp(summary["startTime"] / 1000).strftime("%H:%M:%S")
    end = datetime.fromtimestamp(summary["endTime"] / 1000).strftime("%H:%M:%S")
    return start, end


def pidstat_stats(logs_dir, runtime, iteration, start, end):
    """(rss_max_mb, cpu_avg_pct) over the process-aggregate rows within [start, end].

    See density-table.py's version of this function for why RSS is a peak and CPU an
    average.
    """
    path = logs_dir / f"pidstat-{runtime}-{iteration}.log"
    if not path.exists():
        return None, None
    rss_samples, cpu_samples = [], []
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) < 4 or not fields[2].isdigit() or fields[3] != "-":
            continue
        if not (start <= fields[0] <= end):
            continue
        if len(fields) == 10:
            rss_samples.append(float(fields[7]) / 1024)
        elif len(fields) == 11:
            cpu_samples.append(float(fields[8]))
    rss_max = max(rss_samples) if rss_samples else None
    cpu_avg = sum(cpu_samples) / len(cpu_samples) if cpu_samples else None
    return rss_max, cpu_avg


def session_limit_occurrences(logs_dir, runtime, iteration, phrase="Exceeded session limit"):
    path = logs_dir / f"hf-{runtime}-{iteration}.log"
    if not path.exists():
        return 0
    return path.read_text().count(phrase)


def avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def monthly_cost(cpu_pct, rss_mb, throughput):
    if cpu_pct is None or rss_mb is None or not throughput:
        return None
    cpu_cores_at_target = cpu_pct / 100 / throughput * TARGET_RATE
    rss_gb_at_target = rss_mb / 1024 / throughput * TARGET_RATE
    return cpu_cores_at_target * VCPU_HOUR_RATE * HOURS_PER_MONTH + \
        rss_gb_at_target * RAM_GB_HOUR_RATE * HOURS_PER_MONTH


def build_row(runtime, metrics, logs_dir):
    load = metrics["results"][runtime]["load"]
    num_iterations = len(load["throughput"])

    maxes = []
    rss_samples, cpu_samples = [], []
    session_limit_total = 0

    for i in range(num_iterations):
        summary = load_test_summary(logs_dir, runtime, i)
        if summary is None:
            continue
        maxes.append(summary["maxResponseTime"] / NS_PER_MS)

        start, end = window_of(summary)
        rss, cpu = pidstat_stats(logs_dir, runtime, i, start, end)
        rss_samples.append(rss)
        cpu_samples.append(cpu)
        session_limit_total += session_limit_occurrences(logs_dir, runtime, i)

    throughput = load.get("avThroughput")
    rss = avg(rss_samples)
    cpu = avg(cpu_samples)

    return {
        "runtime": runtime,
        "xmx": xmx_label(metrics, runtime),
        "throughput": throughput,
        "rss": rss,
        "cpu": cpu,
        "cost": monthly_cost(cpu, rss, throughput),
        "max": avg(maxes),
        "session_limit": session_limit_total,
    }


def format_row(row):
    def fmt(v, nd=2):
        return f"{v:.{nd}f}" if v is not None else "—"

    return (
        f"| {row['runtime']} | {row['xmx']} | {fmt(row['throughput'], 1)} | {fmt(row['rss'], 1)} | "
        f"{fmt(row['cpu'], 1)} | ${fmt(row['cost'])} | {fmt(row['max'])} | {row['session_limit']} |"
    )


def main():
    args = sys.argv[1:]
    logs_dir = DEFAULT_LOGS_DIR
    for arg in [a for a in args if a.startswith("--logs-dir=")]:
        logs_dir = Path(arg.split("=", 1)[1])
        args.remove(arg)

    metrics_path = DEFAULT_METRICS
    if args and args[0].endswith(".json"):
        metrics_path = Path(args.pop(0))

    metrics = json.load(open(metrics_path))
    runtimes = args or list(metrics["results"].keys())

    header = (
        "| Runtime | Xmx | Throughput avg (req/s) | RSS avg (MB) | CPU avg (%) | "
        'Monthly cost (1000 req/s) | Max (ms) | "Exceeded session limit" occurrences |'
    )
    print(header)
    print("|---|---|---|---|---|---|---|---|")
    for runtime in runtimes:
        print(format_row(build_row(runtime, metrics, logs_dir)))


if __name__ == "__main__":
    main()
