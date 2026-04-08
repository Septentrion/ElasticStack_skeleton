"""
SciPulse — Hacker News Poller
Polling de l'API Firebase HN et indexation dans Elasticsearch.

Usage :
    python -m src.ingestion.hn_poller              # un seul cycle
    python -m src.ingestion.hn_poller --continuous  # boucle toutes les 60s
"""

import argparse
import logging
import re
import time
from datetime import datetime, timezone

import requests
from elasticsearch import Elasticsearch, helpers

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
ES_HOST = "http://localhost:9200"
ES_INDEX_HN = "hn-items"
ES_INDEX_LINKS = "arxiv-hn-links"
ARXIV_URL_PATTERN = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)")
BATCH_SIZE = 50
POLL_INTERVAL = 60  # secondes


def get_es_client() -> Elasticsearch:
    return Elasticsearch(ES_HOST)


def fetch_new_story_ids() -> list[int]:
    """Récupère les 500 derniers IDs de stories depuis l'API HN."""
    resp = requests.get(f"{HN_API_BASE}/newstories.json", timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_item(item_id: int) -> dict | None:
    """Récupère le détail d'un item HN."""
    try:
        resp = requests.get(f"{HN_API_BASE}/item/{item_id}.json", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Erreur fetch item {item_id}: {e}")
        return None


def extract_arxiv_id(url: str | None) -> str | None:
    """Extrait l'ID ArXiv depuis une URL si elle pointe vers arxiv.org."""
    if not url:
        return None
    match = ARXIV_URL_PATTERN.search(url)
    return match.group(1) if match else None


def item_exists(es: Elasticsearch, item_id: int) -> bool:
    """Vérifie si un item HN est déjà indexé."""
    return es.exists(index=ES_INDEX_HN, id=str(item_id))


def prepare_hn_doc(item: dict) -> dict:
    """Transforme un item HN brut en document ES."""
    doc = {
        "hn_id": str(item["id"]),
        "type": item.get("type", "story"),
        "by": item.get("by"),
        "time": item.get("time"),
        "title": item.get("title"),
        "url": item.get("url"),
        "text": item.get("text"),
        "score": item.get("score", 0),
        "descendants": item.get("descendants", 0),
        "parent": str(item["parent"]) if item.get("parent") else None,
    }

    # Relation parent-child pour les commentaires
    if item.get("type") == "comment" and item.get("parent"):
        doc["relation"] = {"name": "comment", "parent": str(item["parent"])}
    else:
        doc["relation"] = {"name": "story"}

    # Détection de lien ArXiv
    arxiv_id = extract_arxiv_id(item.get("url"))
    if arxiv_id:
        doc["arxiv_id_linked"] = arxiv_id

    return doc


def index_batch(es: Elasticsearch, items: list[dict]) -> int:
    """Indexe un batch de documents HN dans Elasticsearch."""
    actions = []
    links = []

    for item in items:
        if not item or not item.get("id"):
            continue

        doc = prepare_hn_doc(item)

        # Action d'indexation HN
        action = {
            "_index": ES_INDEX_HN,
            "_id": doc["hn_id"],
            "_source": doc,
        }
        # Routing pour les commentaires (parent-child)
        if doc.get("parent") and doc["type"] == "comment":
            action["_routing"] = doc["parent"]

        actions.append(action)

        # Si lien ArXiv détecté → créer aussi un document de liaison
        if doc.get("arxiv_id_linked"):
            links.append(
                {
                    "_index": ES_INDEX_LINKS,
                    "_id": f"{doc['arxiv_id_linked']}_{doc['hn_id']}",
                    "_source": {
                        "arxiv_id": doc["arxiv_id_linked"],
                        "hn_item_id": doc["hn_id"],
                        "hn_score": doc.get("score", 0),
                        "hn_comments": doc.get("descendants", 0),
                        "hn_title": doc.get("title"),
                        "hn_url": doc.get("url"),
                        "hn_time": doc.get("time"),
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                    },
                }
            )

    if not actions:
        return 0

    all_actions = actions + links
    success, errors = helpers.bulk(es, all_actions, raise_on_error=False)

    if errors:
        logger.warning(f"{len(errors)} erreurs lors de l'indexation")

    if links:
        logger.info(f"  🔗 {len(links)} lien(s) ArXiv détecté(s)")

    return success


def poll_once(es: Elasticsearch) -> int:
    """Exécute un cycle de polling : récupère les nouvelles stories et les indexe."""
    story_ids = fetch_new_story_ids()
    logger.info(f"📡 {len(story_ids)} story IDs récupérés depuis l'API HN")

    # Filtrer les items déjà indexés
    new_ids = [sid for sid in story_ids[:100] if not item_exists(es, sid)]
    logger.info(f"  → {len(new_ids)} nouveaux items à indexer")

    if not new_ids:
        return 0

    total_indexed = 0
    for i in range(0, len(new_ids), BATCH_SIZE):
        batch_ids = new_ids[i : i + BATCH_SIZE]
        items = [fetch_item(sid) for sid in batch_ids]
        items = [it for it in items if it is not None]
        count = index_batch(es, items)
        total_indexed += count
        logger.info(f"  ✅ Batch {i // BATCH_SIZE + 1}: {count} documents indexés")

    return total_indexed


def main():
    # Options possibles en ligne de commande
    parser = argparse.ArgumentParser(description="SciPulse — HN Poller")
    parser.add_argument(
        "--continuous", action="store_true", help="Boucle de polling continue"
    )
    parser.add_argument(
        "--interval", type=int, default=POLL_INTERVAL, help="Intervalle en secondes"
    )
    args = parser.parse_args()

    es = get_es_client()
    logger.info(f"Connexion ES: {es.info()['cluster_name']}")

    if args.continuous:
        logger.info(
            f"🔄 Mode continu — polling toutes les {args.interval}s (Ctrl+C pour arrêter)"
        )
        while True:
            try:
                poll_once(es)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                logger.info("⏹  Arrêt du poller.")
                break
    else:
        total = poll_once(es)
        logger.info(f"🏁 Cycle terminé — {total} documents indexés au total.")


if __name__ == "__main__":
    main()
