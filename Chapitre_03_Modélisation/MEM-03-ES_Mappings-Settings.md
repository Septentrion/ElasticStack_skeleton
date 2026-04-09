# Exemples de mappings et settings pour Elasticsearch

## Écrire son propre tokenizer

Elasticsearch offre plusieurs approches pour créer un tokenizer personnalisé, de la plus simple à la plus avancée.

### 1. Utiliser un analyseur custom (le plus courant)

La méthode la plus répandue consiste à combiner un tokenizer existant avec des filtres de caractères et de tokens dans les settings de l'index :

```json
PUT /mon_index
{
  "settings": {
    "analysis": {
      "char_filter": {
        "mon_char_filter": {
          "type": "mapping",
          "mappings": ["& => et", "| => ou"]
        }
      },
      "tokenizer": {
        "mon_tokenizer": {
          "type": "pattern",
          "pattern": "[^a-zA-Z0-9àéèêëïôùûç]+"
        }
      },
      "analyzer": {
        "mon_analyzer": {
          "type": "custom",
          "char_filter": ["mon_char_filter"],
          "tokenizer": "mon_tokenizer",
          "filter": ["lowercase", "asciifolding"]
        }
      }
    }
  }
}
```

Ici, le tokenizer `pattern` découpe le texte selon une expression régulière, puis les filtres affinent le résultat.

### 2. Tokenizer de type `pattern` ou `simple_pattern`

Si votre besoin est surtout de découper selon un motif particulier, `pattern` (basé sur les regex Java) est souvent suffisant. `simple_pattern` est une alternative plus performante mais limitée aux expressions régulières Lucene (pas de backreferences, etc.).

### 3. Écrire un plugin d'analyse (approche avancée)

Pour un contrôle total, vous pouvez écrire un **plugin Elasticsearch** en Java qui implémente votre propre `Tokenizer` Lucene :

**a) Créer la classe Tokenizer (étend `org.apache.lucene.analysis.Tokenizer`)**

```java
public class MonTokenizer extends Tokenizer {
    private final CharTermAttribute termAttr = addAttribute(CharTermAttribute.class);
    private final OffsetAttribute offsetAttr = addAttribute(OffsetAttribute.class);

    @Override
    public boolean incrementToken() throws IOException {
        clearAttributes();
        // Votre logique : lire input (this.input), remplir termAttr, offsetAttr
        // Retourner true tant qu'il y a des tokens, false quand c'est fini
        return false;
    }

    @Override
    public void reset() throws IOException {
        super.reset();
        // Réinitialiser l'état interne
    }
}
```

**b) Créer la TokenizerFactory**

```java
public class MonTokenizerFactory extends AbstractTokenizerFactory {
    public MonTokenizerFactory(IndexSettings indexSettings,
                                Environment env,
                                String name,
                                Settings settings) {
        super(indexSettings, settings, name);
        // Lire les paramètres depuis settings
    }

    @Override
    public Tokenizer create() {
        return new MonTokenizer();
    }
}
```

**c) Enregistrer le plugin**

```java
public class MonPlugin extends Plugin implements AnalysisPlugin {
    @Override
    public Map<String, AnalysisModule.AnalysisProvider<TokenizerFactory>> getTokenizers() {
        return Map.of("mon_tokenizer", MonTokenizerFactory::new);
    }
}
```

Ensuite, vous packagez le plugin (avec un `plugin-descriptor.properties`), l'installez avec `elasticsearch-plugin install`, et vous pouvez l'utiliser comme n'importe quel tokenizer natif dans vos settings d'index.

### Quelle approche choisir ?

La combinaison **custom analyzer + tokenizer pattern + filtres** couvre la grande majorité des cas. Le plugin Java ne se justifie que si vous avez besoin d'une logique de découpage que les regex ne peuvent pas exprimer (analyse morphologique spécifique, segmentation par dictionnaire, etc.).

Vous pouvez tester votre analyseur à tout moment avec l'API `_analyze` :

```json
POST /mon_index/_analyze
{
  "analyzer": "mon_analyzer",
  "text": "Ceci est un test & une vérification"
}
```

## Créer son propre analyzer pour Elasticsearch

Un analyzer est composé de trois briques, toujours appliquées dans cet ordre :

1. **Character filters** — transforment le texte brut avant la tokenisation
2. **Tokenizer** — découpe le texte en tokens
3. **Token filters** — modifient, ajoutent ou suppriment des tokens

### Anatomie d'un custom analyzer

```json
PUT /mon_index
{
  "settings": {
    "analysis": {
      "char_filter": { ... },
      "tokenizer": { ... },
      "filter": { ... },
      "analyzer": {
        "mon_analyzer": {
          "type": "custom",
          "char_filter": ["..."],
          "tokenizer": "...",
          "filter": ["..."]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "titre": {
        "type": "text",
        "analyzer": "mon_analyzer"
      }
    }
  }
}
```

### Exemple concret : un analyzer pour du texte français "métier"

Imaginons un moteur de recherche pour des fiches produits en français, où l'on veut nettoyer le HTML, normaliser les accents, gérer les synonymes et les mots vides :

```json
PUT /catalogue
{
  "settings": {
    "analysis": {
      "char_filter": {
        "nettoyeur_html": {
          "type": "html_strip"
        },
        "remplacements": {
          "type": "mapping",
          "mappings": [
            "& => et",
            "n° => numero",
            "€ => euros"
          ]
        }
      },
      "tokenizer": {
        "mon_tokenizer": {
          "type": "standard"
        }
      },
      "filter": {
        "mots_vides_fr": {
          "type": "stop",
          "stopwords": "_french_"
        },
        "stemmer_fr": {
          "type": "stemmer",
          "language": "light_french"
        },
        "mes_synonymes": {
          "type": "synonym",
          "synonyms": [
            "canapé, sofa, divan",
            "frigo, réfrigérateur"
          ]
        }
      },
      "analyzer": {
        "analyseur_produits": {
          "type": "custom",
          "char_filter": ["nettoyeur_html", "remplacements"],
          "tokenizer": "mon_tokenizer",
          "filter": [
            "lowercase",
            "asciifolding",
            "mes_synonymes",
            "mots_vides_fr",
            "stemmer_fr"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "nom": {
        "type": "text",
        "analyzer": "analyseur_produits"
      },
      "description": {
        "type": "text",
        "analyzer": "analyseur_produits"
      }
    }
  }
}
```

Le texte `<b>Canapé</b> 3 places &amp; repose-pieds — 899€` passerait par ces étapes :

| Étape | Résultat |
|---|---|
| char_filter `html_strip` | `Canapé 3 places & repose-pieds — 899€` |
| char_filter `remplacements` | `Canapé 3 places et repose-pieds — 899 euros` |
| tokenizer `standard` | `[Canapé, 3, places, et, repose, pieds, 899, euros]` |
| `lowercase` | `[canapé, 3, places, et, repose, pieds, 899, euros]` |
| `asciifolding` | `[canape, 3, places, et, repose, pieds, 899, euros]` |
| `mes_synonymes` | `[canape, sofa, divan, 3, places, et, repose, pieds, 899, euros]` |
| `mots_vides_fr` | `[canape, sofa, divan, 3, places, repose, pieds, 899, euros]` |
| `stemmer_fr` | `[canap, sofa, divan, 3, place, repos, pied, 899, euro]` |

### Utiliser des analyzers différents à l'indexation et à la recherche

C'est une pratique courante, notamment pour les synonymes (on les applique souvent uniquement à la recherche) :

```json
"nom": {
  "type": "text",
  "analyzer": "analyseur_indexation",
  "search_analyzer": "analyseur_recherche"
}
```

### Tester et débugger

L'API `_analyze` est votre meilleur outil. Vous pouvez tester l'analyzer complet ou chaque brique séparément :

```json
POST /catalogue/_analyze
{
  "analyzer": "analyseur_produits",
  "text": "<b>Canapé</b> 3 places & repose-pieds — 899€"
}
```

Ou tester un filtre isolé :

```json
POST /catalogue/_analyze
{
  "tokenizer": "standard",
  "filter": ["lowercase", "asciifolding"],
  "text": "Réfrigérateur"
}
```

### Points de vigilance

L'**ordre des token filters** compte beaucoup. Par exemple, `lowercase` doit venir avant `synonym` si vos synonymes sont définis en minuscules, sinon ils ne seront jamais matchés. De même, `asciifolding` avant `stop` permet d'utiliser une liste de mots vides sans accents.

Enfin, un analyzer ne peut pas être modifié sur un index existant sans le fermer (`_close`), mettre à jour les settings, puis le rouvrir (`_open`), ou bien réindexer dans un nouvel index.

## Associer plusieurs analyzers à un même champ : les multi-fields

La bonne pratique dans Elasticsearch est d'utiliser les **multi-fields** (propriété `fields` dans le mapping). Le principe : un même champ source est indexé plusieurs fois, chacun avec un analyzer différent, sous des sous-noms distincts.

### Exemple de base

```json
PUT /articles
{
  "settings": {
    "analysis": {
      "filter": {
        "stemmer_fr": {
          "type": "stemmer",
          "language": "light_french"
        },
        "mots_vides_fr": {
          "type": "stop",
          "stopwords": "_french_"
        }
      },
      "analyzer": {
        "fr_full": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding", "mots_vides_fr", "stemmer_fr"]
        },
        "fr_exact": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase"]
        },
        "trigrams": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "ngram_filter"]
        }
      },
      "filter": {
        "ngram_filter": {
          "type": "ngram",
          "min_gram": 3,
          "max_gram": 4
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "titre": {
        "type": "text",
        "analyzer": "fr_full",
        "fields": {
          "exact": {
            "type": "text",
            "analyzer": "fr_exact"
          },
          "autocomplete": {
            "type": "text",
            "analyzer": "trigrams",
            "search_analyzer": "fr_exact"
          },
          "keyword": {
            "type": "keyword"
          }
        }
      }
    }
  }
}
```

Ici, le champ `titre` est indexé sous quatre formes différentes, sans aucune duplication côté `_source` :

| Chemin d'accès | Analyzer | Usage typique |
|---|---|---|
| `titre` | `fr_full` | Recherche plein texte avec stemming |
| `titre.exact` | `fr_exact` | Recherche exacte sans stemming |
| `titre.autocomplete` | `trigrams` / `fr_exact` | Autocomplétion partielle |
| `titre.keyword` | aucun (terme brut) | Agrégations, tri, filtres exacts |

### Exploiter les multi-fields dans les requêtes

L'intérêt principal est de pouvoir combiner ces variantes dans une requête `multi_match` ou `bool`, en pondérant chaque sous-champ différemment :

```json
GET /articles/_search
{
  "query": {
    "multi_match": {
      "query": "réfrigérateur encastrable",
      "fields": [
        "titre^3",
        "titre.exact^5",
        "titre.autocomplete"
      ],
      "type": "best_fields"
    }
  }
}
```

La logique ici : une correspondance exacte (sans stemming) sur `titre.exact` est la plus valorisée, suivie par la recherche stemmée sur `titre`, puis l'autocomplétion en dernier recours. Cela donne des résultats à la fois précis et tolérants.

### Bonnes pratiques à retenir

**Nommer les sous-champs selon leur rôle**, pas selon leur implémentation technique. Préférez `.exact`, `.autocomplete`, `.keyword` à `.ngram_analyzer_v2`. Le jour où vous changez d'analyzer, le nom reste cohérent.

**Ne pas multiplier les sous-champs inutilement.** Chaque sous-champ consomme de l'espace disque et de la RAM (segments inversés supplémentaires). Trois ou quatre variantes est un maximum raisonnable pour un champ courant.

**Distinguer `analyzer` et `search_analyzer`** sur les sous-champs à base de n-grams ou edge-ngrams. À l'indexation, on génère les n-grams, mais à la recherche on tokenize normalement, sinon la requête `"réf"` matcherait beaucoup trop largement.

**Utiliser le sous-champ `.keyword`** dès qu'on a besoin d'agrégations, de tri ou de filtres stricts sur le champ. C'est quasi systématique.

**Penser au `copy_to`** si plusieurs champs sources doivent alimenter un champ de recherche global :

```json
"titre":       { "type": "text", "copy_to": "recherche_globale" },
"description": { "type": "text", "copy_to": "recherche_globale" },
"recherche_globale": {
  "type": "text",
  "analyzer": "fr_full",
  "fields": {
    "exact": { "type": "text", "analyzer": "fr_exact" }
  }
}
```

Cela évite de lister tous les champs dans chaque requête `multi_match`.

### Résumé du pattern

La règle générale : **un champ, un analyzer principal, des `fields` pour les variantes, et `multi_match` ou `bool` pour combiner le tout à la recherche avec des poids adaptés.** C'est le mécanisme idiomatique d'Elasticsearch pour ce besoin, bien plus propre que de dupliquer les données dans des champs séparés.
