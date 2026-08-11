#!/usr/bin/env python3
"""Assemble index.html from the three generated SVGs and the archived runs.

The SVGs are inlined rather than referenced with <img>: inlined, they inherit the
page's theme scope, so the toggle reaches them. Each one carries its own copy of the
palette CSS when standalone, so those blocks are stripped here and the roles are
declared once for the whole page.

Regenerate the charts first - this script only wraps whatever they last produced.
"""

import glob
import json
import re
from pathlib import Path

from _chartlib import kind

HERE = Path(__file__).resolve().parent
OUT = HERE / "index.html"

CHARTS = [
    (
        "throughput-ranking.svg",
        "Débit maximal",
        "Meilleur des paliers mémoire mesurés pour chaque runtime. Le palier qui "
        "maximise le débit n’est pas celui qui maximise la densité : la vitesse brute "
        "veut un tas généreux, l’efficacité un tas serré.",
    ),
    (
        "density-ranking.svg",
        "Densité de débit",
        "Requêtes par seconde et par MiB de RSS sous charge. Tracé par points sur axe "
        "logarithmique et non des barres : la mesure s’étale sur un facteur 62, et la "
        "longueur d’une barre <em>étant</em> la magnitude, un axe log en fausserait "
        "tous les rapports.",
    ),
    (
        "startup-cost.svg",
        "Coût de démarrage",
        "Les deux coûts payés avant d’avoir servi quoi que ce soit, croisés sur un "
        "nuage plutôt que juxtaposés — des unités différentes sur un même graphique "
        "imposeraient un double axe. En bas à gauche, le moins coûteux.",
    ),
]

CSS = """
  :root { color-scheme: light; --page:#f4f4f2; --card:#fcfcfb; --edge:#e6e5e1;
          --ink:#0b0b0b; --ink2:#52514e; }
  .viz { --surface-1:#fcfcfb; --text-primary:#0b0b0b; --text-secondary:#52514e;
         --grid:#e6e5e1; --quarkus:#2a78d6; --spring:#eb6834; --other:#1baf7a; }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) { color-scheme: dark; --page:#111110;
      --card:#1a1a19; --edge:#333331; --ink:#ffffff; --ink2:#c3c2b7; }
    :root:where(:not([data-theme="light"])) .viz { --surface-1:#1a1a19;
      --text-primary:#ffffff; --text-secondary:#c3c2b7; --grid:#333331;
      --quarkus:#3987e5; --spring:#d95926; --other:#199e70; }
  }
  :root[data-theme="dark"] { color-scheme: dark; --page:#111110; --card:#1a1a19;
    --edge:#333331; --ink:#ffffff; --ink2:#c3c2b7; }
  :root[data-theme="dark"] .viz { --surface-1:#1a1a19; --text-primary:#ffffff;
    --text-secondary:#c3c2b7; --grid:#333331; --quarkus:#3987e5; --spring:#d95926;
    --other:#199e70; }

  * { box-sizing: border-box; }
  body { margin:0; padding:32px 24px 64px; background:var(--page); color:var(--ink);
         font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
  main { max-width:960px; margin:0 auto; }
  h1 { font-size:24px; margin:0 0 6px; letter-spacing:-0.01em; }
  h2 { font-size:17px; margin:0 0 4px; }
  p  { color:var(--ink2); margin:0 0 18px; max-width:78ch; }
  p.lede { font-size:15px; }
  figure { margin:0 0 34px; padding:18px 18px 10px; background:var(--card);
           border:1px solid var(--edge); border-radius:10px; }
  figure svg { width:100%; height:auto; display:block; }
  figcaption { color:var(--ink2); font-size:13.5px; margin:2px 0 8px; max-width:82ch; }
  header { display:flex; align-items:baseline; justify-content:space-between; gap:16px;
           margin-bottom:26px; flex-wrap:wrap; }
  button { font:inherit; font-size:13px; color:var(--ink2); background:var(--card);
           border:1px solid var(--edge); border-radius:7px; padding:5px 11px;
           cursor:pointer; }
  button:hover { color:var(--ink); }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  caption { text-align:left; color:var(--ink2); font-size:13.5px; padding-bottom:10px; }
  th,td { padding:6px 9px; border-bottom:1px solid var(--edge); text-align:right;
          font-variant-numeric:tabular-nums; }
  th:first-child,td:first-child,th:nth-child(2),td:nth-child(2) { text-align:left;
          font-variant-numeric:normal; }
  thead th { color:var(--ink2); font-weight:600; border-bottom:1px solid var(--ink2); }
  tbody tr:hover { background:var(--edge); }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%;
         margin-right:7px; vertical-align:baseline; }
  .sq { border-radius:2px; }
  footer { color:var(--ink2); font-size:12.5px; margin-top:38px; }
"""

TOGGLE = """
  const root = document.documentElement, btn = document.getElementById('theme');
  const label = { auto:'Thème : auto', light:'Thème : clair', dark:'Thème : sombre' };
  let mode = localStorage.getItem('theme') || 'auto';
  const apply = () => {
    if (mode === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', mode);
    btn.textContent = label[mode];
    localStorage.setItem('theme', mode);
  };
  btn.onclick = () => { mode = { auto:'light', light:'dark', dark:'auto' }[mode]; apply(); };
  apply();
"""


def inline(name):
    """Drop the standalone palette block and the fixed size; the page supplies both."""
    svg = (HERE / name).read_text()
    svg = re.sub(r"<style>.*?</style>", "", svg, flags=re.S)
    return re.sub(r'\swidth="\d+"\sheight="\d+"', "", svg, count=1)


def rows():
    out = []
    for f in sorted(glob.glob(str(HERE / "*.json"))):
        m = re.search(r"Xmx(\d+)m", f)
        stamp = Path(f).name.split("__")[0]
        data = json.load(open(f))
        cores = ((data.get("config") or {}).get("resources") or {}).get("app_cpus", "-")
        for rt, v in sorted(data["results"].items()):
            b, s = v.get("build") or {}, v.get("startup") or {}
            r, l = v.get("rss") or {}, v.get("load") or {}
            if not l.get("avThroughput"):
                continue
            out.append(
                {
                    "run": stamp,
                    "rt": rt,
                    "cores": cores,
                    "xmx": f"{m.group(1)}m" if (m and kind(rt)[0] != "other") else "—",
                    "build": b.get("avBuildTime"),
                    "ttfr": s.get("avStartTime"),
                    "rss1": r.get("avFirstRequestRss"),
                    "rssl": l.get("avMaxRss"),
                    "tp": l.get("avThroughput"),
                    "dens": l.get("maxThroughputDensity"),
                }
            )
    return sorted(out, key=lambda x: -(x["dens"] or 0))


def cell(v, digits=1):
    if v is None:
        return "—"
    return f"{v:,.{digits}f}".replace(",", " ") if digits else f"{v:,.0f}".replace(",", " ")


def build():
    figs = []
    for name, title, caption in CHARTS:
        figs.append(
            f"<figure><h2>{title}</h2><figcaption>{caption}</figcaption>"
            f"{inline(name)}</figure>"
        )

    body = []
    for r in rows():
        fam, shape = kind(r["rt"])
        cls = "dot sq" if shape == "square" else "dot"
        body.append(
            f'<tr><td>{r["run"]}</td>'
            f'<td><span class="{cls}" style="background:var(--{fam})"></span>{r["rt"]}</td>'
            f'<td>{r["cores"]}</td><td>{r["xmx"]}</td>'
            f'<td>{cell(r["build"])}</td><td>{cell(r["ttfr"], 0)}</td>'
            f'<td>{cell(r["rss1"])}</td><td>{cell(r["rssl"])}</td>'
            f'<td>{cell(r["tp"], 0)}</td><td>{cell(r["dens"], 2)}</td></tr>'
        )

    table = (
        '<table><caption>Tous les runs archivés, classés par densité décroissante. '
        "Les colonnes vides correspondent à un test non sélectionné dans "
        "<code>--tests</code>.</caption><thead><tr>"
        "<th>Run</th><th>Runtime</th><th>Cœurs</th><th>-Xmx</th><th>Build (s)</th>"
        "<th>TTFR (ms)</th><th>RSS 1ʳᵉ req</th><th>RSS charge</th><th>Débit</th>"
        "<th>Densité</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"
    )

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Résultats — spring-quarkus-perf-comparison</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Résultats de benchmark</h1>
      <p class="lede">Quarkus, Spring Boot, Go, Rust et Node.js sur la même application —
      même domaine, même base PostgreSQL, même contrat REST.</p>
    </div>
    <button id="theme" type="button">Thème : auto</button>
  </header>

  <p>La couleur porte la famille et la forme le mode d’exécution : sept runtimes
  dépassent les trois teintes catégorielles qu’une validation « toutes paires »
  autorise, d’où cet encodage composite. Survolez un point ou une barre pour le
  détail du run.</p>

  {"".join(figs)}

  <h2>Toutes les mesures</h2>
  {table}

  <footer>
    Mesuré sur WSL2, Xeon Gold 6544Y, 2 cœurs dédiés à l’application, PostgreSQL et
    la stack OpenTelemetry isolés sur d’autres cœurs. Les runtimes n’exportent pas
    les mêmes signaux OpenTelemetry : voir <code>README.md</code> pour le détail des
    divergences d’implémentation, qui pèsent sur ces chiffres.
  </footer>
</main>
<script>{TOGGLE}</script>
</body>
</html>
"""


OUT.write_text(build())
print(f"écrit: {OUT}")
