#!/usr/bin/env python3
"""Regenerate the build-time table in README.md's "2 cores" section.

Averaged across every archived 2-core run regardless of -Xmx: unlike density or
throughput, build time doesn't depend on the heap ceiling, so splitting by rung would
just fragment the same measurement instead of adding information.
"""

import glob
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
README = HERE / "README.md"
START = "<!-- build-times:start -->"
END = "<!-- build-times:end -->"


def cores_of(data):
    return str(((data.get("config") or {}).get("resources") or {}).get("app_cpus") or "?")


def main():
    totals = {}
    for f in sorted(glob.glob(str(HERE / "runs" / "*.json"))):
        data = json.load(open(f))
        if cores_of(data) != "2":
            continue
        for rt, v in data["results"].items():
            build_time = (v.get("build") or {}).get("avBuildTime")
            if build_time is not None:
                totals.setdefault(rt, []).append(build_time)

    rows = sorted(totals.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))

    lines = [
        "| Runtime | Runs averaged | Avg build (s) |",
        "|---|---|---|",
    ]
    for rt, values in rows:
        avg = sum(values) / len(values)
        lines.append(f"| {rt} | {len(values)} | {avg:.1f} |")

    table = "\n".join(lines)
    text = README.read_text()
    text = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        f"{START}\n{table}\n{END}",
        text,
        flags=re.DOTALL,
    )
    README.write_text(text)
    print(f"updated: {len(rows)} runtime(s)")


if __name__ == "__main__":
    main()
