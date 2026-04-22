"""
SciPulse — DAG secondaire : poller Hacker News (micro-batch)
Exécuté toutes les 5 minutes pour récupérer les derniers items HN.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "scipulse",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="scipulse_hn_poller",
    default_args=default_args,
    description="Polling Hacker News : ingestion micro-batch + détection liens ArXiv",
    schedule_interval="*/5 * * * *",  # Toutes les 5 minutes
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["scipulse", "hacker-news", "streaming"],
) as dag:

    # ── 1. Polling de l'API HN ──────────────────────────────────────────
    poll_hn = BashOperator(
        task_id="poll_hn_api",
        bash_command="cd /opt/airflow && python -m src.ingestion.hn_poller",
    )

    # ── 2. Détection des liens ArXiv dans les posts HN ──────────────────
    detect_links = BashOperator(
        task_id="detect_arxiv_links",
        bash_command="""
            echo "🔗 Vérification des liens ArXiv dans les derniers posts HN..."
            # Le poller détecte déjà les liens ArXiv lors de l'indexation
            # Cette tâche peut servir à un second passage ou à des enrichissements
            # TODO : python -m src.enrichment.detect_arxiv_links
            echo "  → Détection de liens intégrée au poller"
        """,
    )

    # ── 3. Mise à jour des scores croisés ────────────────────────────────
    update_scores = BashOperator(
        task_id="update_arxiv_hn_scores",
        bash_command="""
            echo "📊 Mise à jour des scores croisés ArXiv ↔ HN..."
            # TODO : python -m src.enrichment.update_hn_scores
            echo "  → Mise à jour des scores à implémenter"
        """,
    )

    poll_hn >> detect_links >> update_scores
