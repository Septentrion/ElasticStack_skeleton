# Mémento — Fonctions utiles pour le TP J4 après-midi
# Dashboard Kibana et monitoring du pipeline

> Classement par bibliothèque / module, avec une courte explication et un exemple d'usage tiré du code du TP.
> Ce mémento est autonome : toutes les fonctions utilisées dans le TP sont documentées.

---

## 1. `elasticsearch.Elasticsearch` — Client Python

### `Elasticsearch(host)`

Crée une connexion au cluster Elasticsearch.

```python
from elasticsearch import Elasticsearch
es = Elasticsearch("http://localhost:9200")
```

### `es.info()`

Retourne les informations du cluster. Vérifie la connexion.

```python
es.info()   # Lève une exception si ES est injoignable
```

### `es.count(index, query)`

Compte les documents dans un index. Avec `query`, ne compte que les documents qui matchent.

```python
# Total
total = es.count(index="arxiv-papers")["count"]

# Avec filtre (documents ayant un champ spécifique)
kw_count = es.count(
    index="arxiv-papers",
    query={"exists": {"field": "keywords"}},
)["count"]
```

### `es.search(index, size, sort, aggs, _source)`

Exécute une requête de recherche. Utilisé dans le TP pour récupérer le dernier item HN (fraîcheur), les top catégories, et les dernières métriques.

```python
# Dernier item HN (tri desc par timestamp)
latest = es.search(
    index="hn-items",
    size=1,
    sort=[{"time": "desc"}],
    _source=["time"],
)
if latest["hits"]["hits"]:
    latest_ts = latest["hits"]["hits"][0]["_source"]["time"]

# Top catégorie avec agrégations
result = es.search(
    index="arxiv-papers",
    size=0,       # Pas de documents, juste les agrégations
    aggs={
        "categories": {"cardinality": {"field": "primary_category"}},
        "top_cat": {"terms": {"field": "primary_category", "size": 1}},
    },
)
distinct = result["aggregations"]["categories"]["value"]
top = result["aggregations"]["top_cat"]["buckets"][0]
```

### `es.indices.exists(index)`

Vérifie si un index existe. Retourne `True` ou `False`.

```python
if not es.indices.exists(index="pipeline-logs"):
    print("Index non trouvé — exécutez le script de collecte")
```

### `es.indices.create(index, body)`

Crée un index avec un mapping explicite. Utilisé pour créer l'index `pipeline-logs` avec les types adaptés aux métriques.

```python
es.indices.create(index="pipeline-logs", body={
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "@timestamp":           {"type": "date"},
            "type":                 {"type": "keyword"},
            "volume_arxiv_papers":  {"type": "integer"},
            "es_status":            {"type": "keyword"},
            "enrichment_rate_keywords": {"type": "float"},
            "index_size_arxiv_mb":  {"type": "float"},
        }
    },
})
```

### `es.index(index, document)`

Indexe un document unique. Sans paramètre `id`, Elasticsearch génère un identifiant aléatoire. Utilisé pour indexer chaque entrée de métriques.

```python
es.index(index="pipeline-logs", document={
    "@timestamp": "2024-06-15T14:30:00+00:00",
    "type": "pipeline_metrics",
    "volume_arxiv_papers": 100000,
    "es_status": "green",
    "enrichment_rate_keywords": 47.8,
})
```

**Différence avec l'indexation dans les TPs précédents** : ici on n'utilise pas `_id` car chaque mesure est un événement unique (pas d'idempotence nécessaire — on veut un historique, pas un remplacement).

### `es.indices.refresh(index)`

Force ES à rendre les documents récemment indexés cherchables immédiatement.

```python
es.indices.refresh(index="pipeline-logs")
```

### `es.indices.stats(index)`

Retourne des statistiques détaillées sur un index. Utilisé pour mesurer la taille en octets.

```python
stats = es.indices.stats(index="arxiv-papers")
size_bytes = stats["indices"]["arxiv-papers"]["total"]["store"]["size_in_bytes"]
size_mb = round(size_bytes / (1024 * 1024), 1)
```

### `es.cluster.health()`

Retourne l'état de santé du cluster Elasticsearch. C'est la métrique de monitoring la plus critique.

```python
health = es.cluster.health()
print(health["status"])              # "green", "yellow", ou "red"
print(health["active_shards"])       # Nombre de shards actifs
print(health["number_of_pending_tasks"])  # Tâches en attente
print(health["number_of_nodes"])     # Nombre de nœuds
```

| Status | Signification | Action |
|--------|---------------|--------|
| `green` | Tous les shards primaires et réplicas sont actifs | Tout va bien |
| `yellow` | Les shards primaires sont actifs, réplicas manquants | Normal en single-node (pas de réplica possible) |
| `red` | Au moins un shard primaire est inactif → perte de données possible | Alerte immédiate |

---

## 2. Agrégations Elasticsearch utilisées pour le monitoring

### `cardinality` — Comptage de valeurs distinctes

Compte le nombre de valeurs uniques d'un champ. Approximatif pour les gros volumes (algorithme HyperLogLog), exact pour les petits volumes.

```python
result = es.search(
    index="arxiv-papers",
    size=0,
    aggs={"distinct_cats": {"cardinality": {"field": "primary_category"}}},
)
n_categories = result["aggregations"]["distinct_cats"]["value"]  # → 42
```

### `terms` — Top N valeurs

Retourne les N valeurs les plus fréquentes d'un champ `keyword`.

```python
result = es.search(
    index="arxiv-papers",
    size=0,
    aggs={"top_cat": {"terms": {"field": "primary_category", "size": 1}}},
)
top = result["aggregations"]["top_cat"]["buckets"][0]
print(f"{top['key']} : {top['doc_count']}")  # → "cs.LG : 15234"
```

---

## 3. `requests` — Requêtes HTTP vers l'API Kibana

### `requests.get(url, headers, timeout)`

Effectue une requête GET. Utilisé pour interroger les API Kibana (Data Views, Saved Objects).

```python
import requests

resp = requests.get(
    "http://localhost:5601/api/data_views",
    headers={"kbn-xsrf": "true"},     # Header obligatoire pour les API Kibana
    timeout=10,
)
data = resp.json()
```

**`kbn-xsrf: true`** : header anti-CSRF obligatoire pour toutes les requêtes API Kibana. Sans lui, Kibana retourne une erreur 400.

### `resp.status_code`

Code de statut HTTP de la réponse.

```python
if resp.status_code != 200:
    print(f"Erreur HTTP {resp.status_code}")
```

### `resp.json()`

Parse la réponse HTTP comme JSON.

```python
data_views = resp.json().get("data_view", [])
```

### `requests.ConnectionError`

Exception levée quand le serveur est injoignable.

```python
try:
    resp = requests.get(url, headers={"kbn-xsrf": "true"}, timeout=10)
except requests.ConnectionError:
    print("Kibana non accessible")
```

---

## 4. API Kibana — Saved Objects

Kibana stocke ses objets (dashboards, visualisations, Data Views) dans Elasticsearch (index `.kibana`). L'API Saved Objects permet de les lister, exporter et importer.

### Lister les Data Views

```python
resp = requests.get(
    "http://localhost:5601/api/data_views",
    headers={"kbn-xsrf": "true"},
)
for dv in resp.json().get("data_view", []):
    print(f"{dv['title']} — timestamp: {dv.get('timeFieldName', '—')}")
```

### Lister les dashboards

```python
resp = requests.get(
    "http://localhost:5601/api/saved_objects/_find?type=dashboard&per_page=100",
    headers={"kbn-xsrf": "true"},
)
for db in resp.json().get("saved_objects", []):
    title = db["attributes"]["title"]
    panels = json.loads(db["attributes"].get("panelsJSON", "[]"))
    print(f"{title} — {len(panels)} visualisations")
```

### Lister les visualisations Lens

```python
resp = requests.get(
    "http://localhost:5601/api/saved_objects/_find?type=lens&per_page=100",
    headers={"kbn-xsrf": "true"},
)
for obj in resp.json().get("saved_objects", []):
    print(f"  • {obj['attributes'].get('title', 'Sans titre')}")
```

### Exporter tous les objets (NDJSON)

```bash
curl -X POST 'http://localhost:5601/api/saved_objects/_export' \
  -H 'kbn-xsrf: true' \
  -H 'Content-Type: application/json' \
  -d '{"type":["dashboard","visualization","lens","index-pattern","search"],"includeReferencesDeep":true}' \
  -o kibana_export.ndjson
```

### Importer depuis un fichier NDJSON

```bash
curl -X POST 'http://localhost:5601/api/saved_objects/_import' \
  -H 'kbn-xsrf: true' \
  --form file=@kibana_export.ndjson
```

### Récapitulatif des endpoints

| Méthode | Endpoint | Rôle |
|---------|----------|------|
| `GET` | `/api/data_views` | Lister les Data Views |
| `GET` | `/api/saved_objects/_find?type=dashboard` | Lister les dashboards |
| `GET` | `/api/saved_objects/_find?type=lens` | Lister les visualisations Lens |
| `GET` | `/api/saved_objects/_find?type=visualization` | Lister les visualisations classiques |
| `POST` | `/api/saved_objects/_export` | Exporter en NDJSON |
| `POST` | `/api/saved_objects/_import` | Importer depuis NDJSON |

---

## 5. `datetime` — Dates et horodatage (bibliothèque standard)

### `datetime.now(timezone.utc)`

Retourne l'heure actuelle en UTC. Utilisé pour le champ `@timestamp` de chaque entrée de métriques.

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
```

### `.isoformat()`

Convertit un objet datetime en chaîne ISO 8601 — le format qu'Elasticsearch attend pour les champs de type `date`.

```python
ts = datetime.now(timezone.utc).isoformat()
# → "2024-06-15T14:30:00.123456+00:00"
```

### `.timestamp()`

Convertit un datetime en timestamp Unix (secondes depuis le 1er janvier 1970). Utilisé pour calculer la fraîcheur des données HN.

```python
now_ts = int(now.timestamp())           # → 1718458200
hn_ts = 1718457600                       # Timestamp du dernier item HN
age_seconds = now_ts - hn_ts             # → 600 (10 minutes)
```

---

## 6. `json` — Manipulation JSON (bibliothèque standard)

### `json.loads(string)`

Parse une chaîne JSON en objet Python. Utilisé dans `verify_dashboards.py` pour parser le champ `panelsJSON` (liste des visualisations d'un dashboard stockée comme chaîne JSON dans le Saved Object).

```python
import json

panels_json = db["attributes"].get("panelsJSON", "[]")
try:
    panels = json.loads(panels_json)
    panel_count = len(panels)
except json.JSONDecodeError:
    panel_count = 0
```

### `collections.Counter` (dans `export_kibana_dashboards.sh`)

Compteur d'occurrences. Utilisé pour compter les objets exportés par type.

```python
from collections import Counter
types = Counter()
for line in open("export.ndjson"):
    obj = json.loads(line)
    types[obj.get("type", "unknown")] += 1
# → Counter({"dashboard": 2, "lens": 7, "index-pattern": 3})
```

---

## 7. `time` — Mesure du temps et pauses (bibliothèque standard)

### `time.sleep(seconds)`

Met le script en pause. Utilisé dans le mode `--repeat` de `pipeline_metrics.py` pour espacer les mesures.

```python
import time

for i in range(5):
    collect_and_index_metrics()
    if i < 4:
        time.sleep(60)    # Attendre 1 minute entre les mesures
```

### `time.time()`

Retourne le timestamp Unix en secondes (float). Utilisé pour mesurer les durées.

```python
start = time.time()
# ... travail ...
elapsed = time.time() - start
print(f"Durée : {elapsed:.1f}s")
```

---

## 8. `argparse` — Arguments en ligne de commande (bibliothèque standard)

### Configuration dans `pipeline_metrics.py`

```python
import argparse

parser = argparse.ArgumentParser(
    description="SciPulse — Collecte de métriques du pipeline",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="Exemples :\n  python -m src.utils.pipeline_metrics --repeat 5",
)
parser.add_argument("--verbose", "-v", action="store_true", help="Affichage détaillé")
parser.add_argument("--repeat", type=int, default=1, help="Nombre de mesures")
parser.add_argument("--interval", type=int, default=60, help="Intervalle en secondes")
args = parser.parse_args()

print(args.verbose)     # True ou False
print(args.repeat)      # 1 (défaut) ou valeur spécifiée
print(args.interval)    # 60 (défaut) ou valeur spécifiée
```

| Type d'argument | Syntaxe | Exemple d'appel |
|----------------|---------|-----------------|
| Flag booléen | `action="store_true"` | `--verbose` (True si présent, False sinon) |
| Short alias | `"-v"` en plus de `"--verbose"` | `-v` équivalent à `--verbose` |
| Entier | `type=int, default=1` | `--repeat 5` |
| Chaîne (défaut) | `default="value"` | `--output my_file.json` |

---

## 9. Fonctions Python natives

### `dict.get(key, default)`

Accès sûr à un dictionnaire. Omniprésent dans le code de collecte de métriques.

```python
health["status"]                          # Lève KeyError si absent
health.get("status", "unknown")           # Retourne "unknown" si absent
```

### `round(value, decimals)`

Arrondit un float au nombre de décimales spécifié.

```python
rate = round(kw_count / total * 100, 1)   # → 47.8 (un décimal)
size_mb = round(size_bytes / (1024 * 1024), 1)
```

### `max(a, b)`

Retourne la plus grande de deux valeurs. Utilisé pour éviter les valeurs négatives sur la fraîcheur.

```python
metrics["hn_freshness_seconds"] = max(0, age_seconds)
```

### `isinstance(obj, types)`

Vérifie le type d'un objet. Utilisé car le champ `time` des items HN peut être un int ou un float.

```python
if isinstance(latest_ts, (int, float)):
    age_seconds = int(now.timestamp()) - int(latest_ts)
```

### `str[:n]` — Troncature de chaînes

```python
ts = src.get("@timestamp", "?")[:19]     # "2024-06-15T14:30:00" (sans microsecondes)
```

### `f-string` avec formatage numérique

```python
print(f"{count:>8,}")      # Aligné à droite, séparateur de milliers → "  100,000"
print(f"{size_mb:>7.1f}")  # 1 décimale, 7 caractères → "  120.3"
print(f"{rate:>9.1f}%")    # Avec pourcentage → "     47.8%"
```

| Spécificateur | Effet | Exemple |
|---------------|-------|---------|
| `:,` | Séparateur de milliers | `100000` → `100,000` |
| `:.1f` | 1 décimale | `47.832` → `47.8` |
| `:>8` | Aligné à droite sur 8 caractères | `"42"` → `"      42"` |
| `:<35` | Aligné à gauche sur 35 caractères | Tableaux formatés |

---

## 10. Mapping de l'index `pipeline-logs`

Le mapping complet définit le type de chaque métrique collectée. C'est la structure du « journal de bord » du pipeline.

### Types de métriques

| Métrique | Type ES | Source | Unité |
|----------|---------|--------|-------|
| `@timestamp` | `date` | `datetime.now(UTC)` | ISO 8601 |
| `type` | `keyword` | Constante `"pipeline_metrics"` | — |
| `volume_arxiv_papers` | `integer` | `es.count(index="arxiv-papers")` | Documents |
| `volume_hn_items` | `integer` | `es.count(index="hn-items")` | Documents |
| `enriched_with_keywords` | `integer` | `es.count(query=exists:keywords)` | Documents |
| `enrichment_rate_keywords` | `float` | `kw_count / total × 100` | % |
| `hn_freshness_seconds` | `long` | `now - last_hn_timestamp` | Secondes |
| `es_status` | `keyword` | `es.cluster.health()` | green/yellow/red |
| `es_active_shards` | `integer` | `es.cluster.health()` | Shards |
| `index_size_arxiv_mb` | `float` | `es.indices.stats()` | Mo |
| `distinct_categories` | `integer` | Agrégation `cardinality` | Catégories |
| `top_category` | `keyword` | Agrégation `terms` size=1 | Nom |

### Choix du type ES selon la nature de la métrique

| Nature de la donnée | Type ES | Pourquoi |
|---------------------|---------|----------|
| Compteurs (volumes, nombre de shards) | `integer` | Valeurs entières, range queries |
| Taux et pourcentages | `float` | Valeurs décimales, line charts |
| Statuts et identifiants | `keyword` | Valeurs exactes, filtres, agrégations terms |
| Horodatage | `date` | Filtres temporels, date_histogram |
| Durées longues (secondes) | `long` | Entier 64 bits (pas de perte de précision) |

---

## 11. Commandes shell dans les scripts

### `curl -sf URL`

Requête HTTP silencieuse avec fail-fast. `-s` = silent (pas de barre de progression), `-f` = fail silencieusement si HTTP ≥ 400.

```bash
# Vérifier qu'un service répond
if curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; then
    echo "ES OK"
fi

if curl -sf http://localhost:5601/api/status > /dev/null 2>&1; then
    echo "Kibana OK"
fi
```

### `curl -s -o fichier -w "%{http_code}"`

Enregistre le corps de la réponse dans un fichier et affiche uniquement le code HTTP. Utilisé pour l'export Kibana.

```bash
HTTP_CODE=$(curl -s -o export.ndjson -w "%{http_code}" \
    "http://localhost:5601/api/saved_objects/_export" \
    -H 'kbn-xsrf: true' \
    -H 'Content-Type: application/json' \
    -d '{"type":["dashboard","lens"],"includeReferencesDeep":true}')

if [ "$HTTP_CODE" = "200" ]; then
    echo "Export réussi"
fi
```

### `python3 -c "..."` — One-liner Python dans bash

Exécute du Python en une ligne depuis un script shell. Pattern récurrent pour parser du JSON dans les scripts de vérification.

```bash
ARXIV_COUNT=$(curl -s http://localhost:9200/arxiv-papers/_count | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")
```

### `wc -l < fichier`

Compte le nombre de lignes d'un fichier. Utilisé pour compter les objets exportés en NDJSON (un objet par ligne).

```bash
OBJECT_COUNT=$(wc -l < export.ndjson)
```

### `du -h fichier | cut -f1`

Affiche la taille d'un fichier en format lisible (Ko, Mo).

```bash
FILE_SIZE=$(du -h export.ndjson | cut -f1)  # → "12K"
```

### `nohup commande &` — Processus en arrière-plan

Lance un processus qui survit à la fermeture du terminal. Utilisé pour la collecte de métriques en arrière-plan pendant que l'étudiant construit les dashboards.

```bash
nohup python -m src.utils.pipeline_metrics --repeat 10 --interval 60 > /tmp/metrics.log 2>&1 &
METRICS_PID=$!
echo "PID: $METRICS_PID"

# Plus tard, pour arrêter :
kill $METRICS_PID
```

### `kill -0 PID` — Vérifier qu'un processus tourne

Envoie le signal 0 (pas de signal réel — juste une vérification). Retourne 0 si le processus existe, 1 sinon.

```bash
if kill -0 "$METRICS_PID" 2>/dev/null; then
    echo "Le processus tourne encore"
    kill "$METRICS_PID"
fi
```

### `read -p "message" variable` — Entrée interactive

Attend que l'utilisateur appuie sur Entrée. Utilisé dans le workflow pour attendre la fin de la construction des dashboards.

```bash
read -p "Appuyez sur Entrée quand les dashboards sont créés... " _
```

### `mkdir -p chemin`

Crée un répertoire et tous ses parents. `-p` = pas d'erreur si le dossier existe déjà.

```bash
mkdir -p docs/
```

---

## 12. Composants Kibana — Référence rapide

Ce TP se fait principalement dans l'interface Kibana (pas en code). Voici les composants utilisés.

### Data View

Connecte Kibana à un index ES. Créé dans Stack Management → Data Views.

| Data View | Index | Timestamp |
|-----------|-------|-----------|
| `arxiv-papers` | `arxiv-papers` | `date_updated` |
| `hn-items` | `hn-items` | `time` |
| `pipeline-logs` | `pipeline-logs*` | `@timestamp` |

### Lens — Types de visualisations

| Type | Usage dans le TP | Agrégation ES sous-jacente |
|------|------------------|---------------------------|
| **Metric** | Total articles, statut ES, taille index | `count`, `last_value` |
| **Bar horizontal** | Top 20 catégories | `terms` |
| **Area chart** | Publications par mois, empilé par catégorie | `date_histogram` + `terms` |
| **Line chart** | Évolution des volumes (monitoring) | `date_histogram` + `last_value` |
| **Tag cloud** | Mots-clés les plus fréquents | `terms` |
| **Pie / Donut** | Répartition des types HN | `terms` |
| **Table** | Articles récents, historique métriques | `top_hits`, `last_value` |

### Dashboard — Fonctionnalités

| Action | Comment |
|--------|---------|
| Créer | Analytics → Dashboard → Create dashboard |
| Ajouter une viz | Bouton « Create visualization » dans le dashboard |
| Plein écran | Icône rectangle en haut à droite |
| Cross-filtering | Cliquer sur une barre / part → filtre tout |
| Modifier une viz | Cliquer → icône crayon |
| Changer la plage temporelle | Sélecteur en haut à droite (Last 15 years pour ArXiv) |
| Sauvegarder | Bouton Save en haut à droite |

---

## 13. Récapitulatif du flux de données du monitoring

```
Elasticsearch                              Python
┌───────────────┐                    ┌──────────────────────┐
│ arxiv-papers  │─── es.count() ────▶│                      │
│ hn-items      │─── es.search() ───▶│  pipeline_metrics.py │
│ arxiv-hn-links│─── es.count() ────▶│                      │
│               │                    │  collect_metrics()   │
│ cluster       │─── health() ──────▶│  → 20+ métriques     │
│               │                    │                      │
│               │    es.index()      │  index_metrics()     │
│ pipeline-logs │◀───────────────────│                      │
└───────┬───────┘                    └──────────────────────┘
        │
        │  Data View
        ▼
┌───────────────┐
│    KIBANA      │
│                │
│  Dashboard     │  ← Metric tiles + Line chart + Table
│  monitoring    │
└───────────────┘
```

### Cycle complet

1. `pipeline_metrics.py` interroge ES (volumes, enrichissement, santé, tailles).
2. Les métriques sont indexées dans `pipeline-logs`.
3. Kibana les affiche dans le dashboard de monitoring via un Data View.
4. Le script peut tourner en boucle (`--repeat`) pour accumuler un historique.
5. Le line chart Kibana montre l'évolution des volumes dans le temps.

---

## 14. Commandes du TP

### Collecte de métriques

```bash
# Une seule mesure
python -m src.utils.pipeline_metrics

# Avec détails
python -m src.utils.pipeline_metrics --verbose

# 5 mesures à 1 minute d'intervalle
python -m src.utils.pipeline_metrics --repeat 5 --interval 60

# En arrière-plan pendant le TP
bash scripts/collect_metrics_loop.sh &
```

### Vérification post-construction

```bash
python scripts/verify_dashboards.py
```

### Export des dashboards pour Git

```bash
bash scripts/export_kibana_dashboards.sh
# → docs/kibana_dashboards_export.ndjson
```
