#!/usr/bin/env python3
"""Render density-cost-latency.svg for the "Density (open loop)" README table.

Monthly cost ($) and latency (ms) are different units, so no single position axis can
carry both - two panels sharing the same runtime rows keep each on its own honestly-
scaled axis instead, the same small-multiples pattern peak-throughput-closed-loop.py
and the density table's earlier chart both use.

The latency panel plots p50-to-p99.9 as a range mark (hollow dot at p50, filled dot at
p99, tick at p99.9, joined by a line) rather than a single mean - a runtime whose median
is fast but whose tail is long looks identical to a uniformly-mid runtime under "mean
alone"; the range makes that visible, and p99.9 alongside p99 shows whether the tail is
still climbing or has flattened out.

Both panels are logarithmic: cost spans a factor of ~3.8 and is inherently a ratio
question ("how many times more expensive"), and the p50-p99.9 range spans a comparable
spread across runtimes.

This is NOT derived from the archived metrics.json files via _chartlib.load(): the
"Density (open loop)" table is a hand-assembled, one-off sweep, so its rows are
transcribed here directly from that table.
"""

import math
from pathlib import Path

from _chartlib import FAMILY_LABEL, SHAPE_LABEL, fmt, kind, log_scale, marker, svg

STEM = Path(__file__).resolve().parent / "density-cost-latency"
W = 760
M = {"t": 112, "l": 150, "r": 24}
GAP = 40
ROW_H = 46
PANEL_W = (W - M["l"] - M["r"] - GAP) / 2

# runtime -> (monthly cost $ at 1000 req/s, p50 ms, p99 ms, p99.9 ms, note)
# Transcribed from the "Density (open loop)" table in README.md, same order (cost
# ascending) the table itself uses.
ROWS = [
    ("quarkus3-virtual", 12.97, 1.79, 7.17, 25.41, "-Xmx 48m"),
    ("rust-orm", 13.01, 4.98, 111.28, 163.58, "—"),
    ("spring4-virtual", 16.02, 1.98, 14.33, 76.94, "-Xmx 128m"),
    ("go-orm", 16.29, 13.70, 87.47, 167.95, "—"),
    ("quarkus3-native", 18.42, 2.50, 21.23, 46.75, "-Xmx 64m"),
    ("spring4-native", 31.47, 6.83, 92.97, 168.12, "-Xmx 256m, target-rate 1500"),
    ("nodejs-orm", 49.79, 3.66, 249.91, 284.51, "target-rate 500"),
]

H = M["t"] + len(ROWS) * ROW_H + 70


def build():
    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Cost and latency spread under the open-loop load test</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"2 cores · MALLOC_ARENA_MAX=2 · constantRate, 2000 req/s target · "
        f"ranked by cost</text>"
    )

    cost_lo, cost_hi, cost_ticks = log_scale([r[1] for r in ROWS])
    lat_lo, lat_hi, lat_ticks = log_scale([v for r in ROWS for v in (r[2], r[3], r[4])])
    lg = math.log10

    def panel_x(i):
        return M["l"] + i * (PANEL_W + GAP)

    def cost_px(v, px0):
        return px0 + (lg(v) - lg(cost_lo)) / (lg(cost_hi) - lg(cost_lo)) * PANEL_W

    def lat_px(v, px0):
        return px0 + (lg(v) - lg(lat_lo)) / (lg(lat_hi) - lg(lat_lo)) * PANEL_W

    row_y = {rt: M["t"] + 30 + j * ROW_H for j, (rt, *_r) in enumerate(ROWS)}
    bottom = M["t"] + len(ROWS) * ROW_H

    for rt in row_y:
        o.append(
            f'<text x="{M["l"] - 12}" y="{row_y[rt] + 4:.1f}" fill="{ink}" font-size="11.5" '
            f'text-anchor="end">{rt}</text>'
        )

    px0 = panel_x(0)
    o.append(
        f'<text x="{px0:.1f}" y="{M["t"] - 6}" fill="{ink}" font-size="12" '
        f'font-weight="600">Monthly cost, 1000 req/s ($)</text>'
    )
    o.append(f'<line x1="{px0:.1f}" y1="{M["t"]}" x2="{px0:.1f}" y2="{bottom}" stroke="{grid}" stroke-width="1"/>')
    for t in cost_ticks:
        x = cost_px(t, px0)
        o.append(f'<line x1="{x:.1f}" y1="{M["t"]}" x2="{x:.1f}" y2="{bottom}" stroke="{grid}" stroke-width="1"/>')
        o.append(
            f'<text x="{x:.1f}" y="{bottom + 18}" fill="{ink2}" font-size="10.5" '
            f'text-anchor="middle">${fmt(t)}</text>'
        )
    for rt, cost, p50, p99, p999, note in ROWS:
        fam, shape = kind(rt)
        y = row_y[rt]
        o.append(marker(shape, cost_px(cost, px0), y, f"var(--{fam})", surface, f"{rt} · {note} · cost ${cost:g}"))

    px1 = panel_x(1)
    o.append(
        f'<text x="{px1:.1f}" y="{M["t"] - 6}" fill="{ink}" font-size="12" '
        f'font-weight="600">Latency, p50→p99.9 (ms)</text>'
    )
    o.append(f'<line x1="{px1:.1f}" y1="{M["t"]}" x2="{px1:.1f}" y2="{bottom}" stroke="{grid}" stroke-width="1"/>')
    for t in lat_ticks:
        x = lat_px(t, px1)
        o.append(f'<line x1="{x:.1f}" y1="{M["t"]}" x2="{x:.1f}" y2="{bottom}" stroke="{grid}" stroke-width="1"/>')
        o.append(
            f'<text x="{x:.1f}" y="{bottom + 18}" fill="{ink2}" font-size="10.5" '
            f'text-anchor="middle">{fmt(t)}</text>'
        )
    for rt, cost, p50, p99, p999, note in ROWS:
        fam, shape = kind(rt)
        y = row_y[rt]
        x0, x1, x2 = lat_px(p50, px1), lat_px(p99, px1), lat_px(p999, px1)
        o.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="var(--{fam})" stroke-width="2"/>')
        o.append(marker("circle", x0, y, surface, f"var(--{fam})", f"{rt} · p50 {p50:g} ms", r=5.0))
        o.append(marker("circle", x1, y, f"var(--{fam})", surface, f"{rt} · p99 {p99:g} ms", r=5.0))
        # A whisker cap, not a third same-style dot: p99.9 marks how far the tail
        # still reaches beyond p99, not a peer measurement of the same kind.
        o.append(
            f'<line x1="{x2:.1f}" y1="{y - 5:.1f}" x2="{x2:.1f}" y2="{y + 5:.1f}" '
            f'stroke="var(--{fam})" stroke-width="2"><title>{rt} · p99.9 {p999:g} ms</title></line>'
        )

    ly = bottom + 44
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
