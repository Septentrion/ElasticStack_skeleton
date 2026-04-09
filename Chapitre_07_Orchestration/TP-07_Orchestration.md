# Jour 4 — Matin
# TP : Orchestration Airflow du pipeline SciPulse

> **Durée** : 2h45  
> **Niveau** : débutant — chaque étape est détaillée  
> **Prérequis** : Jours 1-3 complétés (tous les scripts fonctionnels, index ES peuplés, dbt configuré)

---

## Ce que vous allez construire

À la fin de ce TP, vous aurez :

1. Vérifié qu'Airflow tourne et est accessible via son interface web.
2. Complété le DAG `scipulse_arxiv_pipeline` avec de vrais appels aux scripts des Jours 1-3.
3. Complété le DAG `scipulse_hn_poller` pour le polling micro-batch.
4. Testé les deux DAGs : exécution manuelle, suivi en temps réel, inspection des logs.
5. Simulé un échec pour observer le comportement de retry et de blocage.

---

## Vérifications préalables (10 min)

### Airflow tourne-t-il ?

```bash
docker compose ps | grep airflow
```

Vous devez voir trois conteneurs en `running` :

```
scipulse-airflow-web     running    0.0.0.0:8080->8080/tcp
scipulse-airflow-sched   running
```

Si les conteneurs Airflow ne sont pas listés ou sont en `exited` :

```bash
# Relancer l'initialisation puis les services
docker compose up -d airflow-init
# Attendre ~30 secondes que l'init termine
docker compose up -d airflow-webserver airflow-scheduler
```

### Accéder à l'interface web

Ouvrez http://localhost:8080 dans votre navigateur.

Identifiants : `admin` / `admin`

Vous devez voir la liste des DAGs. Si la page est vide ou affiche une erreur, attendez 30 secondes et rafraîchissez — le scheduler met un moment à scanner les fichiers DAG.

### Les DAGs sont-ils visibles ?

Vous devez voir au moins deux DAGs :

- `scipulse_arxiv_pipeline`
- `scipulse_hn_poller`

S'ils n'apparaissent pas, vérifiez que les fichiers sont bien montés :

```bash
docker exec scipulse-airflow-web ls /opt/airflow/dags/
# → dag_arxiv_pipeline.py  dag_hn_poller.py
```

Si les fichiers ne sont pas là, vérifiez le montage de volume dans `docker-compose.yml` :

```yaml
volumes:
  - ./airflow/dags:/opt/airflow/dags
```

### Les autres services sont-ils disponibles ?

Airflow va déclencher des scripts qui interagissent avec Elasticsearch, PostgreSQL et MinIO. Vérifions que tout est accessible **depuis les conteneurs Airflow** :

```bash
# ES accessible depuis Airflow ?
docker exec scipulse-airflow-web curl -s http://elasticsearch:9200/_cluster/health | python3 -m json.tool

# PostgreSQL accessible depuis Airflow ?
docker exec scipulse-airflow-web python3 -c "
import psycopg2
conn = psycopg2.connect('host=postgres port=5432 dbname=scipulse user=scipulse password=scipulse')
print('✅ PostgreSQL OK')
conn.close()
"
```

**Attention aux noms d'hôte** : depuis l'intérieur des conteneurs Docker, on utilise les noms de service (`elasticsearch`, `postgres`, `minio`), pas `localhost`. C'est une source de confusion fréquente.

---

# PARTIE A — Compléter le DAG ArXiv (1h)

## Étape 1 — Comprendre le DAG existant (10 min)

Ouvrez le fichier du DAG ArXiv :

```bash
code airflow/dags/dag_arxiv_pipeline.py
```

Le DAG du starter kit contient 6 tâches avec des `# TODO` à compléter. Chaque tâche utilise un `BashOperator` qui exécute une commande shell à l'intérieur du conteneur Airflow.

Parcourez le fichier et repérez :

- Le `default_args` : retries, retry_delay, owner.
- Le `schedule_interval=None` : déclenchement manuel (pas de cron).
- Les 6 tâches et leur chaîne de dépendances.

## Étape 2 — Compléter les tâches (40 min)

Nous allons remplacer chaque `# TODO` par la commande réelle. Ouvrez le fichier et modifiez-le étape par étape.

### Tâche 1 : `download_arxiv_dump`

Cette tâche vérifie que les données sont disponibles dans MinIO/volume partagé. Pour le TP, les données sont déjà dans `data/arxiv-raw/` — la tâche se contente de vérifier leur présence :

```python
download_arxiv = BashOperator(
    task_id="download_arxiv_dump",
    bash_command="""
        echo "📥 Vérification des données ArXiv..."
        FILE_COUNT=$(ls -1 /opt/airflow/data/arxiv-raw/*.json 2>/dev/null | wc -l)
        if [ "$FILE_COUNT" -eq "0" ]; then
            echo "❌ Aucun fichier JSON trouvé dans /opt/airflow/data/arxiv-raw/"
            echo "   Placez le dump ArXiv dans data/arxiv-raw/"
            exit 1
        fi
        echo "✅ $FILE_COUNT fichier(s) trouvé(s)"
        LINES=$(wc -l < /opt/airflow/data/arxiv-raw/*.json)
        echo "   $LINES articles au total"
    """,
)
```

### Tâche 2 : `validate_raw_arxiv`

Exécute le script de validation Great Expectations sur les données brutes. Comme Airflow s'exécute dans un conteneur Python, on peut appeler directement nos modules :

```python
validate_raw = BashOperator(
    task_id="validate_raw_arxiv",
    bash_command="""
        echo "🔍 Validation des données brutes ArXiv..."
        cd /opt/airflow
        python -m src.quality.validate_arxiv
        EXIT_CODE=$?
        if [ $EXIT_CODE -ne 0 ]; then
            echo "⚠️  Des validations ont échoué — vérifiez les Data Docs"
            echo "   Le pipeline continue (les échecs sont tolérés au stade raw)"
        fi
        echo "✅ Validation terminée"
    """,
)
```

**Note** : on ne fait pas `exit 1` si les validations échouent au stade raw — c'est *normal* que les données brutes aient des problèmes. L'objectif est de les documenter, pas de bloquer le pipeline.

### Tâche 3 : `ingest_arxiv_logstash`

Logstash tourne en continu dans son propre conteneur et surveille le dossier `/data/arxiv-raw/`. Cette tâche vérifie que l'ingestion a bien eu lieu en comptant les documents dans l'index :

```python
ingest_logstash = BashOperator(
    task_id="ingest_arxiv_logstash",
    bash_command="""
        echo "🔄 Vérification de l'ingestion Logstash..."
        
        # Attendre que Logstash ait indexé des documents (max 120s)
        for i in $(seq 1 24); do
            COUNT=$(curl -s http://elasticsearch:9200/arxiv-papers-raw/_count | \
                    python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")
            echo "   Tentative $i/24 : $COUNT documents dans arxiv-papers-raw"
            if [ "$COUNT" -gt "1000" ]; then
                echo "✅ Ingestion Logstash confirmée : $COUNT documents"
                exit 0
            fi
            sleep 5
        done
        
        echo "❌ Logstash n'a pas indexé suffisamment de documents"
        echo "   Vérifiez les logs : docker compose logs logstash"
        exit 1
    """,
)
```

### Tâche 4 : `transform_dbt`

Exécute les modèles dbt et les tests. Attention : il faut d'abord charger les données dans PostgreSQL (puisque dbt travaille sur PG, pas ES) :

```python
transform_dbt = BashOperator(
    task_id="transform_dbt",
    bash_command="""
        echo "⚙️  Chargement dans PostgreSQL + transformations dbt..."
        cd /opt/airflow
        
        # Étape 1 : Charger ES → PostgreSQL
        echo "  [1/3] Chargement ES → PostgreSQL..."
        python -m src.transformation.load_to_postgres
        
        # Étape 2 : dbt run
        echo "  [2/3] dbt run..."
        cd /opt/airflow/dbt
        dbt run --profiles-dir .
        
        # Étape 3 : dbt test
        echo "  [3/3] dbt test..."
        dbt test --profiles-dir .
        
        echo "✅ Transformations dbt terminées"
    """,
)
```

**Important** : le `--profiles-dir .` indique à dbt de chercher `profiles.yml` dans le répertoire courant (pas dans `~/.dbt/`). Dans le conteneur Airflow, le home directory n'a pas de configuration dbt — il faut pointer vers notre `profiles.yml` dans le dossier `dbt/`.

**Important aussi** : dans `profiles.yml`, le host doit être `postgres` (nom du service Docker), pas `localhost`. Vérifiez :

```bash
cat dbt/profiles.yml | grep host
# → host: postgres    (si exécuté depuis Docker)
```

### Tâche 5 : `enrich_arxiv_python`

Lance le script d'enrichissement TF-IDF + croisement HN :

```python
enrich_python = BashOperator(
    task_id="enrich_arxiv_python",
    bash_command="""
        echo "🧠 Enrichissement NLP et croisement HN..."
        cd /opt/airflow
        python -m src.enrichment.enrich_arxiv --max 50000
        echo "✅ Enrichissement terminé"
    """,
)
```

### Tâche 6 : `validate_enriched`

Revalide les données après enrichissement — cette fois, les seuils devraient être meilleurs :

```python
validate_enriched = BashOperator(
    task_id="validate_enriched",
    bash_command="""
        echo "✅ Validation des données enrichies..."
        cd /opt/airflow
        python -m src.quality.validate_arxiv
        EXIT_CODE=$?
        if [ $EXIT_CODE -ne 0 ]; then
            echo "⚠️  Des validations ont échoué après enrichissement"
            echo "   Consultez les Data Docs pour les détails"
        else
            echo "🎉 Toutes les validations passent après enrichissement !"
        fi
    """,
)
```

### Vérifier la chaîne de dépendances

En bas du fichier, vérifiez que la chaîne est correcte :

```python
download_arxiv >> validate_raw >> ingest_logstash >> transform_dbt >> enrich_python >> validate_enriched
```

Sauvegardez le fichier.

## Étape 3 — Installer les dépendances dans le conteneur Airflow (10 min)

Les conteneurs Airflow n'ont pas automatiquement nos dépendances Python (elasticsearch, scikit-learn, etc.). Il faut les installer :

```bash
# Installer dans le webserver
docker exec scipulse-airflow-web pip install elasticsearch scikit-learn great-expectations psycopg2-binary dbt-postgres --quiet

# Installer dans le scheduler (qui exécute les tâches avec LocalExecutor)
docker exec scipulse-airflow-sched pip install elasticsearch scikit-learn great-expectations psycopg2-binary dbt-postgres --quiet
```

**En production**, on créerait une image Docker custom avec les dépendances pré-installées. En TP, l'installation à la volée suffit.

Vérifiez :

```bash
docker exec scipulse-airflow-sched python3 -c "import elasticsearch; print('✅ elasticsearch OK')"
docker exec scipulse-airflow-sched python3 -c "import sklearn; print('✅ scikit-learn OK')"
```

---

# PARTIE B — Compléter le DAG HN (30 min)

## Étape 4 — Modifier le DAG HN

Ouvrez `airflow/dags/dag_hn_poller.py` et complétez les tâches :

### Tâche 1 : `poll_hn_api`

```python
poll_hn = BashOperator(
    task_id="poll_hn_api",
    bash_command="""
        echo "📡 Polling Hacker News..."
        cd /opt/airflow
        python -m src.ingestion.hn_poller
        echo "✅ Cycle de polling terminé"
    """,
)
```

### Tâche 2 : `detect_arxiv_links`

```python
detect_links = BashOperator(
    task_id="detect_arxiv_links",
    bash_command="""
        echo "🔗 Détection des liens ArXiv dans les posts HN..."
        # La détection est intégrée au poller (dans prepare_hn_doc)
        # Cette tâche vérifie le résultat
        LINK_COUNT=$(curl -s http://elasticsearch:9200/arxiv-hn-links/_count | \
                     python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")
        echo "   $LINK_COUNT liens ArXiv↔HN dans l'index"
        echo "✅ Détection terminée"
    """,
)
```

### Tâche 3 : `update_arxiv_hn_scores`

```python
update_scores = BashOperator(
    task_id="update_arxiv_hn_scores",
    bash_command="""
        echo "📊 Mise à jour des scores croisés..."
        HN_COUNT=$(curl -s http://elasticsearch:9200/hn-items/_count | \
                   python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")
        echo "   $HN_COUNT items HN indexés au total"
        echo "✅ Scores mis à jour"
    """,
)
```

Sauvegardez le fichier.

---

# PARTIE C — Tester les DAGs (45 min)

## Étape 5 — Rafraîchir Airflow (5 min)

Après avoir modifié les fichiers DAG, le scheduler doit les relire :

```bash
# Forcer le rechargement
docker exec scipulse-airflow-sched airflow dags reserialize
```

Retournez dans l'interface web (http://localhost:8080) et rafraîchissez la page. Les DAGs doivent apparaître sans erreur d'import (pas de bandeau rouge).

Si un DAG affiche une erreur de parsing, cliquez dessus pour voir le message d'erreur. Les erreurs les plus courantes sont des problèmes d'import Python (module manquant) ou des erreurs de syntaxe.

## Étape 6 — Tester le DAG HN en premier (10 min)

Le DAG HN est plus rapide et plus simple — idéal pour un premier test.

### 6.1. Activer le DAG

Dans l'interface web, trouvez `scipulse_hn_poller` dans la liste. Cliquez sur le **toggle** à gauche pour le passer de « paused » à « active ».

**Ne l'activez PAS tout de suite si le schedule est `*/5 * * * *`** — il commencerait à tourner automatiquement toutes les 5 minutes. Pour un premier test, déclenchez-le manuellement.

### 6.2. Trigger manuel

Cliquez sur le DAG `scipulse_hn_poller` pour ouvrir sa page.

En haut à droite, cliquez sur le bouton **▶ Trigger DAG** (ou l'icône play).

### 6.3. Suivre l'exécution

Cliquez sur l'onglet **Graph** pour voir le DAG visuellement. Les tâches changent de couleur en temps réel :

| Couleur | État |
|---------|------|
| Vert clair | En cours d'exécution (running) |
| Vert foncé | Succès (success) |
| Rouge | Échec (failed) |
| Jaune | En attente de retry (up_for_retry) |
| Gris | En attente (queued) |

### 6.4. Consulter les logs

Cliquez sur une tâche (par ex. `poll_hn_api`), puis sur **Log** dans le popup. Vous devez voir la sortie de votre script : les messages `📡`, `✅`, et les compteurs.

**Si la tâche échoue** : le log montre l'erreur. Les causes les plus fréquentes :

| Erreur | Cause | Solution |
|--------|-------|----------|
| `ModuleNotFoundError: elasticsearch` | Dépendances pas installées dans le conteneur | Refaire l'étape 3 |
| `ConnectionError: elasticsearch` | ES non accessible depuis le conteneur Airflow | Vérifier le réseau Docker (`docker network ls`) |
| `host=localhost` dans le script | Le script utilise `localhost` au lieu de `elasticsearch` | Modifier la variable `ES_HOST` |

## Étape 7 — Tester le DAG ArXiv (20 min)

### 7.1. Trigger manuel

Allez dans le DAG `scipulse_arxiv_pipeline` et déclenchez-le manuellement.

**Ce DAG prend plus de temps** (5-15 minutes) parce qu'il enchaîne 6 étapes incluant le chargement PostgreSQL, dbt, et l'enrichissement TF-IDF.

### 7.2. Suivre l'exécution en temps réel

Dans l'onglet **Graph**, observez les tâches s'exécuter en séquence. Chaque tâche ne démarre que quand la précédente est en vert foncé (succès).

Pendant que les tâches tournent, cliquez sur chacune pour voir les logs en temps réel. Vous reconnaîtrez les sorties de vos scripts (`✅`, `📊`, `🧮`…).

### 7.3. Vérifier le résultat final

Quand toutes les tâches sont en vert :

```bash
# Vérifier le nombre de documents enrichis
curl -s http://localhost:9200/arxiv-papers/_count | python -m json.tool

# Vérifier que les mots-clés sont présents
curl -s 'http://localhost:9200/arxiv-papers/_search?size=0' \
  -H 'Content-Type: application/json' \
  -d '{"query":{"exists":{"field":"keywords"}}}'
```

### 7.4. Consulter l'onglet Gantt

Cliquez sur le run terminé, puis sur l'onglet **Gantt**. Ce diagramme montre la durée de chaque tâche sous forme de barres horizontales. Vous pouvez identifier les tâches les plus lentes (l'enrichissement TF-IDF est probablement le goulet d'étranglement).

## Étape 8 — Simuler un échec (10 min)

Pour comprendre le comportement d'Airflow en cas d'erreur, introduisons volontairement un problème.

### 8.1. Casser une tâche

Modifiez temporairement la tâche `transform_dbt` pour qu'elle échoue :

```python
transform_dbt = BashOperator(
    task_id="transform_dbt",
    bash_command="""
        echo "⚙️  Transformations dbt..."
        echo "💥 ERREUR SIMULÉE — fichier introuvable !"
        exit 1
    """,
)
```

Sauvegardez et relancez le DAG ArXiv.

### 8.2. Observer le comportement

Dans l'onglet Graph :

- Les tâches 1-2-3 passent au vert (succès).
- La tâche 4 (`transform_dbt`) passe au **jaune** (retry), puis au **rouge** (failed) après les retries.
- Les tâches 5-6 restent en **gris clair** (upstream_failed) — elles ne s'exécutent jamais.

**C'est le circuit breaker DataOps** : l'enrichissement et la validation finale ne tournent pas avec des données potentiellement corrompues.

### 8.3. Relancer uniquement la tâche échouée

Dans l'interface :

1. Cliquez sur la tâche rouge (`transform_dbt`).
2. Cliquez sur **Clear** dans le popup.
3. Confirmez.

Airflow relance uniquement cette tâche et celles en aval — pas les tâches 1-2-3 qui avaient déjà réussi. C'est l'avantage d'un pipeline idempotent : on peut relancer au milieu sans tout recommencer.

### 8.4. Restaurer la tâche

Remettez le code correct dans `transform_dbt` (celui de l'étape 2, tâche 4) et sauvegardez.

---

## Étape 9 — Commit (5 min)

```bash
git add airflow/dags/dag_arxiv_pipeline.py
git add airflow/dags/dag_hn_poller.py
git commit -m "feat: complete Airflow DAGs with real pipeline tasks"
```

---

## Checklist de fin de matinée

- [ ] Airflow accessible sur http://localhost:8080
- [ ] DAG `scipulse_hn_poller` complété et exécuté avec succès
- [ ] DAG `scipulse_arxiv_pipeline` complété et exécuté avec succès (6 tâches au vert)
- [ ] Logs consultés dans l'UI Airflow pour chaque tâche
- [ ] Diagramme Gantt observé (durées des tâches)
- [ ] Échec simulé et relance partielle réalisés
- [ ] Commit Git propre

## Ce qui vient cet après-midi

Cet après-midi, nous construirons le **dashboard Kibana « SciPulse »** — l'interface visuelle qui restitue tout le travail des 4 jours. Area charts, bar charts, tag clouds, métriques, et un dashboard de monitoring du pipeline. Nous ajouterons aussi la collecte des logs du pipeline via Filebeat pour l'observabilité.
