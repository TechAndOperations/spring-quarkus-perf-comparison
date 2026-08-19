#!/usr/bin/env python3
"""Render peak-throughput-closed-loop.svg for the "Peak throughput (closed loop)" table.

Throughput (req/s), Monthly cost ($) and Max latency (ms) are three different units, so
no single position axis can carry all three - the small-multiples pattern already used
by density-small-multiples.py applies here too: one column per measure, each on its own
honestly-scaled axis, sharing the same runtime rows so a runtime's story reads across
the row.

All three panels are linear with a zero baseline: each measure here has a meaningful
zero and none spans more than an order of magnitude (~10x for throughput, ~7.6x for
cost, ~9x for Max latency), so a zero-anchored reading is more honest than a log axis
would be - unlike, say, density's ~134x spread, log doesn't earn its keep here.

This is NOT derived from the archived metrics.json files via _chartlib.load(): the
"Peak throughput (closed loop)" table is a single one-off run (7 runtimes, one
`-Xmx512m` closed-loop pass), so its rows are transcribed here directly from that table.
"""

import math
from pathlib import Path

from _chartlib import FAMILY_LABEL, SHAPE_LABEL, fmt, kind, linear, log_scale, marker, svg

BAR_H = 16


def hbar(x0, y, length, fill, tip, h=BAR_H):
    """Horizontal bar: square at the baseline (x0), rounded at the data end - the
    mirror of _chartlib.bar()'s vertical convention, rotated onto a row-based layout."""
    r = min(4.0, h / 2, length)
    top = y - h / 2
    d = (
        f"M{x0:.1f},{top + r:.1f} Q{x0:.1f},{top:.1f} {x0 + r:.1f},{top:.1f} "
        f"L{x0 + length - r:.1f},{top:.1f} Q{x0 + length:.1f},{top:.1f} {x0 + length:.1f},{top + r:.1f} "
        f"L{x0 + length:.1f},{top + h - r:.1f} Q{x0 + length:.1f},{top + h:.1f} {x0 + length - r:.1f},{top + h:.1f} "
        f"L{x0 + r:.1f},{top + h:.1f} Q{x0:.1f},{top + h:.1f} {x0:.1f},{top + h - r:.1f} Z"
    )
    return f'<path d="{d}" fill="{fill}"><title>{tip}</title></path>'

STEM = Path(__file__).resolve().parent / "peak-throughput-closed-loop"
W = 980
M = {"t": 96, "l": 170, "r": 24}
GAP = 40
ROW_H = 46
PANEL_W = (W - M["l"] - M["r"] - 2 * GAP) / 3

# JIT-compiled runtimes (JVM for Quarkus/Spring, V8 for Node) - see "Warmup time" above.
JIT_RUNTIMES = {"quarkus3-virtual", "spring4-virtual", "nodejs-orm", "nodejs-sql"}

# runtime -> (throughput req/s, monthly cost $ at 1000 req/s, max latency ms, note)
# Transcribed from the "Peak throughput (closed loop)" table in README.md, same order
# (throughput descending) the table itself uses.
ROWS = [
    ("quarkus3-virtual", 7038.1, 6.30, 70.52, "-Xmx 512m"),
    ("spring4-virtual", 5661.1, 9.31, 154.49, "-Xmx 512m"),
    ("quarkus3-native", 4192.9, 12.36, 258.65, "-Xmx 512m"),
    ("go-orm", 3370.0, 12.02, 185.25, "—"),
    ("nodejs-sql", 2461.5, 12.30, 116.74, "—"),
    ("rust-orm", 2394.7, 12.91, 124.08, "—"),
    ("spring4-native", 1736.1, 30.01, 637.53, "-Xmx 512m"),
    ("nodejs-orm", 1578.2, 20.38, 200.63, "—"),
]

PANELS = (
    ("Throughput (req/s)", "linear", [0] + [r[1] for r in ROWS]),
    ("Monthly cost, 1000 req/s ($)", "linear", [0] + [r[2] for r in ROWS]),
    ("Max latency (ms)", "linear", [0] + [r[3] for r in ROWS]),
)

H = M["t"] + len(ROWS) * ROW_H + 70


def scales():
    out = []
    for _title, kind_, values in PANELS:
        if kind_ == "log":
            out.append(("log",) + log_scale(values))
        else:
            out.append(("linear",) + linear(values, target_ticks=5, pad=0.05, floor=0))
    return out


def build():
    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Peak throughput, cost and max latency, closed loop</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"2 cores · -Xmx 512m · closed-loop `always` model · ranked by throughput</text>"
    )

    panel_scales = scales()
    lg = math.log10

    def frac(kind_, lo, hi, v):
        return (lg(v) - lg(lo)) / (lg(hi) - lg(lo)) if kind_ == "log" else (v - lo) / (hi - lo)

    def panel_x(i):
        return M["l"] + i * (PANEL_W + GAP)

    row_y = {rt: M["t"] + 30 + j * ROW_H for j, (rt, *_r) in enumerate(ROWS)}
    bottom = M["t"] + len(ROWS) * ROW_H

    for rt in row_y:
        label = f"{rt} (JIT)" if rt in JIT_RUNTIMES else rt
        o.append(
            f'<text x="{M["l"] - 12}" y="{row_y[rt] + 4:.1f}" fill="{ink}" font-size="11.5" '
            f'text-anchor="end">{label}</text>'
        )

    for i, ((title, kind_, _values), (skind, lo, hi, ticks)) in enumerate(zip(PANELS, panel_scales)):
        px0 = panel_x(i)

        def px(v, lo=lo, hi=hi, skind=skind, px0=px0):
            return px0 + frac(skind, lo, hi, v) * PANEL_W

        o.append(
            f'<text x="{px0:.1f}" y="{M["t"] - 6}" fill="{ink}" font-size="12" '
            f'font-weight="600">{title}</text>'
        )
        o.append(
            f'<line x1="{px0:.1f}" y1="{M["t"]}" x2="{px0:.1f}" y2="{bottom}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        for t in ticks:
            x = px(t)
            o.append(
                f'<line x1="{x:.1f}" y1="{M["t"]}" x2="{x:.1f}" y2="{bottom}" '
                f'stroke="{grid}" stroke-width="1"/>'
            )
            label = f"${fmt(t)}" if i == 1 else fmt(t)
            o.append(
                f'<text x="{x:.1f}" y="{bottom + 18}" fill="{ink2}" font-size="10.5" '
                f'text-anchor="middle">{label}</text>'
            )

        for rt, throughput, cost, maxlat, note in ROWS:
            fam, shape = kind(rt)
            y = row_y[rt]
            v = (throughput, cost, maxlat)[i]
            label = {0: "throughput", 1: "monthly cost", 2: "max latency"}[i]
            unit = {0: "req/s", 1: "$", 2: "ms"}[i]
            tip = f"{rt} · {note} · {label} {v:g} {unit}"
            x = px(v)
            o.append(hbar(px0, y, x - px0, f"var(--{fam})", tip))
            # The bar carries family (colour) and magnitude; a marker at its tip adds
            # execution mode (shape), the second half of this repo's composite encoding.
            o.append(marker(shape, x, y, f"var(--{fam})", surface, tip, r=5.0))

    ly = bottom + 44
    lx = M["l"]
    o.append(f'<text x="{lx}" y="{ly}" fill="{ink}" font-size="11.5" font-weight="600">Family</text>')
    for i, fam in enumerate(FAMILY_LABEL):
        x = lx + 65 + i * 150
        o.append(marker("circle", x, ly - 4, f"var(--{fam})", surface))
        o.append(f'<text x="{x + 13}" y="{ly}" fill="{ink2}" font-size="11.5">{FAMILY_LABEL[fam]}</text>')

    o.append(f'<text x="{lx}" y="{ly + 24}" fill="{ink}" font-size="11.5" font-weight="600">Execution</text>')
    for i, shape in enumerate(SHAPE_LABEL):
        x = lx + 65 + i * 150
        o.append(marker(shape, x, ly + 20, ink2, surface))
        o.append(f'<text x="{x + 13}" y="{ly + 24}" fill="{ink2}" font-size="11.5">{SHAPE_LABEL[shape]}</text>')

    return svg(W, H, "".join(o))


out = Path(f"{STEM}.svg")
out.write_text(build())
print(f"wrote: {out}")
