"""Analysis module for Google Scholar author data."""
import json
import argparse
from collections import Counter
import re
from typing import Dict, List, Tuple, Any

try:
    from .ranking_utils import get_venue_rank
except ImportError:
    # Fallback for standalone script usage
    from ranking_utils import get_venue_rank

class ScholarAnalyzer:
    """
    Encapsulates logic for analyzing Google Scholar author data.
    """
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.publications = data.get('publications', [])
        self.name = data.get('name', 'Unknown Author')

    def get_citation_metrics(self) -> Dict[str, Any]:
        """Returns summary dict of citation metrics."""
        total_citations = self.data.get('citedby', 0)
        cites_per_year = self.data.get('cites_per_year', {})
        sorted_years = sorted(cites_per_year.items())
        
        return {
            "total_citations": total_citations,
            "trends": sorted_years
        }

    def _normalize_keyword(self, word: str) -> str:
        """Normalizes a keyword by handling plurals and variations.

        Args:
            word: The keyword to normalize.

        Returns:
            Normalized keyword.
        """
        # Normalize plurals to singular for consistency (conservative approach)
        # Common technical terms that should be normalized (plural -> singular)
        plural_to_singular = {
            'systems': 'system', 'networks': 'network', 'algorithms': 'algorithm',
            'methods': 'method', 'models': 'model', 'approaches': 'approach',
            'techniques': 'technique', 'frameworks': 'framework', 'architectures': 'architecture',
            'designs': 'design', 'implementations': 'implementation', 'evaluations': 'evaluation',
            'analyses': 'analysis', 'optimizations': 'optimization', 'applications': 'application',
            'solutions': 'solution', 'protocols': 'protocol', 'services': 'service',
            'devices': 'device', 'nodes': 'node', 'processes': 'process', 'threads': 'thread',
            'tasks': 'task', 'jobs': 'job', 'requests': 'request', 'queries': 'query',
            'databases': 'database', 'tables': 'table', 'records': 'record', 'entries': 'entry',
            'files': 'file', 'directories': 'directory', 'paths': 'path', 'links': 'link',
            'engines': 'engine', 'servers': 'server', 'clients': 'client', 'users': 'user',
            'interfaces': 'interface', 'components': 'component', 'modules': 'module',
            'features': 'feature', 'functions': 'function', 'operations': 'operation',
            'events': 'event', 'messages': 'message', 'signals': 'signal', 'packets': 'packet',
            'channels': 'channel', 'streams': 'stream', 'flows': 'flow', 'sessions': 'session',
            'policies': 'policy', 'strategies': 'strategy', 'mechanisms': 'mechanism',
            'studies': 'study', 'experiments': 'experiment', 'tests': 'test', 'benchmarks': 'benchmark',
            'metrics': 'metric', 'measurements': 'measurement', 'results': 'result', 'findings': 'finding',
            'cores': 'core', 'processors': 'processor', 'controllers': 'controller',
            'constraints': 'constraint', 'deadlines': 'deadline', 'priorities': 'priority',
            'resources': 'resource', 'workloads': 'workload', 'partitions': 'partition',
            'platforms': 'platform', 'kernels': 'kernel', 'schedulers': 'scheduler',
            'sensors': 'sensor', 'vehicles': 'vehicle', 'robots': 'robot', 'drones': 'drone'
        }

        # Set of known singular forms for pattern matching
        known_singulars = set(plural_to_singular.values())

        # For hyphenated words, normalize the last component's plural
        if '-' in word:
            parts = word.rsplit('-', 1)
            last = parts[1]
            if last in plural_to_singular:
                return f"{parts[0]}-{plural_to_singular[last]}"
            elif last.endswith('s') and len(last) > 3:
                base = last[:-1]
                if base in known_singulars:
                    return f"{parts[0]}-{base}"
            return word

        # Check if word is a known plural form
        if word in plural_to_singular:
            return plural_to_singular[word]
        # Handle common plural patterns for technical terms
        if word.endswith('ies') and len(word) > 4:
            base = word[:-3] + 'y'
            if base in known_singulars:
                return base
        elif word.endswith('es') and len(word) > 3:
            base = word[:-2]
            if base in known_singulars:
                return base
        elif word.endswith('s') and len(word) > 3:
            base = word[:-1]
            if base in known_singulars:
                return base

        return word

    def get_research_areas(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Extracts common keywords from publication titles.
        
        Args:
            top_n: Number of top keywords to return.
        
        Returns:
            List of tuples (keyword, count) sorted by frequency.
        """
        stop_words = {
            'for', 'and', 'the', 'of', 'in', 'a', 'an', 'to', 'on', 'with', 
            'using', 'based', 'analysis', 'via', 'study', 'from', 'by', 
            'network', 'deep', 'learning', 'system', 'systems', 'with',
            'toward', 'towards', 'this', 'that', 'these', 'those', 'are',
            'is', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had'
        }
        
        words = []
        for pub in self.publications:
            title = pub.get('bib', {}).get('title', '').lower()
            # Match words with at least 3 letters, including hyphenated words (e.g., "real-time", "multi-core")
            tokens = re.findall(r'\b[a-z]+(?:-[a-z]+)*[a-z]{2,}\b', title)
            
            for token in tokens:
                if token not in stop_words:
                    # Normalize equivalent terms automatically
                    normalized = self._normalize_keyword(token)
                    words.append(normalized)
            
        return Counter(words).most_common(top_n)

    def get_authorship_stats(self) -> Dict[str, int]:
        """Analyzes position in author list."""
        positions = {"First": 0, "Last": 0, "Middle": 0, "Single": 0}
        
        target_parts = self.name.lower().split()
        target_surname = target_parts[-1] if target_parts else ""
        
        for pub in self.publications:
            author_str = pub.get('bib', {}).get('author', '')
            if not author_str:
                continue
                
            # Handle "Name, Other" and "Name and Other"
            authors = [a.strip() for a in re.split(r',|\sand\s', author_str)]
            
            # Find index
            match_idx = -1
            for i, a in enumerate(authors):
                if target_surname in a.lower():
                    match_idx = i
                    break
            
            if match_idx == -1:
                continue
                
            if len(authors) == 1:
                positions["Single"] += 1
            elif match_idx == 0:
                positions["First"] += 1
            elif match_idx == len(authors) - 1:
                positions["Last"] += 1
            else:
                positions["Middle"] += 1
                
        return positions

    def get_publication_ranks(self, verbose: bool = False) -> Dict[str, int]:
        """Categorizes publications by venue rank.
        
        Args:
            verbose: If True, prints intermediate results for each publication.
        
        Returns:
            Dictionary mapping rank categories to counts.
        """
        rank_counts = {"A*": 0, "A": 0, "B": 0, "C": 0, "Unranked": 0, "No Venue Found": 0}
        
        if verbose:
            print("\n" + "="*80)
            print("PUBLICATION RANKING ANALYSIS")
            print("="*80)
        
        for i, pub in enumerate(self.publications, 1):
            bib = pub.get('bib', {})
            title = bib.get('title', 'Unknown Title')
            venue = bib.get('venue') or bib.get('journal') or bib.get('conference') or ''
            if not venue:
                # Extract venue from citation string (format: "Venue, pages, year")
                citation = bib.get('citation', '')
                if citation:
                    venue = re.sub(r',\s*\d{4}\s*$', '', citation)
                    venue = re.sub(r',\s*[\d\u2013-]+\s*$', '', venue)
                    venue = re.sub(r'[\s\u2026.]*$', '', venue)
                    venue = re.sub(r'\s+(?:and|of|the|in|on|for|with|a|an)\s*$', '', venue, flags=re.IGNORECASE).strip()

            if verbose:
                print(f"\n[{i}/{len(self.publications)}] {title[:60]}...")
                print(f"  Venue: {venue if venue else 'NOT FOUND'}")

            if not venue:
                rank_counts["No Venue Found"] += 1
                if verbose:
                    print(f"  Rank: No Venue Found")
                continue
                
            rank = get_venue_rank(venue)
            
            # Get IF and SJR for journals
            try:
                from .ranking_utils import get_venue_metrics
            except ImportError:
                from ranking_utils import get_venue_metrics
            rank_result, impact_factor, sjr = get_venue_metrics(venue)
            
            if rank in rank_counts:
                rank_counts[rank] += 1
                if verbose:
                    metrics_str = ""
                    if impact_factor is not None:
                        metrics_str += f", IF: {impact_factor:.2f}" if isinstance(impact_factor, (int, float)) else f", IF: {impact_factor}"
                    if sjr is not None:
                        metrics_str += f", SJR: {sjr:.2f}" if isinstance(sjr, (int, float)) else f", SJR: {sjr}"
                    print(f"  Rank: {rank}{metrics_str}")
            else:
                rank_counts["Unranked"] += 1
                if verbose:
                    metrics_str = ""
                    if impact_factor is not None:
                        metrics_str += f", IF: {impact_factor:.2f}" if isinstance(impact_factor, (int, float)) else f", IF: {impact_factor}"
                    if sjr is not None:
                        metrics_str += f", SJR: {sjr:.2f}" if isinstance(sjr, (int, float)) else f", SJR: {sjr}"
                    print(f"  Rank: Unranked (matched as '{rank}'){metrics_str}")
        
        if verbose:
            print("\n" + "="*80)
            print("RANKING SUMMARY")
            print("="*80)
            for rank, count in rank_counts.items():
                if count > 0:
                    print(f"  {rank}: {count}")
            print("="*80 + "\n")
                
        return rank_counts

def load_data(filepath: str) -> Dict[str, Any]:
    """Loads author data from a JSON file.
    
    Args:
        filepath: Path to the JSON file.
    
    Returns:
        Dictionary containing author data.
    
    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def print_report(analyzer: ScholarAnalyzer, verbose_ranking: bool = False):
    """Print analysis report.
    
    Args:
        analyzer: ScholarAnalyzer instance.
        verbose_ranking: If True, show intermediate results during ranking.
    """
    print(f"Analysis for Author: {analyzer.name}")
    print("="*40)
    
    # Citations
    cit_stats = analyzer.get_citation_metrics()
    print(f"Total Citations: {cit_stats['total_citations']}")
    print("Citation Trend (Year: Count):")
    for year, count in cit_stats['trends'][-5:]:
        print(f"  {year}: {count}")
        
    print("-" * 20)
    
    # Research Areas
    print("Key Research Terms (from Titles):")
    areas = analyzer.get_research_areas()
    for term, count in areas:
        print(f"  {term}: {count}")
        
    print("-" * 20)
    
    # Authorship
    print("Authorship Position Distribution:")
    auth_stats = analyzer.get_authorship_stats()
    for pos, count in auth_stats.items():
        print(f"  {pos}: {count}")
        
    print("-" * 20)
    
    # Ranks
    print("Publication Ranks:")
    rank_stats = analyzer.get_publication_ranks(verbose=verbose_ranking)
    # Only print summary if not in verbose mode (verbose mode already prints it)
    if not verbose_ranking:
        for rank, count in rank_stats.items():
            print(f"  {rank}: {count}")

def main():
    parser = argparse.ArgumentParser(description="Analyze Google Scholar JSON data.")
    parser.add_argument("--file", type=str, default="author_data.json", help="Path to JSON file.")
    parser.add_argument("--verbose-ranking", action="store_true", 
                       help="Show intermediate results when ranking publications.")
    args = parser.parse_args()
    
    try:
        data = load_data(args.file)
        analyzer = ScholarAnalyzer(data)
        print_report(analyzer, verbose_ranking=args.verbose_ranking)
    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{args.file}'.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
