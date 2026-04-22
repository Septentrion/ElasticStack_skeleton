"""
SciPulse — DAG principal : pipeline ArXiv (batch)
Orchestration complète : download → validate → ingest → transform → enrich → validate
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "scipulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="scipulse_arxiv_pipeline",
    default_args=default_args,
    description="Pipeline batch ArXiv : ingestion, transformation, enrichissement",
    schedule_interval=None,  # Déclenchement manuel pour le TP
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["scipulse", "arxiv", "batch"],
) as dag:

    # ── 1. Téléchargement du dump ArXiv vers MinIO ───────────────────────
    download_arxiv = BashOperator(
        task_id="download_arxiv_dump",
        bash_command="""
            echo "📥 Téléchargement du dump ArXiv..."
            # TODO : Adapter le chemin ou utiliser kaggle CLI
            # kaggle datasets download -d Cornell-University/arxiv -p /opt/airflow/data/arxiv-raw/
            echo "  → Vérifier que les fichiers sont dans /opt/airflow/data/arxiv-raw/"
            ls -lh /opt/airflow/data/arxiv-raw/ || echo "⚠️  Pas de fichiers trouvés"
        """,
    )

    # ── 2. Validation des données brutes (Great Expectations) ────────────
    validate_raw = BashOperator(
        task_id="validate_raw_arxiv",
        bash_command="""
            echo "🔍 Validation des données brutes ArXiv..."
            # TODO : great_expectations checkpoint run arxiv_raw_checkpoint
            echo "  → Checkpoint GE à implémenter"
        """,
    )

    # ── 3. Ingestion via Logstash ────────────────────────────────────────
    ingest_logstash = BashOperator(
        task_id="ingest_arxiv_logstash",
        bash_command="""
            echo "🔄 Ingestion ArXiv via Logstash..."
            # Logstash tourne en continu et surveille /data/arxiv-raw/
            # On vérifie simplement que l'index a reçu des documents
            curl -s http://elasticsearch:9200/arxiv-papers-raw/_count | python3 -c "
import sys, json
data = json.load(sys.stdin)
count = data.get('count', 0)
print(f'  → {count} documents dans arxiv-papers-raw')
if count == 0:
    print('⚠️  Aucun document indexé — vérifier Logstash')
    sys.exit(1)
"
        """,
    )

    # ── 4. Transformation dbt ────────────────────────────────────────────
    transform_dbt = BashOperator(
        task_id="transform_dbt",
        bash_command="""
            echo "⚙️  Transformation dbt..."
            # TODO : cd /opt/airflow/dbt && dbt run && dbt test
            echo "  → dbt run + dbt test à implémenter"
        """,
    )

    # ── 5. Enrichissement Python (NLP + croisement HN) ───────────────────
    enrich_python = BashOperator(
        task_id="enrich_arxiv_python",
        bash_command="""
            echo "🧠 Enrichissement NLP et croisement ArXiv × HN..."
            # TODO : python -m src.enrichment.enrich_arxiv
            echo "  → Enrichissement à implémenter"
        """,
    )

    # ── 6. Validation des données enrichies ──────────────────────────────
    validate_enriched = BashOperator(
        task_id="validate_enriched",
        bash_command="""
            echo "✅ Validation des données enrichies..."
            # TODO : great_expectations checkpoint run arxiv_enriched_checkpoint
            echo "  → Checkpoint GE final à implémenter"
        """,
    )

    # ── Dépendances ──────────────────────────────────────────────────────
    download_arxiv >> validate_raw >> ingest_logstash >> transform_dbt >> enrich_python >> validate_enriched
