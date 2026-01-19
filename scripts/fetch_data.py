"""Data fetching module for Google Scholar profiles."""
import argparse
import json
import logging
import time
import random
from typing import Optional, List, Dict, Any
import requests
from scholarly import scholarly, ProxyGenerator
from fake_useragent import UserAgent

# Logger config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Rate limiting configuration (to avoid IP bans)
MIN_DELAY_BETWEEN_PUBS = 2.0  # Minimum seconds between publication fetches
MAX_DELAY_BETWEEN_PUBS = 5.0  # Maximum seconds between publication fetches
MIN_DELAY_BETWEEN_SEARCHES = 1.0  # Minimum seconds between search queries
MAX_DELAY_BETWEEN_SEARCHES = 3.0  # Maximum seconds between search queries
RETRY_BASE_DELAY = 5.0  # Base delay for exponential backoff
MAX_RETRY_DELAY = 60.0  # Maximum retry delay
MAX_RETRIES = 3  # Maximum number of retry attempts

def setup_proxy() -> bool:
    """Sets up a free proxy generator and custom session.
    
    Returns:
        bool: True if proxy was set successfully, False otherwise.
    """
    logger.info("Setting up proxy and session...")
    
    # Note: Newer versions of scholarly may not support set_session
    # Try to set custom headers via the navigator if available
    try:
        # Try to set custom user agent via navigator
        if hasattr(scholarly, '_navigator') and hasattr(scholarly._navigator, 'set_user_agent'):
            try:
                ua = UserAgent()
                user_agent = ua.random
            except Exception:
                user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            scholarly._navigator.set_user_agent(user_agent)
    except Exception as e:
        logger.debug(f"Could not set custom user agent: {e}")

    try:
        pg = ProxyGenerator()
        # Try free proxies (may fail due to API changes or availability)
        try:
            if pg.FreeProxies():
                logger.info("Proxy set successfully.")
                scholarly.use_proxy(pg)
                return True
            else:
                logger.warning("Failed to set proxy. Proceeding without proxy.")
                return False
        except TypeError as e:
            # Handle API changes in FreeProxies
            logger.warning(f"FreeProxies API may have changed: {e}. Proceeding without proxy.")
            return False
    except Exception as e:
        logger.warning(f"Proxy setup failed with error: {e}. Proceeding without proxy.")
        return False

def safe_fetch_with_retry(fetch_func, *args, max_retries: int = MAX_RETRIES, **kwargs):
    """Safely fetch data with exponential backoff retry logic.
    
    Args:
        fetch_func: Function to call for fetching data.
        *args: Positional arguments for fetch_func.
        max_retries: Maximum number of retry attempts.
        **kwargs: Keyword arguments for fetch_func.
    
    Returns:
        Result from fetch_func, or None if all retries failed.
    """
    for attempt in range(max_retries):
        try:
            return fetch_func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                logger.warning(f"Fetch failed (attempt {attempt + 1}/{max_retries}): {e}")
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"Fetch failed after {max_retries} attempts: {e}")
                return None

def fetch_by_id(scholar_id: str, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Fetches author data by Scholar ID.
    
    Args:
        scholar_id: Google Scholar ID of the author.
        limit: Maximum number of publications to fetch full details for.
    
    Returns:
        Dictionary containing author data, or None if fetch failed.
    """
    logger.info(f"Fetching author with ID: {scholar_id}")
    try:
        author = scholarly.search_author_id(scholar_id)
        logger.info(f"Found author: {author.get('name', 'Unknown')} (ID: {author.get('scholar_id', 'N/A')})")
        
        # Fill data
        author = scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
        
        # Process publications
        pubs_to_process = author.get('publications', [])
        if limit and limit > 0:
            pubs_to_process = pubs_to_process[:limit]
            logger.info(f"Limiting detailed fetch to first {limit} publications.")
            
        full_pubs = []
        total_pubs = len(pubs_to_process)
        start_time = time.time()
        
        for i, pub in enumerate(pubs_to_process, 1):
            title = pub.get('bib', {}).get('title', 'Unknown')
            logger.info(f"Fetching details for publication {i}/{total_pubs}: {title[:60]}...")
            
            # Fetch with retry logic
            full_pub = safe_fetch_with_retry(scholarly.fill, pub)
            if full_pub:
                full_pubs.append(full_pub)
            else:
                logger.warning(f"Using partial data for publication {i}")
                full_pubs.append(pub)
            
            # Rate limiting: add delay between fetches (except after last one)
            if i < total_pubs:
                delay = random.uniform(MIN_DELAY_BETWEEN_PUBS, MAX_DELAY_BETWEEN_PUBS)
                
                # Calculate and display progress
                elapsed = time.time() - start_time
                avg_time_per_pub = elapsed / i
                remaining_pubs = total_pubs - i
                estimated_remaining = avg_time_per_pub * remaining_pubs + delay * remaining_pubs
                
                logger.info(f"Waiting {delay:.1f}s before next fetch... "
                          f"(~{estimated_remaining/60:.1f} min remaining)")
                time.sleep(delay)

        author['publications'] = full_pubs
        return author
    except Exception as e:
        logger.error(f"Error fetching by ID: {e}")
        return None

def search_candidates(author_name: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Matches authors by name and returns a list of candidates.
    
    Args:
        author_name: Name of the author to search for.
        max_results: Maximum number of candidates to return.
    
    Returns:
        List of candidate author dictionaries.
    """
    logger.info(f"Searching for candidates matching: {author_name}")
    try:
        search_query = scholarly.search_author(author_name)
        candidates = []
        for i in range(max_results):
            try:
                author = next(search_query)
                candidates.append(author)
                
                # Rate limiting: add delay between search results
                if i < max_results - 1:
                    delay = random.uniform(MIN_DELAY_BETWEEN_SEARCHES, MAX_DELAY_BETWEEN_SEARCHES)
                    logger.info(f"Waiting {delay:.1f}s before next search query...")
                    time.sleep(delay)
            except StopIteration:
                break
        return candidates
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Fetch Google Scholar data.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--author", type=str, help="Name of the author to search.")
    group.add_argument("--id", type=str, help="Google Scholar ID of the author.")
    
    parser.add_argument("--limit", type=int, default=10, help="Limit number of publications to fetch details for (default 10).")
    parser.add_argument("--output", type=str, default="author_data.json", help="Output JSON file.")
    
    # Rate limiting arguments
    parser.add_argument("--min-delay", type=float, default=2.0, 
                       help="Minimum delay between requests in seconds (default: 2.0).")
    parser.add_argument("--max-delay", type=float, default=5.0,
                       help="Maximum delay between requests in seconds (default: 5.0).")
    parser.add_argument("--no-delay", action="store_true",
                       help="Disable rate limiting delays (NOT RECOMMENDED - may cause IP ban).")
    
    args = parser.parse_args()
    
    # Override global delay settings if specified
    global MIN_DELAY_BETWEEN_PUBS, MAX_DELAY_BETWEEN_PUBS
    if args.no_delay:
        logger.warning("Rate limiting disabled! This may result in IP ban from Google Scholar.")
        MIN_DELAY_BETWEEN_PUBS = 0
        MAX_DELAY_BETWEEN_PUBS = 0
    else:
        MIN_DELAY_BETWEEN_PUBS = args.min_delay
        MAX_DELAY_BETWEEN_PUBS = args.max_delay
        logger.info(f"Rate limiting enabled: {MIN_DELAY_BETWEEN_PUBS:.1f}s - {MAX_DELAY_BETWEEN_PUBS:.1f}s between requests")
    
    setup_proxy()
    
    if args.id:
        data = fetch_by_id(args.id, args.limit)
    else:
        # Search mode
        candidates = search_candidates(args.author)
        if not candidates:
            logger.info("No candidates found.")
            return
            
        if len(candidates) == 1:
            logger.info("Single match found. Fetching data...")
            data = fetch_by_id(candidates[0]['scholar_id'], args.limit)
        else:
            print(f"\nMultiple candidates found for '{args.author}':")
            for i, c in enumerate(candidates, 1):
                name = c.get('name', 'Unknown')
                scholar_id = c.get('scholar_id', 'N/A')
                affiliation = c.get('affiliation', 'No affiliation')
                print(f"{i}. {name} (ID: {scholar_id}) - {affiliation}")
            
            print("\nPlease re-run with --id <ID> to fetch specific data.")
            return

    if data:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, default=str)
            logger.info(f"Data saved to {args.output}")
        except IOError as e:
            logger.error(f"Failed to save data to {args.output}: {e}")
    else:
        logger.error("No data fetched.")

if __name__ == "__main__":
    main()
