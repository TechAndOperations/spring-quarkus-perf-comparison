#!/usr/bin/env python3
"""Print a "### Density" markdown table row for each runtime in a perf-lab run.

Density combines three sources the pipeline never merges on its own:

  - /tmp/metrics.json (default) for throughput and the config's -Xmx, one value per run
  - the per-iteration Hyperfoil stats (logs/hyperfoil/<runtime>-<iteration>/run/*/all.json)
    for latencies and the load-test phase's start/end time
  - the per-iteration pidstat log (logs/pidstat-<runtime>-<iteration>.log, needs `-r` for
    RSS - see main.yml's monitor-processes) for RSS and %CPU, averaged over just the
    load-test window so warmup/cooldown samples don't pull the numbers around

Usage:

    ./density-table.py [metrics.json] [--logs-dir=PATH] [runtime ...]

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

    RSS is the peak, not the average: a mean would blur out the load phase's actual
    memory ceiling, which is what "Density" is meant to compare against throughput. CPU
    stays an average since there's no equivalent single peak worth isolating there.

    pidstat -u -w -t -r cycles through separate tables every second - identified here by
    field count (10 for the -r/RSS table, 11 for the -u/CPU table) rather than by command
    name, since that varies by runtime (java, go, rust, node). The aggregate row for the
    whole process (as opposed to one thread) is the one where TID is "-".
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


def build_row(runtime, metrics, logs_dir):
    load = metrics["results"][runtime]["load"]
    num_iterations = len(load["throughput"])

    means, p50s, p90s, p99s, p999s, p9999s, maxes = [], [], [], [], [], [], []
    rss_samples, cpu_samples = [], []
    session_limit_total = 0

    for i in range(num_iterations):
        summary = load_test_summary(logs_dir, runtime, i)
        if summary is None:
            continue
        means.append(summary["meanResponseTime"] / NS_PER_MS)
        maxes.append(summary["maxResponseTime"] / NS_PER_MS)
        pct = summary["percentileResponseTime"]
        p50s.append(pct["50.0"] / NS_PER_MS)
        p90s.append(pct["90.0"] / NS_PER_MS)
        p99s.append(pct["99.0"] / NS_PER_MS)
        p999s.append(pct["99.9"] / NS_PER_MS)
        p9999s.append(pct["99.99"] / NS_PER_MS)

        start, end = window_of(summary)
        rss, cpu = pidstat_stats(logs_dir, runtime, i, start, end)
        rss_samples.append(rss)
        cpu_samples.append(cpu)
        session_limit_total += session_limit_occurrences(logs_dir, runtime, i)

    return {
        "runtime": runtime,
        "xmx": xmx_label(metrics, runtime),
        "throughput": load.get("avThroughput"),
        "rss": avg(rss_samples),
        "cpu": avg(cpu_samples),
        "mean": avg(means),
        "p50": avg(p50s),
        "p90": avg(p90s),
        "p99": avg(p99s),
        "p999": avg(p999s),
        "p9999": avg(p9999s),
        "max": avg(maxes),
        "session_limit": session_limit_total,
    }


def format_row(row):
    def fmt(v, nd=2):
        return f"{v:.{nd}f}" if v is not None else "—"

    return (
        f"| {row['runtime']} | {row['xmx']} | {fmt(row['throughput'], 1)} | {fmt(row['rss'], 1)} | "
        f"{fmt(row['cpu'], 1)} | {fmt(row['mean'])} | {fmt(row['p50'])} | {fmt(row['p90'])} | "
        f"{fmt(row['p99'])} | {fmt(row['p999'])} | {fmt(row['p9999'])} | {fmt(row['max'])} | "
        f"{row['session_limit']} |"
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
        "Mean latency (ms) | p50 (ms) | p90 (ms) | p99 (ms) | p99.9 (ms) | p99.99 (ms) | "
        'Max (ms) | "Exceeded session limit" occurrences |'
    )
    print(header)
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for runtime in runtimes:
        print(format_row(build_row(runtime, metrics, logs_dir)))


if __name__ == "__main__":
    main()
