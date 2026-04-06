# Mémento — Fonctions utiles pour le TP J3 matin
# Transformation dbt et enrichissement Python

> Classement par bibliothèque / module, avec une courte explication et un exemple d'usage tiré du code du TP.
> Ce mémento est autonome : toutes les fonctions utilisées dans le TP sont documentées, y compris celles déjà vues aux Jours 1-2.

---

## 1. `elasticsearch` — Client Python Elasticsearch

### `Elasticsearch(host)`

Crée une connexion au cluster Elasticsearch.

```python
from elasticsearch import Elasticsearch
es = Elasticsearch("http://localhost:9200")
```

### `es.info()`

Retourne les informations du cluster (nom, version). Utilisé pour vérifier que la connexion fonctionne.

```python
info = es.info()
print(info["cluster_name"])   # → "scipulse-cluster"
```

### `es.count(index, query)`

Retourne le nombre de documents dans un index. Avec `query`, ne compte que les documents qui matchent.

```python
# Tous les documents
total = es.count(index="arxiv-papers")["count"]

# Uniquement les documents ayant des mots-clés
kw_count = es.count(
    index="arxiv-papers",
    query={"exists": {"field": "keywords"}},
)["count"]
```

### `es.search(index, size, query, aggs, sort, _source)`

Exécute une requête de recherche. Retourne les documents matchés et les agrégations.

```python
# Recherche avec agrégation
result = es.search(
    index="arxiv-papers",
    size=0,                    # 0 = pas de documents, juste les agrégations
    aggs={
        "top_kw": {"terms": {"field": "keywords", "size": 15}}
    },
)
buckets = result["aggregations"]["top_kw"]["buckets"]

# Recherche avec tri et sélection de champs
result = es.search(
    index="arxiv-papers",
    size=5,
    query={"exists": {"field": "hn_score"}},
    sort=[{"hn_score": "desc"}],
    _source=["arxiv_id", "title", "hn_score"],
)
```

### `es.indices.exists(index)`

Vérifie si un index existe. Retourne `True` ou `False`.

```python
if not es.indices.exists(index="arxiv-hn-links"):
    print("Index non trouvé")
```

### `es.indices.refresh(index)`

Force Elasticsearch à rendre les documents récemment indexés cherchables immédiatement (sinon délai ~1 seconde).

```python
es.indices.refresh(index="arxiv-papers")
```

---

## 2. `elasticsearch.helpers` — Opérations en masse

### `helpers.scan(es, index, query, size)`

Parcourt un index entier de manière efficace (API scroll). Retourne un itérateur de hits. Contrairement à `es.search()` (limité à 10 000 résultats), `scan` peut parcourir des millions de documents.

```python
from elasticsearch import helpers

docs = []
for hit in helpers.scan(
    es,
    index="arxiv-papers",
    query={"query": {"match_all": {}}},
    size=1000,           # Taille des lots internes (pas le nombre total)
):
    docs.append(hit["_source"])
    if len(docs) >= 50_000:
        break
```

### `helpers.streaming_bulk(es, actions, chunk_size, raise_on_error)`

Indexe ou met à jour des documents en masse par lots. Consomme un générateur d'actions. Retourne un itérateur `(ok, result)` pour chaque document — permet de suivre la progression.

```python
for ok, result in helpers.streaming_bulk(
    es,
    generate_update_actions(),
    chunk_size=500,
    raise_on_error=False,
):
    if ok:
        success += 1
    else:
        errors += 1
```

### Format d'une action `update` (mise à jour partielle)

Contrairement à l'action `index` (qui remplace le document entier), l'action `update` ne modifie que les champs spécifiés dans `doc`.

```python
yield {
    "_op_type": "update",              # Mise à jour partielle (pas remplacement)
    "_index":   "arxiv-papers",
    "_id":      "2301.07041",
    "doc":      {"keywords": ["transformer", "attention"]},   # Seuls ces champs changent
    "doc_as_upsert": False,            # Ne pas créer le doc s'il n'existe pas
}
```

---

## 3. `psycopg2` — Client PostgreSQL pour Python

### `psycopg2.connect(dsn)`

Crée une connexion à PostgreSQL. Le DSN (Data Source Name) contient l'hôte, le port, la base, l'utilisateur et le mot de passe.

```python
import psycopg2

conn = psycopg2.connect(
    "host=localhost port=5432 dbname=scipulse user=scipulse password=scipulse"
)
```

### `conn.cursor()`

Crée un curseur pour exécuter des requêtes SQL. Un curseur est un pointeur vers le résultat d'une requête.

```python
cur = conn.cursor()
```

### `cur.execute(sql)`

Exécute une requête SQL. Pour les requêtes DDL (`CREATE`, `DROP`) et DML (`INSERT`, `UPDATE`, `DELETE`), il faut appeler `conn.commit()` ensuite.

```python
cur.execute("DROP TABLE IF EXISTS public.arxiv_papers_raw CASCADE;")
cur.execute("""
    CREATE TABLE public.arxiv_papers_raw (
        arxiv_id         TEXT PRIMARY KEY,
        title            TEXT,
        abstract         TEXT,
        authors_flat     TEXT,
        categories       TEXT,
        primary_category TEXT,
        date_published   TEXT,
        date_updated     TEXT,
        doi              TEXT
    );
""")
conn.commit()       # ← N'oubliez pas le commit !
```

### `cur.fetchone()`

Récupère la prochaine ligne du résultat d'un `SELECT`. Retourne un tuple, ou `None` s'il n'y a plus de lignes.

```python
cur.execute("SELECT COUNT(*) FROM public.arxiv_papers_raw;")
count = cur.fetchone()[0]     # → 100000
```

### `cur.fetchall()`

Récupère toutes les lignes restantes du résultat. Retourne une liste de tuples.

```python
cur.execute("""
    SELECT primary_category, COUNT(*) as n
    FROM public.arxiv_papers_raw
    GROUP BY primary_category
    ORDER BY n DESC
    LIMIT 5;
""")
for row in cur.fetchall():
    print(f"  {row[0]:<12} {row[1]:>6,}")
```

### `cur.close()` / `conn.close()`

Ferme le curseur et la connexion. Toujours fermer pour libérer les ressources.

```python
cur.close()
conn.close()
```

### `conn.commit()`

Valide les modifications en base. Sans commit, les `INSERT`, `UPDATE`, `CREATE TABLE` ne sont pas persistés.

```python
conn.commit()
```

### `conn.rollback()`

Annule les modifications en cours (utilisé en cas d'erreur dans un bloc try/except).

```python
try:
    cur.execute("SELECT ...")
except Exception:
    conn.rollback()
```

---

## 4. `psycopg2.extras.execute_values` — Insertion en masse

### `execute_values(cur, sql, values, page_size)`

Insère de nombreuses lignes d'un coup. Beaucoup plus rapide qu'un `INSERT` par ligne (~10x). Le `%s` dans le SQL est remplacé par chaque tuple de la liste `values`.

```python
from psycopg2.extras import execute_values

columns = ["arxiv_id", "title", "abstract", "authors_flat",
           "categories", "primary_category", "date_published",
           "date_updated", "doi"]

values = []
for _, row in df.iterrows():
    values.append(tuple(
        str(row.get(c)) if row.get(c) is not None else None
        for c in columns
    ))

execute_values(
    cur,
    f"""
    INSERT INTO public.arxiv_papers_raw ({', '.join(columns)})
    VALUES %s
    ON CONFLICT (arxiv_id) DO NOTHING
    """,
    values,
    page_size=1000,       # Nombre de lignes par batch SQL
)
conn.commit()
```

**`ON CONFLICT (arxiv_id) DO NOTHING`** : si un article avec le même `arxiv_id` existe déjà, l'insertion est ignorée silencieusement (idempotence).

---

## 5. `pandas` — Manipulation de DataFrames

### `pd.DataFrame(list_of_dicts)`

Crée un DataFrame à partir d'une liste de dictionnaires. Chaque dict devient une ligne.

```python
import pandas as pd

docs = []
for hit in helpers.scan(es, index="arxiv-papers", ...):
    docs.append(hit["_source"])

df = pd.DataFrame(docs)
```

### `df.iterrows()`

Itère sur les lignes du DataFrame. Retourne `(index, row)` pour chaque ligne. `row` est un objet Series avec les valeurs de chaque colonne.

```python
for _, row in df.iterrows():
    doc = row.to_dict()
    arxiv_id = row.get("arxiv_id")
```

**Note** : `iterrows` est lent pour les gros DataFrames. Pour 100 000 lignes, c'est acceptable. Pour des millions, préférer des opérations vectorisées ou `itertuples()`.

### `row.get(column_name)`

Récupère la valeur d'une colonne dans une ligne, avec `None` par défaut si la colonne n'existe pas.

```python
categories = row.get("categories", "")
```

---

## 6. `sklearn.feature_extraction.text.TfidfVectorizer` — Extraction de mots-clés

### `TfidfVectorizer(**params)`

Crée un vectoriseur TF-IDF qui transforme une collection de textes en matrice numérique. Chaque ligne est un document, chaque colonne un terme, et chaque valeur est le score TF-IDF (terme fréquent dans CE document mais rare dans le corpus → score élevé).

```python
from sklearn.feature_extraction.text import TfidfVectorizer

vectorizer = TfidfVectorizer(
    max_features=5000,       # Vocabulaire limité aux 5000 termes les plus importants
    stop_words="english",    # Supprimer les stopwords anglais (the, a, of, is...)
    min_df=5,                # Ignorer les termes présents dans < 5 documents (trop rares = bruit)
    max_df=0.7,              # Ignorer les termes présents dans > 70% des documents (trop communs)
    ngram_range=(1, 2),      # Unigrammes ET bigrammes ("neural" + "neural network")
    token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",  # Mots de 2+ lettres (exclut les chiffres seuls)
)
```

| Paramètre | Rôle | Valeur dans le TP |
|-----------|------|-------------------|
| `max_features` | Taille du vocabulaire | 5 000 |
| `stop_words` | Stopwords à supprimer | `"english"` (liste intégrée) |
| `min_df` | Fréquence de document minimale | 5 (au moins 5 docs) |
| `max_df` | Fréquence de document maximale | 0.7 (au plus 70% des docs) |
| `ngram_range` | N-grammes à extraire | (1, 2) = uni + bigrammes |
| `token_pattern` | Regex pour le tokenizer | Mots alphabétiques de 2+ lettres |

### `vectorizer.fit_transform(texts)`

Apprend le vocabulaire **et** transforme les textes en matrice TF-IDF en un seul appel. Retourne une matrice sparse (scipy.sparse).

```python
abstracts = ["We propose a novel transformer...", "This paper presents...", ...]

tfidf_matrix = vectorizer.fit_transform(abstracts)
# tfidf_matrix.shape → (47832, 5000) : 47832 documents × 5000 termes
```

**`fit_transform` = `fit` + `transform`** : `fit` apprend le vocabulaire, `transform` applique le calcul TF-IDF. En les combinant, on économise un parcours des données.

### `vectorizer.get_feature_names_out()`

Retourne la liste des termes du vocabulaire. L'indice de chaque terme correspond à la colonne dans la matrice TF-IDF.

```python
feature_names = vectorizer.get_feature_names_out()
# → ["algorithm", "attention", "classification", "cnn", "convolutional", "deep learning", ...]
```

### Extraire les top-N mots-clés par document

Le workflow complet pour extraire les N termes avec le score TF-IDF le plus élevé pour un document donné :

```python
for i, arxiv_id in enumerate(ids):
    # 1. Récupérer la ligne de la matrice pour ce document
    row = tfidf_matrix[i].toarray().flatten()

    # 2. Trier les indices par score décroissant
    top_indices = row.argsort()[-8:][::-1]     # Top 8

    # 3. Convertir les indices en noms de termes
    keywords = [feature_names[j] for j in top_indices if row[j] > 0]

    # keywords → ["transformer", "attention", "self attention", "model", ...]
```

---

## 7. `numpy` — Opérations numériques

### `ndarray.toarray()`

Convertit une matrice sparse (scipy) en matrice dense (numpy). Nécessaire pour accéder aux valeurs individuelles.

```python
dense_row = tfidf_matrix[i].toarray()    # shape: (1, 5000) — matrice 2D
```

### `ndarray.flatten()`

Aplatit une matrice 2D en vecteur 1D. Nécessaire après `toarray()` pour utiliser `argsort()`.

```python
row = tfidf_matrix[i].toarray().flatten()    # shape: (5000,) — vecteur 1D
```

### `ndarray.argsort()`

Retourne les **indices** qui trieraient le tableau par ordre croissant. Pour obtenir les N plus grandes valeurs, on prend les N derniers indices et on inverse.

```python
import numpy as np

row = np.array([0.1, 0.8, 0.3, 0.9, 0.0])
row.argsort()             # → [4, 0, 2, 1, 3]  (indices triés par valeur croissante)
row.argsort()[-2:]        # → [1, 3]            (les 2 plus grandes valeurs)
row.argsort()[-2:][::-1]  # → [3, 1]            (inversé = décroissant : 0.9 puis 0.8)
```

---

## 8. dbt — Fonctions Jinja dans les modèles SQL

### `{{ ref('model_name') }}`

Référence un autre modèle dbt par son nom de fichier (sans `.sql`). dbt résout les dépendances automatiquement : si le modèle A utilise `ref('B')`, B est exécuté avant A.

```sql
-- Dans fct_auteurs_prolifiques.sql :
select * from {{ ref('stg_arxiv_papers') }}
-- dbt remplace par → select * from staging.stg_arxiv_papers
```

### `{{ source('source_name', 'table_name') }}`

Référence une table brute (non gérée par dbt). La source doit être déclarée dans `schema.yml`. Seuls les modèles staging devraient utiliser `source()` — tous les autres utilisent `ref()`.

```sql
-- Dans stg_arxiv_papers.sql :
select * from {{ source('raw', 'arxiv_papers_raw') }}
-- dbt remplace par → select * from public.arxiv_papers_raw
```

---

## 9. Fonctions SQL PostgreSQL utilisées dans les modèles dbt

### `trim(col)` — Supprimer les espaces

Supprime les espaces en début et fin de chaîne. Équivalent Python : `str.strip()`.

```sql
trim(title) as title
```

### `length(col)` — Longueur d'une chaîne

Retourne le nombre de caractères. Équivalent Python : `len(str)`.

```sql
length(abstract) as abstract_length
```

### `split_part(col, sep, n)` — Extraire une partie

Découpe la chaîne par le séparateur et retourne la n-ème partie (indexé à partir de 1). Équivalent Python : `str.split(sep)[n-1]`.

```sql
split_part(primary_category, '.', 1) as domain
-- "cs.AI" → "cs"

split_part(categories, ' ', 1) as first_category
-- "cs.AI cs.LG stat.ML" → "cs.AI"
```

### `coalesce(a, b, ...)` — Première valeur non-null

Retourne la première valeur qui n'est pas null. Équivalent Python : `a if a is not None else b`.

```sql
coalesce(primary_category, split_part(categories, ' ', 1)) as primary_category
-- Si primary_category est null, on prend la première catégorie du tableau
```

### `string_to_array(col, sep)` — Chaîne → tableau

Transforme une chaîne en tableau PostgreSQL. Équivalent Python : `str.split(sep)`.

```sql
string_to_array(categories, ' ')
-- "cs.AI cs.LG stat.ML" → {"cs.AI", "cs.LG", "stat.ML"}
```

### `array_length(arr, dimension)` — Taille d'un tableau

Retourne le nombre d'éléments d'un tableau PostgreSQL. La dimension est presque toujours 1.

```sql
array_length(string_to_array(categories, ' '), 1) as num_categories
-- "cs.AI cs.LG stat.ML" → 3
```

### `unnest(array)` — Éclater un tableau en lignes

Transforme chaque élément du tableau en une ligne séparée. C'est l'opération inverse de l'agrégation — une ligne devient N lignes.

```sql
-- Si authors_flat = "Alice Martin, Bob Chen, Carol White"
trim(unnest(string_to_array(authors_flat, ','))) as author_name
-- Produit 3 lignes :
--   "Alice Martin"
--   "Bob Chen"
--   "Carol White"
```

**Attention** : `unnest` multiplie le nombre de lignes. Si un article a 5 auteurs, il produit 5 lignes — chacune avec le même `arxiv_id` mais un `author_name` différent.

### `date_trunc(interval, date)` — Tronquer une date

Arrondit une date au début de l'intervalle spécifié. Utilisé pour les agrégations temporelles.

```sql
date_trunc('month', date_updated::date)::date as mois
-- "2024-03-15" → "2024-03-01"
-- "2024-07-28" → "2024-07-01"
```

Intervalles possibles : `'year'`, `'quarter'`, `'month'`, `'week'`, `'day'`, `'hour'`.

### `col::type` — Conversion de type (cast)

Syntaxe PostgreSQL raccourcie pour la conversion de type.

```sql
date_updated::date                -- Chaîne → date
avg(abstract_length)::int         -- Float → entier (arrondi)
avg(num_categories)::numeric(3,1) -- Float → décimal avec 1 décimale
```

### `count(distinct col)` — Comptage de valeurs uniques

Compte le nombre de valeurs distinctes (ignore les doublons).

```sql
count(distinct arxiv_id)           as nb_publications
count(distinct primary_category)   as nb_categories
count(distinct domain)             as nb_domaines
```

### `mode() within group (order by col)` — Valeur la plus fréquente

Fonction d'agrégation PostgreSQL qui retourne la valeur la plus fréquente (le mode statistique). Spécifique à PostgreSQL (pas dans le SQL standard).

```sql
mode() within group (order by domain)             as domaine_principal
mode() within group (order by primary_category)   as categorie_principale
```

Si un auteur a publié 5 articles en cs.AI et 2 en cs.LG, `mode()` retourne `"cs.AI"`.

### `min(col)` / `max(col)` — Valeurs extrêmes

```sql
min(date_updated) as premiere_publication
max(date_updated) as derniere_publication
```

### Opérateurs de filtrage

```sql
-- Longueur minimale d'un nom
where length(author_name) > 2

-- Regex : le nom ne commence pas par un chiffre
where author_name !~ '^\d'

-- Null et chaîne vide
where authors_flat is not null and authors_flat != ''

-- Seuil minimum d'agrégation
where nb_publications >= 3
```

---

## 10. Commandes dbt CLI

| Commande | Rôle |
|----------|------|
| `dbt debug` | Tester la connexion PostgreSQL |
| `dbt run` | Exécuter tous les modèles (staging → marts) |
| `dbt test` | Lancer les tests déclarés dans `schema.yml` |
| `dbt docs generate` | Générer la documentation HTML interactive |
| `dbt docs serve --port 8081` | Lancer le serveur web de documentation |
| `dbt run --profiles-dir .` | Chercher `profiles.yml` dans le répertoire courant (nécessaire dans Docker) |

### Tests dbt dans `schema.yml`

Les tests sont déclarés dans le fichier YAML, pas dans du code :

```yaml
columns:
  - name: arxiv_id
    tests: [not_null, unique]       # Deux tests : pas de null, pas de doublons
  - name: primary_category
    tests: [not_null]
```

`dbt test` exécute chaque test comme un `SELECT` qui retourne les lignes en violation. Si le SELECT retourne 0 lignes → le test passe.

---

## 11. Configuration dbt (`dbt_project.yml` et `profiles.yml`)

### `dbt_project.yml` — Configuration du projet

```yaml
name: 'scipulse'
models:
  scipulse:
    staging:
      +schema: staging             # Les modèles staging vont dans le schéma PG "staging"
      +materialized: view          # Matérialisés en vue (pas de stockage physique)
    marts:
      +schema: marts               # Les modèles marts vont dans le schéma "marts"
      +materialized: table         # Matérialisés en table (stockage physique, recréés à chaque run)
```

### `profiles.yml` — Connexion PostgreSQL

```yaml
scipulse:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost        # ← "postgres" si exécuté depuis un conteneur Docker
      port: 5432
      user: scipulse
      password: scipulse
      dbname: scipulse
      schema: public
      threads: 4             # Nombre de modèles exécutés en parallèle
```

---

## 12. Bibliothèques standard Python

### `os.getenv(name, default)`

Lit une variable d'environnement. Utilisé pour la portabilité hôte/Docker.

```python
import os
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
```

### `time.time()`

Retourne le timestamp Unix en secondes. Utilisé pour mesurer les durées.

```python
import time
start = time.time()
# ... travail ...
elapsed = time.time() - start
print(f"Durée : {elapsed:.1f}s")
```

### `argparse.ArgumentParser`

Parse les arguments de la ligne de commande.

```python
import argparse
parser = argparse.ArgumentParser(description="SciPulse — Enrichissement ArXiv")
parser.add_argument("--max", type=int, default=50_000, help="Max articles")
parser.add_argument("--top-keywords", type=int, default=8, help="Mots-clés par article")
args = parser.parse_args()
```

### `sys.exit(code)`

Quitte le programme. `0` = succès, `1` = erreur.

```python
import sys
sys.exit(1)
```

---

## 13. Pattern « générateur » (yield) pour les actions bulk

Le mot-clé `yield` transforme une fonction en générateur : elle produit les éléments un par un sans les stocker tous en mémoire. C'est le pattern utilisé dans `enrich_arxiv.py` pour générer les actions de mise à jour :

```python
def generate_update_actions():
    for arxiv_id in all_ids:
        doc_update = {}

        kw = keywords_map.get(arxiv_id)
        if kw:
            doc_update["keywords"] = kw

        hn = hn_scores.get(arxiv_id)
        if hn:
            doc_update["hn_score"] = hn["hn_score"]

        if doc_update:
            yield {                           # ← yield, pas return ni append
                "_op_type": "update",
                "_index": "arxiv-papers",
                "_id": arxiv_id,
                "doc": doc_update,
                "doc_as_upsert": False,
            }
```

Ce générateur est consommé par `helpers.streaming_bulk` qui tire les actions une par une, les regroupe en lots, et les envoie à ES.

---

## 14. Récapitulatif du flux de données du TP

```
Elasticsearch (arxiv-papers)
         │
    helpers.scan()               ← Extraction
         │
         ▼
    pd.DataFrame()               ← Structuration
         │
    ┌────┴────┐
    ▼         ▼
psycopg2   TfidfVectorizer       ← Transformation / Enrichissement
    │         │
    ▼         ▼
PostgreSQL  keywords_map (dict)   ← Résultats intermédiaires
    │         │
 dbt run      │
    │         ▼
    ▼    helpers.streaming_bulk   ← Mise à jour ES
marts PG       │
               ▼
         Elasticsearch            ← Données enrichies
         (arxiv-papers)
```
