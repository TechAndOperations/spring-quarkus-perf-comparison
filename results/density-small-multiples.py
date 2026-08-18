#!/usr/bin/env python3
"""Render density-small-multiples.svg for the "Density (open loop)" README table.

Three measures - density (req/s per MB), CPU (%) and latency (ms) - live on three
different units, so no single position axis can carry all of them (that's the
dual-axis mistake density-cpu-scatter.py already avoids by crossing two of them on
x/y and folding the third into bubble size). Small multiples sidestep the problem
differently: one column per measure, each with its own honestly-scaled axis, sharing
the same row order so a runtime's story reads across the row.

The latency column plots p50-to-p99.9 as a range mark (hollow dot at p50, filled dot
at p99, tick at p99.9, joined by a line) rather than the mean density-cpu-scatter.py
uses - a runtime whose median is fast but whose tail is long looks identical to a
uniformly-mid runtime under "mean alone"; the range makes that visible, and p99.9
alongside p99 shows whether the tail is still climbing or has flattened out.

Density and latency columns are logarithmic (density spans a factor of 134 rust-orm
to nodejs-orm; the p50-p99.9 range spans a comparable spread). CPU stays linear - only
a factor of ~4 across runtimes, not enough to need it, and log would flatten the
difference the column exists to show.

This is NOT derived from the archived metrics.json files via _chartlib.load(): the
"Density (open loop)" table is a hand-assembled, one-off sweep, so its six rows are
transcribed here directly from that table. nodejs-orm was measured at a --target-rate
of 500 req/s instead of the other rows' 2000, so its CPU is adjusted (x4) before
plotting to put it back on the same footing; density and latency are plotted as
measured, since neither scales with target rate the way CPU load does.
"""

import math
from pathlib import Path

from _chartlib import FAMILY_LABEL, SHAPE_LABEL, fmt, kind, linear, log_scale, marker, svg

STEM = Path(__file__).resolve().parent / "density-small-multiples"
W = 980
M = {"t": 112, "l": 150, "r": 24}
GAP = 40
ROW_H = 46
PANEL_W = (W - M["l"] - M["r"] - 2 * GAP) / 3

# runtime -> (density, CPU adj. %, p50 ms, p99 ms, p99.9 ms, note)
# Transcribed from the "Density (open loop)" table in README.md, same order (density
# descending) the table itself uses.
ROWS = [
    ("rust-orm", 77.74, 94.7, 4.98, 111.28, 163.58, "—"),
    ("go-orm", 38.80, 118.7, 13.70, 87.47, 167.95, "—"),
    ("quarkus3-native", 13.65, 133.6, 2.50, 21.23, 46.75, "-Xmx 64m"),
    ("quarkus3-virtual", 8.39, 92.8, 1.79, 7.17, 25.41, "-Xmx 48m"),
    ("spring4-virtual", 4.89, 113.0, 1.98, 14.33, 76.94, "-Xmx 128m"),
    # Measured at --target-rate 1500 (vs. 2000 for the others): CPU x (2000/1500).
    ("spring4-native", 4.86, 226.27, 6.83, 92.97, 168.12, "-Xmx 256m, target-rate 1500, CPU adjusted"),
    # Measured at --target-rate 500 (vs. 2000 for the others): CPU x 4. Density and
    # p50/p99/p99.9 are plotted as measured - neither scales with target rate.
    ("nodejs-orm", 2.32, 352.8, 3.66, 249.91, 284.51, "target-rate 500, CPU adjusted"),
]

PANELS = (
    ("Density (req/s/MB)", "log", [r[1] for r in ROWS]),
    ("CPU, adjusted (%)", "linear", [r[2] for r in ROWS]),
    ("Latency, p50→p99.9 (ms)", "log", [v for r in ROWS for v in (r[3], r[4], r[5])]),
)

# Canvas grows with the row count so the legend never collides with the last row.
H = M["t"] + len(ROWS) * ROW_H + 46 + 52 + 20


def scales():
    out = []
    for _title, kind_, values in PANELS:
        if kind_ == "log":
            out.append(("log",) + log_scale(values))
        else:
            out.append(("linear",) + linear(values, target_ticks=4, pad=0.25))
    return out


def build():
    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Density, CPU and latency spread under the open-loop load test</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"2 cores · MALLOC_ARENA_MAX=2 · constantRate, 2000 req/s target · "
        f"ranked by density</text>"
    )

    panel_scales = scales()
    lg = math.log10

    def frac(kind_, lo, hi, v):
        return (lg(v) - lg(lo)) / (lg(hi) - lg(lo)) if kind_ == "log" else (v - lo) / (hi - lo)

    def panel_x(i):
        return M["l"] + i * (PANEL_W + GAP)

    row_y = {rt: M["t"] + 30 + j * ROW_H for j, (rt, *_r) in enumerate(ROWS)}

    # Row labels, once, left of the first panel.
    for rt in row_y:
        o.append(
            f'<text x="{M["l"] - 12}" y="{row_y[rt] + 4:.1f}" fill="{ink}" font-size="11.5" '
            f'text-anchor="end">{rt}</text>'
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
            f'<line x1="{px0:.1f}" y1="{M["t"]}" x2="{px0:.1f}" y2="{M["t"] + len(ROWS) * ROW_H}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        for t in ticks:
            x = px(t)
            o.append(
                f'<line x1="{x:.1f}" y1="{M["t"]}" x2="{x:.1f}" '
                f'y2="{M["t"] + len(ROWS) * ROW_H}" stroke="{grid}" stroke-width="1"/>'
            )
            o.append(
                f'<text x="{x:.1f}" y="{M["t"] + len(ROWS) * ROW_H + 18}" fill="{ink2}" '
                f'font-size="10.5" text-anchor="middle">{fmt(t)}</text>'
            )

        for rt, density, cpu, p50, p99, p999, note in ROWS:
            fam, shape = kind(rt)
            y = row_y[rt]
            if i == 0:
                o.append(marker(shape, px(density), y, f"var(--{fam})", surface, f"{rt} · {note} · density {density:g}"))
            elif i == 1:
                o.append(marker(shape, px(cpu), y, f"var(--{fam})", surface, f"{rt} · {note} · CPU {cpu:g}%"))
            else:
                x0, x1, x2 = px(p50), px(p99), px(p999)
                o.append(
                    f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
                    f'stroke="var(--{fam})" stroke-width="2"/>'
                )
                o.append(marker("circle", x0, y, surface, f"var(--{fam})", f"{rt} · p50 {p50:g} ms", r=5.0))
                o.append(marker("circle", x1, y, f"var(--{fam})", surface, f"{rt} · p99 {p99:g} ms", r=5.0))
                # A whisker cap, not a third same-style dot: p99.9 marks how far the tail
                # still reaches beyond p99, not a peer measurement of the same kind.
                o.append(
                    f'<line x1="{x2:.1f}" y1="{y - 5:.1f}" x2="{x2:.1f}" y2="{y + 5:.1f}" '
                    f'stroke="var(--{fam})" stroke-width="2">'
                    f"<title>{rt} · p99.9 {p999:g} ms</title></line>"
                )

    ly = M["t"] + len(ROWS) * ROW_H + 46
    o.append(
        f'<text x="{M["l"]}" y="{ly}" fill="{ink2}" font-size="11">'
        f"○ p50 · ● p99 · ┃ p99.9, joined by a line</text>"
    )

    lx = M["l"]
    o.append(f'<text x="{lx}" y="{ly + 28}" fill="{ink}" font-size="11.5" font-weight="600">Family</text>')
    for i, fam in enumerate(FAMILY_LABEL):
        x = lx + 65 + i * 150
        o.append(marker("circle", x, ly + 24, f"var(--{fam})", surface))
        o.append(f'<text x="{x + 13}" y="{ly + 28}" fill="{ink2}" font-size="11.5">{FAMILY_LABEL[fam]}</text>')

    o.append(f'<text x="{lx}" y="{ly + 52}" fill="{ink}" font-size="11.5" font-weight="600">Execution</text>')
    for i, shape in enumerate(SHAPE_LABEL):
        x = lx + 65 + i * 150
        o.append(marker(shape, x, ly + 48, ink2, surface))
        o.append(f'<text x="{x + 13}" y="{ly + 52}" fill="{ink2}" font-size="11.5">{SHAPE_LABEL[shape]}</text>')

    return svg(W, H, "".join(o))


out = Path(f"{STEM}.svg")
out.write_text(build())
print(f"wrote: {out}")
