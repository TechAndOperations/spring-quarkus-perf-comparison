#!/usr/bin/env python3
"""Print a "Startup cost" markdown table row for each runtime, one core count at a time.

Same source as startup-cost.py's scatter (archived runs/*.json via _chartlib, one point
per runtime from the median-TTFR run) so the two stay consistent - see that file's
docstring for why a median run rather than a best-of. Monthly cost here is RAM-only
(no CPU, no throughput normalization): a Monthly cost figure elsewhere in this README
prices serving load at a target rate, but a runtime pays its startup RSS whether or not
it is serving anything, so this one just prices holding that RSS in memory for a month
at Azure's ~$0.0035/GB RAM-hour (times 730 hours/month).

Usage:

    ./startup-cost-table.py [cores]

With no argument, emits one table per core count present in the archive (densest
first), same as startup-cost.py's chart set.
"""

import sys
from pathlib import Path

from _chartlib import core_counts, fmt, heap_note, kind, load_startup, median_run

RAM_GB_HOUR_RATE = 0.0035
HOURS_PER_MONTH = 730


def monthly_cost(rss_mib):
    rss_gb = rss_mib / 1024
    return rss_gb * RAM_GB_HOUR_RATE * HOURS_PER_MONTH


def format_row(row):
    rt, xmx, ttfr, rss, _cores = row
    xmx_label = heap_note(xmx).removeprefix("-Xmx ") or "—"
    return f"| {rt} | {xmx_label} | {fmt(ttfr)} | {fmt(rss)} | ${monthly_cost(rss):.2f} |"


def print_table(cores):
    rows = median_run(load_startup(cores), key=lambda r: r[2])
    rows.sort(key=lambda r: r[2])

    print(f"#### {cores} core{'' if cores == '1' else 's'}")
    print()
    print("| Runtime | Xmx | Time to first request (ms) | RSS (MB) | Monthly cost ($) |")
    print("|---|---|---|---|---|")
    for row in rows:
        print(format_row(row))
    print()


def main():
    args = sys.argv[1:]
    counts = [args[0]] if args else core_counts()
    for cores in counts:
        print_table(cores)


if __name__ == "__main__":
    main()
