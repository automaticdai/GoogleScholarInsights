"""Utility module for publication ranking.

Ranking Systems:
- Conferences: Based on CORE Conference Ranking (A*, A, B, C)
  See: https://portal.core.edu.au/conf-ranks/
- Journals: CORE discontinued journal rankings in Feb 2022.
  Journal rankings use alternative metrics (Impact Factor, SJR, Q1/Q2 quartiles)
  while maintaining CORE's A*/A/B/C tier system for consistency.
"""
import json
import os
import re
from typing import Dict, Optional, Any, Tuple

# Path to the ranking database
RANKING_DB_PATH = os.path.join(os.path.dirname(__file__), 'venue_ranks.json')

def load_rankings() -> Dict[str, Any]:
    """Loads venue rankings from JSON file.
    
    Returns:
        Dictionary mapping venue names (lowercase) to their ranks (string) or 
        extended data (dict with rank, impact_factor, sjr).
    """
    try:
        with open(RANKING_DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Ranking database not found at {RANKING_DB_PATH}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse ranking database: {e}")
        return {}
    except Exception as e:
        print(f"Warning: Could not load ranking database from {RANKING_DB_PATH}: {e}")
        return {}

def get_venue_metrics(venue_name: Optional[str]) -> Tuple[str, Optional[float], Optional[float]]:
    """Returns rank, impact factor, and SJR for a venue.
    
    Args:
        venue_name: Name of the venue (journal/conference).
    
    Returns:
        Tuple of (rank, impact_factor, sjr). IF and SJR are None for conferences or if not available.
    """
    rank = get_venue_rank(venue_name)
    
    if not venue_name:
        return (rank, None, None)
    
    name_normalized = normalize_venue_name(venue_name)
    if not name_normalized:
        return (rank, None, None)
    
    # Check if we have extended data for this venue
    venue_data = VENUE_RANKS.get(name_normalized)
    if isinstance(venue_data, dict):
        return (rank, venue_data.get('impact_factor'), venue_data.get('sjr'))
    
    # Check normalized matches
    for key, value in VENUE_RANKS.items():
        key_normalized = normalize_venue_name(key)
        if key_normalized == name_normalized:
            if isinstance(value, dict):
                return (rank, value.get('impact_factor'), value.get('sjr'))
            break
    
    # Also check fuzzy matches for extended data
    for key, value in VENUE_RANKS.items():
        key_normalized = normalize_venue_name(key)
        min_length = min(len(key_normalized), len(name_normalized))
        if min_length >= 5:
            if key_normalized in name_normalized or name_normalized in key_normalized:
                if isinstance(value, dict):
                    return (rank, value.get('impact_factor'), value.get('sjr'))
                break
    
    return (rank, None, None)

VENUE_RANKS = load_rankings()

def normalize_venue_name(venue_name: str) -> str:
    """Normalizes venue name for robust matching.
    
    Handles common variations:
    - "&" vs "and"
    - Punctuation differences
    - Multiple whitespace
    - Common abbreviations and variations
    
    Args:
        venue_name: Raw venue name.
    
    Returns:
        Normalized venue name string.
    """
    if not venue_name:
        return ""
    
    # Convert to lowercase
    normalized = venue_name.lower()
    
    # Replace "&" with "and" (and variations)
    normalized = re.sub(r'\s*&\s*', ' and ', normalized)
    normalized = re.sub(r'\s+and\s+', ' and ', normalized)
    
    # Normalize punctuation
    normalized = re.sub(r'[()]', '', normalized)  # Remove parentheses
    normalized = re.sub(r'[,;:]', '', normalized)  # Remove common punctuation
    normalized = re.sub(r'[-–—]', ' ', normalized)  # Normalize dashes to spaces
    
    # Normalize whitespace (multiple spaces to single space)
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip leading/trailing whitespace
    normalized = normalized.strip()
    
    return normalized

def extract_acronym_from_name(full_name: str) -> str:
    """Extracts potential acronym from a full venue name.
    
    Args:
        full_name: Full venue name.
    
    Returns:
        Potential acronym string (e.g., "RTSS" from "Real-Time Systems Symposium").
    """
    words = full_name.split()
    acronym = ""
    for word in words:
        # Skip very short words and common stop words
        if len(word) > 0 and word[0].isalpha() and word.lower() not in ['the', 'of', 'on', 'and', 'for', 'in', 'a', 'an']:
            acronym += word[0].upper()
    return acronym

def match_acronym_to_full_name(acronym: str, full_name: str) -> bool:
    """Checks if an acronym matches a full venue name.
    
    Args:
        acronym: Acronym to match (e.g., "RTSS").
        full_name: Full venue name (e.g., "Real-Time Systems Symposium").
    
    Returns:
        True if acronym matches the full name.
    """
    acronym_upper = acronym.upper()
    words = full_name.split()
    
    # Extract first letters of significant words
    first_letters = ""
    for word in words:
        word_clean = re.sub(r'[^a-zA-Z]', '', word)
        if len(word_clean) > 0 and word_clean.lower() not in ['the', 'of', 'on', 'and', 'for', 'in', 'a', 'an', 'to']:
            first_letters += word_clean[0].upper()
    
    # Check if acronym matches first letters
    return acronym_upper == first_letters

def _extract_rank(value: any) -> str:
    """Extracts rank from either string or dict format.
    
    Args:
        value: Either a string rank (e.g., "A*") or dict with "rank" key.
    
    Returns:
        Rank string.
    """
    if isinstance(value, dict):
        return value.get('rank', 'Unranked')
    return value

def get_venue_rank(venue_name: Optional[str]) -> str:
    """Returns the rank (A*, A, B, C) or 'Unranked' for a given venue name.
    
    Uses robust matching that handles variations like "&" vs "and",
    punctuation differences, whitespace variations, and acronym matching.
    
    Args:
        venue_name: Name of the venue (journal/conference).
    
    Returns:
        Rank string (A*, A, B, C, or Unranked).
    """
    if not venue_name:
        return "Unranked"

    # Normalize the input venue name
    name_normalized = normalize_venue_name(venue_name)

    if not name_normalized:
        return "Unranked"
    
    # Direct match with normalized name
    if name_normalized in VENUE_RANKS:
        return _extract_rank(VENUE_RANKS[name_normalized])
    
    # Try matching against normalized database entries
    # First, try exact match after normalizing both
    for key, value in VENUE_RANKS.items():
        key_normalized = normalize_venue_name(key)
        if key_normalized == name_normalized:
            return _extract_rank(value)
    
    # Check if input is a short acronym (<= 6 chars, no spaces) - try matching to full names
    name_clean = re.sub(r'[^a-zA-Z0-9]', '', venue_name.upper())
    if len(name_clean) <= 6 and len(name_clean) >= 2 and ' ' not in venue_name:
        # Try to match acronym to full names in database
        for key, value in VENUE_RANKS.items():
            # Skip if key is also a short acronym
            key_clean = re.sub(r'[^a-zA-Z0-9]', '', key.upper())
            if len(key_clean) > 6 or ' ' in key:
                # This is a full name, check if acronym matches
                if match_acronym_to_full_name(name_clean, key):
                    return _extract_rank(value)
    
    # Fuzzy match: check if normalized key is substring of normalized name or vice versa
    for key, value in VENUE_RANKS.items():
        key_normalized = normalize_venue_name(key)
        # Check if one contains the other (with minimum length to avoid false matches)
        min_length = min(len(key_normalized), len(name_normalized))
        if min_length >= 5:  # Only do fuzzy match if both are substantial
            if key_normalized in name_normalized or name_normalized in key_normalized:
                return _extract_rank(value)
    
    # Last resort: try original (non-normalized) substring match
    name_lower = venue_name.lower().strip()
    for key, value in VENUE_RANKS.items():
        if key in name_lower or name_lower in key:
            return _extract_rank(value)
            
    return "Unranked"
