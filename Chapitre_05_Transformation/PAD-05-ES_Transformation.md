# Jour 3 — Matin
# Bloc théorique : Transformation et enrichissement

> **Durée** : 45 minutes  
> **Positionnement** : étape transformation du cycle de vie  
> **Objectif** : comprendre les patterns de transformation (ETL/ELT), maîtriser les concepts de dbt, et savoir concevoir un pipeline d'enrichissement Python

---

## 1. La transformation dans le cycle de vie

### 1.1. Pourquoi transformer ?

Les données brutes ne sont presque jamais directement exploitables. Entre l'ingestion et le serving, une couche de transformation est nécessaire pour :

- **Nettoyer** : corriger les erreurs, supprimer les doublons, normaliser les formats (nous en avons fait l'expérience hier avec Great Expectations et le script de nettoyage).
- **Structurer** : organiser les données selon un modèle adapté aux questions métier. Un dump JSON plat ne se prête pas aux mêmes analyses qu'une table dimensionnelle.
- **Enrichir** : ajouter des informations dérivées des données existantes (extraire des mots-clés d'un texte, croiser deux sources, calculer des métriques).
- **Agréger** : pré-calculer des résumés (publications par mois, auteurs les plus prolifiques) pour des dashboards réactifs.

Dans SciPulse, la transformation couvre toute la chaîne : du dump ArXiv brut jusqu'à l'index Elasticsearch enrichi avec les scores Hacker News et les mots-clés extraits par NLP.

### 1.2. Positionnement dans l'architecture

```
    MinIO (raw)                           Elasticsearch (serving)
    ┌──────────┐                          ┌──────────────────────┐
    │ JSON dump│                          │ arxiv-papers         │
    │ brut     │                          │ (mapping optimisé,   │
    └────┬─────┘                          │  enrichi, scoré)     │
         │                                └──────────▲───────────┘
         │                                           │
         ▼                                           │
    ┌──────────┐     ┌──────────────┐     ┌──────────┴──────────┐
    │ Logstash │────▶│ PostgreSQL   │────▶│ Python enrichment   │
    │ (parse)  │     │ + dbt        │     │ (NLP, croisement HN,│
    └──────────┘     │ (transform)  │     │  réindexation ES)   │
                     └──────────────┘     └─────────────────────┘
```

Trois outils complémentaires interviennent :

- **Logstash** : transformations à l'ingestion (parsing, renommage, conversion de types). Déjà vu au Jour 1.
- **dbt** : transformations SQL versionnées dans PostgreSQL (agrégations, jointures, modélisation dimensionnelle).
- **Python** : transformations programmatiques (NLP, enrichissement croisé, logique métier complexe).

---

## 2. ETL vs. ELT — deux philosophies

### 2.1. ETL — Extract, Transform, Load

Le paradigme classique, dominant depuis les années 1990 dans le monde de l'entrepôt de données (data warehouse) :

```
Source → Extract → Transform (moteur dédié) → Load → Destination
```

Les données sont transformées **avant** d'être chargées dans le système de destination. La transformation se fait dans un outil intermédiaire (Informatica, Talend, SSIS, ou un script Python).

**Avantages** : on ne charge que des données propres et structurées. Le système de destination est allégé.

**Inconvénients** : le moteur de transformation est un goulet d'étranglement. Chaque nouvelle transformation nécessite de modifier le pipeline. Les données brutes sont perdues si on ne les conserve pas séparément.

### 2.2. ELT — Extract, Load, Transform

Le paradigme moderne, rendu possible par la puissance des moteurs analytiques cloud (BigQuery, Snowflake, Redshift, ou plus modestement PostgreSQL et Elasticsearch) :

```
Source → Extract → Load (brut) → Transform (dans la destination) → Vue serving
```

Les données sont chargées **telles quelles** dans le système de destination, puis transformées sur place avec la puissance de calcul de ce système. C'est l'approche que dbt a popularisée [1].

**Avantages** : les données brutes sont conservées (immutabilité). Les transformations sont versionnées en SQL (dbt). Le moteur de destination est optimisé pour les transformations analytiques. On peut ajouter de nouvelles transformations sans toucher au pipeline d'ingestion.

**Inconvénients** : le système de destination doit être suffisamment puissant. Les données brutes occupent de l'espace.

### 2.3. Dans SciPulse : une approche hybride

Notre architecture combine les deux :

| Étape | Pattern | Outil | Ce qui se passe |
|-------|---------|-------|-----------------|
| Ingestion ArXiv | ETL | Logstash | Parse, renomme, nettoie **avant** d'écrire dans ES |
| Modélisation tabulaire | ELT | dbt + PostgreSQL | Les données sont d'abord dans PG, puis transformées **sur place** |
| Enrichissement NLP | ETL | Python | Calcule des mots-clés et des scores **puis** réindexe dans ES |

Ce mélange est la réalité de la plupart des pipelines de données en production. Le purisme ETL ou ELT n'existe pas — on choisit le pattern adapté à chaque étape.

---

## 3. L'idempotence — un principe non négociable

### 3.1. Définition

Une transformation est **idempotente** si l'exécuter une fois ou dix fois produit exactement le même résultat. C'est le principe le plus important en ingénierie de données, et c'est un pilier DataOps fondamental.

Pourquoi ? Parce que les pipelines échouent. Un serveur plante, un réseau timeout, un fichier est corrompu. Si la transformation n'est pas idempotente, relancer le pipeline après un échec partiel peut produire des doublons, des valeurs incorrectes, ou des données incohérentes.

### 3.2. Comment l'obtenir

**En SQL (dbt)** : utiliser `CREATE TABLE ... AS SELECT` plutôt que `INSERT INTO`. Chaque exécution de `dbt run` recrée la table de zéro à partir de la requête SELECT. C'est le comportement par défaut de dbt avec `materialized: table`.

**En Python** : utiliser des opérations upsert (`_id` comme clé de déduplication dans ES), et toujours écraser plutôt qu'ajouter. Notre pipeline Logstash et notre script Python utilisent `document_id` / `_id` — c'est de l'idempotence.

**En Airflow** : marquer les tâches comme idempotentes (`depends_on_past: False`) et les rendre re-exécutables sans effets de bord. Si le DAG a échoué à l'étape 4, on peut relancer l'étape 4 seule sans refaire les étapes 1-3.

### 3.3. Le lignage (lineage)

Le **lignage** répond à la question : « d'où vient cette donnée ? ». Pour chaque champ d'une table de sortie, on doit pouvoir retracer :

- De quelle source il provient.
- Quelles transformations il a subies.
- À quel moment la dernière transformation a été exécutée.

dbt fournit le lignage automatiquement grâce à la fonction `ref()` : chaque modèle déclare ses dépendances, et dbt construit un graphe de lignage visualisable. C'est l'un de ses atouts majeurs.

---

## 4. dbt — data build tool

### 4.1. Qu'est-ce que dbt ?

dbt (data build tool) est un outil open-source qui permet d'écrire des transformations de données en SQL, de les versionner, de les tester, et de les documenter — le tout dans un workflow inspiré du développement logiciel [1].

dbt a été créé en 2016 par Fishtown Analytics (aujourd'hui dbt Labs) en partant d'un constat : les data analysts écrivent déjà leurs transformations en SQL, mais dans des scripts ad hoc, sans tests, sans versioning, sans documentation. dbt apporte à SQL ce que pytest apporte à Python et ce que Great Expectations apporte aux données.

**Ce que dbt fait** :

- Exécute des requêtes `SELECT` et matérialise les résultats en tables ou vues.
- Gère les dépendances entre les transformations (DAG de modèles).
- Exécute des tests de qualité sur les résultats.
- Génère une documentation interactive (site web).
- Version tout dans Git.

**Ce que dbt ne fait PAS** :

- L'ingestion (extraction depuis les sources). C'est le rôle de Logstash, Python, Fivetran, Airbyte.
- L'orchestration (planification, retry). C'est le rôle d'Airflow.
- Le stockage. dbt s'appuie sur une base existante (PostgreSQL, BigQuery, Snowflake…).

dbt est le « T » dans ELT — il ne s'occupe que de la transformation.

### 4.2. Les concepts fondamentaux

#### Models

Un **modèle** dbt est un fichier SQL contenant une requête `SELECT`. dbt exécute cette requête et matérialise le résultat en table ou en vue dans la base de données.

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

Chaque fichier `.sql` dans le dossier `models/` est un modèle. Le nom du fichier devient le nom de la table ou vue.

#### La fonction `ref()`

La magie de dbt est la fonction `ref()` : elle déclare une dépendance entre modèles.

```sql
-- models/marts/fct_publications_par_mois.sql

select
    date_trunc('month', date_published) as mois,
    primary_category,
    count(*) as nb_publications
from {{ ref('stg_arxiv_papers') }}    -- ← dépendance déclarée
group by 1, 2
```

`ref('stg_arxiv_papers')` dit à dbt : « ce modèle dépend de `stg_arxiv_papers` — exécute-le d'abord ». dbt construit automatiquement le graphe de dépendances (DAG) et exécute les modèles dans le bon ordre.

C'est aussi grâce à `ref()` que dbt génère le **lignage** : on peut visualiser exactement quels modèles dépendent de quels autres.

#### Sources

Une **source** est une table qui existe déjà dans la base (pas créée par dbt). On la déclare dans un fichier YAML :

```yaml
sources:
  - name: raw
    tables:
      - name: arxiv_papers_raw
```

Et on y fait référence avec `{{ source('raw', 'arxiv_papers_raw') }}`. Cela documente les dépendances vers l'extérieur.

#### Materialization

Comment dbt matérialise-t-il les résultats ? Quatre options :

| Matérialisation | Comportement | Quand l'utiliser |
|----------------|-------------|------------------|
| `view` | Crée une vue SQL (pas de stockage, exécutée à la volée) | Staging, données peu volumineuses |
| `table` | Crée une table (stockage physique, recréée à chaque run) | Marts, données volumineuses, performances |
| `incremental` | Ajoute uniquement les nouvelles lignes (merge/upsert) | Tables très volumineuses, ingestion continue |
| `ephemeral` | CTE intégrée dans les modèles en aval (pas de table) | Transformations intermédiaires légères |

Dans SciPulse, le staging est en `view` (léger, pas besoin de stocker) et les marts en `table` (pré-calculés pour la performance).

### 4.3. Les tests dbt

dbt intègre un framework de tests léger mais efficace, déclaré en YAML :

```yaml
models:
  - name: stg_arxiv_papers
    columns:
      - name: arxiv_id
        tests: [not_null, unique]
      - name: primary_category
        tests: [not_null]
```

Quatre tests génériques intégrés :

| Test | Ce qu'il vérifie |
|------|-----------------|
| `not_null` | Aucune valeur null |
| `unique` | Pas de doublons |
| `accepted_values` | Valeurs dans un ensemble connu |
| `relationships` | Intégrité référentielle (FK) |

On peut aussi écrire des tests custom en SQL (un `SELECT` qui retourne les lignes en erreur) et utiliser des packages communautaires comme `dbt_utils` qui ajoutent des dizaines de tests supplémentaires.

Les tests dbt et les expectations Great Expectations sont **complémentaires** :

- **dbt tests** : intégrés au workflow SQL, exécutés par `dbt test`, portent sur les tables PostgreSQL.
- **GX expectations** : indépendants du moteur SQL, exécutés sur des DataFrames ou des connexions arbitraires, avec des Data Docs et un historique.

En production, on utilise les deux : dbt tests pour les contraintes simples sur les modèles SQL, GX pour les validations plus sophistiquées sur les données brutes et enrichies.

### 4.4. La documentation dbt

`dbt docs generate` produit un site web interactif qui documente :

- Chaque modèle (description, SQL, colonnes).
- Chaque source (tables, colonnes).
- Le graphe de lignage (DAG visuel de toutes les dépendances).
- Les résultats des tests.

`dbt docs serve` lance un serveur local pour explorer cette documentation. C'est de la documentation vivante — mise à jour à chaque `dbt docs generate`.

### 4.5. L'organisation en couches

La convention dbt recommande trois couches de modèles [2] :

```
sources (tables brutes)
    │
    ▼
staging (stg_*)        ← nettoyage, renommage, typage
    │                     une vue par source
    ▼
intermediate (int_*)   ← jointures, calculs intermédiaires (optionnel)
    │
    ▼
marts (fct_*, dim_*)   ← tables finales orientées métier
                          dimensions et faits
```

**Staging** : un modèle par source, matérialisé en `view`. Son rôle est de nettoyer et normaliser — renommer les colonnes, convertir les types, filtrer les lignes invalides. C'est le seul endroit où on référence les `source()` — tous les autres modèles utilisent `ref()`.

**Marts** : tables orientées métier, matérialisées en `table`. Elles répondent à des questions spécifiques : « combien de publications par mois et par catégorie ? », « quels sont les auteurs les plus prolifiques ? ». Ce sont les tables que Kibana ou un outil BI consomme.

---

## 5. L'enrichissement en Python

### 5.1. Quand Python plutôt que SQL ?

SQL est le bon outil pour les transformations tabulaires : filtrage, jointure, agrégation, fenêtrage. Mais certaines transformations dépassent les capacités de SQL :

- **NLP** : extraction de mots-clés, détection de langue, analyse de sentiment, embeddings.
- **Appels à des APIs externes** : géocodage, enrichissement par un service tiers.
- **Logique algorithmique complexe** : matching flou, parsing de formats non standard, calculs itératifs.
- **Croisement de sources hétérogènes** : jointure entre un index Elasticsearch et une API REST.

Dans SciPulse, l'enrichissement Python couvre trois tâches que SQL ne peut pas faire :

1. **Extraction de mots-clés** depuis les abstracts (TF-IDF).
2. **Détection de liens ArXiv** dans les posts Hacker News (regex sur les URLs).
3. **Injection des scores HN** dans les articles ArXiv (croisement inter-sources).

### 5.2. TF-IDF pour l'extraction de mots-clés

TF-IDF (Term Frequency – Inverse Document Frequency) est une méthode classique de recherche d'information pour identifier les termes les plus caractéristiques d'un document au sein d'un corpus [3].

L'intuition est la même que celle de BM25 (vue au Jour 2) :

- **TF (Term Frequency)** : un terme qui apparaît souvent dans un document est important pour ce document.
- **IDF (Inverse Document Frequency)** : un terme qui apparaît dans beaucoup de documents est peu discriminant (stopwords naturels).

Le score TF-IDF d'un terme dans un document est le produit des deux : un terme fréquent dans *ce* document mais rare dans le corpus global a un score élevé — c'est un mot-clé.

En Python, `scikit-learn` fournit une implémentation optimisée :

```python
from sklearn.feature_extraction.text import TfidfVectorizer

vectorizer = TfidfVectorizer(max_features=20, stop_words="english")
tfidf = vectorizer.fit_transform(abstracts)
keywords = vectorizer.get_feature_names_out()
```

Pour chaque article, on extrait les N termes avec le score TF-IDF le plus élevé — ce sont ses mots-clés. Ces mots-clés sont ensuite ajoutés comme champ `keywords` dans l'index Elasticsearch, ce qui enrichit les possibilités de recherche et d'agrégation.

### 5.3. Le croisement ArXiv × Hacker News

Le croisement entre les deux sources est l'enrichissement le plus original de SciPulse. Le mécanisme :

1. Le poller HN détecte les URLs pointant vers ArXiv (`arxiv.org/abs/XXXX.XXXXX`) et stocke le lien dans l'index `arxiv-hn-links`.
2. Le script d'enrichissement lit cet index, regroupe les liens par `arxiv_id`, et calcule pour chaque article : le score HN cumulé, le nombre de commentaires HN, la liste des posts HN.
3. Ces métriques sont injectées dans l'index `arxiv-papers` comme champs `hn_score`, `hn_comments_count`, `hn_item_ids`.

Le résultat : on peut chercher « les articles de reinforcement learning les plus discutés sur Hacker News » — une requête `function_score` qui combine la pertinence textuelle BM25 avec un boost sur `hn_score`. C'est le type de requête qui serait impossible sans enrichissement croisé.

---

## 6. Orchestration des transformations

### 6.1. L'ordre d'exécution

Les transformations doivent s'exécuter dans un ordre précis. On ne peut pas enrichir les articles ArXiv avec les scores HN si les liens croisés n'ont pas encore été détectés. Dans notre DAG Airflow :

```
ingest_arxiv → transform_dbt → enrich_python → validate_enriched
                                    │
poll_hn ─── detect_links ───────────┘
```

Le DAG Airflow garantit cet ordre. dbt gère l'ordre interne de ses modèles via `ref()`. Le script Python d'enrichissement est la dernière étape avant la validation finale.

### 6.2. Atomicité et rollback

Que se passe-t-il si l'enrichissement Python échoue à mi-chemin ? Les documents déjà enrichis sont dans ES, mais pas les autres. L'état est incohérent.

Deux stratégies :

- **Idempotence** (notre approche) : le script est conçu pour être relancé. Chaque document est écrasé par son enrichissement complet. Relancer = résultat identique.
- **Transaction** (approche alternative) : enrichir dans un index temporaire, puis faire un swap atomique (`_alias`). Plus complexe mais garantit la cohérence à tout instant.

Pour le TP, l'idempotence suffit. En production, le swap d'alias est plus robuste.

---

## 7. Ce qui vient dans le TP

Le TP met en pratique ces concepts :

1. **Chargement des données dans PostgreSQL** : miroir tabulaire des articles ArXiv pour dbt.
2. **Modèles dbt** : staging (`stg_arxiv_papers`) et marts (`fct_publications_par_mois`, `fct_auteurs_prolifiques`).
3. **Tests dbt** : `not_null`, `unique`, `accepted_values` sur les modèles.
4. **Script Python d'enrichissement** : extraction de mots-clés par TF-IDF, détection de liens ArXiv dans les posts HN, injection des scores croisés dans ES.

---

## Bibliographie

### Ouvrages de référence

[1] dbt Labs. (2024). *dbt Documentation*. https://docs.getdbt.com  
La documentation officielle de dbt est exceptionnellement pédagogique. Les sections « What is dbt? », « About dbt models », « About dbt tests » et le « Quickstart for dbt Core » constituent le meilleur tutoriel disponible. La section « Best practices » formalise les conventions de nommage (stg_, fct_, dim_) et l'organisation en couches que nous utilisons dans SciPulse.

[2] dbt Labs. (2024). « How we structure our dbt projects ». *dbt Developer Blog*. https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview  
Le guide de référence pour l'organisation d'un projet dbt en couches (staging, intermediate, marts). Explique pourquoi séparer les couches, comment nommer les modèles, et comment gérer les dépendances. Directement applicable au TP.

[3] Reis, J., & Housley, M. (2022). *Fundamentals of Data Engineering*. O'Reilly Media.  
Le chapitre 8 (Queries, Modeling, and Transformation) est la référence la plus complète sur les patterns de transformation dans le contexte du data engineering moderne. La discussion ETL vs. ELT (section 8.2) est nuancée et ancrée dans des cas d'usage réels. Le chapitre 5 (Data Generation in Source Systems) éclaire les enjeux de lignage.

[4] Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly Media.  
Le chapitre 10 (Batch Processing) couvre les fondements théoriques des transformations batch : MapReduce, graphes de dépendances, idempotence, et l'importance de la reproductibilité. Le chapitre 3 (Storage and Retrieval) fournit le contexte pour comprendre pourquoi dbt matérialise en tables vs. vues.

[5] Manning, C.D., Raghavan, P., & Schütze, H. (2008). *Introduction to Information Retrieval*. Cambridge University Press.  
Le chapitre 6 (Scoring, term weighting, and the vector space model) est la référence académique pour TF-IDF. L'explication mathématique est accessible et complète la compréhension intuitive donnée dans le cours. Disponible gratuitement : https://nlp.stanford.edu/IR-book/

### Articles et ressources complémentaires

[6] Kimball, R., & Ross, M. (2013). *The Data Warehouse Toolkit*. 3rd edition. Wiley.  
L'ouvrage fondateur de la modélisation dimensionnelle (tables de faits et de dimensions). Bien que datant de l'ère des data warehouses traditionnels, les principes de modélisation (star schema, slowly changing dimensions, grain) restent la base de toute modélisation analytique — y compris dans dbt. Le chapitre 1 (Dimensional Modeling Primer) suffit pour comprendre la distinction fct_ / dim_ que nous utilisons.

[7] Pedregosa, F. et al. (2011). « Scikit-learn: Machine Learning in Python ». *Journal of Machine Learning Research*, 12, 2825-2830.  
L'article de référence de scikit-learn, la bibliothèque que nous utilisons pour TF-IDF. La documentation de `TfidfVectorizer` (https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html) est particulièrement bien écrite et couvre tous les paramètres que nous utiliserons dans le TP.

[8] dbt Labs. (2024). *dbt Tests Documentation*. https://docs.getdbt.com/docs/build/data-tests  
Documentation complète des tests dbt : tests génériques (not_null, unique, accepted_values, relationships), tests custom en SQL, et packages de tests communautaires (dbt_utils, dbt_expectations). Indispensable pour le TP.

[9] Dehghani, Z. (2022). *Data Mesh*. O'Reilly Media.  
Le chapitre 8 (« Data as a Product ») argumente que chaque transformation doit produire un « data product » documenté, testé, et versionné — exactement ce que dbt permet. La vision data mesh éclaire pourquoi dbt a connu une adoption aussi rapide : il rend les analystes autonomes dans la production de données fiables.

[10] DataOps Manifesto. https://dataopsmanifesto.org  
Les principes 3 (« reproducibility ») et 7 (« disposability ») sont directement liés à l'idempotence et à la reproductibilité des transformations. Le principe 11 (« automate everything ») motive l'intégration de dbt dans Airflow plutôt que l'exécution manuelle.
