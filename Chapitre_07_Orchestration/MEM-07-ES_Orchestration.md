# Mémento — Fonctions utiles pour le TP J4 matin
# Orchestration Airflow du pipeline SciPulse

> Classement par bibliothèque / module, avec une courte explication et un exemple d'usage tiré du code du TP.
> Ce mémento est autonome : toutes les fonctions utilisées dans le TP sont documentées.

---

## 1. `airflow.DAG` — Définition d'un graphe de tâches

### `DAG(dag_id, default_args, schedule_interval, ...)`

Crée un DAG (Directed Acyclic Graph) — l'objet central d'Airflow qui contient et ordonne les tâches. On l'utilise comme context manager (`with DAG(...) as dag:`).

```python
from datetime import datetime, timedelta
from airflow import DAG

with DAG(
    dag_id="scipulse_arxiv_pipeline",
    default_args=default_args,
    description="Pipeline batch ArXiv",
    schedule_interval=None,              # Déclenchement manuel
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["scipulse", "arxiv", "batch"],
) as dag:
    # Définition des tâches ici...
```

### Paramètres du DAG

| Paramètre | Type | Rôle | Valeur dans le TP |
|-----------|------|------|-------------------|
| `dag_id` | `str` | Identifiant unique du DAG (affiché dans l'UI) | `"scipulse_arxiv_pipeline"` |
| `default_args` | `dict` | Paramètres par défaut appliqués à toutes les tâches | Voir section 2 |
| `description` | `str` | Description affichée dans l'UI Airflow | Texte libre |
| `schedule_interval` | `str` ou `None` | Fréquence d'exécution automatique | `None` (manuel) ou `"*/5 * * * *"` (5 min) |
| `start_date` | `datetime` | Date à partir de laquelle le scheduler planifie | `datetime(2024, 1, 1)` |
| `catchup` | `bool` | Rattraper les runs passés au premier démarrage ? | `False` (recommandé en TP) |
| `max_active_runs` | `int` | Nombre maximum de runs simultanés | `1` (pas de chevauchement) |
| `tags` | `list[str]` | Tags pour filtrer dans l'UI | `["scipulse", "arxiv"]` |

### Expressions de scheduling

| Expression | Fréquence | Cas d'usage |
|------------|-----------|-------------|
| `None` | Jamais (déclenchement manuel uniquement) | DAG batch ArXiv (à la demande) |
| `"@daily"` | Tous les jours à minuit UTC | ETL quotidien |
| `"@hourly"` | Toutes les heures | Micro-batch horaire |
| `"*/5 * * * *"` | Toutes les 5 minutes (syntaxe cron) | Poller HN |
| `"0 6 * * 1"` | Tous les lundis à 6h | Rapports hebdomadaires |
| `"0 */2 * * *"` | Toutes les 2 heures | Ingestion modérée |

La syntaxe cron : `minute heure jour_du_mois mois jour_de_la_semaine`. `*` = tous, `*/N` = tous les N.

---

## 2. `default_args` — Paramètres par défaut des tâches

Le dictionnaire `default_args` est appliqué à toutes les tâches du DAG. Les tâches individuelles peuvent surcharger ces valeurs.

```python
from datetime import timedelta

default_args = {
    "owner": "scipulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(hours=1),
}
```

| Paramètre | Type | Rôle | Recommandation |
|-----------|------|------|----------------|
| `owner` | `str` | Propriétaire affiché dans l'UI | Nom du projet ou de l'équipe |
| `depends_on_past` | `bool` | La tâche dépend-elle du succès du run précédent ? | `False` — chaque run est indépendant |
| `email_on_failure` | `bool` | Envoyer un email en cas d'échec ? | `False` en TP, `True` en production |
| `retries` | `int` | Nombre de tentatives en cas d'échec | `1` à `3` selon la criticité |
| `retry_delay` | `timedelta` | Délai entre deux tentatives | `timedelta(minutes=1)` à `timedelta(minutes=5)` |
| `retry_exponential_backoff` | `bool` | Doubler le délai à chaque retry ? | `True` pour les appels API |
| `execution_timeout` | `timedelta` | Durée maximale d'une tâche | `timedelta(hours=1)` (fail-safe) |

---

## 3. `airflow.operators.bash.BashOperator` — Exécuter des commandes shell

### `BashOperator(task_id, bash_command)`

Crée une tâche qui exécute une commande shell. C'est l'opérateur principal utilisé dans SciPulse — chaque tâche déclenche un script Python ou une commande de vérification.

```python
from airflow.operators.bash import BashOperator

download_arxiv = BashOperator(
    task_id="download_arxiv_dump",
    bash_command="""
        echo "📥 Vérification des données ArXiv..."
        FILE_COUNT=$(ls -1 /opt/airflow/data/arxiv-raw/*.json 2>/dev/null | wc -l)
        if [ "$FILE_COUNT" -eq "0" ]; then
            echo "❌ Aucun fichier trouvé"
            exit 1
        fi
        echo "✅ $FILE_COUNT fichier(s) trouvé(s)"
    """,
)
```

| Paramètre | Type | Rôle |
|-----------|------|------|
| `task_id` | `str` | Identifiant unique de la tâche dans le DAG (affiché dans le graphe) |
| `bash_command` | `str` | Commande shell à exécuter (peut être multi-lignes avec `"""..."""`) |

### Comportement de sortie

- Si la commande retourne `exit 0` (ou se termine normalement) → tâche `success`.
- Si la commande retourne `exit 1` (ou tout code ≠ 0) → tâche `failed`.
- Si la tâche dépasse `execution_timeout` → tâche `failed`.
- En cas de `failed` : Airflow relance la tâche selon `retries` et `retry_delay`.

### `|| true` — Ne pas bloquer sur un échec

Ajouter `|| true` après une commande fait que son échec est ignoré (le code de sortie est forcé à 0). Utilisé quand une validation peut échouer sans devoir bloquer le pipeline.

```python
validate_raw = BashOperator(
    task_id="validate_raw_arxiv",
    bash_command="""
        python -m src.quality.validate_arxiv || true
        echo "✅ Validation terminée (échecs tolérés au stade raw)"
    """,
)
```

### `$?` — Code de sortie de la dernière commande

En bash, `$?` contient le code de sortie de la commande précédente (0 = succès, autre = erreur).

```python
validate_enriched = BashOperator(
    task_id="validate_enriched",
    bash_command="""
        python -m src.quality.validate_arxiv
        EXIT_CODE=$?
        if [ $EXIT_CODE -ne 0 ]; then
            echo "⚠️  Des validations ont échoué"
        else
            echo "🎉 Tout est passé !"
        fi
        exit 0    # Toujours retourner succès
    """,
)
```

---

## 4. `>>` — Opérateur de dépendance entre tâches

Définit l'ordre d'exécution : la tâche de gauche doit réussir avant que celle de droite ne démarre. C'est la syntaxe Python que le DAG utilise pour construire le graphe.

```python
# Chaîne séquentielle (6 tâches l'une après l'autre)
download_arxiv >> validate_raw >> ingest_logstash >> transform_dbt >> enrich_python >> validate_enriched
```

Équivalent verbeux (rarement utilisé) :

```python
download_arxiv.set_downstream(validate_raw)
validate_raw.set_downstream(ingest_logstash)
```

### Branchement parallèle

Si deux tâches n'ont pas de dépendance entre elles, elles s'exécutent en parallèle :

```python
# ingest_arxiv et poll_hn s'exécutent en parallèle
# enrich attend que les DEUX soient terminées
[ingest_arxiv, poll_hn] >> enrich
```

### Circuit breaker

Si une tâche échoue (après tous ses retries), toutes les tâches en aval passent en état `upstream_failed` et ne s'exécutent jamais. C'est le mécanisme qui empêche les données corrompues de se propager.

---

## 5. `datetime` et `timedelta` — Dates et durées

### `datetime(year, month, day)`

Crée une date. Utilisé pour `start_date` du DAG.

```python
from datetime import datetime
start_date=datetime(2024, 1, 1)
```

### `timedelta(minutes, hours, days)`

Crée une durée. Utilisé pour `retry_delay` et `execution_timeout`.

```python
from datetime import timedelta
retry_delay=timedelta(minutes=2)
execution_timeout=timedelta(hours=1)
```

---

## 6. `subprocess` — Exécution de commandes système (Python)

### `subprocess.run(cmd, shell, capture_output, text, timeout)`

Exécute une commande shell depuis Python et capture le résultat. Utilisé dans `verify_airflow.py` pour tester l'état des conteneurs et des services.

```python
import subprocess

result = subprocess.run(
    "docker ps --format '{{.Names}}'",
    shell=True,              # Interpréter comme commande shell
    capture_output=True,     # Capturer stdout et stderr
    text=True,               # Retourner des chaînes (pas des bytes)
    timeout=15,              # Abandonner après 15 secondes
)

print(result.returncode)     # 0 = succès
print(result.stdout)         # Sortie standard (chaîne)
print(result.stderr)         # Sortie d'erreur (chaîne)
```

### `subprocess.TimeoutExpired`

Exception levée si la commande dépasse le timeout.

```python
try:
    result = subprocess.run(cmd, shell=True, timeout=15, capture_output=True, text=True)
except subprocess.TimeoutExpired:
    print("Commande trop lente")
```

---

## 7. Commandes Bash dans les BashOperators

### Commandes Elasticsearch (depuis les conteneurs Airflow)

Depuis l'intérieur d'un conteneur Docker, on utilise le **nom de service** (`elasticsearch`, pas `localhost`).

```bash
# Compter les documents d'un index
COUNT=$(curl -s "http://elasticsearch:9200/arxiv-papers-raw/_count" | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")

# Requête avec body JSON (filtre exists)
LINKED=$(curl -s "http://elasticsearch:9200/hn-items/_count" \
    -H 'Content-Type: application/json' \
    -d '{"query":{"exists":{"field":"arxiv_id_linked"}}}' | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))")

# Recherche avec tri et agrégations
curl -s "http://elasticsearch:9200/hn-items/_search" \
    -H 'Content-Type: application/json' \
    -d '{"size":0,"aggs":{"types":{"terms":{"field":"type"}}}}' | \
    python3 -c "
import sys, json
data = json.load(sys.stdin)
for b in data.get('aggregations',{}).get('types',{}).get('buckets',[]):
    print(f'  {b[\"key\"]:<12} {b[\"doc_count\"]:>6}')
"
```

### Pattern de polling en boucle

Attendre qu'une condition soit remplie (ex : Logstash a indexé assez de documents).

```bash
MAX_WAIT=24       # Nombre de tentatives
MIN_DOCS=1000     # Seuil minimum
INTERVAL=5        # Secondes entre tentatives

for i in $(seq 1 $MAX_WAIT); do
    COUNT=$(curl -s "http://elasticsearch:9200/arxiv-papers-raw/_count" | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" || echo "0")

    echo "  Tentative $i/$MAX_WAIT : $COUNT documents"

    if [ "$COUNT" -gt "$MIN_DOCS" ]; then
        echo "✅ Seuil atteint"
        exit 0
    fi

    sleep $INTERVAL
done

echo "❌ Timeout — seuil non atteint"
exit 1
```

### Appel de scripts Python depuis un BashOperator

```bash
cd /opt/airflow
python -m src.transformation.load_to_postgres    # Module Python
python -m src.enrichment.enrich_arxiv --max 50000  # Avec arguments

cd /opt/airflow/dbt
dbt run --profiles-dir .     # dbt dans le répertoire courant
dbt test --profiles-dir .
```

**`--profiles-dir .`** : indique à dbt de chercher `profiles.yml` dans le répertoire courant (pas dans `~/.dbt/`). Nécessaire dans les conteneurs Docker où le home directory n'a pas de configuration dbt.

### Commandes de vérification de fichiers

```bash
# Compter les fichiers JSON dans un dossier
FILE_COUNT=$(ls -1 /opt/airflow/data/arxiv-raw/*.json 2>/dev/null | wc -l)

# Compter les lignes d'un fichier
LINES=$(wc -l < "$f")

# Calculer un total dans une boucle
TOTAL=0
for f in /opt/airflow/data/arxiv-raw/*.json; do
    LINES=$(wc -l < "$f")
    TOTAL=$((TOTAL + LINES))
done
```

---

## 8. Commandes Airflow CLI

Toutes ces commandes s'exécutent soit directement dans un conteneur Airflow, soit via `docker exec`.

### Gestion des DAGs

| Commande | Rôle |
|----------|------|
| `airflow dags list` | Lister tous les DAGs avec leur schedule |
| `airflow dags list-import-errors` | Afficher les erreurs de parsing des fichiers DAG |
| `airflow dags reserialize` | Forcer le rechargement des fichiers DAG (après modification) |
| `airflow dags unpause <dag_id>` | Activer un DAG (le rendre exécutable) |
| `airflow dags pause <dag_id>` | Désactiver un DAG |
| `airflow dags trigger <dag_id>` | Déclencher un run manuellement |
| `airflow dags list-runs -d <dag_id>` | Historique des runs d'un DAG |
| `airflow dags state <dag_id> <date>` | État du dernier run à une date |

### Exécution via `docker exec`

Depuis votre terminal hôte, préfixez chaque commande avec `docker exec <conteneur>` :

```bash
# Lister les DAGs
docker exec scipulse-airflow-sched airflow dags list

# Vérifier les erreurs d'import
docker exec scipulse-airflow-sched airflow dags list-import-errors

# Déclencher un DAG
docker exec scipulse-airflow-sched airflow dags trigger scipulse_hn_poller

# Activer un DAG
docker exec scipulse-airflow-sched airflow dags unpause scipulse_arxiv_pipeline

# Forcer le rechargement après modification d'un fichier DAG
docker exec scipulse-airflow-sched airflow dags reserialize
```

---

## 9. Commandes Docker utilisées dans les scripts

### `docker ps --format '{{.Names}}'`

Liste les noms des conteneurs en cours d'exécution. Utilisé pour vérifier qu'un service tourne.

```bash
docker ps --format '{{.Names}}' | grep -q "^scipulse-airflow-sched$"
# Code de retour 0 si trouvé, 1 sinon
```

### `docker ps --filter name=<nom> --format '{{.Status}}'`

Affiche le statut d'un conteneur spécifique.

```bash
docker ps --filter name=scipulse-es --format '{{.Status}}'
# → "Up 2 hours (healthy)"
```

### `docker exec <conteneur> <commande>`

Exécute une commande à l'intérieur d'un conteneur en cours d'exécution.

```bash
# Exécuter un script Python dans le conteneur Airflow
docker exec scipulse-airflow-sched python3 -c "import elasticsearch; print('OK')"

# Installer des packages
docker exec scipulse-airflow-web pip install elasticsearch scikit-learn --quiet

# Vérifier la connexion réseau depuis le conteneur
docker exec scipulse-airflow-sched curl -sf http://elasticsearch:9200/_cluster/health
```

### `docker compose restart <service>`

Redémarre un service sans toucher aux autres.

```bash
docker compose restart logstash
```

---

## 10. Noms d'hôte Docker — La distinction critique

Les conteneurs Docker communiquent entre eux via les **noms de services** définis dans `docker-compose.yml`, pas via `localhost`.

| Depuis votre machine hôte | Depuis un conteneur Airflow |
|---------------------------|-----------------------------|
| `http://localhost:9200` | `http://elasticsearch:9200` |
| `host=localhost` (PostgreSQL) | `host=postgres` |
| `http://localhost:9000` (MinIO) | `http://minio:9000` |
| `http://localhost:5601` (Kibana) | `http://kibana:5601` |

Dans les `bash_command` des BashOperators, on utilise toujours les noms Docker car les commandes s'exécutent **à l'intérieur** du conteneur Airflow :

```python
BashOperator(
    task_id="check_es",
    bash_command='curl -s http://elasticsearch:9200/_cluster/health',  # ← PAS localhost
)
```

---

## 11. Interface web Airflow — Références rapides

### URL et accès

| Élément | Valeur |
|---------|--------|
| URL | http://localhost:8080 |
| Identifiants | `admin` / `admin` |

### Onglets principaux d'un DAG

| Onglet | Ce qu'il montre |
|--------|-----------------|
| **Grid** | Vue grille avec l'historique des runs (colonnes) et les tâches (lignes) |
| **Graph** | Vue graphique du DAG avec l'état de chaque tâche en couleur |
| **Gantt** | Diagramme temporel montrant la durée de chaque tâche |
| **Code** | Code Python du fichier DAG |

### Couleurs des tâches (onglet Graph)

| Couleur | État | Signification |
|---------|------|---------------|
| Vert clair | `running` | En cours d'exécution |
| Vert foncé | `success` | Terminée avec succès |
| Rouge | `failed` | Échouée (après tous les retries) |
| Jaune | `up_for_retry` | En attente de retry |
| Gris clair | `queued` | En file d'attente |
| Rose/Saumon | `upstream_failed` | Pas exécutée (une tâche amont a échoué) |

### Actions sur une tâche

En cliquant sur une tâche dans le graphe :

| Action | Rôle |
|--------|------|
| **Log** | Afficher les logs de la tâche (stdout + stderr) |
| **Clear** | Effacer l'état et relancer la tâche (+ celles en aval) |
| **Mark Success** | Forcer l'état à success (pour débloquer les tâches en aval) |
| **Mark Failed** | Forcer l'état à failed |

### Déclencher un DAG

1. Cliquer sur le nom du DAG dans la liste.
2. Cliquer sur le bouton **▶ Trigger DAG** en haut à droite.
3. (Optionnel) Passer des paramètres JSON dans le popup de configuration.

---

## 12. Pattern Bash complets utilisés dans les DAGs

### Tâche de vérification de données sources

```bash
DATA_DIR="/opt/airflow/data/arxiv-raw"
FILE_COUNT=$(ls -1 "$DATA_DIR"/*.json 2>/dev/null | wc -l)
if [ "$FILE_COUNT" -eq "0" ]; then
    echo "❌ Aucun fichier trouvé"
    exit 1
fi
echo "✅ $FILE_COUNT fichier(s)"
```

### Tâche de validation (non bloquante)

```bash
cd /opt/airflow
python -m src.quality.validate_arxiv || true
echo "✅ Validation terminée (échecs tolérés)"
```

### Tâche dbt (3 sous-étapes)

```bash
cd /opt/airflow
python -m src.transformation.load_to_postgres   # a) ES → PG

cd /opt/airflow/dbt
dbt run --profiles-dir .                         # b) Modèles
dbt test --profiles-dir .                        # c) Tests
```

### Tâche de polling avec timeout

```bash
for i in $(seq 1 24); do
    COUNT=$(curl -s http://elasticsearch:9200/INDEX/_count | \
            python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" || echo "0")
    [ "$COUNT" -gt "1000" ] && echo "✅ OK" && exit 0
    sleep 5
done
echo "❌ Timeout"
exit 1
```

---

## 13. Récapitulatif des deux DAGs SciPulse

### DAG `scipulse_arxiv_pipeline` (batch)

```
download_arxiv_dump ──▶ validate_raw_arxiv ──▶ ingest_arxiv_logstash
     ──▶ transform_dbt ──▶ enrich_arxiv_python ──▶ validate_enriched
```

| Tâche | Ce qu'elle fait | Bloquante ? |
|-------|----------------|-------------|
| `download_arxiv_dump` | Vérifie les fichiers JSON dans `/data/arxiv-raw/` | Oui (exit 1 si vide) |
| `validate_raw_arxiv` | Exécute GX sur les données brutes | Non (`|| true`) |
| `ingest_arxiv_logstash` | Attend que Logstash ait indexé ≥ 1000 docs | Oui (timeout 2 min) |
| `transform_dbt` | Charge PG + dbt run + dbt test | Oui |
| `enrich_arxiv_python` | TF-IDF + croisement HN | Oui |
| `validate_enriched` | Exécute GX sur les données enrichies | Non (`exit 0` toujours) |

### DAG `scipulse_hn_poller` (micro-batch, toutes les 5 min)

```
poll_hn_api ──▶ detect_arxiv_links ──▶ update_arxiv_hn_scores
```

| Tâche | Ce qu'elle fait |
|-------|----------------|
| `poll_hn_api` | Appelle `hn_poller.py` + affiche le compteur |
| `detect_arxiv_links` | Vérifie les liens ArXiv↔HN dans l'index |
| `update_arxiv_hn_scores` | Affiche les statistiques par type |
