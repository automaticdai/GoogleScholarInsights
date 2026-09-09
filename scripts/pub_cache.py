"""Per-author cache of filled Google Scholar publications.

Fetching a profile costs one request for the author listing plus one request
per publication, and the per-publication requests are what triggers Scholar's
rate limiting. Almost everything those requests return is static: the
abstract, the author list, the venue, the publication URL. Only the citation
count moves, and the author listing already carries it.

So this module stores the filled publications once, keyed by Scholar's stable
``author_pub_id``, and lets a later run rebuild the same records from the
listing alone. Each author gets its own file, so alternating between profiles
never evicts the other's entries.

This module deliberately does not import ``scholarly`` — it holds no network
code and is unit-testable on its own.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_VERSION = 1
DEFAULT_CACHE_DIR = ".scholar_cache"

# Scholar IDs are alphanumeric with - and _; anything else is not one of ours.
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def cache_path_for(scholar_id: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Returns the cache file path for one author.

    Args:
        scholar_id: Google Scholar ID of the author.
        cache_dir: Directory holding the per-author cache files.

    Returns:
        Path to this author's cache file, always directly inside cache_dir.
    """
    safe_id = _UNSAFE.sub("_", scholar_id) or "unknown"
    return os.path.join(cache_dir, f"{safe_id}.json")


def load_cache(path: str) -> Dict[str, Dict[str, Any]]:
    """Loads cached publications, keyed by author_pub_id.

    A missing or unreadable cache is not an error: it just means everything
    has to be fetched.

    Args:
        path: Path to a cache file written by save_cache.

    Returns:
        Mapping of author_pub_id to filled publication, empty if unavailable.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
        return {}

    publications = raw.get("publications")
    return publications if isinstance(publications, dict) else {}


def save_cache(path: str, entries: Dict[str, Dict[str, Any]],
               scholar_id: str = "") -> None:
    """Writes the cache for one author, creating the directory if needed.

    Args:
        path: Destination path from cache_path_for.
        entries: Mapping of author_pub_id to filled publication.
        scholar_id: Author the entries belong to, recorded for inspection.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    payload = {
        "version": CACHE_VERSION,
        "scholar_id": scholar_id,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "publications": entries,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def needs_fetch(stub: Dict[str, Any], cached: Optional[Dict[str, Any]]) -> bool:
    """Reports whether a publication still has to be fetched from Scholar.

    Args:
        stub: Publication as it appears in the author listing.
        cached: Matching cache entry, or None if there is no hit.

    Returns:
        True if the publication must be fetched.
    """
    if not cached or not cached.get("filled"):
        return True
    # The cache only skips a fetch because the listing supplies a fresh
    # citation count. Without one, a cache hit would serve a stale number.
    return stub.get("num_citations") is None


def merge(stub: Dict[str, Any], cached: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuilds a filled publication from a cache entry and a fresh listing.

    Static fields come from the cache; anything the listing reports fresh
    wins over the cached copy.

    Args:
        stub: Publication as it appears in the author listing.
        cached: Matching cache entry.

    Returns:
        A new publication dict; neither argument is modified.
    """
    merged = json.loads(json.dumps(cached, default=str))

    if stub.get("num_citations") is not None:
        merged["num_citations"] = stub["num_citations"]
    if stub.get("cites_per_year"):
        merged["cites_per_year"] = stub["cites_per_year"]

    return merged


def resolve_publications(stubs, cached_entries, fetch_fn, wait_fn=None,
                         refresh=False):
    """Builds the full publication list, fetching only what is not cached.

    Args:
        stubs: Publications from the author listing, in profile order.
        cached_entries: Mapping from load_cache. Updated in place as each
            fetch completes, so a caller interrupted part-way through a long
            run can still save the work already done.
        fetch_fn: Callable taking a stub and returning a filled publication,
            or None if the fetch failed.
        wait_fn: Called between successive fetches for rate limiting.
        refresh: Fetch every publication, ignoring cache hits.

    Returns:
        Tuple of (publications, entries). Entries carries the cached
        publications forward, including any not in this listing, so a
        --limit run does not discard the rest of the author's work.
    """
    entries = cached_entries
    publications = []
    fetched = 0

    for stub in stubs:
        pub_id = stub.get("author_pub_id")
        cached = entries.get(pub_id) if pub_id else None
        title = stub.get("bib", {}).get("title", "Unknown")

        if not refresh and pub_id and not needs_fetch(stub, cached):
            logger.info("Reusing cached details: %s", title[:60])
            publications.append(merge(stub, cached))
            continue

        if fetched and wait_fn:
            wait_fn()
        fetched += 1

        logger.info("Fetching details: %s", title[:60])
        filled = fetch_fn(stub)
        if filled is None:
            logger.warning("Using partial data for: %s", title[:60])
            publications.append(stub)
            continue

        publications.append(filled)
        if pub_id:
            entries[pub_id] = filled

    return publications, entries
