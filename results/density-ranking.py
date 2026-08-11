#!/usr/bin/env python3
"""Render density-ranking.svg from the archived metrics.json files.

One bar per *runtime*, ranked by throughput density (req/s per MiB of RSS under
load). When a runtime was measured at several heap ceilings, only its best rung is
kept - the chart answers "how efficient can each runtime get", not "what does every
configuration score". throughput-vs-rss.svg keeps the full sweep.

Bars are anchored at zero: unlike a scatter, bar length *is* the magnitude, so a
truncated axis would misstate the ratios.

Colour carries the framework only. Sorting by value interleaves the runtimes, so
neighbouring bars can be any pair and the palette has to clear the all-pairs floors;
only three categorical slots do, and four runtimes would need four. The execution
mode and the winning heap ceiling ride in the tick label instead.
"""

import glob
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "density-ranking.svg"

W, H = 760, 470
M = {"t": 84, "r": 26, "b": 82, "l": 62}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]
BAR_MAX = 104

FAMILY = {"quarkus": "Quarkus 3", "spring": "Spring Boot 4"}


def family(runtime):
    return "quarkus" if runtime.startswith("quarkus") else "spring"


def load():
    """Best rung per runtime, ranked. Ties keep the roomier heap - the safer default."""
    best = {}
    for f in sorted(glob.glob(str(HERE / "*.json"))):
        xmx = int(re.search(r"Xmx(\d+)m", f).group(1))
        for rt, v in json.load(open(f))["results"].items():
            load_ = v.get("load") or {}
            d = load_.get("maxThroughputDensity")
            if d is None and load_.get("avThroughput") and load_.get("avMaxRss"):
                d = load_["avThroughput"] / load_["avMaxRss"]
            if not d:
                continue
            row = (rt, xmx, d, load_.get("avThroughput"), load_.get("avMaxRss"))
            if rt not in best or (d, xmx) > (best[rt][2], best[rt][1]):
                best[rt] = row
    return sorted(best.values(), key=lambda r: -r[2])


def ticks(hi, target=5):
    raw = hi / target
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    out, v = [], 0.0
    while v < hi:
        out.append(v)
        v += step
    out.append(v)  # always overshoot hi, so the tallest bar stays inside the plot
    return out


def bar(x, y, w, h, fill, tip):
    """Rounded data-end, square at the baseline - the corner marks where the value is."""
    r = min(4.0, w / 2, h)
    d = (
        f"M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"L{x + w - r:.1f},{y:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"L{x + w:.1f},{y + h:.1f} Z"
    )
    return f'<path d="{d}" fill="{fill}"><title>{tip}</title></path>'


def build():
    rows = load()
    yt = ticks(max(r[2] for r in rows) * 1.06)
    ymax = max(yt)
    slot = PW / len(rows)
    bw = min(BAR_MAX, slot - 2)  # 2px surface gap even when the cap does not bite

    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Densité de débit, meilleure configuration de chaque runtime</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"Requêtes par seconde et par MiB de RSS sous charge · 3 itérations, 2 cœurs · "
        f"le palier <tspan font-weight="'"600"'">-Xmx</tspan> retenu est celui de densité maximale</text>"
    )

    for t in yt:
        y = M["t"] + PH - t / ymax * PH
        o.append(
            f'<line x1="{M["l"]}" y1="{y:.1f}" x2="{M["l"] + PW}" y2="{y:.1f}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        o.append(
            f'<text x="{M["l"] - 10}" y="{y + 4:.1f}" fill="{ink2}" font-size="11.5" '
            f'text-anchor="end">{t:.0f}</text>'
        )

    for i, (rt, xmx, dens, tp, rss) in enumerate(rows):
        cx = M["l"] + i * slot + slot / 2
        h = dens / ymax * PH
        y = M["t"] + PH - h
        tip = f"{rt} · -Xmx{xmx}m · {dens:.2f} tps/MiB · {tp:.0f} req/s · {rss:.1f} MiB"
        o.append(bar(cx - bw / 2, y, bw, h, f"var(--{family(rt)})", tip))

        # Four bars sit well under the clutter threshold the "no number on every mark"
        # rule guards against, and the ranking is the whole point - label them all.
        o.append(
            f'<text x="{cx:.1f}" y="{y - 8:.1f}" fill="{ink}" font-size="13" '
            f'font-weight="600" text-anchor="middle">{dens:.2f}</text>'
        )
        o.append(
            f'<text x="{cx:.1f}" y="{M["t"] + PH + 20:.0f}" fill="{ink}" font-size="12" '
            f'text-anchor="middle">{rt}</text>'
        )
        o.append(
            f'<text x="{cx:.1f}" y="{M["t"] + PH + 37:.0f}" fill="{ink2}" font-size="11" '
            f'text-anchor="middle">-Xmx {xmx}m · {tp:.0f} req/s · {rss:.0f} MiB</text>'
        )

    o.append(
        f'<text transform="translate(18,{M["t"] + PH / 2:.0f}) rotate(-90)" fill="{ink2}" '
        f'font-size="12" text-anchor="middle">Densité (req/s par MiB)</text>'
    )

    for i, fam in enumerate(FAMILY):
        x = M["l"] + 4 + i * 132
        o.append(f'<rect x="{x}" y="{M["t"] - 24}" width="10" height="10" rx="2" fill="var(--{fam})"/>')
        o.append(f'<text x="{x + 16}" y="{M["t"] - 15}" fill="{ink2}" font-size="11.5">{FAMILY[fam]}</text>')

    css = """
  .viz { color-scheme: light; --surface-1:#fcfcfb; --text-primary:#0b0b0b;
         --text-secondary:#52514e; --grid:#e6e5e1; --quarkus:#2a78d6; --spring:#eb6834; }
  @media (prefers-color-scheme: dark) {
    .viz { color-scheme: dark; --surface-1:#1a1a19; --text-primary:#ffffff;
           --text-secondary:#c3c2b7; --grid:#333331; --quarkus:#3987e5; --spring:#d95926; }
  }"""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" class="viz" font-family="system-ui,-apple-system,Segoe UI,sans-serif">'
        f"<style>{css}</style>" + "".join(o) + "</svg>"
    )


OUT.write_text(build())
print(f"écrit: {OUT}")
