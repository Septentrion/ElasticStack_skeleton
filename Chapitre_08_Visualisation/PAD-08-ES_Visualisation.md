# Jour 4 — Après-midi
# Bloc théorique : Visualisation et observabilité

> **Durée** : 45 minutes  
> **Positionnement** : étapes serving et monitoring du cycle de vie  
> **Objectif** : comprendre les principes de dataviz appliqués aux dashboards opérationnels, maîtriser les composants Kibana, et concevoir un dashboard de monitoring de pipeline

---

## 1. La visualisation dans le cycle de vie de la donnée

### 1.1. Le serving — la dernière marche

Un pipeline de données qui produit des données propres, enrichies, et validées n'a de valeur que si quelqu'un peut les **exploiter**. La couche de serving — la dernière étape avant l'utilisateur final — détermine si le travail d'ingénierie de données se traduit en décisions ou reste invisible dans une base que personne ne consulte.

Le serving prend plusieurs formes selon le contexte [6] :

- **Dashboards** : interface visuelle interactive pour l'exploration et le monitoring. C'est ce que nous construisons dans ce TP avec Kibana.
- **API de données** : exposition des données via des endpoints REST ou GraphQL pour les applications clientes. Notre `search_service.py` (Jour 3) est un embryon de cette approche.
- **Exports et rapports** : fichiers CSV, PDF, emails automatiques. Courants dans les contextes métier (finance, RH, marketing).
- **Reverse ETL** : poussée des données transformées *vers* les outils métier (CRM, outil marketing, Slack). Tendance récente qui brouille la frontière entre le pipeline et l'application.

Dans SciPulse, le serving repose sur Kibana (dashboards interactifs) et sur le module de recherche Python (API). Le dashboard est le livrable le plus visible — c'est ce que le jury verra en premier lors de la présentation du Jour 5.

### 1.2. Deux types de dashboards

Deux types de visualisation coexistent dans tout projet DataOps. Il est essentiel de les distinguer car ils répondent à des publics, des questions et des contraintes différents.

**Le dashboard métier** (« que disent les données ? ») est destiné aux utilisateurs finaux — analystes, chercheurs, décideurs. Il répond aux questions du domaine : quelles sont les tendances de publication ? quels termes émergent ? quels articles sont populaires sur Hacker News ? Sa qualité se mesure à sa capacité à **déclencher des actions** : un chercheur qui découvre une tendance émergente et réoriente ses lectures, un analyste qui repère une catégorie en croissance rapide.

**Le dashboard de monitoring** (« le pipeline fonctionne-t-il ? ») est destiné aux data engineers et aux ops. Il répond aux questions opérationnelles : le pipeline a-t-il tourné cette nuit ? combien de documents ont été ingérés ? le taux d'erreur est-il normal ? Sa qualité se mesure à sa capacité à **détecter les problèmes** avant que les utilisateurs finaux ne s'en aperçoivent.

Les deux sont essentiels. Un dashboard métier sans monitoring est une boîte noire — quand les chiffres sont faux, personne ne le sait. Un monitoring sans dashboard métier est de l'infrastructure sans valeur — le pipeline tourne parfaitement, mais personne n'exploite les données.

### 1.3. Kibana dans l'architecture SciPulse

Kibana est la couche de visualisation de la stack Elastic. Il se connecte directement à Elasticsearch et exploite toutes les capacités de requête et d'agrégation que nous avons vues au Jour 3. Chaque visualisation Kibana est une requête ES avec un rendu graphique par-dessus.

```
┌────────────────────────────────────────────────────────┐
│                       KIBANA                           │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │ Discover │  │  Lens    │  │     Dashboard        │ │
│  │ (explore)│  │ (build)  │  │ (compose, share)     │ │
│  └──────────┘  └──────────┘  └──────────────────────┘ │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │Dev Tools │  │  Canvas  │  │     Alerting         │ │
│  │ (query)  │  │ (present)│  │ (Watcher, rules)     │ │
│  └──────────┘  └──────────┘  └──────────────────────┘ │
└──────────────────────┬─────────────────────────────────┘
                       │  Requêtes ES (search, aggs)
                       ▼
               ┌───────────────┐
               │ ELASTICSEARCH │
               │               │
               │ arxiv-papers  │  ← Dashboard métier
               │ hn-items      │  ← Dashboard métier
               │ pipeline-logs │  ← Dashboard monitoring
               └───────────────┘
```

L'avantage de cette architecture est que Kibana n'a pas de base de données propre pour les données — tout vient d'Elasticsearch. Les dashboards sont donc toujours à jour : chaque rafraîchissement relance les requêtes sur les données les plus récentes. L'inconvénient est que des dashboards complexes avec beaucoup de visualisations peuvent générer une charge significative sur le cluster ES.

---

## 2. Principes de dataviz pour les dashboards

### 2.1. Montrer ce qui compte, cacher le reste

Un bon dashboard n'est pas un catalogue de tous les graphiques possibles. C'est une réponse visuelle à des **questions précises** [1]. Edward Tufte, le père de la visualisation de données moderne, a formalisé ce principe sous le concept de **data-ink ratio** : la proportion d'« encre » qui représente effectivement des données par rapport à l'encre totale utilisée dans le graphique. Un data-ink ratio élevé signifie que chaque pixel apporte de l'information ; un ratio faible signifie que le graphique est noyé dans la décoration.

Les erreurs les plus courantes selon Tufte :

- Le **chartjunk** : éléments décoratifs qui n'apportent aucune information (dégradés 3D, textures, icônes décoratives). Kibana, avec son style sobre par défaut, aide à éviter ce piège.
- Le **lie factor** : une distorsion visuelle qui exagère ou minimise un changement réel. Un bar chart dont l'axe Y ne commence pas à 0 peut faire paraître un changement de 5% comme un doublement.
- Les **données superflues** : afficher 42 catégories dans un pie chart quand les 5 premières représentent 80% du total. Mieux vaut un « Top 5 + Autres ».

Pour SciPulse, les questions métier auxquelles le dashboard doit répondre sont :

| Question | Type de visualisation | Données nécessaires |
|----------|----------------------|---------------------|
| Quelles catégories sont les plus actives ? | Bar chart horizontal | Agrégation `terms` sur `primary_category` |
| Comment évolue le volume de publications ? | Area chart / line chart | Agrégation `date_histogram` sur `date_updated` |
| Quels termes émergent récemment ? | Tag cloud / table | Agrégation `significant_terms` sur `abstract` |
| Quels articles sont populaires sur HN ? | Data table avec tri | Sort sur `hn_score` desc |
| Quelle est la distribution des scores HN ? | Histogramme | Agrégation `histogram` sur `hn_score` |
| Quel est le volume total ? | Metric tile | Comptage simple |

Chaque visualisation doit répondre à **une** question. Si un graphique nécessite une explication de 3 paragraphes, il est trop complexe — il faut le simplifier ou le diviser en deux.

### 2.2. Choisir le bon type de visualisation

Le choix du type de graphique n'est pas esthétique — il est sémantique [2]. Chaque type de graphique est optimisé pour un type de comparaison visuelle. Utiliser le mauvais type ne rend pas le graphique « moche » — il le rend **trompeur** ou **illisible**.

| Ce qu'on veut montrer | Type adapté | Mauvais choix | Pourquoi le mauvais choix ne fonctionne pas |
|----------------------|-------------|---------------|----------------------------------------------|
| Classement (top N) | Bar chart horizontal | Pie chart | Au-delà de 5 parts, l'œil ne distingue plus les angles |
| Évolution temporelle | Line chart / area chart | Bar chart | Trop de barres = illisible ; la ligne montre la tendance continue |
| Proportion (part de) | Pie chart (≤ 5 parts) / stacked bar | Pie chart avec 20 parts | Impossible de comparer des angles proches |
| Distribution | Histogramme | Line chart | La ligne implique une continuité qui n'existe pas entre les bins |
| Chiffre clé unique | Metric tile | Graphique complet | Surcharge cognitive pour une seule valeur |
| Détail individuel | Data table | Graphique quelconque | Les graphiques perdent l'information individuelle (moyennage) |
| Mots-clés / tags | Tag cloud / horizontal bars | Pie chart | Les mots-clés sont des catégories nominales, pas des proportions |
| Corrélation (x vs y) | Scatter plot | Bar chart | Les barres ne montrent qu'une dimension à la fois |

Cole Nussbaumer Knaflic, dans *Storytelling with Data* [8], propose une approche complémentaire : avant de choisir un type de graphique, se demander **quelle comparaison** l'utilisateur va faire mentalement. « Est-ce que A est plus grand que B ? » → bar chart. « Est-ce que la tendance est à la hausse ? » → line chart. « Quelle part du total ? » → pie chart (si peu de parts).

### 2.3. Les attributs pré-attentifs

La recherche en psychologie cognitive, synthétisée par Few [2] et Cleveland [9], montre que certains attributs visuels sont traités **avant** la pensée consciente — en moins de 200 millisecondes. Ces attributs pré-attentifs sont les outils du concepteur de dashboard :

- **Longueur** : l'attribut le plus précis pour comparer des quantités. C'est pourquoi les bar charts sont supérieurs aux pie charts pour le classement.
- **Position** : la position verticale (hauteur sur un axe Y) est le deuxième attribut le plus précis. C'est ce qui rend les scatter plots et les line charts efficaces.
- **Couleur (teinte)** : efficace pour les catégories (rouge = erreur, vert = succès), mais l'œil ne distingue que 5-7 teintes simultanément.
- **Couleur (intensité)** : efficace pour les valeurs continues (heatmaps, choroplèthes).
- **Taille** : moins précis que la longueur — difficile de comparer deux cercles de tailles proches. Les bubble charts en souffrent.

Le principe pratique : **encoder la dimension la plus importante dans l'attribut le plus précis** (longueur ou position), et les dimensions secondaires dans les attributs moins précis (couleur, taille).

### 2.4. Les metric tiles — l'entrée du dashboard

Tout bon dashboard commence par 3-5 chiffres clés en haut (metric tiles) qui donnent l'état de santé en un coup d'œil :

- **Total articles** : 100 000
- **Articles avec mots-clés** : 47 832
- **Liens ArXiv↔HN** : 12
- **Catégories distinctes** : 42

Ces chiffres sont les premiers que l'œil voit. Si un chiffre est anormal (ex: total articles = 0), l'utilisateur sait immédiatement qu'il y a un problème — avant même de regarder les graphiques. Les metric tiles fonctionnent comme les voyants d'un tableau de bord de voiture : pas besoin de les analyser, il suffit de vérifier que tout est « normal ».

En monitoring, les metric tiles sont encore plus critiques : statut du cluster ES (vert/jaune/rouge), nombre de documents ingérés dans les dernières 24h, taux d'erreur, et fraîcheur du dernier item HN. Un seul tile au rouge attire l'attention instantanément.

### 2.5. Le layout : hiérarchie visuelle

Un dashboard se lit de haut en bas et de gauche à droite (dans les cultures occidentales). Stephen Few [2] recommande une hiérarchie en trois niveaux :

```
┌─────────┬─────────┬─────────┬─────────┐
│ Metric  │ Metric  │ Metric  │ Metric  │  ← Niveau 1 : KPI en un coup d'œil
└─────────┴─────────┴─────────┴─────────┘
┌───────────────────┬───────────────────┐
│                   │                   │
│  Graphique        │  Graphique        │  ← Niveau 2 : Vue d'ensemble (tendances, répartitions)
│  principal        │  secondaire       │
│  (area chart)     │  (bar chart)      │
│                   │                   │
└───────────────────┴───────────────────┘
┌───────────────────────────────────────┐
│                                       │
│  Table de détail / résultats          │  ← Niveau 3 : Détail à la demande
│                                       │
└───────────────────────────────────────┘
```

**Niveau 1 (haut)** : les chiffres clés. 3-5 metric tiles. L'utilisateur les survole en une seconde et sait si « tout va bien ».

**Niveau 2 (milieu)** : les graphiques principaux. Area charts pour les tendances, bar charts pour les classements, tag clouds pour les mots-clés. L'utilisateur y passe 10-30 secondes pour comprendre la situation.

**Niveau 3 (bas)** : les tables de détail. Articles individuels, logs récents, métriques brutes. L'utilisateur n'y va que quand il a besoin d'approfondir quelque chose repéré au niveau 2.

Ce layout suit le principe du « overview first, zoom and filter, then details on demand » formalisé par Shneiderman [10] et devenu un axiome de la visualisation interactive.

### 2.6. Le cross-filtering — l'interaction la plus puissante

Le cross-filtering (ou brushing/linking) est le mécanisme par lequel une interaction sur une visualisation (cliquer sur une barre, sélectionner une plage temporelle) filtre automatiquement toutes les autres visualisations du même dashboard.

Dans Kibana, le cross-filtering est natif : cliquer sur la barre « cs.AI » dans le bar chart des catégories filtre automatiquement l'area chart (ne montre plus que cs.AI), le tag cloud (mots-clés spécifiques à cs.AI), et la table (articles cs.AI uniquement).

C'est la fonctionnalité la plus valorisable en démonstration : elle montre que le dashboard n'est pas un poster statique mais un outil d'exploration interactive. En quelques clics, l'utilisateur passe d'une vue globale à une analyse ciblée.

---

## 3. Les composants Kibana

### 3.1. Data Views (anciennement Index Patterns)

Un **Data View** connecte Kibana à un index Elasticsearch. Il définit quel index interroger et quel champ utiliser comme timestamp (pour les filtres temporels).

Nous créerons 3 Data Views :

| Data View | Index | Timestamp | Usage |
|-----------|-------|-----------|-------|
| `arxiv-papers` | `arxiv-papers` | `date_updated` | Dashboard métier |
| `hn-items` | `hn-items` | `time` | Dashboard métier (volet HN) |
| `pipeline-logs` | `pipeline-logs-*` | `@timestamp` | Dashboard monitoring |

Le pattern `pipeline-logs-*` avec wildcard permet à Kibana de couvrir tous les index quotidiens (pattern courant en production avec ILM — Index Lifecycle Management).

### 3.2. Discover — l'exploration libre

Discover est le mode « requête libre » de Kibana. Il permet de filtrer, chercher (via le langage KQL — Kibana Query Language), et inspecter les documents individuels.

KQL est un langage de requête simplifié par rapport au Query DSL JSON :

| KQL | Équivalent Query DSL | Ce que ça fait |
|-----|---------------------|----------------|
| `transformer` | `{"query_string": {"query": "transformer"}}` | Cherche dans tous les champs texte |
| `title : "attention mechanism"` | `{"match_phrase": {"title": "attention mechanism"}}` | Phrase exacte dans le titre |
| `primary_category : "cs.AI"` | `{"term": {"primary_category": "cs.AI"}}` | Filtre exact sur un champ keyword |
| `hn_score > 100` | `{"range": {"hn_score": {"gt": 100}}}` | Filtre numérique |
| `primary_category : "cs.AI" and abstract : "RL"` | Bool query combinée | Combinaison de filtres |

Discover est utile pour les liens « voir les données brutes » depuis un graphique (drill-down), et pour le diagnostic en monitoring (« montrez-moi les logs d'erreur des 30 dernières minutes »).

### 3.3. Lens — le constructeur de visualisations

**Lens** est l'outil principal pour créer des visualisations dans Kibana. Il propose un éditeur visuel drag-and-drop qui rend la création de graphiques accessible sans écrire une seule ligne de code.

Le workflow Lens :

1. Sélectionner un Data View (ex: `arxiv-papers`).
2. Glisser un champ depuis le panneau de gauche vers la zone de construction.
3. Lens choisit automatiquement le type de graphique adapté au champ.
4. Ajuster si nécessaire : changer le type, modifier l'agrégation, ajouter un « Break down by ».
5. Renommer la visualisation et sauvegarder.

Types de visualisations supportés par Lens :

| Type | Usage dans SciPulse |
|------|---------------------|
| **Metric** | Total articles, volume HN, statut ES |
| **Bar horizontal** | Top 20 catégories |
| **Bar vertical** | Distribution des scores HN |
| **Area chart** | Publications par mois (empilé par catégorie) |
| **Line chart** | Tendances temporelles (courbes superposées) |
| **Pie / Donut** | Répartition des types HN (story / comment) |
| **Tag cloud** | Mots-clés les plus fréquents |
| **Table** | Articles récents, articles populaires HN |
| **Heatmap** | Matrice catégorie × année (intensité = volume) |
| **Treemap** | Hiérarchie domaines → catégories (surface = volume) |

### 3.4. Dashboard — la composition

Un **Dashboard** Kibana est une page qui compose plusieurs visualisations Lens côte à côte. Les interactions se propagent entre toutes les visualisations (cross-filtering).

Fonctionnalités clés :

- **Filtres globaux** : un filtre en haut du dashboard s'applique à toutes les visualisations.
- **Plage temporelle** : le sélecteur de dates en haut à droite filtre toutes les visualisations. Pour les données historiques ArXiv, élargir à « Last 15 years ».
- **Cross-filtering** : cliquer sur une valeur dans une visualisation filtre automatiquement tout le dashboard.
- **Full-screen** : mode présentation pour les démos (bouton en haut à droite).
- **Export** : les dashboards peuvent être exportés en NDJSON via l'API Saved Objects pour le versioning dans Git.

---

## 4. L'observabilité du pipeline

### 4.1. Pourquoi monitorer un pipeline de données ?

Le troisième pilier DataOps — l'observabilité — exige que le pipeline soit instrumenté. Sans monitoring, un pipeline de données est un système « fire and forget » : on le lance et on espère que tout se passe bien. En production, cette approche mène inévitablement à des situations où les données sont corrompues depuis des jours sans que personne ne s'en soit aperçu.

Les questions critiques auxquelles le monitoring doit répondre :

- **Le pipeline a-t-il tourné ?** Si le DAG Airflow est en échec depuis 3 jours et personne n'a été alerté, les dashboards métier affichent des données obsolètes.
- **Combien de temps a-t-il pris ?** Si l'ingestion qui prenait 5 minutes prend maintenant 45 minutes, c'est un signe de dégradation.
- **Combien de documents ont été traités ?** Si le volume baisse soudainement, la source a peut-être changé de format.
- **Y a-t-il eu des erreurs ?** Un taux d'erreur de 0,1% est normal. Un taux de 15% est un problème. Un taux de 100% est une panne.
- **Les données sont-elles fraîches ?** Si le dernier item HN a été indexé il y a 3 heures alors que le poller tourne toutes les 5 minutes, quelque chose ne fonctionne pas.

### 4.2. Les trois signaux de l'observabilité

L'observabilité des systèmes distribués repose sur trois signaux complémentaires, formalisés par Google dans le SRE Book [3] :

**Les logs** sont des événements textuels horodatés. « 2024-06-15 14:30:05 — 10000 documents indexés dans arxiv-papers ». Les logs racontent l'histoire détaillée de ce qui s'est passé. Leur force est la richesse d'information (contexte, messages d'erreur, stacktraces). Leur faiblesse est le volume : un pipeline qui génère 10 000 lignes de logs par heure est difficile à exploiter manuellement. C'est pourquoi on les centralise dans Elasticsearch et on les interroge via des dashboards et des recherches.

**Les métriques** sont des valeurs numériques agrégées dans le temps. « Volume d'ingestion : 50 000 docs/jour. Durée moyenne d'un run : 12 minutes. Taux d'erreur : 0,3%. » Les métriques montrent les tendances et les anomalies. Leur force est la compression : un seul nombre résume des milliers d'événements. Leur faiblesse est la perte de détail — « le taux d'erreur est monté à 5% » ne dit pas *pourquoi*.

**Les traces** suivent le parcours d'une donnée individuelle à travers le pipeline. « L'article 2301.07041 a été ingéré à 14:30, transformé à 14:32, enrichi à 14:35, et indexé à 14:36. » Les traces permettent le diagnostic fin quand une métrique globale montre un problème. En pratique, le tracing distribué (OpenTelemetry, Jaeger) est plus courant dans les microservices web que dans les pipelines de données batch.

Dans SciPulse, nous couvrirons les deux premiers signaux :

- **Métriques** : collectées par un script Python (`pipeline_metrics.py`) qui interroge ES et indexe les résultats dans `pipeline-logs`.
- **Logs** : en production, Filebeat collecterait les logs d'Airflow et de Logstash. En TP, nos métriques jouent ce rôle.

### 4.3. Les quatre signaux dorés

Le SRE Book [3] définit quatre métriques fondamentales pour monitorer tout système — les « Four Golden Signals ». Transposés aux pipelines de données :

| Signal doré | Définition (web) | Transposition (pipeline) | Indicateur SciPulse |
|-------------|-------------------|--------------------------|---------------------|
| **Latence** | Temps de réponse | Durée d'exécution du pipeline | Durée du DAG Airflow (Gantt chart) |
| **Trafic** | Requêtes par seconde | Volume de données traitées | Nombre de documents ingérés/enrichis |
| **Erreurs** | Taux de réponses en erreur | Taux de documents en échec | `error_count / total_count` |
| **Saturation** | Utilisation des ressources | Taille des index, charge ES | Taille index (Mo), shards, pending tasks |

Si l'on ne monitore que ces quatre métriques, on couvre déjà 80% des problèmes courants.

### 4.4. SLI, SLO, et seuils d'alerte

En complément des métriques brutes, les équipes DataOps définissent des **SLI** (Service Level Indicators) et des **SLO** (Service Level Objectives) [3] :

- **SLI** : la mesure brute. « Le pipeline a pris 8 minutes. »
- **SLO** : le seuil acceptable. « Le pipeline doit prendre moins de 30 minutes dans 95% des cas. »

Quand le SLI dépasse le SLO, une alerte est déclenchée. Sans SLO, les métriques ne sont que des chiffres — on ne sait pas quand s'inquiéter.

| SLI | SLO | Action si violation |
|-----|-----|---------------------|
| Durée du DAG ArXiv | < 30 min (99% des runs) | Alerte Slack |
| Taux d'erreur d'ingestion | < 1% | Alerte + inspection des logs |
| Fraîcheur des données HN | Dernier item < 15 min | Vérifier le poller |
| Taux d'enrichissement (mots-clés) | > 90% des articles | Vérifier le TF-IDF |
| Statut cluster ES | « green » ou « yellow » | « red » = alerte immédiate |

### 4.5. Filebeat pour la collecte de logs

Filebeat (vu au Jour 1 en théorie) entre en jeu concrètement pour la collecte de logs. Son rôle : surveiller les fichiers de logs d'Airflow et de Logstash, et les envoyer dans Elasticsearch.

```
  Airflow (logs)     Logstash (logs)
       │                   │
       └───────┬───────────┘
               │
               ▼
          ┌──────────┐
          │ FILEBEAT  │
          │ (collecte)│
          └─────┬────┘
                │
                ▼
          ┌──────────────┐
          │ ELASTICSEARCH │
          │ pipeline-logs │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────┐
          │  KIBANA   │
          │ Dashboard │
          │ monitoring│
          └──────────┘
```

La configuration Filebeat est déclarative :

```yaml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/airflow/**/*.log
    fields:
      source: airflow
    multiline:
      pattern: '^\d{4}-\d{2}-\d{2}'
      negate: true
      match: after

output.elasticsearch:
  hosts: ["http://elasticsearch:9200"]
  index: "pipeline-logs-%{+yyyy.MM.dd}"
```

**Dans le TP**, nous n'ajoutons pas de conteneur Filebeat (pour ne pas alourdir l'infrastructure). À la place, le script `pipeline_metrics.py` joue un rôle similaire en collectant les métriques directement depuis l'API Elasticsearch et en les indexant dans `pipeline-logs`. Le résultat dans Kibana est le même — seul le mode de collecte diffère.

### 4.6. Elasticsearch Watcher pour les alertes

Un dashboard qu'on ne regarde pas ne sert à rien. L'alerting automatise la surveillance : quand une métrique franchit un seuil, une action est déclenchée sans intervention humaine.

Watcher est le système d'alerting intégré à Elasticsearch. Il fonctionne en quatre étapes :

```
┌──────────────────────────────────────────────────────────┐
│                      WATCHER                             │
│                                                          │
│  1. TRIGGER     → Quand vérifier ? (schedule)            │
│  2. INPUT       → Quelle requête exécuter ?              │
│  3. CONDITION   → Le résultat dépasse-t-il le seuil ?    │
│  4. ACTION      → Que faire ? (log, email, Slack)        │
└──────────────────────────────────────────────────────────┘
```

Exemple : alerter si le taux d'erreur est trop élevé.

```json
{
  "trigger": { "schedule": { "interval": "5m" } },
  "input": {
    "search": {
      "request": {
        "indices": ["pipeline-logs-*"],
        "body": {
          "query": {
            "bool": {
              "must": [
                { "match": { "level": "ERROR" } },
                { "range": { "@timestamp": { "gte": "now-5m" } } }
              ]
            }
          }
        }
      }
    }
  },
  "condition": {
    "compare": { "ctx.payload.hits.total": { "gt": 10 } }
  },
  "actions": {
    "log_alert": {
      "logging": {
        "text": "ALERTE : {{ctx.payload.hits.total}} erreurs dans les 5 dernières minutes !"
      }
    }
  }
}
```

En production, les actions incluraient des notifications Slack, PagerDuty, ou email. En TP, un simple log suffit pour illustrer le concept.

### 4.7. Anti-patterns de monitoring

Quelques erreurs classiques à éviter :

**L'alert fatigue** : trop d'alertes tue les alertes. Si le pipeline envoie 50 alertes par jour, l'équipe les ignore toutes — y compris les vraies urgences. Chaque alerte doit correspondre à une action concrète. Si on ne fait rien quand l'alerte se déclenche, il faut la supprimer.

**Le monitoring post-mortem** : ne monitorer que ce qui a déjà causé un incident. C'est le minimum, mais c'est réactif. Un bon monitoring anticipe les problèmes (tendances, dégradations progressives, seuils d'approche).

**Le dashboard-musée** : un dashboard créé une fois et jamais mis à jour. Les questions métier évoluent, les données changent, le pipeline s'enrichit. Le dashboard doit être un document vivant, itéré comme du code.

---

## 5. Ce qui vient dans le TP

Le TP est divisé en deux parties :

1. **Dashboard métier « SciPulse »** (1h30) : construction du dashboard principal avec 7+ visualisations couvrant les tendances, la fouille de texte, le croisement HN, et les métriques clés. L'accent est mis sur le cross-filtering comme outil d'exploration interactive.
2. **Dashboard de monitoring** (45 min) : script de collecte de métriques (`pipeline_metrics.py`), index `pipeline-logs`, et dashboard de suivi du pipeline avec metric tiles, line chart des volumes, et table d'historique.

---

## Bibliographie

### Ouvrages de référence

[1] Tufte, E. (2001). *The Visual Display of Quantitative Information*. 2nd edition. Graphics Press.  
L'ouvrage fondateur de la visualisation de données. Le concept de « data-ink ratio » (maximiser l'encre qui représente des données, minimiser l'encre décorative) est directement applicable aux dashboards. Les chapitres sur le « chartjunk » et les « lie factors » sont une lecture essentielle pour quiconque crée des visualisations.

[2] Few, S. (2006). *Information Dashboard Design: The Effective Visual Communication of Data*. Analytics Press.  
Le guide pratique de référence pour la conception de dashboards. Les principes de layout, de choix de graphiques, et de hiérarchie visuelle que nous utilisons dans le TP sont tirés de cet ouvrage. La distinction entre dashboards stratégiques (pour les décideurs), analytiques (pour les analystes) et opérationnels (pour les ops) éclaire nos deux dashboards SciPulse.

[3] Beyer, B. et al. (2016). *Site Reliability Engineering: How Google Runs Production Systems*. O'Reilly Media.  
Les chapitres 6 (Monitoring Distributed Systems) et 28 (Accelerating SRE On-Call) formalisent les trois signaux de l'observabilité (logs, métriques, traces), les quatre signaux dorés (latence, trafic, erreurs, saturation), et les bonnes pratiques d'alerting. L'approche SLI/SLO est directement transposable au monitoring de pipelines de données. Disponible gratuitement sur https://sre.google/sre-book/table-of-contents/.

[4] Elastic. (2024). *Kibana Documentation*. https://www.elastic.co/guide/en/kibana/current/index.html  
La documentation officielle de Kibana couvre les Data Views, Lens, Dashboard, Canvas, et Alerting. Les tutoriels « Create your first dashboard » et « Lens » sont directement applicables au TP.

[5] Elastic. (2024). *Filebeat Reference*. https://www.elastic.co/guide/en/beats/filebeat/current/index.html  
Documentation de Filebeat pour la collecte de logs. La section « Filebeat modules » couvre les parseurs prédéfinis pour les logs courants. Pour les logs custom (Airflow), la section « Configure inputs » est la référence.

[6] Reis, J., & Housley, M. (2022). *Fundamentals of Data Engineering*. O'Reilly Media.  
Le chapitre 10 (Serving Data) couvre les patterns de restitution des données (dashboards, API, exports). La section sur le « reverse ETL » éclaire les tendances récentes en matière de serving.

[7] Elastic. (2024). *Watcher Documentation*. https://www.elastic.co/guide/en/elasticsearch/reference/current/xpack-alerting.html  
Documentation du système d'alerting d'Elasticsearch. Les sections « How Watcher works » et « Watcher examples » couvrent les quatre étapes (trigger, input, condition, action).

[8] Knaflic, C.N. (2015). *Storytelling with Data: A Data Visualization Guide for Business Professionals*. Wiley.  
L'ouvrage de référence pour le « data storytelling ». Les chapitres 2 (Choosing an effective visual) et 3 (Clutter is your enemy) sont directement applicables. Le chapitre 7 (Lessons in storytelling) est précieux pour les présentations du Jour 5.

### Ressources complémentaires

[9] Cleveland, W.S. (1993). *Visualizing Data*. Hobart Press.  
Recherche fondamentale sur la perception visuelle des graphiques. Les expériences de Cleveland et McGill sur la précision de la lecture des différents encodages visuels (position > longueur > angle > surface > couleur) sont la base scientifique du choix des types de graphiques.

[10] Shneiderman, B. (1996). « The Eyes Have It: A Task by Data Type Taxonomy for Information Visualizations ». *Proceedings of the IEEE Symposium on Visual Languages*, pp. 336-343.  
Article fondateur du mantra « Overview first, zoom and filter, then details on demand. » Ce principe structure directement le layout de nos dashboards (metric tiles → graphiques → tables).

[11] DataOps Manifesto. https://dataopsmanifesto.org  
Le principe 8 (« Monitor quality and performance ») motive l'intégration des checkpoints de qualité dans les dashboards. Le principe 11 (« Automate ») est le fondement du monitoring automatisé.

[12] Majors, C., Fong-Jones, L., & Miranda, G. (2022). *Observability Engineering: Achieving Production Excellence*. O'Reilly Media.  
Ouvrage récent qui distingue clairement monitoring (vérifier des métriques connues) et observabilité (pouvoir poser des questions inédites). La section sur les « unknown unknowns » explique pourquoi un bon monitoring ne se limite pas aux métriques prédéfinies — il faut aussi pouvoir explorer librement les données de fonctionnement (ce que Kibana Discover permet).

[13] Tufte, E. (2006). *Beautiful Evidence*. Graphics Press.  
Suite de [1], approfondit le concept de « sparklines » (micro-graphiques intégrés dans du texte ou des tableaux). Applicable aux metric tiles Kibana qui peuvent afficher une mini-courbe de tendance en plus du chiffre actuel.

[14] Elastic. (2024). *Elastic Stack Architecture Best Practices*. https://www.elastic.co/blog/elastic-stack-architecture-best-practices  
Guide d'architecture pour le déploiement de la stack Elastic en production, incluant les patterns de collecte de logs (Filebeat → Logstash → ES), le dimensionnement des index, et les stratégies d'ILM (Index Lifecycle Management) pour la rétention des données de monitoring.
