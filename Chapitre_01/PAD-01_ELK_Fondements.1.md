# Jour 1 — Matin
# Fondations : DataOps, environnement et projet SciPulse

> **Durée** : 3h30  
> **Découpage** : Bloc théorique (1h) + TP guidé (2h30)

---

# PARTIE 1 — BLOC THÉORIQUE (1h)

# DataOps & cycle de vie de la donnée

---

## 1. Pourquoi DataOps ?

### Le constat : la « dette de données »

La plupart des projets data échouent non pas à cause des algorithmes, mais à cause de **l'ingénierie autour des données**. Les symptômes sont récurrents :

- Un pipeline qui fonctionne en local mais casse en production.
- Des données corrompues qui ne sont détectées que des semaines plus tard.
- Un data scientist qui attend 3 jours qu'un ingénieur lui prépare un dataset.
- Personne ne sait quelle version du code a produit le dashboard de lundi dernier.
- Un hotfix en production fait par copier-coller, sans tests, sans review.

Ces problèmes ont un nom : c'est la **dette de données**, l'équivalent data de la dette technique logicielle. Et tout comme le monde du développement a répondu à sa dette technique avec DevOps, le monde de la donnée a besoin de **DataOps**.

### Définition

> **DataOps** est l'application des principes Agile et DevOps au cycle de vie des données.  
> L'objectif est de **réduire le temps de mise en valeur des données** tout en **augmentant la qualité et la fiabilité** des pipelines.

Le terme a été formalisé en 2018 par le *DataOps Manifesto* (dataopsmanifesto.org), qui s'inspire directement du Manifeste Agile et des principes DevOps.

### Ce que DataOps n'est PAS

Clarifions quelques confusions fréquentes :

- **DataOps ≠ DevOps pour la data.** C'est plus que ça : DevOps se concentre sur le déploiement de logiciels. DataOps ajoute la dimension spécifique des données — qualité, lignage, schéma, volumétrie, fraîcheur.
- **DataOps ≠ un outil.** Aucun outil ne « fait du DataOps ». C'est un ensemble de pratiques, de principes et de culture. Les outils les outillent.
- **DataOps ≠ MLOps.** MLOps s'occupe du cycle de vie des modèles de machine learning. DataOps s'occupe du cycle de vie des données en amont. Les deux sont complémentaires.

---

## 2. Les trois piliers du DataOps

Le DataOps repose sur trois piliers fondamentaux. Chaque outil et chaque pratique que nous verrons dans ce cours s'inscrit dans l'un de ces piliers.

### Pilier 1 — Automatisation

**Principe** : tout ce qui peut être automatisé doit l'être. Un pipeline exécuté manuellement est un pipeline qui tombera en panne un vendredi soir.

**Pratiques concrètes** :

- **Infrastructure as Code (IaC)** : l'environnement entier est décrit dans des fichiers (Docker Compose, Terraform, Ansible). Un nouveau développeur doit pouvoir lancer la stack complète en une commande.
- **Pipeline as Code** : les pipelines de données sont définis en code (Airflow DAGs, configs Logstash), versionnés dans Git, revus en pull request.
- **CI/CD pour la data** : chaque commit déclenche des tests automatiques sur les transformations, les schémas, les requêtes.
- **Orchestration** : les tâches sont planifiées, séquencées, avec gestion des dépendances, des retries et des alertes (Airflow, Prefect, Dagster).

**Dans notre projet** : Docker Compose (IaC), Airflow (orchestration), Git (versioning), Logstash configs (pipeline as code).

### Pilier 2 — Observabilité

**Principe** : on ne peut pas améliorer ce qu'on ne mesure pas. Un pipeline de données est une boîte noire tant qu'on ne l'instrumente pas.

**Pratiques concrètes** :

- **Logging structuré** : chaque étape du pipeline produit des logs exploitables (pas juste des `print()`).
- **Métriques** : nombre de documents ingérés, durée d'exécution, taux d'erreur, fraîcheur des données.
- **Alerting** : notification automatique quand un seuil est dépassé (volume anormalement bas, taux d'erreur en hausse).
- **Lignage (lineage)** : savoir d'où vient chaque donnée, quelles transformations elle a subies, et quand.
- **Data quality monitoring** : vérification continue que les données respectent les contrats de qualité.

**Dans notre projet** : Kibana dashboards (monitoring), Filebeat (collecte de logs), Great Expectations (qualité), Elasticsearch index `pipeline-logs` (métriques).

### Pilier 3 — Collaboration

**Principe** : les silos entre équipes (data engineers, data scientists, analystes, ops) sont l'ennemi de la vélocité.

**Pratiques concrètes** :

- **Git comme source de vérité** : tout le monde travaille sur le même dépôt, avec des branches, des reviews, et un historique.
- **Documentation as code** : la documentation est générée automatiquement depuis le code (dbt docs, Great Expectations Data Docs, Swagger/OpenAPI).
- **Environnements reproductibles** : chaque développeur a le même environnement grâce à Docker. « Ça marche sur ma machine » n'est plus une excuse.
- **Self-service** : les analystes peuvent explorer les données sans attendre qu'un ingénieur leur prépare un export.

**Dans notre projet** : Git (versioning), dbt docs (documentation), Kibana (self-service exploration), Docker Compose (environnement reproductible).

---

## 3. Le cycle de vie de la donnée

Tout pipeline de données, qu'il traite 100 lignes ou 100 milliards, suit le même cycle de vie. Comprendre ce cycle est essentiel pour savoir **où intervient chaque outil** de notre stack.

### Les 6 étapes

```
  ┌──────────┐    ┌───────────┐    ┌──────────────┐
  │ INGESTION│───▶│ STOCKAGE  │───▶│TRANSFORMATION│
  └──────────┘    └───────────┘    └──────────────┘
                                          │
                                          ▼
  ┌───────────┐   ┌───────────┐    ┌──────────────┐
  │MONITORING │◀──│  SERVING  │◀───│ INDEXATION    │
  └───────────┘   └───────────┘    └──────────────┘
```

#### Étape 1 — Ingestion

**Quoi** : collecter les données depuis les sources et les amener dans le système.

**Patterns** :

| Pattern | Description | Latence | Exemple |
|---------|------------|---------|---------|
| Batch | Traitement par lots, à intervalle régulier | Minutes à heures | Dump ArXiv quotidien |
| Micro-batch | Petits lots très fréquents | Secondes à minutes | Polling API HN toutes les 60s |
| Streaming | Traitement événement par événement | Millisecondes | Kafka, Kinesis (hors scope TP) |

**Outils dans notre stack** :
- **Logstash** : ingestion batch du dump ArXiv (plugin `file`, codec `json`).
- **Python + requests** : polling micro-batch de l'API Hacker News.
- **Filebeat** : collecte de fichiers de logs (complément léger à Logstash).
- **MinIO** : zone de landing (staging area) pour les fichiers bruts avant traitement.

**Bonne pratique DataOps** : toujours conserver les données brutes (raw) dans une zone séparée. On ne transforme jamais en place — on crée une copie enrichie. C'est le principe d'**immutabilité des données sources**.

#### Étape 2 — Stockage

**Quoi** : persister les données de manière fiable et accessible.

**Patterns** :

| Couche | Usage | Technologie (notre stack) |
|--------|-------|--------------------------|
| Landing zone | Données brutes, telles que reçues | MinIO (S3-compatible) |
| Base opérationnelle | Stockage structuré pour requêtes | PostgreSQL |
| Moteur de recherche | Indexation full-text et analytique | Elasticsearch |

**Bonne pratique DataOps** : séparer les couches de stockage. Les données brutes ne sont jamais dans la même base que les données transformées. C'est le principe du **data lakehouse** : un lac de données (MinIO) + un entrepôt structuré (PostgreSQL) + un moteur de recherche (Elasticsearch).

#### Étape 3 — Transformation

**Quoi** : nettoyer, enrichir, structurer les données pour les rendre exploitables.

**Deux approches** :

| Approche | Description | Quand l'utiliser |
|----------|-------------|------------------|
| **ETL** (Extract-Transform-Load) | Transformer avant de charger | Données volumineuses, transformation lourde |
| **ELT** (Extract-Load-Transform) | Charger d'abord, transformer ensuite | Moteur de destination puissant (BigQuery, Snowflake, ES) |

**Outils dans notre stack** :
- **dbt** : transformations SQL versionnées dans PostgreSQL (ELT).
- **Python (Pandas/Polars)** : transformations programmatiques (nettoyage, NLP, enrichissement).
- **Logstash filters** : transformations à l'ingestion (parsing, renommage, conversion de types).

**Bonne pratique DataOps** : chaque transformation doit être **idempotente** — l'exécuter une fois ou dix fois produit le même résultat. C'est ce qui permet de relancer un pipeline en toute sécurité après un échec.

#### Étape 4 — Indexation

**Quoi** : organiser les données pour permettre des recherches rapides.

C'est le cœur d'**Elasticsearch** dans notre stack. L'indexation ne se résume pas à « mettre les données dans ES » — c'est un acte de **modélisation** :

- Choisir le bon type pour chaque champ (`text` vs `keyword`).
- Configurer les analyseurs (stemming, synonymes, stopwords).
- Définir les multi-fields (un champ searchable ET aggregable).
- Optimiser pour les requêtes attendues.

Nous détaillerons tout cela au Jour 2.

#### Étape 5 — Serving (restitution)

**Quoi** : mettre les données à disposition des utilisateurs finaux.

**Canaux de restitution** :

- **Dashboards** : Kibana pour l'exploration interactive.
- **API** : module Python `search_service.py` pour intégrer la recherche dans une application.
- **Rapports** : exports programmés (dbt docs, Data Docs).

#### Étape 6 — Monitoring (observabilité)

**Quoi** : surveiller en continu la santé du pipeline et la qualité des données.

- **Pipeline monitoring** : les tâches Airflow s'exécutent-elles ? Combien de temps prennent-elles ?
- **Data quality monitoring** : les données respectent-elles les contrats ? (Great Expectations)
- **Infrastructure monitoring** : Elasticsearch est-il en bonne santé ? Combien de documents par index ?

---

## 4. Panorama de la stack SciPulse

Chaque outil du cours a un rôle précis dans le cycle de vie. Voici comment ils s'articulent :

```
┌─────────────────────────────────────────────────────────────────────┐
│                            DataOps                                  │
│         Git (versioning) · Docker (reproductibilité)                │
│         Pytest (tests code) · Great Expectations (tests data)       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  INGESTION        STOCKAGE       TRANSFORMATION    SERVING          │
│  ─────────        ────────       ──────────────    ───────          │
│  Logstash         MinIO          dbt (SQL)         Kibana           │
│  Python           PostgreSQL     Python/Pandas     Python API       │
│  Filebeat         Elasticsearch  Logstash filters                   │
│                                                                     │
│  ORCHESTRATION                   MONITORING                         │
│  ──────────────                  ──────────                         │
│  Airflow                         Kibana dashboards                  │
│                                  Filebeat → ES                      │
│                                  Watcher (alertes)                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Présentation du projet SciPulse

### Le pitch

Nous allons construire **SciPulse**, une plateforme de veille intelligente qui croise deux sources de données :

- **ArXiv** : 2 millions d'articles scientifiques (titres, abstracts, auteurs, catégories). Source batch — un dump JSON massif.
- **Hacker News** : le flux temps réel des posts et commentaires de la communauté tech. Source streaming — polling de l'API Firebase.

Le projet est conçu pour couvrir **toutes les étapes du cycle de vie** et **tous les piliers DataOps** :

| Pilier DataOps | Manifestation dans SciPulse |
|----------------|----------------------------|
| Automatisation | Docker Compose lance tout en une commande. Airflow orchestre le pipeline. Git versionne tout. |
| Observabilité | Kibana dashboard de monitoring. Great Expectations valide la qualité. Logs centralisés. |
| Collaboration | Dépôt Git partagé. dbt docs auto-générées. Kibana en self-service pour l'exploration. |

### Les sources de données

#### ArXiv (batch)

Le dataset ArXiv Kaggle contient les métadonnées de plus de 2 millions de publications scientifiques. Voici un exemple d'enregistrement :

```json
{
  "id": "2301.07041",
  "title": "A Comprehensive Survey of AI-Generated Content (AIGC)",
  "abstract": "Recently, AI-generated content (AIGC) has received increasing attention...",
  "authors": "Yihan Cao, Siyu Li, Yixin Liu, Zhiling Yan, ...",
  "categories": "cs.AI cs.CL cs.LG",
  "update_date": "2023-02-07",
  "doi": "10.1007/s10462-023-10539-y"
}
```

Points d'intérêt :

- Les **abstracts** sont des blocs de texte de 100 à 500 mots — parfaits pour la fouille de texte Elasticsearch.
- Les **catégories** sont hiérarchiques : `cs.AI` = Computer Science > Artificial Intelligence. Un article peut avoir plusieurs catégories.
- Les **auteurs** sont une chaîne de texte brute qu'il faudra parser et normaliser.
- La **date** permet des analyses temporelles sur 30 ans de publications.

#### Hacker News (streaming)

L'API Hacker News est publique, sans authentification, et très permissive. Elle expose le flux temps réel des posts et commentaires :

```json
{
  "id": 38792160,
  "type": "story",
  "by": "dhouston",
  "time": 1702396800,
  "title": "Show HN: A new way to explore ArXiv papers",
  "url": "https://arxiv.org/abs/2312.12345",
  "score": 245,
  "descendants": 67,
  "kids": [38792200, 38792350, ...]
}
```

Points d'intérêt :

- Le champ `url` peut contenir un lien vers un article ArXiv → **enrichissement croisé**.
- La relation `kids` (commentaires d'un post) permet d'explorer les **relations parent-child** dans Elasticsearch.
- Le `score` et `descendants` sont des métriques de popularité → **function_score** pour pondérer la pertinence.
- Le `type` peut être `story`, `comment`, `job`, `poll` → facettes et agrégations.

### Architecture cible

```
ArXiv (batch, dump Kaggle)          Hacker News (micro-batch, API Firebase)
        │                                       │
        ▼                                       ▼
   MinIO (landing)                     Python hn_poller.py
   bucket: arxiv-raw/                           │
        │                                       │
        ▼                                       │
   Logstash (parse JSON)                        │
        │                                       │
        ▼                                       ▼
┌─────────────────── Elasticsearch ───────────────────┐
│                                                     │
│  arxiv-papers-raw    (données brutes Logstash)      │
│  arxiv-papers        (mapping optimisé full-text)   │
│  hn-items            (posts + comments, join field) │
│  arxiv-hn-links      (table de liaison)             │
│  pipeline-logs       (observabilité)                │
│                                                     │
└──────────┬──────────────────────────────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
  Kibana      PostgreSQL + dbt
  (dashboard)  (transformations SQL)
```

### Planning du projet sur 4 jours

| Jour | Ce qu'on construit |
|------|--------------------|
| J1 | Environnement Docker + ingestion batch ArXiv (Logstash) |
| J2 | Mapping ES optimisé + ingestion HN + tests de qualité |
| J3 | Transformations dbt + enrichissement NLP + fouille de texte ES |
| J4 | Orchestration Airflow + dashboard Kibana + monitoring |
| J5 | Présentations orales |

---

# PARTIE 2 — TRAVAUX PRATIQUES (2h30)

# Mise en place de l'environnement SciPulse

---

## Objectif du TP

À la fin de cette session, vous aurez :

- Un dépôt Git initialisé avec la structure du projet.
- Une stack complète lancée via Docker Compose (Elasticsearch, Logstash, Kibana, Airflow, PostgreSQL, MinIO).
- Vérifié que chaque service est accessible.
- Téléchargé un subset du dump ArXiv et déposé les données dans MinIO.
- Écrit votre premier script Python d'interaction avec MinIO.

---

## Étape 1 — Initialiser le dépôt Git (20 min)

### 1.1. Cloner le starter kit

Le formateur vous fournit un starter kit contenant la structure de base. Clonez-le et explorez l'arborescence :

```bash
git clone <url-du-repo> scipulse
cd scipulse
```

### 1.2. Explorer la structure

Prenez 5 minutes pour parcourir l'arborescence :

```
scipulse/
├── docker-compose.yml       ← Stack complète
├── requirements.txt         ← Dépendances Python
├── Makefile                 ← Raccourcis (make up, make test…)
├── .env.example             ← Variables d'environnement
├── .gitignore
├── README.md
│
├── docker/                  ← Configs Docker par service
│   ├── logstash/
│   │   ├── config/logstash.yml
│   │   └── pipeline/arxiv.conf
│   └── postgres/
│       └── init.sql
│
├── airflow/                 ← DAGs et plugins Airflow
│   └── dags/
│       ├── dag_arxiv_pipeline.py
│       └── dag_hn_poller.py
│
├── src/                     ← Code source Python
│   ├── ingestion/
│   │   └── hn_poller.py
│   ├── search/
│   │   └── search_service.py
│   └── utils/
│       └── mappings.py
│
├── dbt/                     ← Projet dbt
├── tests/                   ← Tests Pytest
├── data/                    ← Données (non versionnées)
├── notebooks/               ← Exploration Jupyter
└── docs/                    ← Documentation
```

**Question à se poser** : quel pilier DataOps est déjà en action juste avec cette structure ? *(Réponse : collaboration — structure partagée, Git, .gitignore, README.)*

### 1.3. Configurer l'environnement

```bash
# Copier le fichier d'environnement
cp .env.example .env

# Créer un environnement virtuel Python
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### 1.4. Créer votre branche de travail

```bash
git checkout -b feature/setup-<votre-nom>
```

**Bonne pratique DataOps** : ne jamais committer directement sur `main`. Toujours travailler sur une branche et faire une pull request. Même en TP, on prend les bonnes habitudes.

---

## Étape 2 — Comprendre le docker-compose.yml (20 min)

Avant de lancer quoi que ce soit, prenons le temps de **lire et comprendre** le fichier `docker-compose.yml`. C'est un exercice DataOps fondamental : on ne lance jamais une stack qu'on ne comprend pas.

### 2.1. Lecture guidée

Ouvrez `docker-compose.yml` dans votre éditeur. Identifions chaque service :

| Service | Image | Ports | Rôle |
|---------|-------|-------|------|
| `elasticsearch` | `elastic/elasticsearch:8.13.4` | 9200 | Moteur de recherche et stockage |
| `logstash` | `elastic/logstash:8.13.4` | — | Ingestion et parsing des données |
| `kibana` | `elastic/kibana:8.13.4` | 5601 | Interface d'exploration |
| `postgres` | `postgres:16-alpine` | 5432 | Backend Airflow + entrepôt dbt |
| `minio` | `minio/minio:latest` | 9000, 9001 | Stockage objet (landing zone) |
| `minio-init` | `minio/mc:latest` | — | Création des buckets au démarrage |
| `airflow-init` | `apache/airflow:2.9.3` | — | Initialisation de la DB Airflow |
| `airflow-webserver` | `apache/airflow:2.9.3` | 8080 | Interface web Airflow |
| `airflow-scheduler` | `apache/airflow:2.9.3` | — | Planificateur de tâches |

### 2.2. Points d'attention à discuter

**Les healthchecks** : Elasticsearch déclare un healthcheck (`curl -f http://localhost:9200/_cluster/health`). Les services qui en dépendent (`depends_on: elasticsearch: condition: service_healthy`) ne démarrent qu'une fois ES prêt. Sans ça, Logstash et Kibana planteraient au démarrage parce qu'ES n'est pas encore prêt à accepter des connexions.

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 10
```

**Les volumes nommés** : `es-data`, `pg-data` et `minio-data` sont des volumes Docker persistants. Les données survivent à un `docker compose down` mais pas à un `docker compose down -v` (qui supprime aussi les volumes).

**Le réseau** : tous les services sont sur le même réseau Docker `scipulse`. Ils se voient par leur nom de service (ex. : `http://elasticsearch:9200` depuis Logstash).

**La sécurité désactivée** : `xpack.security.enabled=false` sur ES et Kibana. En production, c'est évidemment interdit ! En TP, ça simplifie considérablement la configuration.

**L'ancre YAML `&airflow-common`** : c'est une technique DRY (Don't Repeat Yourself) pour factoriser la config commune entre les 3 services Airflow. Notez le `<<: *airflow-common` qui « hérite » de l'ancre.

**Le `minio-init`** : ce conteneur éphémère s'exécute une fois au démarrage pour créer les buckets (`arxiv-raw`, `hn-raw`, `processed`), puis s'arrête. C'est un pattern courant pour l'initialisation d'infrastructure.

### 2.3. Le fichier init.sql

PostgreSQL exécute automatiquement les scripts dans `/docker-entrypoint-initdb.d/` au premier démarrage. Notre `init.sql` crée une base `scipulse` séparée de la base `airflow`, avec deux schémas (`staging` et `marts`) pour dbt :

```sql
CREATE USER scipulse WITH PASSWORD 'scipulse';
CREATE DATABASE scipulse OWNER scipulse;

\c scipulse
CREATE SCHEMA IF NOT EXISTS staging AUTHORIZATION scipulse;
CREATE SCHEMA IF NOT EXISTS marts   AUTHORIZATION scipulse;
```

---

## Étape 3 — Lancer la stack (20 min)

### 3.1. Démarrage

```bash
# Depuis la racine du projet
docker compose up -d
```

Le premier lancement est long (téléchargement des images, ~5 Go au total). Les fois suivantes seront quasi-instantanées.

Suivez la progression :

```bash
# Voir l'état de tous les conteneurs
docker compose ps

# Suivre les logs en temps réel (Ctrl+C pour quitter)
docker compose logs -f
```

### 3.2. Vérification de chaque service

Attendez que tous les services soient `healthy` ou `running`, puis vérifiez un par un :

#### Elasticsearch

```bash
# Santé du cluster
curl -s http://localhost:9200/_cluster/health?pretty
```

Vous devez voir :

```json
{
  "cluster_name": "scipulse-cluster",
  "status": "green",
  "number_of_nodes": 1,
  ...
}
```

Le statut doit être `green` (ou `yellow` en single-node, ce qui est normal).

```bash
# Version et infos
curl -s http://localhost:9200
```

#### Kibana

Ouvrez http://localhost:5601 dans votre navigateur. L'interface Kibana doit s'afficher.

Naviguez vers **Dev Tools** (menu gauche > Management > Dev Tools). C'est ici que vous écrirez vos requêtes Elasticsearch :

```
GET _cluster/health
```

Cliquez sur le bouton ▶ pour exécuter. Vous devez obtenir la même réponse que `curl`.

#### MinIO

Ouvrez http://localhost:9001 (console d'administration).

Identifiants : `minioadmin` / `minioadmin`.

Vérifiez que les 3 buckets ont été créés automatiquement :
- `arxiv-raw`
- `hn-raw`
- `processed`

Vous pouvez aussi vérifier en ligne de commande :

```bash
# Depuis le conteneur minio-init (s'il est encore là) ou en installant mc localement
docker run --rm --network=scipulse minio/mc alias set local http://minio:9000 minioadmin minioadmin && mc ls local/
```

#### PostgreSQL

```bash
# Connexion à la base scipulse
docker exec -it scipulse-postgres psql -U scipulse -d scipulse -c "\dn"
```

Vous devez voir les schémas `public`, `staging`, et `marts`.

#### Airflow

Ouvrez http://localhost:8080.

Identifiants : `admin` / `admin`.

Vous devez voir les deux DAGs :
- `scipulse_arxiv_pipeline` (pausé)
- `scipulse_hn_poller` (pausé)

Ne les activez pas encore — nous les utiliserons au Jour 4.

### 3.3. Résumé des URLs

| Service | URL | Identifiants |
|---------|-----|-------------|
| Elasticsearch | http://localhost:9200 | — |
| Kibana | http://localhost:5601 | — |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Airflow | http://localhost:8080 | admin / admin |
| PostgreSQL | localhost:5432 | scipulse / scipulse |

### 3.4. Dépannage courant

| Problème | Cause probable | Solution |
|----------|---------------|----------|
| ES ne démarre pas | RAM insuffisante | Allouer ≥ 8 Go à Docker Desktop |
| `max virtual memory areas` | Limite système Linux | `sudo sysctl -w vm.max_map_count=262144` |
| Port déjà utilisé | Un autre service écoute | `docker compose down` puis vérifier `lsof -i :9200` |
| Airflow init échoue | DB pas encore prête | `docker compose restart airflow-init` |
| MinIO buckets manquants | Init trop rapide | `docker compose restart minio-init` |

---

## Étape 4 — Préparer les données ArXiv (30 min)

### 4.1. Télécharger le dataset

Le dump complet ArXiv fait ~3.5 Go. Pour le TP, nous utiliserons un **subset** de ~100 000 articles filtrés sur les catégories Computer Science (`cs.*`) et Machine Learning (`stat.ML`).

**Option A — Dataset Kaggle (recommandé)** :

Si vous avez un compte Kaggle et le CLI installé :

```bash
pip install kaggle
kaggle datasets download -d Cornell-University/arxiv -p data/
```

**Option B — Subset pré-préparé par le formateur** :

Le formateur met à disposition un fichier `arxiv-cs-subset-100k.json` sur un serveur local ou un drive partagé :

```bash
# Adapter l'URL fournie par le formateur
curl -o data/arxiv-raw/arxiv-cs-subset-100k.json <URL>
```

**Option C — Générer le subset soi-même** :

Si vous avez le dump complet, filtrez-le avec un script Python :

```python
"""Extraction d'un subset CS/ML depuis le dump ArXiv complet."""
import json

INPUT  = "data/arxiv-metadata-oai-snapshot.json"
OUTPUT = "data/arxiv-raw/arxiv-cs-subset-100k.json"
MAX    = 100_000

count = 0
with open(INPUT, "r") as fin, open(OUTPUT, "w") as fout:
    for line in fin:
        article = json.loads(line)
        cats = article.get("categories", "")
        # Garder uniquement CS et stat.ML
        if any(c.startswith("cs.") or c == "stat.ML" for c in cats.split()):
            fout.write(line)
            count += 1
            if count >= MAX:
                break

print(f"✅ {count} articles extraits → {OUTPUT}")
```

### 4.2. Inspecter les données

Avant de charger quoi que ce soit, **regardons les données**. C'est un réflexe DataOps : ne jamais ingérer à l'aveugle.

```bash
# Nombre de lignes
wc -l data/arxiv-raw/arxiv-cs-subset-100k.json

# Premiers articles
head -3 data/arxiv-raw/arxiv-cs-subset-100k.json | python -m json.tool
```

Observez et notez :

- Les champs disponibles.
- Le format du champ `authors` (chaîne brute vs. JSON structuré ?).
- La longueur typique d'un abstract.
- Le format des dates.
- Les catégories (mono vs. multi-valuées).

**Exercice** : Combien de catégories uniques contient le subset ?

```bash
cat data/arxiv-raw/arxiv-cs-subset-100k.json \
  | python -c "
import sys, json
cats = set()
for line in sys.stdin:
    art = json.loads(line)
    for c in art.get('categories', '').split():
        cats.add(c)
print(f'{len(cats)} catégories uniques')
for c in sorted(cats)[:20]:
    print(f'  {c}')
"
```

---

## Étape 5 — Charger les données dans MinIO (30 min)

### 5.1. Pourquoi MinIO ?

En production, les données brutes arrivent rarement directement dans le moteur de traitement. Elles atterrissent d'abord dans une **landing zone** — un stockage objet de type S3. Cela permet :

- De conserver une copie brute (immutabilité).
- De découpler l'ingestion du traitement.
- De rejouer le pipeline depuis les données brutes si nécessaire.

MinIO est un serveur S3-compatible local — parfait pour le TP.

### 5.2. Script Python d'upload

Créez le script `src/ingestion/upload_to_minio.py` :

```python
"""
SciPulse — Upload des données ArXiv vers MinIO
Découpe le dump JSON en chunks et les dépose dans le bucket arxiv-raw.
"""

import json
import os

import boto3
from botocore.client import Config

# ── Configuration MinIO ─────────────────────────────────────────────

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS   = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET   = os.getenv("MINIO_SECRET_KEY", "minioadmin")
BUCKET         = "arxiv-raw"

# ── Connexion ────────────────────────────────────────────────────────

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS,
    aws_secret_access_key=MINIO_SECRET,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

def upload_file(local_path: str, object_name: str | None = None):
    """Upload un fichier vers MinIO."""
    if object_name is None:
        object_name = os.path.basename(local_path)

    s3.upload_file(local_path, BUCKET, object_name)
    print(f"  ✅ {object_name} → s3://{BUCKET}/{object_name}")


def split_and_upload(
    source_file: str,
    chunk_size: int = 10_000,
    prefix: str = "chunks/",
):
    """
    Découpe un fichier JSON lines en chunks et les upload vers MinIO.
    Chaque chunk contient `chunk_size` articles.
    """
    chunk_num = 0
    buffer = []

    with open(source_file, "r") as f:
        for i, line in enumerate(f, 1):
            buffer.append(line)

            if len(buffer) >= chunk_size:
                chunk_name = f"{prefix}arxiv-chunk-{chunk_num:04d}.json"
                _upload_chunk(buffer, chunk_name)
                buffer = []
                chunk_num += 1

    # Dernier chunk partiel
    if buffer:
        chunk_name = f"{prefix}arxiv-chunk-{chunk_num:04d}.json"
        _upload_chunk(buffer, chunk_name)
        chunk_num += 1

    print(f"\n🏁 {chunk_num} chunks uploadés ({i} articles au total)")


def _upload_chunk(lines: list[str], object_name: str):
    """Upload un chunk en mémoire vers MinIO."""
    body = "".join(lines)
    s3.put_object(Bucket=BUCKET, Key=object_name, Body=body.encode("utf-8"))
    print(f"  ✅ {object_name} ({len(lines)} articles)")


if __name__ == "__main__":
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else "data/arxiv-raw/arxiv-cs-subset-100k.json"

    if not os.path.exists(source):
        print(f"❌ Fichier non trouvé : {source}")
        sys.exit(1)

    print(f"📤 Upload de {source} vers MinIO (bucket: {BUCKET})")
    print(f"   Endpoint: {MINIO_ENDPOINT}\n")

    # Upload du fichier complet
    upload_file(source)

    # Découpage en chunks de 10 000 articles
    print(f"\n📦 Découpage en chunks de 10 000 articles...")
    split_and_upload(source, chunk_size=10_000)
```

### 5.3. Exécuter le script

```bash
python -m src.ingestion.upload_to_minio data/arxiv-raw/arxiv-cs-subset-100k.json
```

Sortie attendue :

```
📤 Upload de data/arxiv-raw/arxiv-cs-subset-100k.json vers MinIO (bucket: arxiv-raw)
   Endpoint: http://localhost:9000

  ✅ arxiv-cs-subset-100k.json → s3://arxiv-raw/arxiv-cs-subset-100k.json

📦 Découpage en chunks de 10 000 articles...
  ✅ chunks/arxiv-chunk-0000.json (10000 articles)
  ✅ chunks/arxiv-chunk-0001.json (10000 articles)
  ...
  ✅ chunks/arxiv-chunk-0009.json (10000 articles)

🏁 10 chunks uploadés (100000 articles au total)
```

### 5.4. Vérifier dans MinIO Console

Retournez sur http://localhost:9001 et naviguez dans le bucket `arxiv-raw`. Vous devez voir :

- Le fichier complet `arxiv-cs-subset-100k.json`
- Le dossier `chunks/` avec 10 fichiers de 10 000 articles chacun

### 5.5. Vérification programmatique

```python
# Quick check — lister le contenu du bucket
import boto3
from botocore.client import Config

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)

response = s3.list_objects_v2(Bucket="arxiv-raw")
for obj in response.get("Contents", []):
    print(f"  {obj['Key']:50s} {obj['Size'] / 1024 / 1024:.1f} Mo")
```

---

## Étape 6 — Premier contact avec Elasticsearch (20 min)

Avant de configurer Logstash (cet après-midi), familiarisons-nous avec Elasticsearch via Kibana Dev Tools.

### 6.1. Indexer un document manuellement

Dans Kibana > Dev Tools, exécutez :

```
PUT /test-index/_doc/1
{
  "title": "A Comprehensive Survey of AI-Generated Content",
  "abstract": "Recently, AI-generated content (AIGC) has received increasing attention and is becoming a hot topic in both research and industry.",
  "categories": ["cs.AI", "cs.CL"],
  "date_published": "2023-02-07"
}
```

Réponse attendue :

```json
{
  "_index": "test-index",
  "_id": "1",
  "result": "created",
  ...
}
```

### 6.2. Rechercher le document

```
GET /test-index/_search
{
  "query": {
    "match": {
      "abstract": "AI content"
    }
  }
}
```

Observez :

- Le `_score` : c'est le score de pertinence BM25.
- Le `_source` : c'est le document stocké.
- Le `hits.total.value` : nombre de résultats.

### 6.3. Explorer le mapping auto-généré

```
GET /test-index/_mapping
```

Elasticsearch a **deviné** les types de champs. Regardez :

- `title` a été mappé en `text` (recherche full-text possible).
- `categories` a été mappé en `text` aussi (mais on voudrait `keyword` pour les agrégations !).
- `date_published` a été mappé en `date` (ES a détecté le format).

C'est exactement pourquoi nous définirons un **mapping explicite** demain : le mapping automatique fait des choix raisonnables mais rarement optimaux.

### 6.4. Nettoyer

```
DELETE /test-index
```

---

## Étape 7 — Commit et checkpoint (10 min)

Avant de partir en pause, committons notre travail :

```bash
# Ajouter les fichiers créés pendant le TP
git add src/ingestion/upload_to_minio.py
git add .env   # (si vous l'avez modifié)

# Commit
git commit -m "feat: setup environment + upload arxiv data to minio"

# Push (si un remote est configuré)
git push origin feature/setup-<votre-nom>
```

### Checklist de fin de matinée

Avant de passer à l'après-midi, vérifiez que vous avez :

- [ ] Un dépôt Git initialisé avec la structure du projet
- [ ] Docker Compose lancé avec tous les services en `running` ou `healthy`
- [ ] Kibana accessible sur http://localhost:5601
- [ ] MinIO accessible sur http://localhost:9001 avec les 3 buckets
- [ ] Airflow accessible sur http://localhost:8080 avec les 2 DAGs visibles
- [ ] Le dump ArXiv (ou subset) téléchargé dans `data/arxiv-raw/`
- [ ] Les données uploadées dans MinIO (fichier complet + chunks)
- [ ] Un document indexé et recherché manuellement dans ES via Dev Tools
- [ ] Un commit Git propre

---

## Ce qui vient cet après-midi

Cet après-midi, nous attaquons l'**ingestion à grande échelle** : configurer un pipeline Logstash qui parse automatiquement le dump ArXiv et indexe les 100 000 articles dans Elasticsearch. Nous comparerons avec un pipeline Python utilisant `elasticsearch-py` et les `bulk` helpers.

À la fin de la journée, vous aurez 100 000 articles scientifiques indexés dans Elasticsearch et consultables dans Kibana Discover — prêts à être modélisés et fouillés au Jour 2.

---

## Mémo — Commandes utiles

```bash
# Stack Docker
docker compose up -d              # Lancer tout
docker compose down               # Arrêter tout
docker compose down -v            # Arrêter + supprimer les volumes
docker compose logs -f <service>  # Suivre les logs d'un service
docker compose ps                 # État des conteneurs

# Elasticsearch
curl -s localhost:9200/_cluster/health?pretty   # Santé
curl -s localhost:9200/_cat/indices?v            # Liste des index

# MinIO (via Docker)
docker run --rm --network=scipulse minio/mc \
  alias set local http://minio:9000 minioadmin minioadmin && \
  mc ls local/arxiv-raw/

# Raccourcis Makefile
make up                           # docker compose up -d
make status                       # ps + indices ES
make down                         # docker compose down
make clean                        # down -v + nettoyage
```
