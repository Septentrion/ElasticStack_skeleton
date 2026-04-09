# Exercices sur les requêtes dans Elasticsearch

## **A - Syntaxe des briques unitaires**

> Utilisation de `match`, `term`, `range`, `wildcard`, etc.

### **1** — Match simple

> Recherchez tous les articles dont le résumé (`abstract`) contient le mot **"reinforcement"**.

### 2 — Term exact

> Recherchez tous les articles dont la catégorie (`categories`) vaut exactement **"cs.AI"**.

### 3 — Match avec opérateur

> Recherchez les articles dont le titre (`title`) contient **"neural"** ET **"network"** (les deux mots doivent être présents).

### 4 — Match phrase

> Recherchez les articles dont le titre contient l'expression exacte **"deep learning"** (mots consécutifs, dans cet ordre).

### 5 — Multi-match

> Recherchez le terme **"transformer"** à la fois dans le titre et dans le résumé, en en privilégiant le titre d'uncoefficient **3**.

### 6 — Range sur date

> Recherchez tous les articles publiés (`update_date`) entre le **1er janvier 2020** et le **31 décembre 2020**.

### 7 — Wildcard

> Recherchez les articles dont l'identifiant auteur (`authors_parsed`) correspond au pattern **"Ben*"** (commence par "Ben").

### 8 — Exists

> Recherchez tous les articles pour lesquels le champ `doi` existe (n'est pas `null`).

## **B — Contraintes logiques et agrégations**

### 9 — Bool – must / must_not
> Recherchez les articles qui appartiennent à la catégorie **"math.CO"** mais dont le résumé ne contient **pas** le mot **"graph"**.

### 10 — Bool – should avec minimum_should_match
> Recherchez les articles dont le résumé contient au moins **deux** des trois mots suivants : **"quantum"**, **"entanglement"**, **"superposition"**.

### 11 — Fuzzy
> Recherchez dans le titre le mot **"reinfrocement"** (faute de frappe volontaire) avec une tolérance de distance d'édition (`fuzziness`) de **2**.

### 12 — Prefix + Highlight
> Recherchez les articles dont le résumé commence par le préfixe **"optim"** et renvoyez les résultats avec les fragments surlignés (`highlight`) sur le champ `abstract`.

### 13 — Terms aggregation
Écrivez une requête qui retourne les **10 catégories les plus fréquentes** dans l'index, sans retourner aucun document (taille 0).

### 14 — Date histogram aggregation
Produisez un histogramme du nombre d'articles par **mois** sur l'année **2021**, en utilisant une agrégation `date_histogram` sur `update_date` et un filtre `range`.

### 15 — Bool imbriqué + boost
> Recherchez les articles qui : (a) doivent contenir **"GAN"** dans le titre (boost **2**), (b) devraient contenir **"image synthesis"** dans le résumé, et (c) ne doivent pas appartenir à la catégorie **"cs.CL"**. Utilisez une requête `bool` avec `must`, `should` et `must_not`.

## **C — Requêtes avancées**

> Utilisation de `function_score`, `script_score`, `search_after`, ainsi que les agrégations pipeline

### 16 — Multi-match cross-fields + analyser
> Recherchez **"Yoshua Bengio"** en mode `cross_fields` sur les champs `authors_parsed` et `submitter`, en spécifiant l'analyseur **"standard"**. Expliquez quand `cross_fields` est préférable à `best_fields`.

### 17 — Function score
Reprenez une recherche sur **"attention mechanism"** dans le résumé, puis appliquez un `function_score` avec une fonction `gauss` sur `update_date` centrée sur **2023-01-01**, avec un `scale` de **180d** et un `decay` de **0.5**, afin de favoriser les articles récents.

### 18 — Script score + nested bool
> Recherchez les articles contenant **"BERT"** dans le titre ou le résumé. Ajoutez un `script_score` qui multiplie le score de pertinence par le **logarithme du nombre de versions** du document (`versions.length`), en gérant le cas où ce champ serait absent.

### 19 — Search after + pit (pagination profonde)
> Écrivez la séquence complète de requêtes pour parcourir **tous** les articles de la catégorie **"astro-ph.CO"** triés par date décroissante, en utilisant `point_in_time` et `search_after` (par lots de 500). Expliquez pourquoi cette méthode est préférable à `from`/`size` pour une pagination profonde.

### 20 — Agrégation pipeline + requête composite
> En une seule requête : (a) filtrez les articles publiés après **2018**, (b) regroupez-les par catégorie (`terms`), (c) pour chaque catégorie, créez un sous-histogramme par **année**, (d) calculez dans chaque bucket annuel la **moyenne mobile** (`moving_avg` ou `moving_fn`) sur le nombre d'articles, et (e) triez les catégories par nombre total d'articles décroissant via une agrégation `bucket_sort`. Justifiez l'utilisation des agrégations *pipeline*.
