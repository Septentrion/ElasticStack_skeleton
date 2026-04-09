# Mémento Elasticsearch

> Toutes les fonctions essentielles du TP « Fouille de texte » et de l'examen — avec exemples prêts à coller dans Kibana Dev Tools.

---

## Recherche full-text

### `match`

Recherche plein texte sur un seul champ. Par défaut, les termes sont combinés avec OR (un seul suffit). On peut passer `"operator": "and"` pour exiger tous les termes, ou `"minimum_should_match": "75%"` pour doser la précision.

```json
{
  "query": {
    "match": {
      "abstract": {
        "query": "reinforcement learning",
        "operator": "and"
      }
    }
  }
}
```

### `multi_match`

Recherche sur plusieurs champs à la fois. Le suffixe `^N` applique un boost : un match dans le titre pondéré `^3` vaut 3× un match dans l'abstract. Le mode `cross_fields` traite les champs comme un seul grand texte.

```json
{
  "query": {
    "multi_match": {
      "query": "generative adversarial network",
      "fields": ["title^3", "abstract"],
      "type": "cross_fields"
    }
  }
}
```

### `match_phrase`

Recherche d'une phrase exacte : les termes doivent apparaître dans l'ordre. Le paramètre `slop` autorise N mots intercalés (slop 0 = strictement adjacent, slop 3 = jusqu'à 3 mots entre les termes).

```json
{
  "query": {
    "match_phrase": {
      "abstract": {
        "query": "attention mechanism",
        "slop": 2
      }
    }
  }
}
```

### `wildcard`

Recherche par motif avec `*` (zéro ou plusieurs caractères) et `?` (un seul caractère). À utiliser sur des champs `.keyword` (valeurs non analysées). Pratique pour chercher des noms d'auteurs par préfixe partiel, mais coûteux en performance sur de gros index.

```json
{
  "query": {
    "wildcard": {
      "authors_parsed.keyword": { "value": "Ben*" }
    }
  }
}
```

### `prefix`

Recherche tous les termes commençant par un préfixe donné. Plus efficace que `wildcard` quand on n'a besoin que d'un préfixe (pas de `*` au milieu). Se combine bien avec `highlight` pour visualiser les termes matchés.

```json
{
  "query": {
    "prefix": {
      "abstract": { "value": "optim" }
    }
  }
}
```

### `fuzzy`

Tolère les fautes de frappe en recherchant les termes à une distance d'édition (Levenshtein) donnée. `fuzziness: 2` autorise jusqu'à 2 caractères différents. Peut aussi s'utiliser comme option de `match` : `{ "match": { "title": { "query": "reinfrocement", "fuzziness": 2 }}}`.

```json
{
  "query": {
    "fuzzy": {
      "title": { "value": "reinfrocement", "fuzziness": 2 }
    }
  }
}
```

---

## Requête composée

### `bool`

Combine plusieurs clauses : `must` (obligatoire, contribue au score), `filter` (obligatoire, sans score — plus rapide), `should` (bonus optionnel), `must_not` (exclut). C'est la brique de base de toute requête complexe.

```json
{
  "query": {
    "bool": {
      "must":     [{ "match": { "abstract": "transformer" }}],
      "filter":   [{ "term": { "primary_category": "cs.CL" }},
                   { "range": { "date_updated": { "gte": "2023-01-01" }}}],
      "should":   [{ "exists": { "field": "hn_score" }}],
      "must_not": [{ "match": { "title": "survey" }}]
    }
  }
}
```

---

## Scoring avancé

### `function_score`

Modifie le score BM25 avec des fonctions supplémentaires. `gauss` applique un déclin temporel (les articles récents sont favorisés). `field_value_factor` booste selon la valeur d'un champ numérique (ex. popularité HN). `boost_mode` détermine comment combiner le score original et les fonctions (multiply, sum…).

```json
{
  "query": {
    "function_score": {
      "query": { "match": { "abstract": "language model" }},
      "functions": [
        { "gauss": { "date_updated": {
            "origin": "now", "scale": "365d", "decay": 0.5 }}},
        { "field_value_factor": {
            "field": "hn_score", "modifier": "log1p", "missing": 1 }}
      ],
      "boost_mode": "multiply"
    }
  }
}
```

### `script_score`

Remplace entièrement le calcul de score par un script Painless personnalisé. Plus flexible que `function_score` : on peut accéder à n'importe quel champ du document via `doc['champ']` et combiner `_score` (le BM25 original) avec une logique arbitraire. Penser à protéger les champs potentiellement absents avec `doc.containsKey(...)`.

```json
{
  "query": {
    "script_score": {
      "query": { "match": { "title": "BERT" }},
      "script": {
        "source": "return _score * Math.log(1 + doc['versions.keyword'].size())"
      }
    }
  }
}
```

---

## Similarité

### `more_like_this`

Trouve les documents les plus similaires à un document de référence (par son ID) ou à un texte libre. Elasticsearch extrait les termes représentatifs du document source et lance une recherche avec. Utile pour la recommandation « articles similaires ».

```json
{
  "query": {
    "more_like_this": {
      "fields": ["title", "abstract"],
      "like": [{ "_index": "arxiv-papers", "_id": "2106.09685" }],
      "min_term_freq": 1,
      "max_query_terms": 25,
      "min_doc_freq": 2
    }
  }
}
```

---

## Affichage & suggestions

### `highlight`

Retourne des fragments de texte avec les termes matchés entourés de balises personnalisables. Indispensable pour montrer à l'utilisateur *pourquoi* un résultat est pertinent. `fragment_size` contrôle la longueur du fragment, `number_of_fragments` le nombre retourné.

```json
{
  "highlight": {
    "fields": {
      "title": {},
      "abstract": { "fragment_size": 200, "number_of_fragments": 2 }
    },
    "pre_tags": ["<mark>"],
    "post_tags": ["</mark>"]
  }
}
```

### `suggest` (phrase)

Corrige les fautes de frappe en proposant des alternatives basées sur les termes réellement présents dans l'index. Le `phrase` suggester utilise des n-grams pour proposer des corrections de phrases entières (ex. « convlutional nueral » → « convolutional neural »).

```json
{
  "suggest": {
    "correction": {
      "text": "convlutional nueral network",
      "phrase": {
        "field": "title",
        "size": 3,
        "gram_size": 3,
        "direct_generator": [
          { "field": "title", "suggest_mode": "popular" }
        ]
      }
    }
  }
}
```

### `suggest` (completion)

Autocomplétion ultra-rapide : retourne les valeurs d'un champ de type `completion` commençant par le préfixe tapé. Optimisé pour le temps réel (stocké en mémoire sous forme de FST).

```json
{
  "suggest": {
    "title_autocomplete": {
      "prefix": "deep rein",
      "completion": {
        "field": "title.suggest",
        "size": 5,
        "skip_duplicates": true
      }
    }
  }
}
```

---

## Agrégations

### `terms`

Retourne les N valeurs les plus fréquentes d'un champ (équivalent d'un `GROUP BY … ORDER BY COUNT DESC`). Sert à construire des facettes de filtrage (catégories, auteurs…).

```json
{
  "size": 0,
  "aggs": {
    "par_categorie": {
      "terms": { "field": "primary_category", "size": 10 }
    }
  }
}
```

### `significant_terms`

Compare un sous-ensemble de documents (défini par la query) au corpus global et identifie les termes *statistiquement sur-représentés*. Beaucoup plus informatif que `terms` pour détecter des tendances : un terme fréquent globalement (« model ») ne ressort pas, mais un terme émergent (« rlhf ») oui.

```json
{
  "size": 0,
  "query": { "range": { "date_updated": { "gte": "2023-06-01" }}},
  "aggs": {
    "tendances": {
      "significant_terms": {
        "field": "abstract",
        "size": 20,
        "min_doc_count": 10
      }
    }
  }
}
```

### `date_histogram`

Découpe un champ date en intervalles réguliers (jour, semaine, mois, année…) et compte les documents dans chaque bucket. Idéal pour tracer des courbes d'évolution temporelle.

```json
{
  "size": 0,
  "aggs": {
    "par_mois": {
      "date_histogram": {
        "field": "date_updated",
        "calendar_interval": "month"
      }
    }
  }
}
```

### `sampler`

Limite le nombre de documents passés aux sous-agrégations (`shard_size` documents par shard). Utile avec `significant_terms` pour gagner en performance sur de gros index sans sacrifier la qualité statistique.

```json
{
  "aggs": {
    "echantillon": {
      "sampler": { "shard_size": 5000 },
      "aggs": {
        "termes": {
          "significant_terms": { "field": "abstract", "size": 15 }
        }
      }
    }
  }
}
```

### `value_count`

Agrégation métrique qui compte le nombre de valeurs (non-null) d'un champ dans chaque bucket. Utile comme base pour des agrégations pipeline en aval.

```json
{
  "aggs": {
    "nb_articles": {
      "value_count": { "field": "_id" }
    }
  }
}
```

### `moving_fn` (agrégation pipeline parent)

Applique une fonction glissante (moyenne mobile, dérivée…) sur les valeurs d'une agrégation sœur, bucket par bucket. `window` définit le nombre de buckets précédents pris en compte. Fonctionne à l'intérieur d'un `date_histogram` ou `histogram`.

```json
{
  "aggs": {
    "par_annee": {
      "date_histogram": { "field": "update_date", "calendar_interval": "year" },
      "aggs": {
        "nb": { "value_count": { "field": "_id" }},
        "moyenne_mobile": {
          "moving_fn": {
            "buckets_path": "nb",
            "window": 2,
            "script": "MovingFunctions.unweightedAvg(values)"
          }
        }
      }
    }
  }
}
```

### `sum_bucket` (agrégation pipeline sibling)

Additionne les valeurs d'une métrique à travers tous les sous-buckets d'une agrégation parente. `buckets_path` utilise la notation `>` pour naviguer dans les agrégations imbriquées (ex. `par_annee>nb`).

```json
{
  "aggs": {
    "par_categorie": {
      "terms": { "field": "categories.keyword", "size": 50 },
      "aggs": {
        "par_annee": {
          "date_histogram": { "field": "update_date", "calendar_interval": "year" },
          "aggs": { "nb": { "value_count": { "field": "_id" }}}
        },
        "total": {
          "sum_bucket": { "buckets_path": "par_annee>nb" }
        }
      }
    }
  }
}
```

### `bucket_sort` (agrégation pipeline sibling)

Ré-ordonne les buckets d'une agrégation parente selon la valeur d'une métrique. Permet par exemple de trier les catégories par nombre décroissant d'articles, ce que `terms` seul ne peut pas faire quand le tri porte sur une sous-agrégation.

```json
{
  "aggs": {
    "par_categorie": {
      "terms": { "field": "categories.keyword", "size": 50 },
      "aggs": {
        "total": { "sum_bucket": { "buckets_path": "par_annee>nb" }},
        "tri": {
          "bucket_sort": {
            "sort": [{ "total": { "order": "desc" }}]
          }
        }
      }
    }
  }
}
```

---

## Relations parent-enfant

### `has_child`

Retourne les documents parents dont au moins un enfant satisfait la requête. `score_mode` détermine comment le score des enfants influence le parent (max, avg, sum…). Exemple : trouver les stories HN dont un commentaire mentionne un terme.

```json
{
  "query": {
    "has_child": {
      "type": "comment",
      "query": { "match": { "text": "interesting" }},
      "score_mode": "max"
    }
  }
}
```

---

## Filtres & clauses utiles

### `term` / `terms`

`term` filtre sur une valeur exacte (pas d'analyse textuelle). `terms` accepte une liste de valeurs (OR). À utiliser dans une clause `filter` d'un `bool` pour filtrer sans affecter le score.

```json
{ "term":  { "primary_category": "cs.CL" }}
{ "terms": { "primary_category": ["cs.CL", "cs.AI"] }}
```

### `range`

Filtre sur un intervalle numérique ou de dates. Opérateurs : `gte` (≥), `gt` (>), `lte` (≤), `lt` (<).

```json
{ "range": { "date_updated": { "gte": "2023-01-01" }}}
```

### `exists`

Vérifie qu'un champ est présent et non-null dans le document. Utile en `should` (bonus) ou en `filter` (obligation).

```json
{ "exists": { "field": "hn_score" }}
```

---

## Pagination profonde

### `search_after` + Point-In-Time (PIT)

La pagination classique `from`/`size` est limitée à 10 000 résultats et coûteuse en mémoire. Pour parcourir un grand nombre de résultats, on ouvre un PIT (snapshot cohérent de l'index), puis on pagine avec `search_after` en passant la valeur `sort` du dernier hit de la page précédente. On itère jusqu'à recevoir un tableau `hits.hits` vide, puis on ferme le PIT.

```json
// 1. Ouvrir un PIT
POST /arxiv/_pit?keep_alive=5m

// 2. Première page
GET /_search
{
  "size": 500,
  "query": { "term": { "categories.keyword": "astro-ph.CO" }},
  "sort": [{ "update_date": "desc" }, { "_id": "asc" }],
  "pit": { "id": "PIT_ID", "keep_alive": "5m" }
}

// 3. Pages suivantes (copier le sort du dernier hit)
GET /_search
{
  "size": 500,
  "query": { "term": { "categories.keyword": "astro-ph.CO" }},
  "sort": [{ "update_date": "desc" }, { "_id": "asc" }],
  "pit": { "id": "PIT_ID", "keep_alive": "5m" },
  "search_after": ["2023-06-15T00:00:00.000Z", "2106.12345"]
}

// 4. Fermer le PIT
DELETE /_pit
{ "id": "PIT_ID" }
```
