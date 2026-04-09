# Jour 4 — Après-midi
# TP : Dashboard Kibana « SciPulse » et monitoring

> **Durée** : 2h45  
> **Niveau** : débutant — chaque étape est détaillée avec des captures d'écran textuelles  
> **Prérequis** : Jour 4 matin complété (DAGs Airflow fonctionnels, index ES peuplés et enrichis)

---

## Ce que vous allez construire

À la fin de ce TP, vous aurez :

1. Trois Data Views configurés dans Kibana (arxiv, hn, logs).
2. Un dashboard métier « SciPulse » avec 7+ visualisations.
3. Un index `pipeline-logs` alimenté par des métriques de pipeline.
4. Un dashboard de monitoring du pipeline.
5. Un livrable prêt pour la présentation du Jour 5.

---

## Vérifications préalables (5 min)

```bash
# Kibana accessible ?
curl -sf http://localhost:5601/api/status | python -m json.tool | head -5
# → "status": { "overall": { "level": "available" } }

# Données enrichies dans ES ?
curl -s http://localhost:9200/arxiv-papers/_count
# → ~100 000

# Mots-clés présents ?
curl -s 'http://localhost:9200/arxiv-papers/_count' \
  -H 'Content-Type: application/json' \
  -d '{"query":{"exists":{"field":"keywords"}}}'
# → > 0
```

Ouvrez Kibana : http://localhost:5601

---

# PARTIE A — Configuration des Data Views (10 min)

## Étape 1 — Créer les Data Views

### 1.1. Data View ArXiv

1. Menu ☰ → **Stack Management** → **Kibana** → **Data Views**.
2. Cliquez **Create data view**.
3. Remplissez :
   - **Name** : `arxiv-papers`
   - **Index pattern** : `arxiv-papers`
   - **Timestamp field** : `date_updated`
4. Cliquez **Save data view to Kibana**.

### 1.2. Data View HN

Même procédure :

- **Name** : `hn-items`
- **Index pattern** : `hn-items`
- **Timestamp field** : `time`

### 1.3. Data View Pipeline Logs

- **Name** : `pipeline-logs`
- **Index pattern** : `pipeline-logs-*`
- **Timestamp field** : `@timestamp`

*(Si l'index `pipeline-logs-*` n'existe pas encore, ce n'est pas grave — nous le créerons dans la Partie C.)*

---

# PARTIE B — Dashboard métier « SciPulse » (1h30)

## Étape 2 — Créer le dashboard

1. Menu ☰ → **Analytics** → **Dashboard**.
2. Cliquez **Create dashboard**.
3. Cliquez le bouton **Save** en haut à droite.
4. Nommez-le : `SciPulse — Observatoire scientifique`.
5. Sauvegardez.

Le dashboard est vide pour l'instant. Nous allons ajouter les visualisations une par une.

**Important** : élargissez la plage temporelle en haut à droite. Sélectionnez **Last 15 years** (ou « Absolute » avec 2010-01-01 → aujourd'hui) pour voir les données historiques ArXiv.

---

## Étape 3 — Metric tiles : les chiffres clés (10 min)

Les metric tiles donnent l'état de santé du corpus en un coup d'œil. Nous en créerons 4.

### 3.1. Total articles

1. Dans le dashboard, cliquez **Create visualization**.
2. Kibana ouvre **Lens**.
3. En haut à gauche, sélectionnez le data view `arxiv-papers`.
4. Dans le panneau de gauche, trouvez le champ `Records` (tout en haut de la liste).
5. Glissez-le dans la zone centrale.
6. Lens affiche automatiquement un **Metric** avec le nombre total de documents.
7. Cliquez sur le titre « Count of records » dans la zone de configuration à droite et renommez-le en `Total articles`.
8. Cliquez **Save and return** (en haut à droite).

Le metric tile apparaît dans le dashboard.

### 3.2. Articles avec mots-clés

1. Cliquez **Create visualization** à nouveau.
2. Data view : `arxiv-papers`.
3. Dans la zone de configuration de la métrique :
   - Cliquez sur la métrique par défaut (Count).
   - Changez la fonction en **Count**.
   - Ajoutez un filtre en cliquant sur l'icône filtre : `keywords : *` (exists).
   
   *Méthode alternative plus simple :*
   - Type de visualisation : **Metric**.
   - Glissez `Records` dans la zone.
   - Dans le panneau de droite, ajoutez un filtre KQL : `keywords: *`.
4. Renommez en `Articles enrichis (mots-clés)`.
5. **Save and return**.

### 3.3. Articles liés à HN

Même procédure avec le filtre : `hn_score > 0`.

- Renommez : `Articles liés à HN`.

### 3.4. Catégories distinctes

1. Créez une visualisation Metric.
2. Changez la fonction en **Unique count** sur le champ `primary_category`.
3. Renommez : `Catégories distinctes`.
4. **Save and return**.

**Résultat** : 4 metric tiles en haut du dashboard montrant les KPI essentiels.

Redimensionnez les tiles pour qu'ils soient alignés sur une seule ligne. Glissez-les pour les réordonner : Total → Enrichis → Liés HN → Catégories.

---

## Étape 4 — Area chart : évolution temporelle (15 min)

### 4.1. Publications par mois

1. **Create visualization**.
2. Data view : `arxiv-papers`.
3. Type de visualisation : **Area** (sélectionnez dans le sélecteur de type en haut à gauche de Lens).
4. Axe horizontal :
   - Glissez `date_updated` sur l'axe horizontal.
   - Lens configure automatiquement un `date_histogram` par mois.
5. Axe vertical : déjà configuré sur `Count`.
6. Pour ajouter une ventilation par catégorie :
   - Glissez `primary_category` dans la section **Break down by**.
   - Lens va créer une area empilée par catégorie.
   - Dans la configuration, limitez à **Top 5** catégories (sinon c'est illisible).
7. Renommez : `Publications par mois (top 5 catégories)`.
8. **Save and return**.

Vous devriez voir l'évolution exponentielle des publications avec la ventilation par catégorie — cs.LG et cs.AI dominent les dernières années.

---

## Étape 5 — Bar chart : top catégories (10 min)

### 5.1. Top 20 catégories

1. **Create visualization**.
2. Data view : `arxiv-papers`.
3. Type : **Bar horizontal**.
4. Axe vertical : glissez `primary_category`. Configurez **Top 20**.
5. Axe horizontal : **Count**.
6. Dans les options de style, assurez-vous que les barres sont triées par valeur décroissante.
7. Renommez : `Top 20 catégories`.
8. **Save and return**.

---

## Étape 6 — Tag cloud : mots-clés émergents (10 min)

### 6.1. Nuage de mots-clés TF-IDF

1. **Create visualization**.
2. Data view : `arxiv-papers`.
3. Type : **Tag cloud** (dans le sélecteur de types en haut).
4. Tag : glissez `keywords`. Configurez **Top 50**.
5. Size : **Count** (les mots-clés les plus fréquents sont les plus gros).
6. Renommez : `Mots-clés les plus fréquents`.
7. **Save and return**.

Le tag cloud montre les termes les plus courants extraits par TF-IDF : `learning`, `model`, `neural network`, `algorithm`…

**Exercice** : filtrez le dashboard sur une catégorie spécifique (cliquez sur une barre du bar chart « Top 20 catégories ») et observez comment le tag cloud change. Les mots-clés de cs.CV seront très différents de ceux de cs.CL.

---

## Étape 7 — Data table : résultats de recherche (15 min)

### 7.1. Articles les plus récents avec mots-clés

1. **Create visualization**.
2. Data view : `arxiv-papers`.
3. Type : **Table**.
4. Colonnes à ajouter (glissez depuis la liste de champs) :
   - `title` (cliquez pour configurer : afficher les 100 premiers caractères).
   - `primary_category`.
   - `date_updated`.
   - `keywords` (les mots-clés TF-IDF).
   - `hn_score` (score HN, si disponible).
5. Triez par `date_updated` décroissant.
6. Configurez le nombre de lignes à 15.
7. Renommez : `Articles récents`.
8. **Save and return**.

### 7.2. Articles populaires sur HN

Si vous avez des articles avec un `hn_score` > 0 :

1. **Create visualization**.
2. Data view : `arxiv-papers`.
3. Type : **Table**.
4. Ajoutez un filtre KQL : `hn_score > 0`.
5. Colonnes : `title`, `primary_category`, `hn_score`, `hn_comments_count`.
6. Triez par `hn_score` décroissant.
7. Renommez : `Articles les plus populaires sur Hacker News`.
8. **Save and return**.

*Si aucun article n'a de score HN, passez cette visualisation — elle apparaîtra quand le poller aura accumulé plus de données.*

---

## Étape 8 — Line chart : tendances temporelles (10 min)

### 8.1. Évolution des publications par domaine

1. **Create visualization**.
2. Data view : `arxiv-papers`.
3. Type : **Line**.
4. Axe X : `date_updated` (date_histogram, interval year).
5. Axe Y : Count.
6. Break down by : glissez `primary_category`, **Top 3**.
7. Renommez : `Tendances par catégorie (top 3)`.
8. **Save and return**.

---

## Étape 9 — Pie chart : répartition HN (10 min)

### 9.1. Types de posts HN

1. **Create visualization**.
2. Changez le Data View : `hn-items`.
3. Type : **Pie** (ou **Donut**).
4. Slice by : glissez `type`.
5. Size : Count.
6. Renommez : `Répartition des types HN`.
7. **Save and return**.

---

## Étape 10 — Organiser le dashboard (10 min)

Maintenant que toutes les visualisations sont créées, organisons le layout :

### Layout recommandé

```
┌──────────┬──────────┬──────────┬──────────┐
│  Total   │ Enrichis │ Liés HN  │ Catég.   │  ← Row 1 : Metric tiles
│ articles │ (kw)     │          │ distinctes│
└──────────┴──────────┴──────────┴──────────┘
┌──────────────────────────────────────────┐
│                                          │
│   Publications par mois (area chart)     │  ← Row 2 : Vue temporelle
│                                          │
└──────────────────────────────────────────┘
┌──────────────────┬───────────────────────┐
│                  │                       │
│ Top 20 catég.    │  Mots-clés (tag cloud)│  ← Row 3 : Distribution
│ (bar horiz.)     │                       │
│                  │                       │
└──────────────────┴───────────────────────┘
┌──────────────────┬───────────────────────┐
│ Tendances top 3  │ Répartition HN (pie)  │  ← Row 4 : Détails
│ (line chart)     │                       │
└──────────────────┴───────────────────────┘
┌──────────────────────────────────────────┐
│                                          │
│   Articles récents (table)               │  ← Row 5 : Détail
│                                          │
└──────────────────────────────────────────┘
```

Pour redimensionner : survolez le coin bas-droit d'une visualisation et glissez.

Pour réordonner : survolez le titre et glissez la visualisation vers sa nouvelle position.

### Sauvegardez

Cliquez **Save** en haut à droite. Le dashboard est prêt.

### Testez le cross-filtering

Cliquez sur une barre dans « Top 20 catégories » (par ex. `cs.CV`). Toutes les autres visualisations se filtrent automatiquement sur cette catégorie :

- L'area chart ne montre plus que les publications cs.CV.
- Le tag cloud montre les mots-clés spécifiques à Computer Vision.
- La table ne montre que les articles cs.CV.

C'est le **cross-filtering** — la fonctionnalité la plus puissante des dashboards Kibana pour l'exploration interactive.

---

# PARTIE C — Dashboard de monitoring (45 min)

## Étape 11 — Créer l'index de logs du pipeline (15 min)

Pour le monitoring, nous avons besoin de logs du pipeline dans Elasticsearch. Plutôt que de configurer Filebeat (qui nécessiterait un conteneur supplémentaire), nous allons créer un script Python qui alimente l'index `pipeline-logs` avec des métriques du pipeline.

### 11.1. Créer le script de métriques

Créez `src/utils/pipeline_metrics.py` :

```python
"""
SciPulse — Collecte de métriques du pipeline pour le dashboard de monitoring

Ce script interroge Elasticsearch et PostgreSQL pour collecter des
métriques opérationnelles (volumes, fraîcheur, santé) et les indexe
dans un index dédié pipeline-logs.

Usage :
    python -m src.utils.pipeline_metrics
"""

import sys
from datetime import datetime, timezone

from elasticsearch import Elasticsearch

ES_HOST = "http://localhost:9200"
LOG_INDEX = "pipeline-logs"


def collect_metrics(es: Elasticsearch) -> dict:
    """Collecte les métriques du pipeline."""
    metrics = {
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "pipeline_metrics",
    }

    # ── Volumes ────────────────────────────────────────────────────
    for index_name in ["arxiv-papers", "arxiv-papers-raw", "hn-items", "arxiv-hn-links"]:
        try:
            count = es.count(index=index_name)["count"]
            metrics[f"volume_{index_name.replace('-', '_')}"] = count
        except Exception:
            metrics[f"volume_{index_name.replace('-', '_')}"] = 0

    # ── Enrichissement ─────────────────────────────────────────────
    try:
        kw_count = es.count(
            index="arxiv-papers",
            query={"exists": {"field": "keywords"}},
        )["count"]
        metrics["enriched_with_keywords"] = kw_count
    except Exception:
        metrics["enriched_with_keywords"] = 0

    try:
        hn_count = es.count(
            index="arxiv-papers",
            query={"exists": {"field": "hn_score"}},
        )["count"]
        metrics["enriched_with_hn_score"] = hn_count
    except Exception:
        metrics["enriched_with_hn_score"] = 0

    # ── Fraîcheur ──────────────────────────────────────────────────
    try:
        latest = es.search(
            index="hn-items",
            size=1,
            sort=[{"time": "desc"}],
            _source=["time"],
        )
        if latest["hits"]["hits"]:
            latest_time = latest["hits"]["hits"][0]["_source"]["time"]
            metrics["hn_latest_timestamp"] = latest_time
    except Exception:
        pass

    # ── Santé ES ───────────────────────────────────────────────────
    try:
        health = es.cluster.health()
        metrics["es_status"] = health["status"]
        metrics["es_active_shards"] = health["active_shards"]
        metrics["es_pending_tasks"] = health["number_of_pending_tasks"]
    except Exception:
        metrics["es_status"] = "unknown"

    # ── Taille des index ───────────────────────────────────────────
    try:
        stats = es.indices.stats(index="arxiv-papers")
        size_bytes = stats["indices"]["arxiv-papers"]["total"]["store"]["size_in_bytes"]
        metrics["index_size_mb"] = round(size_bytes / (1024 * 1024), 1)
    except Exception:
        metrics["index_size_mb"] = 0

    return metrics


def index_metrics(es: Elasticsearch, metrics: dict):
    """Indexe les métriques dans l'index pipeline-logs."""
    # Créer l'index s'il n'existe pas
    if not es.indices.exists(index=LOG_INDEX):
        es.indices.create(index=LOG_INDEX, body={
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "type": {"type": "keyword"},
                    "es_status": {"type": "keyword"},
                }
            },
        })

    es.index(index=LOG_INDEX, document=metrics)
    es.indices.refresh(index=LOG_INDEX)


def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SciPulse — Collecte de métriques du pipeline           ║")
    print("╚══════════════════════════════════════════════════════════╝")

    es = Elasticsearch(ES_HOST)
    try:
        es.info()
    except Exception as e:
        print(f"\n❌ ES non accessible : {e}")
        sys.exit(1)

    print("\n📊 Collecte des métriques...")
    metrics = collect_metrics(es)

    print("\n  Métriques collectées :")
    for k, v in sorted(metrics.items()):
        if k != "@timestamp":
            print(f"    {k:<35} {v}")

    print("\n📤 Indexation dans '{}'...".format(LOG_INDEX))
    index_metrics(es, metrics)

    total = es.count(index=LOG_INDEX)["count"]
    print(f"   ✅ {total} entrées dans '{LOG_INDEX}'")

    print("\n💡 Exécutez ce script régulièrement pour accumuler un historique.")
    print("   En production, intégrez-le comme tâche Airflow.")
    print()


if __name__ == "__main__":
    main()
```

### 11.2. Exécuter la collecte

```bash
python -m src.utils.pipeline_metrics
```

Exécutez le script **3-4 fois** à quelques minutes d'intervalle pour créer un petit historique :

```bash
python -m src.utils.pipeline_metrics
sleep 60
python -m src.utils.pipeline_metrics
sleep 60
python -m src.utils.pipeline_metrics
```

### 11.3. Créer le Data View

Si vous ne l'avez pas fait à l'étape 1 :

1. Menu ☰ → Stack Management → Data Views → Create data view.
2. Name : `pipeline-logs`, Index pattern : `pipeline-logs*`, Timestamp : `@timestamp`.

---

## Étape 12 — Construire le dashboard de monitoring (30 min)

### 12.1. Créer le dashboard

1. Menu ☰ → Dashboard → Create dashboard.
2. Sauvegardez immédiatement sous le nom : `SciPulse — Monitoring Pipeline`.

### 12.2. Metric tiles de santé

Créez 4 metric tiles (même procédure que l'étape 3) avec le Data View `pipeline-logs` :

**Tile 1 — Statut ES** :
- Type : Metric.
- Métrique : **Last value** du champ `es_status`.
- Renommez : `Statut Elasticsearch`.

**Tile 2 — Volume ArXiv** :
- Métrique : **Last value** du champ `volume_arxiv_papers`.
- Renommez : `Volume arxiv-papers`.

**Tile 3 — Volume HN** :
- Métrique : **Last value** du champ `volume_hn_items`.
- Renommez : `Volume hn-items`.

**Tile 4 — Taille index** :
- Métrique : **Last value** du champ `index_size_mb`.
- Renommez : `Taille index (Mo)`.

### 12.3. Line chart — évolution des volumes

1. **Create visualization**.
2. Data view : `pipeline-logs`.
3. Type : **Line**.
4. Axe X : `@timestamp`.
5. Axe Y : ajoutez plusieurs métriques :
   - **Last value** de `volume_arxiv_papers` (renommez en « ArXiv »).
   - **Last value** de `volume_hn_items` (renommez en « HN »).
   - **Last value** de `enriched_with_keywords` (renommez en « Enrichis »).
6. Renommez : `Évolution des volumes`.
7. **Save and return**.

*Note : si vous n'avez que 3-4 points de données, le graphique sera rudimentaire. En production, avec des métriques toutes les 5 minutes, la courbe serait beaucoup plus riche.*

### 12.4. Table — dernières métriques

1. **Create visualization**.
2. Data view : `pipeline-logs`.
3. Type : **Table**.
4. Colonnes : `@timestamp`, `es_status`, `volume_arxiv_papers`, `volume_hn_items`, `enriched_with_keywords`, `index_size_mb`.
5. Triez par `@timestamp` décroissant.
6. Limitez à 10 lignes.
7. Renommez : `Historique des métriques`.
8. **Save and return**.

### 12.5. Layout du dashboard monitoring

```
┌──────────┬──────────┬──────────┬──────────┐
│  Statut  │ Volume   │ Volume   │ Taille   │  ← Santé en un coup d'œil
│  ES      │ ArXiv    │ HN       │ index    │
└──────────┴──────────┴──────────┴──────────┘
┌──────────────────────────────────────────┐
│                                          │
│   Évolution des volumes (line chart)     │  ← Tendance
│                                          │
└──────────────────────────────────────────┘
┌──────────────────────────────────────────┐
│                                          │
│   Historique des métriques (table)       │  ← Détail
│                                          │
└──────────────────────────────────────────┘
```

Sauvegardez le dashboard.

---

## Étape 13 — Mode présentation (5 min)

Testez le mode plein écran pour préparer la démo du Jour 5 :

1. Ouvrez le dashboard `SciPulse — Observatoire scientifique`.
2. Cliquez sur l'icône **plein écran** (rectangle en haut à droite, à côté de Share).
3. Le dashboard occupe tout l'écran — parfait pour une projection.
4. Appuyez sur `Escape` pour revenir au mode normal.

Testez aussi le **cross-filtering** en mode plein écran : cliquez sur une catégorie dans le bar chart et observez toutes les visualisations se mettre à jour.

---

## Étape 14 — Commit (5 min)

```bash
git add src/utils/pipeline_metrics.py
git commit -m "feat: add pipeline metrics collection + Kibana dashboards documented"
```

**Note** : les dashboards Kibana sont stockés dans Elasticsearch (index `.kibana`), pas dans Git. Pour les versionner en production, on utiliserait l'API Saved Objects de Kibana pour les exporter en JSON :

```bash
# Export des dashboards (pour information)
curl -s http://localhost:5601/api/saved_objects/_export \
  -H 'kbn-xsrf: true' \
  -H 'Content-Type: application/json' \
  -d '{"type":["dashboard","visualization","lens","index-pattern"]}' \
  > kibana_export.ndjson
```

---

## Checklist de fin de journée

- [ ] 3 Data Views configurés (arxiv-papers, hn-items, pipeline-logs)
- [ ] Dashboard « SciPulse — Observatoire scientifique » créé avec 7+ visualisations
- [ ] Metric tiles (4) montrant les KPI essentiels
- [ ] Area chart de l'évolution temporelle par catégorie
- [ ] Bar chart horizontal des top 20 catégories
- [ ] Tag cloud des mots-clés
- [ ] Data table des articles récents
- [ ] Cross-filtering testé (cliquer sur une catégorie filtre tout)
- [ ] Script `pipeline_metrics.py` créé et exécuté
- [ ] Dashboard « SciPulse — Monitoring Pipeline » créé
- [ ] Mode plein écran testé (prêt pour la présentation)
- [ ] Commit Git propre

## Ce qui vient demain

Demain matin (Jour 5), c'est le jour des **présentations orales**. Chaque groupe présente (15-20 min + 5-10 min de questions) :

- L'architecture du pipeline (schéma des flux batch + streaming).
- Les choix techniques et les difficultés rencontrées.
- **Démonstration live** : lancer le DAG Airflow, montrer le dashboard SciPulse, exécuter une recherche full-text.
- Les résultats des tests de qualité (Data Docs GE).
- Les insights découverts et les améliorations envisagées.

**Préparez-vous ce soir** : relisez vos dashboards, préparez quelques requêtes de démonstration marquantes, et testez le mode plein écran de Kibana.
