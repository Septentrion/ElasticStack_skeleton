# Jour 3 — Matin
# TP : Pipeline de transformation et enrichissement croisé

> **Durée** : 2h45  
> **Niveau** : débutant — chaque étape est détaillée  
> **Prérequis** : Jour 2 complété (index `arxiv-papers` avec 100k docs, `hn-items` avec quelques dizaines de docs, stack Docker lancée)

---

## Ce que vous allez construire

À la fin de ce TP, vous aurez :

1. Les données ArXiv chargées dans PostgreSQL (miroir tabulaire pour dbt).
2. Deux modèles dbt fonctionnels : un staging et un mart.
3. Des tests dbt exécutés et passants.
4. Un script Python d'enrichissement qui extrait les mots-clés (TF-IDF) et croise ArXiv × HN.
5. L'index `arxiv-papers` enrichi avec les mots-clés et les scores HN.

---

## Vérifications préalables (5 min)

```bash
# Stack Docker OK ?
docker compose ps

# Index ArXiv peuplé ?
curl -s http://localhost:9200/arxiv-papers/_count
# → ~100 000

# PostgreSQL accessible ?
docker exec -it scipulse-postgres psql -U scipulse -d scipulse -c "SELECT 1;"
# → Doit retourner "1"

# dbt installé ?
dbt --version
# → Si "command not found" : pip install dbt-postgres
```

---

# PARTIE A — Chargement dans PostgreSQL (25 min)

## Étape 1 — Pourquoi PostgreSQL en plus d'Elasticsearch ?

Elasticsearch est excellent pour la recherche full-text et les agrégations, mais il n'est pas conçu pour les jointures SQL, les fenêtres analytiques, ou la modélisation dimensionnelle. PostgreSQL complète ES pour les transformations tabulaires classiques.

Le flux est : ES (données indexées) → export vers PG → dbt (transformations SQL) → résultats utilisables par les dashboards et le script d'enrichissement.

## Étape 2 — Script de chargement ES → PostgreSQL

Créez `src/transformation/load_to_postgres.py` :

```python
"""
SciPulse — Chargement des données ArXiv depuis Elasticsearch vers PostgreSQL
Crée un miroir tabulaire pour les transformations dbt.

Usage :
    python -m src.transformation.load_to_postgres
"""

import sys
import time

import pandas as pd
import psycopg
from psycopg.extras import execute_values
from elasticsearch import Elasticsearch, helpers

ES_HOST = "http://localhost:9200"
PG_DSN  = "host=localhost port=5432 dbname=scipulse user=scipulse password=scipulse"


def extract_from_es(es: Elasticsearch, max_docs: int = 200_000) -> pd.DataFrame:
    """
    Extrait les articles ArXiv depuis Elasticsearch.
    Construit un dataframe.
    """

    return df


def load_to_postgres(df: pd.DataFrame):
    """
    Charge le DataFrame dans PostgreSQL.
    """

    # 1. Connexion à PostgreSQL
    pass

    # 1. Créer la table (DROP + CREATE pour idempotence)
    pass
    print("   ✅ Table 'arxiv_papers_raw' créée")

    # 3. Insérer par batch
    columns = [
        "arxiv_id", "title", "abstract", "authors_flat",
        "categories", "primary_category", "date_published",
        "date_updated", "doi",
    ]

    pass
    
    # Vérification
    cur.execute("SELECT COUNT(*) FROM public.arxiv_papers_raw;")
    count = cur.fetchone()[0]
    print(f"   ✅ {count:,} lignes insérées en {elapsed:.1f}s")

    cur.close()
    conn.close()


if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SciPulse — Chargement ArXiv → PostgreSQL               ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # 1. Connexion à Elasticsearch
    pass
    
    # 2. Extraction des données

    # 3. Chargement des données dans PostgreSQL

    print("\n🎉 Données prêtes pour dbt !")
    print("   Vérifiez : docker exec -it scipulse-postgres psql -U scipulse -d scipulse -c \"SELECT COUNT(*) FROM arxiv_papers_raw;\"")
    print()
```

### Exécuter le chargement

```bash
python -m src.transformation.load_to_postgres
```

Sortie attendue :

```
📥 Extraction depuis Elasticsearch...
    25,000 extraits...
    50,000 extraits...
    75,000 extraits...
   100,000 extraits...
   ✅ 100,000 articles extraits depuis Elasticsearch

📤 Chargement dans PostgreSQL...
   ✅ Table 'arxiv_papers_raw' créée
   ✅ 100,000 lignes insérées en 12.3s

🎉 Données prêtes pour dbt !
```

### Vérifier dans PostgreSQL

```bash
docker exec -it scipulse-postgres psql -U scipulse -d scipulse
```

Dans le shell `psql` :

```sql
-- Nombre de lignes
SELECT COUNT(*) FROM arxiv_papers_raw;

-- Aperçu
SELECT arxiv_id, primary_category, LEFT(title, 50) FROM arxiv_papers_raw LIMIT 5;

-- Top catégories
SELECT primary_category, COUNT(*) as n
FROM arxiv_papers_raw
GROUP BY primary_category
ORDER BY n DESC
LIMIT 10;

-- Quitter psql
\q
```

---

# PARTIE B — Transformations dbt (50 min)

## Étape 3 — Configurer dbt (10 min)

### 3.1. Vérifier le projet dbt

Le starter kit contient déjà un projet dbt dans le dossier `dbt/`. Vérifions sa structure :

```bash
ls dbt/
# → dbt_project.yml  macros/  models/  profiles.yml  tests/
```

### 3.2. Vérifier la connexion

```bash
cd dbt
dbt debug
```

Vous devez voir :

```
  Connection test: [OK connection ok]
```

Si la connexion échoue, vérifiez `dbt/profiles.yml` :

```yaml
scipulse:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      port: 5432
      user: scipulse
      password: scipulse
      dbname: scipulse
      schema: public
      threads: 4
```

**Si vous êtes dans un conteneur Docker** (pas en local), remplacez `host: localhost` par `host: postgres`.

## Étape 4 — Comprendre et compléter les modèles dbt (25 min)

### 4.1. Le modèle staging

Le fichier `dbt/models/staging/stg_arxiv_papers.sql` existe déjà dans le starter kit. Ouvrons-le :

```bash
code dbt/models/staging/stg_arxiv_papers.sql
```

Ce modèle fait le nettoyage de base :

- Filtre les lignes sans `arxiv_id` ni `abstract`.
- Extrait la catégorie primaire et le domaine.
- Calcule la longueur de l'abstract et le nombre de catégories.

Vérifiez que la requête `source('raw', 'arxiv_papers_raw')` correspond bien à la table que nous venons de créer.

### 4.2. Déclarer la source

Le fichier `dbt/models/schema.yml` du starter kit déclare déjà la source. Vérifions :

```yaml
sources:
  - name: raw
    schema: public
    tables:
      - name: arxiv_papers_raw
```

### 4.3. Créer un nouveau modèle mart — Top auteurs

Créez le fichier `dbt/models/marts/fct_auteurs_prolifiques.sql` :

```sql
-- =============================================================================
--  fct_auteurs_prolifiques.sql
--  Mart : classement des auteurs par nombre de publications
--
--  Ce modèle dépend de stg_arxiv_papers (via ref()).
--  dbt exécutera stg_arxiv_papers en premier automatiquement.
-- =============================================================================

with papers as (
    select * from {{ ref('stg_arxiv_papers') }}
),

-- Éclater les auteurs (un auteur par ligne)
-- Le champ authors_flat contient "Alice Martin, Bob Chen, ..."
-- On utilise unnest + string_to_array pour séparer
authors_exploded as (
    select
        arxiv_id,
        primary_category,
        domain,
        date_published,
        trim(unnest(string_to_array(authors_flat, ','))) as author_name
    from papers
    where authors_flat is not null
      and authors_flat != ''
),

-- Agréger par auteur
author_stats as (
    select
        author_name,
        count(distinct arxiv_id)                    as nb_publications,
        count(distinct primary_category)            as nb_categories,
        min(date_published)                         as premiere_publication,
        max(date_published)                         as derniere_publication,
        mode() within group (order by domain)       as domaine_principal
    from authors_exploded
    where length(author_name) > 2     -- Filtrer les artefacts de parsing
    group by author_name
)

select
    author_name,
    nb_publications,
    nb_categories,
    premiere_publication,
    derniere_publication,
    domaine_principal,
    -- Score d'activité : publications × diversité
    nb_publications * nb_categories                 as score_activite
from author_stats
where nb_publications >= 3     -- Au moins 3 publications
order by nb_publications desc
```

### 4.4. Ajouter les tests pour le nouveau modèle

Ouvrez `dbt/models/schema.yml` et ajoutez le nouveau modèle dans la section `models` :

```yaml
  - name: fct_auteurs_prolifiques
    description: "Classement des auteurs par nombre de publications et diversité"
    columns:
      - name: author_name
        tests: [not_null]
      - name: nb_publications
        tests:
          - not_null
```

### 4.5. Exécuter dbt

```bash
# Depuis le dossier dbt/
cd dbt

# Exécuter tous les modèles
dbt run
```

Sortie attendue :

```
Running with dbt=1.7.x

Found 3 models, 6 tests, 1 source

Concurrency: 4 threads (target='dev')

1 of 3 START sql view model staging.stg_arxiv_papers .............. [RUN]
1 of 3 OK created sql view model staging.stg_arxiv_papers ......... [CREATE VIEW in 0.42s]
2 of 3 START sql table model marts.fct_publications_par_mois ....... [RUN]
3 of 3 START sql table model marts.fct_auteurs_prolifiques ......... [RUN]
2 of 3 OK created sql table model marts.fct_publications_par_mois . [SELECT 2847 in 3.21s]
3 of 3 OK created sql table model marts.fct_auteurs_prolifiques ... [SELECT 18432 in 5.67s]

Completed successfully

Done. PASS=3 WARN=0 ERROR=0 SKIP=0 TOTAL=3
```

### 4.6. Exécuter les tests dbt

```bash
dbt test
```

Sortie attendue :

```
Found 3 models, 6 tests, 1 source

1 of 6 START test not_null_stg_arxiv_papers_arxiv_id .............. [PASS in 0.31s]
2 of 6 START test unique_stg_arxiv_papers_arxiv_id ................ [PASS in 0.28s]
3 of 6 START test not_null_stg_arxiv_papers_primary_category ...... [PASS in 0.25s]
...

Completed successfully

Done. PASS=6 WARN=0 ERROR=0 SKIP=0 TOTAL=6
```

Si un test échoue, dbt affiche les lignes en violation. Corrigez le modèle ou ajustez le test.

### 4.7. Explorer les résultats dans PostgreSQL

```bash
docker exec -it scipulse-postgres psql -U scipulse -d scipulse
```

```sql
-- Top 10 des auteurs les plus prolifiques
SELECT author_name, nb_publications, nb_categories, domaine_principal
FROM marts.fct_auteurs_prolifiques
ORDER BY nb_publications DESC
LIMIT 10;

-- Publications par mois (dernière année)
SELECT mois, primary_category, nb_publications
FROM marts.fct_publications_par_mois
WHERE mois >= '2023-01-01'
ORDER BY mois DESC, nb_publications DESC
LIMIT 20;

\q
```

### 4.8. Générer la documentation dbt

```bash
dbt docs generate
dbt docs serve --port 8081
```

Ouvrez http://localhost:8081. Explorez :

- Le graphe de lignage (icône en bas à droite) : vous verrez `arxiv_papers_raw` → `stg_arxiv_papers` → `fct_publications_par_mois` et → `fct_auteurs_prolifiques`.
- La description de chaque modèle.
- Les résultats des tests.

Appuyez sur `Ctrl+C` pour arrêter le serveur docs.

```bash
# Revenir à la racine du projet
cd ..
```

---

# PARTIE C — Enrichissement Python (50 min)

## Étape 5 — Extraction de mots-clés par TF-IDF (25 min)

### 5.1. Créer le script d'enrichissement

Créez `src/enrichment/enrich_arxiv.py` :

```python
"""
SciPulse — Enrichissement des articles ArXiv

Ce script :
  1. Extrait les abstracts depuis Elasticsearch
  2. Calcule les mots-clés par TF-IDF (scikit-learn)
  3. Détecte les liens ArXiv dans les posts Hacker News
  4. Injecte les scores HN croisés dans les articles ArXiv
  5. Met à jour l'index Elasticsearch

Usage :
    python -m src.enrichment.enrich_arxiv
    python -m src.enrichment.enrich_arxiv --max 10000    # Limiter l'échantillon
    python -m src.enrichment.enrich_arxiv --top-keywords 10
"""

import argparse
import sys
import time

import numpy as np
from elasticsearch import Elasticsearch, helpers
from sklearn.feature_extraction.text import TfidfVectorizer

ES_HOST = "http://localhost:9200"


# ═════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 1 : EXTRACTION DE MOTS-CLÉS PAR TF-IDF
# ═════════════════════════════════════════════════════════════════════════════

def extract_keywords_tfidf(
    es: Elasticsearch,
    index: str = "arxiv-papers",
    max_docs: int = 50_000,
    top_n: int = 8,
) -> dict[str, list[str]]:
    """
    Extrait les mots-clés de chaque article via TF-IDF.

    Paramètres
    ----------
    es : Elasticsearch client
    index : nom de l'index
    max_docs : nombre max d'articles à traiter
    top_n : nombre de mots-clés par article

    Retourne
    --------
    dict[str, list[str]]
        { arxiv_id: [keyword1, keyword2, ...], ... }
    """
    print(f"  📖 Extraction des abstracts (max {max_docs:,})...")

    # Collecter les articles (ID + abstract)
    articles = []
    for hit in helpers.scan(es, index=index, query={"query": {"match_all": {}}}, size=1000):
        src = hit["_source"]
        arxiv_id = src.get("arxiv_id")
        abstract = src.get("abstract", "")
        if arxiv_id and abstract and len(abstract) > 50:
            articles.append((arxiv_id, abstract))
        if len(articles) >= max_docs:
            break

    print(f"     {len(articles):,} articles avec abstract valide")

    if not articles:
        return {}

    ids = [a[0] for a in articles]
    abstracts = [a[1] for a in articles]

    # Calculer la matrice TF-IDF
    print(f"  🧮 Calcul TF-IDF...")
    start = time.time()

    vectorizer = TfidfVectorizer(
        max_features=5000,      # Vocabulaire limité aux 5000 termes les plus fréquents
        stop_words="english",   # Supprimer les stopwords anglais
        min_df=5,               # Ignorer les termes qui apparaissent dans < 5 documents
        max_df=0.7,             # Ignorer les termes qui apparaissent dans > 70% des documents
        ngram_range=(1, 2),     # Unigrammes et bigrammes (ex: "neural network")
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",  # Mots de 2+ lettres uniquement
    )

    tfidf_matrix = vectorizer.fit_transform(abstracts)
    feature_names = vectorizer.get_feature_names_out()

    elapsed = time.time() - start
    print(f"     Matrice {tfidf_matrix.shape[0]} docs × {tfidf_matrix.shape[1]} termes ({elapsed:.1f}s)")

    # Extraire les top_n mots-clés par article
    print(f"  🏷  Extraction des top {top_n} mots-clés par article...")

    keywords_map = {}
    for i, arxiv_id in enumerate(ids):
        row = tfidf_matrix[i].toarray().flatten()
        top_indices = row.argsort()[-top_n:][::-1]
        keywords = [feature_names[j] for j in top_indices if row[j] > 0]
        keywords_map[arxiv_id] = keywords

    non_empty = sum(1 for v in keywords_map.values() if v)
    print(f"     {non_empty:,} articles ont des mots-clés")

    return keywords_map


# ═════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 2 : CROISEMENT ARXIV × HACKER NEWS
# ═════════════════════════════════════════════════════════════════════════════

def load_hn_scores(es: Elasticsearch) -> dict[str, dict]:
    """
    Charge les liens ArXiv↔HN depuis l'index arxiv-hn-links.
    Agrège les scores HN par arxiv_id.

    Retourne
    --------
    dict[str, dict]
        { arxiv_id: { "hn_score": total, "hn_comments_count": total, "hn_item_ids": [...] }, ... }
    """
    print(f"  🔗 Chargement des liens ArXiv ↔ HN...")

    if not es.indices.exists(index="arxiv-hn-links"):
        print(f"     ⚠️  Index 'arxiv-hn-links' n'existe pas — pas de scores HN")
        return {}

    count = es.count(index="arxiv-hn-links")["count"]
    if count == 0:
        print(f"     ⚠️  Aucun lien trouvé — pas de scores HN")
        return {}

    hn_data = {}
    for hit in helpers.scan(es, index="arxiv-hn-links", query={"query": {"match_all": {}}}):
        src = hit["_source"]
        arxiv_id = src.get("arxiv_id")
        if not arxiv_id:
            continue

        if arxiv_id not in hn_data:
            hn_data[arxiv_id] = {"hn_score": 0, "hn_comments_count": 0, "hn_item_ids": []}

        hn_data[arxiv_id]["hn_score"] += src.get("hn_score", 0) or 0
        hn_data[arxiv_id]["hn_comments_count"] += src.get("hn_comments", 0) or 0
        hn_data[arxiv_id]["hn_item_ids"].append(src.get("hn_item_id", ""))

    print(f"     {len(hn_data):,} articles ArXiv liés à des posts HN (sur {count} liens)")
    return hn_data


# ═════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 3 : MISE À JOUR DE L'INDEX ELASTICSEARCH
# ═════════════════════════════════════════════════════════════════════════════

def update_index(
    es: Elasticsearch,
    keywords_map: dict[str, list[str]],
    hn_scores: dict[str, dict],
    index: str = "arxiv-papers",
):
    """
    Met à jour les articles dans ES avec les mots-clés et scores HN.
    Utilise l'API _update (partial update) pour ne pas écraser les champs existants.
    """
    # Fusionner les deux sources d'enrichissement
    all_ids = set(list(keywords_map.keys()) + list(hn_scores.keys()))
    print(f"\n  📝 Mise à jour de {len(all_ids):,} articles dans '{index}'...")

    def generate_update_actions():
        for arxiv_id in all_ids:
            doc_update = {}

            # Mots-clés TF-IDF
            kw = keywords_map.get(arxiv_id)
            if kw:
                doc_update["keywords"] = kw

            # Scores HN
            hn = hn_scores.get(arxiv_id)
            if hn:
                doc_update["hn_score"] = hn["hn_score"]
                doc_update["hn_comments_count"] = hn["hn_comments_count"]
                doc_update["hn_item_ids"] = hn["hn_item_ids"]

            if doc_update:
                yield {
                    "_op_type": "update",
                    "_index": index,
                    "_id": arxiv_id,
                    "doc": doc_update,
                    "doc_as_upsert": False,
                }

    start = time.time()
    success = 0
    errors = 0

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

        total = success + errors
        if total % 10_000 == 0 and total > 0:
            print(f"     {total:>7,} mis à jour...")

    elapsed = time.time() - start
    es.indices.refresh(index=index)

    print(f"\n  ✅ {success:,} articles mis à jour en {elapsed:.1f}s")
    if errors > 0:
        print(f"  ❌ {errors:,} erreurs (articles probablement absents de l'index)")


# ═════════════════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="SciPulse — Enrichissement ArXiv")
    parser.add_argument("--max", type=int, default=50_000, help="Max articles pour TF-IDF (défaut: 50000)")
    parser.add_argument("--top-keywords", type=int, default=8, help="Mots-clés par article (défaut: 8)")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SciPulse — Enrichissement ArXiv                        ║")
    print("║  TF-IDF + croisement Hacker News                        ║")
    print("╚══════════════════════════════════════════════════════════╝")

    es = Elasticsearch(ES_HOST)
    try:
        es.info()
    except Exception as e:
        print(f"\n❌ Elasticsearch non accessible : {e}")
        sys.exit(1)

    # Étape 1 : Mots-clés TF-IDF
    print("\n🧠 ÉTAPE 1 — Extraction de mots-clés par TF-IDF\n")
    keywords_map = extract_keywords_tfidf(es, max_docs=args.max, top_n=args.top_keywords)

    # Aperçu
    if keywords_map:
        sample_id = list(keywords_map.keys())[0]
        print(f"\n  📋 Exemple — {sample_id} :")
        print(f"     Mots-clés : {keywords_map[sample_id]}")

    # Étape 2 : Scores HN
    print(f"\n🔗 ÉTAPE 2 — Croisement ArXiv × Hacker News\n")
    hn_scores = load_hn_scores(es)

    if hn_scores:
        sample_id = list(hn_scores.keys())[0]
        sample = hn_scores[sample_id]
        print(f"\n  📋 Exemple — {sample_id} :")
        print(f"     Score HN : {sample['hn_score']}, Commentaires : {sample['hn_comments_count']}")

    # Étape 3 : Mise à jour
    print(f"\n📤 ÉTAPE 3 — Mise à jour de l'index Elasticsearch\n")
    update_index(es, keywords_map, hn_scores)

    # Vérification
    print(f"\n🔍 Vérification...")
    sample = es.search(
        index="arxiv-papers",
        query={"exists": {"field": "keywords"}},
        size=1,
        _source=["arxiv_id", "title", "keywords", "hn_score"],
    )
    if sample["hits"]["hits"]:
        hit = sample["hits"]["hits"][0]["_source"]
        print(f"  Exemple d'article enrichi :")
        print(f"    ID       : {hit.get('arxiv_id')}")
        print(f"    Titre    : {hit.get('title', '')[:60]}")
        print(f"    Mots-clés: {hit.get('keywords', [])}")
        print(f"    Score HN : {hit.get('hn_score', 'N/A')}")

    # Statistiques finales
    kw_count = es.count(index="arxiv-papers", query={"exists": {"field": "keywords"}})["count"]
    hn_count = es.count(index="arxiv-papers", query={"exists": {"field": "hn_score"}})["count"]
    print(f"\n  📊 Articles avec mots-clés : {kw_count:,}")
    print(f"  📊 Articles avec score HN  : {hn_count:,}")

    print(f"\n🎉 Enrichissement terminé !")
    print()


if __name__ == "__main__":
    main()
```

### 5.2. Exécuter l'enrichissement

```bash
# Commencer avec un échantillon de 10 000 articles (rapide)
python -m src.enrichment.enrich_arxiv --max 10000

# Puis sur le corpus complet (prend 1-3 minutes)
python -m src.enrichment.enrich_arxiv
```

Sortie attendue :

```
╔══════════════════════════════════════════════════════════╗
║  SciPulse — Enrichissement ArXiv                        ║
║  TF-IDF + croisement Hacker News                        ║
╚══════════════════════════════════════════════════════════╝

🧠 ÉTAPE 1 — Extraction de mots-clés par TF-IDF

  📖 Extraction des abstracts (max 50,000)...
     47,832 articles avec abstract valide
  🧮 Calcul TF-IDF...
     Matrice 47832 docs × 5000 termes (2.1s)
  🏷  Extraction des top 8 mots-clés par article...
     47,832 articles ont des mots-clés

  📋 Exemple — 2301.07041 :
     Mots-clés : ['generative', 'content', 'aigc', 'diffusion', 'model', ...]

🔗 ÉTAPE 2 — Croisement ArXiv × Hacker News

  🔗 Chargement des liens ArXiv ↔ HN...
     12 articles ArXiv liés à des posts HN (sur 15 liens)

📤 ÉTAPE 3 — Mise à jour de l'index Elasticsearch

  📝 Mise à jour de 47,838 articles dans 'arxiv-papers'...
     10,000 mis à jour...
     ...
  ✅ 47,838 articles mis à jour en 18.4s

🔍 Vérification...
  Exemple d'article enrichi :
    ID       : 2301.07041
    Titre    : A Comprehensive Survey of AI-Generated Content (AIGC)
    Mots-clés: ['generative', 'content', 'aigc', 'diffusion', 'model', ...]
    Score HN : N/A

  📊 Articles avec mots-clés : 47,832
  📊 Articles avec score HN  : 12

🎉 Enrichissement terminé !
```

---

## Étape 6 — Vérifier l'enrichissement dans Kibana (10 min)

### 6.1. Vérifier les mots-clés

Dans Kibana Dev Tools :

```
GET /arxiv-papers/_search
{
  "query": { "exists": { "field": "keywords" } },
  "size": 3,
  "_source": ["arxiv_id", "title", "keywords"]
}
```

Vérifiez que le champ `keywords` contient des termes pertinents pour chaque article.

### 6.2. Agrégation sur les mots-clés

```
GET /arxiv-papers/_search
{
  "size": 0,
  "aggs": {
    "top_keywords": {
      "terms": { "field": "keywords", "size": 20 }
    }
  }
}
```

Vous devriez voir les mots-clés les plus fréquents du corpus : `learning`, `model`, `neural network`, `algorithm`, `deep learning`…

### 6.3. Vérifier le croisement HN

```
GET /arxiv-papers/_search
{
  "query": {
    "bool": {
      "must": [
        { "exists": { "field": "hn_score" } },
        { "range": { "hn_score": { "gt": 0 } } }
      ]
    }
  },
  "size": 5,
  "_source": ["arxiv_id", "title", "hn_score", "hn_comments_count", "hn_item_ids"],
  "sort": [{ "hn_score": "desc" }]
}
```

Si vous avez des résultats, vous voyez les articles ArXiv les plus populaires sur Hacker News — triés par score décroissant. Si aucun résultat, c'est normal : les liens ArXiv sur HN sont peu fréquents et dépendent de ce que le poller a capturé.

---

## Étape 7 — Commit (5 min)

```bash
git add src/transformation/load_to_postgres.py
git add src/enrichment/enrich_arxiv.py
git add dbt/models/marts/fct_auteurs_prolifiques.sql
git add dbt/models/schema.yml
git commit -m "feat: add dbt transformations + TF-IDF enrichment + HN cross-scores"
```

---

## Checklist de fin de matinée

- [ ] Données ArXiv chargées dans PostgreSQL (100k lignes dans `arxiv_papers_raw`)
- [ ] Modèle staging `stg_arxiv_papers` créé et fonctionnel (vue)
- [ ] Modèle mart `fct_publications_par_mois` créé et fonctionnel (table)
- [ ] Modèle mart `fct_auteurs_prolifiques` créé et fonctionnel (table)
- [ ] Tests dbt passants (6+ tests)
- [ ] Documentation dbt générée et consultée
- [ ] Enrichissement TF-IDF exécuté (mots-clés ajoutés aux articles)
- [ ] Croisement ArXiv × HN exécuté (scores HN ajoutés quand disponibles)
- [ ] Vérification dans Kibana (agrégation sur les keywords, articles avec score HN)
- [ ] Commit Git propre

## Ce qui vient cet après-midi

Cet après-midi est le moment le plus attendu du cours : la **fouille de texte avancée** avec Elasticsearch. Maintenant que nos données sont enrichies (mots-clés, scores HN, analyseur custom), nous allons exploiter toute la puissance d'ES : `more_like_this` pour trouver des articles similaires, `significant_terms` pour détecter des tendances émergentes, `function_score` pour combiner pertinence textuelle et popularité HN, et les requêtes `has_child` pour naviguer les commentaires.
