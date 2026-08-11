#!/usr/bin/env python3
"""Render throughput-vs-rss.svg from the archived metrics.json files.

A connected scatter: one point per run, joined per runtime in -Xmx order, so each
line is that runtime's trajectory as the heap ceiling tightens. Colour carries the
framework and shape carries the execution mode - a scatter validates colour on all
pairs, not just adjacent ones, and only three categorical slots clear that bar, so
four series cannot each take a hue.

Axes are padded to the data rather than anchored at zero: a scatter of two
continuous measures needs no zero baseline, and anchoring squeezed every point into
the top-right corner.
"""

import glob
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "throughput-vs-rss.svg"

W, H = 860, 560
M = {"t": 74, "r": 150, "b": 66, "l": 74}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]

# Slots 1 and 2 of the reference categorical palette, validated --pairs all in both
# modes (worst CVD dE 24.7 light / 26.8 dark).
FAMILY = {"quarkus": "Quarkus 3", "spring": "Spring Boot 4"}
SERIES = {
    "quarkus3-virtual": ("quarkus", "circle"),
    "quarkus3-native": ("quarkus", "square"),
    "spring4-virtual": ("spring", "circle"),
    "spring4-native": ("spring", "square"),
}


def load():
    runs = {}
    for f in sorted(glob.glob(str(HERE / "*.json"))):
        xmx = int(re.search(r"Xmx(\d+)m", f).group(1))
        for rt, v in json.load(open(f))["results"].items():
            load_ = v.get("load") or {}
            if load_.get("avThroughput") and load_.get("avMaxRss"):
                runs.setdefault(rt, []).append(
                    (xmx, load_["avThroughput"], load_["avMaxRss"])
                )
    return {rt: sorted(v, reverse=True) for rt, v in runs.items()}


def scale(values, target_ticks, pad=0.08):
    """Domain padded around the data, plus round ticks strictly inside it."""
    lo, hi = min(values), max(values)
    span = hi - lo
    lo, hi = lo - span * pad, hi + span * pad
    raw = (hi - lo) / target_ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    first = math.ceil(lo / step) * step
    ticks = []
    while first <= hi:
        ticks.append(first)
        first += step
    return lo, hi, ticks


def marker(shape, x, y, fill, ring, tip=None):
    """8px marks with a 2px surface ring, so overlapping points stay separable.

    A <title> must be a *child* of the shape to surface as a tooltip; as a sibling it
    renders nothing.
    """
    inner = f"<title>{tip}</title>" if tip else ""
    if shape == "circle":
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{fill}" '
            f'stroke="{ring}" stroke-width="2">{inner}</circle>'
        )
    s = 5.4
    return (
        f'<rect x="{x - s:.1f}" y="{y - s:.1f}" width="{2 * s:.1f}" height="{2 * s:.1f}" '
        f'rx="1.5" fill="{fill}" stroke="{ring}" stroke-width="2">{inner}</rect>'
    )


def build():
    runs = load()
    xlo, xhi, xt = scale([p[1] for v in runs.values() for p in v], 8)
    ylo, yhi, yt = scale([p[2] for v in runs.values() for p in v], 5)

    def px(v):
        return M["l"] + (v - xlo) / (xhi - xlo) * PW

    def py(v):
        return M["t"] + PH - (v - ylo) / (yhi - ylo) * PH

    ink, ink2 = "var(--text-primary)", "var(--text-secondary)"
    grid, surface = "var(--grid)", "var(--surface-1)"
    o = [f'<rect width="{W}" height="{H}" fill="{surface}"/>']

    o.append(
        f'<text x="{M["l"]}" y="30" fill="{ink}" font-size="17" font-weight="600">'
        f"Débit et empreinte mémoire selon le plafond de tas</text>"
    )
    o.append(
        f'<text x="{M["l"]}" y="50" fill="{ink2}" font-size="12.5">'
        f"Un point par run de 3 itérations ; chaque ligne suit un runtime de "
        f"-Xmx 512 Mo (en haut à droite) vers 64 Mo</text>"
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
        label = f"{t:,.0f}".replace(",", " ")
        o.append(
            f'<text x="{x:.1f}" y="{M["t"] + PH + 22}" fill="{ink2}" font-size="11.5" '
            f'text-anchor="middle">{label}</text>'
        )

    o.append(
        f'<text x="{M["l"] + PW / 2:.0f}" y="{H - 14}" fill="{ink2}" font-size="12" '
        f'text-anchor="middle">Débit (req/s)</text>'
    )
    o.append(
        f'<text transform="translate(20,{M["t"] + PH / 2:.0f}) rotate(-90)" fill="{ink2}" '
        f'font-size="12" text-anchor="middle">RSS sous charge (MiB)</text>'
    )

    for rt, pts in sorted(runs.items()):
        fam, shape = SERIES[rt]
        col = f"var(--{fam})"
        o.append(
            f'<polyline points="{" ".join(f"{px(t):.1f},{py(r):.1f}" for _, t, r in pts)}" '
            f'fill="none" stroke="{col}" stroke-width="2" stroke-opacity="0.45" '
            f'stroke-linecap="round"/>'
        )
        for xmx, t, r in pts:
            o.append(
                marker(
                    shape,
                    px(t),
                    py(r),
                    col,
                    surface,
                    f"{rt} · -Xmx{xmx}m · {t:.0f} req/s · {r:.1f} MiB",
                )
            )

        # Direct-label at the tightest rung, the sparse end of every trajectory. The
        # 512m end is where the points bunch, so a label there lands on a neighbour.
        _, t, r = pts[-1]
        o.append(
            f'<text x="{px(t):.1f}" y="{py(r) + 21:.1f}" fill="{ink2}" font-size="10.5" '
            f'text-anchor="middle">{rt}</text>'
        )

    lx, ly = M["l"] + PW + 26, M["t"] + 6
    o.append(f'<text x="{lx}" y="{ly}" fill="{ink}" font-size="11.5" font-weight="600">Framework</text>')
    for i, fam in enumerate(FAMILY):
        y = ly + 22 + i * 21
        o.append(marker("circle", lx + 7, y - 4, f"var(--{fam})", surface))
        o.append(f'<text x="{lx + 20}" y="{y}" fill="{ink2}" font-size="11.5">{FAMILY[fam]}</text>')
    o.append(f'<text x="{lx}" y="{ly + 82}" fill="{ink}" font-size="11.5" font-weight="600">Exécution</text>')
    for i, (shape, label) in enumerate((("circle", "JVM"), ("square", "Image native"))):
        y = ly + 104 + i * 21
        o.append(marker(shape, lx + 7, y - 4, ink2, surface))
        o.append(f'<text x="{lx + 20}" y="{y}" fill="{ink2}" font-size="11.5">{label}</text>')

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
