# Résultats de benchmark — `spring-quarkus-perf-comparison`

Archive des `metrics.json` produits par `scripts/perf-lab/run-benchmarks.sh`.

Le pipeline écrit toujours au même endroit (`/tmp/metrics.json` par défaut, via `--output-dir`) et
**écrase le fichier à chaque run**. Les résultats ne survivent donc que jusqu'au run suivant, d'où
cette archive.

## Le programme de benchmark

Le projet compare des piles techniques sur **une même application** : le domaine `Fruit` / `Store` /
`Address`, une base PostgreSQL identique et alimentée par le même jeu de données, et un contrat REST
unique — `openapi.yml` à la racine du dépôt, auquel chaque module doit se conformer. La charge est
générée par Hyperfoil sur l'endpoint `GET /fruits`, à connexions fixes.

Les piles mesurées : **Quarkus 3** (dont une variante threads virtuels et une variante de
compatibilité Spring), **Spring Boot 3 et 4**, **NestJS**, **Axum** (Rust) et **net/http** (Go).
Chacune se décline en plusieurs runtimes — JVM, natif GraalVM, AOT, Leyden, threads virtuels selon
les cas — soit une trentaine d'entrées dans `scripts/perf-lab/main.yml`.

**Tous les cas sont fonctionnellement équivalents.** Ils exposent les mêmes routes, les mêmes codes
de statut et les mêmes charges utiles ; les écarts de comportement rencontrés en cours de route —
validation d'un nom vide, forme du 404, statut d'un POST — ont été alignés explicitement, et les
tests d'intégration de chaque module le vérifient.

Les trois modules non-JVM proposent en outre une **déclinaison « SQL pur »** en plus de leur chemin
ORM, sélectionnée par la variable `QUERY_MODE` : `go-sql`, `rust-sql` et `nodejs-sql` exécutent une
requête écrite à la main plutôt que de passer par GORM, SeaORM ou TypeORM. **Cette déclinaison
n'existe pas pour les workloads Java** : Quarkus et Spring Boot sont mesurés uniquement via
Hibernate. Une comparaison ORM contre SQL brut n'est donc possible que sur Go, Rust et Node.

## Équivalence fonctionnelle, divergences d'implémentation

L'équivalence porte sur le comportement observable, pas sur la façon d'y parvenir. Trois écarts
pèsent sur les chiffres et doivent être présents à l'esprit avant toute comparaison.

### Accès aux données

Pour un même `GET /fruits`, le nombre d'allers-retours vers PostgreSQL varie du simple au triple.

| Pile | Requêtes SQL | Stratégie | Cache L2 |
|---|---|---|---|
| TypeORM (`nodejs-orm`) | **1** | `find({ relations })` — une jointure couvrant les trois tables, dédoublonnage en mémoire | non |
| SeaORM (`rust-orm`) | **2** | `fruit::find()`, puis `find_also_related(store)` qui joint prix et magasins | non |
| Hibernate (Quarkus, Spring) | **3 à froid, 2 à chaud** | collection paresseuse chargée en batch (`where fruit_id = any (?)`), puis les magasins | **oui** — `Store` est `@Cacheable` |
| GORM (`go-orm`) | **3** | `Preload("StorePrices.Store")` — une requête par niveau de relation | non |

Hibernate est le seul à disposer d'un cache de second niveau : après le warmup, les magasins sont
servis depuis Caffeine et la troisième requête disparaît. C'est un avantage réel et légitime sous
charge, mais il n'a pas d'équivalent dans les trois autres ORM.

Les comptes TypeORM, Hibernate et GORM sont **mesurés** — relevés dans Tempo sur des traces réelles.
Celui de SeaORM est **lu dans le code** : le module Rust n'a pas d'instrumentation SQL, ses requêtes
n'apparaissent donc dans aucune trace.

### Télémétrie

Tous les modules exportent en OTLP vers le collecteur du conteneur Grafana LGTM, mais ni les mêmes
signaux ni la même profondeur. Relevés le 10/08/2026 en interrogeant Tempo, Prometheus et Loki.

| Pile | Traces | Spans / requête | Métriques | Logs |
|---|---|---|---|---|
| `springboot4` | ✅ | 5 | ✅ 135 séries | ✅ |
| `quarkus3-virtual` | ✅ | 4 (5 à froid) | ✅ 132 séries | ✅ |
| `nodejs` | ✅ | **10** | ✅ 109 séries | ✅ |
| `go` | ✅ | 5 | ✅ 71 séries | ✅ |
| `rust` | ✅ | **1** | ❌ **aucune** | ✅ |

L'écart de profondeur est important : Node instrumente automatiquement chaque middleware Express en
plus de NestJS et du driver `pg`, quand Rust ne produit qu'un span applicatif — ni middleware HTTP,
ni requête SQL. **Le coût de l'observabilité n'est donc pas comparable d'une pile à l'autre**, et il
avantage Rust dans les mesures de débit.

Rust reste sans métriques parce que les crates d'instrumentation nécessaires
(`opentelemetry-instrumentation-tokio`, `axum-tracing-opentelemetry`, `sqlx-otel`) n'ont aucune
version compatible avec l'`opentelemetry` 0.27 auquel le module est épinglé.

### Niveau des ORM face à Hibernate

Hibernate sert de référence : c'est le plus riche fonctionnellement, et les trois autres se
positionnent en retrait sur des axes différents.

| Capacité | Hibernate | TypeORM | SeaORM | GORM |
|---|---|---|---|---|
| Chargement des relations | batch fetch paramétrable | jointure unique | jointure sur les to-one | une requête par niveau |
| Cache de second niveau | ✅ Caffeine, par entité | ❌ | ❌ | ❌ |
| Contexte de persistance, dirty checking | ✅ | partiel | ❌ | ❌ |
| Clé composite embarquée | ✅ `@EmbeddedId` + `@MapsId` | contournée | contournée | contournée |
| Génération d'identifiants | ✅ `@SequenceGenerator` | partiel | manuel | manuel — `nextval()` explicite |
| Pagination sur collection jointe | protégée, avertie | non gardée | n/a | n/a |

Aucun des trois ne propose d'équivalent au `@EmbeddedId` : la clé composite de `StoreFruitPrice` est
partout exprimée en deux colonnes marquées comme clés primaires. Aucun n'a de générateur de séquence
intégré, d'où l'appel manuel à `nextval()` côté Go et Rust. Et surtout aucun n'a de cache de second
niveau, ce qui explique à lui seul l'écart de requêtes SQL observé sous charge.

Ces différences ne sont pas des défauts : chaque ORM applique le défaut idiomatique de son
écosystème. Elles signifient simplement que le benchmark compare **des applications au comportement
identique mais au travail interne différent**.

### Temps de chauffe

Les runtimes à compilation à la volée — la JVM pour Quarkus et Spring, V8 pour Node —
ne servent pas leurs premières requêtes à la vitesse qu'ils atteindront ensuite. Le
code démarre interprété, puis est compilé par paliers ; côté HotSpot, seul le passage
au compilateur C2 donne le régime définitif. Les images natives GraalVM, Go et Rust
n'ont pas cette phase : leur code est déjà compilé au lancement.

Le pipeline le prend en compte — 2 minutes de warmup, 30 secondes de pause, puis 30
secondes de mesure — mais ça atténue le phénomène sans garantir que C2 ait terminé.
Deux traces le montrent dans les mesures de cette archive.

**Les latences de queue du warmup sont d'un autre ordre.** Sur un run
`quarkus3-virtual`, la phase de chauffe monte à 2,11 s au maximum et 1,82 s au
p99.99, contre 68 ms et 59 ms sur la phase mesurée juste après. Un facteur 30.

**La dispersion entre itérations sépare nettement les deux familles.** À réglages
identiques, `quarkus3-native` varie de 0,8 % d'une itération à l'autre là où
`quarkus3-virtual` varie de 9,3 %. Sur les runtimes JIT, un écart inférieur à ~10 %
entre deux configurations n'est donc pas nécessairement significatif — plusieurs
comparaisons de cette archive tombent sous ce seuil.

La [PR #681](https://github.com/quarkusio/spring-quarkus-perf-comparison/pull/681)
propose une amélioration du protocole sur ce point : s'assurer que la phase C2 est
bien terminée avant de commencer à mesurer, plutôt que de le supposer d'après une
durée de warmup fixe.

## Archiver un run

```sh
./archive.py                    # lit /tmp/metrics.json
./archive.py /chemin/metrics.json
```

Le script nomme le fichier d'après le run lui-même — horodatage de démarrage, runtimes mesurés,
configuration mémoire et nombre d'itérations — puis remplit les deux tableaux ci-dessous. Il refuse
les runs avortés (section `results` vide) et ne duplique pas un run déjà archivé.

## Graphiques

Régénérés depuis les JSON archivés, à relancer après chaque `archive.py` :

```sh
./density-ranking.py       # points : densité maximale de chaque runtime
./startup-cost.py          # nuage : TTFR × RSS après la 1ʳᵉ requête
./throughput-ranking.py    # barres : débit maximal de chaque runtime
```

Chaque script produit **un jeu par nombre de cœurs** trouvé dans l'archive, suffixé
`-2c` ou `-1c`. Des runs à nombres de cœurs différents ne sont pas comparables, donc
ils ne partagent pas un graphique.

Les trois partagent `_chartlib.py` — chargement, échelles, marques, palette. La
couleur porte la famille (Quarkus, Spring, non-JVM) et la forme le mode d'exécution :
sept runtimes dépassent les trois créneaux catégoriels que la validation « toutes
paires » autorise, d'où cet encodage composite. Seul le chemin **ORM** est représenté ;
les variantes `-sql` répondent à une autre question et restent dans le tableau.

### 2 cœurs

![Densité de débit, 2 cœurs](density-ranking-2c.svg)

Un tracé par points sur axe logarithmique, pas des barres : la densité s'étale sur un
facteur 62, et la longueur d'une barre *étant* la magnitude, un axe log en fausserait
tous les rapports. Un point encode par position, ce que le log représente honnêtement.

![Coût de démarrage, 2 cœurs](startup-cost-2c.svg)

Les deux coûts payés avant d'avoir servi quoi que ce soit, croisés sur un nuage plutôt
que juxtaposés en deux séries — des unités différentes sur un même graphique
imposeraient un double axe.

![Débit maximal, 2 cœurs](throughput-ranking-2c.svg)

Chaque runtime n'apparaît qu'une fois, à son meilleur palier — et **ce n'est pas le
même palier selon la mesure** : le débit brut culmine à `-Xmx` 512 ou 384 Mo, la
densité à 128 Mo. Le classement s'en trouve partiellement inversé, Rust étant premier
en densité et cinquième en débit.

### 1 cœur

Un seul run, du 11/08/2026 : les dix runtimes à `-Xmx128m`, Node à
`--max-old-space-size=512`. Chaque runtime n'a donc qu'une configuration ici, là où le
jeu à 2 cœurs résume un balayage mémoire.

![Densité de débit, 1 cœur](density-ranking-1c.svg)

![Coût de démarrage, 1 cœur](startup-cost-1c.svg)

![Débit maximal, 1 cœur](throughput-ranking-1c.svg)

Les quatre runtimes Java conservent **56,5 % ± 0,3** de leur débit à 2 cœurs, sauf
`spring4-native` à 51,2 %. Une montée en charge légèrement super-linéaire : le second
cœur n'était pas exploité à 100 %, ce qui est cohérent avec une charge partagée entre
traitement applicatif et attente de PostgreSQL.

## Runs

| Fichier | Début (UTC) | Runtimes | Itér. | Config JVM | Scénario |
|---|---|---|---|---|---|
| [`20260810_1522__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx512m-ParallelGC_3it.json`](20260810_1522__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx512m-ParallelGC_3it.json) | 2026-08-10T15:22:16Z | quarkus3-native, quarkus3-virtual, spring4-native, spring4-virtual | 3 | `-Xmx512m` `-XX:+UseParallelGC` | tuned |
| [`20260810_1723__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx384m-ParallelGC_3it.json`](20260810_1723__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx384m-ParallelGC_3it.json) | 2026-08-10T17:23:25Z | quarkus3-native, quarkus3-virtual, spring4-native, spring4-virtual | 3 | `-Xmx384m` `-XX:+UseParallelGC` | tuned |
| [`20260810_1925__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx256m-ParallelGC_3it.json`](20260810_1925__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx256m-ParallelGC_3it.json) | 2026-08-10T19:25:33Z | quarkus3-native, quarkus3-virtual, spring4-native, spring4-virtual | 3 | `-Xmx256m` `-XX:+UseParallelGC` | tuned |
| [`20260811_0338__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx128m-ParallelGC_3it.json`](20260811_0338__quarkus3-native+quarkus3-virtual+spring4-native+spring4-virtual__Xmx128m-ParallelGC_3it.json) | 2026-08-11T03:38:27Z | quarkus3-native, quarkus3-virtual, spring4-native, spring4-virtual | 3 | `-Xmx128m` `-XX:+UseParallelGC` | tuned |
| [`20260811_0548__quarkus3-native__Xmx64m-ParallelGC_3it.json`](20260811_0548__quarkus3-native__Xmx64m-ParallelGC_3it.json) | 2026-08-11T05:48:17Z | quarkus3-native | 3 | `-Xmx64m` `-XX:+UseParallelGC` | tuned |
| [`20260811_0655__go-orm+nodejs-orm+rust-orm__Xms512m-Xmx512m_ParallelGC_3it.json`](20260811_0655__go-orm+nodejs-orm+rust-orm__Xms512m-Xmx512m_ParallelGC_3it.json) | 2026-08-11T06:55:09Z | go-orm, nodejs-orm, rust-orm | 3 | `-Xms512m -Xmx512m` `-XX:+UseParallelGC` | tuned |
| [`20260811_0914__nodejs-orm__node384m_3it.json`](20260811_0914__nodejs-orm__node384m_3it.json) | 2026-08-11T09:14:36Z | nodejs-orm | 3 | `--max-old-space-size=384` | tuned |
| [`20260811_0935__nodejs-orm__node256m_3it.json`](20260811_0935__nodejs-orm__node256m_3it.json) | 2026-08-11T09:35:45Z | nodejs-orm | 3 | `--max-old-space-size=256` | tuned |
| [`20260811_0956__nodejs-orm__node128m_3it.json`](20260811_0956__nodejs-orm__node128m_3it.json) | 2026-08-11T09:56:40Z | nodejs-orm | 3 | `--max-old-space-size=128` | tuned |
| [`20260811_1031__10runtimes__Xmx128m-ParallelGC_node512m_3it.json`](20260811_1031__10runtimes__Xmx128m-ParallelGC_node512m_3it.json) | 2026-08-11T10:31:06Z | go-orm, go-sql, nodejs-orm, nodejs-sql, quarkus3-native, quarkus3-virtual, rust-orm, rust-sql, spring4-native, spring4-virtual | 3 | `-Xmx128m` `-XX:+UseParallelGC` `--max-old-space-size=512` | tuned |
<!-- runs -->

## Résultats

Une ligne par runtime, moyennée sur les itérations du run.

| Run | Runtime | Cœurs | `-Xmx` | Build (s) | TTFR (ms) | RSS 1ʳᵉ req (MiB) | RSS charge (MiB) | Débit (tps) | Densité (tps/MiB) |
|---|---|---|---|---|---|---|---|---|---|
| `20260810_1522` | quarkus3-native | 2 | 512m | 326.5 | 100 | 99.3 | 246.4 | 4 138 | 17.42 |
| `20260810_1522` | quarkus3-virtual | 2 | 512m | 12.5 | 3 216 | 260.7 | 499.3 | 7 032 | 15.03 |
| `20260810_1522` | spring4-native | 2 | 512m | 531.8 | 938 | 273.7 | 390.2 | 1 659 | 4.32 |
| `20260810_1522` | spring4-virtual | 2 | 512m | 5.7 | 9 045 | 445.6 | 571.4 | 5 506 | 9.87 |
| `20260810_1723` | quarkus3-native | 2 | 384m | 314.4 | 109 | 98.9 | 246.0 | 4 078 | 17.97 |
| `20260810_1723` | quarkus3-virtual | 2 | 384m | 12.9 | 3 339 | 258.0 | 423.6 | 6 950 | 17.47 |
| `20260810_1723` | spring4-native | 2 | 384m | 517.1 | 1 011 | 274.4 | 346.2 | 1 665 | 4.91 |
| `20260810_1723` | spring4-virtual | 2 | 384m | 5.5 | 8 818 | 421.8 | 556.6 | 5 547 | 10.36 |
| `20260810_1925` | quarkus3-native | 2 | 256m | 307.8 | 123 | 99.3 | 205.9 | 4 007 | 20.04 |
| `20260810_1925` | quarkus3-virtual | 2 | 256m | 12.6 | 3 318 | 251.2 | 478.4 | 6 653 | 14.20 |
| `20260810_1925` | spring4-native | 2 | 256m | 524.6 | 925 | 265.1 | 284.3 | 1 622 | 5.92 |
| `20260810_1925` | spring4-virtual | 2 | 256m | 5.6 | 8 824 | 373.9 | 546.4 | 5 450 | 10.34 |
| `20260811_0338` | quarkus3-native | 2 | 128m | 309.9 | 132 | 99.4 | 168.5 | 3 390 | 21.52 |
| `20260811_0338` | quarkus3-virtual | 2 | 128m | 13.0 | 3 501 | 245.1 | 356.7 | 6 336 | 18.47 |
| `20260811_0338` | spring4-native | 2 | 128m | 521.3 | 1 027 | 233.3 | 250.2 | 1 501 | 6.10 |
| `20260811_0338` | spring4-virtual | 2 | 128m | 6.1 | 9 278 | 341.2 | 431.7 | 4 955 | 12.05 |
| `20260811_0548` | quarkus3-native | 2 | 64m | 315.7 | 111 | 99.3 | 142.0 | 2 798 | 20.69 |
| `20260811_0655` | go-orm | 2 | - | 43.7 | 51 | 28.7 | 51.4 | 3 128 | 62.57 |
| `20260811_0655` | nodejs-orm | 2 | - | 6.0 | 1 557 | 151.4 | 231.3 | 680 | 3.00 |
| `20260811_0655` | rust-orm | 2 | - | 254.5 | 29 | 8.2 | 13.6 | 2 455 | 186.62 |
| `20260811_0914` | nodejs-orm | 2 | 384m | 5.6 | 1 567 | 151.3 | 231.1 | 677 | 3.05 |
| `20260811_0935` | nodejs-orm | 2 | 256m | 6.3 | 1 747 | 151.4 | 225.8 | 661 | 3.00 |
| `20260811_0956` | nodejs-orm | 2 | 128m | 5.9 | 1 698 | 151.0 | 226.1 | 700 | 3.11 |
| `20260811_1031` | go-orm | 1 | - | 84.6 | 43 | 28.1 | 48.4 | 2 111 | 45.00 |
| `20260811_1031` | go-sql | 1 | - | 84.2 | 37 | 27.8 | 44.5 | 4 605 | 110.55 |
| `20260811_1031` | nodejs-orm | 1 | 512m | 7.3 | 1 761 | 180.0 | 219.9 | 521 | 2.47 |
| `20260811_1031` | nodejs-sql | 1 | 512m | 6.8 | 1 693 | 160.3 | 212.1 | 972 | 4.63 |
| `20260811_1031` | quarkus3-native | 1 | 128m | 588.0 | 101 | 99.0 | 162.6 | 1 922 | 11.89 |
| `20260811_1031` | quarkus3-virtual | 1 | 128m | 22.2 | 6 154 | 239.1 | 347.6 | 3 604 | 10.74 |
| `20260811_1031` | rust-orm | 1 | - | 391.0 | 24 | 8.2 | 13.1 | 2 468 | 191.21 |
| `20260811_1031` | rust-sql | 1 | - | 389.7 | 24 | 8.1 | 13.2 | 4 127 | 321.11 |
| `20260811_1031` | spring4-native | 1 | 128m | 946.6 | 1 047 | 238.6 | 251.0 | 769 | 3.18 |
| `20260811_1031` | spring4-virtual | 1 | 128m | 10.5 | 18 374 | 336.0 | 430.1 | 2 793 | 6.81 |
<!-- results -->

### Origine des colonnes

| Colonne | Clé JSON | Test requis |
|---|---|---|
| Cœurs | `config.resources.app_cpus`, sinon compté depuis `config.resources.cpu.app` (`--cpus-app`) | — |
| `-Xmx` | `config.jvm.memory`, runtimes Quarkus et Spring uniquement | — |
| Build | `build.avBuildTime` | toujours produit |
| TTFR | `startup.avStartTime` | `measure-time-to-first-request` |
| RSS 1ʳᵉ req | `rss.avFirstRequestRss` | `measure-rss` |
| RSS charge | `load.avMaxRss` | `run-load-test` |
| Débit | `load.avThroughput` | `run-load-test` |
| Densité | `load.maxThroughputDensity` | `run-load-test` |

Un tiret signale un test non sélectionné dans `--tests`. Le RSS **au démarrage**
(`rss.avStartupRss`), la taille du binaire natif (`build.native.binarySize`) et les compteurs de
réflexion GraalVM ne figurent pas dans le tableau mais restent dans le JSON archivé.

## Mises en garde connues

- **La branche annoncée est fausse** quand `--repo-url` est un chemin local : le pipeline fait un
  `cp -R` de la copie de travail sans `checkout`, donc `config.repo.branch` ne reflète pas ce qui a
  réellement été mesuré.
- **Le niveau d'instrumentation a changé le 10/08/2026.** Les modules `go`, `nodejs` et `rust` ont
  reçu métriques et logs OTel ce jour-là ; leurs chiffres antérieurs sont plus légers et ne sont pas
  comparables aux suivants. Les modules Quarkus et Spring ne sont pas concernés.
- **La densité hérite du budget mémoire.** C'est un ratio débit/RSS sous charge, donc un `-Xmx`
  généreux la dégrade mécaniquement sans que le runtime soit en cause.

## Pour aller plus loin

Les billets du perf lab Quarkus, qui documentent la méthodologie de ce banc et les
pièges rencontrés en le construisant :

- [Fairness in benchmarking](https://quarkus.io/blog/fairness-in-benchmarking/) — ce
  que « comparer à égalité » veut dire, et pourquoi c'est plus difficile qu'il n'y
  paraît
- [When the JIT can't keep up](https://quarkus.io/blog/when-the-jit-cant-keep-up/) —
  le temps de chauffe et ses effets sur la mesure
- [The hidden cost of rootless container networking](https://quarkus.io/blog/hidden-cost-rootless-container-networking/)
  — comment l'environnement d'exécution fausse les chiffres
- [Reflection-free Jackson serializers](https://quarkus.io/blog/reflection-free-jsckson-serializers/)
  — l'optimisation activée ici par `enable-reflection-free-serializers`
- [New benchmarks](https://quarkus.io/blog/new-benchmarks/) — la présentation du banc
  et de ses résultats
