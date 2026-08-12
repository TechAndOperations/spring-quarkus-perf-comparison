#!/usr/bin/env python3
"""Render throughput-ranking.svg from the archived metrics.json files.

One bar per runtime, ranked by its best throughput. Where a runtime was swept across
heap ceilings, the rung shown is the one that maximises throughput - which is not the
rung that maximises density: raw speed wants a generous heap, efficiency a tight one.
density-ranking.svg ranks the same runtimes on the other measure.

Bars are anchored at zero on a linear scale - bar length is the magnitude. The spread
here is a factor of 10, so every bar stays readable, unlike the density ranking.
"""

from pathlib import Path

from _chartlib import (FAMILY_LABEL, core_counts, cores_label, bar, best_per_runtime, heap_note, fmt, kind, svg,
                       zero_ticks)

STEM = Path(__file__).resolve().parent / "throughput-ranking"
W, H = 900, 530
# t leaves room for three header lines *and* a clear gap before the legend, which is
# drawn just above the plot at t-24: at t=92 the third line ended one pixel above it.
M = {"t": 122, "r": 26, "b": 96, "l": 68}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]
BAR_MAX = 88


def build(cores):
    rows = best_per_runtime(lambda r: r[2], cores)  # r = (runtime, xmx, throughput, rss, density)
    yt = zero_ticks(max(r[2] for r in rows) * 1.05)
    ymax = max(yt)
    slot = PW / len(rows)
    bw = min(BAR_MAX, slot - 2)  # 2px surface gap between adjacent bars

    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Peak throughput reached by each runtime</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"Each runtime's best measured configuration · 3 iterations per run · "
        f"{cores_label(cores)} dedicated to the application</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="67" fill="{ink2}" font-size="11.5">'
        f"The rung that maximises throughput is not the one that maximises density: "
        f"raw speed wants a generous heap, efficiency a tight one</text>"
    )

    for t in yt:
        y = M["t"] + PH - t / ymax * PH
        o.append(
            f'<line x1="{M["l"]}" y1="{y:.1f}" x2="{M["l"] + PW}" y2="{y:.1f}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        o.append(
            f'<text x="{M["l"] - 10}" y="{y + 4:.1f}" fill="{ink2}" font-size="11.5" '
            f'text-anchor="end">{fmt(t)}</text>'
        )

    for i, (rt, xmx, tp, rss, dens, _c) in enumerate(rows):
        cx = M["l"] + i * slot + slot / 2
        h = tp / ymax * PH
        y = M["t"] + PH - h
        fam, _ = kind(rt)
        note = heap_note(xmx)
        o.append(
            bar(
                cx - bw / 2,
                y,
                bw,
                h,
                f"var(--{fam})",
                f"{rt} · {note} · {tp:.0f} req/s · {rss:.1f} MiB · {dens:.2f} tps/MiB",
            )
        )
        # A ranking chart's content *is* its numbers, and seven bars stay well under
        # the clutter threshold the "no number on every mark" rule guards against.
        o.append(
            f'<text x="{cx:.1f}" y="{y - 8:.1f}" fill="{ink}" font-size="12.5" '
            f'font-weight="600" text-anchor="middle">{fmt(tp)}</text>'
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
            f'text-anchor="middle">{rss:.0f} MiB · {dens:.1f} tps/MiB</text>'
        )

    o.append(
        f'<text transform="translate(18,{M["t"] + PH / 2:.0f}) rotate(-90)" fill="{ink2}" '
        f'font-size="12" text-anchor="middle">Throughput (req/s)</text>'
    )

    for i, fam in enumerate(FAMILY_LABEL):
        x = M["l"] + 4 + i * 150
        o.append(f'<rect x="{x}" y="{M["t"] - 24}" width="10" height="10" rx="2" fill="var(--{fam})"/>')
        o.append(f'<text x="{x + 16}" y="{M["t"] - 15}" fill="{ink2}" font-size="11.5">{FAMILY_LABEL[fam]}</text>')

    return svg(W, H, "".join(o))


for _cores in core_counts():
    out = Path(f"{STEM}-{_cores}c.svg")
    out.write_text(build(_cores))
    print(f"wrote: {out}")
