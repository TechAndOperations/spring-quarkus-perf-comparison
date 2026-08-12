#!/usr/bin/env python3
"""Render startup-cost.svg from the archived metrics.json files.

Time to first request against the RSS measured just after that request - the two
costs a runtime pays before it has served anything useful. Lower-left is better on
both counts.

A scatter, not two bar charts: these are different units, and putting them on one
plot with two y-scales is the dual-axis mistake. Crossing them on x and y keeps a
single chart and shows the startup *profile* rather than two rankings.

Both axes are logarithmic. TTFR spans a factor of 312 across the seven runtimes (29
ms for Rust against 9 s for Spring on the JVM) and the RSS a factor of 54; on linear
axes the four fastest runtimes collapse into the corner.

One point per runtime, from the run with the median TTFR - a real observation, not a
best-of assembled from different heap ceilings. -Xmx barely moves these two measures
for Quarkus but shifts Spring's first-request RSS by up to 31%, which this single
point necessarily hides; the archived JSON keeps every rung.
"""

import math
from pathlib import Path

from _chartlib import (
    FAMILY_LABEL,
    SHAPE_LABEL,
    core_counts,
    cores_label,
    fmt,
    heap_note,
    kind,
    load_startup,
    log_scale,
    marker,
    median_run,
    svg,
)

STEM = Path(__file__).resolve().parent / "startup-cost"
W, H = 900, 560
M = {"t": 122, "r": 168, "b": 66, "l": 74}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]

# Vertical offset and horizontal anchor per label, tuned against the rendered geometry
# so none rides its own marker, a neighbour, or the plot edge. The two extreme points
# anchor to their inner side: centred, they would spill left of the axis and right into
# the legend once the RSS value lengthened them.
LABEL_AT = {
    "rust-orm": (-17, "start"),
    "go-orm": (24, "middle"),
    "quarkus3-native": (-17, "middle"),
    "nodejs-orm": (24, "middle"),
    "spring4-native": (-17, "middle"),
    "quarkus3-virtual": (24, "middle"),
    "spring4-virtual": (-17, "end"),
}


def build(cores):
    rows = median_run(load_startup(cores), key=lambda r: r[2])
    xlo, xhi, xt = log_scale([r[2] for r in rows])
    ylo, yhi, yt = log_scale([r[3] for r in rows])
    lg = math.log10

    def px(v):
        return M["l"] + (lg(v) - lg(xlo)) / (lg(xhi) - lg(xlo)) * PW

    def py(v):
        return M["t"] + PH - (lg(v) - lg(ylo)) / (lg(yhi) - lg(ylo)) * PH

    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Startup cost: delay and memory before the first response</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"One point per runtime, median-TTFR run · {cores_label(cores)} · "
        f"bottom-left is cheapest</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="67" fill="{ink2}" font-size="11.5">'
        f"Both axes logarithmic: TTFR varies by a factor of 312 between Rust and "
        f"Spring on the JVM, RSS by a factor of 54</text>"
    )

    for t in yt:
        y = py(t)
        o.append(
            f'<line x1="{M["l"]}" y1="{y:.1f}" x2="{M["l"] + PW}" y2="{y:.1f}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        o.append(
            f'<text x="{M["l"] - 10}" y="{y + 4:.1f}" fill="{ink2}" font-size="11.5" '
            f'text-anchor="end">{t:.0f}</text>'
        )
    for t in xt:
        x = px(t)
        o.append(
            f'<line x1="{x:.1f}" y1="{M["t"]}" x2="{x:.1f}" y2="{M["t"] + PH}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        o.append(
            f'<text x="{x:.1f}" y="{M["t"] + PH + 22}" fill="{ink2}" font-size="11.5" '
            f'text-anchor="middle">{fmt(t)}</text>'
        )

    o.append(
        f'<text x="{M["l"] + PW / 2:.0f}" y="{H - 14}" fill="{ink2}" font-size="12" '
        f'text-anchor="middle">Time to first response (ms, log scale)</text>'
    )
    o.append(
        f'<text transform="translate(20,{M["t"] + PH / 2:.0f}) rotate(-90)" fill="{ink2}" '
        f'font-size="12" text-anchor="middle">RSS after the 1st request (MiB, log scale)</text>'
    )

    for rt, xmx, ttfr, rss, _c in sorted(rows, key=lambda r: r[2]):
        fam, shape = kind(rt)
        note = heap_note(xmx)
        o.append(
            marker(
                shape,
                px(ttfr),
                py(rss),
                f"var(--{fam})",
                surface,
                f"{rt} · {note} · {ttfr:.0f} ms · {rss:.1f} MiB",
                r=7.0,
            )
        )
        # The RSS rides in the label so each point states its own y value; below 10 MiB
        # a decimal still carries information, above it the integer is enough. The core
        # count is abbreviated to `2c`: spelled out it pushed the longest labels past the
        # axis, and two points of one runtime differ only by it.
        shown = f"{rss:.1f}" if rss < 10 else f"{rss:.0f}"
        dy, anchor = LABEL_AT.get(rt, (-17, "middle"))
        o.append(
            f'<text x="{px(ttfr):.1f}" y="{py(rss) + dy:.1f}" fill="{ink2}" '
            f'font-size="10.5" text-anchor="{anchor}">{rt} · {shown} MiB</text>'
        )

    lx, ly = M["l"] + PW + 26, M["t"] + 6
    o.append(f'<text x="{lx}" y="{ly}" fill="{ink}" font-size="11.5" font-weight="600">Family</text>')
    for i, fam in enumerate(FAMILY_LABEL):
        y = ly + 22 + i * 21
        o.append(marker("circle", lx + 7, y - 4, f"var(--{fam})", surface))
        o.append(f'<text x="{lx + 20}" y="{y}" fill="{ink2}" font-size="11.5">{FAMILY_LABEL[fam]}</text>')
    o.append(f'<text x="{lx}" y="{ly + 103}" fill="{ink}" font-size="11.5" font-weight="600">Execution</text>')
    for i, shape in enumerate(SHAPE_LABEL):
        y = ly + 125 + i * 21
        o.append(marker(shape, lx + 7, y - 4, ink2, surface))
        o.append(f'<text x="{lx + 20}" y="{y}" fill="{ink2}" font-size="11.5">{SHAPE_LABEL[shape]}</text>')

    return svg(W, H, "".join(o))


for _cores in core_counts():
    out = Path(f"{STEM}-{_cores}c.svg")
    out.write_text(build(_cores))
    print(f"wrote: {out}")
