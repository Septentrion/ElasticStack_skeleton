# Jour 3 — Après-midi
# Bloc théorique : Fouille de texte avec Elasticsearch

> **Durée** : 1 heure  
> **Positionnement** : étape indexation et serving du cycle de vie — c'est ici que la valeur est extraite  
> **Objectif** : maîtriser les requêtes de recherche avancées, les agrégations textuelles, et le tuning de la pertinence dans Elasticsearch

---

## 1. La fouille de texte — de la recherche à l'intelligence

### 1.1. Ce que nous avons maintenant

Après deux jours et demi de travail, notre index `arxiv-papers` est riche :

- **100 000 articles** avec un mapping explicite et un analyseur custom (`scientific_english` : stemming, synonymes, stopwords).
- **Mots-clés TF-IDF** extraits par scikit-learn et stockés dans un champ `keyword`.
- **Scores Hacker News** croisés pour les articles ayant été discutés sur HN.
- **Term vectors** activés sur l'abstract pour le highlighting et `more_like_this`.
- **Multi-fields** sur le titre (text + keyword + completion) pour les recherches, agrégations et suggestions.
- Un index **`hn-items`** avec un join field pour la relation stories/commentaires.

Nous avons les données, le mapping, et l'analyseur. Il manque l'essentiel : savoir **poser les bonnes questions**. C'est l'objet de ce bloc théorique — le plus dense de la semaine en termes de fonctionnalités Elasticsearch.

### 1.2. Les trois familles de requêtes

Elasticsearch expose trois familles de requêtes qui répondent à des besoins distincts :

| Famille | Question posée | Exemple SciPulse |
|---------|---------------|------------------|
| **Recherche** (queries) | « Quels documents correspondent à cette requête, classés par pertinence ? » | Trouver les articles sur « transformer attention mechanism » |
| **Agrégations** (aggregations) | « Quelles sont les statistiques de ce corpus ? » | Top 20 mots-clés, distribution temporelle, termes émergents |
| **Suggestions** (suggesters) | « Que voulait dire l'utilisateur ? » | Corriger « convlutional nueral network » en « convolutional neural network » |

Ces trois familles peuvent être combinées dans une seule requête — c'est la force d'Elasticsearch par rapport à un moteur SQL classique.

---

## 2. Les requêtes de recherche plein texte

### 2.1. `match` — la requête de base

La requête `match` est le point de départ de toute recherche textuelle. Elle analyse le texte de recherche avec le même analyseur que celui du champ, puis cherche les termes dans l'index inversé.

```json
{
  "query": {
    "match": {
      "abstract": "reinforcement learning robotics"
    }
  }
}
```

Par défaut, `match` utilise l'opérateur **OR** : un document qui contient « reinforcement » OU « learning » OU « robotics » sera retourné. Plus un document contient de termes, plus son score BM25 est élevé.

Pour exiger que **tous** les termes soient présents :

```json
{
  "query": {
    "match": {
      "abstract": {
        "query": "reinforcement learning robotics",
        "operator": "and"
      }
    }
  }
}
```

Le compromis entre OR et AND est le paramètre `minimum_should_match` :

```json
{
  "query": {
    "match": {
      "abstract": {
        "query": "reinforcement learning robotics",
        "minimum_should_match": "75%"
      }
    }
  }
}
```

Avec 3 termes et un seuil de 75%, au moins 2 termes sur 3 doivent matcher. C'est un bon équilibre pour éviter les résultats trop bruyants (OR pur) sans être trop restrictif (AND pur).

### 2.2. `multi_match` — chercher dans plusieurs champs

La plupart des interfaces de recherche ont un seul champ de saisie mais doivent chercher dans plusieurs champs du document (titre, abstract, mots-clés…). C'est le rôle de `multi_match` :

```json
{
  "query": {
    "multi_match": {
      "query": "transformer attention mechanism",
      "fields": ["title^3", "abstract", "keywords^2"],
      "type": "cross_fields"
    }
  }
}
```

**Le boost `^3`** sur le titre signifie qu'un match dans le titre vaut 3 fois un match dans l'abstract. C'est intuitif : un article dont le titre contient « transformer » est probablement plus pertinent qu'un article qui en parle en passant dans son abstract.

**Les types de `multi_match`** contrôlent comment les scores des différents champs sont combinés :

| Type | Comportement | Quand l'utiliser |
|------|-------------|------------------|
| `best_fields` (défaut) | Score = meilleur champ | Quand les champs sont des alternatives (titre anglais / titre français) |
| `most_fields` | Score = somme de tous les champs | Quand un match dans plusieurs champs est meilleur |
| `cross_fields` | Les termes peuvent être répartis entre les champs | Quand la requête est une « phrase globale » qui peut traverser titre + abstract |

**`cross_fields`** est le type le plus adapté à SciPulse : si l'utilisateur cherche « transformer attention mechanism for NLP », certains mots peuvent être dans le titre et d'autres dans l'abstract. `cross_fields` traite les champs comme un seul grand champ virtuel.

### 2.3. `match_phrase` — la recherche de phrase exacte

`match` cherche des termes individuels. `match_phrase` cherche une **séquence de termes dans l'ordre** :

```json
{
  "query": {
    "match_phrase": {
      "abstract": "neural network architecture"
    }
  }
}
```

Cela ne retourne que les documents contenant les trois mots consécutifs dans cet ordre. C'est très précis mais très restrictif.

Le paramètre `slop` ajoute de la flexibilité — il autorise N positions de décalage entre les termes :

```json
{
  "query": {
    "match_phrase": {
      "abstract": {
        "query": "neural network architecture",
        "slop": 2
      }
    }
  }
}
```

Avec `slop: 2`, la phrase « neural *convolutional* network architecture » matcherait (un mot intercalé = 1 position de décalage). C'est utile pour les expressions techniques qui existent sous plusieurs formes proches.

### 2.4. `bool` — la requête composée

La requête `bool` est le ciment qui relie toutes les autres. Elle combine des clauses avec quatre opérateurs logiques :

```json
{
  "query": {
    "bool": {
      "must": [
        { "multi_match": { "query": "transformer attention", "fields": ["title^3", "abstract"] } }
      ],
      "filter": [
        { "term": { "primary_category": "cs.CL" } },
        { "range": { "date_updated": { "gte": "2023-01-01" } } }
      ],
      "should": [
        { "term": { "primary_category": "cs.AI" } }
      ],
      "must_not": [
        { "match": { "title": "survey" } }
      ]
    }
  }
}
```

La distinction entre les clauses est fondamentale pour comprendre le scoring :

| Clause | Effet sur le résultat | Effet sur le score | Usage typique |
|--------|----------------------|-------------------|---------------|
| `must` | Le document DOIT matcher | Contribue au score | Recherche textuelle principale |
| `filter` | Le document DOIT matcher | Aucun impact sur le score | Filtres exacts (catégorie, date, statut) |
| `should` | Le document PEUT matcher | Bonus au score si match | Signaux de pertinence additionnels |
| `must_not` | Le document ne DOIT PAS matcher | Aucun | Exclusion |

**Pourquoi `filter` plutôt que `must` pour les filtres exacts ?** Deux raisons. D'abord, les filtres n'impactent pas le score — filtrer par catégorie ne devrait pas changer le classement par pertinence textuelle. Ensuite, les filtres sont **cachés** par Elasticsearch : après la première exécution, le résultat du filtre est mémorisé, ce qui accélère les requêtes suivantes [1].

### 2.5. `term` et `terms` — les filtres exacts

Les requêtes `term` et `terms` font du matching exact sur des champs `keyword` (pas d'analyse textuelle) :

```json
{ "term":  { "primary_category": "cs.AI" } }
{ "terms": { "primary_category": ["cs.AI", "cs.CL", "cs.LG"] } }
```

Ne jamais utiliser `term` sur un champ `text` — le texte a été analysé (minuscules, stemming…) mais la valeur de recherche de `term` n'est pas analysée. Chercher `term: "Neural Network"` dans un champ text ne matcherait pas, parce que l'index inversé contient `neural` et `network` (minuscules, stemmés), pas `Neural Network` [1].

### 2.6. `range` — les intervalles

```json
{ "range": { "date_updated": { "gte": "2023-01-01", "lte": "2024-12-31" } } }
{ "range": { "hn_score": { "gt": 100 } } }
```

Fonctionne sur les dates, les nombres, et même les chaînes (tri lexicographique).

---

## 3. Le tuning de la pertinence

### 3.1. `function_score` — aller au-delà de BM25

BM25 donne un score de pertinence textuelle. Mais la pertinence d'un article scientifique ne se réduit pas au texte — sa date de publication, sa popularité sur HN, le nombre de ses citations sont aussi des signaux.

`function_score` permet de combiner le score BM25 avec des fonctions arbitraires :

```json
{
  "query": {
    "function_score": {
      "query": {
        "multi_match": {
          "query": "reinforcement learning robotics",
          "fields": ["title^3", "abstract"]
        }
      },
      "functions": [
        {
          "gauss": {
            "date_updated": {
              "origin": "now",
              "scale": "365d",
              "decay": 0.5
            }
          }
        },
        {
          "field_value_factor": {
            "field": "hn_score",
            "factor": 1.2,
            "modifier": "log1p",
            "missing": 0
          }
        }
      ],
      "boost_mode": "multiply",
      "score_mode": "multiply"
    }
  }
}
```

Décomposons les deux fonctions :

**`gauss` sur `date_updated`** : un decay gaussien qui réduit le score des articles anciens. L'`origin` est « maintenant », le `scale` est 365 jours, et le `decay` est 0.5 — un article publié il y a un an aura un multiplicateur de 0.5 (moitié du score textuel). Un article publié hier aura un multiplicateur proche de 1.0. Un article d'il y a 5 ans aura un multiplicateur proche de 0.

L'effet : à pertinence textuelle égale, un article récent est mieux classé. C'est le comportement attendu pour une plateforme de veille scientifique — les résultats récents ont plus de valeur.

**`field_value_factor` sur `hn_score`** : multiplie le score par `log1p(1.2 × hn_score)`. Le `log1p` (log(1 + x)) atténue l'effet des scores très élevés — un article avec 1 000 points HN ne sera pas 10× mieux classé qu'un article avec 100 points. Le `missing: 0` traite les articles sans score HN comme ayant un score de 0, ce qui donne un multiplicateur de `log1p(0) = 0`. Pour éviter que les articles sans score HN soient complètement pénalisés, on peut utiliser `missing: 1`.

**`boost_mode`** contrôle comment le score de la fonction est combiné avec le score BM25 : `multiply` (défaut recommandé), `sum`, `replace`, `avg`, `max`, `min`.

**`score_mode`** contrôle comment les scores des différentes fonctions entre elles sont combinés avant d'être appliqués au score BM25.

### 3.2. `boost` sur les clauses `should`

Une alternative plus légère à `function_score` pour les signaux binaires :

```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "abstract": "transformer" } }
      ],
      "should": [
        { "exists": { "field": "hn_score", "boost": 2 } },
        { "term":   { "primary_category": { "value": "cs.AI", "boost": 1.5 } } }
      ]
    }
  }
}
```

Les articles qui ont un score HN ou qui sont en cs.AI reçoivent un bonus. Mais ces conditions ne sont pas obligatoires — un article sans score HN apparaîtra quand même, juste un peu plus bas dans le classement.

---

## 4. Les requêtes avancées

### 4.1. `more_like_this` — trouver des articles similaires

`more_like_this` (MLT) est l'une des fonctionnalités les plus puissantes et les moins connues d'Elasticsearch. Étant donné un document de référence, elle trouve les documents les plus similaires dans le corpus.

```json
{
  "query": {
    "more_like_this": {
      "fields": ["title", "abstract"],
      "like": [
        { "_index": "arxiv-papers", "_id": "2301.07041" }
      ],
      "min_term_freq": 1,
      "max_query_terms": 25,
      "min_doc_freq": 2
    }
  }
}
```

**Comment ça fonctionne** : MLT extrait les termes les plus significatifs du document de référence (en utilisant les term vectors ou en les recalculant à la volée), puis construit une requête `bool` + `should` avec ces termes. Les documents du corpus sont scorés par leur similarité avec cette requête construite. C'est essentiellement un TF-IDF inversé côté Elasticsearch [2].

**Les paramètres clés** :

| Paramètre | Effet | Valeur recommandée |
|-----------|-------|-------------------|
| `min_term_freq` | Fréquence minimale d'un terme dans le doc source pour être considéré | 1 (garder les termes rares aussi) |
| `max_query_terms` | Nombre max de termes utilisés pour la requête MLT | 25 (bon compromis précision/rappel) |
| `min_doc_freq` | Le terme doit apparaître dans au moins N docs du corpus | 2 (exclure les hapax) |

**Cas d'usage dans SciPulse** : « À partir de cet article sur les transformers, quels sont les 10 articles les plus similaires ? ». C'est la fonctionnalité « articles recommandés » qu'on trouve sur Google Scholar, ArXiv, ou Semantic Scholar.

Le `term_vector: "with_positions_offsets"` que nous avons configuré sur le champ `abstract` accélère considérablement MLT : les termes n'ont pas besoin d'être recalculés à chaque requête.

### 4.2. `highlight` — surligner les termes trouvés

Le highlighting montre à l'utilisateur **pourquoi** un document a été retourné — quels mots de sa requête ont matché, et où exactement dans le texte :

```json
{
  "query": { "match": { "abstract": "transformer attention" } },
  "highlight": {
    "fields": {
      "abstract": {
        "fragment_size": 200,
        "number_of_fragments": 3
      },
      "title": {}
    },
    "pre_tags": ["<mark>"],
    "post_tags": ["</mark>"]
  }
}
```

La réponse inclut un champ `highlight` par document :

```json
{
  "highlight": {
    "abstract": [
      "We propose a novel <mark>transformer</mark>-based architecture with multi-head <mark>attention</mark>...",
      "The <mark>attention</mark> mechanism allows the model to focus on relevant parts..."
    ]
  }
}
```

**`fragment_size`** contrôle la taille des extraits retournés (en caractères). 150-200 est un bon défaut pour un affichage en résultat de recherche.

**`number_of_fragments`** contrôle le nombre d'extraits. 2-3 fragments montrent suffisamment de contexte sans noyer l'utilisateur.

Le highlighting est rendu plus performant par le `term_vector` que nous avons activé sur l'abstract — Elasticsearch n'a pas besoin de ré-analyser le texte à chaque requête.

### 4.3. `suggest` — la correction de saisie

Le Suggester corrige les fautes de frappe et propose des alternatives. Deux types sont pertinents pour SciPulse :

**`phrase` suggest** — corrige une phrase entière en tenant compte du contexte :

```json
{
  "suggest": {
    "text": "convlutional nueral network",
    "title_suggest": {
      "phrase": {
        "field": "title",
        "size": 3,
        "gram_size": 3,
        "direct_generator": [
          { "field": "title", "suggest_mode": "popular" }
        ],
        "highlight": {
          "pre_tag": "<em>",
          "post_tag": "</em>"
        }
      }
    }
  }
}
```

La réponse propose des corrections :

```json
{
  "suggest": {
    "title_suggest": [{
      "text": "convlutional nueral network",
      "options": [
        { "text": "convolutional neural network", "highlighted": "<em>convolutional</em> <em>neural</em> network", "score": 0.089 }
      ]
    }]
  }
}
```

**`completion` suggest** — autocomplétion en temps réel (typeahead) :

```json
{
  "suggest": {
    "title_autocomplete": {
      "prefix": "trans",
      "completion": {
        "field": "title.suggest",
        "size": 5
      }
    }
  }
}
```

Retourne les titres commençant par « trans… » : « transformer », « transfer learning », « translation »… Ce type de suggestion utilise le sous-champ `completion` que nous avons configuré dans le mapping.

---

## 5. Les agrégations textuelles

Les agrégations répondent à la question : « quelles sont les statistiques de ce corpus ? ». Elles sont le pendant analytique des requêtes de recherche.

### 5.1. `terms` — les facettes

L'agrégation `terms` retourne les N valeurs les plus fréquentes d'un champ `keyword` :

```json
{
  "size": 0,
  "aggs": {
    "top_categories": {
      "terms": { "field": "primary_category", "size": 20 }
    }
  }
}
```

C'est l'équivalent d'un `GROUP BY ... ORDER BY COUNT(*) DESC LIMIT 20` en SQL. Le `"size": 0` sur la requête principale signifie qu'on ne veut pas les documents individuels — uniquement les agrégations.

### 5.2. `significant_terms` — la pépite de la fouille de texte

`significant_terms` est l'agrégation la plus puissante pour la fouille de texte — et la plus sous-utilisée. Elle identifie les termes **statistiquement surreprésentés** dans un sous-ensemble de documents par rapport au corpus global [3].

```json
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term": { "primary_category": "cs.AI" } },
        { "range": { "date_updated": { "gte": "2023-01-01" } } }
      ]
    }
  },
  "aggs": {
    "trending_terms": {
      "sampler": { "shard_size": 5000 },
      "aggs": {
        "keywords": {
          "significant_terms": {
            "field": "abstract",
            "size": 20,
            "min_doc_count": 10
          }
        }
      }
    }
  }
}
```

**Que fait cette requête ?** Elle compare les termes des articles cs.AI publiés en 2023-2024 avec les termes de l'ensemble du corpus. Les termes qui sont significativement plus fréquents dans le sous-ensemble que dans le corpus global remontent en tête.

**Résultat typique** : « diffusion », « LLM », « RLHF », « prompt », « GPT-4 » — les buzzwords de la recherche en IA qui ont émergé récemment mais n'étaient pas fréquents dans le corpus historique.

**La différence avec `terms`** : `terms` retourne les termes les plus fréquents en absolu. « learning », « model », « algorithm » seront toujours en tête parce qu'ils apparaissent partout. `significant_terms` retourne les termes qui **distinguent** le sous-ensemble du corpus global — c'est beaucoup plus informatif.

**Le `sampler`** en wrapper limite l'analyse aux 5 000 premiers documents du sous-ensemble, pour des raisons de performance. Sans sampler, `significant_terms` analyserait tous les documents du sous-ensemble, ce qui peut être lent sur de gros corpus.

**Applications dans SciPulse** :

- Détection de tendances : quels termes émergent dans les publications des 3 derniers mois ?
- Analyse comparative : quels termes distinguent cs.AI de cs.CR (cryptographie) ?
- Profiling d'auteurs : quels sont les termes signature de cet auteur par rapport au corpus ?

### 5.3. `date_histogram` — la dimension temporelle

```json
{
  "size": 0,
  "aggs": {
    "publications_par_mois": {
      "date_histogram": {
        "field": "date_updated",
        "calendar_interval": "month"
      },
      "aggs": {
        "top_category": {
          "terms": { "field": "primary_category", "size": 3 }
        }
      }
    }
  }
}
```

Cette requête produit un histogramme mensuel avec, pour chaque mois, les 3 catégories les plus actives. C'est la base des visualisations temporelles dans Kibana.

| Option | Signification |
|---|---|
| `size` | Equivalent à un LIMIT de SQL : ne retourne que les `n` résultats lesplus pertinents |

### 5.4. Agrégations imbriquées

Les agrégations peuvent être imbriquées pour créer des analyses multi-dimensionnelles :

```json
{
  "size": 0,
  "aggs": {
    "par_domaine": {
      "terms": { "field": "primary_category", "size": 5 },
      "aggs": {
        "par_annee": {
          "date_histogram": {
            "field": "date_updated",
            "calendar_interval": "year"
          },
          "aggs": {
            "mots_cles_emergents": {
              "significant_terms": {
                "field": "abstract",
                "size": 5
              }
            }
          }
        }
      }
    }
  }
}
```

Trois niveaux : catégorie → année → termes émergents. Le résultat montre l'évolution des buzzwords par catégorie et par année — une analyse exploratoire extrêmement riche en une seule requête.

---

## 6. Les relations parent-child

### 6.1. Requêtes `has_child` et `has_parent`

Le join field de l'index `hn-items` (configuré au Jour 2) permet de naviguer entre les posts et leurs commentaires.

**`has_child`** : trouver les posts dont au moins un commentaire matche un critère.

```json
{
  "query": {
    "has_child": {
      "type": "comment",
      "query": {
        "match": { "text": "breakthrough impressive" }
      },
      "score_mode": "max"
    }
  }
}
```

« Trouve les stories HN qui ont au moins un commentaire contenant *breakthrough* ou *impressive*. » Le `score_mode: "max"` utilise le score du meilleur commentaire comme contribution au score du parent.

**`has_parent`** : trouver les commentaires dont le post parent matche un critère.

```json
{
  "query": {
    "has_parent": {
      "parent_type": "story",
      "query": {
        "range": { "score": { "gte": 200 } }
      }
    }
  }
}
```

« Trouve les commentaires dont la story parente a un score ≥ 200. »

### 6.2. Limites et considérations de performance

Les requêtes parent-child sont plus coûteuses que les requêtes normales parce qu'elles nécessitent un lookup entre documents. En production, trois précautions sont essentielles [4] :

- **Routing** : les parents et les enfants doivent être sur le même shard (garanti par le paramètre `routing` lors de l'indexation des enfants).
- **Volume** : éviter les relations avec des milliers d'enfants par parent — les performances se dégradent. Pour SciPulse, les posts HN ont rarement plus de quelques centaines de commentaires.
- **Index unique** : parents et enfants doivent être dans le même index. C'est une contrainte forte qui limite la flexibilité du modèle.

---

## 7. Combiner recherche et agrégations

La puissance d'Elasticsearch est de combiner ces trois familles dans une seule requête. Voici une « super-requête » réaliste pour SciPulse :

```json
{
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must": [
            { "multi_match": {
                "query": "reinforcement learning multi-agent",
                "fields": ["title^3", "abstract"],
                "type": "cross_fields"
            }}
          ],
          "filter": [
            { "terms": { "primary_category": ["cs.AI", "cs.LG", "cs.MA"] } },
            { "range": { "date_updated": { "gte": "2022-01-01" } } }
          ],
          "should": [
            { "exists": { "field": "hn_score" } }
          ]
        }
      },
      "functions": [{
        "gauss": { "date_updated": { "origin": "now", "scale": "365d", "decay": 0.5 } }
      }]
    }
  },
  "highlight": {
    "fields": {
      "abstract": { "fragment_size": 200, "number_of_fragments": 2 }
    }
  },
  "aggs": {
    "termes_emergents": {
      "significant_terms": { "field": "abstract", "size": 10 }
    },
    "par_categorie": {
      "terms": { "field": "primary_category", "size": 5 }
    }
  },
  "suggest": {
    "correction": {
      "text": "reinforcement learning multi-agent",
      "phrase": {
        "field": "title",
        "size": 2
      }
    }
  },
  "size": 10,
  "_source": ["arxiv_id", "title", "primary_category", "date_updated", "hn_score"]
}
```

Cette requête unique retourne :

1. Les **10 meilleurs articles** sur « reinforcement learning multi-agent » en cs.AI/cs.LG/cs.MA depuis 2022, classés par pertinence × fraîcheur, avec un bonus pour ceux discutés sur HN.
2. Le **highlighting** des termes trouvés dans les abstracts.
3. Les **termes émergents** dans les résultats (significativement différents du corpus global).
4. La **répartition par catégorie** des résultats.
5. Une **suggestion de correction** au cas où la requête contiendrait des fautes.

Tout cela en une seule requête HTTP, exécutée en quelques millisecondes.

---

## 8. Ce qui vient dans le TP

Le TP de cet après-midi est un atelier guidé dans Kibana Dev Tools. Vous allez exécuter, modifier, et combiner toutes les requêtes vues dans ce bloc théorique. Le TP culminera avec l'encapsulation des requêtes dans le module Python `search_service.py` et l'écriture de tests unitaires.

---

## Bibliographie

### Ouvrages de référence

[1] Elastic. (2024). *Elasticsearch Reference — Query DSL*. https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html  
La référence canonique pour toutes les requêtes Elasticsearch. Les sections « Full text queries » (match, multi_match, match_phrase), « Compound queries » (bool, function_score), et « Term-level queries » (term, range, exists) couvrent l'intégralité de ce bloc théorique. La section « Query and filter context » explique la distinction fondamentale must/filter et le mécanisme de cache.

[2] Elastic. (2024). *Elasticsearch Reference — More Like This Query*. https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-mlt-query.html  
Documentation détaillée de la requête `more_like_this` : algorithme interne (extraction de termes, construction de la requête), paramètres de tuning (`min_term_freq`, `max_query_terms`, `min_doc_freq`), et impact des term vectors sur les performances. Les exemples avec `like` par document ID et par texte libre sont directement applicables à SciPulse.

[3] Elastic. (2024). *Elasticsearch Reference — Significant Terms Aggregation*. https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations-bucket-significantterms-aggregation.html  
Documentation de l'agrégation `significant_terms` : l'algorithme JLH (Jonhson-Lindenstrauss Hash) par défaut, les algorithmes alternatifs (chi-square, GND, mutual information), les paramètres de filtrage, et les bonnes pratiques avec le `sampler`. L'encadré « How are the scores calculated » est indispensable pour comprendre pourquoi certains termes remontent et pas d'autres.

[4] Elastic. (2024). *Elasticsearch Reference — Join Field Type*. https://www.elastic.co/guide/en/elasticsearch/reference/current/parent-join.html  
Documentation du join field et des requêtes `has_child`/`has_parent`. Les avertissements sur les performances, les contraintes de routing, et la recommandation de privilégier la dénormalisation sont des lectures essentielles avant de déployer des relations parent-child en production.

### Ouvrages complémentaires

[5] Turnbull, D., & Berryman, J. (2016). *Relevant Search: With Applications for Solr and Elasticsearch*. Manning Publications.  
L'ouvrage de référence sur le relevance engineering. Le chapitre 7 (« Shaping the relevance function ») couvre en profondeur le tuning de `function_score`, les stratégies de boosting, et la mesure de la qualité des résultats. Le chapitre 8 (« Providing relevance feedback ») traite de `more_like_this` et des approches de recommandation. L'approche « judgment list + test-driven relevancy » proposée par les auteurs est une pratique DataOps avant l'heure.

[6] Gormley, C., & Tong, Z. (2015). *Elasticsearch: The Definitive Guide*. O'Reilly Media.  
Les chapitres 9-14 couvrent en détail le full-text search, le scoring, le multi-field search, et les proximity queries (match_phrase + slop). Bien que basé sur ES 2.x, les concepts fondamentaux n'ont pas changé. Disponible gratuitement sur elastic.co/guide.

[7] Robertson, S., & Zaragoza, H. (2009). « The Probabilistic Relevance Framework: BM25 and Beyond ». *Foundations and Trends in Information Retrieval*, 3(4), 333-389.  
Pour comprendre en profondeur comment `function_score` interagit avec le scoring BM25 de base. La section sur le « prior probability of relevance » fournit le cadre théorique du boosting par des signaux externes (date, popularité).

[8] Manning, C.D., Raghavan, P., & Schütze, H. (2008). *Introduction to Information Retrieval*. Cambridge University Press.  
Le chapitre 9 (Relevance feedback and query expansion) éclaire les fondements de `more_like_this` (Rocchio algorithm, relevance feedback). Le chapitre 8 (Evaluation in information retrieval) pose le cadre pour mesurer la qualité de la recherche (precision, recall, MAP, NDCG). Disponible gratuitement : https://nlp.stanford.edu/IR-book/

[9] Elastic. (2024). *Elasticsearch Reference — Highlighting*. https://www.elastic.co/guide/en/elasticsearch/reference/current/highlighting.html  
Documentation des trois types de highlighter (unified, plain, fvh — fast vector highlighter). Le FVH utilise les term vectors que nous avons configurés et est significativement plus rapide que le plain highlighter pour les champs longs comme les abstracts.

[10] Elastic. (2024). *Elasticsearch Reference — Suggesters*. https://www.elastic.co/guide/en/elasticsearch/reference/current/search-suggesters.html  
Documentation des quatre types de suggesters : term, phrase, completion, et context. La section sur le phrase suggester explique l'algorithme de correction (Stupid Backoff, Laplace smoothing) et les paramètres de tuning. La section sur le completion suggester couvre la structure FST (Finite State Transducer) et ses contraintes.
