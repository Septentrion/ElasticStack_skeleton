# Jour 4 — Matin
# Bloc théorique : Orchestration avec Apache Airflow

> **Durée** : 45 minutes  
> **Positionnement** : transversal — l'orchestration coordonne toutes les étapes du cycle de vie  
> **Objectif** : comprendre les concepts fondamentaux d'Airflow, savoir concevoir un DAG, et connaître les bonnes pratiques d'orchestration DataOps

---

## 1. Pourquoi orchestrer ?

### 1.1. Le problème

Jusqu'ici, nous avons exécuté chaque étape du pipeline manuellement, dans le bon ordre :

```
python -m src.transformation.load_to_postgres    # Étape 1
cd dbt && dbt run && dbt test && cd ..            # Étape 2
python -m src.enrichment.enrich_arxiv             # Étape 3
python -m src.quality.validate_arxiv              # Étape 4
```

Cela fonctionne en TP, mais en production c'est intenable :

- **Qui lance les scripts ?** Si c'est un humain, le pipeline ne tourne pas le week-end. Si quelqu'un est malade, le pipeline ne tourne pas du tout.
- **Que se passe-t-il si l'étape 2 échoue ?** L'étape 3 ne doit pas s'exécuter avec des données corrompues. Un humain doit surveiller, détecter l'échec, et relancer. À 3 heures du matin.
- **Comment relancer après un échec partiel ?** Si l'étape 3 échoue mais que les étapes 1 et 2 ont réussi, on veut relancer uniquement l'étape 3 — pas tout depuis le début (ce qui prendrait des heures).
- **Comment savoir ce qui s'est passé ?** Sans logs centralisés, diagnostiquer un problème survenu la semaine dernière est un cauchemar archéologique.

L'orchestration résout tous ces problèmes. Un **orchestrateur** est un système qui planifie, séquence, exécute, surveille et relance les tâches d'un pipeline automatiquement.

### 1.2. L'orchestrateur dans l'architecture DataOps

L'orchestrateur est le **chef d'orchestre** du pipeline. Il ne fait rien lui-même — il dit aux autres quoi faire, dans quel ordre, et il surveille que tout se passe bien.

```
┌─────────────────────────────────────────────────────────────┐
│                      AIRFLOW                                │
│                                                             │
│   ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌─────────┐  │
│   │download │──▶│ validate │──▶│ ingest  │──▶│transform│  │
│   └─────────┘   └──────────┘   └─────────┘   └─────────┘  │
│                                                   │         │
│                                              ┌────▼────┐    │
│                                              │ enrich  │    │
│                                              └────┬────┘    │
│                                              ┌────▼────┐    │
│                                              │validate │    │
│                                              └─────────┘    │
│                                                             │
│   Scheduling · Retry · Alerting · Logging · UI              │
└─────────────────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
     Logstash       PostgreSQL    Elasticsearch
      MinIO           dbt           Python
```

Dans les trois piliers DataOps :

- **Automatisation** : le pipeline s'exécute automatiquement selon un planning, sans intervention humaine.
- **Observabilité** : chaque exécution est loggée, les durées sont mesurées, les échecs déclenchent des alertes.
- **Collaboration** : le DAG (Directed Acyclic Graph) est un schéma visuel que toute l'équipe peut lire, versionné dans Git.

---

## 2. Apache Airflow — concepts fondamentaux

### 2.1. Qu'est-ce qu'Airflow ?

Apache Airflow est un orchestrateur de workflows open-source créé par Airbnb en 2014 et devenu un projet Apache en 2019. C'est le standard de facto pour l'orchestration de pipelines de données [1].

Airflow n'exécute pas les transformations lui-même — il **déclenche** des scripts, des commandes, des API. Son rôle est de garantir que les bonnes tâches s'exécutent dans le bon ordre, au bon moment, et de réagir en cas d'échec.

### 2.2. Le DAG — Directed Acyclic Graph

Le concept central d'Airflow est le **DAG** (graphe orienté acyclique) : un ensemble de tâches reliées par des dépendances.

```python
download >> validate_raw >> ingest >> transform >> enrich >> validate_final
```

**Directed** : les flèches ont un sens (download → validate, pas l'inverse).

**Acyclic** : pas de boucle (une tâche ne peut pas dépendre d'elle-même, directement ou indirectement). C'est ce qui garantit que le pipeline a une fin.

**Graph** : les tâches peuvent avoir des branchements (parallélisme) et des convergences (synchronisation).

Un DAG est défini dans un **fichier Python** — pas dans un fichier YAML ou une interface graphique. C'est du code, versionné dans Git, revue en pull request. C'est un pilier DataOps : *pipeline as code*.

### 2.3. Les Tasks et les Operators

Une **Task** est une unité de travail dans un DAG. Chaque tâche encapsule une action via un **Operator** :

| Operator | Ce qu'il fait | Exemple SciPulse |
|----------|--------------|------------------|
| `BashOperator` | Exécute une commande shell | `dbt run`, `curl`, scripts shell |
| `PythonOperator` | Exécute une fonction Python | Enrichissement NLP, validation GX |
| `EmptyOperator` | Ne fait rien (point de synchronisation) | Jonction entre branches parallèles |

Il existe des dizaines d'opérateurs spécialisés (pour S3, GCS, Spark, Kubernetes…), mais ces trois couvrent 90% des cas. La philosophie Airflow est que l'opérateur déclenche le travail — le travail lui-même est dans le script externe [1].

### 2.4. Le scheduling

Chaque DAG a un `schedule_interval` qui définit la fréquence d'exécution :

| Expression | Fréquence |
|------------|-----------|
| `None` | Uniquement par déclenchement manuel |
| `"@daily"` | Tous les jours à minuit |
| `"@hourly"` | Toutes les heures |
| `"*/5 * * * *"` | Toutes les 5 minutes (syntaxe cron) |
| `"0 6 * * 1"` | Tous les lundis à 6h |

Dans SciPulse, nous avons deux DAGs avec des fréquences différentes :

- `scipulse_arxiv_pipeline` : `schedule_interval=None` (manuel ou quotidien en production) — le pipeline batch n'a pas besoin de tourner toutes les 5 minutes.
- `scipulse_hn_poller` : `schedule_interval="*/5 * * * *"` — le poller HN tourne toutes les 5 minutes pour capturer le flux en quasi-temps réel.

### 2.5. Retry et gestion des échecs

Chaque tâche peut être configurée avec des paramètres de résilience :

```python
default_args = {
    "retries": 3,                          # Nombre de tentatives
    "retry_delay": timedelta(minutes=5),   # Délai entre tentatives
    "retry_exponential_backoff": True,     # Backoff exponentiel
    "email_on_failure": True,              # Alerter par email
    "execution_timeout": timedelta(hours=2), # Timeout global
}
```

Si une tâche échoue après tous ses retries, le DAG s'arrête et les tâches en aval ne s'exécutent pas. C'est le **circuit breaker** DataOps — les données corrompues ne se propagent pas.

### 2.6. XCom — communication entre tâches

Les **XComs** (cross-communications) permettent aux tâches de se transmettre de petites quantités de données :

```python
# Tâche A : pousser un résultat
context["ti"].xcom_push(key="doc_count", value=100000)

# Tâche B : récupérer le résultat
count = context["ti"].xcom_pull(task_ids="task_a", key="doc_count")
```

Les XComs sont stockés dans la base de données Airflow (PostgreSQL). Ils sont conçus pour de petites valeurs (nombres, chaînes, listes courtes) — pas pour des DataFrames ou des fichiers. Pour les données volumineuses, on passe par un stockage partagé (MinIO, Elasticsearch, PostgreSQL).

### 2.7. L'architecture d'Airflow

```
┌───────────────────────────────────────────────────────┐
│                      AIRFLOW                          │
│                                                       │
│  ┌──────────────┐   ┌────────────┐   ┌────────────┐  │
│  │  WEBSERVER   │   │ SCHEDULER  │   │  EXECUTOR   │  │
│  │  (UI web)    │   │ (planning) │   │  (workers)  │  │
│  └──────┬───────┘   └──────┬─────┘   └──────┬─────┘  │
│         │                  │                │         │
│         └──────────┬───────┘                │         │
│                    │                        │         │
│              ┌─────▼──────┐                 │         │
│              │ METADATA   │                 │         │
│              │ DATABASE   │◀────────────────┘         │
│              │ (Postgres) │                           │
│              └────────────┘                           │
│                                                       │
│  DAGs lus depuis : airflow/dags/*.py                  │
└───────────────────────────────────────────────────────┘
```

Quatre composants :

- **Scheduler** : lit les fichiers DAG, détermine quelles tâches doivent s'exécuter, et les soumet à l'executor. C'est le cerveau d'Airflow.
- **Executor** : exécute les tâches. Plusieurs types : `LocalExecutor` (processus locaux, notre choix en TP), `CeleryExecutor` (workers distribués), `KubernetesExecutor` (un pod par tâche).
- **Webserver** : l'interface web (http://localhost:8080). Permet de visualiser les DAGs, suivre les exécutions, consulter les logs, et déclencher des runs manuels.
- **Metadata database** : stocke l'état de chaque DAG, chaque tâche, chaque exécution. C'est la mémoire d'Airflow. Dans SciPulse, c'est le même PostgreSQL que celui de dbt (mais une base séparée : `airflow`).

---

## 3. Bonnes pratiques DataOps pour l'orchestration

### 3.1. DAGs versionnés dans Git

Les fichiers DAG sont du code Python — ils doivent être versionnés, revus en PR, et testés. Dans SciPulse, les DAGs sont dans `airflow/dags/`, inclus dans le dépôt Git du projet.

### 3.2. Idempotence des tâches

Chaque tâche doit être re-exécutable sans effet de bord. C'est ce qui permet de relancer une tâche individuelle après un échec sans corrompre les données. Nous l'avons assuré dans chaque script du projet (document_id dans ES, DROP+CREATE dans PG, upsert dans le poller HN).

### 3.3. Tâches atomiques et focalisées

Une tâche doit faire **une seule chose**. Si la tâche « ingest_and_transform » échoue, on ne sait pas si c'est l'ingestion ou la transformation qui a échoué. Avec deux tâches séparées, le diagnostic est immédiat.

### 3.4. `depends_on_past: False`

Par défaut, Airflow peut conditionner l'exécution d'une tâche à la réussite de la même tâche dans le run précédent. En DataOps, c'est généralement indésirable : si le run de lundi a échoué, on veut que celui de mardi puisse s'exécuter quand même (les données de mardi ne dépendent pas de celles de lundi).

### 3.5. Sensors pour le déclenchement événementiel

Un **Sensor** est un type de tâche qui attend qu'une condition soit remplie avant de continuer :

```python
from airflow.sensors.filesystem import FileSensor

wait_for_file = FileSensor(
    task_id="wait_for_arxiv_dump",
    filepath="/data/arxiv-raw/*.json",
    poke_interval=60,       # Vérifier toutes les 60 secondes
    timeout=3600,           # Abandonner après 1 heure
)
```

Cas d'usage : attendre qu'un fichier apparaisse dans MinIO, qu'une API soit disponible, ou qu'un autre DAG ait terminé. C'est le pattern « event-driven orchestration » — plus élégant qu'un cron fixe quand le timing est imprévisible.

---

## 4. Conception des DAGs SciPulse

### 4.1. Deux DAGs pour deux patterns

Notre architecture utilise deux DAGs distincts parce que les deux sources de données ont des rythmes différents :

| DAG | Pattern | Fréquence | Tâches |
|-----|---------|-----------|--------|
| `scipulse_arxiv_pipeline` | Batch | Manuel / quotidien | 6 tâches séquentielles |
| `scipulse_hn_poller` | Micro-batch | Toutes les 5 minutes | 3 tâches séquentielles |

**Pourquoi pas un seul DAG ?** Parce que les deux pipelines sont indépendants en timing : le batch ArXiv tourne une fois par jour (ou sur demande), tandis que le poller HN tourne en continu. Les coupler dans un seul DAG forcerait le poller à attendre la fin du batch ArXiv — c'est une perte de réactivité.

### 4.2. DAG ArXiv — le pipeline batch complet

```
download_arxiv_dump
        │
        ▼
validate_raw_arxiv        ← Checkpoint GE (données brutes)
        │
        ▼
ingest_arxiv_logstash     ← Déclencher Logstash
        │
        ▼
transform_dbt             ← dbt run + dbt test
        │
        ▼
enrich_arxiv_python       ← TF-IDF + croisement HN
        │
        ▼
validate_enriched         ← Checkpoint GE (données enrichies)
```

Chaque flèche est une dépendance : si une tâche échoue, les suivantes ne s'exécutent pas.

### 4.3. DAG HN — le poller micro-batch

```
poll_hn_api
     │
     ▼
detect_arxiv_links
     │
     ▼
update_arxiv_hn_scores
```

Exécuté toutes les 5 minutes. `max_active_runs=1` garantit qu'un seul run est actif à la fois — si un cycle prend plus de 5 minutes, le suivant attend.

---

## 5. Ce qui vient dans le TP

Le TP met en pratique ces concepts :

1. **Ajout d'Airflow** au `docker-compose.yml` (déjà fait dans le starter kit — vérification).
2. **Complétion du DAG ArXiv** : remplacer les `# TODO` par de vrais appels aux scripts que nous avons écrits aux Jours 1-3.
3. **Complétion du DAG HN** : connecter le poller et la détection de liens.
4. **Test des DAGs** : trigger manuel, visualisation dans l'UI Airflow, inspection des logs.
5. **Simulation d'échec** : introduire volontairement une erreur pour observer le comportement de retry et l'arrêt du DAG.

---

## Bibliographie

### Ouvrages de référence

[1] Harenslak, B., & de Ruiter, J. (2021). *Data Pipelines with Apache Airflow*. Manning Publications.  
L'ouvrage de référence sur Airflow. Les chapitres 1-3 couvrent les concepts fondamentaux (DAGs, operators, scheduling). Les chapitres 7-8 traitent des tests et du déploiement. Le chapitre 10 couvre l'intégration avec les systèmes externes (bases de données, API, cloud). Directement applicable au TP.

[2] Apache Airflow. (2024). *Airflow Documentation*. https://airflow.apache.org/docs/  
La documentation officielle est exhaustive : concepts, tutoriels, référence des opérateurs, guides de déploiement. Les sections « Concepts » et « How-to Guides » sont les plus utiles pour le cours. La section « Best Practices » formalise les principes que nous appliquons.

[3] Reis, J., & Housley, M. (2022). *Fundamentals of Data Engineering*. O'Reilly Media.  
Le chapitre 9 (Orchestration) positionne Airflow dans l'écosystème et le compare aux alternatives (Prefect, Dagster, Mage). La discussion « orchestration vs. choreography » éclaire le choix entre un orchestrateur centralisé (Airflow) et une approche événementielle décentralisée.

[4] Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly Media.  
Le chapitre 10 (Batch Processing) discute les graphes de dépendances de tâches dans le contexte de MapReduce et des systèmes de workflow. Les concepts de linéarité, d'idempotence et de reproductibilité sont directement applicables à la conception de DAGs Airflow.

### Ressources complémentaires

[5] Apache Airflow. (2024). *Airflow Operators Reference*. https://airflow.apache.org/docs/apache-airflow/stable/howto/operator/index.html  
Catalogue complet des opérateurs intégrés (BashOperator, PythonOperator, sensors, etc.) avec exemples de code. Indispensable pendant le TP.

[6] Astronomer. (2024). *Airflow Best Practices*. https://www.astronomer.io/guides/  
Astronomer (la société derrière la distribution commerciale d'Airflow) publie des guides de bonnes pratiques exceptionnellement bien écrits. Les articles « DAG Writing Best Practices », « Testing Airflow DAGs », et « Managing Dependencies » sont directement applicables.

[7] DataOps Manifesto. https://dataopsmanifesto.org  
Le principe 11 (« Automate as many stages of the analytics process as possible ») et le principe 4 (« Orchestrate ») sont le fondement philosophique de l'orchestration. Le principe 8 (« Monitor quality and performance ») motive l'intégration des checkpoints de qualité dans les DAGs.

[8] Apache Airflow. (2024). *XComs Documentation*. https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html  
Documentation des XComs : limites de taille, sérialisation, backends custom. L'avertissement sur la taille maximale des XComs (variable selon le backend) est important pour éviter les mauvaises surprises.

[9] Beauchemin, M. (2015). « The Rise of the Data Engineer ». *The Airflow Blog*.  
Article fondateur écrit par le créateur d'Airflow chez Airbnb, qui décrit les motivations derrière la création d'Airflow : le besoin d'un orchestrateur programmatique (Python, pas YAML), versionnable, testable, et adapté aux workflows de données.
