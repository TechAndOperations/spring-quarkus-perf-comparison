#!/usr/bin/env python3
"""Render density-ranking.svg from the archived metrics.json files.

One dot per runtime, ranked by throughput density (req/s per MiB of RSS under load).
Where a runtime was swept across heap ceilings, the rung shown is the one that
maximises density - not the one that maximises raw throughput, which
throughput-ranking.svg ranks instead.

A dot plot on a log axis, not bars. Density spans a factor of 62 across the seven
runtimes, and on a linear bar chart the five lowest collapsed into a few pixels each.
Bars cannot be rescued by a log axis - their length *is* the magnitude, so a log
length would misstate every ratio - but a dot encodes by *position*, which a log axis
represents honestly.
"""

import math
from pathlib import Path

from _chartlib import (FAMILY_LABEL, core_counts, cores_label, SHAPE_LABEL, best_per_runtime, heap_note, kind,
                       log_scale, marker, svg)

STEM = Path(__file__).resolve().parent / "density-ranking"
W, H = 900, 530
# t leaves room for three header lines *and* a clear gap before the legend, which is
# drawn just above the plot at t-24: at t=92 the third line ended one pixel above it.
M = {"t": 122, "r": 26, "b": 96, "l": 68}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]


def build(cores):
    rows = best_per_runtime(lambda r: r[4], cores)
    ylo, yhi, yt = log_scale([r[4] for r in rows])
    lg = math.log10

    def py(v):
        return M["t"] + PH - (lg(v) - lg(ylo)) / (lg(yhi) - lg(ylo)) * PH

    slot = PW / len(rows)
    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Throughput density, each runtime's best configuration</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"Requests per second per MiB of RSS under load · 3 iterations per run · "
        f"{cores_label(cores)} · logarithmic y-axis</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="67" fill="{ink2}" font-size="11.5">'
        f"Rust and Go do not export the same OpenTelemetry signals as the Java "
        f"modules: part of their lead measures what they do not instrument</text>"
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

    for i, (rt, xmx, tp, rss, dens, _c) in enumerate(rows):
        cx = M["l"] + i * slot + slot / 2
        y = py(dens)
        fam, shape = kind(rt)
        note = heap_note(xmx)

        # A faint drop line to the category tick: on a log axis there is no zero to
        # anchor a stem to, so this only helps the eye find the column, and stays
        # recessive enough not to read as a bar.
        o.append(
            f'<line x1="{cx:.1f}" y1="{y + 10:.1f}" x2="{cx:.1f}" y2="{M["t"] + PH}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        o.append(
            marker(
                shape,
                cx,
                y,
                f"var(--{fam})",
                surface,
                f"{rt} · {note} · {dens:.2f} tps/MiB · {tp:.0f} req/s · {rss:.1f} MiB",
                r=8.0,
            )
        )
        o.append(
            f'<text x="{cx:.1f}" y="{y - 15:.1f}" fill="{ink}" font-size="12.5" '
            f'font-weight="600" text-anchor="middle">{dens:.1f}</text>'
        )
        o.append(
            f'<text x="{cx:.1f}" y="{M["t"] + PH + 20:.0f}" fill="{ink}" font-size="11.5" '
            f'text-anchor="middle">{rt}</text>'
        )
        o.append(
            f'<text x="{cx:.1f}" y="{M["t"] + PH + 36:.0f}" fill="{ink2}" font-size="10.5" '
            f'text-anchor="middle">{note}</text>'
        )
        o.append(
            f'<text x="{cx:.1f}" y="{M["t"] + PH + 50:.0f}" fill="{ink2}" font-size="10.5" '
            f'text-anchor="middle">{tp:.0f} req/s · {rss:.0f} MiB</text>'
        )

    o.append(
        f'<text transform="translate(18,{M["t"] + PH / 2:.0f}) rotate(-90)" fill="{ink2}" '
        f'font-size="12" text-anchor="middle">Density (req/s per MiB, log scale)</text>'
    )

    for i, fam in enumerate(FAMILY_LABEL):
        x = M["l"] + 4 + i * 150
        o.append(f'<rect x="{x}" y="{M["t"] - 24}" width="10" height="10" rx="2" fill="var(--{fam})"/>')
        o.append(f'<text x="{x + 16}" y="{M["t"] - 15}" fill="{ink2}" font-size="11.5">{FAMILY_LABEL[fam]}</text>')
    for i, shape in enumerate(SHAPE_LABEL):
        x = M["l"] + 500 + i * 132
        o.append(marker(shape, x + 5, M["t"] - 19, ink2, surface, r=5.0))
        o.append(f'<text x="{x + 16}" y="{M["t"] - 15}" fill="{ink2}" font-size="11.5">{SHAPE_LABEL[shape]}</text>')

    return svg(W, H, "".join(o))


for _cores in core_counts():
    out = Path(f"{STEM}-{_cores}c.svg")
    out.write_text(build(_cores))
    print(f"wrote: {out}")
