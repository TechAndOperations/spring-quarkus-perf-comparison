#!/usr/bin/env python3
"""Render density-cost-per-request.svg for the "Density and Cost - November 2026" README section.

Cost of serving one million requests (USD, Azure on-demand rates) against the request rate,
for Quarkus native, Quarkus on the JVM with virtual threads, Spring Boot with virtual threads and
NestJS (Node.js).

Like density-cost-latency.py, this is NOT derived from the archived metrics.json files: the
numbers are transcribed from the table in the README section. Each point is
  "m" - measured (3 iterations, strict p99 < 50 ms rule),
  "i" - interpolated between two measured rates,
  "x" - extrapolated with replicas: the load is split evenly over the smallest number of pods that
        keeps each pod at or below the runtime's optimum (no fixed per-pod cost).
Both axes are logarithmic: the rate spans three decades and the price falls by more than an order of
magnitude, and a linear X axis would squeeze the low-load range, where memory decides the ranking,
against the Y axis.
"""

import math
from pathlib import Path

from _chartlib import marker, svg

STEM = Path(__file__).resolve().parent / "density-cost-per-request"

# (rate req/s, USD per 1M requests, kind)
NATIVE = [
    (10, 0.0319, "m"),
    (50, 0.0177, "m"),
    (100, 0.0169, "m"),
    (250, 0.0136, "m"),
    (500, 0.0102, "m"),
    (750, 0.0100, "m"),
    (1000, 0.0087, "m"),
    (1250, 0.0082, "i"),
    (1500, 0.0078, "m"),
    (2000, 0.0071, "m"),
    (2500, 0.0082, "x"),
    (3000, 0.0078, "x"),
    (3500, 0.0074, "x"),
    (4000, 0.0071, "x"),
    (4500, 0.0078, "x"),
    (5000, 0.0075, "x"),
    (5500, 0.0073, "x"),
    (6000, 0.0071, "x"),
    (7000, 0.0074, "x"),
    (8000, 0.0071, "x"),
    (9000, 0.0074, "x"),
    (10000, 0.0071, "x"),
]
VIRTUAL = [
    (10, 0.0491, "m"),
    (50, 0.0212, "m"),
    (100, 0.0157, "m"),
    (250, 0.0114, "m"),
    (500, 0.0094, "m"),
    (750, 0.0084, "m"),
    (1000, 0.0067, "m"),
    (1250, 0.0062, "i"),
    (1500, 0.0057, "m"),
    (2000, 0.0050, "m"),
    (2500, 0.0044, "m"),
    (3000, 0.0040, "m"),
    (3500, 0.0037, "m"),
    (4000, 0.0035, "m"),
    (4500, 0.0032, "m"),
    (5000, 0.0030, "m"),
    (5500, 0.0028, "m"),
    (6000, 0.0040, "x"),
    (7000, 0.0037, "x"),
    (8000, 0.0035, "x"),
    (9000, 0.0032, "x"),
    (10000, 0.0030, "x"),
]
SPRING = [
    (10, 0.0635, "m"),
    (50, 0.0242, "m"),
    (100, 0.0181, "m"),
    (250, 0.0129, "m"),
    (500, 0.0103, "m"),
    (750, 0.0096, "m"),
    (1000, 0.0081, "m"),
    (1250, 0.0075, "i"),
    (1500, 0.0070, "m"),
    (2000, 0.0062, "m"),
    (2500, 0.0056, "m"),
    (3000, 0.0070, "x"),
    (3500, 0.0066, "x"),
    (4000, 0.0062, "x"),
    (4500, 0.0059, "x"),
    (5000, 0.0056, "x"),
    (5500, 0.0064, "x"),
    (6000, 0.0062, "x"),
    (7000, 0.0058, "x"),
    (8000, 0.0062, "x"),
    (9000, 0.0059, "x"),
    (10000, 0.0056, "x"),
]
NODE = [
    (10, 0.0511, "m"),
    (50, 0.0235, "m"),
    (100, 0.0168, "m"),
    (250, 0.0134, "m"),
    (500, 0.0105, "m"),
    (750, 0.0101, "m"),
    (1000, 0.0093, "m"),
    (1250, 0.0091, "m"),
    (1500, 0.0101, "x"),
    (2000, 0.0093, "x"),
    (2500, 0.0091, "x"),
    (3000, 0.0093, "x"),
    (3500, 0.0091, "x"),
    (4000, 0.0093, "x"),
    (4500, 0.0092, "x"),
    (5000, 0.0091, "x"),
    (5500, 0.0092, "x"),
    (6000, 0.0091, "x"),
    (7000, 0.0091, "x"),
    (8000, 0.0092, "x"),
    (9000, 0.0092, "x"),
    (10000, 0.0091, "x"),
]

SERIES = [
    ("quarkus3-native", NATIVE, "quarkus", "square", "7 5"),
    ("quarkus3-virtual", VIRTUAL, "quarkus", "circle", ""),
    ("spring4-virtual", SPRING, "spring", "circle", ""),
    ("nodejs-orm", NODE, "other", "circle", ""),
]

W, H = 900, 520
M = {"t": 96, "r": 150, "b": 70, "l": 78}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]
XLO, XHI = 8, 13000
YLO, YHI = 0.0022, 0.07
Y_TICKS = [0.003, 0.005, 0.01, 0.02, 0.05]


def px(v):
    return M["l"] + (math.log10(v) - math.log10(XLO)) / (math.log10(XHI) - math.log10(XLO)) * PW


def py(v):
    return M["t"] + PH - (math.log10(v) - math.log10(YLO)) / (math.log10(YHI) - math.log10(YLO)) * PH


def build():
    ink, ink2, grid, surface = "var(--text-primary)", "var(--text-secondary)", "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']
    o.append(f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">Cost of one million requests vs request rate</text>')
    o.append(
        f'<text x="{M["l"]}" y="51" fill="{ink2}" font-size="12.5">USD, Azure on-demand rates ($0.0375 per vCPU-hour, '
        f"$0.0035 per GB-hour) &#183; 2 cores &#183; open loop &#183; 3 iterations</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="69" fill="{ink2}" font-size="12.5">Filled marker, solid line: measured &#183; '
        f"hollow diamond, dotted line: extrapolated with replicas &#183; both axes are logarithmic</text>"
    )
    for t in Y_TICKS:
        y = py(t)
        o.append(f'<line x1="{M["l"]}" x2="{M["l"] + PW}" y1="{y:.1f}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>')
        o.append(f'<text x="{M["l"] - 8}" y="{y + 4:.1f}" fill="{ink2}" font-size="11.5" text-anchor="end">{t:g}</text>')
    for v in (10, 50, 100, 500, 1000, 5000, 10000):
        x = px(v)
        o.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{M["t"]}" y2="{M["t"] + PH}" stroke="{grid}" stroke-width="1"/>')
        o.append(f'<text x="{x:.1f}" y="{M["t"] + PH + 18}" fill="{ink2}" font-size="11.5" text-anchor="middle">{v:,}</text>')
    o.append(f'<text x="{M["l"] + PW / 2}" y="{H - 16}" fill="{ink2}" font-size="12" text-anchor="middle">Request rate (req/s)</text>')
    o.append(
        f'<text transform="translate(18,{M["t"] + PH / 2}) rotate(-90)" fill="{ink2}" font-size="12" '
        f'text-anchor="middle">USD per 1M requests</text>'
    )

    labels = []
    for name, pts, fam, shape, dash in SERIES:
        col = f"var(--{fam})"
        solid = [p for p in pts if p[2] != "x"]
        ext = [p for p in pts if p[2] == "x"]

        def path(pp, dd):
            d = " ".join(f'{"M" if i == 0 else "L"}{px(r):.1f},{py(v):.1f}' for i, (r, v, _) in enumerate(pp))
            extra = f' stroke-dasharray="{dd}"' if dd else ""
            return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="2.2" stroke-linejoin="round"{extra}/>'

        o.append(path(solid, dash))
        if ext:
            o.append(path([solid[-1]] + ext, "2 4"))
        for r, v, k in pts:
            x, y = px(r), py(v)
            tip = f"{name} &#183; {r:,} req/s &#183; ${v:.4f} per 1M requests" + {"m": "", "i": " (interpolated)", "x": " (extrapolated)"}[k]
            if k == "x":
                o.append(
                    f'<path d="M{x:.1f},{y - 6.5:.1f} L{x + 6.5:.1f},{y:.1f} L{x:.1f},{y + 6.5:.1f} L{x - 6.5:.1f},{y:.1f} Z" '
                    f'fill="{surface}" stroke="{col}" stroke-width="2"><title>{tip}</title></path>'
                )
            else:
                o.append(marker(shape, x, y, col, surface, tip, r=5.0))
        r, v, _ = pts[-1]
        labels.append([py(v), name, col, px(r), py(v)])

    labels.sort()
    for i in range(1, len(labels)):
        if labels[i][0] - labels[i - 1][0] < 16:
            labels[i][0] = labels[i - 1][0] + 16
    for y, name, col, lx, ly in labels:
        o.append(
            f'<line x1="{lx + 9:.1f}" y1="{ly:.1f}" x2="{M["l"] + PW + 8}" y2="{y:.1f}" stroke="{col}" '
            f'stroke-width="1" stroke-dasharray="2 3"/>'
        )
        o.append(f'<text x="{M["l"] + PW + 12}" y="{y + 4:.1f}" fill="{ink}" font-size="12.5" font-weight="600">{name}</text>')
    return svg(W, H, "".join(o))


out = Path(f"{STEM}.svg")
out.write_text(build())
print(f"wrote: {out}")
