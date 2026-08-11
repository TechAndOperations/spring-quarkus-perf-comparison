#!/usr/bin/env python3
"""Archive a benchmark run's metrics.json here under a descriptive name, and index it in README.md.

The perf-lab pipeline overwrites /tmp/metrics.json on every run, so results survive only until the
next one starts. Usage:

    ./archive.py [path-to-metrics.json]     # defaults to /tmp/metrics.json

Re-running on an already-archived file is a no-op: the name is derived from the run's own start
timestamp, so the same run always maps to the same filename and is skipped if present.
"""

import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
README = HERE / "README.md"
RUNS_MARKER = "<!-- runs -->"
RESULTS_MARKER = "<!-- results -->"


def condense(memory, args):
    """`-Xms512m -Xmx512m` + `-XX:+UseParallelGC` -> `Xms512m-Xmx512m_ParallelGC`."""
    parts = [t.lstrip("-") for t in (memory or "").split() if t]
    for token in (args or "").split():
        parts.append(token.replace("-XX:+Use", "").replace("-XX:+", "").lstrip("-"))
    return "-".join(parts[:2]) + ("_" + "_".join(parts[2:]) if parts[2:] else "") or "default"


def heap_ceiling(runtime, memory):
    """The -Xmx the runtime was actually given, or `-` when the flag does not reach it.

    main.yml appends config.jvm.memory to every Quarkus and Spring runCmd, native images included -
    GraalVM honours -Xmx just like the JVM. The Go and Rust runCmds take no memory flag at all, and
    Node gets config.node.args (--max-old-space-size) instead, which is a different knob.
    """
    if not runtime.startswith(("quarkus", "spring")):
        return "-"

    found = re.search(r"-Xmx(\S+)", memory or "")
    return found.group(1) if found else "-"


def app_cores(resources):
    """How many cores the application under test was pinned to.

    run-benchmarks.sh already counts them into config.resources.app_cpus, so that wins. The fallback
    parses config.resources.cpu.app, a taskset list where `0-1` is two cores, `0` is one and
    `10,11,2` is three - a plain length would read the first as one core and the last as eight.
    """
    resources = resources or {}
    if resources.get("app_cpus"):
        return str(resources["app_cpus"])

    total = 0
    for chunk in ((resources.get("cpu") or {}).get("app") or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            low, _, high = chunk.partition("-")
            first = int(low)  # parsed in both branches, so a non-numeric chunk is caught
            total += int(high) - first + 1 if high else 1
        except ValueError:
            return "-"

    return str(total) if total else "-"


def num(value, digits=0, thousands=False):
    """Format a metric, or `-` when the run did not produce it (a test that was not selected)."""
    if value is None:
        return "-"
    if digits == 0:
        text = f"{round(value):,}".replace(",", " ") if thousands else str(round(value))
        return text
    return f"{value:.{digits}f}"


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/metrics.json")
    data = json.loads(src.read_text())

    results = data.get("results") or {}
    if not results:
        sys.exit(f"{src}: no results section - aborted run, nothing to archive")

    config = data.get("config") or {}
    timing = data.get("timing") or {}
    jvm = config.get("jvm") or {}
    repo = config.get("repo") or {}

    stamp = (timing.get("start") or timing.get("stop") or "unknown")
    stamp = stamp.replace("-", "").replace(":", "").replace("T", "_").rstrip("Z")[:13]

    runtimes = sorted(results)
    label = "+".join(runtimes) if len(runtimes) <= 4 else f"{len(runtimes)}runtimes"
    iterations = str(config.get("num_iterations") or "?")

    name = f"{stamp}__{label}__{condense(jvm.get('memory'), jvm.get('args'))}_{iterations}it.json"
    dest = HERE / name

    if dest.exists():
        print(f"already archived: {name}")
        return

    shutil.copy2(src, dest)

    index_row = (
        f"| [`{name}`]({name}) "
        f"| {timing.get('start', '?')} "
        f"| {', '.join(runtimes)} "
        f"| {iterations} "
        f"| `{jvm.get('memory') or '-'}` `{jvm.get('args') or '-'}` "
        f"| {repo.get('scenario') or '-'} |"
    )

    result_rows = []
    for rt in runtimes:
        entry = results[rt]
        build = entry.get("build") or {}
        rss = entry.get("rss") or {}
        startup = entry.get("startup") or {}
        load = entry.get("load") or {}

        density = load.get("maxThroughputDensity")
        if density is None and load.get("avThroughput") and load.get("avMaxRss"):
            density = load["avThroughput"] / load["avMaxRss"]

        result_rows.append(
            f"| `{name.split('__')[0]}` "
            f"| {rt} "
            f"| {app_cores(config.get('resources'))} "
            f"| {heap_ceiling(rt, jvm.get('memory'))} "
            f"| {num(build.get('avBuildTime'), 1)} "
            f"| {num(startup.get('avStartTime'), 0, thousands=True)} "
            f"| {num(rss.get('avFirstRequestRss'), 1)} "
            f"| {num(load.get('avMaxRss'), 1)} "
            f"| {num(load.get('avThroughput'), 0, thousands=True)} "
            f"| {num(density, 2)} |"
        )

    # Rows go *above* the marker, which therefore sits on the last line of each table. A marker
    # between the header separator and the rows would end the table there as far as Markdown is
    # concerned, and every row below it would render as one run-on paragraph.
    text = README.read_text()
    text = text.replace(RUNS_MARKER, index_row + "\n" + RUNS_MARKER)
    text = text.replace(RESULTS_MARKER, "\n".join(result_rows) + "\n" + RESULTS_MARKER)
    README.write_text(text)

    print(f"archived: {name}")
    print(f"  {len(result_rows)} runtime(s) indexed")


if __name__ == "__main__":
    main()
