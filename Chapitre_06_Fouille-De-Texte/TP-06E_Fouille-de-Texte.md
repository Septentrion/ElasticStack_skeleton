# Jour 3 — Après-midi
# TP : Exploration full-text et agrégations avancées

> **Durée** : 2h30  
> **Niveau** : débutant — chaque requête est donnée en entier, prête à copier-coller dans Kibana Dev Tools  
> **Prérequis** : TP du matin complété (index `arxiv-papers` enrichi avec mots-clés TF-IDF, index `hn-items` avec quelques dizaines d'items)

---

## Ce que vous allez construire

À la fin de ce TP, vous aurez :

1. Exécuté et compris 15+ requêtes Elasticsearch avancées dans Kibana Dev Tools.
2. Encapsulé les requêtes les plus importantes dans le module Python `search_service.py`.
3. Écrit des tests unitaires (Pytest) pour le module de recherche.
4. Un carnet de requêtes réutilisable pour votre présentation du Jour 5.

---

## Vérifications préalables (5 min)

```bash
# Index ArXiv enrichi ?
curl -s http://localhost:9200/arxiv-papers/_count
# → ~100 000

# Mots-clés présents ?
curl -s 'http://localhost:9200/arxiv-papers/_search?size=0' -H 'Content-Type: application/json' -d '{"query":{"exists":{"field":"keywords"}}}'
# → hits.total.value > 0

# Items HN ?
curl -s http://localhost:9200/hn-items/_count
# → > 0
```

Ouvrez Kibana Dev Tools : http://localhost:5601 → menu ☰ → Management → Dev Tools.

Tout ce TP se déroule en deux volets :

- **Volet A** (1h15) : atelier dans Kibana Dev Tools — exécuter, observer, modifier les requêtes.
- **Volet B** (1h) : encapsulation en Python + tests unitaires.
- **Volet C** (15 min) : commit et bilan.

---

# VOLET A — Atelier Kibana Dev Tools (1h15)

Copiez chaque requête dans Kibana Dev Tools, exécutez-la (bouton ▶ ou Ctrl+Entrée), puis observez les résultats. Les exercices entre les requêtes vous demandent de **modifier** la requête pour explorer d'autres aspects.

---

## Étape 1 — Recherche full-text de base (15 min)

### 1.1. `match` simple

```
GET /arxiv-papers/_search
{
  "query": {
    "match": {
      "abstract": "reinforcement learning"
    }
  },
  "size": 3,
  "_source": ["arxiv_id", "title", "primary_category"]
}
```

Observez :

- Le `_score` de chaque résultat — c'est le score BM25.
- Le nombre total de résultats (`hits.total.value`).
- Les résultats parlent-ils bien de reinforcement learning ?

**Exercice** : remplacez `"reinforcement learning"` par `"RL"`. Grâce aux synonymes de notre analyseur custom, vous devriez obtenir des résultats similaires. Comparez les `hits.total.value`.

### 1.2. `match` avec opérateur AND

```
GET /arxiv-papers/_search
{
  "query": {
    "match": {
      "abstract": {
        "query": "transformer attention image classification",
        "operator": "and"
      }
    }
  },
  "size": 3,
  "_source": ["title"]
}
```

Observez combien de résultats il y a avec AND vs. le comportement OR par défaut. Avec 4 termes et AND, les résultats sont très spécifiques — chaque article doit contenir les 4 termes.

**Exercice** : remplacez `"operator": "and"` par `"minimum_should_match": "75%"`. Avec 4 termes et 75%, au moins 3 termes sur 4 doivent matcher. Combien de résultats supplémentaires obtenez-vous ?

### 1.3. `multi_match` cross-fields avec boost

```
GET /arxiv-papers/_search
{
  "query": {
    "multi_match": {
      "query": "generative adversarial network image synthesis",
      "fields": ["title^3", "abstract"],
      "type": "cross_fields"
    }
  },
  "size": 5,
  "_source": ["title", "primary_category", "date_updated"]
}
```

Le `^3` sur le titre signifie qu'un match dans le titre vaut 3× un match dans l'abstract.

**Exercice** : changez `"title^3"` en `"title^1"` (même poids que l'abstract). Le classement change-t-il ? Les articles dont le titre contient les termes descendent-ils dans le classement ?

### 1.4. `match_phrase` avec slop

```
GET /arxiv-papers/_search
{
  "query": {
    "match_phrase": {
      "abstract": {
        "query": "attention mechanism",
        "slop": 0
      }
    }
  },
  "size": 0
}
```

Notez le total de résultats avec `slop: 0` (phrase exacte) : _____.

Maintenant augmentez le slop :

```
GET /arxiv-papers/_search
{
  "query": {
    "match_phrase": {
      "abstract": {
        "query": "attention mechanism",
        "slop": 3
      }
    }
  },
  "size": 0
}
```

Nouveau total avec `slop: 3` : _____.

Avec `slop: 3`, des phrases comme « attention *-based* mechanism », « attention *scoring* mechanism », ou « attention *and gating* mechanism » matchent aussi.

---

## Étape 2 — Requête composée `bool` (10 min)

### 2.1. Combiner recherche textuelle + filtres

```
GET /arxiv-papers/_search
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "transformer language model",
            "fields": ["title^3", "abstract"],
            "type": "cross_fields"
          }
        }
      ],
      "filter": [
        { "term": { "primary_category": "cs.CL" } },
        { "range": { "date_updated": { "gte": "2022-01-01" } } }
      ],
      "should": [
        { "exists": { "field": "hn_score" } }
      ],
      "must_not": [
        { "match": { "title": "survey review" } }
      ]
    }
  },
  "size": 5,
  "_source": ["title", "primary_category", "date_updated", "hn_score"]
}
```

Cette requête dit :

- **DOIT** contenir « transformer language model » (dans le titre ou l'abstract).
- **FILTRÉ** sur la catégorie cs.CL (Computation and Language) et les articles depuis 2022.
- **BONUS** si l'article a un score HN (mais pas obligatoire).
- **EXCLUT** les articles de type survey/review.

**Exercice** : modifiez la requête pour chercher des articles de `cs.CV` (Computer Vision) sur « object detection ». Changez la date pour ne garder que 2023+.

---

## Étape 3 — `function_score` : tuning de la pertinence (15 min)

### 3.1. Decay gaussien sur la date

```
GET /arxiv-papers/_search
{
  "query": {
    "function_score": {
      "query": {
        "multi_match": {
          "query": "neural architecture search",
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
        }
      ],
      "boost_mode": "multiply"
    }
  },
  "size": 5,
  "_source": ["title", "date_updated"]
}
```

Observez les dates des résultats. Les articles récents devraient dominer le top, même si des articles plus anciens sont textuellement aussi pertinents.

**Exercice** : changez `"scale": "365d"` en `"scale": "90d"` (3 mois). Le classement change-t-il ? Les articles de plus de 3 mois reculent-ils fortement ?

### 3.2. Combiner fraîcheur + popularité HN

```
GET /arxiv-papers/_search
{
  "query": {
    "function_score": {
      "query": {
        "multi_match": {
          "query": "large language model",
          "fields": ["title^3", "abstract"],
          "type": "cross_fields"
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
            "missing": 1
          }
        }
      ],
      "score_mode": "multiply",
      "boost_mode": "multiply"
    }
  },
  "size": 5,
  "_source": ["title", "date_updated", "hn_score"],
  "explain": false
}
```

Si vous avez des articles avec un `hn_score`, ils devraient remonter dans le classement.

**Pour comprendre le scoring en détail** : changez `"explain": false` en `"explain": true`. Elasticsearch retournera le détail complet du calcul de score pour chaque document. C'est verbeux mais extrêmement instructif — vous verrez le score BM25, le multiplicateur gaussien, et le facteur HN séparément.

---

## Étape 4 — `more_like_this` : articles similaires (10 min)

### 4.1. Trouver un article de référence

D'abord, cherchons un article intéressant :

```
GET /arxiv-papers/_search
{
  "query": {
    "match": { "title": "attention is all you need" }
  },
  "size": 1,
  "_source": ["arxiv_id", "title"]
}
```

Copiez l'`arxiv_id` retourné. Si l'article exact n'est pas dans votre corpus, prenez n'importe quel article sur les transformers.

### 4.2. Trouver les articles similaires

Remplacez `VOTRE_ID` par l'ID copié :

```
GET /arxiv-papers/_search
{
  "query": {
    "more_like_this": {
      "fields": ["title", "abstract"],
      "like": [
        { "_index": "arxiv-papers", "_id": "VOTRE_ID" }
      ],
      "min_term_freq": 1,
      "max_query_terms": 25,
      "min_doc_freq": 2
    }
  },
  "size": 10,
  "_source": ["arxiv_id", "title", "primary_category"]
}
```

Les résultats sont les 10 articles les plus similaires au document de référence. Vérifiez : parlent-ils du même sujet ? Sont-ils de la même catégorie ?

### 4.3. MLT par texte libre

On peut aussi utiliser MLT avec un texte libre (pas un document existant) :

```
GET /arxiv-papers/_search
{
  "query": {
    "more_like_this": {
      "fields": ["abstract"],
      "like": [
        "We propose a novel approach to few-shot learning using meta-learning techniques combined with graph neural networks for classification tasks."
      ],
      "min_term_freq": 1,
      "max_query_terms": 15,
      "min_doc_freq": 2
    }
  },
  "size": 5,
  "_source": ["title", "primary_category"]
}
```

**Exercice** : collez un abstract d'un de vos propres articles ou d'un article qui vous intéresse, et voyez quels articles similaires Elasticsearch trouve.

---

## Étape 5 — `highlight` : surligner les termes (5 min)

```
GET /arxiv-papers/_search
{
  "query": {
    "multi_match": {
      "query": "graph neural network node classification",
      "fields": ["title^3", "abstract"],
      "type": "cross_fields"
    }
  },
  "highlight": {
    "fields": {
      "title": {},
      "abstract": {
        "fragment_size": 200,
        "number_of_fragments": 2
      }
    },
    "pre_tags": [">>>"],
    "post_tags": ["<<<"]
  },
  "size": 3,
  "_source": ["title"]
}
```

Dans la réponse, chaque document a un objet `highlight` qui montre les fragments de texte avec les termes matchés entourés par `>>>` et `<<<`.

Observez comment les mots-clés de votre requête sont mis en évidence dans les abstracts — c'est ce qu'on affiche dans un résultat de recherche pour aider l'utilisateur à comprendre *pourquoi* ce document est pertinent.

---

## Étape 6 — `suggest` : correction de saisie (5 min)

### 6.1. Phrase suggest

```
GET /arxiv-papers/_search
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

Résultat attendu : « convolutional neural network » avec un score de confiance.

**Exercice** : testez d'autres fautes de frappe : `"trnasformer atention"`, `"reinfrocement lerning"`, `"generatve adverserial"`. La correction fonctionne-t-elle à chaque fois ?

### 6.2. Completion suggest (autocomplétion)

```
GET /arxiv-papers/_search
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

Cela retourne les titres commençant par « deep rein… ». Si aucun résultat n'apparaît, c'est que le champ `title.suggest` (type `completion`) n'a pas été alimenté lors de la réindexation. Ce n'est pas grave — le `phrase` suggest fonctionne indépendamment.

---

## Étape 7 — `significant_terms` : détection de tendances (15 min)

C'est l'agrégation la plus puissante du TP. Prenez le temps de bien comprendre les résultats.

### 7.1. Termes émergents récents

```
GET /arxiv-papers/_search
{
  "size": 0,
  "query": {
    "range": { "date_updated": { "gte": "2023-06-01" } }
  },
  "aggs": {
    "termes_emergents": {
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

Cette requête compare les termes des articles **récents** (depuis juin 2023) avec ceux de l'ensemble du corpus. Les termes qui sont significativement *plus fréquents* dans les articles récents remontent.

Vous devriez voir des termes comme « diffusion », « llm », « chatgpt », « rlhf », « prompt » — les buzzwords de la recherche IA récente.

**Exercice** : changez la date à `"gte": "2020-01-01"`. Les termes émergents changent-ils ? Vous devriez voir les buzzwords de 2020-2021 (« self-supervised », « contrastive », « vision transformer »…).

### 7.2. Comparaison de deux catégories

Quels termes distinguent les articles de NLP (cs.CL) de ceux de Computer Vision (cs.CV) ?

```
GET /arxiv-papers/_search
{
  "size": 0,
  "query": {
    "term": { "primary_category": "cs.CL" }
  },
  "aggs": {
    "signature_NLP": {
      "sampler": { "shard_size": 3000 },
      "aggs": {
        "termes": {
          "significant_terms": {
            "field": "abstract",
            "size": 15,
            "min_doc_count": 20
          }
        }
      }
    }
  }
}
```

Les termes retournés sont ceux qui distinguent le NLP du reste du corpus : « language », « sentence », « translation », « token », « semantic »…

**Exercice** : changez `"cs.CL"` en `"cs.CV"` et relancez. Les termes signature de Computer Vision seront très différents : « image », « pixel », « segmentation », « detection »…

### 7.3. Mots-clés et significant_terms

Essayons aussi sur le champ `keywords` (nos mots-clés TF-IDF) :

```
GET /arxiv-papers/_search
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
    "trending_keywords": {
      "terms": {
        "field": "keywords",
        "size": 20
      }
    }
  }
}
```

Comparez les résultats de `terms` (mots-clés les plus fréquents) avec ceux de `significant_terms` (mots-clés les plus distinctifs). Quels mots apparaissent dans l'un mais pas dans l'autre ?

---

## Étape 8 — Requêtes parent-child sur Hacker News (10 min)

*Si votre index `hn-items` est vide ou contient très peu de documents, vous pouvez passer cette étape. Les requêtes parent-child nécessitent des données avec des relations story/comment.*

### 8.1. Compter les stories vs. commentaires

```
GET /hn-items/_search
{
  "size": 0,
  "aggs": {
    "par_type": {
      "terms": { "field": "type" }
    }
  }
}
```

### 8.2. Requête `has_child`

Trouver les stories qui ont des commentaires contenant un terme :

```
GET /hn-items/_search
{
  "query": {
    "has_child": {
      "type": "comment",
      "query": {
        "match": { "text": "interesting" }
      },
      "score_mode": "max"
    }
  },
  "size": 5,
  "_source": ["title", "score", "by"]
}
```

Si vous n'avez pas de commentaires indexés (uniquement des stories), cette requête retournera 0 résultats — c'est normal. Le poller actuel ne récupère que les stories de niveau 1, pas les commentaires. En production, on ajouterait la récupération récursive des `kids`.

### 8.3. Stories avec liens ArXiv

```
GET /hn-items/_search
{
  "query": {
    "exists": { "field": "arxiv_id_linked" }
  },
  "size": 10,
  "_source": ["title", "url", "arxiv_id_linked", "score"],
  "sort": [{ "score": "desc" }]
}
```

Ce sont les posts HN qui pointent vers un article ArXiv. Vérifiez que l'`arxiv_id_linked` correspond bien à un ID ArXiv valide dans l'URL.

---

# VOLET B — Encapsulation Python + Tests (1h)

## Étape 9 — Compléter le module `search_service.py` (30 min)

Le starter kit contient déjà un fichier `src/search/search_service.py` avec les méthodes principales. Nous allons le compléter et le tester.

### 9.1. Ouvrir et relire le module existant

```bash
code src/search/search_service.py
```

Le module contient déjà les méthodes :

- `full_text()` : recherche multi_match avec function_score.
- `more_like_this()` : articles similaires.
- `significant_terms()` : termes émergents.
- `suggest()` : correction de saisie.
- `phrase_search()` : match_phrase avec slop.

### 9.2. Ajouter une méthode `combined_search`

Ajoutez cette méthode à la classe `SciPulseSearch` qui combine recherche + highlight + agrégations en une seule requête — la « super-requête » du bloc théorique :

```python
def combined_search(
    self,
    query: str,
    categories: list[str] | None = None,
    date_from: str | None = None,
    boost_recent: bool = True,
    size: int = 10,
) -> dict:
    """
    Requête combinée : recherche full-text + highlighting +
    agrégations (termes émergents + répartition par catégorie) +
    suggestion de correction.

    C'est la requête « tout-en-un » pour l'interface de recherche.
    """
    # Recherche textuelle principale
    must = [{
        "multi_match": {
            "query": query,
            "fields": ["title^3", "abstract", "keywords^2"],
            "type": "cross_fields",
        }
    }]

    # Filtres
    filters = []
    if categories:
        filters.append({"terms": {"primary_category": categories}})
    if date_from:
        filters.append({"range": {"date_updated": {"gte": date_from}}})

    bool_query = {"must": must}
    if filters:
        bool_query["filter"] = filters

    # Clause should : bonus si score HN
    bool_query["should"] = [{"exists": {"field": "hn_score"}}]

    # Construire la requête
    if boost_recent:
        query_part = {
            "function_score": {
                "query": {"bool": bool_query},
                "functions": [
                    {
                        "gauss": {
                            "date_updated": {
                                "origin": "now",
                                "scale": "365d",
                                "decay": 0.5,
                            }
                        }
                    }
                ],
                "boost_mode": "multiply",
            }
        }
    else:
        query_part = {"bool": bool_query}

    body = {
        "query": query_part,
        "highlight": {
            "fields": {
                "abstract": {"fragment_size": 200, "number_of_fragments": 2},
                "title": {},
            },
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        },
        "aggs": {
            "termes_emergents": {
                "significant_terms": {"field": "abstract", "size": 10}
            },
            "par_categorie": {
                "terms": {"field": "primary_category", "size": 5}
            },
        },
        "suggest": {
            "correction": {
                "text": query,
                "phrase": {
                    "field": "title",
                    "size": 2,
                },
            }
        },
        "size": size,
        "_source": [
            "arxiv_id", "title", "primary_category",
            "date_updated", "hn_score", "keywords",
        ],
    }

    return self.es.search(index=self.index, body=body)
```

### 9.3. Ajouter une méthode utilitaire d'affichage

Ajoutez cette méthode qui formate les résultats pour le terminal :

```python
@staticmethod
def format_results(response: dict) -> str:
    """Formate une réponse ES pour l'affichage terminal."""
    lines = []
    hits = response.get("hits", {}).get("hits", [])
    total = response.get("hits", {}).get("total", {}).get("value", 0)

    lines.append(f"\n  {total:,} résultats trouvés\n")

    for i, hit in enumerate(hits[:10], 1):
        src = hit["_source"]
        score = hit.get("_score", 0)
        title = src.get("title", "?")[:70]
        cat = src.get("primary_category", "?")
        date = src.get("date_updated", "?")
        hn = src.get("hn_score")

        lines.append(f"  {i:>2}. [{score:.2f}] {title}")
        lines.append(f"      {cat} | {date}" + (f" | HN:{hn}" if hn else ""))

        # Highlight
        hl = hit.get("highlight", {})
        if "abstract" in hl:
            fragment = hl["abstract"][0][:120]
            lines.append(f"      ... {fragment}...")
        lines.append("")

    # Agrégations
    aggs = response.get("aggregations", {})
    if "par_categorie" in aggs:
        buckets = aggs["par_categorie"]["buckets"]
        if buckets:
            lines.append("  Catégories :")
            for b in buckets:
                lines.append(f"    {b['key']:<10} {b['doc_count']:>5}")

    if "termes_emergents" in aggs:
        buckets = aggs["termes_emergents"]["buckets"]
        if buckets:
            lines.append("\n  Termes distinctifs :")
            for b in buckets[:8]:
                lines.append(f"    {b['key']:<25} (score: {b['score']:.4f})")

    # Suggestions
    suggest = response.get("suggest", {})
    if "correction" in suggest:
        options = suggest["correction"]
        for s in options:
            if s.get("options"):
                lines.append(f"\n  💡 Vouliez-vous dire : {s['options'][0]['text']} ?")

    return "\n".join(lines)
```

### 9.4. Tester le module interactivement

Sauvegardez et testez :

```bash
python -c "
from src.search.search_service import SciPulseSearch

search = SciPulseSearch()

print('=== Full-text ===')
r = search.full_text('transformer attention mechanism')
for hit in r['hits']['hits'][:3]:
    print(f\"  [{hit['_score']:.2f}] {hit['_source']['title'][:60]}\")

print()
print('=== More Like This ===')
# Prenez un ID d'un article trouvé ci-dessus
first_id = r['hits']['hits'][0]['_id']
mlt = search.more_like_this(first_id)
for hit in mlt['hits']['hits'][:3]:
    print(f\"  {hit['_source']['title'][:60]}\")

print()
print('=== Suggest ===')
s = search.suggest('convlutional nueral network')
for entry in s.get('suggest', {}).get('title_suggest', []):
    for opt in entry.get('options', []):
        print(f\"  → {opt['text']}\")

print()
print('=== Combined ===')
c = search.combined_search('reinforcement learning robotics', categories=['cs.AI', 'cs.RO'])
print(search.format_results(c))
"
```

---

## Étape 10 — Écrire les tests unitaires (20 min)

Le starter kit contient déjà `tests/unit/test_search_service.py` avec des tests de base. Nous allons ajouter des tests pour la nouvelle méthode `combined_search`.

### 10.1. Ouvrir le fichier de tests

```bash
code tests/unit/test_search_service.py
```

### 10.2. Ajouter les tests pour `combined_search`

Ajoutez cette classe de tests à la fin du fichier :

```python
class TestCombinedSearch:
    """Tests de la méthode combined_search."""

    @pytest.fixture
    def mock_es(self):
        with patch("src.search.search_service.Elasticsearch") as MockES:
            instance = MockES.return_value
            yield instance

    @pytest.fixture
    def search(self, mock_es):
        from src.search.search_service import SciPulseSearch
        s = SciPulseSearch()
        s.es = mock_es
        return s

    def test_combined_sends_multi_match(self, search, mock_es):
        """combined_search doit envoyer une requête multi_match."""
        mock_es.search.return_value = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
            "suggest": {},
        }

        search.combined_search("transformer attention")

        call_body = mock_es.search.call_args[1]["body"]
        # Vérifier qu'il y a un multi_match quelque part dans la requête
        import json
        body_str = json.dumps(call_body)
        assert "multi_match" in body_str
        assert "transformer attention" in body_str

    def test_combined_includes_highlight(self, search, mock_es):
        """combined_search doit inclure le highlighting."""
        mock_es.search.return_value = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
            "suggest": {},
        }

        search.combined_search("test query")

        call_body = mock_es.search.call_args[1]["body"]
        assert "highlight" in call_body
        assert "abstract" in call_body["highlight"]["fields"]

    def test_combined_includes_aggregations(self, search, mock_es):
        """combined_search doit inclure les agrégations."""
        mock_es.search.return_value = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
            "suggest": {},
        }

        search.combined_search("test query")

        call_body = mock_es.search.call_args[1]["body"]
        assert "aggs" in call_body
        assert "termes_emergents" in call_body["aggs"]
        assert "par_categorie" in call_body["aggs"]

    def test_combined_includes_suggestion(self, search, mock_es):
        """combined_search doit inclure le suggest."""
        mock_es.search.return_value = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
            "suggest": {},
        }

        search.combined_search("some query")

        call_body = mock_es.search.call_args[1]["body"]
        assert "suggest" in call_body
        assert call_body["suggest"]["correction"]["text"] == "some query"

    def test_combined_with_category_filter(self, search, mock_es):
        """combined_search avec catégories doit ajouter un filtre terms."""
        mock_es.search.return_value = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
            "suggest": {},
        }

        search.combined_search("test", categories=["cs.AI", "cs.CL"])

        call_body = mock_es.search.call_args[1]["body"]
        import json
        body_str = json.dumps(call_body)
        assert "cs.AI" in body_str
        assert "cs.CL" in body_str

    def test_combined_with_date_filter(self, search, mock_es):
        """combined_search avec date_from doit ajouter un filtre range."""
        mock_es.search.return_value = {
            "hits": {"hits": [], "total": {"value": 0}},
            "aggregations": {},
            "suggest": {},
        }

        search.combined_search("test", date_from="2023-01-01")

        call_body = mock_es.search.call_args[1]["body"]
        import json
        body_str = json.dumps(call_body)
        assert "2023-01-01" in body_str
```

### 10.3. Exécuter les tests

```bash
pytest tests/unit/test_search_service.py -v
```

Sortie attendue :

```
tests/unit/test_search_service.py::TestSciPulseSearch::test_full_text_builds_multi_match PASSED
tests/unit/test_search_service.py::TestSciPulseSearch::test_full_text_includes_highlight PASSED
tests/unit/test_search_service.py::TestSciPulseSearch::test_full_text_with_hn_filter PASSED
tests/unit/test_search_service.py::TestSciPulseSearch::test_mlt_uses_correct_id PASSED
tests/unit/test_search_service.py::TestSciPulseSearch::test_significant_terms_with_category PASSED
tests/unit/test_search_service.py::TestSciPulseSearch::test_suggest_sends_phrase_suggest PASSED
tests/unit/test_search_service.py::TestSciPulseSearch::test_phrase_search_with_slop PASSED
tests/unit/test_search_service.py::TestCombinedSearch::test_combined_sends_multi_match PASSED
tests/unit/test_search_service.py::TestCombinedSearch::test_combined_includes_highlight PASSED
tests/unit/test_search_service.py::TestCombinedSearch::test_combined_includes_aggregations PASSED
tests/unit/test_search_service.py::TestCombinedSearch::test_combined_includes_suggestion PASSED
tests/unit/test_search_service.py::TestCombinedSearch::test_combined_with_category_filter PASSED
tests/unit/test_search_service.py::TestCombinedSearch::test_combined_with_date_filter PASSED

========================= 13 passed in 0.42s =========================
```

**Tous les tests doivent passer.** Si un test échoue, lisez le message d'erreur — il indique quel aspect de la requête n'est pas conforme à l'attendu. Corrigez le code dans `search_service.py`, pas les tests.

---

# VOLET C — Commit et bilan (15 min)

## Étape 11 — Commit

```bash
git add src/search/search_service.py
git add tests/unit/test_search_service.py
git commit -m "feat: add combined_search + format_results + tests"
```

## Étape 12 — Bilan des requêtes

Récapitulons les requêtes que vous maîtrisez maintenant :

| Requête | Ce qu'elle fait | Quand l'utiliser |
|---------|----------------|------------------|
| `match` | Recherche sur un champ | Recherche simple |
| `multi_match` | Recherche sur plusieurs champs avec boost | Interface de recherche globale |
| `match_phrase` | Recherche de phrase exacte (avec slop) | Expressions techniques spécifiques |
| `bool` | Combinaison must/filter/should/must_not | Requêtes complexes avec filtres |
| `function_score` | Tuning du score (fraîcheur, popularité) | Classement pertinence + signaux business |
| `more_like_this` | Articles similaires | Recommandation, exploration |
| `highlight` | Surligner les termes matchés | Affichage des résultats |
| `suggest` | Correction de saisie, autocomplétion | Champ de recherche |
| `terms` agg | Top N valeurs d'un champ | Facettes, filtres |
| `significant_terms` agg | Termes distinctifs d'un sous-ensemble | Détection de tendances, comparaison |
| `date_histogram` agg | Distribution temporelle | Visualisations temporelles |
| `has_child` / `has_parent` | Navigation parent-enfant | Posts ↔ commentaires HN |

---

## Checklist de fin de journée

- [ ] 15+ requêtes exécutées et comprises dans Kibana Dev Tools
- [ ] `match`, `multi_match`, `match_phrase` (slop) maîtrisés
- [ ] `bool` (must/filter/should/must_not) maîtrisé
- [ ] `function_score` (decay + field_value_factor) exécuté et compris
- [ ] `more_like_this` exécuté sur un article concret
- [ ] `highlight` activé et observé
- [ ] `suggest` testé avec des fautes de frappe
- [ ] `significant_terms` exécuté et comparé avec `terms`
- [ ] `combined_search` ajouté au module Python
- [ ] `format_results` ajouté au module Python
- [ ] 13 tests unitaires passants
- [ ] Commit Git propre

## Ce qui vient demain

Demain (Jour 4), nous passons à l'**orchestration et au dashboarding**. Le matin, nous assemblerons le pipeline complet dans Airflow (2 DAGs : batch ArXiv + polling HN). L'après-midi, nous construirons le dashboard Kibana « SciPulse » avec toutes les visualisations et le monitoring du pipeline.
