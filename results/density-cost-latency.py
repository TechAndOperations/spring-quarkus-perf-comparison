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

Both panels are linear with a zero baseline: cost spans a factor of ~3.8 and latency's
p50-p99.9 range, while wider, still reads more honestly zero-anchored - the same
zero-baseline reasoning peak-throughput-closed-loop.py's panels use.

This is NOT derived from the archived metrics.json files via _chartlib.load(): the
"Density (open loop)" table is a hand-assembled, one-off sweep, so its rows are
transcribed here directly from that table.
"""

from pathlib import Path

from _chartlib import FAMILY_LABEL, SHAPE_LABEL, fmt, kind, linear, marker, svg

STEM = Path(__file__).resolve().parent / "density-cost-latency"
W = 760
M = {"t": 112, "l": 170, "r": 24}
GAP = 40
ROW_H = 46
BAR_H = 16

# JIT-compiled runtimes (JVM for Quarkus/Spring, V8 for Node) - see "Warmup time" above.
JIT_RUNTIMES = {"quarkus3-virtual", "spring4-virtual", "nodejs-orm", "nodejs-sql"}
PANEL_W = (W - M["l"] - M["r"] - GAP) / 2


def hbar(x0, y, length, fill, tip, h=BAR_H):
    """Zero-anchored bar: square at the baseline (x0), rounded at the data end."""
    r = min(4.0, h / 2, length)
    top = y - h / 2
    d = (
        f"M{x0:.1f},{top + r:.1f} Q{x0:.1f},{top:.1f} {x0 + r:.1f},{top:.1f} "
        f"L{x0 + length - r:.1f},{top:.1f} Q{x0 + length:.1f},{top:.1f} {x0 + length:.1f},{top + r:.1f} "
        f"L{x0 + length:.1f},{top + h - r:.1f} Q{x0 + length:.1f},{top + h:.1f} {x0 + length - r:.1f},{top + h:.1f} "
        f"L{x0 + r:.1f},{top + h:.1f} Q{x0:.1f},{top + h:.1f} {x0:.1f},{top + h - r:.1f} Z"
    )
    return f'<path d="{d}" fill="{fill}"><title>{tip}</title></path>'



# runtime -> (monthly cost $ at 1000 req/s, p50 ms, p99 ms, p99.9 ms, note)
# Transcribed from the "Density (open loop)" table in README.md, same order (cost
# ascending) the table itself uses.
ROWS = [
    ("quarkus3-virtual", 9.67, 2.03, 9.72, 53.22, "-Xmx 128m, target-rate 3400"),
    ("rust-orm", 12.72, 3.80, 21.15, 47.23, "target-rate 1800"),
    ("nodejs-sql", 15.67, 1.67, 26.61, 47.97, "target-rate 1400"),
    ("spring4-virtual", 16.68, 1.82, 5.96, 22.19, "-Xmx 128m, target-rate 1700"),
    ("quarkus3-native", 18.42, 2.50, 21.23, 46.75, "-Xmx 64m"),
    ("go-orm", 20.17, 12.76, 63.09, 81.09, "target-rate 1500"),
    ("nodejs-orm", 23.66, 2.02, 30.02, 57.06, "target-rate 1000"),
    ("spring4-native", 32.58, 4.05, 55.23, 94.37, "-Xmx 256m, target-rate 1300"),
]

H = M["t"] + len(ROWS) * ROW_H + 110


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

    cost_lo, cost_hi, cost_ticks = linear([0] + [r[1] for r in ROWS], target_ticks=5, pad=0.05, floor=0)
    lat_lo, lat_hi, lat_ticks = linear(
        [0] + [v for r in ROWS for v in (r[2], r[3], r[4])], target_ticks=5, pad=0.05, floor=0
    )

    def panel_x(i):
        return M["l"] + i * (PANEL_W + GAP)

    def cost_px(v, px0):
        return px0 + (v - cost_lo) / (cost_hi - cost_lo) * PANEL_W

    def lat_px(v, px0):
        return px0 + (v - lat_lo) / (lat_hi - lat_lo) * PANEL_W

    row_y = {rt: M["t"] + 30 + j * ROW_H for j, (rt, *_r) in enumerate(ROWS)}
    bottom = M["t"] + len(ROWS) * ROW_H

    for rt in row_y:
        label = f"{rt} (JIT)" if rt in JIT_RUNTIMES else rt
        o.append(
            f'<text x="{M["l"] - 12}" y="{row_y[rt] + 4:.1f}" fill="{ink}" font-size="11.5" '
            f'text-anchor="end">{label}</text>'
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
        x = cost_px(cost, px0)
        tip = f"{rt} · {note} · cost ${cost:g}"
        o.append(hbar(px0, y, x - px0, f"var(--{fam})", tip))
        o.append(marker(shape, x, y, f"var(--{fam})", surface, tip, r=5.0))

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
