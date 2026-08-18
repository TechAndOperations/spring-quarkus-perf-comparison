"""Shared pieces for the result charts: data loading, scales, marks, palette.

Seven runtimes is past the point where each can hold its own hue - an all-pairs form
caps at three categorical slots. So colour carries the *family* (Quarkus / Spring /
non-JVM) and shape carries how the code runs (compiled binary vs virtual machine),
the composite encoding the method prescribes at this series count.

Slots 1-3 of the reference palette, validated --pairs all in both modes: worst CVD
dE 9.2 light / 9.4 dark. Aqua sits at 2.74:1 on the light surface, under the 3:1
bar, so the relief rule applies - every series carries a visible direct label.
"""

import glob
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

FAMILY_LABEL = {"quarkus": "Quarkus 3", "spring": "Spring Boot 4", "other": "Go · Rust · Node"}
SHAPE_LABEL = {"square": "Native binary", "circle": "Virtual machine"}

# runtime -> (family slot, shape)
KIND = {
    "quarkus3-virtual": ("quarkus", "circle"),
    "quarkus3-native": ("quarkus", "square"),
    "spring4-virtual": ("spring", "circle"),
    "spring4-native": ("spring", "square"),
    "go-orm": ("other", "square"),
    "rust-orm": ("other", "square"),
    "nodejs-orm": ("other", "circle"),
    "go-sql": ("other", "square"),
    "rust-sql": ("other", "square"),
    "nodejs-sql": ("other", "circle"),
}

CSS = """
  .viz { color-scheme: light; --surface-1:#fcfcfb; --text-primary:#0b0b0b;
         --text-secondary:#52514e; --grid:#e6e5e1;
         --quarkus:#2a78d6; --spring:#eb6834; --other:#1baf7a; }
  @media (prefers-color-scheme: dark) {
    .viz { color-scheme: dark; --surface-1:#1a1a19; --text-primary:#ffffff;
           --text-secondary:#c3c2b7; --grid:#333331;
           --quarkus:#3987e5; --spring:#d95926; --other:#199e70; }
  }"""


def kind(runtime):
    return KIND.get(runtime, ("other", "circle"))


def included(runtime):
    """Charts cover the ORM path only. The -sql variants answer a different question -
    hand-written SQL against the ecosystem's ORM, at runtime constant - and would double
    an already crowded axis. They stay in the README table."""
    return not runtime.endswith("-sql")


def cores_of(data):
    """Cores pinned to the app. Runs at different core counts are not comparable, so
    every consumer groups on this alongside the runtime name."""
    return str(((data.get("config") or {}).get("resources") or {}).get("app_cpus") or "?")


def cores_label(cores):
    return f"{cores} core" + ("" if cores == "1" else "s")


def heap_note(xmx):
    """What distinguishes two points of the same runtime *within* one chart. The core
    count is not in here: each chart covers a single core count and says so in its
    subtitle, because runs across core counts are not comparable at all."""
    return f"-Xmx {xmx}m" if xmx else ""


def core_counts():
    """Core counts present in the archive, densest first - one chart set per count."""
    return sorted({r[-1] for r in load()}, key=lambda c: -int(c))


def load(cores=None):
    """(runtime, xmx|None, throughput, rss, density, cores), optionally one core count.

    Cores come last so existing index-based unpacking keeps working."""
    rows = []
    for f in sorted(glob.glob(str(HERE / "runs" / "*.json"))):
        m = re.search(r"Xmx(\d+)m", f)
        xmx = int(m.group(1)) if m else None
        data = json.load(open(f))
        c = cores_of(data)
        if cores and c != cores:
            continue
        for rt, v in data["results"].items():
            load_ = v.get("load") or {}
            tp, rss = load_.get("avThroughput"), load_.get("avMaxRss")
            if not (tp and rss):
                continue
            d = load_.get("maxThroughputDensity") or tp / rss
            # -Xmx only reaches the Quarkus and Spring runCmds; elsewhere it is noise.
            if included(rt):
                rows.append((rt, xmx if kind(rt)[0] != "other" else None, tp, rss, d, c))
    return rows


def load_startup(cores=None):
    """(runtime, xmx|None, ttfr_ms, rss_first_request_mib, cores), optionally one core
    count.

    Only produced when the run included measure-time-to-first-request and measure-rss.
    """
    rows = []
    for f in sorted(glob.glob(str(HERE / "runs" / "*.json"))):
        m = re.search(r"Xmx(\d+)m", f)
        xmx = int(m.group(1)) if m else None
        data = json.load(open(f))
        c = cores_of(data)
        if cores and c != cores:
            continue
        for rt, v in data["results"].items():
            ttfr = (v.get("startup") or {}).get("avStartTime")
            rss = (v.get("rss") or {}).get("avFirstRequestRss")
            if ttfr and rss and included(rt):
                rows.append((rt, xmx if kind(rt)[0] != "other" else None, ttfr, rss, c))
    return rows


def median_run(rows, key):
    """One representative run per runtime and core count: the median by `key`, kept as a real
    observation so the reported pair was actually measured together rather than
    assembled from different rungs."""
    grouped = {}
    for row in rows:
        grouped.setdefault((row[0], row[-1]), []).append(row)
    out = []
    for rt, runs in grouped.items():
        runs.sort(key=key)
        out.append(runs[len(runs) // 2])
    return out


def linear(values, target_ticks, pad=0.08, floor=None):
    lo, hi = min(values), max(values)
    span = hi - lo
    lo, hi = lo - span * pad, hi + span * pad
    if floor is not None:
        lo = max(lo, floor)
    raw = (hi - lo) / target_ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    t, ticks = math.ceil(lo / step) * step, []
    while t <= hi:
        ticks.append(t)
        t += step
    return lo, hi, ticks


def log_scale(values):
    """Decade-anchored log domain with 1/2/5 ticks - RSS here spans a factor of 42."""
    lo, hi = min(values), max(values)
    lo, hi = lo / 1.35, hi * 1.2
    ticks = []
    d = 10 ** math.floor(math.log10(lo))
    while d <= hi:
        for m in (1, 2, 5):
            v = d * m
            if lo <= v <= hi:
                ticks.append(v)
        d *= 10
    return lo, hi, ticks


def zero_ticks(hi, target=5):
    raw = hi / target
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    out, v = [], 0.0
    while v < hi:
        out.append(v)
        v += step
    out.append(v)  # always overshoot, so the tallest mark stays inside the plot
    return out


def marker(shape, x, y, fill, ring, tip=None, r=6.0):
    """A <title> must be a *child* of the shape; as a sibling it renders nothing."""
    inner = f"<title>{tip}</title>" if tip else ""
    if shape == "circle":
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
            f'stroke="{ring}" stroke-width="2">{inner}</circle>'
        )
    s = r * 0.9
    return (
        f'<rect x="{x - s:.1f}" y="{y - s:.1f}" width="{2 * s:.1f}" height="{2 * s:.1f}" '
        f'rx="1.5" fill="{fill}" stroke="{ring}" stroke-width="2">{inner}</rect>'
    )


def bar(x, y, w, h, fill, tip):
    """Rounded data-end, square at the baseline - the corner marks where the value is."""
    r = min(4.0, w / 2, h)
    d = (
        f"M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"L{x + w - r:.1f},{y:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"L{x + w:.1f},{y + h:.1f} Z"
    )
    return f'<path d="{d}" fill="{fill}"><title>{tip}</title></path>'


def best_per_runtime(key, cores=None):
    """The rung that maximises `key` for each runtime *and core count*, ranked.

    Ties keep the roomier heap - the safer default when two ceilings score the same.
    Which rung wins depends on the measure: density peaks at a tight heap, raw
    throughput at a generous one.
    """
    best = {}
    for row in load(cores):
        g = (row[0], row[-1])  # runtime x cores: a 1-core run is not a 2-core run
        if g not in best or (key(row), row[1] or 0) > (key(best[g]), best[g][1] or 0):
            best[g] = row
    return sorted(best.values(), key=lambda r: -key(r))


def svg(w, h, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" '
        f'height="{h}" class="viz" font-family="system-ui,-apple-system,Segoe UI,sans-serif">'
        f"<style>{CSS}</style>{body}</svg>"
    )


def fmt(v):
    return f"{v:,.0f}".replace(",", " ")
