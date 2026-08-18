#!/usr/bin/env python3
"""Render peak-throughput-closed-loop.svg for the "Peak throughput (closed loop)" table.

Throughput (req/s) and Max latency (ms) are different units, so putting them on one
axis would be the dual-axis mistake; two panels sharing the same runtime rows keep
each on its own honestly-scaled axis instead.

Throughput is linear with a zero baseline, drawn as a lollipop (stem + dot) rather
than a bare dot: with a real zero to anchor to, the stem reads as a magnitude the way
a bar would, without needing a separate horizontal-bar primitive. Max latency has no
such natural zero and spans a factor of ~9 across runtimes, so it's a plain dot on a
log axis instead - the pattern density-small-multiples.py's latency panel already
uses.

This is NOT derived from the archived metrics.json files via _chartlib.load(): the
"Peak throughput (closed loop)" table is a single one-off run (7 runtimes, one
`-Xmx512m` closed-loop pass), so its rows are transcribed here directly from that
table rather than recomputed from the archive.
"""

from pathlib import Path
import math

from _chartlib import FAMILY_LABEL, SHAPE_LABEL, fmt, kind, linear, log_scale, marker, svg

STEM = Path(__file__).resolve().parent / "peak-throughput-closed-loop"
W = 900
M = {"t": 96, "l": 150, "r": 24}
GAP = 60
ROW_H = 46
PANEL_W = (W - M["l"] - M["r"] - GAP) / 2

# runtime -> (throughput req/s, max latency ms, note)
# Transcribed from the "Peak throughput (closed loop)" table in README.md, same order
# (throughput descending) the table itself uses.
ROWS = [
    ("quarkus3-virtual", 7038.1, 70.52, "-Xmx 512m"),
    ("spring4-virtual", 5661.1, 154.49, "-Xmx 512m"),
    ("quarkus3-native", 4192.9, 258.65, "-Xmx 512m"),
    ("go-orm", 3370.0, 185.25, "—"),
    ("rust-orm", 2394.7, 124.08, "—"),
    ("spring4-native", 1736.1, 637.53, "-Xmx 512m"),
    ("nodejs-orm", 689.8, 496.33, "—"),
]

H = M["t"] + len(ROWS) * ROW_H + 70


def build():
    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Peak throughput and max latency, closed loop</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"2 cores · -Xmx 512m · closed-loop `always` model · ranked by throughput</text>"
    )

    tp_lo, tp_hi, tp_ticks = linear([0] + [r[1] for r in ROWS], target_ticks=5, pad=0.05, floor=0)
    lat_lo, lat_hi, lat_ticks = log_scale([r[2] for r in ROWS])
    lg = math.log10

    def panel_x(i):
        return M["l"] + i * (PANEL_W + GAP)

    def tp_px(v, px0):
        return px0 + (v - tp_lo) / (tp_hi - tp_lo) * PANEL_W

    def lat_px(v, px0):
        return px0 + (lg(v) - lg(lat_lo)) / (lg(lat_hi) - lg(lat_lo)) * PANEL_W

    row_y = {rt: M["t"] + 30 + j * ROW_H for j, (rt, *_r) in enumerate(ROWS)}

    for rt in row_y:
        o.append(
            f'<text x="{M["l"] - 12}" y="{row_y[rt] + 4:.1f}" fill="{ink}" font-size="11.5" '
            f'text-anchor="end">{rt}</text>'
        )

    panels = (
        ("Throughput (req/s)", tp_px, tp_ticks, 1),
        ("Max latency (ms)", lat_px, lat_ticks, 0),
    )
    bottom = M["t"] + len(ROWS) * ROW_H

    for i, (title, px, ticks, is_throughput) in enumerate(panels):
        px0 = panel_x(i)
        o.append(
            f'<text x="{px0:.1f}" y="{M["t"] - 6}" fill="{ink}" font-size="12" '
            f'font-weight="600">{title}</text>'
        )
        for t in ticks:
            x = px(t, px0)
            o.append(
                f'<line x1="{x:.1f}" y1="{M["t"]}" x2="{x:.1f}" y2="{bottom}" '
                f'stroke="{grid}" stroke-width="1"/>'
            )
            o.append(
                f'<text x="{x:.1f}" y="{bottom + 18}" fill="{ink2}" font-size="10.5" '
                f'text-anchor="middle">{fmt(t)}</text>'
            )

        for rt, throughput, maxlat, note in ROWS:
            fam, shape = kind(rt)
            y = row_y[rt]
            v = throughput if is_throughput else maxlat
            x = px(v, px0)
            if is_throughput:
                # A lollipop: the stem to a real zero reads as magnitude, like a bar.
                o.append(
                    f'<line x1="{px0:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
                    f'stroke="var(--{fam})" stroke-width="2"/>'
                )
            tip = f"{rt} · {note} · {'throughput' if is_throughput else 'max latency'} {v:g}"
            o.append(marker(shape, x, y, f"var(--{fam})", surface, tip, r=6.0))

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
