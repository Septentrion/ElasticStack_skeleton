# dbt : transformer vos données avec la rigueur du code

## Le problème que dbt résout

Dans un pipeline de données classique, la transformation est souvent le maillon faible. Les analystes écrivent des requêtes SQL dans des scripts éparpillés, sans tests, sans documentation, sans gestion des dépendances. Le résultat : des pipelines fragiles où personne ne sait vraiment d'où vient une donnée ni si elle est fiable.

**dbt** (data build tool) apporte au SQL ce que `pytest` apporte à Python : du versioning, des tests, de la documentation, et un graphe de dépendances automatique. Créé en 2016 par dbt Labs, il est devenu l'outil de référence pour le « T » de l'approche **ELT** (Extract, Load, Transform) — celle où les données sont d'abord chargées brutes dans une base, puis transformées sur place.

## Ce que dbt fait — et ce qu'il ne fait pas

dbt se concentre exclusivement sur la transformation. Concrètement, il exécute des requêtes `SELECT`, matérialise les résultats en tables ou vues, gère les dépendances entre modèles, exécute des tests de qualité et génère une documentation interactive.

En revanche, dbt **ne fait pas** l'ingestion (c'est le rôle de Logstash, Airbyte, ou d'un script Python), ni l'orchestration (Airflow s'en charge), ni le stockage — il s'appuie sur une base existante comme PostgreSQL, BigQuery ou Snowflake.

## Installer dbt avec Python

dbt s'installe comme n'importe quel package Python. La version open-source (`dbt-core`) se couple avec un adaptateur selon votre base de données :

```bash
# Installation de dbt-core avec l'adaptateur PostgreSQL
pip install dbt-core dbt-postgres

# Vérification
dbt --version
```

Pour créer un nouveau projet :

```bash
dbt init mon_projet
cd mon_projet
```

Cela génère une arborescence standard :

```
mon_projet/
├── dbt_project.yml          # Configuration du projet
├── models/
│   ├── staging/             # Nettoyage des sources brutes
│   └── marts/               # Tables orientées métier
├── tests/                   # Tests custom
└── profiles.yml             # Connexion à la base (hors du projet)
```

## Le fichier `profiles.yml`

Ce fichier configure la connexion à votre base. Il se place généralement dans `~/.dbt/` :

```yaml
mon_projet:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      port: 5432
      user: dataeng
      password: "{{ env_var('DBT_PASSWORD') }}"
      dbname: scipulse
      schema: transform
      threads: 4
```

> **Bonne pratique** : ne stockez jamais vos mots de passe en dur. Utilisez `env_var()` pour lire une variable d'environnement.

## Les modèles : du SQL, tout simplement

Un modèle dbt est un fichier `.sql` contenant une requête `SELECT`. Le nom du fichier devient le nom de la table ou vue créée dans la base.

### Couche staging : nettoyer les données brutes

```sql
-- models/staging/stg_arxiv_papers.sql

select
    arxiv_id,
    trim(title) as title,
    trim(abstract) as abstract,
    split_part(categories, ' ', 1) as primary_category,
    date_published
from {{ source('raw', 'arxiv_papers_raw') }}
where arxiv_id is not null
```

Ce modèle nettoie la table brute : il supprime les espaces superflus, extrait la catégorie principale, et filtre les lignes sans identifiant. La fonction `source()` déclare une dépendance vers une table externe (non gérée par dbt).

### Couche marts : répondre aux questions métier

```sql
-- models/marts/fct_publications_par_mois.sql

select
    date_trunc('month', date_published) as mois,
    primary_category,
    count(*) as nb_publications
from {{ ref('stg_arxiv_papers') }}
group by 1, 2
```

La magie opère avec `ref()` : cette fonction dit à dbt « exécute `stg_arxiv_papers` **avant** ce modèle ». dbt construit automatiquement le graphe de dépendances (DAG) et détermine l'ordre d'exécution.

## Matérialisation : table, vue, ou autre chose ?

On configure la matérialisation dans `dbt_project.yml` :

```yaml
# dbt_project.yml
models:
  mon_projet:
    staging:
      +materialized: view       # Léger, recalculé à la volée
    marts:
      +materialized: table      # Pré-calculé, performant
```

Les quatre options principales :

- **view** — une vue SQL, sans stockage physique. Idéale pour le staging.
- **table** — une table recréée à chaque `dbt run`. Idéale pour les marts.
- **incremental** — seules les nouvelles lignes sont ajoutées. Pour les très gros volumes.
- **ephemeral** — une CTE injectée dans les modèles en aval. Aucune trace en base.

## Tester vos transformations

dbt intègre un framework de tests déclaratifs en YAML :

```yaml
# models/staging/schema.yml
version: 2

sources:
  - name: raw
    tables:
      - name: arxiv_papers_raw

models:
  - name: stg_arxiv_papers
    columns:
      - name: arxiv_id
        tests: [not_null, unique]
      - name: primary_category
        tests:
          - not_null
          - accepted_values:
              values: ['cs.AI', 'cs.LG', 'stat.ML', 'cs.CL', 'cs.CV']
```

Quatre tests sont intégrés nativement : `not_null`, `unique`, `accepted_values` et `relationships` (intégrité référentielle). On peut aussi écrire des tests custom en SQL — toute requête qui retourne des lignes signale une erreur.

## Piloter dbt depuis Python

En plus de la ligne de commande, dbt expose une **API Python** qui permet d'intégrer les transformations dans un script ou un DAG Airflow :

```python
from dbt.cli.main import dbtRunner, dbtRunnerResult

# Initialiser le runner
dbt = dbtRunner()

# Exécuter les modèles
result: dbtRunnerResult = dbt.invoke(["run", "--project-dir", "./mon_projet"])

if result.success:
    print("Tous les modèles ont été exécutés avec succès.")
else:
    print("Erreur lors de l'exécution :")
    for r in result.result:
        if r.status != "success":
            print(f"  - {r.node.unique_id} : {r.status}")

# Exécuter les tests
test_result = dbt.invoke(["test", "--project-dir", "./mon_projet"])

if not test_result.success:
    print("Des tests ont échoué !")
    for r in test_result.result:
        if r.status == "fail":
            print(f"  - {r.node.unique_id} : {r.failures} lignes en erreur")
```

### Intégration dans un DAG Airflow

Dans un vrai pipeline, dbt s'intègre naturellement avec Airflow :

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG("scipulse_transform", start_date=datetime(2025, 1, 1),
         schedule_interval="@daily", catchup=False) as dag:

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/dbt/scipulse && dbt run --profiles-dir /opt/dbt",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/dbt/scipulse && dbt test --profiles-dir /opt/dbt",
    )

    enrich_python = BashOperator(
        task_id="enrich_python",
        bash_command="python /opt/scripts/enrich_arxiv.py",
    )

    dbt_run >> dbt_test >> enrich_python
```

L'ordre est essentiel : on transforme d'abord avec dbt (SQL), on valide avec les tests, puis on enrichit avec Python (NLP, croisement de sources) — ce que SQL ne sait pas faire.

## Charger les données avant dbt : le rôle de Python

dbt ne gère que la transformation — il faut d'abord que les données brutes soient dans la base. Voici un script Python minimal pour charger des données JSON dans PostgreSQL avant de lancer dbt :

```python
import json
import psycopg2
from psycopg2.extras import execute_values

# Connexion
conn = psycopg2.connect(
    host="localhost", dbname="scipulse",
    user="dataeng", password="secret"
)

# Lecture des données brutes
with open("arxiv_dump.json") as f:
    papers = json.load(f)

# Insertion en masse
rows = [
    (p["id"], p["title"], p["abstract"], p["categories"], p["published"])
    for p in papers
]

with conn.cursor() as cur:
    execute_values(cur, """
        INSERT INTO raw.arxiv_papers_raw (arxiv_id, title, abstract, categories, date_published)
        VALUES %s
        ON CONFLICT (arxiv_id) DO UPDATE SET
            title = EXCLUDED.title,
            abstract = EXCLUDED.abstract
    """, rows)

conn.commit()
conn.close()

print(f"{len(rows)} articles chargés dans PostgreSQL.")
```

Le `ON CONFLICT ... DO UPDATE` garantit l'**idempotence** : relancer le script produit toujours le même résultat, sans doublons.

## Générer la documentation

Une dernière commande pour la route :

```bash
dbt docs generate
dbt docs serve
```

Cela produit un site web interactif avec la documentation de chaque modèle, le graphe de lignage complet, et les résultats des tests. De la documentation vivante, mise à jour à chaque exécution.

## En résumé

| Étape | Outil | Rôle |
|-------|-------|------|
| Extraction + chargement | Python, Logstash, Airbyte | Mettre les données brutes en base |
| Transformation SQL | **dbt** | Nettoyer, structurer, agréger |
| Tests de qualité | dbt tests + Great Expectations | Valider les résultats |
| Enrichissement avancé | Python (NLP, APIs, croisements) | Ce que SQL ne peut pas faire |
| Orchestration | Airflow | Coordonner l'ensemble |

dbt ne remplace pas Python — il le complète. SQL pour les transformations tabulaires, Python pour la logique complexe, et dbt comme pont entre les deux mondes, avec la rigueur du développement logiciel : versioning, tests, documentation, et reproductibilité.
