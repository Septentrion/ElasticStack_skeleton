# TP J3 après-midi — Fouille de texte avancée

---

## 1. Requêtes Elasticsearch (Query DSL)

Toutes s'exécutent via `es.search(index=..., body={...})` en Python ou copier-coller dans Kibana Dev Tools.

### `match` — Recherche sur un champ

```json
{"query": {"match": {"abstract": {"query": "reinforcement learning", "operator": "and"}}}}
```

### `multi_match` — Recherche multi-champs avec boost

```json
{"query": {"multi_match": {"query": "transformer", "fields": ["title^3", "abstract"], "type": "cross_fields"}}}
```

Les types : `best_fields` (meilleur champ), `most_fields` (somme), `cross_fields` (termes répartis entre champs).

### `match_phrase` — Phrase exacte avec tolérance

```json
{"query": {"match_phrase": {"abstract": {"query": "attention mechanism", "slop": 2}}}}
```

`slop` : nombre de mots intercalés autorisés.

### `bool` — Combinaison de clauses

```json
{"query": {"bool": {
  "must": [...],       "filter": [...],
  "should": [...],     "must_not": [...]
}}}
```

`must` : contribue au score. `filter` : pas de score, mis en cache.

### `function_score` — Tuning de la pertinence

```json
{"query": {"function_score": {
  "query": {"bool": {...}},
  "functions": [
    {"gauss": {"date_updated": {"origin": "now", "scale": "365d", "decay": 0.5}}},
    {"field_value_factor": {"field": "hn_score", "modifier": "log1p", "missing": 1}}
  ],
  "boost_mode": "multiply"
}}}
```

### `more_like_this` — Articles similaires

```json
{"query": {"more_like_this": {
  "fields": ["title", "abstract"],
  "like": [{"_index": "arxiv-papers", "_id": "2301.07041"}],
  "min_term_freq": 1, "max_query_terms": 25, "min_doc_freq": 2
}}}
```

### `highlight` — Surligner les termes matchés

```json
{"highlight": {"fields": {"abstract": {"fragment_size": 200, "number_of_fragments": 2}},
  "pre_tags": ["<mark>"], "post_tags": ["</mark>"]}}
```

### `suggest` — Correction de saisie

```json
{"suggest": {"s": {"text": "convlutional nueral", "phrase": {"field": "title", "size": 3,
  "direct_generator": [{"field": "title", "suggest_mode": "popular"}]}}}}
```

---

## 2. Agrégations Elasticsearch

### `terms` — Top N valeurs

```json
{"aggs": {"top_cat": {"terms": {"field": "primary_category", "size": 20}}}}
```

### `significant_terms` — Termes distinctifs

```json
{"aggs": {"sig": {"sampler": {"shard_size": 5000}, "aggs": {"kw": {"significant_terms": {"field": "abstract", "size": 20}}}}}}
```

### `date_histogram` — Distribution temporelle

```json
{"aggs": {"par_mois": {"date_histogram": {"field": "date_updated", "calendar_interval": "month"}}}}
```

### `cardinality` — Comptage distinct

```json
{"aggs": {"distinct_cats": {"cardinality": {"field": "primary_category"}}}}
```

---

## 3. `pytest` + `unittest.mock` — Tests unitaires

### `@pytest.fixture`

Déclare une fixture (objet réutilisable par les tests). Injecté automatiquement par nom de paramètre.

```python
import pytest

@pytest.fixture
def mock_es():
    with patch("src.search.search_service.Elasticsearch") as MockES:
        yield MockES.return_value
```

### `patch(target)` (context manager)

Remplace un objet par un mock pendant la durée du `with`. Utilisé pour simuler Elasticsearch sans connexion réelle.

```python
from unittest.mock import patch

with patch("src.search.search_service.Elasticsearch") as MockES:
    instance = MockES.return_value
    instance.search.return_value = {"hits": {"hits": [], "total": {"value": 0}}}
```

### `mock.return_value`

Définit ce que le mock retourne quand il est appelé.

```python
mock_es.search.return_value = {"hits": {"hits": [], "total": {"value": 0}}}
```

### `mock.call_args`

Accède aux arguments du dernier appel au mock. `[0]` = args positionnels, `[1]` = kwargs.

```python
call_body = mock_es.search.call_args[1]["body"]
assert "multi_match" in json.dumps(call_body)
```

### `json.dumps(obj)` pour les assertions

Convertit un dict en chaîne JSON pour vérifier la présence d'un mot-clé quelque part dans la structure.

```python
import json
body_str = json.dumps(call_body)
assert "cs.AI" in body_str
```

---
---

# TP J4 matin — Orchestration Airflow

---

## 1. `airflow` — Concepts et API

### `DAG(dag_id, default_args, schedule_interval, ...)`

Définit un graphe orienté acyclique de tâches.

```python
from datetime import datetime, timedelta
from airflow import DAG

with DAG(
    dag_id="scipulse_arxiv_pipeline",
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    schedule_interval=None,          # Déclenchement manuel
    start_date=datetime(2024, 1, 1),
    catchup=False,                   # Ne pas rattraper les runs passés
    max_active_runs=1,               # Un seul run à la fois
    tags=["scipulse"],
) as dag:
    ...
```

### `BashOperator(task_id, bash_command)`

Exécute une commande shell. Le principal opérateur utilisé dans SciPulse.

```python
from airflow.operators.bash import BashOperator

download = BashOperator(
    task_id="download_arxiv_dump",
    bash_command='echo "Hello" && ls /data/',
)
```

### `>>` — Opérateur de dépendance

Définit l'ordre d'exécution entre les tâches.

```python
download >> validate >> ingest >> transform >> enrich >> validate_final
```

### `default_args` — Paramètres par défaut

| Paramètre | Rôle | Valeur typique |
|-----------|------|----------------|
| `retries` | Nombre de tentatives en cas d'échec | `1` à `3` |
| `retry_delay` | Délai entre les tentatives | `timedelta(minutes=2)` |
| `execution_timeout` | Durée max d'une tâche | `timedelta(hours=1)` |
| `depends_on_past` | Conditionner sur le run précédent | `False` (recommandé) |
| `email_on_failure` | Envoyer un email en cas d'échec | `False` en TP |

---

## 2. `subprocess` — Exécution de commandes système

### `subprocess.run(cmd, capture_output, text, timeout)`

Exécute une commande shell et capture la sortie. Utilisé dans `verify_airflow.py`.

```python
import subprocess

result = subprocess.run(
    "docker ps --format '{{.Names}}'",
    shell=True,
    capture_output=True,
    text=True,
    timeout=15,
)
print(result.returncode)    # 0 = succès
print(result.stdout)        # Sortie standard
```

---

## 3. Commandes Airflow CLI

| Commande | Rôle |
|----------|------|
| `airflow dags list` | Lister tous les DAGs |
| `airflow dags list-import-errors` | Afficher les erreurs de parsing des DAGs |
| `airflow dags trigger <dag_id>` | Déclencher un run manuellement |
| `airflow dags unpause <dag_id>` | Activer un DAG |
| `airflow dags reserialize` | Forcer le rechargement des fichiers DAG |
| `airflow dags list-runs -d <dag_id>` | Historique des runs d'un DAG |

---
---

# TP J4 après-midi — Dashboard Kibana et monitoring

---

## 1. `requests` — Requêtes HTTP vers l'API Kibana

### `requests.get(url, headers, timeout)`

Requête GET. Utilisé pour interroger l'API Saved Objects de Kibana.

```python
import requests

resp = requests.get(
    "http://localhost:5601/api/data_views",
    headers={"kbn-xsrf": "true"},     # Header obligatoire pour les API Kibana
    timeout=10,
)
data_views = resp.json().get("data_view", [])
```

### `requests.ConnectionError`

Exception levée si Kibana n'est pas accessible.

```python
try:
    resp = requests.get(url, headers={"kbn-xsrf": "true"}, timeout=10)
except requests.ConnectionError:
    print("Kibana non accessible")
```

### API Kibana Saved Objects

| Endpoint | Rôle |
|----------|------|
| `GET /api/data_views` | Lister les Data Views |
| `GET /api/saved_objects/_find?type=dashboard` | Lister les dashboards |
| `GET /api/saved_objects/_find?type=lens` | Lister les visualisations Lens |
| `POST /api/saved_objects/_export` | Exporter tous les objets en NDJSON |
| `POST /api/saved_objects/_import` | Importer depuis un fichier NDJSON |

---

## 2. `datetime` — Dates et horodatage (bibliothèque standard)

### `datetime.now(timezone.utc).isoformat()`

Retourne l'horodatage courant en UTC au format ISO 8601. Utilisé pour le champ `@timestamp` des métriques.

```python
from datetime import datetime, timezone

ts = datetime.now(timezone.utc).isoformat()   # → "2024-06-15T14:30:00.123456+00:00"
```

---

## 3. Elasticsearch — Fonctions spécifiques au monitoring

### `es.cluster.health()`

Retourne l'état de santé du cluster (green/yellow/red, nombre de shards, tâches en attente).

```python
health = es.cluster.health()
print(health["status"])           # → "green"
print(health["active_shards"])    # → 12
print(health["number_of_nodes"])  # → 1
```

### `es.indices.create(index, body)`

Crée un index avec un mapping et des settings explicites.

```python
es.indices.create(index="pipeline-logs", body={
    "settings": {"number_of_shards": 1},
    "mappings": {
        "properties": {
            "@timestamp": {"type": "date"},
            "es_status": {"type": "keyword"},
            "volume_arxiv_papers": {"type": "integer"},
        }
    },
})
```

### `es.index(index, document)`

Indexe un document unique (sans `_id` explicite — Elasticsearch génère un ID aléatoire). Utilisé pour les métriques de monitoring.

```python
es.index(index="pipeline-logs", document={
    "@timestamp": "2024-06-15T14:30:00Z",
    "type": "pipeline_metrics",
    "volume_arxiv_papers": 100000,
    "es_status": "green",
})
```

---

## 4. Composants Kibana (interface graphique)

Référence rapide des éléments construits dans le TP (pas de code — manipulation dans l'UI).

| Composant | Rôle | Où le créer |
|-----------|------|-------------|
| **Data View** | Connecte Kibana à un index ES | Stack Management → Data Views |
| **Lens** | Constructeur visuel de graphiques | Create visualization (dans un dashboard) |
| **Dashboard** | Composition de visualisations | Analytics → Dashboard |
| **Metric tile** | Chiffre clé unique (KPI) | Lens → type Metric |
| **Bar chart** | Classement (top N catégories) | Lens → type Bar horizontal |
| **Area chart** | Évolution temporelle empilée | Lens → type Area |
| **Line chart** | Tendances (courbes) | Lens → type Line |
| **Tag cloud** | Nuage de mots-clés | Lens → type Tag cloud |
| **Data table** | Tableau de résultats détaillés | Lens → type Table |
| **Pie / Donut** | Répartition proportionnelle (≤ 5 parts) | Lens → type Pie |

### Raccourcis Kibana

| Action | Comment |
|--------|---------|
| Plein écran | Icône rectangle en haut à droite du dashboard |
| Cross-filtering | Cliquer sur une barre/part → filtre tout le dashboard |
| Modifier une viz | Cliquer sur la viz → icône crayon |
| Changer la plage temporelle | Sélecteur en haut à droite (Last 15 years pour ArXiv) |
| Export NDJSON | `curl -X POST localhost:5601/api/saved_objects/_export -H 'kbn-xsrf: true' -d '{"type":["dashboard"]}'` |
